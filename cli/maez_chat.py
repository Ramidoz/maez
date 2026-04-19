# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
maez_chat.py — Terminal chat for Maez (Rich + prompt_toolkit).

Same stack aider uses. Flows inline in the terminal (no full-screen
takeover), renders markdown with real code block syntax highlighting,
and stays in pure Python. Primary purpose right now: a clean debug
surface while we build out Maez. Not the final consumer product.

Run:
    /home/rohit/maez/.venv/bin/python3 -m cli.maez_chat

Slash commands (type at the prompt):
    /help       show commands
    /status     service + brain health
    /proposals  list pending dream proposals
    /signals    recent iPhone signals
    /ambient    current ambient context snapshot
    /deep       re-enable thinking mode for one turn
    /clear      clear screen (history retained)
    /quit, /q   exit

Keyboard:
    Enter       send message
    Ctrl+C      cancel current stream (or exit at prompt)
    Ctrl+D      exit
    Up / Down   history
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Generator, Iterator, Optional

# Bootstrap path
_MAEZ_ROOT = Path(__file__).resolve().parent.parent
if str(_MAEZ_ROOT) not in sys.path:
    sys.path.insert(0, str(_MAEZ_ROOT))

from dotenv import load_dotenv
load_dotenv(_MAEZ_ROOT / "config" / ".env")

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.table import Table

from core import identity, soul_loader
from core.ambient_format import ambient_prompt_block
from core.ambient import ambient_context, current_coords, latest_per_kind
from core.action_engine import _covenant_violation as _covenant_check
from skills import claude_router

# ── config ─────────────────────────────────────────────────────────────
LOCAL_BRAIN_URL = os.environ.get("MAEZ_LLAMACPP_URL", "http://127.0.0.1:8080/v1")
LOCAL_MODEL = os.environ.get("MAEZ_LLAMACPP_MODEL", "qwen36-35b-sft")
HISTORY_PATH = _MAEZ_ROOT / "logs" / ".maez_chat_history"

# Tool-loop limits
MAX_TOOL_ITERATIONS = 5  # avoid infinite agent loops
TOOL_TIMEOUT_SEC = 60    # per-command shell timeout
TOOL_OUTPUT_MAX = 4000   # cap per-command output fed back to the model

# Regex to pull ```bash ...``` / ```sh ...``` / ```shell ...``` fences
BASH_FENCE_RE = re.compile(
    r"```(?:bash|sh|zsh|shell)?\s*\n(.*?)```",
    re.DOTALL,
)

console = Console()


# ── turn ───────────────────────────────────────────────────────────────
@dataclass
class Turn:
    role: str
    content: str = ""
    thinking: str = ""
    meta: str = ""


