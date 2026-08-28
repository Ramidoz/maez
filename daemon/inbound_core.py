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
from dataclasses import dataclass
from datetime import UTC, datetime
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


def conversational_consent_enabled() -> bool:
    """Strict DEFAULT-OFF flag for the conversational consent spine."""

    return strict_env_flag("MAEZ_CONVERSATIONAL_CONSENT_ENABLED")


@dataclass(frozen=True)
class OwnerUtteranceExtraction:
    utterance: Any | None
    refusal_code: str | None = None
    binding: Any | None = None


def _surface_kind_for_label(surface_label: str) -> str:
    label = (surface_label or "").strip().lower()
    if label.startswith("telegram"):
        return "telegram"
    return label or "unknown"


def _raw_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _raw_id(obj: Any) -> str | None:
    raw = _raw_value(obj, "id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _truthy_raw(obj: Any, key: str) -> bool:
    return bool(_raw_value(obj, key))


def extract_owner_utterance_from_raw_metadata(
    *,
    surface_label: str,
    text: str,
    reply_to_message_id: str | None,
    raw_platform_metadata: Any,
    binding_registry: Any | None,
) -> OwnerUtteranceExtraction:
    """Construct an OwnerUtterance only from raw platform sender metadata.

    Normalized adapter ``source`` fields are deliberately not accepted here,
    because Telegram can synthesize ``source.user_id`` from chat id when
    ``from_user`` is absent.
    """

    del binding_registry
    surface_kind = _surface_kind_for_label(surface_label)
    if surface_kind != "telegram":
        return OwnerUtteranceExtraction(
            utterance=None,
            refusal_code="surface_identity_unverifiable",
        )
    raw = raw_platform_metadata
    if raw is None:
        return OwnerUtteranceExtraction(
            utterance=None,
            refusal_code="surface_identity_unverifiable",
        )
    raw_message = _raw_value(raw, "message") or raw
    from_user = _raw_value(raw_message, "from_user")
    chat = _raw_value(raw_message, "chat")
    user_id = _raw_id(from_user)
    chat_id = _raw_id(chat)
    if user_id is None or chat_id is None:
        return OwnerUtteranceExtraction(
            utterance=None,
            refusal_code="surface_identity_unverifiable",
        )

    fresh = not any(
        (
            _truthy_raw(raw_message, "forward_origin"),
            _truthy_raw(raw_message, "forward_from"),
            _truthy_raw(raw_message, "forward_date"),
            _truthy_raw(raw_message, "via_bot"),
            _truthy_raw(raw_message, "edit_date"),
            _truthy_raw(raw, "edited_message"),
        )
    )
    try:
        from core.consent.bindings import telegram_surface_identity
        from core.consent.spine import OwnerUtterance
    except Exception:
        return OwnerUtteranceExtraction(
            utterance=None,
            refusal_code="surface_identity_unverifiable",
        )

    return OwnerUtteranceExtraction(
        utterance=OwnerUtterance(
            surface_kind="telegram",
            surface_identity=telegram_surface_identity(user_id, chat_id),
            text=text,
            fresh=fresh,
            reply_to_ref=reply_to_message_id,
            at=datetime.now(UTC).isoformat(),
        )
    )


def _trace_consent(daemon: Any, event: tuple) -> None:
    trace = getattr(daemon, "_trace", None)
    if isinstance(trace, list):
        trace.append(event)


def _content_light_open_cards_fact(open_cards: list[Any]) -> str | None:
    facts = []
    now = datetime.now(UTC).timestamp()
    for card in open_cards[:5]:
        created_at = getattr(card, "created_at", None)
        try:
            age_s = max(0, int(now - float(created_at)))
        except Exception:
            age_s = None
        fact = {
            "action": str(getattr(card, "action", "") or ""),
            "age_s": age_s,
        }
        token = getattr(card, "echo_token", None)
        if token:
            fact["echo_token"] = str(token)
        facts.append(fact)
    if not facts:
        return None
    return f"CONVERSATIONAL CONSENT BODY FACT: {{'open_cards': {facts!r}}}"


async def run_inbound_turn(
    *,
    daemon: Any,
    # Surface-decoupled turn payload (the adapter resolves these from its event
    # in ``_build_inbound_descriptor`` so the core never touches a surface event):
    text: str,
    event_identity: str = "",
    proposal_entry: "dict | None" = None,
    chat_id: str = "",
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
    # ORGAN 3b: per-descriptor felt-time opt-in. When True, owner_auth_factory()
    # is constructed (granting subjective-duration / felt-time) even if the
    # global surface_parity flag is off. DEFAULT False => byte-identical to
    # today for every caller that omits the key (telegram-V2 and any other):
    # parity off + felt_time_enabled False => factory not called. Lets the
    # cockpit grant felt-time on its OWN flag without flipping global parity.
    felt_time_enabled: bool = False,
    observe_turn_label: str = "telegram_turn",
    chat_history_turns: int,
    # SLICE 2 covenant levers (DEFAULT preserves Telegram byte-identity):
    #   mark_s4_promotion_policy: when an S4 match fires, whether to mark the
    #     SHARED global M1 promotion window s4_ineligible. Telegram IS an M1
    #     source so it marks (True). Cockpit is M1-excluded and must NOT mutate
    #     the shared (Telegram-fed) window from an unauthenticated surface, so it
    #     passes False — the crisis-care answer_text is STILL returned either way.
    #   gate_d20_on_pipe: when False (default = Telegram inline body), the D20
    #     capability-gap block fires whenever surface_parity is on, even if pipe
    #     is None (byte-identical to the inline Telegram body). Cockpit passes
    #     True to SKIP D20 when pipe is None (no orphaned card to a default store).
    mark_s4_promotion_policy: bool = True,
    gate_d20_on_pipe: bool = False,
    raw_platform_metadata: Any = None,
    consent_binding_registry: Any = None,
    consent_spine_store: Any = None,
    consent_resolution_paths: Any = None,
    consent_approve_channel: Any = None,
    # Injected pipeline / action handles (adapter resolves daemon-level handles;
    # a future cockpit caller passes its own without going through daemon.telegram):
    action_engine: Any,
    get_pipeline: "Callable[[], Any] | None",
    # Injected dependencies (adapter methods / module helpers become callables):
    chat_history_provider: Callable[[int], Any],
    try_proposal_intent: Callable[..., Awaitable[Optional[str]]],
    try_search_commitment_intent: Callable[..., Awaitable[Any]],
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

    # Phase 2: advance the conversation turn ordinal ONCE at admitted-
    # turn entry, before every interceptor (gate build note 1) --
    # idempotent on event identity; None when the action-lane flags
    # are off (store untouched). Referents assemble read-only here.
    current_turn_seq = None
    action_referents: tuple = ()
    try:
        from core.brain.action_referents import assemble_action_referents
        from core.brain.conversation_turn_seq import (
            advance_and_get,
            action_lane_enabled as _al_on,
            action_lane_shadow_enabled as _al_shadow,
        )

        if not (_al_on() or _al_shadow()):
            raise StopIteration  # flags off: untouched path
        # Store-key convention: cards/receipts are keyed under the
        # legacy channel name, not the surface label (gate blocker 5).
        _ref_channel = "telegram_text" if str(
            owner_surface_label or ""
        ).startswith("telegram") else str(owner_surface_label or "")
        if event_identity:
            current_turn_seq = advance_and_get(
                _ref_channel, chat_id, event_identity
            )
        _pipe_for_ref = None
        try:
            _lt = getattr(daemon, "telegram", None)
            _pipe_for_ref = (
                _lt._get_pipeline() if _lt is not None else None
            )
        except Exception:
            _pipe_for_ref = None
        action_referents = assemble_action_referents(
            channel=_ref_channel,
            chat_id=chat_id,
            user_id=resolved_user_id,
            card_store=getattr(_pipe_for_ref, "card_store", None),
            controller=search_commitment_controller(),
            proposal_entry=proposal_entry,
            current_turn_seq=current_turn_seq,
        )
    except Exception:
        logger.debug("action referent assembly skipped", exc_info=True)


    _s4_result = guard_owner_text(
        text,
        surface=owner_surface_label,
        crisis_signal_writer=PrivateThoughtsCrisisSignalWriter(
            getattr(daemon, "private_thoughts", None)
        ),
    )
    if _s4_result.matched:
        # The crisis-care answer is returned regardless of surface — an owner in
        # crisis on cockpit still gets the care reply. Only the SHARED-window
        # promotion mark is conditional: cockpit (mark_s4_promotion_policy=False)
        # must not mutate the Telegram-fed global M1 window from an
        # unauthenticated localhost surface (a durable-selfhood mutation).
        if mark_s4_promotion_policy:
            mark = getattr(daemon, "_mark_m1_s4_policy", None)
            if callable(mark):
                mark(_s4_result.promotion_policy)
        # A3 seam closure (twenty-second round): the crisis exchange is an
        # ORDINARY pair of turns in the record. The guard has already run
        # (ADR 0035 order holds); before this, the whole exchange recorded
        # nothing — this branch returns before handle_message's
        # user_message admission. Byte-inert while MAEZ_LEDGER_WRITES is
        # unset; the reply ships regardless of what recording does.
        # SEPARATE try blocks (twenty-second round, half-exchange rule):
        # a crashing owner record must never withhold the organ record —
        # record what you have, thread what you can.
        _a3_owner_turn = None
        try:
            from core.ledger.recorder import record_owner_message

            _a3_owner_turn = record_owner_message(
                surface=owner_surface_label, raw_text=text
            )
        except Exception:
            logger.exception(
                "A3 owner record failed on the S4 path; the crisis reply "
                "ships regardless"
            )
        try:
            from core.ledger.recorder import (
                OrganProvenance,
                record_organ_event,
            )

            record_organ_event(
                surface=owner_surface_label,
                event_origin="s4_clinical_boundary",
                provenance=OrganProvenance.CANNED,
                raw_text=_s4_result.answer_text,
                parent=_a3_owner_turn,
            )
        except Exception:
            logger.exception(
                "A3 organ record failed on the S4 path; the crisis reply "
                "ships regardless"
            )
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

    consent_owner_utterance = None
    consent_binding = None
    consent_open_cards_snapshot = None
    consent_flow_state = "IDLE"
    consent_legacy_suppressed = False
    if conversational_consent_enabled():
        try:
            extraction = extract_owner_utterance_from_raw_metadata(
                surface_label=owner_surface_label,
                text=text,
                reply_to_message_id=reply_to_msg_id,
                raw_platform_metadata=raw_platform_metadata,
                binding_registry=consent_binding_registry,
            )
            consent_owner_utterance = extraction.utterance
            if consent_owner_utterance is None:
                _trace_consent(
                    daemon,
                    ("consent.identity_refusal", extraction.refusal_code),
                )
            else:
                from core.consent.bindings import BindingRegistry, ConsentBindingPaths
                from core.consent.spine import ConsentSpineStore

                if consent_binding_registry is not None:
                    registry = consent_binding_registry
                else:
                    binding_paths = ConsentBindingPaths.defaults()
                    registry = (
                        BindingRegistry(binding_paths)
                        if binding_paths.db_path.exists()
                        else None
                    )
                consent_binding = (
                    registry.active_binding_for(
                        consent_owner_utterance.surface_kind,
                        consent_owner_utterance.surface_identity,
                    )
                    if registry is not None
                    else None
                )
                if consent_binding is not None:
                    consent_spine_store = consent_spine_store or ConsentSpineStore()
                    if pipe is not None:
                        try:
                            consent_open_cards_snapshot = pipe.card_store.get_open_for_channel(
                                channel,
                                chat_id=chat_id,
                            )
                        except Exception:
                            consent_open_cards_snapshot = []
                    else:
                        consent_open_cards_snapshot = []
                    consent_flow_state = consent_spine_store.active_flow_state(
                        consent_binding.binding_id
                    )
                    _trace_consent(
                        daemon,
                        (
                            "consent.snapshot",
                            consent_flow_state,
                            len(consent_open_cards_snapshot or []),
                        ),
                    )
        except Exception:
            logger.debug("conversational consent snapshot skipped", exc_info=True)
            consent_owner_utterance = None
            consent_binding = None
            consent_open_cards_snapshot = None
            consent_flow_state = "IDLE"

    # Surface Parity Restoration v0: D20 capability-gap detection.
    # Placement law: after auth, before every early-return interceptor.
    # The helper creates cards through pending_card_store; this path
    # never sends card messages manually.
    #
    # None-safety (SLICE 2): the pipe-gate is OPT-IN via ``gate_d20_on_pipe``.
    # DEFAULT False reproduces the inline Telegram body EXACTLY — D20 fires
    # whenever surface_parity is on, even if pipe is None (the inline body never
    # gated on pipe). The cockpit caller passes gate_d20_on_pipe=True so that
    # when ``pipe`` is None (get_pipeline=None for the minimal S4 + synthesis
    # scope) the D20 block is SKIPPED — with pending_card_store=None,
    # maybe_fire_capability_proposal would construct a default PendingCardStore
    # and could create an orphaned durable card, outside SLICE 2's scope.
    if surface_parity_enabled() and (pipe is not None or not gate_d20_on_pipe):
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
        consent_scoped = consent_binding is not None and consent_open_cards_snapshot is not None
        if consent_scoped:
            open_cards = list(consent_open_cards_snapshot or [])
            consent_legacy_suppressed = consent_flow_state != "IDLE" or bool(open_cards)
        else:
            try:
                open_cards = pipe.card_store.get_open_for_channel(
                    channel,
                    chat_id=chat_id,
                )
            except Exception:
                open_cards = []
        if open_cards and not consent_legacy_suppressed:
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
        # A3 seam closure: the proposal interceptor answers and returns
        # before the ledger seam, so this exchange recorded nothing.
        # Provenance checked before encoding (twentieth round: not all
        # interceptor text is canned) — every proposal producer was read
        # and none calls a model; the rendered content is Maez's own
        # stored proposals, so {self_generated} is honest and a
        # model_reply row would be six false claims. SEPARATE try blocks
        # per the half-exchange rule; byte-inert while the flag is unset;
        # the reply ships regardless.
        _a3_owner_turn = None
        try:
            from core.ledger.recorder import record_owner_message

            _a3_owner_turn = record_owner_message(
                surface=owner_surface_label, raw_text=text
            )
        except Exception:
            logger.exception(
                "A3 owner record failed on the proposal path; the reply "
                "ships regardless"
            )
        try:
            from core.ledger.recorder import (
                OrganProvenance,
                record_organ_event,
            )

            record_organ_event(
                surface=owner_surface_label,
                event_origin="proposal_interceptor",
                provenance=OrganProvenance.CANNED,
                raw_text=proposal_reply,
                parent=_a3_owner_turn,
            )
        except Exception:
            logger.exception(
                "A3 organ record failed on the proposal path; the reply "
                "ships regardless"
            )
        return proposal_reply

    search_commitment_result = await try_search_commitment_intent(
        text=text,
        chat_id=chat_id,
    )
    if search_commitment_result is not None:
        # A3 seam closure: the search-commitment mouth. It was BLOCKED,
        # not merely open — the producer returned two materially
        # different provenances (canned sentences, and a formatter that
        # embeds LIVE WEB CONTENT) through one `str`, so both fixed
        # labels lied in one branch. It now EXPORTS its shape and the
        # seam binds the taint set (twenty-third round, 3-0).
        #
        # The owner's echoed query inside "Here's what I found for ..."
        # is NOT a provenance component: owner-provenance rides the
        # PARENT EDGE (owner ruling, 2026-08-28), so the frozen taint
        # map is not widened and the web set is one the writer already
        # admits. raw_text is the bytes the interceptor PRODUCED
        # (twenty-fourth round, 3-0). SEPARATE try blocks per the
        # half-exchange rule; byte-inert while the flag is unset; the
        # reply ships regardless.
        _a3_owner_turn = None
        try:
            from core.ledger.recorder import record_owner_message

            _a3_owner_turn = record_owner_message(
                surface=owner_surface_label, raw_text=text
            )
        except Exception:
            logger.exception(
                "A3 owner record failed on the search-commitment path; "
                "the reply ships regardless"
            )
        try:
            from core.ledger.recorder import record_organ_event

            record_organ_event(
                surface=owner_surface_label,
                event_origin="search_commitment",
                provenance=search_commitment_result.provenance,
                raw_text=search_commitment_result.text,
                parent=_a3_owner_turn,
            )
        except Exception:
            logger.exception(
                "A3 organ record failed on the search-commitment path; "
                "the reply ships regardless"
            )
        # A stale producer returning a bare str would raise here and
        # cost the owner the reply (Codex walk M5). The export is the
        # contract; a violation is logged and the text still ships.
        _shipped = getattr(search_commitment_result, "text", None)
        if _shipped is None:
            logger.error(
                "search-commitment producer returned %s, not a "
                "ProducedReply — the typed export contract is broken; "
                "shipping the value unrecorded",
                type(search_commitment_result).__name__,
            )
            return search_commitment_result
        return _shipped

    # Self-mod dialog bridge + recall progress receipt closures are built by
    # the adapter (they capture its loop / _surface_v2_adapter / chat_id) and
    # passed in as ``send_intermediate`` (used by run_brain_loop) and
    # ``send_progress_receipt`` (passed to handle_message as send_intermediate).

    # Fetch the last few exchanges so the brain-loop's tool-planner has
    # conversational context. Without this, the planner sees only the current
    # user message and drifts on follow-up questions. None-safe — fall open if
    # memory is unreachable.
    chat_history = None
    held_now_history = None
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
            held_now_history = None
            try:
                from core.routing.focused_cognition import (
                    held_now_enabled as _hn_on,
                    held_now_shadow_enabled as _hn_shadow,
                )

                if (_hn_on() or _hn_shadow()) and str(
                    owner_surface_label or ""
                ).startswith("telegram"):
                    _coalesced = await loop.run_in_executor(
                        get_shared_executor(),
                        lambda: _mem.get_telegram_exchanges_coalesced(
                            limit=chat_history_turns,
                            origin_surface=owner_surface_label,
                            chat_id=chat_id or None,
                        ),
                    )
                    held_now_history = [
                        {
                            "content": clean_exchange(_row.get("content") or ""),
                            "metadata": dict(_row.get("metadata") or {}),
                        }
                        for _row in _coalesced or []
                    ]
            except Exception as _hn_exc:
                logger.warning("held_now history fetch failed (v2): %s", _hn_exc)
                held_now_history = None
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

    if consent_binding is not None and consent_open_cards_snapshot:
        fact = _content_light_open_cards_fact(list(consent_open_cards_snapshot or []))
        if fact:
            context_note = f"{context_note}\n\n{fact}" if context_note else fact

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
        dispatcher_transcript = ""
        combined_mode = False
        jarvis_tool_calls: list[dict] = []
        jarvis_recall_items = ()
        consent_intent = None
        brain_failed = False
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
                                action_referents=action_referents,
                            )
                        ),
                    )
                if hasattr(_result, "transcript"):
                    jarvis_transcript = _result.transcript or ""
                    jarvis_tool_calls = list(getattr(_result, "tool_calls", []) or [])
                    jarvis_recall_items = tuple(getattr(_result, "recall_items", ()) or ())
                    consent_intent = getattr(_result, "consent_intent", None)
                    dispatcher_transcript = getattr(
                        _result, "dispatcher_transcript", ""
                    ) or ""
                    combined_mode = bool(
                        getattr(_result, "combined_mode", False)
                    )
                else:  # legacy str fallback
                    jarvis_transcript = _result or ""
        except Exception as e:
            logger.warning("brain_loop failed on %s: %s", owner_surface_label, e)
            jarvis_transcript = ""
            jarvis_tool_calls = []
            jarvis_recall_items = ()
            brain_failed = True

        if brain_failed and consent_legacy_suppressed:
            try:
                if consent_binding is not None and consent_spine_store is not None:
                    consent_spine_store.record_refusal(
                        consent_binding.binding_id,
                        "intent_unavailable",
                    )
            except Exception:
                logger.debug("consent intent_unavailable record failed", exc_info=True)
            try:
                turn.update(output="intent_unavailable")
            except Exception:
                pass
            return "intent_unavailable"

        if (
            consent_binding is not None
            and consent_owner_utterance is not None
            and consent_spine_store is not None
            and consent_intent is not None
        ):
            try:
                spine_result = consent_spine_store.handle_turn(
                    binding_id=consent_binding.binding_id,
                    utterance=consent_owner_utterance,
                    intent=consent_intent,
                    open_cards=list(consent_open_cards_snapshot or []),
                )
                _trace_consent(
                    daemon,
                    (
                        "consent.spine",
                        spine_result.state,
                        spine_result.card_id,
                        spine_result.refusal_code,
                    ),
                )
                if spine_result.state == "RESOLVING" and spine_result.card_id:
                    from core.consent.resolution import (
                        ConsentResolutionRequest,
                        resolve_consent_decision,
                    )

                    request = ConsentResolutionRequest(
                        utterance=consent_owner_utterance,
                        intent=consent_intent,
                        binding_id=consent_binding.binding_id,
                        card_id=spine_result.card_id,
                        decision=spine_result.decision or consent_intent.kind,
                    )
                    resolve_kwargs = {}
                    if consent_approve_channel is not None:
                        resolve_kwargs["approve_channel"] = consent_approve_channel
                    receipt = resolve_consent_decision(
                        request,
                        card_store=pipe.card_store,
                        binding_registry=registry,
                        paths=consent_resolution_paths,
                        flag_enabled=True,
                        **resolve_kwargs,
                    )
                    if receipt.get("outcome") == "resolved":
                        consent_spine_store.mark_resolved(consent_binding.binding_id)
                    else:
                        consent_spine_store.record_refusal(
                            consent_binding.binding_id,
                            str(
                                receipt.get("reason")
                                or receipt.get("outcome")
                                or "refused"
                            ),
                        )
                    _trace_consent(
                        daemon,
                        (
                            "consent.receipt",
                            receipt.get("outcome"),
                            receipt.get("reason"),
                        ),
                    )
            except Exception:
                logger.debug("conversational consent tap skipped", exc_info=True)

        # Synthesis stage — daemon.handle_message does the final text reply and
        # OWNS the pipeline: strip tool-call leaks, self-claim audit,
        # store_telegram, trace. For photo turns it synthesizes over a BOUNDED
        # working set internally when photo_analysis is present. The audit is
        # owned by handle_message; the core does NOT double-audit.
        subjective_duration_owner_auth = None
        if surface_parity_enabled() or felt_time_enabled:
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
                            dispatcher_transcript=dispatcher_transcript,
                            combined_mode=combined_mode,
                            context_note=context_note,
                            photo_analysis=photo_analysis,
                            chat_history=chat_history,
                            chat_id=chat_id,
                            tool_calls=jarvis_tool_calls or None,
                            recall_items=jarvis_recall_items,
                            subjective_duration_owner_auth=subjective_duration_owner_auth,
                            held_now_history=held_now_history,
                            send_intermediate=send_progress_receipt,
                            brain_failed=brain_failed,
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
