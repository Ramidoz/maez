# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
maez_chat.py — Claude-Code-style terminal UI for Maez.

MVP day-1 scope: streaming chat against the local llama-server with
the hybrid router in front (code/reasoning → Claude, emotional/
grandmother → local). Uses the composable core modules directly:
paths, identity, soul_loader, ambient_format, claude_router.

Next (day 2): tool-use cards inline, proposal approval widgets,
ambient sidebar, slash commands.

Run:
    python3 -m cli.maez_chat
or:
    /home/rohit/maez/.venv/bin/python3 -m cli.maez_chat
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Bootstrap path so core/ and skills/ import cleanly when run as a script.
_MAEZ_ROOT = Path(__file__).resolve().parent.parent
if str(_MAEZ_ROOT) not in sys.path:
    sys.path.insert(0, str(_MAEZ_ROOT))

from dotenv import load_dotenv
load_dotenv(_MAEZ_ROOT / "config" / ".env")

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, Static

from core import identity, soul_loader
from core.ambient_format import ambient_prompt_block
from skills import claude_router

# ── config ─────────────────────────────────────────────────────────────
LOCAL_BRAIN_URL = os.environ.get("MAEZ_LLAMACPP_URL", "http://127.0.0.1:8080/v1")
LOCAL_MODEL = os.environ.get("MAEZ_LLAMACPP_MODEL", "qwen36-35b-sft")

# Sentinel used by the async stream pump to detect generator exhaustion.
_SENTINEL = object()


# ── turn model ─────────────────────────────────────────────────────────
@dataclass
class Turn:
    role: str            # "user" | "assistant" | "system"
    content: str = ""    # final-answer text (markdown; shown below thinking)
    thinking: str = ""   # reasoning-content (hidden by default — Ctrl+T to reveal)
    meta: str = ""       # small gray annotation (route, model, latency)
    thinking_visible: bool = False   # per-turn toggle


# ── one turn in the transcript ────────────────────────────────────────
# Each turn = a header row (role + meta) + optional thinking block + content.
# We use a Vertical container with two children: a Static for the header and
# a Markdown widget for the content so final answers render with real code
# blocks, bullets, headers, etc.
class TurnWidget(Vertical):
    def __init__(self, turn: Turn, **kwargs):
        super().__init__(**kwargs)
        self.turn = turn

    def compose(self) -> ComposeResult:
        yield Static(id="turn-header")
        yield Static(id="turn-thinking", classes="thinking")
        yield Markdown(id="turn-content")

    def on_mount(self) -> None:
        self.refresh_text()

    def _header_markup(self) -> str:
        role = self.turn.role
        if role == "user":
            tag = "[bold cyan]you[/bold cyan]"
        elif role == "assistant":
            tag = "[bold magenta]maez[/bold magenta]"
        elif role == "system":
            tag = "[dim]system[/dim]"
        else:
            tag = f"[dim]{role}[/dim]"
        meta = f" [dim italic]· {self.turn.meta}[/dim italic]" if self.turn.meta else ""
        return f"{tag}{meta}"

    def _thinking_markup(self) -> str:
        if not self.turn.thinking:
            return ""
        if self.turn.thinking_visible:
            # expanded — show full reasoning, dim italic
            return f"[dim italic]{self.turn.thinking.rstrip()}[/dim italic]"
        # collapsed — show only a "thinking" status, lines count
        lines = self.turn.thinking.count("\n") + 1
        if self.turn.content:
            return f"[dim italic](hidden thinking — {lines} lines — Ctrl+T to toggle)[/dim italic]"
        return f"[dim italic]thinking… ({lines} lines)[/dim italic]"

    def refresh_text(self) -> None:
        try:
            header = self.query_one("#turn-header", Static)
            thinking = self.query_one("#turn-thinking", Static)
            content = self.query_one("#turn-content", Markdown)
        except Exception:
            return  # not mounted yet
        header.update(self._header_markup())
        thinking.update(self._thinking_markup())
        thinking.display = bool(self.turn.thinking)
        # For user/system messages, keep content as plain text inside Markdown.
        # Markdown widget handles code fences, lists, bold, etc. naturally.
        body = self.turn.content or ("" if self.turn.thinking else "…")
        content.update(body)


