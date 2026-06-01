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
import re
import time
from typing import Any, Optional

from core.health.shared_executor import get_shared_executor
from core.routing.brain_gateway import (
    BrainPurpose,
    copy_current_context_callable,
    with_purpose,
)
from core.safety.clinical_boundary import PrivateThoughtsCrisisSignalWriter, guard_owner_text
from skills.surface.platform_base import MessageEvent
from skills.surface.platform_config import PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


# 2026-04-23: strip the stored prompt envelope before passing a prior
# exchange to run_brain_loop as chat_history. Stored content shapes:
#
#   (a) daemon telegram  (daemon/maez_daemon.py:1346):
#       the owner (<source>): <USER_MSG>
#       [<TURN STATE/FORBIDDEN/JARVIS TRANSCRIPT/etc. envelope>]
#       Maez: <REPLY>
#
#   (b) web + telegram_voice  (web_interface.py, telegram_voice.py):
#       the owner asked: <USER_MSG>
#       Maez replied: <REPLY>
#
# Passing form (a) raw would flood the planning prompt with stale
# FORBIDDEN and AMBIGUOUS-REFERENT rule text from the previous turn,
# burying the actual Q/A signal. Form (b) has no envelope but the
# `Maez replied:` delimiter doesn't match the daemon-form
# `Maez:` delimiter the parser expected.
#
# 2026-04-24 audit pass (F4): both forms now clean to the same
# shape — `"<display_name>: <USER_MSG>\nMaez: <REPLY>"` — so the
# downstream `core.brain.conversation_history.history_to_messages`
# threads them uniformly. Without this, web + voice follow-ups
# silently lost continuity threading (the failure we just closed
# for telegram in commit cc462c5).
_SOURCE_PREFIX_RE = re.compile(r"^the owner \([^)]+\):\s*")
_ASKED_PREFIX_RE = re.compile(r"^the owner asked:\s*")
_ASSISTANT_MARKER_DAEMON = "\nMaez:"
_ASSISTANT_MARKER_WEB_VOICE = "\nMaez replied:"


