from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from core import paths
from core.policies.signal_gate import GateDecision, OwnerState, PriorityClass, SignalQuality


class ReflectionDecision(Enum):
    PROCEED = "proceed"
    DEFER_CONTEXT_NOT_RIPE = "defer_context_not_ripe"
    DEFER_EXTRACTION_SHAPE = "defer_extraction_shape"
    ABANDON = "abandon"


class OwnerResponse(Enum):
    NO_RESPONSE = "no_response"
    ACKNOWLEDGED = "acknowledged"
    CORRECTED = "corrected"
    INVITED_MORE = "invited_more"
    DEFERRED = "deferred"
    DECLINED_WITHOUT_TEACHING = "declined_without_teaching"


@dataclass(frozen=True)
class ReflectionInputs:
    object_id: str
    bond_id: str
    priority_class: PriorityClass
    salience: float
    can_resolve_interiorly_candidate: bool
    is_worth_interrupting: bool
    is_extraction_shaped: bool
    reasoning_digest: str
    owner_response: OwnerResponse | None = None


@dataclass(frozen=True)
class ReflectionAudit:
    object_id: str
    bond_id: str
    reflection_utc: datetime
    can_resolve_interiorly: bool
    is_owner_likely_available: bool
    is_worth_interrupting: bool
    is_extraction_shaped: bool
    decision: ReflectionDecision
    reasoning_digest: str
    owner_response: OwnerResponse | None


DiagnosticSink = Callable[[dict], None]


class ReflectionAuditLedger:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.reflection_audit_db()
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
            con.execute("PRAGMA foreign_keys = ON")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS reflection_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_id TEXT NOT NULL,
                    bond_id TEXT NOT NULL,
                    reflection_utc TEXT NOT NULL,
                    can_resolve_interiorly INTEGER NOT NULL,
                    is_owner_likely_available INTEGER NOT NULL,
                    is_worth_interrupting INTEGER NOT NULL,
                    is_extraction_shaped INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    reasoning_digest TEXT NOT NULL,
                    owner_response TEXT
                )
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reflection_audits_bond_time
                ON reflection_audits (bond_id, reflection_utc)
                """
            )
            existing_cols = {
                row[1]
                for row in con.execute("PRAGMA table_info(reflection_audits)").fetchall()
            }
            for column_name, column_sql in (
                ("owner_response", "owner_response TEXT"),
                ("is_extraction_shaped", "is_extraction_shaped INTEGER NOT NULL DEFAULT 0"),
            ):
                if column_name in existing_cols:
                    continue
                try:
                    con.execute(f"ALTER TABLE reflection_audits ADD COLUMN {column_sql}")
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise

    def append(self, audit: ReflectionAudit) -> int:
        _validate_audit(audit)
        with self._lock, self._conn() as con:
            cur = con.execute(
                """
                INSERT INTO reflection_audits (
                    object_id,
                    bond_id,
                    reflection_utc,
                    can_resolve_interiorly,
                    is_owner_likely_available,
                    is_worth_interrupting,
                    is_extraction_shaped,
                    decision,
                    reasoning_digest,
                    owner_response
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.object_id,
                    audit.bond_id,
                    audit.reflection_utc.isoformat(),
                    int(audit.can_resolve_interiorly),
                    int(audit.is_owner_likely_available),
                    int(audit.is_worth_interrupting),
                    int(audit.is_extraction_shaped),
                    audit.decision.value,
                    audit.reasoning_digest,
                    None if audit.owner_response is None else audit.owner_response.value,
                ),
            )
            return int(cur.lastrowid)

    def audits_for_bond(self, bond_id: str) -> list[sqlite3.Row]:
        if not bond_id:
            raise ValueError("bond_id is required")
        with self._lock, self._conn() as con:
            return con.execute(
                """
                SELECT *
                FROM reflection_audits
                WHERE bond_id = ?
                ORDER BY reflection_utc ASC, id ASC
                """,
                (bond_id,),
            ).fetchall()