# ── streaming wrappers ─────────────────────────────────────────────────
def _stream_local(messages: list[dict], max_tokens: int = 6000,
                  temperature: float = 0.7, think: bool = False):
    """Yield (kind, chunk) from the local llama-server.

    kind is "thinking" (Qwen3 reasoning_content — render in gray italic)
    or "content" (the final answer text). Callers can display them differently.

    think=False by default — Qwen3 thinking mode eats 2-3k tokens before
    producing any content. For a snappy chat UX, thinking is disabled and
    the model jumps straight to the answer. Deep reasoning path can opt
    in per-turn via a slash command later (not yet wired).

    Runs synchronously; dispatch via run_in_executor.
    """
    body = {
        "model": LOCAL_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Qwen3-specific knob. Recognised by llama-server's jinja template.
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
                    thinking = delta.get("reasoning_content")
                    content = delta.get("content")
                    if thinking:
                        yield ("thinking", thinking)
                    if content:
                        yield ("content", content)
                except Exception:
                    continue
    except Exception as e:
        yield ("content", f"\n[dim red][local stream error: {e}][/dim red]")


def _stream_claude(system: str, messages: list[dict], tier: str,
                   max_tokens: int = 4096):
    """Yield (kind, chunk) from Claude. kind is always "content" here.
    Runs synchronously; dispatch via run_in_executor.
    """
    try:
        client = claude_router._get_client()
    except Exception as e:
        yield ("content", f"[dim red][claude unavailable: {e}][/dim red]")
        return
    model = claude_router.MODEL_OPUS if tier == "opus" else claude_router.MODEL_SONNET
    api_messages = [m for m in messages if m.get("role") != "system"]
    try:
        with client.messages.stream(
            model=model,
            system=system,
            messages=api_messages,
            max_tokens=max_tokens,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield ("content", text)
    except Exception as e:
        yield ("content", f"\n[dim red][claude stream error: {e}][/dim red]")


# ── the app ────────────────────────────────────────────────────────────
class MaezChat(App):
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }
    #transcript {
        height: 1fr;
        padding: 1 2;
        border: tall $primary-background;
    }
    TurnWidget {
        margin-bottom: 1;
        height: auto;
    }
    #turn-header {
        height: 1;
    }
    #turn-thinking {
        height: auto;
        color: $text-muted;
        text-style: italic;
        padding: 0 0 0 2;
    }
    #turn-thinking.thinking { display: block; }
    #turn-content {
        height: auto;
        background: transparent;
        padding: 0;
        margin: 0;
    }
    #input {
        dock: bottom;
        margin: 0;
        border: solid $accent;
    }
    Footer {
        background: $primary-background;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+c", "interrupt", "Interrupt"),
        Binding("ctrl+t", "toggle_thinking", "Toggle thinking"),
    ]

    TITLE = "Maez"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.turns: list[Turn] = []
        self.generating = False
        self._cancel_flag = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="transcript")
        yield Input(placeholder="Talk to Maez — Ctrl+Q to quit, Ctrl+L to clear",
                    id="input")
        yield Footer()

    def on_mount(self) -> None:
        name = identity.display_name()
        self.sub_title = f"— {name}'s Maez —"
        system = Turn(
            role="system",
            content=f"Welcome, {name}. Local brain: {LOCAL_MODEL}. "
                    f"Jarvis tier: {'on' if identity.jarvis_tier() else 'off'}.",
        )
        self._append(system)
        self.query_one(Input).focus()

    # ── helpers ──
    def _append(self, turn: Turn) -> TurnWidget:
        self.turns.append(turn)
        w = TurnWidget(turn)
        self.query_one("#transcript", VerticalScroll).mount(w)
        self.call_after_refresh(self._scroll_to_bottom)
        return w

    def _scroll_to_bottom(self) -> None:
        scroll = self.query_one("#transcript", VerticalScroll)
        scroll.scroll_end(animate=False)

    # ── actions ──
    def action_clear(self) -> None:
        self.turns.clear()
        for w in list(self.query_one("#transcript", VerticalScroll).children):
            w.remove()
        self._append(Turn("system", "(transcript cleared)"))

    def action_interrupt(self) -> None:
        if self.generating:
            self._cancel_flag = True
            self._append(Turn("system", "(interrupting…)"))

    def action_toggle_thinking(self) -> None:
        """Toggle visibility of the last assistant turn's thinking block."""
        for turn, widget in reversed(list(self._turn_widgets())):
            if turn.role == "assistant" and turn.thinking:
                turn.thinking_visible = not turn.thinking_visible
                widget.refresh_text()
                return

    def _turn_widgets(self):
        transcript = self.query_one("#transcript", VerticalScroll)
        for child in transcript.children:
            if isinstance(child, TurnWidget):
                yield child.turn, child

    # ── main chat flow ──
    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if self.generating:
            return  # ignore while a reply is streaming
        text = message.value.strip()
        if not text:
            return
        message.input.value = ""

        self._append(Turn("user", text))

        # Classifier + router decision
        decision = claude_router.classify(text)
        profile_id = identity.user_profile_id()
        route_external = (
            decision.route == "external"
            and identity.jarvis_tier()
            and claude_router.jarvis_tier_enabled(profile_id)
        )

        # Build messages
        soul = soul_loader.current_soul()
        try:
            ambient = ambient_prompt_block()
        except Exception:
            ambient = ""
        system_prompt = soul + ("\n\n" + ambient if ambient else "")
        history_pairs = [
            {"role": t.role, "content": t.content}
            for t in self.turns
            if t.role in ("user", "assistant") and t.content
        ]
        messages = [{"role": "system", "content": system_prompt}] + history_pairs

        # Placeholder assistant bubble that will fill as tokens stream in
        assistant = Turn(
            role="assistant",
            content="",
            meta=(f"claude:{decision.tier}" if route_external else "local"),
        )
        assistant_widget = self._append(assistant)

        self.generating = True
        self._cancel_flag = False
        try:
            if route_external:
                await self._stream_into_widget_claude(
                    assistant, assistant_widget, system_prompt,
                    history_pairs + [{"role": "user", "content": text}],
                    decision.tier or "sonnet",
                )
            else:
                await self._stream_into_widget_local(
                    assistant, assistant_widget, messages,
                )
        finally:
            self.generating = False

        # Trajectory log — same pattern as web_interface
        try:
            claude_router.log_trajectory({
                "profile_id": profile_id,
                "display": identity.display_name(),
                "channel": "cli",
                "message": text,
                "reply": assistant.content,
                "source": f"claude:{decision.tier}" if route_external else "local",
                "decision": decision.to_dict(),
            })
        except Exception:
            pass

    async def _pump_stream(self, turn: Turn, widget: TurnWidget,
                           sync_gen) -> None:
        """Pump a synchronous (kind, chunk) generator into the widget
        without blocking the UI. Runs next() in a thread per chunk so
        the UI stays responsive for each token."""
        loop = asyncio.get_event_loop()
        iterator = iter(sync_gen)
        while True:
            if self._cancel_flag:
                turn.content += "\n[dim](interrupted)[/dim]"
                widget.refresh_text()
                return
            try:
                item = await loop.run_in_executor(None, next, iterator, _SENTINEL)
            except StopIteration:
                return
            if item is _SENTINEL:
                return
            kind, chunk = item
            if kind == "thinking":
                turn.thinking += chunk
            else:
                turn.content += chunk
            widget.refresh_text()
            self._scroll_to_bottom()

    async def _stream_into_widget_local(
        self, turn: Turn, widget: TurnWidget, messages: list[dict]
    ) -> None:
        gen = _stream_local(messages)
        await self._pump_stream(turn, widget, gen)

    async def _stream_into_widget_claude(
        self, turn: Turn, widget: TurnWidget,
        system: str, messages: list[dict], tier: str,
    ) -> None:
        gen = _stream_claude(system, messages, tier)
        await self._pump_stream(turn, widget, gen)


def main() -> None:
    MaezChat().run()


if __name__ == "__main__":
    main()