def _clean_exchange(doc: str) -> str:
    """Collapse a stored telegram_exchange envelope to a clean Q/A pair.

    Handles two stored forms (see module-level note):
      (a) daemon telegram:      `the owner (<source>): <msg>\\n[envelope]\\nMaez: <reply>`
      (b) web + telegram_voice: `the owner asked: <msg>\\nMaez replied: <reply>`

    Any other shape (operational notes like card-state summaries,
    recovery markers, test fixtures, future formats) passes through
    unchanged so this helper is safe to add without migrating every
    caller. The downstream parser rejects unparseable passthroughs.

    The owner-side prefix used in the cleaned output is resolved from
    `core.memory.identity.display_name()` at call time — not hardcoded
    — so a fresh install with `display_name="Friend"` (or any other
    configured value) produces self-consistent conversation history.
    Falls back to a generic "Owner:" if identity lookup fails so the
    cleaner can never crash a surface turn.
    """
    if not doc:
        return ""
    first_line = doc.split("\n", 1)[0]
    user_msg = None
    reply = None

    # Try daemon form first — the `\nMaez:` marker is more
    # restrictive than `\nMaez replied:`, so match that explicitly.
    if _SOURCE_PREFIX_RE.match(first_line):
        user_msg = _SOURCE_PREFIX_RE.sub("", first_line).strip()
        # The reply is appended after a final "\nMaez:" delimiter
        # (prefer `rfind` so an embedded "Maez:" mention in the
        # envelope can't fool us — the real reply is always the last
        # segment).
        pos = doc.rfind(_ASSISTANT_MARKER_DAEMON)
        if pos == -1:
            pos = doc.find(_ASSISTANT_MARKER_DAEMON)
        if pos < 0:
            return doc
        reply = doc[pos + len(_ASSISTANT_MARKER_DAEMON) :].strip()
    # Then the web/voice form — single-line user, `\nMaez replied:`
    # marker, no envelope between.
    elif _ASKED_PREFIX_RE.match(first_line):
        user_msg = _ASKED_PREFIX_RE.sub("", first_line).strip()
        pos = doc.find(_ASSISTANT_MARKER_WEB_VOICE)
        if pos < 0:
            return doc
        reply = doc[pos + len(_ASSISTANT_MARKER_WEB_VOICE) :].strip()
    else:
        return doc

    if not user_msg and not reply:
        return doc
    try:
        from core.memory.identity import display_name as _display_name

        owner_prefix = _display_name() or "Owner"
    except Exception:
        owner_prefix = "Owner"
    return f"{owner_prefix}: {user_msg}\nMaez: {reply}".strip()


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

        _s4_result = guard_owner_text(
            text,
            surface=SURFACE_NAME,
            crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
                getattr(self.daemon, "private_thoughts", None)
            ),
        )
        if _s4_result.matched:
            mark = getattr(self.daemon, "_mark_m1_s4_policy", None)
            if callable(mark):
                mark(_s4_result.promotion_policy)
            return _s4_result.answer_text

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
        get_pipeline = getattr(legacy_tg, "_get_pipeline", None) if legacy_tg is not None else None

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
                        "telegram_text",
                        chat_id=chat_id,
                    )
                except Exception:
                    open_cards = []
                if open_cards:
                    try:
                        result = await loop.run_in_executor(
                            get_shared_executor(),
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
                            SURFACE_NAME,
                            e,
                        )
                        result = None
                    if result is not None:
                        # Pipeline handled it — resolution was sent by
                        # its CardRenderer. Return any mid-dialog
                        # continuation text so the adapter sends it
                        # as the reply to this message.
                        dialog_reply = getattr(
                            result,
                            "dialog_reply_text",
                            None,
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
                from core.egress.provenance import ProvenancedText

                payload = ProvenancedText.maez_authored_owner_third_party_transport(
                    msg_text,
                    source_ref=f"{SURFACE_NAME}:self_mod_dialog_intermediate",
                )
                coro = adapter.send(chat_id, payload)
                fut = asyncio.run_coroutine_threadsafe(coro, adapter_loop)
                fut.result(timeout=20)
            except Exception as e:
                logger.warning(
                    "send_intermediate failed on %s: %s",
                    SURFACE_NAME,
                    e,
                )

        def _send_progress_receipt(
            msg_text: str,
            *,
            on_complete=None,
            should_send=None,
        ) -> None:
            def _complete(result: str) -> None:
                if on_complete is None:
                    return
                try:
                    on_complete(result, time.monotonic())
                except Exception:
                    logger.debug("recall progress receipt completion callback failed")

            if not adapter or not loop or not chat_id:
                _complete("failed")
                return

            async def _send() -> None:
                try:
                    if should_send is not None and not should_send():
                        _complete("failed")
                        return
                    from core.egress.provenance import ProvenancedText
                    from core.routing.recall_receipt import RECEIPT_SEND_TIMEOUT_MS

                    payload = ProvenancedText.maez_authored_owner_third_party_transport(
                        msg_text,
                        source_ref=f"{SURFACE_NAME}:recall_progress_receipt",
                    )
                    result = await asyncio.wait_for(
                        adapter.send(chat_id, payload),
                        timeout=RECEIPT_SEND_TIMEOUT_MS / 1000.0,
                    )
                    _complete("ok" if getattr(result, "success", False) else "failed")
                except asyncio.TimeoutError:
                    _complete("timeout")
                except Exception as e:
                    logger.debug(
                        "recall progress receipt send failed on %s: %s",
                        SURFACE_NAME,
                        type(e).__name__,
                    )
                    _complete("failed")

            try:
                asyncio.run_coroutine_threadsafe(_send(), loop)
            except Exception as e:
                logger.debug(
                    "recall progress receipt scheduling failed on %s: %s",
                    SURFACE_NAME,
                    type(e).__name__,
                )
                _complete("failed")

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
                _raw_exchanges = await loop.run_in_executor(
                    get_shared_executor(),
                    lambda: _mem.get_telegram_exchanges(
                        limit=_CHAT_HISTORY_TURNS,
                    ),
                )
                # 2026-04-23: clean the stored envelope into a tight
                # "Rohit: ... / Maez: ..." pair before it reaches
                # run_brain_loop. Without this, `chat_history` injects
                # hundreds of lines of old FORBIDDEN / TURN STATE /
                # AMBIGUOUS REFERENT rule text into the current prompt
                # and the planner loses the actual conversational
                # signal. Observed symptom: the owner says "What
                # happened?" after an npm install failure and Maez
                # replies "I don't know what you're referring to."
                # The cleaner preserves other keys (metadata, id) so
                # downstream contracts stay intact; only `content` is
                # rewritten, and only when the envelope prefix matches.
                chat_history = []
                for _ex in _raw_exchanges or []:
                    if not _ex:
                        continue
                    _new = dict(_ex)
                    _cleaned = _clean_exchange(_new.get("content", ""))
                    if not _cleaned:
                        continue
                    _new["content"] = _cleaned
                    chat_history.append(_new)
        except Exception as e:
            logger.debug("chat_history fetch failed on %s: %s", SURFACE_NAME, e)
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
            jarvis_tool_calls: list[dict] = []
            jarvis_recall_items = ()
            try:
                from core import brain_loop as _brain_loop

                if action_engine is not None and get_pipeline is not None:
                    # Slice 3 of trace work: ask for the structured
                    # result so we can pass tool_calls into
                    # handle_message and the per-turn trace records the
                    # actual tool trajectory, not just the synthesis
                    # text. Falls back to a string + empty tool_calls
                    # if a future change reverts the structured API.
                    with with_purpose(BrainPurpose.OWNER_REPLY):
                        _result = await loop.run_in_executor(
                            get_shared_executor(),
                            copy_current_context_callable(
                                lambda: _brain_loop.run_brain_loop(
                                    text,
                                    action_engine=action_engine,
                                    get_pipeline=get_pipeline,
                                    user_id="rohit",
                                    chat_id=chat_id,
                                    surface=SURFACE_NAME,
                                    send_intermediate=_send_intermediate,
                                    chat_history=chat_history,
                                    turn=turn,
                                    return_structured=True,
                                )
                            ),
                        )
                    if hasattr(_result, "transcript"):
                        jarvis_transcript = _result.transcript or ""
                        jarvis_tool_calls = list(getattr(_result, "tool_calls", []) or [])
                        jarvis_recall_items = tuple(getattr(_result, "recall_items", ()) or ())
                    else:  # legacy str fallback
                        jarvis_transcript = _result or ""
            except Exception as e:
                logger.warning("brain_loop failed on %s: %s", SURFACE_NAME, e)
                jarvis_transcript = ""
                jarvis_tool_calls = []
                jarvis_recall_items = ()

            # Synthesis stage — daemon.handle_message does the final text
            # reply with registry + residue + self-model blocks injected.
            # 2026-04-23 memory-integrity contract (Commit 1): the audit
            # is now owned by handle_message. The adapter passes the
            # Jarvis transcript into handle_message so the audit sees
            # the tool-loop context and correctly sets
            # in_tool_continuation. Adapter no longer double-audits the
            # returned reply.
            try:
                with with_purpose(BrainPurpose.OWNER_REPLY):
                    reply = await loop.run_in_executor(
                        get_shared_executor(),
                        copy_current_context_callable(
                            lambda: self.daemon.handle_message(
                                text,
                                SURFACE_NAME,
                                transcript=jarvis_transcript or "",
                                chat_history=chat_history,
                                chat_id=chat_id,
                                tool_calls=jarvis_tool_calls or None,
                                recall_items=jarvis_recall_items,
                                send_intermediate=_send_progress_receipt,
                            )
                        ),
                    )
            except Exception as e:
                logger.warning("daemon dispatch failed on %s: %s", SURFACE_NAME, e)
                turn.update(output=f"(internal error: {e})")
                return f"(internal error: {e})"

            if not isinstance(reply, str) or not reply.strip():
                turn.update(output=jarvis_transcript or "(empty)")
                return jarvis_transcript or None

            # 2026-04-23 Commit 7b: strip_tool_call_leaks was moved INTO
            # daemon.handle_message (before audit, before store) so the
            # stored / audited / displayed text are all the same string.
            # Adapter no longer re-strips — the reply returned here is
            # already clean wire-format.

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
