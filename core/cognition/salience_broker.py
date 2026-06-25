"""Slice C / C1 shadow attention broker.

This is a motion detector, not a taste-maker: it observes only which idle-window
facts changed since the last pulse. It never claims a fact is important.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json

BROKER_VERSION = "salience_broker.v0"
STRATEGY = "changed_since_last"
WATCHED_KEYS = ("time_facts", "body_state", "open_loops", "recent_private_thoughts")


@dataclass(frozen=True)
class Proposal:
    fact_key: str
    change_kind: str
    strategy: str = STRATEGY


def _signature(value: object) -> str:
    if value in (None, {}, (), []):
        return "empty"
    canonical = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def fact_signatures(facts: Mapping[str, object]) -> dict[str, str]:
    window = facts or {}
    return {key: _signature(window.get(key)) for key in WATCHED_KEYS}


def _change_kind(baseline_signature: str, current_signature: str) -> str:
    if baseline_signature == "empty" and current_signature != "empty":
        return "appeared"
    if baseline_signature != "empty" and current_signature == "empty":
        return "cleared"
    return "changed"


def propose_changes(
    current_signatures: Mapping[str, str],
    baseline_signatures: Mapping[str, str] | None,
) -> list[Proposal]:
    if baseline_signatures is None:
        return []
    proposals: list[Proposal] = []
    for key in WATCHED_KEYS:
        current = current_signatures.get(key, "empty")
        baseline = baseline_signatures.get(key, "empty")
        if current != baseline:
            proposals.append(
                Proposal(
                    fact_key=key,
                    change_kind=_change_kind(baseline, current),
                )
            )
    return proposals


def broker_receipt(proposals: list[Proposal], *, cold_start: bool) -> dict:
    return {
        "schema_version": BROKER_VERSION,
        "strategy": STRATEGY,
        "cold_start": bool(cold_start),
        "watched_keys": list(WATCHED_KEYS),
        "proposals": [
            {"fact_key": proposal.fact_key, "change_kind": proposal.change_kind}
            for proposal in proposals
        ],
        "proposal_count": len(proposals),
    }
