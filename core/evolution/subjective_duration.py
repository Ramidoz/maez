# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Subjective-duration substrate: continuous felt-time, not a reset timer."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Literal, Mapping

from core.egress.gate import load_or_create_telemetry_key
from core.evolution.temperament import DEFAULT_DB_PATH as TEMPERAMENT_DB_PATH
from core.evolution.temperament import PARAMETER_NAMES
from core.time.temporal_spine import canonical_utc, canonical_utc_iso

SUBJECTIVE_DURATION_MIN = 0.0
SUBJECTIVE_DURATION_MAX = 10.0
MODULATION_TEMPERAMENT_INPUTS = (
    "curiosity",
    "awareness",
    "persistence",
    "joy",
    "warmth",
    "caution",
)
SCHEMA_VERSION = "subjective-duration-diagnostic-v2"
OWNER_AUTH_SURFACES = frozenset(
    {"daemon_owner", "telegram_owner", "web_owner_bridge", "manual_test", "cockpit"}
)
OWNER_AUTH_PROOFS = frozenset(
    {
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "manual_test",
        "cockpit_web_owner",
    }
)
OWNER_AUTH_PAIRINGS = {
    "daemon_owner": "daemon_reviewed_owner_auth",
    "telegram_owner": "telegram_authorized_user",
    "web_owner_bridge": "web_private_owner_bridge",
    "manual_test": "manual_test",
    "cockpit": "cockpit_web_owner",
}
# A "last owner contact" reference must come from a REAL production surface, never the manual_test
# scratch fixture — else a test row seeds a false "Rohit was here". owner_auth_class stores the SURFACE
# (see record_salience_event), so this is OWNER_AUTH_SURFACES minus the scratch surface. Derived (not a
# hand-list) so a future real surface is auto-included while manual_test is always excluded.
REAL_OWNER_CONTACT_AUTH_CLASSES = frozenset(OWNER_AUTH_SURFACES - {"manual_test"})


@dataclass(frozen=True)
class SubjectiveDurationOwnerAuth:
    surface: Literal["daemon_owner", "telegram_owner", "web_owner_bridge", "manual_test", "cockpit"]
    proof: Literal[
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "manual_test",
        "cockpit_web_owner",
    ]

    def __post_init__(self) -> None:
        if self.surface not in OWNER_AUTH_SURFACES:
            raise ValueError("unknown subjective-duration owner-auth surface")
        if self.proof not in OWNER_AUTH_PROOFS:
            raise ValueError("unknown subjective-duration owner-auth proof")
        if OWNER_AUTH_PAIRINGS[self.surface] != self.proof:
            raise ValueError("subjective-duration owner-auth surface/proof mismatch")


@dataclass(frozen=True)
class SubjectiveDurationSnapshot:
    value: float
    felt_time_rate: float
    residual_resonance: float
    retrospective_density: float
    render_band: str
    surface_phrase: str
    source_ref_digest: str | None
    elapsed_seconds: float = 0.0
    drag_multiplier: float = 0.0
    engagement_multiplier: float = 0.0

    @property
    def felt_value(self) -> float:
        return self.value


@dataclass(frozen=True)
class SalienceEventDefinition:
    kind: str
    producer_ref_required: bool
    affects: frozenset[str]
    owner_auth_required: bool
    reviewed_registration_ref: str


class ProducerRef(Enum):
    """Reviewed producer identities allowed to submit producer snapshots."""

    MANUAL_TEST_PRODUCER = "manual_test_producer"
    DRIVE_DRIVEN_CURIOSITY = "drive_driven_curiosity"


@dataclass(frozen=True)
class MeaningfulSalienceEventRecord:
    event_id: int
    ts_utc: str
    salience_event_kind: str
    producer_ref: str
    bond_id: str
    producer_event_id: str
    producer_temperament_before: dict[str, float | None]
    producer_temperament_after: dict[str, float | None]
    meaningfulness_score: float
    meaningfulness_input_count: int
    temperament_delta_mean: float | None
    temperament_delta_max: float | None
    is_canary: bool