def run_reflection_audit(
    *,
    inputs: ReflectionInputs,
    gate_decision: GateDecision,
    reflection_utc: datetime,
    ledger: ReflectionAuditLedger | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> ReflectionAudit:
    when = _coerce_utc(reflection_utc, field_name="reflection_utc")
    _validate_inputs(inputs)
    _validate_gate_decision(gate_decision)
    if inputs.bond_id != gate_decision.bond_id:
        raise ValueError("gate decision bond_id does not match reflection input bond_id")
    can_resolve_interiorly = (
        False
        if inputs.priority_class is PriorityClass.OWNER_BOND
        else bool(inputs.can_resolve_interiorly_candidate)
    )
    gate_allowed = gate_decision.decision == "allow"
    is_owner_likely_available = gate_allowed and gate_decision.owner_state is OwnerState.AVAILABLE
    decision = _decide(
        gate_allowed=gate_allowed,
        can_resolve_interiorly=can_resolve_interiorly,
        is_owner_likely_available=is_owner_likely_available,
        is_worth_interrupting=inputs.is_worth_interrupting,
        is_extraction_shaped=inputs.is_extraction_shaped,
    )
    audit = ReflectionAudit(
        object_id=inputs.object_id,
        bond_id=inputs.bond_id,
        reflection_utc=when,
        can_resolve_interiorly=can_resolve_interiorly,
        is_owner_likely_available=is_owner_likely_available,
        is_worth_interrupting=inputs.is_worth_interrupting,
        is_extraction_shaped=inputs.is_extraction_shaped,
        decision=decision,
        reasoning_digest=inputs.reasoning_digest,
        owner_response=inputs.owner_response,
    )
    active_ledger = ledger or ReflectionAuditLedger()
    audit_id = active_ledger.append(audit)
    if decision is not ReflectionDecision.PROCEED:
        _emit_suppression(audit=audit, diagnostic_sink=diagnostic_sink)
    _emit_audit(audit=audit, audit_id=audit_id, diagnostic_sink=diagnostic_sink)
    return audit


def _decide(
    *,
    gate_allowed: bool,
    can_resolve_interiorly: bool,
    is_owner_likely_available: bool,
    is_worth_interrupting: bool,
    is_extraction_shaped: bool,
) -> ReflectionDecision:
    if not gate_allowed:
        return ReflectionDecision.DEFER_CONTEXT_NOT_RIPE
    if can_resolve_interiorly:
        return ReflectionDecision.ABANDON
    if is_extraction_shaped:
        return ReflectionDecision.DEFER_EXTRACTION_SHAPE
    if not is_owner_likely_available or not is_worth_interrupting:
        return ReflectionDecision.DEFER_CONTEXT_NOT_RIPE
    return ReflectionDecision.PROCEED


def _emit_suppression(*, audit: ReflectionAudit, diagnostic_sink: DiagnosticSink | None) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "SUPPRESSION_EVENT",
            "suppression_kind": "REFLECTION_DEFERRED",
            "bond_id": audit.bond_id,
            "object_id": audit.object_id,
            "reason": audit.decision.value,
        }
    )


def _emit_audit(
    *,
    audit: ReflectionAudit,
    audit_id: int,
    diagnostic_sink: DiagnosticSink | None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "REFLECTION_AUDIT",
            "audit_id": audit_id,
            "bond_id": audit.bond_id,
            "object_id": audit.object_id,
            "decision": audit.decision.value,
            "can_resolve_interiorly": audit.can_resolve_interiorly,
            "is_owner_likely_available": audit.is_owner_likely_available,
            "is_worth_interrupting": audit.is_worth_interrupting,
            "is_extraction_shaped": audit.is_extraction_shaped,
        }
    )


def _validate_inputs(inputs: ReflectionInputs) -> None:
    if not inputs.object_id:
        raise ValueError("object_id is required")
    if not inputs.bond_id:
        raise ValueError("bond_id is required")
    if not isinstance(inputs.priority_class, PriorityClass):
        raise ValueError("priority_class must be PriorityClass")
    if inputs.owner_response is not None and not isinstance(inputs.owner_response, OwnerResponse):
        raise ValueError("owner_response must be OwnerResponse")
    if not _is_digest(inputs.reasoning_digest):
        raise ValueError("reasoning_digest must be hmac-sha256")


def _validate_gate_decision(gate_decision: GateDecision) -> None:
    if gate_decision.decision not in {"allow", "deny", "defer"}:
        raise ValueError("gate_decision.decision must be allow, deny, or defer")
    if not isinstance(gate_decision.owner_state, OwnerState):
        raise ValueError("gate_decision.owner_state must be OwnerState")
    if not isinstance(gate_decision.signal_quality, SignalQuality):
        raise ValueError("gate_decision.signal_quality must be SignalQuality")


def _validate_audit(audit: ReflectionAudit) -> None:
    if not audit.object_id:
        raise ValueError("object_id is required")
    if not audit.bond_id:
        raise ValueError("bond_id is required")
    _coerce_utc(audit.reflection_utc, field_name="reflection_utc")
    if not _is_digest(audit.reasoning_digest):
        raise ValueError("reasoning_digest must be hmac-sha256")


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
