# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Drive-driven curiosity adapter over the existing wonderings store."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
import hashlib
from typing import Callable, Mapping

from core.evolution.temperament import Temperament
from core.evolution.wonderings import Wonderings
from core.memory import identity
from core.policies.exceptions import CrossBondAccessError, SubjectKindRefused
from core.policies.diagnostics import DriveCuriosityDiagnosticSink
from core.policies.third_party_subject_gate import SubjectKind


class LegacyWonderingProjectionRefused(ValueError):
    """Raised when a pre-bond `_LEGACY` wondering is projected as curiosity."""


class ProducerRegistrationRefused(ValueError):
    """Raised when an encounter producer violates registration invariants."""


class SidecarBondMismatchRefused(ValueError):
    """Raised when sidecar metadata disagrees with its parent wondering bond."""


class SidecarDuplicateWriteRefused(ValueError):
    """Raised when code tries to rewrite append-only sidecar metadata."""


class CuriosityAuthorityRefused(ValueError):
    """Raised when the curiosity producer exceeds its reviewed authority."""


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
DRIVE_RESOLUTION_TEMPERAMENT_SOURCE = "drive_driven_curiosity_resolution"
BASE_RESOLUTION_DELTA = 0.5
NEUTRAL_TEMPERAMENT_VALUE_FOR_FIRST_OBSERVATION = 5.0
TEMPERAMENT_VALUE_MIN = 0.0
TEMPERAMENT_VALUE_MAX = 10.0
BASE_SATURATION_CAPACITY = 10.0


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
    created_at: float | None = None
    advance_count: int = 0
    extraction_shape_blocked: bool = False
    third_party_blocked: bool = False
    can_resolve_interiorly: bool = False
    fixation_released: bool = False
    produced_via_subjective_duration_depth: int = 0


class MeaningfulExchangeEligibility(Enum):
    ELIGIBLE_OWNER_BOND = "eligible_owner_bond"
    ELIGIBLE_SELF_MODEL = "eligible_self_model"
    ELIGIBLE_LONG_CARRIED_RESOLUTION = "eligible_long_carried_resolution"
    NOT_ELIGIBLE_ROUTINE_FACT = "not_eligible_routine_fact"
    NOT_ELIGIBLE_LOW_CONFIDENCE = "not_eligible_low_confidence"
    NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY = "not_eligible_can_resolve_interiorly"
    NOT_ELIGIBLE_OWNER_BOND_ROUTINE = "not_eligible_owner_bond_routine"


class PressBand(Enum):
    LIGHT = "light"
    PRESS = "press"
    HEAVY = "heavy"
    OVERLOADED = "overloaded"


@dataclass(frozen=True)
class OwnerBondSaturationGuard:
    rolling_window_hours: int = 24
    owner_bond_meaningful_daily_cap: int = 3


@dataclass(frozen=True)
class CuriosityResolutionCeremonyResult:
    eligibility: MeaningfulExchangeEligibility
    temperament_event_id: int | None
    salience_event_id: int | None
    producer_event_id: str
    delta_intent: float
    delta_applied: float


@dataclass(frozen=True)
class SaturationRegister:
    bond_id: str
    open_object_count: int
    total_salience: float
    weighted_salience: float
    carrying_capacity: float
    press: float
    sampled_utc: datetime


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


@dataclass(frozen=True)
class _ParentCuriosityProvenance:
    wondering_id: int
    bond_id: str
    priority_class: str
    subject_kind: SubjectKind
    produced_via_subjective_duration_depth: int


_REGISTERED_PRODUCERS: dict[EncounterSource, ProducerEntry | ProducerSourceDeferred] = {}


def _digest(value: object) -> str | None:
    if value is None:
        return None
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _hmac_shaped_digest(value: object) -> str:
    return "hmac-sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _producer_ref_value(producer_ref: object) -> str:
    return str(getattr(producer_ref, "value", producer_ref))


