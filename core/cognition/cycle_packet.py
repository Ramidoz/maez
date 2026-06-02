"""Focused evidence packet for daemon cognition cycles.

This module selects sourced evidence for reflection. It does not summarize or
conclude; the daemon brain produces any reflection from the rendered items.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from typing import Iterable

from core.routing.focused_cognition import (
    EvidenceItem,
    WorkingSet,
    _render_evidence_lines,
)


CYCLE_REFLECTION_INSTRUCTION = (
    "Reflect over the evidence below. Notice what matters, connect, wonder. "
    "Ground what you say in the [E#] items and their authority labels; treat a "
    "signal_absence item as absent, never inferred present. If nothing here is "
    "worth a thought, say so plainly."
)

_CRITICAL_SOURCE_TYPES = ("signal_absence", "action_outcome", "open_loop")
_SOURCE_PRIORITY = {
    "signal_absence": 0,
    "action_outcome": 1,
    "open_loop": 2,
    "builder_event": 3,
    "quality_signal": 4,
    "fresh_evidence": 5,
    "memory_evidence": 6,
    "memory_context": 7,
    "web_context": 8,
}


@dataclass(frozen=True)
class CycleEvidenceCandidate:
    source_type: str
    text: str
    durable_id: str = ""
    temporal_provenance: dict | None = None
    salience: int = 0


def _content_hash(text: str) -> str:
    return "ch_" + hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _token_est(text: str) -> int:
    return max(1, len(text or "") // 4)


def _item_token_est(item: EvidenceItem) -> int:
    return _token_est(item.text)


def _candidate_sort_key(candidate: CycleEvidenceCandidate) -> tuple[int, int, str]:
    return (
        _SOURCE_PRIORITY.get(candidate.source_type, 99),
        -int(candidate.salience or 0),
        candidate.durable_id or candidate.text,
    )


def _to_item(candidate: CycleEvidenceCandidate, index: int) -> EvidenceItem:
    text = str(candidate.text or "").strip()
    return EvidenceItem(
        local_label=f"E{index}",
        source_type=str(candidate.source_type or "memory_context"),
        text=text,
        durable_id=candidate.durable_id or _content_hash(text),
        temporal_provenance=candidate.temporal_provenance,
    )


def select_cycle_evidence(
    candidates: Iterable[CycleEvidenceCandidate],
    *,
    budget_tokens: int,
) -> list[EvidenceItem]:
    """Select a bounded, provenance-preserving cycle evidence set.

    The selector reserves room for anti-fabrication rails and recent failures,
    then fills the remaining budget with a balanced pass over source types so a
    memory dump cannot crowd out other evidence classes.
    """

    clean_candidates = [
        candidate
        for candidate in candidates
        if str(getattr(candidate, "text", "") or "").strip()
    ]
    if not clean_candidates:
        return []

    budget = max(int(budget_tokens or 0), 1)
    selected: list[CycleEvidenceCandidate] = []
    selected_ids: set[str] = set()
    used_tokens = 0

    def maybe_add(candidate: CycleEvidenceCandidate) -> bool:
        nonlocal used_tokens
        identity = candidate.durable_id or candidate.text
        if identity in selected_ids:
            return False
        cost = _token_est(candidate.text)
        if used_tokens + cost > budget and selected:
            return False
        selected.append(candidate)
        selected_ids.add(identity)
        used_tokens += cost
        return True

    grouped: dict[str, list[CycleEvidenceCandidate]] = defaultdict(list)
    for candidate in clean_candidates:
        grouped[candidate.source_type].append(candidate)
    for group in grouped.values():
        group.sort(key=_candidate_sort_key)

    for source_type in _CRITICAL_SOURCE_TYPES:
        if grouped.get(source_type):
            maybe_add(grouped[source_type][0])

    per_source_soft_cap = max(budget // max(len(grouped), 1), 1)
    source_used: dict[str, int] = defaultdict(int)
    for candidate in selected:
        source_used[candidate.source_type] += _token_est(candidate.text)

    remaining = [
        candidate
        for candidate in sorted(clean_candidates, key=_candidate_sort_key)
        if (candidate.durable_id or candidate.text) not in selected_ids
    ]
    for candidate in remaining:
        cost = _token_est(candidate.text)
        if source_used[candidate.source_type] + cost > per_source_soft_cap:
            other_sources_available = any(
                (
                    other.source_type != candidate.source_type
                    and (other.durable_id or other.text) not in selected_ids
                    and used_tokens + _token_est(other.text) <= budget
                )
                for other in remaining
            )
            if other_sources_available:
                continue
        if maybe_add(candidate):
            source_used[candidate.source_type] += cost

    items = [_to_item(candidate, index + 1) for index, candidate in enumerate(selected)]
    return items


def build_cycle_packet(items: Iterable[EvidenceItem]) -> WorkingSet:
    """Render cycle evidence into the shared focused-cognition WorkingSet type."""

    item_list = list(items)
    render_version = "v2"
    ordered = "\n".join(_render_evidence_lines(item_list, render_version=render_version))
    total_chars = len(ordered) + len(CYCLE_REFLECTION_INSTRUCTION)
    return WorkingSet(
        items=item_list,
        ordered_evidence_text=ordered,
        owner_question=CYCLE_REFLECTION_INSTRUCTION,
        working_set_chars=total_chars,
        working_set_tokens_est=total_chars // 4,
        citation_render_version=render_version,
    )
