# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Recall projection read-models.

Slice 4a created the first-class projection object. Slice 4b adds a
shadow strengthening rule without changing production recall behavior.
Audit evidence must keep using raw ledger-derived self_history, not
these projection objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import time
from typing import Any, Iterable


PROJECTION_SCHEMA_VERSION = 2
MIN_TEMPORAL_SEPARATION_SECONDS = 3600
EXCLUDED_STRENGTHENING_KINDS = frozenset({"daemon_cycle"})
POLICY_DOC_PATH = "docs/governance/MEMORY_PROJECTION_RULES.md"


@dataclass(frozen=True)
class ProjectionPolicy:
    """Versioned covenant policy for a projection report."""

    projection_rules_schema_version: int = PROJECTION_SCHEMA_VERSION
    projection_policy_id: str = "maez-memory-projection-v1"
    projection_policy_version: str = "2.0.0"
    rule_id: str = "identity.v1"
    rule_version: str = "1.0.0"
    raw_truth_invariant: str = "append_only_never_delete"
    allowed_change_surface: str = "projection_only_no_audit_evidence"

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_rules_schema_version":
                self.projection_rules_schema_version,
            "projection_policy_id": self.projection_policy_id,
            "projection_policy_version": self.projection_policy_version,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "raw_truth_invariant": self.raw_truth_invariant,
            "allowed_change_surface": self.allowed_change_surface,
        }


DEFAULT_POLICY = ProjectionPolicy()
REPETITION_WITH_CONTINUITY_POLICY = ProjectionPolicy(
    rule_id="repetition_with_continuity.v1",
    rule_version="1.0.0",
)


@dataclass(frozen=True)
class ProjectionCandidate:
    """Typed observation input for non-self-history recall candidates.

    Slice 4c uses this adapter shape for offline observation only. It
    lets lived-recall-shaped candidates enter the projection rule without
    pretending that episodes, edges, and self_history are the same organ.
    """

    candidate_id: str
    candidate_kind: str
    text: str
    source_ids: tuple[str, ...]
    continuity_key: str
    continuity_key_basis: str
    timestamp: float
    lifecycle_stage: str
    trust_scope: str
    counterevidence_for: str = ""


@dataclass(frozen=True)
class ProjectionSourceRef:
    """Raw source pointer for one projected item."""

    turn_id: str
    kind: str
    lifecycle_stage: str
    source_text_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "kind": self.kind,
            "lifecycle_stage": self.lifecycle_stage,
            "source_text_sha256": self.source_text_sha256,
        }


@dataclass(frozen=True)
class ProjectedMemoryItem:
    """One projected memory item.

    In Slice 4a, ``projected_text`` is always identical to the raw
    self_history summary. Later slices may add non-identity rules, but
    must preserve source refs and keep audit evidence raw.
    """

    turn_id: str
    kind: str
    lifecycle_stage: str
    projected_text: str
    source_refs: list[ProjectionSourceRef]
    rule_id: str
    projection_effect: str = "identity"
    strength_score: int = 0
    strength_reasons: list[str] = field(default_factory=list)
    rule_inputs: dict[str, Any] = field(default_factory=dict)
    counterevidence_refs: list[ProjectionSourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "kind": self.kind,
            "lifecycle_stage": self.lifecycle_stage,
            "projected_text": self.projected_text,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
            "rule_id": self.rule_id,
            "projection_effect": self.projection_effect,
            "strength_score": self.strength_score,
            "strength_reasons": list(self.strength_reasons),
            "rule_inputs": dict(self.rule_inputs),
            "counterevidence_refs": [
                ref.to_dict() for ref in self.counterevidence_refs
            ],
        }


@dataclass(frozen=True)
class ProjectionReport:
    """Projection health record for a bounded recall set."""

    schema_version: int
    policy: ProjectionPolicy
    items: list[ProjectedMemoryItem]
    created_at: float = field(default_factory=time.time)
    raw_count: int = 0
    omitted_count: int = 0
    audit_boundary: str = "not_audit_evidence"
    policy_doc_path: str = POLICY_DOC_PATH
    policy_doc_sha256: str = ""

    @property
    def projected_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "policy": self.policy.to_dict(),
            "audit_boundary": self.audit_boundary,
            "policy_doc_path": self.policy_doc_path,
            "policy_doc_sha256": self.policy_doc_sha256,
            "raw_count": self.raw_count,
            "projected_count": self.projected_count,
            "omitted_count": self.omitted_count,
            "items": [item.to_dict() for item in self.items],
        }


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _policy_doc_sha256() -> str:
    repo = Path(__file__).resolve().parents[2]
    path = repo / POLICY_DOC_PATH
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _entry_text(entry: dict[str, Any]) -> str:
    value = entry.get("utterance_summary")
    if value is None:
        value = entry.get("raw_text")
    return value if isinstance(value, str) else ""


