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

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

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
from core.tool_loop import (
    ToolRun, extract_shell_commands, safety_check,
    _run_shell, format_tool_results_for_model,
)
from skills import claude_router

# ── config ─────────────────────────────────────────────────────────────
LOCAL_BRAIN_URL = os.environ.get("MAEZ_LLAMACPP_URL", "http://127.0.0.1:8080/v1")
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL  # /etc/maez/model.env
LOCAL_MODEL = os.environ.get("MAEZ_LLAMACPP_MODEL", _PRIMARY_MODEL)
HISTORY_PATH = _MAEZ_ROOT / "logs" / ".maez_chat_history"

# Tool-loop iteration limits (CLI-specific — tool_loop.py has no concept of
# iteration count; that's a chat-surface policy, not a primitive).
MAX_TOOL_ITERATIONS = int(os.environ.get("MAEZ_MAX_TOOL_ITERS", "10"))
EXTEND_ITERATIONS_BY = int(os.environ.get("MAEZ_EXTEND_ITERS_BY", "10"))

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
        t.append("thinking… ", style="dim italic")
        t.append(f"[{lines} lines so far]", style="dim")
    return t


# ── tool-use loop ──────────────────────────────────────────────────────
# Pattern adapted from QwenLM/qwen-code (Apache 2.0) and the prior Jarvis
# loop in the legacy cli.py. When Maez emits a ```bash``` fence, the loop
# proposes it as an approval card, runs via subprocess on approve, and
# feeds real output back to the model for synthesis.
#
# The primitives (ToolRun, extract_shell_commands, safety_check, _run_shell,
# format_tool_results_for_model, BASH_FENCE_RE, TOOL_TIMEOUT_SEC,
# TOOL_OUTPUT_MAX) live in core.tool_loop so the daemon's wondering-cycle
# can share them. They're imported at the top of this file.


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


