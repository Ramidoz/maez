# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Inert recall projection read-models.

Slice 4a creates a first-class projection object without changing live
behavior. The default projection is identity-only: same order, same
text, same lifecycle labels. Audit evidence must keep using raw
ledger-derived self_history, not these projection objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Iterable


PROJECTION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProjectionPolicy:
    """Versioned covenant policy for a projection report."""

    projection_rules_schema_version: int = PROJECTION_SCHEMA_VERSION
    projection_policy_id: str = "maez-memory-projection-v1"
    projection_policy_version: str = "1.0.0"
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "kind": self.kind,
            "lifecycle_stage": self.lifecycle_stage,
            "projected_text": self.projected_text,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
            "rule_id": self.rule_id,
            "projection_effect": self.projection_effect,
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

    @property
    def projected_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "policy": self.policy.to_dict(),
            "raw_count": self.raw_count,
            "projected_count": self.projected_count,
            "omitted_count": self.omitted_count,
            "items": [item.to_dict() for item in self.items],
        }


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry_text(entry: dict[str, Any]) -> str:
    value = entry.get("utterance_summary")
    if value is None:
        value = entry.get("raw_text")
    return value if isinstance(value, str) else ""


def _validate_policy(policy: ProjectionPolicy) -> None:
    if policy.projection_rules_schema_version != PROJECTION_SCHEMA_VERSION:
        raise ValueError(
            "projection policy schema version does not match report schema "
            f"version {PROJECTION_SCHEMA_VERSION}"
        )


def project_self_history(
    entries: Iterable[dict[str, Any]],
    *,
    policy: ProjectionPolicy = DEFAULT_POLICY,
) -> ProjectionReport:
    """Return an inert projection report for self_history entries.

    The function copies from caller-supplied entries and never mutates
    them. It preserves order, text, kind, turn_id, and lifecycle_stage.
    """
    _validate_policy(policy)
    raw_entries = [dict(entry) for entry in entries]
    items: list[ProjectedMemoryItem] = []
    for entry in raw_entries:
        text = _entry_text(entry)
        turn_id = str(entry.get("turn_id") or "")
        kind = str(entry.get("kind") or entry.get("turn_kind") or "")
        lifecycle_stage = str(entry.get("lifecycle_stage") or "unknown")
        source = ProjectionSourceRef(
            turn_id=turn_id,
            kind=kind,
            lifecycle_stage=lifecycle_stage,
            source_text_sha256=_hash_text(text),
        )
        items.append(ProjectedMemoryItem(
            turn_id=turn_id,
            kind=kind,
            lifecycle_stage=lifecycle_stage,
            projected_text=text,
            source_refs=[source],
            rule_id=policy.rule_id,
        ))
    return ProjectionReport(
        schema_version=PROJECTION_SCHEMA_VERSION,
        policy=policy,
        items=items,
        raw_count=len(raw_entries),
        omitted_count=0,
    )