@dataclass(frozen=True)
class SubjectiveDurationConfig:
    base_rate_per_hour: float = 0.42
    recovery_rate_per_hour: float = 0.18
    residual_echo_half_life_seconds: float = 4 * 60 * 60
    default_timeout_s: float = 10.0

    def __post_init__(self) -> None:
        for name in (
            "base_rate_per_hour",
            "recovery_rate_per_hour",
            "residual_echo_half_life_seconds",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")


def _default_db_path() -> Path:
    override = os.environ.get("MAEZ_SUBJECTIVE_DURATION_DB")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir

        return memory_dir() / "subjective_duration.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "subjective_duration.db"


def _default_log_path() -> Path:
    override = os.environ.get("MAEZ_SUBJECTIVE_DURATION_LOG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "logs" / "subjective_duration_diagnostics.jsonl"


def build_salience_event_registry() -> Mapping[str, SalienceEventDefinition]:
    entries = {
        "owner_contact": SalienceEventDefinition(
            kind="owner_contact",
            producer_ref_required=True,
            affects=frozenset({"felt_time_rate", "retrospective_density"}),
            owner_auth_required=True,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "meaningful_exchange": SalienceEventDefinition(
            kind="meaningful_exchange",
            producer_ref_required=True,
            affects=frozenset({"residual_resonance", "retrospective_density"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "engaged_work": SalienceEventDefinition(
            kind="engaged_work",
            producer_ref_required=True,
            affects=frozenset({"retrospective_density", "engagement_multiplier"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "idle_cycle": SalienceEventDefinition(
            kind="idle_cycle",
            producer_ref_required=True,
            affects=frozenset({"drag_multiplier"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "public_stranger_contact": SalienceEventDefinition(
            kind="public_stranger_contact",
            producer_ref_required=True,
            affects=frozenset({"retrospective_density"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "manual_test_event": SalienceEventDefinition(
            kind="manual_test_event",
            producer_ref_required=False,
            affects=frozenset({"diagnostic_trace"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
        "clock_degraded_event": SalienceEventDefinition(
            kind="clock_degraded_event",
            producer_ref_required=False,
            affects=frozenset({"degraded_clock"}),
            owner_auth_required=False,
            reviewed_registration_ref="docs/slices/track-b-subjective-duration/spec.md",
        ),
    }
    return dict(entries)


def _clamp(value: float, low: float = SUBJECTIVE_DURATION_MIN, high: float = SUBJECTIVE_DURATION_MAX) -> float:
    return max(low, min(high, value))


def _require_finite_nonnegative(name: str, value: float) -> float:
    value_f = float(value)
    if not math.isfinite(value_f) or value_f < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value_f


def compute_subjective_duration_update(
    *,
    prior_value: float,
    delta_hours: float,
    drag_multiplier: float,
    engagement_multiplier: float,
    residual_multiplier: float,
    config: SubjectiveDurationConfig,
) -> float:
    prior_raw = float(prior_value)
    if not math.isfinite(prior_raw):
        raise ValueError("prior_value must be finite")
    prior = _clamp(prior_raw)
    delta = _require_finite_nonnegative("delta_hours", delta_hours)
    drag = _require_finite_nonnegative("drag_multiplier", drag_multiplier)
    engagement = _require_finite_nonnegative("engagement_multiplier", engagement_multiplier)
    residual = _require_finite_nonnegative("residual_multiplier", residual_multiplier)
    upward = config.base_rate_per_hour * drag * residual * (1.0 - prior / 10.0)
    downward = config.recovery_rate_per_hour * engagement * (prior / 10.0)
    return _clamp(prior + (upward - downward) * delta)


def _normalize_event_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime) and value.tzinfo is None:
        raise ValueError("subjective_duration requires aware UTC-compatible datetime")
    return canonical_utc(value, field_name="event_at")


def _hmac_digest(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    raw = value if isinstance(value, bytes) else str(value).encode("utf-8", errors="replace")
    key = load_or_create_telemetry_key()
    return "hmac-sha256:" + hmac.new(key, raw, hashlib.sha256).hexdigest()


def _digest_temperament(values: Mapping[str, float | None]) -> str:
    payload = json.dumps(
        {name: values.get(name) for name in MODULATION_TEMPERAMENT_INPUTS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return _hmac_digest(payload) or "hmac-sha256:" + ("0" * 64)


def _safe_temperament(temperament_reader: Callable[[], Mapping[str, float | None]]) -> dict[str, float | None]:
    try:
        raw = dict(temperament_reader() or {})
    except Exception:
        raw = {}
    return {name: raw.get(name) for name in MODULATION_TEMPERAMENT_INPUTS}


def _read_current_temperament() -> dict[str, float | None]:
    if not TEMPERAMENT_DB_PATH.exists():
        return {name: None for name in PARAMETER_NAMES}
    try:
        with closing(sqlite3.connect(TEMPERAMENT_DB_PATH)) as conn:
            rows = conn.execute(
                "SELECT parameter, value FROM temperament_events "
                "WHERE event_id IN ("
                "  SELECT MAX(event_id) FROM temperament_events GROUP BY parameter"
                ")"
            ).fetchall()
    except sqlite3.Error:
        return {name: None for name in PARAMETER_NAMES}
    latest = {str(parameter): float(value) for parameter, value in rows}
    return {name: latest.get(name) for name in PARAMETER_NAMES}


def _observed_temperament_values(values: Mapping[str, float | None]) -> dict[str, float]:
    observed: dict[str, float] = {}
    for name in MODULATION_TEMPERAMENT_INPUTS:
        value = values.get(name)
        if value is None:
            continue
        try:
            observed[name] = _clamp(float(value))
        except (TypeError, ValueError):
            continue
    return observed


def _serialize_temperament_snapshot(snapshot: Mapping[str, float | None] | None) -> str:
    if snapshot is None:
        return ""
    normalized = {str(key): (None if value is None else float(value)) for key, value in snapshot.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _parse_temperament_snapshot(raw: str) -> dict[str, float | None]:
    if not raw:
        return {}
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    parsed: dict[str, float | None] = {}
    for key, value in loaded.items():
        parsed[str(key)] = None if value is None else float(value)
    return parsed


def _validate_producer_ref(producer_ref: str) -> None:
    valid = {entry.value for entry in ProducerRef}
    if producer_ref not in valid:
        raise ValueError(f"unknown producer_ref: {producer_ref!r}; valid: {sorted(valid)}")


def _build_metadata_json(*, salience_event_kind: str, producer_snapshot_path: bool) -> str:
    metadata: dict[str, object] = {}
    if producer_snapshot_path and salience_event_kind != "meaningful_exchange":
        metadata["kind_gated_zero_score"] = True
    return json.dumps(metadata, sort_keys=True, separators=(",", ":")) if metadata else "{}"


def _migrate_meaningful_salience_seam(conn: sqlite3.Connection) -> None:
    info = conn.execute("PRAGMA table_info(subjective_duration_salience_events)").fetchall()
    existing = {row[1] for row in info}
    migrations = [
        ("bond_id", "ADD COLUMN bond_id TEXT NOT NULL DEFAULT '_LEGACY'"),
        ("producer_event_id", "ADD COLUMN producer_event_id TEXT NOT NULL DEFAULT ''"),
        (
            "producer_temperament_before_json",
            "ADD COLUMN producer_temperament_before_json TEXT NOT NULL DEFAULT ''",
        ),
        (
            "producer_temperament_after_json",
            "ADD COLUMN producer_temperament_after_json TEXT NOT NULL DEFAULT ''",
        ),
        ("is_canary", "ADD COLUMN is_canary INTEGER NOT NULL DEFAULT 0"),
    ]
    for column_name, alter_sql in migrations:
        if column_name not in existing:
            conn.execute(f"ALTER TABLE subjective_duration_salience_events {alter_sql}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sd_events_bond_producer "
        "ON subjective_duration_salience_events(bond_id, producer_event_id)"
    )
    conn.commit()


def _temperament_modulators(values: Mapping[str, float | None]) -> tuple[float, float, float]:
    def v(name: str) -> float:
        raw = values.get(name)
        try:
            return _clamp(float(raw)) / 10.0 if raw is not None else 0.5
        except (TypeError, ValueError):
            return 0.5

    engagement = (
        0.30 * v("curiosity")
        + 0.20 * v("awareness")
        + 0.20 * v("persistence")
        + 0.15 * v("joy")
        + 0.15 * v("warmth")
    )
    caution = v("caution")
    caution_drag = 0.5 + (0.5 * caution)
    drag_multiplier = _clamp(1.35 - (0.70 * engagement) + (0.25 * caution_drag), 0.35, 1.75)
    engagement_multiplier = _clamp(0.40 + (0.90 * engagement), 0.40, 1.30)
    felt_time_rate = _require_finite_nonnegative("felt_time_rate", drag_multiplier / max(engagement_multiplier, 0.001))
    return drag_multiplier, engagement_multiplier, felt_time_rate


def _render(value: float) -> tuple[str, str]:
    if value < 1.0:
        return "light", "time feels light right now"
    if value < 3.0:
        return "mildly_stretched", "time has a little stretch to it"
    if value < 6.0:
        return "felt_while", "it has felt like a while"
    if value < 8.5:
        return "long_stretch", "time has felt like a long quiet stretch"
    return "very_long_stretch", "the quiet has felt very long"


def _diagnostic_row(
    *,
    timestamp_utc: str,
    event_type: Literal["sample", "salience_event"],
    value: float,
    felt_time_rate: float,
    render_band: str,
    residual_resonance: float,
    retrospective_density: float,
    salience_event_kind: str | None = None,
    producer_ref: str | None = None,
    owner_auth_class: str | None = None,
    source_ref_digest: str | None = None,
    source_ref_present: bool = False,
    meaningfulness_score: float | None = None,
    meaningfulness_input_count: int | None = None,
    temperament_delta_mean: float | None = None,
    temperament_delta_max: float | None = None,
    temperament_before_digest: str | None = None,
    temperament_after_digest: str | None = None,
    explicit_salience_marker_present: bool = False,
    bond_id: str | None = None,
    producer_event_id: str | None = None,
    producer_temperament_before_json: str | None = None,
    producer_temperament_after_json: str | None = None,
    is_canary: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp_utc": timestamp_utc,
        "event_type": event_type,
        "value": round(float(value), 6),
        "felt_time_rate": round(float(felt_time_rate), 6),
        "render_band": render_band,
        "residual_resonance": round(float(residual_resonance), 6),
        "retrospective_density": round(float(retrospective_density), 6),
        "salience_event_kind": salience_event_kind,
        "producer_ref": producer_ref,
        "owner_auth_class": owner_auth_class,
        "source_ref_digest": source_ref_digest,
        "source_ref_present": bool(source_ref_present),
        "meaningfulness_score": meaningfulness_score,
        "meaningfulness_input_count": meaningfulness_input_count,
        "temperament_delta_mean": temperament_delta_mean,
        "temperament_delta_max": temperament_delta_max,
        "temperament_before_digest": temperament_before_digest,
        "temperament_after_digest": temperament_after_digest,
        "explicit_salience_marker_present": bool(explicit_salience_marker_present),
        "bond_id": bond_id,
        "producer_event_id": producer_event_id,
        "producer_temperament_before_json": producer_temperament_before_json,
        "producer_temperament_after_json": producer_temperament_after_json,
        "is_canary": bool(is_canary),
        "content_recorded": False,
    }


def humanize_elapsed(seconds: float) -> str:
    """Render elapsed seconds as a coarse human phrase for the felt-time perception line."""
    s = max(0.0, float(seconds))
    if s < 60:
        return "under a minute"
    minutes = int(s // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours}h {rem_min}m" if rem_min else f"{hours}h"
    days = hours // 24
    rem_hr = hours % 24
    return f"{days}d {rem_hr}h" if rem_hr else f"{days}d"


CURRENT_COMPUTE_VERSION = 1


def config_for_version(compute_version: int) -> SubjectiveDurationConfig:
    """Map a stored compute_version to the curve config that produced it, so old intervals
    replay under their original formula — never today's. v1 == the original curve constants."""
    return SubjectiveDurationConfig()


def replay_felt_value(anchor_row: Mapping[str, object], *, at_ts: datetime) -> float:
    """Reconstruct felt_value at `at_ts` by replaying FORWARD from `anchor_row` using the anchor's
    FROZEN modulators + compute_version. Reads ONLY the anchor — never live temperament/residual.
    anchor_row needs: ts (aware dt), value, drag_multiplier, engagement_multiplier,
    residual_resonance, compute_version."""
    delta_hours = max(0.0, (at_ts - anchor_row["ts"]).total_seconds() / 3600.0)
    return compute_subjective_duration_update(
        prior_value=float(anchor_row["value"]),
        delta_hours=delta_hours,
        drag_multiplier=float(anchor_row["drag_multiplier"]),
        engagement_multiplier=float(anchor_row["engagement_multiplier"]),
        residual_multiplier=1.0 + (0.35 * float(anchor_row["residual_resonance"])),
        config=config_for_version(int(anchor_row.get("compute_version", 1))),
    )


class SubjectiveDuration:
    """Append-only continuous felt-time store.

    The substrate reads temperament as felt weight; it never writes it.
    """

    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        diagnostic_log_path: Path | str | None = None,
        temperament_reader: Callable[[], Mapping[str, float | None]] | None = None,
        config: SubjectiveDurationConfig | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.diagnostic_log_path = (
            Path(diagnostic_log_path) if diagnostic_log_path is not None else _default_log_path()
        )
        self.config = config or SubjectiveDurationConfig()
        self.temperament_reader = temperament_reader or _read_current_temperament
        self.registry = build_salience_event_registry()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS subjective_duration_samples (
                    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    value REAL NOT NULL,
                    felt_time_rate REAL NOT NULL,
                    drag_multiplier REAL NOT NULL,
                    engagement_multiplier REAL NOT NULL,
                    residual_resonance REAL NOT NULL,
                    retrospective_density REAL NOT NULL,
                    compute_version INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS subjective_duration_salience_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    salience_event_kind TEXT NOT NULL,
                    producer_ref TEXT NOT NULL DEFAULT '',
                    owner_auth_class TEXT NOT NULL DEFAULT '',
                    source_ref_digest TEXT NOT NULL DEFAULT '',
                    meaningfulness_score REAL NOT NULL DEFAULT 0.0,
                    meaningfulness_input_count INTEGER NOT NULL DEFAULT 0,
                    temperament_delta_mean REAL,
                    temperament_delta_max REAL,
                    temperament_before_digest TEXT NOT NULL DEFAULT '',
                    temperament_after_digest TEXT NOT NULL DEFAULT '',
                    explicit_salience_marker_present INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_sd_samples_ts ON subjective_duration_samples(ts_utc);
                CREATE INDEX IF NOT EXISTS idx_sd_events_ts ON subjective_duration_salience_events(ts_utc);
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(subjective_duration_samples)")}
            if "compute_version" not in cols:
                conn.execute("ALTER TABLE subjective_duration_samples "
                             "ADD COLUMN compute_version INTEGER NOT NULL DEFAULT 1")
                conn.commit()
            _migrate_meaningful_salience_seam(conn)

    def _compute(self, now: datetime) -> tuple[SubjectiveDurationSnapshot, Mapping[str, object] | None]:
        """PURE read-only felt-time computation — writes NOTHING (no sample, no salience event).

        Returns (snapshot, degraded_latest): on clock-degraded (now < latest ts) the snapshot is
        the last row's (which lacks elapsed_seconds/modulators — the honest-failure path) and
        degraded_latest is that row, so the WRITER (current()) can record the degraded salience
        event. On the normal path degraded_latest is None. peek() ignores it (truly read-only)."""
        latest = self._latest_sample()
        if latest is not None and now < latest["ts"]:
            return self._snapshot_from_row(latest, source_ref_digest=None), latest
        prior_value = 0.0 if latest is None else float(latest["value"])
        prior_ts = now if latest is None else latest["ts"]
        delta_hours = max(0.0, (now - prior_ts).total_seconds() / 3600.0)
        temperament = _safe_temperament(self.temperament_reader)
        drag, engagement, felt_time_rate = _temperament_modulators(temperament)
        residual = self._residual_resonance(now)
        value = compute_subjective_duration_update(
            prior_value=prior_value,
            delta_hours=delta_hours,
            drag_multiplier=drag,
            engagement_multiplier=engagement,
            residual_multiplier=1.0 + (0.35 * residual),
            config=self.config,
        )
        retrospective_density = self._retrospective_density(now, temperament)
        render_band, surface_phrase = _render(value)
        return SubjectiveDurationSnapshot(
            value=value,
            felt_time_rate=felt_time_rate,
            residual_resonance=residual,
            retrospective_density=retrospective_density,
            render_band=render_band,
            surface_phrase=surface_phrase,
            source_ref_digest=None,
            elapsed_seconds=(now - prior_ts).total_seconds(),
            drag_multiplier=drag,
            engagement_multiplier=engagement,
        ), None

    def peek(self, *, now_utc: str | datetime | None = None) -> SubjectiveDurationSnapshot:
        now = _normalize_event_time(now_utc or datetime.now(UTC))
        snap, _degraded_latest = self._compute(now)   # truly read-only — ignores the degraded signal
        return snap

    def time_sense_context(self, *, now: str | datetime | None = None) -> dict | None:
        """Truthful read-only felt-time context for Slice-2 feed/stamp. Returns a valid context
        {felt_value, felt_phrase, felt_compute_version, seconds_since_last_owner_contact} or None.
        None (without writing) when: the clock is degraded, or there is no real owner-contact
        reference. NEVER records a clock_degraded_event (that write belongs to current())."""
        now_dt = _normalize_event_time(now or datetime.now(UTC))
        snap, degraded_latest = self._compute(now_dt)
        if degraded_latest is not None:
            return None                      # clock-degraded -> absent, not stale-as-alive (no write)
        seconds_since = self._seconds_since_last_owner_contact(now_dt)
        if seconds_since is None:
            return None                      # no real owner-contact reference yet
        return {
            "felt_value": snap.value,
            "felt_phrase": snap.surface_phrase,
            "felt_compute_version": CURRENT_COMPUTE_VERSION,
            "seconds_since_last_owner_contact": seconds_since,
        }

    def _seconds_since_last_owner_contact(self, now: datetime) -> float | None:
        """Wall-clock seconds since the latest REAL owner_contact salience event (canary/scratch
        rows excluded). None if there is no such row or the clock is before it."""
        classes = tuple(sorted(REAL_OWNER_CONTACT_AUTH_CLASSES))
        placeholders = ",".join("?" for _ in classes)
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT ts_utc FROM subjective_duration_salience_events "
                "WHERE salience_event_kind = 'owner_contact' AND is_canary = 0 "
                f"AND owner_auth_class IN ({placeholders}) "
                "ORDER BY event_id DESC LIMIT 1",
                classes,
            ).fetchone()
        if row is None:
            return None
        contact_ts = _normalize_event_time(row[0])
        delta = (now - contact_ts).total_seconds()
        return delta if delta >= 0 else None

    def current(self, *, now_utc: str | datetime | None = None) -> SubjectiveDurationSnapshot:
        now = _normalize_event_time(now_utc or datetime.now(UTC))
        snap, degraded_latest = self._compute(now)
        if degraded_latest is not None:
            # clock-degraded: current() OWNS the honesty write (once); NO sample insert on this path.
            self._record_clock_degraded_event(now=now, latest=degraded_latest)
            return snap
        ts_iso = now.isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO subjective_duration_samples "
                "(ts_utc, value, felt_time_rate, drag_multiplier, engagement_multiplier, "
                "residual_resonance, retrospective_density, metadata_json, compute_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts_iso,
                    snap.value,
                    snap.felt_time_rate,
                    snap.drag_multiplier,
                    snap.engagement_multiplier,
                    snap.residual_resonance,
                    snap.retrospective_density,
                    "{}",
                    CURRENT_COMPUTE_VERSION,
                ),
            )
            conn.commit()
        self._write_diagnostic(
            _diagnostic_row(
                timestamp_utc=ts_iso,
                event_type="sample",
                value=snap.value,
                felt_time_rate=snap.felt_time_rate,
                render_band=snap.render_band,
                residual_resonance=snap.residual_resonance,
                retrospective_density=snap.retrospective_density,
            )
        )
        return snap

    def perception_line(self, *, owner_auth: SubjectiveDurationOwnerAuth | None = None,
                        now_utc: str | datetime | None = None) -> str:
        if owner_auth is not None and not isinstance(owner_auth, SubjectiveDurationOwnerAuth):
            return ""
        snap = self.peek(now_utc=now_utc)   # recompute to exact-now (read-only); never echo the stale row
        return f"Felt time: {snap.surface_phrase}."

    def record_salience_event(
        self,
        *,
        salience_event_kind: str,
        producer_ref: str = "",
        source_ref: str | None = None,
        owner_auth: SubjectiveDurationOwnerAuth | None = None,
        meaningfulness_score: float | None = None,
        explicit_salience_marker_present: bool = False,
        now_utc: str | datetime | None = None,
        bond_id: str | None = None,
        producer_event_id: str | None = None,
        producer_temperament_before: Mapping[str, float | None] | None = None,
        producer_temperament_after: Mapping[str, float | None] | None = None,
        is_canary: bool = False,
    ) -> int:
        if salience_event_kind not in self.registry:
            raise ValueError(f"unknown salience_event_kind: {salience_event_kind}")
        definition = self.registry[salience_event_kind]

        producer_kwargs = (
            bond_id,
            producer_event_id,
            producer_temperament_before,
            producer_temperament_after,
        )
        producer_snapshot_path = any(value is not None for value in producer_kwargs)
        if is_canary and not producer_snapshot_path:
            raise ValueError("is_canary=True requires the producer-snapshot path")
        if producer_snapshot_path and any(value is None for value in producer_kwargs):
            raise ValueError(
                "producer-snapshot path requires ALL of: bond_id, producer_event_id, "
                "producer_temperament_before, producer_temperament_after"
            )
        if producer_snapshot_path:
            if not isinstance(bond_id, str) or not bond_id:
                raise ValueError("bond_id must be a non-empty string")
            if bond_id == "_LEGACY":
                raise ValueError(
                    "bond_id='_LEGACY' is the pre-bond-substrate sentinel; "
                    "live producers may not write under it"
                )
            if bond_id in {"*", "%", "all", "any"}:
                raise ValueError(f"bond_id={bond_id!r} is a wildcard pattern; refused")
            _validate_producer_ref(producer_ref)
            if not isinstance(producer_event_id, str) or not producer_event_id:
                raise ValueError("producer_event_id must be a non-empty string")
            if meaningfulness_score is not None:
                raise ValueError(
                    "producer-snapshot path auto-computes meaningfulness_score; "
                    "callers may not supply an explicit score"
                )
        if definition.owner_auth_required and not isinstance(owner_auth, SubjectiveDurationOwnerAuth):
            raise PermissionError("owner-authenticated salience event requires typed owner auth")
        if definition.producer_ref_required and not producer_ref:
            raise ValueError("producer_ref required for salience event")

        now = _normalize_event_time(now_utc or datetime.now(UTC))
        if producer_snapshot_path:
            before = {
                name: producer_temperament_before.get(name)  # type: ignore[union-attr]
                for name in MODULATION_TEMPERAMENT_INPUTS
            }
            after = {
                name: producer_temperament_after.get(name)  # type: ignore[union-attr]
                for name in MODULATION_TEMPERAMENT_INPUTS
            }
        else:
            before = _safe_temperament(self.temperament_reader)
            after = _safe_temperament(self.temperament_reader)
        observed_before = _observed_temperament_values(before)
        observed_after = _observed_temperament_values(after)
        shared = [name for name in MODULATION_TEMPERAMENT_INPUTS if name in observed_before and name in observed_after]
        deltas = [abs(observed_after[name] - observed_before[name]) for name in shared]
        if meaningfulness_score is None:
            if deltas and salience_event_kind == "meaningful_exchange":
                meaningfulness_score = _clamp(sum(deltas) / len(deltas) / 2.0, 0.0, 1.0)
            else:
                meaningfulness_score = 0.0
        else:
            meaningfulness_value = float(meaningfulness_score)
            if not math.isfinite(meaningfulness_value):
                raise ValueError("meaningfulness_score must be finite")
            meaningfulness_score = _clamp(meaningfulness_value, 0.0, 1.0)
            if meaningfulness_score > 0.0 and not explicit_salience_marker_present:
                raise PermissionError(
                    "nonzero explicit meaningfulness_score requires reviewed salience marker"
                )
        delta_mean = (sum(deltas) / len(deltas)) if deltas else None
        delta_max = max(deltas) if deltas else None
        source_ref_present = bool(source_ref)
        source_digest = _hmac_digest(source_ref) if source_ref_present else ""
        before_json = _serialize_temperament_snapshot(producer_temperament_before) if producer_snapshot_path else ""
        after_json = _serialize_temperament_snapshot(producer_temperament_after) if producer_snapshot_path else ""
        row_bond_id = bond_id if producer_snapshot_path else "_LEGACY"
        row_producer_event_id = producer_event_id if producer_snapshot_path else ""
        metadata_json = _build_metadata_json(
            salience_event_kind=salience_event_kind,
            producer_snapshot_path=producer_snapshot_path,
        )
        ts_iso = now.isoformat()
        latest = self._latest_sample()
        value = 0.0 if latest is None else float(latest["value"])
        residual = self._residual_resonance(now)
        render_band, _ = _render(value)
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO subjective_duration_salience_events "
                "(ts_utc, salience_event_kind, producer_ref, owner_auth_class, source_ref_digest, "
                "meaningfulness_score, meaningfulness_input_count, temperament_delta_mean, temperament_delta_max, "
                "temperament_before_digest, temperament_after_digest, explicit_salience_marker_present, metadata_json, "
                "bond_id, producer_event_id, producer_temperament_before_json, producer_temperament_after_json, is_canary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts_iso,
                    salience_event_kind,
                    producer_ref or "",
                    owner_auth.surface if owner_auth else "",
                    source_digest,
                    meaningfulness_score,
                    len(deltas),
                    delta_mean,
                    delta_max,
                    _digest_temperament(before),
                    _digest_temperament(after),
                    1 if explicit_salience_marker_present else 0,
                    metadata_json,
                    row_bond_id,
                    row_producer_event_id,
                    before_json,
                    after_json,
                    1 if is_canary else 0,
                ),
            )
            event_id = int(cur.lastrowid)
            conn.commit()
        self._write_diagnostic(
            _diagnostic_row(
                timestamp_utc=ts_iso,
                event_type="salience_event",
                value=value,
                felt_time_rate=0.0,
                render_band=render_band,
                residual_resonance=residual,
                retrospective_density=self._retrospective_density(now, after),
                salience_event_kind=salience_event_kind,
                producer_ref=producer_ref or None,
                owner_auth_class=owner_auth.surface if owner_auth else "",
                source_ref_digest=source_digest,
                source_ref_present=source_ref_present,
                meaningfulness_score=meaningfulness_score,
                meaningfulness_input_count=len(deltas),
                temperament_delta_mean=delta_mean,
                temperament_delta_max=delta_max,
                temperament_before_digest=_digest_temperament(before),
                temperament_after_digest=_digest_temperament(after),
                explicit_salience_marker_present=explicit_salience_marker_present,
                bond_id=row_bond_id,
                producer_event_id=producer_event_id if producer_snapshot_path else None,
                producer_temperament_before_json=before_json or None,
                producer_temperament_after_json=after_json or None,
                is_canary=is_canary,
            )
        )
        return event_id

    def lookup_meaningful_salience_event_record(
        self,
        *,
        bond_id: str,
        producer_event_id: str,
    ) -> MeaningfulSalienceEventRecord | None:
        if not bond_id:
            raise ValueError("bond_id required; empty string refused")
        if bond_id == "_LEGACY":
            raise ValueError(
                "bond_id='_LEGACY' is the pre-bond-substrate sentinel; "
                "legacy rows are addressable only via event_id"
            )
        if bond_id == "_SCRATCH_FIXTURE":
            raise ValueError("bond_id='_SCRATCH_FIXTURE' is the scratch-canary sentinel; production lookup refuses it")
        if bond_id in {"*", "%", "all", "any"}:
            raise ValueError(f"bond_id={bond_id!r} is a wildcard pattern; refused")
        if not producer_event_id:
            raise ValueError("producer_event_id required; empty string refused")

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT event_id, ts_utc, salience_event_kind, producer_ref, bond_id, producer_event_id, "
                "producer_temperament_before_json, producer_temperament_after_json, meaningfulness_score, "
                "meaningfulness_input_count, temperament_delta_mean, temperament_delta_max, is_canary "
                "FROM subjective_duration_salience_events "
                "WHERE bond_id = ? AND producer_event_id = ? "
                "ORDER BY event_id DESC LIMIT 1",
                (bond_id, producer_event_id),
            ).fetchone()
        if row is None:
            return None
        return MeaningfulSalienceEventRecord(
            event_id=int(row["event_id"]),
            ts_utc=str(row["ts_utc"]),
            salience_event_kind=str(row["salience_event_kind"]),
            producer_ref=str(row["producer_ref"]),
            bond_id=str(row["bond_id"]),
            producer_event_id=str(row["producer_event_id"]),
            producer_temperament_before=_parse_temperament_snapshot(str(row["producer_temperament_before_json"])),
            producer_temperament_after=_parse_temperament_snapshot(str(row["producer_temperament_after_json"])),
            meaningfulness_score=float(row["meaningfulness_score"]),
            meaningfulness_input_count=int(row["meaningfulness_input_count"]),
            temperament_delta_mean=None if row["temperament_delta_mean"] is None else float(row["temperament_delta_mean"]),
            temperament_delta_max=None if row["temperament_delta_max"] is None else float(row["temperament_delta_max"]),
            is_canary=bool(row["is_canary"]),
        )

    def _latest_sample(self) -> dict[str, object] | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM subjective_duration_samples ORDER BY sample_id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        parsed = canonical_utc(str(result["ts_utc"]), field_name="event_at")
        result["ts"] = parsed
        render_band, surface_phrase = _render(float(result["value"]))
        result["render_band"] = render_band
        result["surface_phrase"] = surface_phrase
        return result

    def _snapshot_from_row(self, row: Mapping[str, object], *, source_ref_digest: str | None) -> SubjectiveDurationSnapshot:
        return SubjectiveDurationSnapshot(
            value=float(row["value"]),
            felt_time_rate=float(row["felt_time_rate"]),
            residual_resonance=float(row["residual_resonance"]),
            retrospective_density=float(row["retrospective_density"]),
            render_band=str(row["render_band"]),
            surface_phrase=str(row["surface_phrase"]),
            source_ref_digest=source_ref_digest,
        )

    def _record_clock_degraded_event(self, *, now: datetime, latest: Mapping[str, object]) -> None:
        ts_iso = canonical_utc_iso(now, field_name="event_at")
        self.record_salience_event(
            salience_event_kind="clock_degraded_event",
            producer_ref="subjective_duration:clock",
            now_utc=ts_iso,
        )

    def _residual_resonance(self, now: datetime) -> float:
        lookback_seconds = max(24 * 60 * 60, 6 * self.config.residual_echo_half_life_seconds)
        cutoff = now - timedelta(seconds=lookback_seconds)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT ts_utc, meaningfulness_score FROM subjective_duration_salience_events "
                "WHERE salience_event_kind = 'meaningful_exchange' "
                "AND bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE') "
                "AND is_canary = 0 "
                "ORDER BY event_id DESC"
            ).fetchall()
        resonance = 0.0
        half_life = self.config.residual_echo_half_life_seconds
        for ts_raw, score in rows:
            event_ts = canonical_utc(str(ts_raw), field_name="event_at")
            if event_ts < cutoff or event_ts > now:
                continue
            age_seconds = (now - event_ts).total_seconds()
            resonance += float(score or 0.0) * (0.5 ** (age_seconds / half_life))
        return _clamp(resonance, 0.0, 1.0)

    def _retrospective_density(self, now: datetime, temperament: Mapping[str, float | None]) -> float:
        observed = _observed_temperament_values(temperament)
        engagement_names = ("curiosity", "awareness", "persistence", "joy", "warmth")
        weights = {"curiosity": 0.30, "awareness": 0.20, "persistence": 0.20, "joy": 0.15, "warmth": 0.15}
        engagement = sum(weights[name] * (observed.get(name, 5.0) / 10.0) for name in engagement_names)
        recent_count = self._recent_meaningful_event_count_capped(now)
        return _clamp((0.45 * engagement) + (0.35 * self._residual_resonance(now)) + (0.20 * recent_count), 0.0, 1.0)

    def _recent_meaningful_event_count_capped(self, now: datetime) -> float:
        lookback_seconds = max(24 * 60 * 60, 6 * self.config.residual_echo_half_life_seconds)
        cutoff = now - timedelta(seconds=lookback_seconds)
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT ts_utc FROM subjective_duration_salience_events "
                "WHERE salience_event_kind = 'meaningful_exchange' "
                "AND meaningfulness_score > 0.0 "
                "AND bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE') "
                "AND is_canary = 0"
            ).fetchall()
        count = 0
        for (ts_raw,) in rows:
            event_ts = canonical_utc(str(ts_raw), field_name="event_at")
            if cutoff <= event_ts <= now:
                count += 1
        return _clamp(count / 3.0, 0.0, 1.0)

    def _write_diagnostic(self, row: Mapping[str, object]) -> None:
        try:
            self.diagnostic_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.diagnostic_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":")) + "\n")
        except Exception:
            pass


def subjective_duration_prompt_line(
    *,
    owner_auth: SubjectiveDurationOwnerAuth | None = None,
    store: SubjectiveDuration | None = None,
    now_utc: str | datetime | None = None,
) -> str:
    if not isinstance(owner_auth, SubjectiveDurationOwnerAuth):
        return ""
    try:
        sd = store or SubjectiveDuration()
        snap = sd.current(now_utc=now_utc or datetime.now(UTC))
        return f"Felt time: {snap.surface_phrase}."
    except Exception:
        return ""
