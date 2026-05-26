from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Literal

from core import paths
from core.policies.autonomy_preferences import (
    AutonomyPreferences,
    PreferenceClass,
    composed_policy,
)


class SignalQuality(Enum):
    HIGH = "high"
    LOW = "low"
    UNKNOWN = "unknown"


class OwnerState(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PriorityClass(Enum):
    OWNER_BOND = "owner_bond"
    SAFETY_OR_HEALTH = "safety_or_health"
    SELF_GROWTH = "self_growth"
    WORLD_KNOWLEDGE = "world_knowledge"

    @property
    def override_budget(self) -> bool:
        return self is PriorityClass.SAFETY_OR_HEALTH


class SuppressionKind(Enum):
    SIGNAL_GATED = "SIGNAL_GATED"


@dataclass(frozen=True)
class SignalObservation:
    name: str
    confidence: float
    owner_state: OwnerState


@dataclass(frozen=True)
class GateDecision:
    bond_id: str
    decision: Literal["allow", "deny", "defer"]
    reason: str
    consulted_signals: frozenset[str]
    signal_quality: SignalQuality
    owner_state: OwnerState
    recheck_after_seconds: int | None


DiagnosticSink = Callable[[dict], None]


class OutreachLedger:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.owner_outreach_db()
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
                CREATE TABLE IF NOT EXISTS owner_outreach_dispatches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bond_id TEXT NOT NULL,
                    dispatched_utc TEXT NOT NULL,
                    priority_class TEXT NOT NULL,
                    owner_state_at_dispatch TEXT NOT NULL,
                    signal_quality TEXT NOT NULL,
                    importance REAL NOT NULL,
                    decision TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_owner_outreach_bond_time
                ON owner_outreach_dispatches (bond_id, dispatched_utc)
                """
            )
            existing_cols = {
                row[1]
                for row in con.execute(
                    "PRAGMA table_info(owner_outreach_dispatches)"
                ).fetchall()
            }
            if "owner_state_at_dispatch" not in existing_cols:
                try:
                    con.execute(
                        "ALTER TABLE owner_outreach_dispatches "
                        "ADD COLUMN owner_state_at_dispatch TEXT NOT NULL DEFAULT 'unknown'"
                    )
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise

    def record_dispatch(
        self,
        *,
        bond_id: str,
        dispatched_utc: datetime,
        priority_class: str,
        owner_state_at_dispatch: OwnerState,
        signal_quality: SignalQuality,
        importance: float,
        decision: str,
    ) -> int:
        if not bond_id:
            raise ValueError("bond_id is required")
        when = _coerce_utc(dispatched_utc)
        with self._lock, self._conn() as con:
            cur = con.execute(
                """
                INSERT INTO owner_outreach_dispatches (
                    bond_id,
                    dispatched_utc,
                    priority_class,
                    owner_state_at_dispatch,
                    signal_quality,
                    importance,
                    decision
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bond_id,
                    when.isoformat(),
                    str(priority_class),
                    owner_state_at_dispatch.value,
                    signal_quality.value,
                    float(importance),
                    str(decision),
                ),
            )
            return int(cur.lastrowid)

    def allowed_count_since(self, *, bond_id: str, since_utc: datetime) -> int:
        since = _coerce_utc(since_utc).isoformat()
        with self._lock, self._conn() as con:
            return int(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM owner_outreach_dispatches
                    WHERE bond_id = ? AND dispatched_utc >= ? AND decision = 'allow'
                    """,
                    (bond_id, since),
                ).fetchone()[0]
            )

    def last_allowed_dispatch(self, *, bond_id: str) -> sqlite3.Row | None:
        with self._lock, self._conn() as con:
            return con.execute(
                """
                SELECT *
                FROM owner_outreach_dispatches
                WHERE bond_id = ? AND decision = 'allow'
                ORDER BY dispatched_utc DESC, id DESC
                LIMIT 1
                """,
                (bond_id,),
            ).fetchone()

    def dispatches_for_bond(self, bond_id: str) -> list[sqlite3.Row]:
        with self._lock, self._conn() as con:
            return con.execute(
                """
                SELECT *
                FROM owner_outreach_dispatches
                WHERE bond_id = ?
                ORDER BY dispatched_utc ASC, id ASC
                """,
                (bond_id,),
            ).fetchall()


def evaluate_signal_gate(
    *,
    bond_id: str,
    signals: Iterable[SignalObservation],
    priority_class: PriorityClass,
    importance: float,
    now_utc: datetime,
    ledger: OutreachLedger | None = None,
    preference_store: AutonomyPreferences | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> GateDecision:
    now = _coerce_utc(now_utc)
    ledger = ledger or OutreachLedger()
    policy = composed_policy(
        bond_id,
        PreferenceClass.LANE_CEILING,
        now_utc=now,
        store=preference_store,
    )
    observed = tuple(signals)
    signal_quality, owner_state = _interpret_signals(observed)
    consulted = frozenset(signal.name for signal in observed)
    can_override = (
        priority_class.override_budget
        and float(importance) >= float(policy.signal_unknown_override_threshold_importance)
    )

    if (
        signal_quality is SignalQuality.HIGH
        and owner_state is OwnerState.UNAVAILABLE
        and not can_override
    ):
        return _deny(
            bond_id=bond_id,
            reason="owner_unavailable",
            consulted_signals=consulted,
            signal_quality=signal_quality,
            owner_state=owner_state,
            diagnostic_sink=diagnostic_sink,
        )

    if signal_quality is SignalQuality.UNKNOWN:
        if not can_override:
            return _defer(
                bond_id=bond_id,
                reason="signal_quality_unknown",
                consulted_signals=consulted,
                signal_quality=signal_quality,
                owner_state=OwnerState.UNKNOWN,
                recheck_after_seconds=900,
                diagnostic_sink=diagnostic_sink,
            )

    if _inside_quiet_hours(now, policy.owner_interrupting_quiet_hours) and not priority_class.override_budget:
        return _defer(
            bond_id=bond_id,
            reason="quiet_hours",
            consulted_signals=consulted,
            signal_quality=signal_quality,
            owner_state=owner_state,
            recheck_after_seconds=1800,
            diagnostic_sink=diagnostic_sink,
        )

    last = ledger.last_allowed_dispatch(bond_id=bond_id)
    if last is not None and not priority_class.override_budget:
        last_utc = datetime.fromisoformat(str(last["dispatched_utc"]))
        elapsed_minutes = (now - last_utc).total_seconds() / 60.0
        if elapsed_minutes < float(policy.owner_interrupting_cooldown_minutes):
            return _deny(
                bond_id=bond_id,
                reason="cooldown_active",
                consulted_signals=consulted,
                signal_quality=signal_quality,
                owner_state=owner_state,
                diagnostic_sink=diagnostic_sink,
            )

    day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    if (
        ledger.allowed_count_since(bond_id=bond_id, since_utc=day_start)
        >= int(policy.owner_interrupting_daily_max_count)
        and not priority_class.override_budget
    ):
        return _deny(
            bond_id=bond_id,
            reason="daily_budget_exhausted",
            consulted_signals=consulted,
            signal_quality=signal_quality,
            owner_state=owner_state,
            diagnostic_sink=diagnostic_sink,
        )

    dispatch_state = owner_state
    event_id = ledger.record_dispatch(
        bond_id=bond_id,
        dispatched_utc=now,
        priority_class=priority_class.value,
        owner_state_at_dispatch=dispatch_state,
        signal_quality=signal_quality,
        importance=float(importance),
        decision="allow",
    )
    decision = GateDecision(
        bond_id=bond_id,
        decision="allow",
        reason="allowed",
        consulted_signals=consulted,
        signal_quality=signal_quality,
        owner_state=dispatch_state,
        recheck_after_seconds=None,
    )
    _emit_gate_decision(
        decision=decision,
        diagnostic_sink=diagnostic_sink,
        outreach_dispatch_id=event_id,
    )
    return decision


def _interpret_signals(signals: tuple[SignalObservation, ...]) -> tuple[SignalQuality, OwnerState]:
    if not signals:
        return SignalQuality.UNKNOWN, OwnerState.UNKNOWN
    high = [signal for signal in signals if signal.confidence >= 0.8]
    if high:
        if any(signal.owner_state is OwnerState.UNAVAILABLE for signal in high):
            return SignalQuality.HIGH, OwnerState.UNAVAILABLE
        if any(signal.owner_state is OwnerState.AVAILABLE for signal in high):
            return SignalQuality.HIGH, OwnerState.AVAILABLE
        return SignalQuality.HIGH, OwnerState.UNKNOWN
    return SignalQuality.LOW, OwnerState.UNKNOWN


def _deny(
    *,
    bond_id: str,
    reason: str,
    consulted_signals: frozenset[str],
    signal_quality: SignalQuality,
    owner_state: OwnerState,
    diagnostic_sink: DiagnosticSink | None,
) -> GateDecision:
    decision = GateDecision(
        bond_id=bond_id,
        decision="deny",
        reason=reason,
        consulted_signals=consulted_signals,
        signal_quality=signal_quality,
        owner_state=owner_state,
        recheck_after_seconds=None,
    )
    _emit_suppression(decision=decision, diagnostic_sink=diagnostic_sink)
    _emit_gate_decision(decision=decision, diagnostic_sink=diagnostic_sink)
    return decision


def _defer(
    *,
    bond_id: str,
    reason: str,
    consulted_signals: frozenset[str],
    signal_quality: SignalQuality,
    owner_state: OwnerState,
    recheck_after_seconds: int,
    diagnostic_sink: DiagnosticSink | None,
) -> GateDecision:
    decision = GateDecision(
        bond_id=bond_id,
        decision="defer",
        reason=reason,
        consulted_signals=consulted_signals,
        signal_quality=signal_quality,
        owner_state=owner_state,
        recheck_after_seconds=recheck_after_seconds,
    )
    _emit_suppression(decision=decision, diagnostic_sink=diagnostic_sink)
    _emit_gate_decision(decision=decision, diagnostic_sink=diagnostic_sink)
    return decision


def _emit_suppression(
    *,
    decision: GateDecision,
    diagnostic_sink: DiagnosticSink | None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "SUPPRESSION_EVENT",
            "suppression_kind": SuppressionKind.SIGNAL_GATED.value,
            "bond_id": decision.bond_id,
            "reason": decision.reason,
            "signal_quality": decision.signal_quality.value,
            "owner_state": decision.owner_state.value,
        }
    )


def _emit_gate_decision(
    *,
    decision: GateDecision,
    diagnostic_sink: DiagnosticSink | None,
    outreach_dispatch_id: int | None = None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "SIGNAL_GATE_DECISION",
            "bond_id": decision.bond_id,
            "decision": decision.decision,
            "reason": decision.reason,
            "signal_quality": decision.signal_quality.value,
            "owner_state": decision.owner_state.value,
            "consulted_signals": sorted(decision.consulted_signals),
            "outreach_dispatch_id": outreach_dispatch_id,
        }
    )


def _inside_quiet_hours(now_utc: datetime, quiet_hours: tuple[int, int]) -> bool:
    start_hour, end_hour = quiet_hours
    hour = now_utc.hour
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware UTC")
    coerced = value.astimezone(UTC)
    if value.utcoffset() != UTC.utcoffset(None):
        raise ValueError("datetime must be timezone-aware UTC")
    return coerced
