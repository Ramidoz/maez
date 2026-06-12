"""S7 ceremony bridge helpers for soul-affecting proposals.

The bridge never authorizes a soul write. It seeds the existing lane-3
self-mod-dialog vehicle with proposal-bound params, then later points the owner
to the existing WebAuthn ceremony if Maez's voice seat does not object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SeedResult:
    card_request_id: str
    action: str


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
