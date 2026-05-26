from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from core import paths


class PreferenceClass(Enum):
    QUIET_PERIOD = "quiet_period"
    ENCOURAGED_TOPIC = "encouraged_topic"
    DISCOURAGED_TOPIC = "discouraged_topic"
    LANE_CEILING = "lane_ceiling"
    LANE_FLOOR = "lane_floor"
    PROVIDER_RESTRICTION = "provider_restriction"
    MAINTENANCE_RATIFICATION = "maintenance_ratification"


class PreferenceExpressedBy(Enum):
    OWNER_EXPLICIT = "owner_explicit"
    OWNER_EXPLICIT_REVISION = "owner_explicit_revision"
    OWNER_OBSERVED = "owner_observed"
    SYSTEM_DEFAULT = "system_default"


class SuppressionKind(Enum):
    SIGNAL_GATED = "SIGNAL_GATED"
    REFLECTION_DEFERRED = "REFLECTION_DEFERRED"
    EXTRACTION_BLOCKED = "EXTRACTION_BLOCKED"


@dataclass(frozen=True)
class AutonomyPreference:
    preference_id: str
    bond_id: str
    recorded_utc: datetime
    preference_class: PreferenceClass
    pattern_digest: str
    weight: float
    expressed_by: PreferenceExpressedBy
    relevance_decay_half_life_days: float
    notes_digest: str | None
    target_field: str
    encoded_modifier: float


@dataclass(frozen=True)
class DeliveredOutreachSample:
    bond_id: str
    delivered_utc: datetime
    owner_response: str


@dataclass(frozen=True)
class SuppressionEvent:
    bond_id: str
    occurred_utc: datetime
    suppression_kind: SuppressionKind


DiagnosticSink = Callable[[dict], None]
OWNER_OBSERVED_MIN_DELIVERED_SAMPLE_SIZE = 5
SUPPRESSION_WINDOW_MINUTES = 30
_SUPPORTED_OWNER_RESPONSE_VALUES = frozenset(
    {
        "acknowledged",
        "corrected",
        "invited_more",
        "deferred",
        "declined_without_teaching",
        "no_response",
    }
)

_POLICY_FIELDS = frozenset(
    {
        "external_knowledge_daily_call_cap",
        "external_knowledge_cost_cap_cents",
        "owner_interrupting_daily_max_count",
        "owner_interrupting_cooldown_minutes",
        "owner_interrupting_minimum_importance",
        "capability_acquisition_proposal_rate_per_day",
    }
)
_NON_POLICY_FIELDS = frozenset({"maintenance_proposal_ratified"})

_FIELDS_BY_CLASS = {
    PreferenceClass.QUIET_PERIOD: frozenset(
        {
            "owner_interrupting_quiet_hours",
            "owner_interrupting_daily_max_count",
            "owner_interrupting_cooldown_minutes",
            "owner_interrupting_minimum_importance",
        }
    ),
    PreferenceClass.ENCOURAGED_TOPIC: frozenset(
        {
            "owner_interrupting_minimum_importance",
            "capability_acquisition_proposal_rate_per_day",
        }
    ),
    PreferenceClass.DISCOURAGED_TOPIC: frozenset(
        {
            "owner_interrupting_minimum_importance",
            "capability_acquisition_proposal_rate_per_day",
        }
    ),
    PreferenceClass.LANE_CEILING: _POLICY_FIELDS,
    PreferenceClass.LANE_FLOOR: _POLICY_FIELDS,
    PreferenceClass.PROVIDER_RESTRICTION: frozenset(
        {
            "external_knowledge_daily_call_cap",
            "external_knowledge_cost_cap_cents",
        }
    ),
    PreferenceClass.MAINTENANCE_RATIFICATION: _NON_POLICY_FIELDS,
}


