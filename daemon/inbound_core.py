# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""inbound_core.py — surface-agnostic inbound turn pipeline.

This is the SPINE of the surface-merge. ``run_inbound_turn`` is a faithful,
parameterized extraction of ``MaezMessageHandler.__call__``'s body (the
Telegram inbound pipeline). Every surface-coupled literal that the Telegram
adapter hardcodes becomes an injected keyword parameter so cockpit/web can
later drive the same core with their own labels, channels, and transport
closures.

SLICE 0 contract: this changes NOTHING observable. It is a pure, flag-gated
refactor. With ``MAEZ_INBOUND_CORE_V2`` OFF the adapter runs its untouched
inline body; with it ON the adapter delegates here. The two paths are proven
byte-identical by ``tests/test_inbound_core_equivalence.py`` (a recorded
call-trace must be IDENTICAL across both flag states).

The interceptor order is PRESERVED EXACTLY from the adapter:
  (1) S4 guard_owner_text
  (2) inner-residue + approval pre-detect
  (3) resolve shared refs (action_engine / legacy_tg / get_pipeline / chat_id /
      user_id / reply_to / pipe / has_local_photo_context)
  (4) D20 capability-gap detector
  (5) intake faculty shadow
  (6) card-reply interceptor
  (7) surface-parity proposal intent
  (8) search-commitment intent
  (9) _send_intermediate / _send_progress_receipt closures (passed IN)
  (10) chat_history fetch
  (11) observe_turn { brain_loop -> handle_message -> fallback -> return }

The audit-once / store-once contract is unchanged: ``handle_message`` owns
audit+store; the core only audits the locally-composed interceptor strings via
the injected ``audit_surface_reply`` callable, exactly as the adapter does.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from core.health.shared_executor import get_shared_executor
from core.routing.brain_gateway import (
    BrainPurpose,
    copy_current_context_callable,
    with_purpose,
)
from core.cognition.parity_flag import surface_parity_enabled
from core.infra.env_flags import strict_env_flag
from core.safety.clinical_boundary import (
    PrivateThoughtsCrisisSignalWriter,
    guard_owner_text,
)

logger = logging.getLogger(__name__)


def inbound_core_v2_enabled() -> bool:
    """Return True iff ``MAEZ_INBOUND_CORE_V2`` is set to 1/true/yes/on.

    Strict on/off parser (mirrors ``core.infra.env_flags.strict_env_flag`` and
    ``core.cognition.capability_card``'s flag helpers): ``"0"``, ``false``,
    ``no``, ``off``, empty, unset, or any other value -> False. DEFAULT OFF.
    """
    return strict_env_flag("MAEZ_INBOUND_CORE_V2")


