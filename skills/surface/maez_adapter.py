# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
maez_adapter.py — bridges the vendored platform adapter layer into
Maez's brain.

The vendored `BasePlatformAdapter` exposes a `MessageHandler` protocol:

    MessageHandler = Callable[[MessageEvent], Awaitable[Optional[str]]]

`MaezMessageHandler` implements that protocol by taking a `MessageEvent`,
running Maez's standard pre-processing (inner-residue, approval-session
detection), dispatching through the daemon's synchronous `handle_message`
in an executor, and post-auditing the reply with the self-claim audit.

That's the full Maez-specific wiring. Everything else — covenant,
decision pipeline, owner-trust, capability registry, organism loops —
is already invoked transitively by `daemon.handle_message` and by the
audit path.

Bootstrap entry point is `build_telegram_adapter(...)`. Caller is
responsible for scheduling `adapter.connect()` on an event loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from skills.surface.platform_base import MessageEvent
from skills.surface.platform_config import Platform, PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter

logger = logging.getLogger(__name__)

# Distinct surface label so logs make the routing path obvious during
# parallel operation with the legacy `skills/telegram_voice.py` path.
# When the old path is retired, this can be renamed to simply
# "telegram" or "telegram_text" (the current legacy label).
SURFACE_NAME = "telegram_surface"

# How many prior telegram exchanges to inject into the brain_loop's
# planning context. Kept small on purpose — the planning prompt is
# ~512 tokens and each exchange is capped at 800 chars by
# core.brain_loop, so 3 fits comfortably with headroom for the tool
# manifest. Bump only if the model starts missing context from
# further back; prefer retrieval changes over blind enlargement.
_CHAT_HISTORY_TURNS = 3