class AutonomyPreferences:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.autonomy_preferences_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_schema(self) -> None:
        with self._lock, self._conn() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS autonomy_preferences (
                    preference_id TEXT PRIMARY KEY,
                    bond_id TEXT NOT NULL,
                    recorded_utc TEXT NOT NULL,
                    preference_class TEXT NOT NULL,
                    pattern_digest TEXT NOT NULL,
                    weight REAL NOT NULL,
                    expressed_by TEXT NOT NULL,
                    relevance_decay_half_life_days REAL NOT NULL,
                    notes_digest TEXT,
                    target_field TEXT NOT NULL,
                    encoded_modifier REAL NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_autonomy_preferences_bond_class
                ON autonomy_preferences (bond_id, preference_class, recorded_utc)
                """
            )

            existing_cols = {
                row[1]
                for row in con.execute(
                    "PRAGMA table_info(autonomy_preferences)"
                ).fetchall()
            }
            for column_name, column_sql in (
                ("target_field", "target_field TEXT NOT NULL DEFAULT ''"),
                ("encoded_modifier", "encoded_modifier REAL NOT NULL DEFAULT 0.0"),
            ):
                if column_name in existing_cols:
                    continue
                try:
                    con.execute(
                        f"ALTER TABLE autonomy_preferences ADD COLUMN {column_sql}"
                    )
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise

    def append(self, preference: AutonomyPreference) -> None:
        _validate_preference(preference)
        with self._lock, self._conn() as con:
            con.execute(
                """
                INSERT INTO autonomy_preferences (
                    preference_id,
                    bond_id,
                    recorded_utc,
                    preference_class,
                    pattern_digest,
                    weight,
                    expressed_by,
                    relevance_decay_half_life_days,
                    notes_digest,
                    target_field,
                    encoded_modifier
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preference.preference_id,
                    preference.bond_id,
                    preference.recorded_utc.isoformat(),
                    preference.preference_class.value,
                    preference.pattern_digest,
                    float(preference.weight),
                    preference.expressed_by.value,
                    float(preference.relevance_decay_half_life_days),
                    preference.notes_digest,
                    preference.target_field,
                    float(preference.encoded_modifier),
                ),
            )

    def preferences_for_bond_and_class(
        self,
        bond_id: str,
        preference_class: PreferenceClass,
    ) -> list[AutonomyPreference]:
        if not bond_id:
            raise ValueError("bond_id is required")
        with self._lock, self._conn() as con:
            rows = con.execute(
                """
                SELECT *
                FROM autonomy_preferences
                WHERE bond_id = ? AND preference_class = ?
                ORDER BY recorded_utc ASC, preference_id ASC
                """,
                (str(bond_id), preference_class.value),
            ).fetchall()
        return [_row_to_preference(row) for row in rows]


def preferences_for_bond_and_class(
    bond_id: str,
    preference_class: PreferenceClass,
    *,
    store: AutonomyPreferences | None = None,
) -> list[AutonomyPreference]:
    active_store = store or AutonomyPreferences()
    return active_store.preferences_for_bond_and_class(bond_id, preference_class)


def tier_weight(expressed_by: PreferenceExpressedBy) -> float:
    if expressed_by is PreferenceExpressedBy.OWNER_EXPLICIT:
        return 1.0
    if expressed_by is PreferenceExpressedBy.OWNER_EXPLICIT_REVISION:
        return 1.2
    if expressed_by is PreferenceExpressedBy.OWNER_OBSERVED:
        return 0.4
    if expressed_by is PreferenceExpressedBy.SYSTEM_DEFAULT:
        return 0.1
    raise ValueError(f"unknown preference tier: {expressed_by!r}")