# ── chat session ───────────────────────────────────────────────────────
class ChatSession:

    def __init__(self):
        self.turns: list[Turn] = []
        self.session = PromptSession(history=FileHistory(str(HISTORY_PATH)))
        self._stop_stream = threading.Event()
        self._deep_once = False  # re-enable thinking for one turn
        # Per-turn routing override. None = use classifier. Set by /local,
        # /sonnet, /opus. Consumed after one turn.
        self._force_route_once: Optional[tuple[str, Optional[str]]] = None
        self.commands: dict[str, Callable[[str], None]] = {
            "/help": self.cmd_help,
            "/?": self.cmd_help,
            "/status": self.cmd_status,
            "/proposals": self.cmd_proposals,
            "/signals": self.cmd_signals,
            "/ambient": self.cmd_ambient,
            "/deep": self.cmd_deep,
            "/local": self.cmd_force_local,
            "/sonnet": self.cmd_force_sonnet,
            "/opus": self.cmd_force_opus,
            "/route": self.cmd_show_route,
            "/wonder": self.cmd_wonder,
            "/wonderings": self.cmd_wonderings,
            "/label": self.cmd_label,
            "/labels": self.cmd_labels,
            "/memory": self.cmd_memory,
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
            ("/route",          "show routing override for next turn"),
            ("/local",          "force next turn → local brain"),
            ("/sonnet",         "force next turn → Claude Sonnet 4.6"),
            ("/opus",           "force next turn → Claude Opus 4.7"),
            ("/deep",           "re-enable thinking mode for the next turn"),
            ("/wonder <q>",     "seed a wondering for the daemon to explore"),
            ("/wonderings",     "list open + recent wonderings and probes"),
            ("/label <id> <good|bad> [-- note]",
                                "label a trace turn for KTO-shaped feedback"),
            ("/labels",         "show recent trace labels + counts"),
            ("/memory [query]", "memory introspection: stats + recent core/episodes; with arg, token-overlap search"),
            ("/clear",          "clear screen"),
            ("/quit, /q",       "exit"),
        ]
        for k, v in rows:
            table.add_row(Text(k, style="bold"), Text(v, style="dim"))
        console.print(Panel(table, title="commands", border_style="dim", expand=False))

    def cmd_status(self, _: str):
        def svc_active(name: str) -> str:
            try:
                r = subprocess.run(["systemctl", "is-active", name],
                                   capture_output=True, text=True, timeout=3)
                return r.stdout.strip()
            except Exception:
                return "?"
        # 2026-04-23 Commit 6: removed stale "llama-server-vision.service"
        # from the /status list — no such unit exists on the machine.
        # Vision is retired per ADR 0009; re-add this label when a
        # multimodal endpoint is re-provisioned as its own systemd unit.
        svcs = [
            "llama-server.service",
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
            lines.append("[bold]window[/bold]   [dim]not detected (no DISPLAY or Wayland)[/dim]")
        sigs = ctx.get("signals_latest") or {}
        if sigs:
            lines.append(f"[bold]signals[/bold]  {', '.join(sorted(sigs))}")
        console.print(Panel("\n".join(lines), title="ambient snapshot",
                            border_style="dim", expand=False))

    def cmd_deep(self, _: str):
        self._deep_once = True
        console.print("[dim italic](thinking mode armed — next turn will use "
                      "Qwen3 reasoning)[/dim italic]")

    def cmd_force_local(self, _: str):
        self._force_route_once = ("local", None)
        console.print("[dim italic](next turn will route local, "
                      "regardless of classifier)[/dim italic]")

    def cmd_force_sonnet(self, _: str):
        self._force_route_once = ("external", "sonnet")
        console.print("[dim italic](next turn will route claude:sonnet)[/dim italic]")

    def cmd_force_opus(self, _: str):
        self._force_route_once = ("external", "opus")
        console.print("[dim italic](next turn will route claude:opus)[/dim italic]")

    def cmd_show_route(self, _: str):
        if self._force_route_once:
            route, tier = self._force_route_once
            tag = f"{route}" + (f":{tier}" if tier else "")
            console.print(f"[cyan]next turn forced: {tag}[/cyan]")
        else:
            console.print("[dim](no override — classifier decides next turn)[/dim]")

    def cmd_wonder(self, arg: str):
        question = (arg or "").strip()
        if not question:
            console.print("[yellow]usage: /wonder <question>[/yellow]")
            return
        from core.wonderings import get_store
        wid = get_store().add(question, source="chat")
        console.print(f"[green]wondering #{wid} seeded.[/green] "
                      f"[dim]The daemon will advance it on upcoming cycles.[/dim]")

    def cmd_wonderings(self, _: str):
        from core.wonderings import get_store
        store = get_store()
        rows = store.list_all(limit=15)
        if not rows:
            console.print("[dim](no wonderings yet — /wonder <question> to seed one)[/dim]")
            return
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("#", style="dim", width=4)
        table.add_column("status", width=22)
        table.add_column("adv", width=4)
        table.add_column("defer", width=5)
        # Slice 2 Session 3 — pursuit history per wondering. ``surf``
        # is total proactive surfacings; ``last surf`` is hours since
        # the most recent surface (or '·' if never).
        table.add_column("surf", width=5)
        table.add_column("last surf", width=10)
        table.add_column("question")
        import time as _time
        for w in rows:
            pursuit_count = w.get("pursuit_count") or 0
            last_pursuit_at = w.get("last_pursuit_at")
            if last_pursuit_at:
                age_h = max(0.0, (_time.time() - float(last_pursuit_at)) / 3600.0)
                if age_h < 1:
                    last_surf = f"{int(age_h * 60)}m ago"
                elif age_h < 24:
                    last_surf = f"{age_h:.1f}h ago"
                else:
                    last_surf = f"{age_h / 24:.1f}d ago"
            else:
                last_surf = "·"
            table.add_row(
                str(w["id"]), w["status"], str(w["advance_count"]),
                str(w["deferral_count"]),
                str(pursuit_count) if pursuit_count else "·",
                last_surf,
                (w["question"] or "")[:80],
            )
        console.print(Panel(table, title="wonderings", border_style="dim", expand=False))
        # Show probes for the most recent open/active wondering
        focus = next((w for w in rows if w["status"] in ("open", "active",
                                                         "blocked_pending_approval")), None)
        if focus:
            probes = store.recent_probes(focus["id"], limit=5)
            if probes:
                ptable = Table(show_header=True, header_style="bold",
                                box=None, padding=(0, 1))
                ptable.add_column("rc", width=4)
                ptable.add_column("tied", width=5)
                ptable.add_column("cmd", max_width=40, overflow="fold")
                ptable.add_column("learning", overflow="fold")
                for p in reversed(probes):
                    ptable.add_row(
                        str(p.get("returncode")),
                        "✓" if p.get("evidence_tied") else "·",
                        (p.get("cmd") or "")[:60],
                        (p.get("learning") or "")[:120],
                    )
                console.print(Panel(
                    ptable,
                    title=f"recent probes · wondering #{focus['id']}",
                    border_style="dim", expand=False,
                ))

    def cmd_label(self, arg: str):
        """``/label <trace_id> <good|bad> [--kind axis] [--note "text"]``
        — pin a binary KTO-shaped label to a specific chat turn.
        Slice 5 annotation surface; feeds the labelled-corpus
        foundation the audit identified for owner-feedback training.

        Re-labelling the same ``(trace_id, kind)`` updates rather
        than duplicates. Quotes work via shlex parsing, so notes
        with embedded spaces don't need escaping."""
        import shlex
        import sqlite3 as _sq
        from core.feedback.labels import LabelStore

        # Audit M1+M2: shlex-based parser. Handles quoted notes,
        # both flag orderings, and surfaces unknown flags as a
        # usage error instead of silently dropping tokens.
        try:
            tokens = shlex.split(arg)
        except ValueError as exc:
            console.print(f"[red]parse error: {exc}[/red]")
            return
        if len(tokens) < 2:
            console.print(
                "[dim red]usage:[/dim red] "
                "/label <trace_id> <good|bad> [--kind axis] [--note text]"
            )
            return
        trace_id, label = tokens[0].strip(), tokens[1].strip().lower()
        rest = tokens[2:]
        kind = "overall"
        note: "str | None" = None
        i = 0
        while i < len(rest):
            tok = rest[i]
            if tok == "--kind" and i + 1 < len(rest):
                kind = rest[i + 1].strip().lower() or "overall"
                i += 2
            elif tok == "--note" and i + 1 < len(rest):
                note = rest[i + 1]
                i += 2
            elif tok == "--":
                # Legacy form: everything after `--` is the note.
                note = " ".join(rest[i + 1:])
                break
            elif tok.startswith("--"):
                console.print(
                    f"[red]unknown flag: {tok}[/red]  "
                    f"[dim](use --kind / --note)[/dim]"
                )
                return
            else:
                # Bare positional token after the label — treat as
                # the note (legacy convenience). Take rest of tokens
                # joined so multi-word notes don't drop tokens.
                note = " ".join(rest[i:])
                break
        # Audit Explore #1: warn (don't block) when the trace_id
        # doesn't appear in any recent JSONL — owner can still
        # label, but a typo gets flagged immediately rather than
        # silently joining to nothing downstream.
        from core.feedback.labels import trace_id_exists_in_jsonl

        if not trace_id_exists_in_jsonl(trace_id):
            console.print(
                f"[yellow]warning:[/yellow] trace_id "
                f"[bold]{trace_id}[/bold] not found in recent JSONL "
                f"— labelling anyway (typo? old trace?)"
            )
        # Audit M3: catch DB errors (race, schema mismatch) plus the
        # validation ValueError so the REPL never crashes on a label.
        try:
            store = LabelStore()
            row_id = store.add_label(
                trace_id=trace_id, label=label, kind=kind, note=note,
            )
        except ValueError as exc:
            console.print(f"[red]label rejected: {exc}[/red]")
            return
        except _sq.DatabaseError as exc:
            console.print(f"[red]label store error: {exc}[/red]")
            return
        ind = "✓" if label == "good" else "✗"
        console.print(
            f"[green]labelled[/green] [dim]#{row_id}[/dim] "
            f"trace=[bold]{trace_id}[/bold] "
            f"{ind} {label} kind=[dim]{kind}[/dim]"
            + (f" note=[dim]{note}[/dim]" if note else "")
        )

    def cmd_labels(self, _: str):
        """Show recent trace labels + per-label / per-kind counts."""
        from core.feedback.labels import LabelStore

        store = LabelStore()
        rows = store.recent(limit=15)
        stats = store.stats()
        if not rows:
            console.print(
                "[dim](no trace labels yet — "
                "/label <trace_id> good|bad to seed one)[/dim]"
            )
            return
        table = Table(show_header=True, header_style="bold",
                      box=None, padding=(0, 1))
        table.add_column("when", width=20)
        table.add_column("trace", width=12)
        table.add_column("label", width=6)
        table.add_column("kind", width=10)
        table.add_column("note", overflow="fold")
        for r in rows:
            ts = (r.get("created_at") or "")[:19]
            ind = "✓" if r["label"] == "good" else "✗"
            table.add_row(
                ts,
                (r["trace_id"] or "")[:12],
                f"{ind} {r['label']}",
                (r.get("kind") or "overall"),
                (r.get("note") or "")[:80],
            )
        console.print(Panel(
            table, title="trace labels (recent)",
            border_style="dim", expand=False,
        ))
        # Stats row.
        stats_line = (
            f"[bold]total[/bold] {stats.get('total', 0)} · "
            f"[green]good[/green] {stats.get('good', 0)} · "
            f"[red]bad[/red] {stats.get('bad', 0)}"
        )
        if stats.get("latest_at"):
            stats_line += f" · [dim]latest {stats['latest_at']}[/dim]"
        console.print(stats_line)

    def cmd_memory(self, arg: str):
        """``/memory [query]`` — Letta-style introspection over the
        lived memory layer. No args: stats summary + recent core +
        recent episodes. With args: token-overlap search across
        core+daily."""
        from core.agent_tools.memory_view import (
            list_recent_core,
            list_recent_episodes,
            memory_stats,
            search_memories,
            summarize_for_prompt,
        )
        from core import paths as _paths
        from core.memory.episodes import EpisodeStore

        # Reuse the singleton MM if one is cached on this chat;
        # otherwise lazy-build + cache so repeated /memory calls
        # don't spawn fresh Chroma clients.
        mm = getattr(self, "_memory_view_mm", None)
        if mm is None:
            from memory.memory_manager import MemoryManager
            mm = MemoryManager()
            self._memory_view_mm = mm
        ep_store = getattr(self, "_memory_view_eps", None)
        if ep_store is None:
            ep_store = EpisodeStore(
                str(_paths.memory_dir() / "lived_episodes.db")
            )
            self._memory_view_eps = ep_store
        query = (arg or "").strip()
        if query:
            results = search_memories(mm, query=query, limit=10)
            if not results:
                console.print(f"[dim](no matches for '{query}')[/dim]")
                return
            table = Table(show_header=True, header_style="bold",
                          box=None, padding=(0, 1))
            table.add_column("id", width=12)
            table.add_column("content", overflow="fold")
            for r in results:
                table.add_row(
                    (r.get("id") or "")[:12],
                    (r.get("content") or "")[:200],
                )
            console.print(Panel(
                table, title=f"memory search: '{query}'",
                border_style="dim", expand=False,
            ))
            return
        stats = memory_stats(mm, ep_store)
        console.print(Text.from_markup(summarize_for_prompt(mm, ep_store)))
        cores = list_recent_core(mm, limit=5)
        if cores:
            t = Table(show_header=True, header_style="bold",
                      box=None, padding=(0, 1))
            t.add_column("when", width=20)
            t.add_column("source", width=18)
            t.add_column("content", overflow="fold")
            for c in cores:
                meta = c.get("metadata") or {}
                ts = (meta.get("timestamp") or meta.get("created_at") or "")[:19]
                t.add_row(
                    ts,
                    (meta.get("source") or "")[:18],
                    (c.get("content") or "")[:160],
                )
            console.print(Panel(
                t, title="recent core memories",
                border_style="dim", expand=False,
            ))
        eps = list_recent_episodes(ep_store, limit=5)
        if eps:
            t = Table(show_header=True, header_style="bold",
                      box=None, padding=(0, 1))
            t.add_column("id", width=14)
            t.add_column("title", overflow="fold")
            for e in eps:
                t.add_row(
                    str(e.get("id") or "")[:14],
                    (e.get("title") or e.get("summary") or "")[:120],
                )
            console.print(Panel(
                t, title="recent active episodes",
                border_style="dim", expand=False,
            ))
        _ = stats  # already rendered via summary

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

        # Inner-residue detection: if the user text carries clear
        # rejection markers, record a residue event so the next turn's
        # prompt reflects the weight. Silent on failure.
        try:
            from core import inner_residue as _residue
            if _residue.detect_user_rejection(user_text):
                _residue.record(kind="user_rejection",
                                context={"surface": "cli"})
        except Exception:
            pass

        # Blanket-approval detection. See core/approval_sessions.py.
        try:
            from core import approval_sessions as _approvals
            _approvals.detect_and_grant(user_text)
        except Exception:
            pass

        soul = soul_loader.current_soul()
        try:
            ambient = ambient_prompt_block()
        except Exception:
            ambient = ""
        system_prompt = soul + ("\n\n" + ambient if ambient else "")

        # Capability registry injection — gives the model grounded facts
        # to consult for self-description before it generates. Added
        # 2026-04-20 after the Maelstrom-class fabrications demonstrated
        # that the model invents modules, schedules, and postconditions
        # when asked "what do you have?" questions. Silent on failure.
        try:
            from core.capability_registry import prompt_snippet as _cap_snippet
            system_prompt += "\n\n" + _cap_snippet()
        except Exception:
            pass

        # Web search injection — mirrors daemon.handle_message so the model
        # sees REAL search results instead of emitting `[WEB SEARCH] "..."`
        # pseudo-markers and stopping. Silent on failure; a missing result
        # just falls through to normal chat.
        try:
            from skills.web_search import (
                search as _web_search, format_for_context as _web_format,
                needs_web_search as _web_needs, search_rss as _web_rss,
                is_news_query as _web_is_news,
            )
            if _web_needs(user_text):
                console.print(Text.from_markup(
                    f"[dim]— web search: {user_text[:80]} —[/dim]"
                ))
                _sr = (_web_rss(user_text, max_results=5)
                       if _web_is_news(user_text)
                       else _web_search(user_text, max_results=3))
                if _sr.get("success"):
                    system_prompt += (
                        "\n\n" + _web_format(_sr)
                        + "\n\nINSTRUCTION: Real search results above are "
                        "the source of truth for any factual claim you make "
                        "this turn. Synthesize into 3-5 sentences — do NOT "
                        "list raw headlines and do NOT emit `[WEB SEARCH]` "
                        "markers yourself."
                    )
        except Exception:
            pass

        decision = claude_router.classify(user_text)
        # Apply /local /sonnet /opus override if armed
        if self._force_route_once:
            forced_route, forced_tier = self._force_route_once
            self._force_route_once = None
            if forced_route == "local":
                decision.route = "local"
                decision.tier = None
                decision.reason = "manual:/local"
            else:
                decision.route = "external"
                decision.tier = forced_tier or "sonnet"
                decision.reason = f"manual:/{forced_tier or 'sonnet'}"
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
        iteration = 0
        cap = MAX_TOOL_ITERATIONS
        while iteration < cap:
            meta = meta_base + (f" · iter {iteration+1}/{cap}" if iteration else "")
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

            # Safety-net compression for runaway CLI sessions. Unlike
            # Telegram this path has no hard truncation; a long-running
            # chat would accumulate hundreds of turns and eventually
            # bust the model's context window. When the thread exceeds
            # 30 turns, summarize the dropped head via
            # core.context_compressor (fail-safe to plain truncation).
            if len(history_pairs) > 30:
                try:
                    from core.context_compressor import compress as _compress
                    history_pairs = _compress(history_pairs, keep_tail_n=20)
                except Exception:
                    history_pairs = history_pairs[-20:]

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

                # B023: `assistant` is captured by closure here. The
                # surrounding scope is a single iteration — build_renderable
                # is only called while `assistant` still refers to the
                # current turn — but ruff flags the pattern defensively.
                # Bind via default-arg to make the capture explicit.
                def build_renderable(done: bool = False, _a=assistant):
                    body = _a.content
                    md = Markdown(body) if body else Text("…", style="dim")
                    parts: list = []
                    if _a.thinking:
                        parts.append(_thinking_status(_a.thinking, done))
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

            # Self-claim audit — rewrite ungrounded first-person internal
            # claims to uncertainty before the turn completes. Skip for
            # tool-loop continuation turns (iteration > 0 means the model
            # is synthesizing over real tool stdout, which is grounded by
            # construction).
            try:
                from core.self_claim_audit import audit as _sc_audit
                _sc_result = _sc_audit(
                    assistant.content,
                    surface="cli",
                    in_tool_continuation=(iteration > 0),
                )
                if _sc_result.rewritten:
                    assistant.content = _sc_result.text
                    console.print(Text.from_markup(
                        f"[dim yellow]— self-claim audit rewrote "
                        f"{len(_sc_result.flags)} ungrounded claim(s) "
                        f"({_sc_result.mode}) —[/dim yellow]"
                    ))
                    console.print(Markdown(_sc_result.text))
            except Exception as _e:
                console.print(f"[dim red](audit failed: {_e})[/dim red]")

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
            iteration += 1

            # If we just finished the last iteration in this cap, offer extension.
            # User decides whether the loop keeps going.
            if iteration >= cap:
                console.print(Text.from_markup(
                    f"[yellow]— tool loop reached {cap} iterations; "
                    f"extend by {EXTEND_ITERATIONS_BY} more? (tool runs so far: "
                    f"{len([t for t in tool_history if not t.skipped])}) —[/yellow]"
                ))
                try:
                    ans = self.session.prompt(
                        HTML("<ansiyellow>extend? [y/N]:</ansiyellow> "),
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "n"
                if ans in ("y", "yes"):
                    cap += EXTEND_ITERATIONS_BY
                    console.print(Text.from_markup(
                        f"[dim italic](extended to {cap} iterations)[/dim italic]"
                    ))
                else:
                    console.print(Text.from_markup(
                        "[dim italic](loop stopped by user)[/dim italic]"
                    ))
                    break

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