def _timestamp(entry: dict[str, Any]) -> float | None:
    value = entry.get("timestamp")
    if isinstance(value, int | float):
        return float(value)
    return None


def _validate_policy(policy: ProjectionPolicy) -> None:
    if policy.projection_rules_schema_version != PROJECTION_SCHEMA_VERSION:
        raise ValueError(
            "projection policy schema version does not match report schema "
            f"version {PROJECTION_SCHEMA_VERSION}"
        )


def _source_ref(entry: dict[str, Any]) -> ProjectionSourceRef:
    text = _entry_text(entry)
    return ProjectionSourceRef(
        turn_id=str(entry.get("turn_id") or ""),
        kind=str(entry.get("kind") or entry.get("turn_kind") or ""),
        lifecycle_stage=str(entry.get("lifecycle_stage") or "unknown"),
        source_text_sha256=_hash_text(text),
    )


def _candidate_to_entry(candidate: ProjectionCandidate) -> dict[str, Any]:
    """Validate and adapt one typed candidate to the projection entry shape."""

    if not candidate.candidate_id:
        raise ValueError("projection candidate requires candidate_id")
    if not candidate.candidate_kind:
        raise ValueError("projection candidate requires candidate_kind")
    if candidate.candidate_kind in EXCLUDED_STRENGTHENING_KINDS:
        raise ValueError("projection candidate kind daemon_cycle is forbidden")
    if not candidate.text:
        raise ValueError("projection candidate requires text")
    if not candidate.source_ids or any(not sid for sid in candidate.source_ids):
        raise ValueError("projection candidate requires non-empty source_ids")
    if not candidate.continuity_key:
        raise ValueError("projection candidate requires continuity_key")
    if candidate.continuity_key_basis != "source_metadata":
        raise ValueError(
            "projection candidate continuity_key_basis must be source_metadata"
        )
    if not candidate.lifecycle_stage:
        raise ValueError("projection candidate requires lifecycle_stage")
    if candidate.trust_scope != "owner_private":
        raise ValueError(
            "projection candidate trust_scope must be owner_private"
        )
    if candidate.timestamp is None:
        raise ValueError("projection candidate requires timestamp")
    return {
        "turn_id": candidate.candidate_id,
        "kind": candidate.candidate_kind,
        "utterance_summary": candidate.text,
        "timestamp": candidate.timestamp,
        "lifecycle_stage": candidate.lifecycle_stage,
        "continuity_key": candidate.continuity_key,
        "counterevidence_for": candidate.counterevidence_for,
        "strengthening_source_ids": tuple(candidate.source_ids),
    }


def _counterevidence_by_key(
    entries: Iterable[dict[str, Any]],
) -> dict[str, list[ProjectionSourceRef]]:
    out: dict[str, list[ProjectionSourceRef]] = {}
    for entry in entries:
        key = entry.get("counterevidence_for")
        if isinstance(key, str) and key:
            out.setdefault(key, []).append(_source_ref(entry))
    return out


