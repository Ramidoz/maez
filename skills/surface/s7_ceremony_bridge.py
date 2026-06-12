"""S7 ceremony bridge helpers for soul-affecting proposals.

The bridge never authorizes a soul write. It seeds the existing lane-3
self-mod-dialog vehicle with proposal-bound params, then later points the owner
to the existing WebAuthn ceremony if Maez's voice seat does not object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import urllib.request


@dataclass(frozen=True)
class SeedResult:
    card_request_id: str
    action: str


@dataclass(frozen=True)
class ConsultResult:
    ceremony_pointer: str | None
    blocked: bool


@dataclass
class LiveBridgeDeps:
    dream: Any
    pipeline: Any
    chat_id: str
    user_id: str = "rohit"
    channel: str = "telegram_text"

    @property
    def card_store(self) -> Any:
        return self.pipeline.card_store

    def open_dialog_for_proposal(self, prop_id: int) -> Any | None:
        try:
            cards = self.card_store.get_open_for_channel(
                self.channel,
                chat_id=self.chat_id,
            )
        except Exception:
            cards = []
        for card in cards:
            params = dict(getattr(card, "params", {}) or {})
            if int(params.get("_proposal_id") or -1) == int(prop_id):
                return SeedResult(
                    card_request_id=card.request_id,
                    action=card.action,
                )
        return None

    def s7_request_envelope_for_card(self, card: Any) -> Any:
        return self.pipeline._s7_request_envelope_for_card(card)

    def s7_request_envelope_hash_for_card(self, card: Any) -> str:
        from core.governance import operator_user_boundary as s7

        return s7.work_request_envelope_hash(
            self.s7_request_envelope_for_card(card)
        )

    def open_dialog_for_card(self, card: Any) -> None:
        from skills.self_mod_dialog import open_dialog_for_card

        open_dialog_for_card(
            store=self.pipeline._get_dialog_store(),
            card_action=card.action,
            card_params=card.params,
            card_request_id=card.request_id,
            audit_reasoning=getattr(card, "audit_reasoning", "") or "",
            concerns=list(getattr(card, "audit_concerns", []) or []),
            require_s7_linkage=True,
            s7_request_envelope_hash=self.s7_request_envelope_hash_for_card(card),
        )

    def remember_open_dialog(self, prop_id: int, card_request_id: str, action: str) -> None:
        return None

    def get_card(self, card_request_id: str) -> Any:
        card = self.card_store.get(card_request_id)
        if card is None:
            raise ValueError(f"S7 bridge card {card_request_id} not found")
        return card

    def run_voice_consultation(self, card: Any, envelope: Any) -> Any:
        return self.pipeline._s7_voice_consultation_for_card(card, envelope)

    def full_voice_bundle_present(self, request_id: str) -> bool:
        pending = getattr(self.pipeline, "_s7_pending_voice_source_bundles", None)
        if not isinstance(pending, dict):
            return False
        entry = pending.get(request_id)
        if not isinstance(entry, dict):
            return False
        return all(
            key in entry
            for key in (
                "consultation",
                "raw_response_text",
                "semantic_reader_attempt",
                "source_ref_hash",
            )
        )

    def set_blocked_for_card(self, card_request_id: str, *, reason: str) -> None:
        store = self.pipeline._get_dialog_store()
        dialog = store.get_for_card(card_request_id)
        if dialog is not None:
            store.set_blocked(dialog.dialog_id, reason=reason)
        try:
            self.card_store.block(card_request_id, reason)
        except Exception:
            pass

    def ceremony_pointer_for(self, card_request_id: str) -> str:
        return (
            "http://127.0.0.1:11437/cockpit/s7-webauthn-proof"
            f"#{card_request_id}"
        )


def cockpit_available(url: str = "http://127.0.0.1:11437/", timeout_s: float = 0.5) -> bool:
    """Return true when the local cockpit surface is reachable."""

    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            return int(getattr(response, "status", 200) or 200) < 500
    except Exception:
        return False


def _proposal_to_card_action(proposal: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    proposal_type = str(
        proposal.get("proposal_type") or proposal.get("kind") or "append"
    )
    if proposal_type in {"section_replace", "edit"}:
        return (
            "edit_soul_section",
            {
                "target_name": (
                    proposal.get("target_name")
                    or proposal.get("target_section")
                    or proposal.get("target")
                    or proposal.get("section")
                    or ""
                ),
                "new_body": proposal.get("new_body")
                if proposal.get("new_body") is not None
                else proposal.get("proposed_new_body") or "",
                "rationale": proposal.get("rationale") or proposal.get("insight") or "",
            },
        )
    return (
        "write_soul_note",
        {"note": proposal.get("note") or f"[DREAM] {proposal.get('insight') or ''}"},
    )


def seed_soul_proposal_dialog(*, prop_id: int, deps: Any) -> SeedResult | None:
    """Seed a lane-3 dialog card for a pending soul-affecting proposal.

    ``deps`` is intentionally injected. In production it is built from the live
    Telegram surface, dream state, card store, and decision pipeline; unit tests
    use fakes. The helper's invariant is narrower than the transport: card
    params must be executable by the action engine, plus the private
    ``_proposal_*`` freshness sticker that execution later strips.
    """

    existing = getattr(deps, "open_dialog_for_proposal", lambda _prop_id: None)(prop_id)
    if existing is not None:
        return SeedResult(
            card_request_id=existing.card_request_id,
            action=existing.action,
        )

    proposal = deps.dream.get_proposal(prop_id)
    if proposal is None or str(proposal.get("status") or "") != "pending":
        return None

    action, params = _proposal_to_card_action(proposal)
    params["_proposal_id"] = int(prop_id)
    params["_proposal_fingerprint"] = deps.dream.proposal_fingerprint(prop_id)

    from core.decision.decision_pipeline import (
        DecisionPipeline,
        _drop_volatile,
        _fingerprint_for_action,
    )

    state_fields = _drop_volatile(_fingerprint_for_action(action, params))
    card = deps.card_store.create_card(
        action=action,
        params=params,
        reason=f"S7 ceremony bridge for proposal #{prop_id}",
        proposed_action_summary=f"Open S7 ceremony for proposal #{prop_id}",
        classification={"intent_category": "SELF_MODIFICATION", "lane": "3"},
        state_fields=state_fields,
        channel=getattr(deps, "channel", "telegram_text"),
        chat_id=getattr(deps, "chat_id", None),
        user_id=getattr(deps, "user_id", None),
    )
    if not DecisionPipeline._is_pending_dialog_card(card):
        raise RuntimeError("S7 bridge card was not lane-3 / ESCALATE")

    deps.open_dialog_for_card(card)
    remember = getattr(deps, "remember_open_dialog", None)
    if callable(remember):
        remember(prop_id, card.request_id, action)
    return SeedResult(card_request_id=card.request_id, action=action)


def _objection_state(consultation: Any) -> str:
    return str(
        getattr(
            consultation,
            "maez_objection_state",
            getattr(consultation, "objection_state", "not_determined"),
        )
        or "not_determined"
    )


def consult_then_block_or_pointer(*, card_request_id: str, deps: Any) -> ConsultResult:
    """Run Maez's existing S7 voice seat and return a ceremony pointer or block.

    The consultation producer owns the evidence bundle. This helper never writes
    that bundle; it only verifies the reviewed producer left a complete one
    before showing the owner a WebAuthn ceremony pointer.
    """

    card = deps.get_card(card_request_id)
    envelope = deps.s7_request_envelope_for_card(card)
    consultation = deps.run_voice_consultation(card, envelope)
    objection = _objection_state(consultation)
    consultation_id = str(
        getattr(consultation, "consultation_id", "") or card_request_id
    )

    if objection == "present":
        deps.set_blocked_for_card(
            card_request_id,
            reason=f"voice_objection_present:{consultation_id}",
        )
        return ConsultResult(ceremony_pointer=None, blocked=True)

    if objection != "absent":
        deps.set_blocked_for_card(
            card_request_id,
            reason=f"voice_consultation_unavailable:{consultation_id}",
        )
        return ConsultResult(ceremony_pointer=None, blocked=True)

    if not deps.full_voice_bundle_present(envelope.request_id):
        deps.set_blocked_for_card(
            card_request_id,
            reason=f"voice_consultation_unavailable:{consultation_id}",
        )
        return ConsultResult(ceremony_pointer=None, blocked=True)

    return ConsultResult(
        ceremony_pointer=deps.ceremony_pointer_for(card_request_id),
        blocked=False,
    )
