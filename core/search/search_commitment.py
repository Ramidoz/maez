"""Typed search-offer commitments — the dignity fix, made structural.

Pure logic, no I/O: an ``OfferReceipt`` born at the substrate's offer decision,
and a conjunctive resolver that fires ONLY a low-stakes, sovereign-local, fresh,
clearly-confirmed, healthy search — never a write, a paid-API egress, a stale
offer, or a search while an approval card is awaiting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# clear-yes: bias toward following through (a stray search is cheap; the miss is
# the wound), but exclude bare acknowledgments / negations / questions.
_CLEAR_YES = re.compile(
    r"^\s*(yes|yeah|yep|yup|sure|ok(ay)?\s+(do|go|search|please)|go ahead|do it|please do|sounds good|"
    r"yes please|ok do it|search it)\b",
    re.IGNORECASE,
)


def is_clear_yes(text: str) -> bool:
    return bool(_CLEAR_YES.match((text or "").strip()))


@dataclass
class OfferReceipt:
    action_type: str          # "web_search"
    stakes: str               # "low_read"
    offered_query: str        # the EXACT query that may run
    created_ts: float
    ttl_seconds: float
    ttl_turns: int
    requires_confirmation: bool
    confirmation_mode: str    # "clear_yes_ok"
    executor: str             # "searxng"
    egress_class: str         # "sovereign_local_search"

    def is_fresh(self, now_ts: float, turns_since: int) -> bool:
        return (now_ts - self.created_ts) <= self.ttl_seconds and turns_since <= self.ttl_turns


@dataclass
class ResolveDecision:
    execute: bool
    reason: str
    query: Optional[str] = None


def resolve_affirmation(receipt, text, *, health, has_awaiting_card, now_ts, turns_since) -> ResolveDecision:
    """The conjunctive gate. Auto-execute ONLY when every guard holds. Order is
    chosen so the safety-critical reasons (card, stakes, egress) are explicit."""
    if receipt is None:
        return ResolveDecision(False, "no_pending_offer")
    if has_awaiting_card:
        return ResolveDecision(False, "card_precedence")        # an approval card wins over a search
    if not is_clear_yes(text):
        return ResolveDecision(False, "not_clear_yes")
    if not receipt.is_fresh(now_ts, turns_since):
        return ResolveDecision(False, "stale_offer")
    if receipt.stakes != "low_read":
        return ResolveDecision(False, "stakes_too_high")        # trap-proof: no write on "sure"
    if receipt.egress_class != "sovereign_local_search":
        return ResolveDecision(False, "egress_not_sovereign")   # trap-proof: no paid-API egress on "sure"
    if health != "healthy":
        return ResolveDecision(False, "search_unhealthy")
    return ResolveDecision(True, "execute", query=receipt.offered_query)  # egress rail: the STORED query only