class MaezMessageHandler:
    """MessageHandler that plugs Maez's brain into the vendored
    platform adapter.

    Each incoming Telegram message flows through three stages here:
      1. Pre-processing: user-rejection detection (→ inner-residue) and
         blanket-approval detection (→ approval-sessions).
      2. Brain loop: runs `core.brain_loop.run_brain_loop` to let the
         model iterate tool calls through the decision pipeline, then
         calls `daemon.handle_message` for the final text synthesis
         with the jarvis transcript folded in.
      3. Post-processing: self-claim audit rewrites fabrications.

    The brain loop and audit are IDENTICAL to what
    `skills/telegram_voice.py` runs on the legacy path — they both call
    `core.brain_loop.run_brain_loop` so any surface here and any surface
    there produce the same tool-use behavior."""

    def __init__(self, daemon: Any):
        self.daemon = daemon

    async def __call__(self, event: MessageEvent) -> Optional[str]:
        text = (event.text or "").strip()
        if not text:
            return None

        # Pre-processing — same signals the daemon's own
        # handle_message path picks up. Safe to run here too because
        # both detections are idempotent for a single turn.
        try:
            from core import inner_residue as _residue
            if _residue.detect_user_rejection(text):
                _residue.record(
                    kind="user_rejection",
                    context={"surface": SURFACE_NAME},
                )
        except Exception:
            pass

        try:
            from core import approval_sessions as _approvals
            _approvals.detect_and_grant(text)
        except Exception:
            pass

        loop = asyncio.get_event_loop()

        # Resolve shared references — pipeline + action engine live on
        # the legacy TelegramVoice instance (it constructs them lazily
        # in `_get_pipeline`). In v2 mode legacy still holds these for
        # shared card rendering during the parallel-run period.
        action_engine = getattr(self.daemon, "actions", None)
        legacy_tg = getattr(self.daemon, "telegram", None)
        get_pipeline = (
            getattr(legacy_tg, "_get_pipeline", None)
            if legacy_tg is not None else None
        )

        chat_id = ""
        try:
            src = event.source
            if src and src.chat_id:
                chat_id = str(src.chat_id)
        except Exception:
            pass
        reply_to_msg_id = getattr(event, "reply_to_message_id", None)

        # Card-reply intent check — if there's an open approval card
        # and this message looks like a yes/no/defer, route through
        # the pipeline's reply handler. The renderer inside the
        # pipeline sends the resolution notice directly, so we return
        # any mid-dialog continuation text (or None if fully handled).
        if get_pipeline is not None:
            try:
                pipe = get_pipeline()
            except Exception:
                pipe = None
            if pipe is not None:
                try:
                    open_cards = pipe.card_store.get_open_for_channel(
                        "telegram_text", chat_id=chat_id,
                    )
                except Exception:
                    open_cards = []
                if open_cards:
                    try:
                        result = await loop.run_in_executor(
                            None,
                            lambda: pipe.handle_reply(
                                text=text,
                                user_id="rohit",
                                chat_id=chat_id,
                                reply_to_message_id=reply_to_msg_id,
                                channel="telegram_text",
                            ),
                        )
                    except Exception as e:
                        logger.warning(
                            "pipe.handle_reply failed on %s: %s",
                            SURFACE_NAME, e,
                        )
                        result = None
                    if result is not None:
                        # Pipeline handled it — resolution was sent by
                        # its CardRenderer. Return any mid-dialog
                        # continuation text so the adapter sends it
                        # as the reply to this message.
                        dialog_reply = getattr(
                            result, "dialog_reply_text", None,
                        )
                        if dialog_reply:
                            # Strip tool-call JSON leaks (e.g. the
                            # {"action": "log", ...} block observed
                            # in a 2026-04-20 dialog reply).
                            try:
                                from core.brain_loop import (
                                    strip_tool_call_leaks,
                                )
                                dialog_reply = strip_tool_call_leaks(
                                    dialog_reply,
                                )
                            except Exception:
                                pass
                            try:
                                from core.self_claim_audit import (
                                    audit as _sc_audit,
                                )
                                r = _sc_audit(
                                    dialog_reply,
                                    surface=f"{SURFACE_NAME}_dialog",
                                )
                                return r.text if r.rewritten else dialog_reply
                            except Exception:
                                return dialog_reply
                        return None

        # Self-mod dialog bridge — brain_loop needs a callable that
        # surfaces the Lane-3 dialog opening as a Telegram message
        # BEFORE the final synthesis reply. The brain loop runs in an
        # executor (sync), so we bridge to the adapter's async send
        # via run_coroutine_threadsafe on this handler's loop.
        adapter = getattr(self.daemon, "_surface_v2_adapter", None)
        adapter_loop = getattr(self.daemon, "_surface_v2_loop", None)

        def _send_intermediate(msg_text: str) -> None:
            if not adapter or not adapter_loop or not chat_id:
                return
            try:
                coro = adapter.send(chat_id, msg_text)
                fut = asyncio.run_coroutine_threadsafe(coro, adapter_loop)
                fut.result(timeout=20)
            except Exception as e:
                logger.warning(
                    "send_intermediate failed on %s: %s",
                    SURFACE_NAME, e,
                )

        # Fetch the last few telegram exchanges so the brain-loop's
        # tool-planner has conversational context. Without this, the
        # planner sees only the current user message and drifts on
        # follow-up questions ("what did you find?", "try that again").
        # get_telegram_exchanges already exists and is used by
        # continuity + dream_state; this just extends its reach to the
        # tool-planning path. None-safe — fall open if memory is
        # unreachable.
        chat_history = None
        try:
            _mem = getattr(self.daemon, "memory", None)
            if _mem is not None:
                chat_history = await loop.run_in_executor(
                    None,
                    lambda: _mem.get_telegram_exchanges(
                        limit=_CHAT_HISTORY_TURNS,
                    ),
                )
        except Exception as e:
            logger.debug("chat_history fetch failed on %s: %s",
                         SURFACE_NAME, e)
            chat_history = None

        # Observability: wrap the whole turn in a Langfuse trace so
        # every LLM call + tool dispatch lands in the UI. No-op when
        # LANGFUSE_PUBLIC_KEY isn't set (default). See
        # core.observability for the abstraction.
        from core.observability import observe_turn
        with observe_turn(
            "telegram_turn",
            input={"text": text, "chat_id": chat_id},
            metadata={"user_id": "rohit", "surface": SURFACE_NAME},
        ) as turn:
            # Brain-loop stage — runs the tool iteration synchronously
            # with the pipeline for card-or-inline decisions.
            jarvis_transcript = ""
            try:
                from core import brain_loop as _brain_loop
                if action_engine is not None and get_pipeline is not None:
                    jarvis_transcript = await loop.run_in_executor(
                        None,
                        lambda: _brain_loop.run_brain_loop(
                            text,
                            action_engine=action_engine,
                            get_pipeline=get_pipeline,
                            user_id="rohit",
                            chat_id=chat_id,
                            send_intermediate=_send_intermediate,
                            chat_history=chat_history,
                            turn=turn,
                        ),
                    )
            except Exception as e:
                logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
                jarvis_transcript = ""

            # Fold the brain-loop transcript into the user-text seen by
            # the synthesis call.
            try:
                from core.brain_loop import build_synthesis_user_text
                synthesis_text = build_synthesis_user_text(
                    text, jarvis_transcript,
                )
            except Exception:
                synthesis_text = text

            # Synthesis stage — daemon.handle_message does the final text
            # reply with registry + residue + self-model blocks injected.
            try:
                reply = await loop.run_in_executor(
                    None,
                    self.daemon.handle_message,
                    synthesis_text,
                    SURFACE_NAME,
                )
            except Exception as e:
                logger.warning("daemon dispatch failed on %s: %s",
                               SURFACE_NAME, e)
                turn.update(output=f"(internal error: {e})")
                return f"(internal error: {e})"

            if not isinstance(reply, str) or not reply.strip():
                turn.update(output=jarvis_transcript or "(empty)")
                return jarvis_transcript or None

            # Strip tool-call JSON leaks before audit + send.
            try:
                from core.brain_loop import strip_tool_call_leaks
                reply = strip_tool_call_leaks(reply)
            except Exception:
                pass

            # Structural self-claim audit on the final reply.
            # When a jarvis_transcript exists, the reply is a synthesis
            # of REAL tool output (shell commands that actually ran on
            # the owner's machine). The judge doesn't see the transcript
            # — it only sees the prose reply, so "disk at 70.7%, CPU at
            # 45%" reads as an invented trend claim and triggers the
            # shortcircuit. Observed 2026-04-21 after a simple
            # "heartbeat" turn produced a whole-response "I don't have
            # a grounded answer" reply.
            #
            # Fix: when a non-empty Jarvis transcript is present, pass
            # in_tool_continuation=True so the audit skips the judge
            # entirely — the real stdout is what grounds the claim by
            # construction. This matches the v1 regex-era policy.
            try:
                from core.self_claim_audit import audit as _sc_audit
                _has_real_tools = bool(jarvis_transcript and jarvis_transcript.strip())
                r = _sc_audit(
                    reply,
                    surface=SURFACE_NAME,
                    in_tool_continuation=_has_real_tools,
                    transcript=jarvis_transcript,
                )
                if r.rewritten:
                    reply = r.text
            except Exception as e:
                logger.warning("self-claim audit failed on %s: %s",
                               SURFACE_NAME, e)

            # Record the final reply into the trace before the with
            # block exits and flushes. This is what the Langfuse UI
            # shows as the turn's "output".
            try:
                turn.update(output=reply)
            except Exception:
                pass

        return reply


def build_telegram_adapter(
    token: str,
    authorized_users: list[int],
    daemon: Any,
    *,
    reply_to_mode: str = "first",
    extra: Optional[dict] = None,
) -> TelegramAdapter:
    """Instantiate the vendored TelegramAdapter wired to Maez's brain.

    The caller is responsible for scheduling `adapter.connect()` on
    an event loop. Typical bootstrap:

        adapter = build_telegram_adapter(token, [user_id], daemon)
        asyncio.create_task(adapter.connect())

    Or in a thread with its own loop (matches the current legacy
    pattern in `skills/telegram_voice.py`):

        loop = asyncio.new_event_loop()
        loop.run_until_complete(adapter.connect())
    """
    merged_extra: dict = {"allowed_users": list(authorized_users)}
    if extra:
        merged_extra.update(extra)

    cfg = PlatformConfig(
        enabled=True,
        token=token,
        reply_to_mode=reply_to_mode,
        extra=merged_extra,
    )
    adapter = TelegramAdapter(cfg)
    handler = MaezMessageHandler(daemon)
    adapter.set_message_handler(handler)
    return adapter