# ── streaming ──────────────────────────────────────────────────────────
def _stream_local(messages: list[dict], max_tokens: int = 6000,
                  temperature: float = 0.7, think: bool = False
                  ) -> Iterator[tuple[str, str]]:
    """Yield (kind, chunk) from local llama-server. kind ∈ {thinking, content}."""
    body = {
        "model": LOCAL_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": bool(think)},
    }
    req = urllib.request.Request(
        f"{LOCAL_BRAIN_URL}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                    delta = obj["choices"][0]["delta"] or {}
                    if delta.get("reasoning_content"):
                        yield ("thinking", delta["reasoning_content"])
                    if delta.get("content"):
                        yield ("content", delta["content"])
                except Exception:
                    continue
    except Exception as e:
        yield ("content", f"\n_[local stream error: {e}]_")


def _stream_claude(system: str, messages: list[dict], tier: str,
                   max_tokens: int = 4096) -> Iterator[tuple[str, str]]:
    """Yield (kind, chunk) from Claude. kind is always content here."""
    try:
        client = claude_router._get_client()
    except Exception as e:
        yield ("content", f"_[claude unavailable: {e}]_")
        return
    model = claude_router.MODEL_OPUS if tier == "opus" else claude_router.MODEL_SONNET
    api_messages = [m for m in messages if m.get("role") != "system"]
    try:
        with client.messages.stream(
            model=model, system=system, messages=api_messages,
            max_tokens=max_tokens,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield ("content", text)
    except Exception as e:
        yield ("content", f"\n_[claude stream error: {e}]_")


# ── rendering ──────────────────────────────────────────────────────────
def _role_header(role: str, meta: str = "") -> Text:
    t = Text()
    if role == "user":
        t.append("you", style="bold cyan")
    elif role == "assistant":
        t.append("maez", style="bold magenta")
    elif role == "system":
        t.append("system", style="dim")
    else:
        t.append(role, style="dim")
    if meta:
        t.append(f"  · {meta}", style="dim italic")
    return t


def _thinking_status(thinking: str, done: bool) -> Text:
    lines = thinking.count("\n") + 1 if thinking else 0
    t = Text()
    if done:
        t.append(f"(hidden thinking · {lines} lines — Ctrl+T pending for next session)",
                 style="dim italic")
    else:
        t.append(f"thinking… ", style="dim italic")
        t.append(f"[{lines} lines so far]", style="dim")
    return t


# ── tool-use loop ──────────────────────────────────────────────────────
# Pattern adapted from QwenLM/qwen-code (Apache 2.0) and the prior Jarvis
# loop in the legacy cli.py. When Maez emits a ```bash``` fence, the loop
# proposes it as an approval card, runs via subprocess on approve, and
# feeds real output back to the model for synthesis.

@dataclass
class ToolRun:
    cmd: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    skipped: bool = False
    refused_reason: str = ""


def extract_shell_commands(text: str) -> list[str]:
    """Pull ```bash/sh/shell``` blocks out of model output.
    Returns deduplicated, stripped command strings in order of appearance.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in BASH_FENCE_RE.finditer(text):
        block = m.group(1).strip()
        if not block or block in seen:
            continue
        seen.add(block)
        out.append(block)
    return out


def safety_check(cmd: str) -> Optional[str]:
    """Extra defensive layer on top of core.action_engine's covenant regex.

    Philosophy: Rohit's explicit `y` approval IS the permission for this
    session. We only hard-refuse things that would bypass covenant or
    destroy the Maez tree even with approval — those aren't one-off
    mistakes, they're category failures.

    sudo is intentionally NOT hard-refused here. When Maez proposes a
    sudo command, it goes through the same [y/N/q] approval as any
    other command. Rohit sees it, types y if he consents.

    Returns a reason string if hard-blocked, None if OK (still needs
    interactive approval downstream).
    """
    low = cmd.lower()
    # Covenant regex first — verb+protected-surface combinations.
    reason = _covenant_check(low)
    if reason:
        return f"covenant: {reason}"
    # rm -rf — always refuse, even with sudo. This is never what you want
    # from an agent loop; a human should do irreversible destruction manually.
    if re.search(r"\brm\s+-[rRfF]*[rRfF]", low):
        return "rm -rf forbidden from agent loop (run manually if intended)"
    # Any mutation targeting the Maez tree via shell — block even with
    # approval. Code changes go through edit_soul_section / evolution
    # engine with proper diffs and rollback, not ad-hoc sed/tee.
    maez_root = str(_MAEZ_ROOT).lower()
    if maez_root in low and re.search(
        r"\b(rm\s|mv\s|sed\s+-i|tee\s+|>\s*|>>\s*|truncate\s|chmod\s|chown\s)",
        low,
    ):
        return (f"write/modify inside {maez_root} needs to go through the "
                f"evolution engine, not an ad-hoc shell command")
    return None


def _run_shell(cmd: str) -> tuple[str, str, int]:
    """Run a shell command, capture output. Truncates to TOOL_OUTPUT_MAX."""
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True, text=True,
            timeout=TOOL_TIMEOUT_SEC,
        )
        out = (r.stdout or "")[:TOOL_OUTPUT_MAX]
        err = (r.stderr or "")[:TOOL_OUTPUT_MAX]
        return out, err, r.returncode
    except subprocess.TimeoutExpired:
        return "", f"[timeout after {TOOL_TIMEOUT_SEC}s]", 124
    except Exception as e:
        return "", f"[runner error: {e}]", 1


def render_approval(cmd: str, refused: Optional[str]) -> None:
    """Show a proposed command in a Rich panel. Highlights sudo in red border."""
    is_sudo = bool(re.search(r"\bsudo\b", cmd.lower()))
    body_lines = [f"[cyan]{cmd.strip()}[/cyan]"]
    if is_sudo:
        body_lines.append("")
        body_lines.append("[red bold]⚠ elevated (sudo) — will prompt for your password[/red bold]")
    if refused:
        body_lines.append("")
        body_lines.append(f"[red]safety refuses: {refused}[/red]")
    title = "proposed shell"
    if is_sudo and not refused:
        title = "proposed shell · elevated"
    border = "red" if refused else ("magenta" if is_sudo else "yellow")
    console.print(Panel("\n".join(body_lines),
                        title=title,
                        border_style=border,
                        expand=False))


def render_tool_result(tr: ToolRun) -> None:
    """Show the real output of a tool run."""
    if tr.skipped:
        console.print(Panel(f"[dim]{tr.refused_reason or 'skipped'}[/dim]",
                            title="skipped",
                            border_style="dim", expand=False))
        return
    status_color = "green" if tr.returncode == 0 else "red"
    body = []
    if tr.stdout.strip():
        body.append(f"[dim]stdout:[/dim]\n{tr.stdout.rstrip()}")
    if tr.stderr.strip():
        body.append(f"[dim]stderr:[/dim]\n[yellow]{tr.stderr.rstrip()}[/yellow]")
    if not body:
        body.append("[dim](no output)[/dim]")
    console.print(Panel(
        "\n".join(body),
        title=f"exit {tr.returncode}",
        border_style=status_color, expand=False,
    ))


def format_tool_results_for_model(runs: list[ToolRun]) -> str:
    """Produce a single message the model can read as real tool output."""
    lines = ["I ran these commands and these are the actual outputs:\n"]
    for i, tr in enumerate(runs, 1):
        lines.append(f"### command {i}")
        lines.append("```bash")
        lines.append(tr.cmd.strip())
        lines.append("```")
        if tr.skipped:
            lines.append(f"_(skipped: {tr.refused_reason or 'user declined'})_")
            lines.append("")
            continue
        lines.append(f"exit code: {tr.returncode}")
        if tr.stdout.strip():
            lines.append("stdout:")
            lines.append("```")
            lines.append(tr.stdout.rstrip())
            lines.append("```")
        if tr.stderr.strip():
            lines.append("stderr:")
            lines.append("```")
            lines.append(tr.stderr.rstrip())
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


# ── chat session ───────────────────────────────────────────────────────
class ChatSession:

    def __init__(self):
        self.turns: list[Turn] = []
        self.session = PromptSession(history=FileHistory(str(HISTORY_PATH)))
        self._stop_stream = threading.Event()
        self._deep_once = False  # re-enable thinking for one turn
        self.commands: dict[str, Callable[[str], None]] = {
            "/help": self.cmd_help,
            "/?": self.cmd_help,
            "/status": self.cmd_status,
            "/proposals": self.cmd_proposals,
            "/signals": self.cmd_signals,
            "/ambient": self.cmd_ambient,
            "/deep": self.cmd_deep,
            "/clear": self.cmd_clear,
            "/quit": self.cmd_quit,
            "/q": self.cmd_quit,
            "/exit": self.cmd_quit,
        }

    # ── banner ──
    def banner(self):
        name = identity.display_name()
        jarvis = "on" if identity.jarvis_tier() else "off"
        place = current_coords()[2]
        console.print()
        console.print(Rule(Text.from_markup(
            f"[bold magenta]maez[/bold magenta] "
            f"[dim]· {name}'s Maez · brain={LOCAL_MODEL} · jarvis={jarvis} · {place}[/dim]"
        )))
        console.print(Text.from_markup(
            "[dim]/help for commands · Ctrl+C cancels · Ctrl+D exits[/dim]\n"
        ))

    # ── main loop ──
    def run(self):
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.banner()
        while True:
            try:
                text = self.session.prompt(
                    HTML("<ansibrightcyan>› </ansibrightcyan>"),
                    style=Style.from_dict({"": "ansidefault"}),
                ).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("[dim]\nbye.[/dim]")
                return
            if not text:
                continue
            if text.startswith("/"):
                self._dispatch_command(text)
            else:
                self._handle_chat(text)

    # ── commands ──
    def _dispatch_command(self, text: str):
        parts = text.split(None, 1)
        name = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        fn = self.commands.get(name)
        if not fn:
            console.print(f"[dim red]unknown command: {name}[/dim red]  "
                          f"[dim](try /help)[/dim]")
            return
        try:
            fn(arg)
        except Exception as e:
            console.print(f"[red]command failed: {e}[/red]")

    def cmd_help(self, _: str):
        table = Table(show_header=False, box=None, padding=(0, 2))
        rows = [
            ("/help, /?",       "show this"),
            ("/status",         "service + brain health"),
            ("/proposals",      "pending dream proposals"),
            ("/signals",        "recent iPhone signals"),
            ("/ambient",        "current ambient snapshot (weather, window, signals)"),
            ("/deep",           "re-enable thinking mode for the next turn"),
            ("/clear",          "clear screen"),
            ("/quit, /q",       "exit"),
        ]
        for k, v in rows:
            table.add_row(Text(k, style="bold"), Text(v, style="dim"))
        console.print(Panel(table, title="commands", border_style="dim", expand=False))

    def cmd_status(self, _: str):
        import subprocess
        def svc_active(name: str) -> str:
            try:
                r = subprocess.run(["systemctl", "is-active", name],
                                   capture_output=True, text=True, timeout=3)
                return r.stdout.strip()
            except Exception:
                return "?"
        svcs = [
            "llama-server.service",
            "llama-server-vision.service",
            "maez.service",
            "maez-web.service",
        ]
        table = Table(show_header=False, box=None, padding=(0, 2))
        for s in svcs:
            status = svc_active(s)
            color = "green" if status == "active" else "red" if status != "?" else "yellow"
            table.add_row(Text(s, style="bold"),
                          Text(status, style=color))
        # brain latency probe
        try:
            t0 = time.time()
            with urllib.request.urlopen(f"{LOCAL_BRAIN_URL}/models", timeout=3) as r:
                dt = (time.time() - t0) * 1000
                table.add_row(Text("brain probe", style="bold"),
                              Text(f"HTTP {r.status} · {dt:.0f}ms", style="green"))
        except Exception as e:
            table.add_row(Text("brain probe", style="bold"),
                          Text(f"FAIL: {e}", style="red"))
        console.print(Panel(table, title="status", border_style="dim", expand=False))

    def cmd_proposals(self, _: str):
        try:
            import sqlite3
            db = _MAEZ_ROOT / "memory" / "dream_proposals.db"
            if not db.exists():
                console.print("[dim](no dream_proposals.db — daemon hasn't proposed any yet)[/dim]")
                return
            con = sqlite3.connect(str(db))
            rows = con.execute(
                "SELECT id, proposal_type, substr(insight, 1, 120), created_at "
                "FROM dream_proposals WHERE status='pending' ORDER BY id DESC LIMIT 10"
            ).fetchall()
            con.close()
        except Exception as e:
            console.print(f"[red]proposal query failed: {e}[/red]")
            return
        if not rows:
            console.print("[dim](no pending proposals)[/dim]")
            return
        table = Table(title="pending dream proposals", show_header=True, box=None,
                      title_style="bold", header_style="dim")
        table.add_column("#", justify="right", style="bold")
        table.add_column("type", style="cyan")
        table.add_column("insight", overflow="fold")
        for pid, ptype, insight, created in rows:
            table.add_row(str(pid), ptype, (insight or "").replace("\n", " "))
        console.print(table)

    def cmd_signals(self, _: str):
        try:
            snap = latest_per_kind(max_age_days=2)
        except Exception as e:
            console.print(f"[red]signals read failed: {e}[/red]")
            return
        if not snap:
            console.print("[dim](no recent iPhone signals)[/dim]")
            return
        table = Table(show_header=True, box=None, header_style="dim")
        table.add_column("kind", style="cyan")
        table.add_column("when", style="dim")
        table.add_column("data", overflow="fold")
        for kind in sorted(snap):
            entry = snap[kind]
            ts = entry.get("timestamp", "")[:19]
            data = entry.get("data") or {}
            table.add_row(kind, ts, json.dumps(data, ensure_ascii=False)[:100])
        console.print(Panel(table, title="recent iPhone signals",
                            border_style="dim", expand=False))

    def cmd_ambient(self, _: str):
        try:
            ctx = ambient_context()
        except Exception as e:
            console.print(f"[red]ambient snapshot failed: {e}[/red]")
            return
        lat, lon, place = current_coords()
        weather = ctx.get("weather") or {}
        window = ctx.get("active_window") or {}
        lines = [
            f"[bold]place[/bold]    {place}  ({lat}, {lon}; source: {ctx.get('coords_source')})",
            f"[bold]weather[/bold]  {weather.get('temp_c', '?')}°C · "
            f"{weather.get('conditions', '?')} · tz={weather.get('timezone', '?')}",
        ]
        if window.get("title"):
            lines.append(f"[bold]window[/bold]   {window['title']} ({window.get('class')})")
        else:
            lines.append(f"[bold]window[/bold]   [dim]not detected (no DISPLAY or Wayland)[/dim]")
        sigs = ctx.get("signals_latest") or {}
        if sigs:
            lines.append(f"[bold]signals[/bold]  {', '.join(sorted(sigs))}")
        console.print(Panel("\n".join(lines), title="ambient snapshot",
                            border_style="dim", expand=False))

    def cmd_deep(self, _: str):
        self._deep_once = True
        console.print("[dim italic](thinking mode armed — next turn will use "
                      "Qwen3 reasoning)[/dim italic]")

    def cmd_clear(self, _: str):
        console.clear()
        self.banner()

    def cmd_quit(self, _: str):
        console.print("[dim]bye.[/dim]")
        sys.exit(0)

    # ── chat turn ──
    def _handle_chat(self, user_text: str):
        # Assemble messages
        self.turns.append(Turn("user", user_text))
        soul = soul_loader.current_soul()
        try:
            ambient = ambient_prompt_block()
        except Exception:
            ambient = ""
        system_prompt = soul + ("\n\n" + ambient if ambient else "")

        decision = claude_router.classify(user_text)
        profile_id = identity.user_profile_id()
        route_external = (
            decision.route == "external"
            and identity.jarvis_tier()
            and claude_router.jarvis_tier_enabled(profile_id)
        )
        think_opt = self._deep_once and not route_external
        if self._deep_once:
            self._deep_once = False
        meta_base = f"claude:{decision.tier}" if route_external else "local"

        # Agent-style loop: model may propose commands, we run them (with
        # approval), feed results back, and let the model synthesize.
        tool_history: list[ToolRun] = []
        iteration_suffix = ""  # appended message text for continuation turns
        for iteration in range(MAX_TOOL_ITERATIONS):
            meta = meta_base + (f" · iter {iteration+1}" if iteration else "")
            console.print(_role_header("assistant", meta))

            # Build the live messages for THIS iteration, including any
            # running tool-result message appended after the user turn.
            history_pairs = [
                {"role": t.role, "content": t.content}
                for t in self.turns if t.role in ("user", "assistant") and t.content
            ]
            history_pairs.append({"role": "user", "content": user_text})
            if iteration_suffix:
                history_pairs.append({"role": "user", "content": iteration_suffix})
            messages = ([{"role": "system", "content": system_prompt}]
                        + history_pairs)

            assistant = Turn("assistant", meta=meta)
            self.turns.append(assistant)
            self._stop_stream.clear()
            original_sigint = signal.getsignal(signal.SIGINT)
            def _handle_sigint(sig, frame):
                self._stop_stream.set()
            signal.signal(signal.SIGINT, _handle_sigint)

            try:
                if route_external:
                    gen = _stream_claude(system_prompt, history_pairs,
                                         decision.tier or "sonnet")
                else:
                    gen = _stream_local(messages, think=think_opt)

                last_render = 0.0
                RENDER_EVERY = 0.08

                def build_renderable(done: bool = False):
                    body = assistant.content
                    md = Markdown(body) if body else Text("…", style="dim")
                    parts: list = []
                    if assistant.thinking:
                        parts.append(_thinking_status(assistant.thinking, done))
                    parts.append(md)
                    return Group(*parts)

                with Live(build_renderable(), console=console,
                          refresh_per_second=12, transient=False,
                          auto_refresh=False) as live:
                    for kind, chunk in gen:
                        if self._stop_stream.is_set():
                            assistant.content += "\n\n_(interrupted)_"
                            live.update(build_renderable(done=True), refresh=True)
                            break
                        if kind == "thinking":
                            assistant.thinking += chunk
                        else:
                            assistant.content += chunk
                        now = time.time()
                        if now - last_render > RENDER_EVERY:
                            live.update(build_renderable(), refresh=True)
                            last_render = now
                    live.update(build_renderable(done=True), refresh=True)
            finally:
                signal.signal(signal.SIGINT, original_sigint)
                console.print()

            # Interrupted → exit the whole agent loop
            if self._stop_stream.is_set():
                break

            # Look for proposed shell commands; if none, we're done
            commands = extract_shell_commands(assistant.content)
            if not commands:
                break

            console.print(Text.from_markup(
                f"[dim]— {len(commands)} shell command(s) proposed —[/dim]"
            ))

            runs_this_iter: list[ToolRun] = []
            for cmd in commands:
                refused = safety_check(cmd)
                render_approval(cmd, refused)
                if refused:
                    tr = ToolRun(cmd=cmd, skipped=True,
                                 refused_reason=refused)
                    render_tool_result(tr)
                    runs_this_iter.append(tr)
                    tool_history.append(tr)
                    continue
                # Prompt user
                try:
                    ans = self.session.prompt(
                        HTML("<ansibrightcyan>run? [y/N/q]:</ansibrightcyan> "),
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "q"
                if ans == "q":
                    tr = ToolRun(cmd=cmd, skipped=True, refused_reason="user quit approvals")
                    runs_this_iter.append(tr)
                    tool_history.append(tr)
                    break
                if ans not in ("y", "yes"):
                    tr = ToolRun(cmd=cmd, skipped=True, refused_reason="user declined")
                    render_tool_result(tr)
                    runs_this_iter.append(tr)
                    tool_history.append(tr)
                    continue
                # Run
                with console.status("[dim]running…[/dim]", spinner="dots"):
                    out, err, rc = _run_shell(cmd)
                tr = ToolRun(cmd=cmd, stdout=out, stderr=err, returncode=rc)
                render_tool_result(tr)
                runs_this_iter.append(tr)
                tool_history.append(tr)

            # If user quit approvals OR all commands were skipped, stop looping
            if any(tr.skipped and tr.refused_reason == "user quit approvals"
                   for tr in runs_this_iter):
                break
            if all(tr.skipped for tr in runs_this_iter):
                # Nothing actually ran; don't continue the agent loop,
                # user doesn't want these commands.
                break

            # Feed real output back into the next iteration's context
            iteration_suffix = format_tool_results_for_model(runs_this_iter)
        else:
            console.print(Text.from_markup(
                f"[yellow dim]— tool loop hit max iterations ({MAX_TOOL_ITERATIONS}) —[/yellow dim]"
            ))

        # Trajectory log (final turn only — keeps log tidy)
        final_reply = self.turns[-1].content if self.turns else ""
        try:
            claude_router.log_trajectory({
                "profile_id": profile_id,
                "display": identity.display_name(),
                "channel": "cli",
                "message": user_text,
                "reply": final_reply,
                "source": meta_base,
                "decision": decision.to_dict(),
                "thinking_len": len(self.turns[-1].thinking) if self.turns else 0,
                "tool_runs": len([t for t in tool_history if not t.skipped]),
                "tool_skipped": len([t for t in tool_history if t.skipped]),
            })
        except Exception:
            pass


def main():
    try:
        ChatSession().run()
    except KeyboardInterrupt:
        console.print("[dim]\nbye.[/dim]")


if __name__ == "__main__":
    main()
