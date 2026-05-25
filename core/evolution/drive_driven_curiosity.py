# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Drive-driven curiosity adapter over the existing wonderings store."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Callable, Mapping

from core.evolution.wonderings import Wonderings
from core.policies.exceptions import SubjectKindRefused
from core.policies.third_party_subject_gate import SubjectKind


class LegacyWonderingProjectionRefused(ValueError):
    """Raised when a pre-bond `_LEGACY` wondering is projected as curiosity."""


class ProducerRegistrationRefused(ValueError):
    """Raised when an encounter producer violates registration invariants."""


class SidecarBondMismatchRefused(ValueError):
    """Raised when sidecar metadata disagrees with its parent wondering bond."""


class SidecarDuplicateWriteRefused(ValueError):
    """Raised when code tries to rewrite append-only sidecar metadata."""


class EncounterSource(Enum):
    WONDERING_GENERATED = "wondering_generated"
    EXPLICIT_OWNER_FLAG = "explicit_owner_flag"
    SUBJECTIVE_DURATION_MEANINGFUL_EVENT = "subjective_duration_meaningful_event"
    COGNITION_QUALITY_UNCERTAINTY = "cognition_quality_uncertainty"
    UNRESOLVED_TOOL_LOOP_BRANCH = "unresolved_tool_loop_branch"
    PRIVATE_THOUGHT_LANDED = "private_thought_landed"
    CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY = (
        "conversation_declared_unknown_via_cognition_quality"
    )


TIMER_ONLY_REFUSAL_SET = frozenset({"timer", "cron", "scheduler_tick"})
DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF = "drive_driven_curiosity"
MANUAL_TEST_PRODUCER_REF = "manual_test_producer"


@dataclass(frozen=True)
class CuriosityObject:
    wondering_id: int
    bond_id: str
    question: str
    encounter_source: str
    priority_class: str
    salience: float
    subject_kind: SubjectKind | str = SubjectKind.UNKNOWN
    subject_ref: str | None = None
    resolution_marker_type: str | None = None
    resolution_marker_utc: str | None = None


@dataclass(frozen=True)
class ProducerEntry:
    source: EncounterSource
    evidence_pointer_kind: str
    producer_ref: object
    canary: bool
    create: Callable[[Mapping], CuriosityObject]


@dataclass(frozen=True)
class ProducerSourceDeferred:
    source: EncounterSource
    reason: str


_REGISTERED_PRODUCERS: dict[EncounterSource, ProducerEntry | ProducerSourceDeferred] = {}


def _digest(value: object) -> str | None:
    if value is None:
        return None
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _producer_ref_value(producer_ref: object) -> str:
    return str(getattr(producer_ref, "value", producer_ref))


def _emit_subject_kind_refused(fields: Mapping, refusal_kind: str) -> None:
    diagnostic_sink = fields.get("diagnostic_sink")
    if not callable(diagnostic_sink):
        return
    diagnostic_sink(
        {
            "event_type": "SUBJECT_KIND_REFUSED",
            "refusal_kind": refusal_kind,
            "bond_digest": _digest(fields.get("bond_id")),
            "subject_kind": fields.get("subject_kind"),
            "subject_ref_digest": _digest(fields.get("subject_ref")),
        }
    )


def clear_encounter_producers_for_tests() -> None:
    _REGISTERED_PRODUCERS.clear()


def v1_wired_encounter_sources() -> tuple[EncounterSource, ...]:
    return (
        EncounterSource.WONDERING_GENERATED,
        EncounterSource.EXPLICIT_OWNER_FLAG,
        EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT,
    )


def deferred_encounter_sources() -> tuple[EncounterSource, ...]:
    return (
        EncounterSource.COGNITION_QUALITY_UNCERTAINTY,
        EncounterSource.UNRESOLVED_TOOL_LOOP_BRANCH,
        EncounterSource.PRIVATE_THOUGHT_LANDED,
        EncounterSource.CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY,
    )


def _subject_kind(value: object, *, fields: Mapping | None = None) -> SubjectKind:
    if isinstance(value, SubjectKind):
        return value
    if value is None:
        if fields is not None:
            _emit_subject_kind_refused(fields, "missing_subject_kind")
        raise SubjectKindRefused("subject_kind is required")
    if isinstance(value, str):
        try:
            return SubjectKind(value)
        except ValueError:
            pass
    if fields is not None:
        _emit_subject_kind_refused(fields, "unrecognized_subject_kind")
    raise SubjectKindRefused("subject_kind is required and must be recognized")


def _third_party_consent_allows_external_research(
    *,
    bond_id: str,
    subject_ref: str | None,
) -> bool:
    # OWNER_EXPLICIT consent memory lands later in this slice. The v1 default
    # must fail closed until a real consent lookup is wired.
    return False


