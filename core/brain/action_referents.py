"""ActionReferent union — Phase 2 commit D (gate-approved passes 3-5).

The ONLY objects an anaphoric go-ahead ("go ahead", "do it") may
legally resolve against. History prose NEVER confers referent
authority. Fallback-only: the existing pre-brain interceptors (cards,
proposals, search commitments) keep their authority and run first;
this assembler feeds the syntactic floor's anaphora branch only.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("maez")


@dataclass(frozen=True)
class CardReferent:
    request_id: str
    action: str
    status: str  # open | deferred (both are awaiting per store semantics)


@dataclass(frozen=True)
class CommitmentReferent:
    offered_query: str
    created_ts: float


@dataclass(frozen=True)
class ProposalReferent:
    kind: str
    shown_ts: float


_PROPOSAL_FRESHNESS_S = 600.0


def assemble_action_referents(
    *,
    channel: str,
    chat_id: str,
    user_id: str,
    card_store=None,
    controller=None,
    proposal_entry: dict | None = None,
    now_ts: float | None = None,
    current_turn_seq: "int | None" = None,
) -> tuple:
    """Best-effort, read-only, never raises. Empty tuple = no referent
    = anaphora stays 'none' (conversation wins)."""
    now = time.time() if now_ts is None else now_ts
    out: list = []

    # CardReferent: OPEN + DEFERRED (both awaiting; gate P3a reversal),
    # getter scopes channel+chat, we add the explicit user_id filter.
    try:
        if card_store is not None:
            for rec in card_store.get_open_for_channel(channel, chat_id) or []:
                rec_user = getattr(rec, "user_id", None)
                if rec_user and str(rec_user) != str(user_id):
                    continue
                out.append(CardReferent(
                    request_id=str(getattr(rec, "request_id", "")),
                    action=str(getattr(rec, "action", "")),
                    status=str(getattr(rec, "status", "")),
                ))
    except Exception as exc:
        logger.debug("card referent assembly skipped: %s", exc)

    # CommitmentReferent: OfferReceipt gated by is_fresh. turns_since
    # from the turn-seq store when BOTH ordinals exist; otherwise
    # turns-based freshness is conservative-off (0) and time governs.
    try:
        if controller is not None:
            receipt = controller.get_search_offer(channel, chat_id)
            if receipt is not None:
                created_seq = getattr(receipt, "created_turn_seq", None)
                turns_since = (
                    max(current_turn_seq - created_seq, 0)
                    if (current_turn_seq is not None and created_seq is not None
                        and current_turn_seq >= created_seq)
                    else 0
                )
                if receipt.is_fresh(now, turns_since):
                    out.append(CommitmentReferent(
                        offered_query=str(getattr(receipt, "offered_query", "")),
                        created_ts=float(getattr(receipt, "created_ts", 0.0)),
                    ))
    except Exception as exc:
        logger.debug("commitment referent assembly skipped: %s", exc)

    # ProposalReferent: adapter last-shown entry, chat-scoped, <=600s.
    try:
        if proposal_entry:
            shown = float(proposal_entry.get("ts", 0.0))
            if shown and (now - shown) <= _PROPOSAL_FRESHNESS_S:
                out.append(ProposalReferent(
                    kind=str(proposal_entry.get("kind", "proposal")),
                    shown_ts=shown,
                ))
    except Exception as exc:
        logger.debug("proposal referent assembly skipped: %s", exc)

    return tuple(out)