def _coerce_datetime(value: datetime | float | int | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.fromtimestamp(float(value), tz=UTC)


def _priority_class_weight(priority_class: str) -> float:
    return {
        "owner_bond": 1.0,
        "self_growth": 0.9,
        "world_knowledge": 0.4,
        "aesthetic_play": 0.4,
    }.get(str(priority_class), 0.5)


def _marker_confidence_weight(marker_type: str) -> float:
    return {
        "explicit_owner_resolved": 1.0,
        "explicit_self_resolved": 0.9,
    }.get(str(marker_type), 0.5)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _emit_subject_kind_refused(fields: Mapping, refusal_kind: str) -> None:
    diagnostic_sink = fields.get("diagnostic_sink")
    if not callable(diagnostic_sink):
        return
    if getattr(diagnostic_sink, "accepts_raw_diagnostic_fields", False):
        diagnostic_sink(
            {
                "event_type": "SUBJECT_KIND_REFUSED",
                "refusal_kind": refusal_kind,
                "bond_id": fields.get("bond_id"),
                "subject_kind": fields.get("subject_kind"),
                "subject_ref": fields.get("subject_ref"),
            }
        )
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


def _emit_cross_bond_access_refused(
    *,
    attempted_bond_id: str,
    authorized_bond_id: str,
    surface: str,
    diagnostic_sink: Callable[[dict], None] | None,
) -> None:
    if diagnostic_sink is None:
        diagnostic_sink = DriveCuriosityDiagnosticSink()
    if getattr(diagnostic_sink, "accepts_raw_diagnostic_fields", False):
        diagnostic_sink(
            {
                "event_type": "CROSS_BOND_ACCESS_REFUSED",
                "bond_id": authorized_bond_id,
                "requested_bond_id": attempted_bond_id,
                "surface": surface,
            }
        )
        return
    diagnostic_sink(
        {
            "event_type": "CROSS_BOND_ACCESS_REFUSED",
            "requested_bond_digest": _digest(attempted_bond_id),
            "bond_digest": _digest(authorized_bond_id),
            "surface": surface,
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
        created_at=None if fields.get("created_at") is None else float(fields["created_at"]),
        advance_count=int(fields.get("advance_count") or 0),
        extraction_shape_blocked=bool(fields.get("extraction_shape_blocked")),
        third_party_blocked=bool(fields.get("third_party_blocked")),
        can_resolve_interiorly=bool(fields.get("can_resolve_interiorly")),
        fixation_released=bool(fields.get("fixation_released")),
        produced_via_subjective_duration_depth=int(
            fields.get("produced_via_subjective_duration_depth") or 0
        ),
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


def _wonderings_backed_fields(
    store: Wonderings,
    *,
    source: EncounterSource,
    seed: Mapping,
) -> dict:
    wondering_id = seed.get("wondering_id")
    if wondering_id is None:
        raise ValueError("wondering_id is required for wonderings-backed producer")
    with store._lock, store._conn() as c:
        parent = c.execute(
            "SELECT source FROM wonderings WHERE id = ?",
            (int(wondering_id),),
        ).fetchone()
    if parent is None:
        raise KeyError(f"wondering not found: {wondering_id}")
    if (
        source is EncounterSource.EXPLICIT_OWNER_FLAG
        and parent["source"] != EncounterSource.EXPLICIT_OWNER_FLAG.value
    ):
        raise ValueError(
            f"wondering #{wondering_id} source={parent['source']!r} "
            "cannot enter explicit_owner_flag producer"
        )
    obj = project_curiosity_object(store, int(wondering_id))
    if obj.encounter_source != source.value:
        raise ValueError(
            f"wondering #{wondering_id} encounter_source={obj.encounter_source!r} "
            f"does not match registered producer {source.value!r}"
        )
    fields = obj.__dict__.copy()
    if "diagnostic_sink" in seed:
        fields["diagnostic_sink"] = seed["diagnostic_sink"]
    return fields


def register_wonderings_backed_producers(store: Wonderings) -> None:
    for source in (
        EncounterSource.WONDERING_GENERATED,
        EncounterSource.EXPLICIT_OWNER_FLAG,
    ):
        register_encounter_producer(
            source=source,
            evidence_pointer_kind="wonderings.id",
            producer_ref=DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF,
            create_curiosity_object=lambda seed, source=source: _wonderings_backed_fields(
                store,
                source=source,
                seed=seed,
            ),
        )


def register_subjective_duration_meaningful_event_producer(
    store: Wonderings,
    subjective_duration: object,
    *,
    max_recursion_depth: int = 2,
    recursion_dedupe_window_hours: int = 4,
) -> None:
    seen_event_ids: dict[int, datetime] = {}

    def create(seed: Mapping) -> dict:
        fields = _subjective_duration_meaningful_event_fields(
            store,
            subjective_duration,
            seed=seed,
            seen_event_ids=seen_event_ids,
            max_recursion_depth=max_recursion_depth,
            recursion_dedupe_window_hours=recursion_dedupe_window_hours,
        )
        return fields

    register_encounter_producer(
        source=EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT,
        evidence_pointer_kind="subjective_duration_salience_events.event_id",
        producer_ref=DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF,
        create_curiosity_object=create,
    )


def _subjective_duration_meaningful_event_fields(
    store: Wonderings,
    subjective_duration: object,
    *,
    seed: Mapping,
    seen_event_ids: dict[int, datetime],
    max_recursion_depth: int,
    recursion_dedupe_window_hours: int,
) -> dict:
    event_id_raw = seed.get("event_id")
    if event_id_raw is None:
        raise ValueError("event_id is required for subjective_duration producer")
    event_id = int(event_id_raw)
    event = _subjective_duration_event_by_id(subjective_duration, event_id)
    if event is None:
        raise KeyError(f"subjective_duration salience event not found: {event_id}")
    if str(event["salience_event_kind"]) != "meaningful_exchange":
        raise ValueError("subjective_duration producer only accepts meaningful_exchange")
    bond_id = str(event["bond_id"])
    if not bond_id or bond_id == "_LEGACY":
        raise ValueError("subjective_duration event must carry a real bond_id")
    requested_bond_id = seed.get("bond_id")
    if requested_bond_id is not None and str(requested_bond_id) != bond_id:
        raise ValueError("bond_id mismatch for subjective_duration event")
    if bool(event["is_canary"]):
        raise ValueError("canary salience events cannot produce curiosity objects")
    if float(event["meaningfulness_score"]) <= 0.0:
        raise ValueError("meaningfulness_score must be positive")
    producer_ref = str(event["producer_ref"])
    if producer_ref == MANUAL_TEST_PRODUCER_REF:
        raise ValueError("manual-test salience events cannot produce curiosity objects")
    if not producer_ref:
        raise ValueError("producer_ref is required for subjective_duration producer")

    now = seed.get("now_utc")
    now_utc = _coerce_datetime(now)
    _prune_seen_event_ids(
        seen_event_ids,
        now_utc=now_utc,
        recursion_dedupe_window_hours=recursion_dedupe_window_hours,
    )
    if event_id in seen_event_ids:
        raise ValueError("subjective_duration recursion dedupe refused duplicate event_id")

    parent = _parent_subjective_duration_provenance(
        store,
        bond_id=bond_id,
        producer_event_id=str(event["producer_event_id"]),
    )
    if parent.produced_via_subjective_duration_depth < 0:
        raise ValueError("recursion depth cannot be negative")
    if parent.produced_via_subjective_duration_depth >= int(max_recursion_depth):
        raise ValueError("subjective_duration recursion depth limit reached")
    next_depth = parent.produced_via_subjective_duration_depth + 1
    subject_kind = parent.subject_kind
    if subject_kind is SubjectKind.NAMED_THIRD_PARTY and not _third_party_consent_allows_external_research(
        bond_id=bond_id,
        subject_ref=seed.get("subject_ref"),
    ):
        _emit_subject_kind_refused(seed, "named_third_party_without_owner_explicit_consent")
        raise SubjectKindRefused("NAMED_THIRD_PARTY requires OWNER_EXPLICIT consent")

    wondering_id = store.add(
        _subjective_duration_question(event),
        source=EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT.value,
        bond_id=bond_id,
    )
    record_wondering_drive_metadata(
        store,
        wondering_id=wondering_id,
        bond_id=bond_id,
        encounter_source=EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT.value,
        encounter_ref_digest=_hmac_shaped_digest(f"subjective_duration:{event_id}"),
        priority_class=str(seed.get("priority_class", parent.priority_class)),
        salience=float(event["meaningfulness_score"]),
        subject_kind=subject_kind,
        produced_via_subjective_duration_depth=next_depth,
    )
    seen_event_ids[event_id] = now_utc
    obj = project_curiosity_object(store, wondering_id)
    fields = obj.__dict__.copy()
    if "diagnostic_sink" in seed:
        fields["diagnostic_sink"] = seed["diagnostic_sink"]
    return fields


def _subjective_duration_event_by_id(
    subjective_duration: object,
    event_id: int,
) -> sqlite3.Row | None:
    db_path = getattr(subjective_duration, "db_path", None)
    if db_path is None:
        raise ValueError("subjective_duration store must expose db_path")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            """
            SELECT event_id, ts_utc, salience_event_kind, producer_ref, bond_id,
                   producer_event_id, meaningfulness_score, is_canary
            FROM subjective_duration_salience_events
            WHERE event_id = ?
            """,
            (int(event_id),),
        ).fetchone()


def _parent_subjective_duration_provenance(
    store: Wonderings,
    *,
    bond_id: str,
    producer_event_id: str,
) -> _ParentCuriosityProvenance:
    parent_id = _parent_wondering_id_from_producer_event_id(producer_event_id)
    if parent_id is None:
        raise ValueError("parent wondering id required for subjective_duration producer")
    with store._lock, store._conn() as c:
        row = c.execute(
            """
            SELECT w.id, w.bond_id, m.priority_class, m.subject_kind,
                   m.produced_via_subjective_duration_depth
            FROM wonderings AS w
            LEFT JOIN wondering_drive_metadata AS m
              ON m.wondering_id = w.id
            WHERE w.id = ?
            """,
            (int(parent_id),),
        ).fetchone()
    if row is None:
        raise ValueError("parent wondering not found for subjective_duration producer")
    if str(row["bond_id"]) != str(bond_id):
        raise ValueError("parent bond_id mismatch for subjective_duration producer")
    if row["produced_via_subjective_duration_depth"] is None:
        raise ValueError("parent wondering missing drive metadata")
    return _ParentCuriosityProvenance(
        wondering_id=int(row["id"]),
        bond_id=str(row["bond_id"]),
        priority_class=str(row["priority_class"]),
        subject_kind=_subject_kind(row["subject_kind"]),
        produced_via_subjective_duration_depth=int(
            row["produced_via_subjective_duration_depth"]
        ),
    )


def _parent_wondering_id_from_producer_event_id(producer_event_id: str) -> int | None:
    parts = str(producer_event_id).split(":")
    if len(parts) < 2 or parts[0] != "wondering":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _prune_seen_event_ids(
    seen_event_ids: dict[int, datetime],
    *,
    now_utc: datetime,
    recursion_dedupe_window_hours: int,
) -> None:
    cutoff = now_utc - timedelta(hours=max(1, int(recursion_dedupe_window_hours)))
    expired = [
        event_id
        for event_id, seen_utc in seen_event_ids.items()
        if seen_utc < cutoff
    ]
    for event_id in expired:
        seen_event_ids.pop(event_id, None)


def _subjective_duration_question(event: Mapping) -> str:
    return (
        "What should Maez understand from meaningful salience event "
        f"#{int(event['event_id'])}?"
    )


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
        created_at=None if data.get("created_at") is None else float(data["created_at"]),
        advance_count=int(data.get("pursuit_count") or data.get("advance_count") or 0),
        produced_via_subjective_duration_depth=int(
            data.get("produced_via_subjective_duration_depth") or 0
        ),
    )


def project_curiosity_object(store: Wonderings, wondering_id: int) -> CuriosityObject:
    with store._lock, store._conn() as c:
        row = c.execute(
            """
            SELECT w.*, m.encounter_source, m.priority_class, m.salience,
                   m.subject_kind, m.resolution_marker_type, m.resolution_marker_utc,
                   m.produced_via_subjective_duration_depth
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
                   m.subject_kind, m.resolution_marker_type, m.resolution_marker_utc,
                   m.produced_via_subjective_duration_depth
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


def list_open_drive_curiosity_objects(
    store: Wonderings,
    *,
    bond_id: str,
) -> list[CuriosityObject]:
    out: list[CuriosityObject] = []
    with store._lock, store._conn() as c:
        rows = c.execute(
            """
            SELECT w.*, m.encounter_source, m.priority_class, m.salience,
                   m.subject_kind, m.resolution_marker_type, m.resolution_marker_utc,
                   m.produced_via_subjective_duration_depth
            FROM wonderings AS w
            JOIN wondering_drive_metadata AS m
              ON m.wondering_id = w.id
            WHERE m.bond_id = ?
              AND w.bond_id = ?
              AND w.status IN ('open', 'active')
            ORDER BY w.id ASC
            """,
            (str(bond_id), str(bond_id)),
        ).fetchall()
    for row in rows:
        try:
            out.append(_project_row(row))
        except LegacyWonderingProjectionRefused:
            continue
    return out


def snapshot_temperament_for_bond(
    bond_id: str,
    *,
    temperament: object | None = None,
    diagnostic_sink: Callable[[dict], None] | None = None,
) -> Mapping[str, float | None]:
    authorized_bond_id = identity.user_profile_id()
    if str(bond_id) != str(authorized_bond_id):
        _emit_cross_bond_access_refused(
            attempted_bond_id=str(bond_id),
            authorized_bond_id=str(authorized_bond_id),
            surface="snapshot_temperament_for_bond",
            diagnostic_sink=diagnostic_sink,
        )
        raise CrossBondAccessError(
            "v1 single-bond temperament wrapper refused cross-bond access; "
            "see CROSS_BOND_ACCESS_REFUSED diagnostic row for details"
        )
    temperament_store = temperament if temperament is not None else Temperament()
    return dict(temperament_store.current())


def compute_carrying_capacity(temperament_snapshot: Mapping[str, float | None]) -> float:
    awareness = temperament_snapshot.get("awareness")
    persistence = temperament_snapshot.get("persistence")
    if awareness is None:
        awareness = 5.0
    if persistence is None:
        persistence = 5.0
    return BASE_SATURATION_CAPACITY * (float(awareness) / 5.0) * (
        float(persistence) / 5.0
    )


def classify_press(press: float) -> PressBand:
    value = float(press)
    if value < 0.3:
        return PressBand.LIGHT
    if value < 0.7:
        return PressBand.PRESS
    if value < 1.2:
        return PressBand.HEAVY
    return PressBand.OVERLOADED


def compute_saturation(
    bond_id: str,
    *,
    store: Wonderings | None = None,
    temperament_snapshot: Mapping[str, float | None] | None = None,
    temperament: object | None = None,
    now_utc: datetime | float | int | None = None,
    diagnostic_sink: Callable[[dict], None] | None = None,
) -> SaturationRegister:
    if not bond_id:
        raise ValueError("bond_id is required for saturation computation")
    curiosity_store = store if store is not None else Wonderings()
    open_objects = list_open_drive_curiosity_objects(curiosity_store, bond_id=str(bond_id))
    total_salience = sum(float(obj.salience) for obj in open_objects)
    weighted_salience = sum(
        float(obj.salience) * _priority_class_weight(obj.priority_class)
        for obj in open_objects
    )
    snapshot = (
        temperament_snapshot
        if temperament_snapshot is not None
        else snapshot_temperament_for_bond(
            str(bond_id),
            temperament=temperament,
            diagnostic_sink=diagnostic_sink,
        )
    )
    carrying_capacity = compute_carrying_capacity(snapshot)
    press = (
        weighted_salience / carrying_capacity
        if carrying_capacity > 0
        else float("inf")
    )
    return SaturationRegister(
        bond_id=str(bond_id),
        open_object_count=len(open_objects),
        total_salience=total_salience,
        weighted_salience=weighted_salience,
        carrying_capacity=carrying_capacity,
        press=press,
        sampled_utc=_coerce_datetime(now_utc),
    )


def _parse_event_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _count_owner_bond_meaningful_events(
    *,
    subjective_duration: object,
    bond_id: str,
    guard: OwnerBondSaturationGuard,
    now_utc: datetime,
) -> int:
    db_path = getattr(subjective_duration, "db_path", None)
    if db_path is None:
        return 0
    cutoff = now_utc - timedelta(hours=max(1, int(guard.rolling_window_hours)))
    with closing(sqlite3.connect(db_path)) as conn, conn:
        rows = conn.execute(
            """
            SELECT ts_utc, producer_event_id FROM subjective_duration_salience_events
             WHERE bond_id = ?
               AND salience_event_kind = 'meaningful_exchange'
               AND producer_ref = ?
               AND is_canary = 0
            """,
            (str(bond_id), DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF),
        ).fetchall()
    count = 0
    for ts_raw, producer_event_id in rows:
        if ":priority:owner_bond:" not in str(producer_event_id):
            continue
        ts = _parse_event_time(str(ts_raw))
        if ts is not None and cutoff <= ts <= now_utc:
            count += 1
    return count


def classify_meaningful_exchange(
    *,
    curiosity_object: CuriosityObject,
    subjective_duration: object,
    guard: OwnerBondSaturationGuard | None = None,
    now_utc: datetime | float | int | None = None,
    diagnostic_sink: Callable[[dict], None] | None = None,
) -> MeaningfulExchangeEligibility:
    guard = guard or OwnerBondSaturationGuard()
    now = _coerce_datetime(now_utc)
    priority = str(curiosity_object.priority_class)
    subject_kind = _subject_kind(curiosity_object.subject_kind)
    age_hours = (
        None
        if curiosity_object.created_at is None
        else max(0.0, (now.timestamp() - float(curiosity_object.created_at)) / 3600.0)
    )

    if priority == "owner_bond":
        if curiosity_object.extraction_shape_blocked or curiosity_object.third_party_blocked:
            return MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE
        count = _count_owner_bond_meaningful_events(
            subjective_duration=subjective_duration,
            bond_id=curiosity_object.bond_id,
            guard=guard,
            now_utc=now,
        )
        cap = max(1, int(guard.owner_bond_meaningful_daily_cap))
        if count >= cap:
            if diagnostic_sink is not None:
                diagnostic_sink(
                    {
                        "event_type": "SATURATION_SAMPLE",
                        "reason": "owner_bond_saturation",
                        "bond_id": curiosity_object.bond_id,
                        "eligibility": (
                            MeaningfulExchangeEligibility
                            .NOT_ELIGIBLE_OWNER_BOND_ROUTINE
                            .value
                        ),
                    }
                )
            return MeaningfulExchangeEligibility.NOT_ELIGIBLE_OWNER_BOND_ROUTINE
        return MeaningfulExchangeEligibility.ELIGIBLE_OWNER_BOND
    if curiosity_object.can_resolve_interiorly:
        return MeaningfulExchangeEligibility.NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY
    if priority == "self_growth" and subject_kind is SubjectKind.SELF_MODEL:
        return MeaningfulExchangeEligibility.ELIGIBLE_SELF_MODEL
    if (
        age_hours is not None
        and age_hours >= 7 * 24
        and float(curiosity_object.salience) > 0.4
        and not curiosity_object.fixation_released
    ):
        return MeaningfulExchangeEligibility.ELIGIBLE_LONG_CARRIED_RESOLUTION
    if priority in {"world_knowledge", "aesthetic_play"}:
        if (age_hours is None or age_hours < 24) and curiosity_object.advance_count <= 1:
            return MeaningfulExchangeEligibility.NOT_ELIGIBLE_ROUTINE_FACT
        return MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE
    return MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE


def _consumed_daily_delta(
    *,
    temperament: object,
    bond_id: str,
    parameter: str,
    date_utc: str,
) -> float:
    consumed = 0.0
    for event in temperament.history(parameter, limit=500):
        if event.get("source") != DRIVE_RESOLUTION_TEMPERAMENT_SOURCE:
            continue
        evidence_raw = event.get("evidence")
        if isinstance(evidence_raw, Mapping):
            evidence = evidence_raw
        else:
            try:
                evidence = json.loads(str(event.get("evidence_json") or "{}"))
            except json.JSONDecodeError:
                continue
        if evidence.get("bond_id") != bond_id:
            continue
        if evidence.get("budget_date_utc") != date_utc:
            continue
        consumed += abs(float(evidence.get("delta_applied") or 0.0))
    return consumed


def _emit_temperament_write_clamped(
    *,
    diagnostic_sink: Callable[[dict], None] | None,
    bond_id: str,
    parameter: str,
    proposed_delta: float,
    delta_applied: float,
    first_observation_suppressed: bool,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "TEMPERAMENT_WRITE_CLAMPED",
            "bond_id": bond_id,
            "parameter": parameter,
            "proposed_delta": proposed_delta,
            "delta_applied": delta_applied,
            "first_observation_suppressed": first_observation_suppressed,
        }
    )


def _producer_event_id(
    *,
    curiosity_object: CuriosityObject,
    resolution_marker_type: str,
    resolution_marker_utc: datetime,
) -> str:
    return (
        f"wondering:{curiosity_object.wondering_id}:"
        f"priority:{curiosity_object.priority_class}:"
        f"resolution:{resolution_marker_type}:{int(resolution_marker_utc.timestamp())}"
    )


def write_curiosity_resolution_seam_call(
    *,
    curiosity_object: CuriosityObject,
    temperament: object,
    subjective_duration: object,
    resolution_marker_type: str,
    resolution_marker_utc: datetime | float | int | None,
    guard: OwnerBondSaturationGuard | None = None,
    daily_delta_budget: float = 2.0,
    salience_event_kind: str = "meaningful_exchange",
    temperament_parameter: str = "curiosity",
    diagnostic_sink: Callable[[dict], None] | None = None,
    is_canary: bool = False,
) -> CuriosityResolutionCeremonyResult:
    if salience_event_kind != "meaningful_exchange":
        raise CuriosityAuthorityRefused(
            "drive-driven curiosity may only write meaningful_exchange salience events"
        )
    if temperament_parameter != "curiosity":
        raise CuriosityAuthorityRefused(
            "drive-driven curiosity may only write the curiosity temperament parameter"
        )

    marker_utc = _coerce_datetime(resolution_marker_utc)
    producer_event_id = _producer_event_id(
        curiosity_object=curiosity_object,
        resolution_marker_type=resolution_marker_type,
        resolution_marker_utc=marker_utc,
    )
    eligibility = classify_meaningful_exchange(
        curiosity_object=curiosity_object,
        subjective_duration=subjective_duration,
        guard=guard,
        now_utc=marker_utc,
        diagnostic_sink=diagnostic_sink,
    )
    if not eligibility.value.startswith("eligible_"):
        return CuriosityResolutionCeremonyResult(
            eligibility=eligibility,
            temperament_event_id=None,
            salience_event_id=None,
            producer_event_id=producer_event_id,
            delta_intent=0.0,
            delta_applied=0.0,
        )

    before_snapshot = temperament.current()
    current_value = temperament.current_value("curiosity")
    prior = (
        NEUTRAL_TEMPERAMENT_VALUE_FOR_FIRST_OBSERVATION
        if current_value is None
        else float(current_value)
    )
    delta_intent = (
        BASE_RESOLUTION_DELTA
        * _priority_class_weight(curiosity_object.priority_class)
        * float(curiosity_object.salience)
        * _marker_confidence_weight(resolution_marker_type)
    )
    budget_date = marker_utc.date().isoformat()
    consumed = _consumed_daily_delta(
        temperament=temperament,
        bond_id=curiosity_object.bond_id,
        parameter="curiosity",
        date_utc=budget_date,
    )
    remaining = max(0.0, float(daily_delta_budget) - consumed)
    delta_applied = min(delta_intent, remaining)
    if delta_applied < delta_intent:
        _emit_temperament_write_clamped(
            diagnostic_sink=diagnostic_sink,
            bond_id=curiosity_object.bond_id,
            parameter="curiosity",
            proposed_delta=delta_intent,
            delta_applied=delta_applied,
            first_observation_suppressed=current_value is None and delta_applied == 0.0,
        )
    if current_value is None and delta_applied == 0.0:
        return CuriosityResolutionCeremonyResult(
            eligibility=eligibility,
            temperament_event_id=None,
            salience_event_id=None,
            producer_event_id=producer_event_id,
            delta_intent=delta_intent,
            delta_applied=delta_applied,
        )

    new_value = _clamp(
        prior + delta_applied,
        TEMPERAMENT_VALUE_MIN,
        TEMPERAMENT_VALUE_MAX,
    )
    if is_canary:
        temperament_event_id = None
        before_snapshot = {**before_snapshot, "curiosity": prior}
        after_snapshot = {**before_snapshot, "curiosity": new_value}
    else:
        temperament_event_id = temperament.record_event(
            parameter="curiosity",
            value=new_value,
            source="drive_driven_curiosity_resolution",
            reason=f"resolution:{resolution_marker_type}",
            evidence={
                "object_id_digest": _digest(curiosity_object.wondering_id),
                "bond_id": curiosity_object.bond_id,
                "priority_class": curiosity_object.priority_class,
                "marker_type": resolution_marker_type,
                "delta_intent": delta_intent,
                "delta_applied": delta_applied,
                "budget_date_utc": budget_date,
            },
        )
        after_snapshot = temperament.current()
    salience_event_id = subjective_duration.record_salience_event(
        salience_event_kind="meaningful_exchange",
        producer_ref=DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF,
        bond_id=curiosity_object.bond_id,
        producer_event_id=producer_event_id,
        producer_temperament_before=before_snapshot,
        producer_temperament_after=after_snapshot,
        now_utc=marker_utc,
        is_canary=is_canary,
    )
    return CuriosityResolutionCeremonyResult(
        eligibility=eligibility,
        temperament_event_id=temperament_event_id,
        salience_event_id=salience_event_id,
        producer_event_id=producer_event_id,
        delta_intent=delta_intent,
        delta_applied=delta_applied,
    )


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