def _materialize_curiosity_object(fields: Mapping) -> CuriosityObject:
    if not fields.get("bond_id"):
        raise ValueError("bond_id is required for curiosity object creation")
    kind = _subject_kind(fields.get("subject_kind"), fields=fields)
    if kind is SubjectKind.NAMED_THIRD_PARTY and not _third_party_consent_allows_external_research(
        bond_id=str(fields["bond_id"]),
        subject_ref=fields.get("subject_ref"),
    ):
        _emit_subject_kind_refused(fields, "named_third_party_without_owner_explicit_consent")
        raise SubjectKindRefused("NAMED_THIRD_PARTY requires OWNER_EXPLICIT consent")
    return CuriosityObject(
        wondering_id=int(fields["wondering_id"]),
        bond_id=str(fields["bond_id"]),
        question=str(fields["question"]),
        encounter_source=str(fields["encounter_source"]),
        priority_class=str(fields["priority_class"]),
        salience=float(fields["salience"]),
        subject_kind=kind,
        subject_ref=fields.get("subject_ref"),
        resolution_marker_type=fields.get("resolution_marker_type"),
        resolution_marker_utc=fields.get("resolution_marker_utc"),
    )


def _wrap_with_subject_kind_validator(
    create_curiosity_object: Callable[[Mapping], Mapping | CuriosityObject],
) -> Callable[[Mapping], CuriosityObject]:
    def wrapped(seed: Mapping) -> CuriosityObject:
        result = create_curiosity_object(seed)
        if isinstance(result, CuriosityObject):
            fields = result.__dict__
            if "diagnostic_sink" in seed:
                fields = {**fields, "diagnostic_sink": seed["diagnostic_sink"]}
        else:
            fields = result
        return _materialize_curiosity_object(fields)

    return wrapped


def register_encounter_producer(
    *,
    source: EncounterSource,
    evidence_pointer_kind: str,
    producer_ref: object,
    create_curiosity_object: Callable[[Mapping], Mapping | CuriosityObject],
    canary: bool = False,
) -> None:
    if evidence_pointer_kind in TIMER_ONLY_REFUSAL_SET:
        raise ProducerRegistrationRefused(
            f"timer-only producer refused: {evidence_pointer_kind}"
        )
    if (not canary) and _producer_ref_value(producer_ref) == MANUAL_TEST_PRODUCER_REF:
        raise ProducerRegistrationRefused(
            "MANUAL_TEST_PRODUCER is reserved for canary/manual seam tests"
        )
    _REGISTERED_PRODUCERS[source] = ProducerEntry(
        source=source,
        evidence_pointer_kind=str(evidence_pointer_kind),
        producer_ref=producer_ref,
        canary=bool(canary),
        create=_wrap_with_subject_kind_validator(create_curiosity_object),
    )


def get_registered_producer(source: EncounterSource) -> ProducerEntry | ProducerSourceDeferred:
    return _REGISTERED_PRODUCERS[source]


_DEFERRED_REASONS = {
    EncounterSource.COGNITION_QUALITY_UNCERTAINTY: (
        "upstream cognition_quality signal lacks durable event IDs with bond attribution"
    ),
    EncounterSource.UNRESOLVED_TOOL_LOOP_BRANCH: (
        "tool-loop state is process-scoped and lacks a stable event-id table"
    ),
    EncounterSource.PRIVATE_THOUGHT_LANDED: (
        "private_thoughts has no bond_id column in this slice"
    ),
    EncounterSource.CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY: (
        "cognition_quality boundary lacks durable event IDs with bond attribution"
    ),
}


def _default_wired_fields(source: EncounterSource, seed: Mapping) -> dict:
    return {
        "wondering_id": seed.get("wondering_id", 1),
        "bond_id": seed.get("bond_id", "private_owner"),
        "question": seed.get("question", "drive curiosity seed"),
        "encounter_source": source.value,
        "priority_class": seed.get("priority_class", "owner_bond"),
        "salience": seed.get("salience", 0.5),
        "subject_kind": seed.get("subject_kind", SubjectKind.OWNER_BOND_RELATIONAL),
        "subject_ref": seed.get("subject_ref"),
    }


def register_default_encounter_producers() -> None:
    for source in v1_wired_encounter_sources():
        evidence_pointer_kind = (
            "subjective_duration_salience_events.event_id"
            if source is EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            else "wonderings.id"
        )
        register_encounter_producer(
            source=source,
            evidence_pointer_kind=evidence_pointer_kind,
            producer_ref=DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF,
            create_curiosity_object=lambda seed, source=source: _default_wired_fields(
                source,
                seed,
            ),
        )
    for source, reason in _DEFERRED_REASONS.items():
        _REGISTERED_PRODUCERS[source] = ProducerSourceDeferred(source=source, reason=reason)