def _group_entries_by_continuity_key(
    entries: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        key = entry.get("continuity_key")
        if isinstance(key, str) and key:
            groups.setdefault(key, []).append(entry)
    return groups


def _has_temporal_distinctness(group: list[dict[str, Any]]) -> bool:
    timestamps = sorted(
        t for entry in group
        if _is_strengthening_eligible(entry)
        if (t := _timestamp(entry)) is not None
    )
    if len(timestamps) < 2:
        return False
    return (timestamps[-1] - timestamps[0]) >= MIN_TEMPORAL_SEPARATION_SECONDS


def _is_strengthening_eligible(entry: dict[str, Any]) -> bool:
    kind = str(entry.get("kind") or entry.get("turn_kind") or "")
    return kind not in EXCLUDED_STRENGTHENING_KINDS


def _strengthening_inputs(
    entry: dict[str, Any],
    *,
    group: list[dict[str, Any]],
) -> dict[str, Any]:
    independent_source_ids: set[str] = set()
    for e in group:
        if not _is_strengthening_eligible(e):
            continue
        source_ids = e.get("strengthening_source_ids")
        if isinstance(source_ids, tuple | list):
            independent_source_ids.update(str(sid) for sid in source_ids if sid)
        elif e.get("turn_id"):
            independent_source_ids.add(str(e.get("turn_id") or ""))
    return {
        "continuity_key": entry.get("continuity_key") or "",
        "independent_source_count": len(independent_source_ids),
        "temporal_distinct": _has_temporal_distinctness(group),
        "eligible_for_strengthening": _is_strengthening_eligible(entry),
        "min_temporal_separation_seconds": MIN_TEMPORAL_SEPARATION_SECONDS,
        "excluded_strengthening_kinds": sorted(EXCLUDED_STRENGTHENING_KINDS),
    }


def _projection_effect_for(
    entry: dict[str, Any],
    *,
    policy: ProjectionPolicy,
    group: list[dict[str, Any]],
) -> tuple[str, int, list[str], dict[str, Any]]:
    rule_inputs = _strengthening_inputs(entry, group=group)
    if policy.rule_id != "repetition_with_continuity.v1":
        return "identity", 0, [], rule_inputs
    can_strengthen = (
        rule_inputs["eligible_for_strengthening"]
        and rule_inputs["independent_source_count"] >= 2
        and rule_inputs["temporal_distinct"]
    )
    if not can_strengthen:
        return "identity", 0, [], rule_inputs
    return (
        "strengthened",
        1,
        ["temporal_distinct_repetition"],
        rule_inputs,
    )


def project_self_history(
    entries: Iterable[dict[str, Any]],
    *,
    policy: ProjectionPolicy = DEFAULT_POLICY,
) -> ProjectionReport:
    """Return a projection report for self_history entries.

    The function copies from caller-supplied entries and never mutates
    them. It preserves order, text, kind, turn_id, and lifecycle_stage.
    Non-identity policies may annotate items, but they remain
    conversation projection data and not audit evidence.
    """
    _validate_policy(policy)
    raw_entries = [dict(entry) for entry in entries]
    groups = _group_entries_by_continuity_key(raw_entries)
    counterevidence = _counterevidence_by_key(raw_entries)
    items: list[ProjectedMemoryItem] = []
    for entry in raw_entries:
        text = _entry_text(entry)
        turn_id = str(entry.get("turn_id") or "")
        kind = str(entry.get("kind") or entry.get("turn_kind") or "")
        lifecycle_stage = str(entry.get("lifecycle_stage") or "unknown")
        source = _source_ref(entry)
        key = entry.get("continuity_key")
        group = groups.get(key, [entry]) if isinstance(key, str) else [entry]
        effect, strength_score, reasons, rule_inputs = _projection_effect_for(
            entry,
            policy=policy,
            group=group,
        )
        items.append(ProjectedMemoryItem(
            turn_id=turn_id,
            kind=kind,
            lifecycle_stage=lifecycle_stage,
            projected_text=text,
            source_refs=[source],
            rule_id=policy.rule_id,
            projection_effect=effect,
            strength_score=max(0, strength_score),
            strength_reasons=reasons,
            rule_inputs=rule_inputs,
            counterevidence_refs=(
                counterevidence.get(key, []) if isinstance(key, str) else []
            ),
        ))
    return ProjectionReport(
        schema_version=PROJECTION_SCHEMA_VERSION,
        policy=policy,
        items=items,
        raw_count=len(raw_entries),
        omitted_count=0,
        policy_doc_sha256=_policy_doc_sha256(),
    )


def project_candidates(
    candidates: Iterable[ProjectionCandidate],
    *,
    policy: ProjectionPolicy = DEFAULT_POLICY,
) -> ProjectionReport:
    """Return a projection report for typed observation candidates.

    This is the Slice 4c adapter path. It is intentionally equivalent to
    projecting validated entry dictionaries, so report schema v2 remains
    readable and unchanged.
    """

    return project_self_history(
        [_candidate_to_entry(candidate) for candidate in candidates],
        policy=policy,
    )