def record_owner_response_preference(
    *,
    bond_id: str,
    object_id: str,
    owner_response,
    pattern_digest: str,
    target_field: str,
    encoded_modifier: float,
    recorded_utc: datetime,
    store: AutonomyPreferences | None = None,
    store_path: Path | str | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> AutonomyPreference | None:
    response = _owner_response_value(owner_response)
    if response in {"acknowledged", "deferred", "no_response"}:
        return None
    if response == "corrected":
        preference = AutonomyPreference(
            preference_id=f"owner-response:{object_id}:corrected",
            bond_id=bond_id,
            recorded_utc=_coerce_utc(recorded_utc, field_name="recorded_utc"),
            preference_class=PreferenceClass.LANE_CEILING,
            pattern_digest=pattern_digest,
            weight=1.0,
            expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT_REVISION,
            relevance_decay_half_life_days=90.0,
            notes_digest=None,
            target_field=target_field,
            encoded_modifier=encoded_modifier,
        )
    elif response == "invited_more":
        preference = AutonomyPreference(
            preference_id=f"owner-response:{object_id}:invited_more",
            bond_id=bond_id,
            recorded_utc=_coerce_utc(recorded_utc, field_name="recorded_utc"),
            preference_class=PreferenceClass.ENCOURAGED_TOPIC,
            pattern_digest=pattern_digest,
            weight=0.6,
            expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
            relevance_decay_half_life_days=60.0,
            notes_digest=None,
            target_field=target_field,
            encoded_modifier=encoded_modifier,
        )
    elif response == "declined_without_teaching":
        preference = AutonomyPreference(
            preference_id=f"owner-response:{object_id}:declined_without_teaching",
            bond_id=bond_id,
            recorded_utc=_coerce_utc(recorded_utc, field_name="recorded_utc"),
            preference_class=PreferenceClass.DISCOURAGED_TOPIC,
            pattern_digest=pattern_digest,
            weight=0.4,
            expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
            relevance_decay_half_life_days=30.0,
            notes_digest=None,
            target_field=target_field,
            encoded_modifier=encoded_modifier,
        )
    else:
        raise ValueError(f"unsupported owner_response: {response!r}")

    active_store = store or AutonomyPreferences(store_path)
    active_store.append(preference)
    _emit_preference_recorded(preference, diagnostic_sink=diagnostic_sink)
    return preference


def owner_observed_preference_from_response_window(
    *,
    bond_id: str,
    samples: Iterable[DeliveredOutreachSample],
    suppression_events: Iterable[SuppressionEvent],
    preference_id: str,
    pattern_digest: str,
    target_field: str,
    encoded_modifier: float,
    recorded_utc: datetime,
) -> AutonomyPreference | None:
    delivered = _unsuppressed_delivered_samples(
        bond_id=bond_id,
        samples=samples,
        suppression_events=suppression_events,
    )
    if len(delivered) < OWNER_OBSERVED_MIN_DELIVERED_SAMPLE_SIZE:
        return None
    consistency = sum(
        1
        for sample in delivered
        if _owner_response_value(sample.owner_response) == "declined_without_teaching"
    ) / len(delivered)
    weight = 0.3 + (0.3 * consistency)
    return AutonomyPreference(
        preference_id=preference_id,
        bond_id=bond_id,
        recorded_utc=_coerce_utc(recorded_utc, field_name="recorded_utc"),
        preference_class=PreferenceClass.DISCOURAGED_TOPIC,
        pattern_digest=pattern_digest,
        weight=round(weight, 3),
        expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
        relevance_decay_half_life_days=30.0,
        notes_digest=None,
        target_field=target_field,
        encoded_modifier=encoded_modifier,
    )


def composed_policy(
    bond_id: str,
    situation_class: PreferenceClass,
    *,
    now_utc: datetime,
    store: AutonomyPreferences | None = None,
):
    from core.policies.autonomy_policy import AutonomyPolicy

    base = AutonomyPolicy.for_bond(bond_id)
    relevant = preferences_for_bond_and_class(
        bond_id,
        situation_class,
        store=store,
    )
    if not relevant:
        return base
    if situation_class is PreferenceClass.MAINTENANCE_RATIFICATION:
        return base

    candidate = base
    field_floor_authority: dict[str, bool] = {}
    field_declaration_authority: dict[str, bool] = {}
    for target_field, preferences in _group_by_target_field(relevant).items():
        weighted_sum = 0.0
        weight_total = 0.0
        can_reduce_floor = bool(preferences)
        can_exceed_declaration = False
        for pref in preferences:
            age_days = max(0.0, (now_utc - pref.recorded_utc).total_seconds() / 86400.0)
            relevance = 0.5 ** (age_days / pref.relevance_decay_half_life_days)
            contribution = pref.weight * relevance * tier_weight(pref.expressed_by)
            weighted_sum += contribution * pref.encoded_modifier
            weight_total += contribution
            if pref.expressed_by is not base.charter_floor.floor_can_only_be_reduced_by:
                can_reduce_floor = False
            if pref.expressed_by in (
                PreferenceExpressedBy.OWNER_EXPLICIT,
                PreferenceExpressedBy.OWNER_EXPLICIT_REVISION,
            ):
                can_exceed_declaration = True

        if weight_total == 0:
            continue
        candidate = _apply_modifier(
            candidate,
            target_field,
            weighted_sum / weight_total,
        )
        field_floor_authority[target_field] = can_reduce_floor
        field_declaration_authority[target_field] = can_exceed_declaration

    return _clamp_policy_by_authority(
        candidate,
        base,
        field_floor_authority,
        field_declaration_authority,
    )


def _group_by_target_field(
    preferences: Iterable[AutonomyPreference],
) -> dict[str, list[AutonomyPreference]]:
    grouped: dict[str, list[AutonomyPreference]] = {}
    for pref in preferences:
        grouped.setdefault(pref.target_field, []).append(pref)
    return grouped


def _apply_modifier(policy, target_field: str, value: float):
    if target_field not in _POLICY_FIELDS:
        raise ValueError(f"unsupported autonomy policy field: {target_field}")
    current = getattr(policy, target_field)
    if isinstance(current, int):
        value = int(round(value))
    return replace(policy, **{target_field: value})


def _clamp_policy_by_authority(
    candidate,
    base,
    field_floor_authority: dict[str, bool],
    field_declaration_authority: dict[str, bool],
):
    from core.policies.autonomy_policy import clamp_to_charter_floor

    clamped = clamp_to_charter_floor(
        candidate,
        base.charter_floor,
        expressed_by=PreferenceExpressedBy.SYSTEM_DEFAULT,
    )
    restore: dict[str, object] = {}
    floor_fields = {
        "external_knowledge_daily_call_cap",
        "owner_interrupting_daily_max_count",
        "capability_acquisition_proposal_rate_per_day",
    }
    for field in floor_fields:
        if field_floor_authority.get(field):
            restore[field] = getattr(candidate, field)
        if not field_declaration_authority.get(field):
            restore[field] = min(getattr(clamped, field), getattr(base, field))
    if restore:
        return replace(clamped, **restore)
    return clamped


def _validate_preference(preference: AutonomyPreference) -> None:
    if not preference.preference_id:
        raise ValueError("preference_id is required")
    if not preference.bond_id:
        raise ValueError("bond_id is required")
    _coerce_utc(preference.recorded_utc, field_name="recorded_utc")
    if not _is_digest(preference.pattern_digest):
        raise ValueError("pattern_digest must be hmac-sha256")
    if preference.notes_digest is not None and not _is_digest(preference.notes_digest):
        raise ValueError("notes_digest must be hmac-sha256")
    if preference.target_field not in _POLICY_FIELDS | _NON_POLICY_FIELDS:
        raise ValueError(f"unsupported autonomy policy field: {preference.target_field}")
    allowed_fields = _FIELDS_BY_CLASS[preference.preference_class]
    if preference.target_field not in allowed_fields:
        raise ValueError(
            f"{preference.preference_class.value} cannot modify {preference.target_field}"
        )
    if not 0.0 <= preference.weight <= 1.0:
        raise ValueError("weight must be between 0.0 and 1.0")
    if preference.relevance_decay_half_life_days <= 0:
        raise ValueError("relevance_decay_half_life_days must be positive")


def _unsuppressed_delivered_samples(
    *,
    bond_id: str,
    samples: Iterable[DeliveredOutreachSample],
    suppression_events: Iterable[SuppressionEvent],
) -> list[DeliveredOutreachSample]:
    relevant_events = [
        event
        for event in suppression_events
        if event.bond_id == bond_id
    ]
    for event in relevant_events:
        if not isinstance(event.suppression_kind, SuppressionKind):
            raise ValueError("suppression_kind must be SuppressionKind")
    delivered: list[DeliveredOutreachSample] = []
    for sample in samples:
        if sample.bond_id != bond_id:
            continue
        delivered_utc = _coerce_utc(sample.delivered_utc, field_name="delivered_utc")
        _owner_response_value(sample.owner_response)
        if _inside_suppression_window(delivered_utc, relevant_events):
            continue
        delivered.append(sample)
    return delivered


def _inside_suppression_window(
    delivered_utc: datetime,
    suppression_events: Iterable[SuppressionEvent],
) -> bool:
    for event in suppression_events:
        occurred = _coerce_utc(event.occurred_utc, field_name="occurred_utc")
        if occurred <= delivered_utc < occurred + timedelta(minutes=SUPPRESSION_WINDOW_MINUTES):
            return True
    return False


def _owner_response_value(owner_response) -> str:
    value = str(getattr(owner_response, "value", owner_response))
    if value not in _SUPPORTED_OWNER_RESPONSE_VALUES:
        raise ValueError(f"unsupported owner_response: {value!r}")
    return value


def _emit_preference_recorded(
    preference: AutonomyPreference,
    *,
    diagnostic_sink: DiagnosticSink | None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "PREFERENCE_RECORDED",
            "bond_id": preference.bond_id,
            "preference_id": preference.preference_id,
            "preference_class": preference.preference_class.value,
            "expressed_by": preference.expressed_by.value,
            "weight": preference.weight,
        }
    )


def _is_digest(value: str) -> bool:
    prefix = "hmac-sha256:"
    if not value.startswith(prefix):
        return False
    digest = value.removeprefix(prefix)
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _coerce_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value.astimezone(UTC)


def _row_to_preference(row: sqlite3.Row) -> AutonomyPreference:
    return AutonomyPreference(
        preference_id=str(row["preference_id"]),
        bond_id=str(row["bond_id"]),
        recorded_utc=datetime.fromisoformat(str(row["recorded_utc"])),
        preference_class=PreferenceClass(str(row["preference_class"])),
        pattern_digest=str(row["pattern_digest"]),
        weight=float(row["weight"]),
        expressed_by=PreferenceExpressedBy(str(row["expressed_by"])),
        relevance_decay_half_life_days=float(row["relevance_decay_half_life_days"]),
        notes_digest=row["notes_digest"],
        target_field=str(row["target_field"]),
        encoded_modifier=float(row["encoded_modifier"]),
    )