def record_wondering_drive_metadata(
    store: Wonderings,
    *,
    wondering_id: int,
    bond_id: str,
    encounter_source: str,
    encounter_ref_digest: str,
    priority_class: str,
    salience: float,
    subject_kind: SubjectKind | str,
    autonomy_lane_hints: str = "[]",
    third_party_consent_allows_external_research: bool = False,
    produced_via_subjective_duration_depth: int = 0,
) -> None:
    now = time.time()
    with store._lock, store._conn() as c:
        parent = c.execute(
            "SELECT bond_id FROM wonderings WHERE id = ?",
            (int(wondering_id),),
        ).fetchone()
        if parent is None:
            raise KeyError(f"wondering not found: {wondering_id}")
        parent_bond_id = parent["bond_id"]
        if parent_bond_id != bond_id:
            raise SidecarBondMismatchRefused(
                "wondering_drive_metadata.bond_id must match wonderings.bond_id"
            )
        existing = c.execute(
            "SELECT 1 FROM wondering_drive_metadata WHERE wondering_id = ?",
            (int(wondering_id),),
        ).fetchone()
        if existing is not None:
            raise SidecarDuplicateWriteRefused(
                "wondering_drive_metadata is append-only per wondering_id"
            )
        c.execute(
            """
            INSERT INTO wondering_drive_metadata (
                wondering_id, bond_id, encounter_source, encounter_ref_digest,
                priority_class, salience, autonomy_lane_hints, subject_kind,
                third_party_consent_allows_external_research,
                produced_via_subjective_duration_depth, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(wondering_id),
                str(bond_id),
                str(encounter_source),
                str(encounter_ref_digest),
                str(priority_class),
                float(salience),
                str(autonomy_lane_hints),
                _subject_kind(subject_kind).value,
                1 if third_party_consent_allows_external_research else 0,
                int(produced_via_subjective_duration_depth),
                now,
            ),
        )


def _project_row(row: sqlite3.Row | dict) -> CuriosityObject:
    data = dict(row)
    if data.get("bond_id") == "_LEGACY":
        raise LegacyWonderingProjectionRefused(
            "wonderings.bond_id='_LEGACY' cannot be projected into curiosity"
        )
    return CuriosityObject(
        wondering_id=int(data["id"]),
        bond_id=str(data["bond_id"]),
        question=str(data["question"]),
        encounter_source=str(data["encounter_source"]),
        priority_class=str(data["priority_class"]),
        salience=float(data["salience"]),
        subject_kind=_subject_kind(data.get("subject_kind")),
        resolution_marker_type=data.get("resolution_marker_type"),
        resolution_marker_utc=data.get("resolution_marker_utc"),
    )


def project_curiosity_object(store: Wonderings, wondering_id: int) -> CuriosityObject:
    with store._lock, store._conn() as c:
        row = c.execute(
            """
            SELECT w.*, m.encounter_source, m.priority_class, m.salience,
                   m.subject_kind, m.resolution_marker_type, m.resolution_marker_utc
            FROM wonderings AS w
            LEFT JOIN wondering_drive_metadata AS m
              ON m.wondering_id = w.id
            WHERE w.id = ?
            """,
            (int(wondering_id),),
        ).fetchone()
    if row is None:
        raise KeyError(f"wondering not found: {wondering_id}")
    if row["bond_id"] == "_LEGACY":
        raise LegacyWonderingProjectionRefused(
            "wonderings.bond_id='_LEGACY' cannot be projected into curiosity"
        )
    if row["encounter_source"] is None:
        raise ValueError(f"wondering has no drive metadata: {wondering_id}")
    return _project_row(row)


def list_drive_curiosity_objects(store: Wonderings, *, bond_id: str) -> list[CuriosityObject]:
    out: list[CuriosityObject] = []
    with store._lock, store._conn() as c:
        rows = c.execute(
            """
            SELECT w.*, m.encounter_source, m.priority_class, m.salience,
                   m.subject_kind, m.resolution_marker_type, m.resolution_marker_utc
            FROM wonderings AS w
            JOIN wondering_drive_metadata AS m
              ON m.wondering_id = w.id
            WHERE m.bond_id = ?
            ORDER BY w.id ASC
            """,
            (str(bond_id),),
        ).fetchall()
    for row in rows:
        try:
            out.append(_project_row(row))
        except LegacyWonderingProjectionRefused:
            continue
    return out


def resolve_curiosity_object(
    store: Wonderings,
    *,
    wondering_id: int,
    conclusion: str,
    resolution_marker_type: str,
    resolution_marker_utc: float,
) -> None:
    resolved_at = time.time()
    store.resolve(int(wondering_id), conclusion, resolved_at=resolved_at)
    with store._lock, store._conn() as c:
        c.execute(
            """
            UPDATE wondering_drive_metadata
               SET resolution_marker_type = ?,
                   resolution_marker_utc = ?
             WHERE wondering_id = ?
            """,
            (
                str(resolution_marker_type),
                float(resolution_marker_utc),
                int(wondering_id),
            ),
        )