async def run_inbound_turn(
    *,
    daemon: Any,
    # Surface-decoupled turn payload (the adapter resolves these from its event
    # in ``_build_inbound_descriptor`` so the core never touches a surface event):
    text: str,
    chat_id: str,
    resolved_user_id: str,
    reply_to_message_id: "str | None",
    context_note: Any,
    photo_analysis: "str | None",
    is_photo_turn: bool,
    # Surface-coupled literals (Telegram adapter injects its own values):
    owner_surface_label: str,
    user_id: str,
    channel: str,
    owner_auth_factory: Callable[[], Any],
    observe_turn_label: str = "telegram_turn",
    chat_history_turns: int,
    # Injected pipeline / action handles (adapter resolves daemon-level handles;
    # a future cockpit caller passes its own without going through daemon.telegram):
    action_engine: Any,
    get_pipeline: "Callable[[], Any] | None",
    # Injected dependencies (adapter methods / module helpers become callables):
    chat_history_provider: Callable[[int], Any],
    try_proposal_intent: Callable[..., Awaitable[Optional[str]]],
    try_search_commitment_intent: Callable[..., Awaitable[Optional[str]]],
    search_commitment_controller: Callable[[], Any],
    audit_surface_reply: Callable[..., str],
    clean_exchange: Callable[[str], str],
    # Transport closures (adapter builds these capturing its loop/adapter/chat):
    send_intermediate: Callable[[str], None],
    send_progress_receipt: Callable[..., None],
) -> Optional[str]:
    """Surface-agnostic inbound turn.

    Faithful parameterized copy of ``MaezMessageHandler.__call__``'s body from
    just after the empty-text guard onward. The empty-text guard is included
    here (so a flag-on caller gets the same early-return) but the adapter also
    keeps it in ``__call__`` for the flag-off byte-identical path.
    """
    text = (text or "").strip()
    if not text:
        return None

    _s4_result = guard_owner_text(
        text,
        surface=owner_surface_label,
        crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
            getattr(daemon, "private_thoughts", None)
        ),
    )
    if _s4_result.matched:
        mark = getattr(daemon, "_mark_m1_s4_policy", None)
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
                context={"surface": owner_surface_label},
            )
    except Exception:
        pass

    try:
        from core import approval_sessions as _approvals

        _approvals.detect_and_grant(text)
    except Exception:
        pass

    loop = asyncio.get_event_loop()

    # Pipeline + action engine are INJECTED. The Telegram adapter resolves them
    # from the legacy TelegramVoice instance (it constructs the pipeline lazily
    # in `_get_pipeline`); a future cockpit caller passes daemon-level handles
    # directly. ``action_engine`` and ``get_pipeline`` arrive as params.

    # ``user_id`` (the injected literal param, "rohit") is used verbatim at the
    # handle_reply / observe_turn-metadata / run_brain_loop sites, while the
    # SEPARATELY-RESOLVED ``resolved_user_id`` (the adapter resolved it from
    # ``event.source.user_id`` with a "rohit" fallback) is used at the D20
    # detector and proposal-intent sites. The adapter owns that resolution; the
    # core preserves the literal-vs-resolved split exactly.
    _resolved_user_id = resolved_user_id
    reply_to_msg_id = reply_to_message_id
    pipe = None
    if get_pipeline is not None:
        try:
            pipe = get_pipeline()
        except Exception:
            pipe = None
    has_local_photo_context = bool(is_photo_turn)

    # Surface Parity Restoration v0: D20 capability-gap detection.
    # Placement law: after auth, before every early-return interceptor.
    # The helper creates cards through pending_card_store; this path
    # never sends card messages manually.
    if surface_parity_enabled():
        try:
            from core.infra.capability_gap_detector import maybe_fire_capability_proposal

            def _fire_gap_detector() -> None:
                try:
                    maybe_fire_capability_proposal(
                        text,
                        pending_card_store=getattr(pipe, "card_store", None) if pipe else None,
                        chat_id=chat_id,
                        user_id=_resolved_user_id,
                    )
                except Exception:
                    logger.debug("d20 gap detection skipped", exc_info=True)

            loop.run_in_executor(get_shared_executor(), _fire_gap_detector)
        except Exception:
            logger.debug("d20 gap detection enqueue failed", exc_info=True)

    if strict_env_flag("MAEZ_INTAKE_FACULTY_SHADOW"):
        try:
            from core.cognition.intake_shadow import observe_owner_turn

            observe_owner_turn(
                text,
                surface=owner_surface_label,
                chat_id=chat_id,
                controller=search_commitment_controller(),
                memory=getattr(daemon, "memory", None),
            )
        except Exception:
            logger.debug("intake faculty shadow enqueue failed", exc_info=True)

    # Card-reply intent check — if there's an open approval card
    # and this message looks like a yes/no/defer, route through
    # the pipeline's reply handler. The renderer inside the
    # pipeline sends the resolution notice directly, so we return
    # any mid-dialog continuation text (or None if fully handled).
    if pipe is not None:
        try:
            open_cards = pipe.card_store.get_open_for_channel(
                channel,
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
                        user_id=user_id,
                        chat_id=chat_id,
                        reply_to_message_id=reply_to_msg_id,
                        channel=channel,
                    ),
                )
            except Exception as e:
                logger.warning(
                    "pipe.handle_reply failed on %s: %s",
                    owner_surface_label,
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
                            surface=f"{owner_surface_label}_dialog",
                        )
                        return r.text if r.rewritten else dialog_reply
                    except Exception:
                        return dialog_reply
                return None

    proposal_reply = await try_proposal_intent(
        text=text,
        chat_id=chat_id,
        pipe=pipe,
        user_id=_resolved_user_id,
    )
    if proposal_reply:
        return proposal_reply

    search_commitment_reply = await try_search_commitment_intent(
        text=text,
        chat_id=chat_id,
    )
    if search_commitment_reply:
        return search_commitment_reply

    # Self-mod dialog bridge + recall progress receipt closures are built by
    # the adapter (they capture its loop / _surface_v2_adapter / chat_id) and
    # passed in as ``send_intermediate`` (used by run_brain_loop) and
    # ``send_progress_receipt`` (passed to handle_message as send_intermediate).

    # Fetch the last few exchanges so the brain-loop's tool-planner has
    # conversational context. Without this, the planner sees only the current
    # user message and drifts on follow-up questions. None-safe — fall open if
    # memory is unreachable.
    chat_history = None
    try:
        _mem = getattr(daemon, "memory", None)
        if _mem is not None:
            _raw_exchanges = await loop.run_in_executor(
                get_shared_executor(),
                lambda: chat_history_provider(chat_history_turns),
            )
            # Clean the stored envelope into a tight "Owner: ... / Maez: ..."
            # pair before it reaches run_brain_loop. Preserves other keys
            # (metadata, id) so downstream contracts stay intact; only
            # `content` is rewritten, and only when the envelope prefix matches.
            chat_history = []
            for _ex in _raw_exchanges or []:
                if not _ex:
                    continue
                _new = dict(_ex)
                _cleaned = clean_exchange(_new.get("content", ""))
                if not _cleaned:
                    continue
                _new["content"] = _cleaned
                chat_history.append(_new)
    except Exception as e:
        logger.debug("chat_history fetch failed on %s: %s", owner_surface_label, e)
        chat_history = None

    # Observability: wrap the whole turn in a Langfuse trace so every LLM call
    # + tool dispatch lands in the UI. No-op when LANGFUSE_PUBLIC_KEY isn't set.
    from core.observability import observe_turn

    with observe_turn(
        observe_turn_label,
        input={"text": text, "chat_id": chat_id},
        metadata={"user_id": user_id, "surface": owner_surface_label},
    ) as turn:
        # Brain-loop stage — runs the tool iteration synchronously
        # with the pipeline for card-or-inline decisions.
        jarvis_transcript = ""
        jarvis_tool_calls: list[dict] = []
        jarvis_recall_items = ()
        try:
            from core import brain_loop as _brain_loop

            if (
                action_engine is not None
                and get_pipeline is not None
                and not has_local_photo_context
            ):
                # Ask for the structured result so we can pass tool_calls into
                # handle_message and the per-turn trace records the actual tool
                # trajectory. Falls back to a string + empty tool_calls if a
                # future change reverts the structured API.
                with with_purpose(BrainPurpose.OWNER_REPLY):
                    _result = await loop.run_in_executor(
                        get_shared_executor(),
                        copy_current_context_callable(
                            lambda: _brain_loop.run_brain_loop(
                                text,
                                action_engine=action_engine,
                                get_pipeline=get_pipeline,
                                user_id=user_id,
                                chat_id=chat_id,
                                surface=owner_surface_label,
                                send_intermediate=send_intermediate,
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
            logger.warning("brain_loop failed on %s: %s", owner_surface_label, e)
            jarvis_transcript = ""
            jarvis_tool_calls = []
            jarvis_recall_items = ()

        # Synthesis stage — daemon.handle_message does the final text reply and
        # OWNS the pipeline: strip tool-call leaks, self-claim audit,
        # store_telegram, trace. For photo turns it synthesizes over a BOUNDED
        # working set internally when photo_analysis is present. The audit is
        # owned by handle_message; the core does NOT double-audit.
        subjective_duration_owner_auth = None
        if surface_parity_enabled():
            try:
                subjective_duration_owner_auth = owner_auth_factory()
            except Exception:
                logger.debug(
                    "subjective duration auth construction failed",
                    exc_info=True,
                )
        try:
            with with_purpose(BrainPurpose.OWNER_REPLY):
                reply = await loop.run_in_executor(
                    get_shared_executor(),
                    copy_current_context_callable(
                        lambda: daemon.handle_message(
                            text,
                            owner_surface_label,
                            transcript=jarvis_transcript or "",
                            context_note=context_note,
                            photo_analysis=photo_analysis,
                            chat_history=chat_history,
                            chat_id=chat_id,
                            tool_calls=jarvis_tool_calls or None,
                            recall_items=jarvis_recall_items,
                            subjective_duration_owner_auth=subjective_duration_owner_auth,
                            send_intermediate=send_progress_receipt,
                        )
                    ),
                )
        except Exception as e:
            logger.warning("daemon dispatch failed on %s: %s", owner_surface_label, e)
            turn.update(output=f"(internal error: {e})")
            return f"(internal error: {e})"

        if not isinstance(reply, str) or not reply.strip():
            turn.update(output=jarvis_transcript or "(empty)")
            return jarvis_transcript or None

        # strip_tool_call_leaks was moved INTO daemon.handle_message (before
        # audit, before store) so the stored / audited / displayed text are all
        # the same string. Core no longer re-strips — the reply returned here is
        # already clean wire-format.

        # Record the final reply into the trace before the with block exits and
        # flushes. This is what the Langfuse UI shows as the turn's "output".
        try:
            turn.update(output=reply)
        except Exception:
            pass

    return reply
