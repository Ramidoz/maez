from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from core import paths
from core.policies.autonomy_preferences import (
    AutonomyPreference,
    AutonomyPreferences,
    PreferenceClass,
    PreferenceExpressedBy,
)


DiagnosticSink = Callable[[dict], None]


class ProposalScopeClass(Enum):
    BEHAVIORAL_FIX = "behavioral_fix"
    RANKING_REFINEMENT = "ranking_refinement"
    PATTERN_SET_EXTENSION = "pattern_set_extension"
    DIAGNOSTIC_INSTRUMENTATION = "diagnostic_instrumentation"
    TEST_STABILIZATION = "test_stabilization"


class ProposalStatus(Enum):
    PROPOSED = "proposed"
    RATIFIED = "ratified"
    DECLINED = "declined"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_kind: str
    ref_digest: str
    observed_utc: datetime

    def __post_init__(self) -> None:
        if not self.evidence_kind:
            raise ValueError("evidence_kind is required")
        if not _is_digest(self.ref_digest):
            raise ValueError("ref_digest must be hmac-sha256")
        _coerce_utc(self.observed_utc, field_name="observed_utc")


@dataclass(frozen=True)
class SandboxWitness:
    red_tests_passed: bool
    focused_tests_passed: bool
    scratch_canary_passed: bool
    witness_digest: str

    def __post_init__(self) -> None:
        if not _is_digest(self.witness_digest):
            raise ValueError("witness_digest must be hmac-sha256")


@dataclass(frozen=True)
class MaintenanceProposal:
    proposal_id: str
    bond_id: str
    emitted_utc: datetime
    scope_class: ProposalScopeClass
    diagnosis_digest: str
    proposed_patch_ref: str
    predicted_effect: str
    sandbox_witness: SandboxWitness | None
    evidence_refs: tuple[EvidenceRef, ...]
    status: ProposalStatus
    ratified_utc: datetime | None
    decline_reason_digest: str | None

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if not self.bond_id:
            raise ValueError("bond_id is required")
        _coerce_utc(self.emitted_utc, field_name="emitted_utc")
        if self.ratified_utc is not None:
            _coerce_utc(self.ratified_utc, field_name="ratified_utc")
        if not isinstance(self.scope_class, ProposalScopeClass):
            raise ValueError("scope_class must be ProposalScopeClass")
        if not isinstance(self.status, ProposalStatus):
            raise ValueError("status must be ProposalStatus")
        if not _is_digest(self.diagnosis_digest):
            raise ValueError("diagnosis_digest must be hmac-sha256")
        if self.decline_reason_digest is not None and not _is_digest(
            self.decline_reason_digest
        ):
            raise ValueError("decline_reason_digest must be hmac-sha256")
        if not self.proposed_patch_ref:
            raise ValueError("proposed_patch_ref is required")
        if not self.predicted_effect:
            raise ValueError("predicted_effect is required")
        if not self.evidence_refs:
            raise ValueError("evidence_refs are required")


class MaintenanceProposals:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.maintenance_proposals_db()
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
                CREATE TABLE IF NOT EXISTS maintenance_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    bond_id TEXT NOT NULL,
                    emitted_utc TEXT NOT NULL,
                    scope_class TEXT NOT NULL,
                    diagnosis_digest TEXT NOT NULL,
                    proposed_patch_ref TEXT NOT NULL,
                    predicted_effect TEXT NOT NULL,
                    sandbox_witness_json TEXT,
                    evidence_refs_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    ratified_utc TEXT,
                    decline_reason_digest TEXT
                )
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_maintenance_proposals_bond_status
                ON maintenance_proposals (bond_id, status, emitted_utc)
                """
            )

    def append(self, proposal: MaintenanceProposal) -> None:
        _validate_proposal(proposal)
        with self._lock, self._conn() as con:
            con.execute(
                """
                INSERT INTO maintenance_proposals (
                    proposal_id,
                    bond_id,
                    emitted_utc,
                    scope_class,
                    diagnosis_digest,
                    proposed_patch_ref,
                    predicted_effect,
                    sandbox_witness_json,
                    evidence_refs_json,
                    status,
                    ratified_utc,
                    decline_reason_digest
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _proposal_values(proposal),
            )

    def get(self, bond_id: str, proposal_id: str) -> MaintenanceProposal:
        if not bond_id:
            raise ValueError("bond_id is required")
        with self._lock, self._conn() as con:
            row = con.execute(
                """
                SELECT *
                FROM maintenance_proposals
                WHERE bond_id = ? AND proposal_id = ?
                """,
                (bond_id, proposal_id),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return _row_to_proposal(row)

    def proposals_for_bond(self, bond_id: str) -> list[MaintenanceProposal]:
        if not bond_id:
            raise ValueError("bond_id is required")
        with self._lock, self._conn() as con:
            rows = con.execute(
                """
                SELECT *
                FROM maintenance_proposals
                WHERE bond_id = ?
                ORDER BY emitted_utc ASC, proposal_id ASC
                """,
                (bond_id,),
            ).fetchall()
        return [_row_to_proposal(row) for row in rows]

    def update(self, proposal: MaintenanceProposal) -> None:
        _validate_proposal(proposal)
        with self._lock, self._conn() as con:
            cur = con.execute(
                """
                UPDATE maintenance_proposals
                SET status = ?,
                    ratified_utc = ?,
                    decline_reason_digest = ?,
                    sandbox_witness_json = ?
                WHERE bond_id = ? AND proposal_id = ?
                """,
                (
                    proposal.status.value,
                    proposal.ratified_utc.isoformat()
                    if proposal.ratified_utc is not None
                    else None,
                    proposal.decline_reason_digest,
                    _sandbox_to_json(proposal.sandbox_witness),
                    proposal.bond_id,
                    proposal.proposal_id,
                ),
            )
            if cur.rowcount != 1:
                raise KeyError(proposal.proposal_id)


def emit_maintenance_proposal(
    proposal: MaintenanceProposal,
    *,
    store: MaintenanceProposals | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> MaintenanceProposal:
    active_store = store or MaintenanceProposals()
    active_store.append(proposal)
    _emit(
        diagnostic_sink,
        event_type="MAINTENANCE_PROPOSAL_EMITTED",
        proposal=proposal,
    )
    return proposal


def ratify_maintenance_proposal(
    *,
    bond_id: str,
    proposal_id: str,
    ratified_utc: datetime,
    store: MaintenanceProposals | None = None,
    preference_store: AutonomyPreferences | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> MaintenanceProposal:
    active_store = store or MaintenanceProposals()
    proposal = active_store.get(bond_id, proposal_id)
    ratified = replace(
        proposal,
        status=ProposalStatus.RATIFIED,
        ratified_utc=_coerce_utc(ratified_utc, field_name="ratified_utc"),
        decline_reason_digest=None,
    )
    active_preferences = preference_store or AutonomyPreferences()
    active_preferences.append(_ratification_preference(ratified))
    active_store.update(ratified)
    _emit(
        diagnostic_sink,
        event_type="MAINTENANCE_PROPOSAL_RATIFIED",
        proposal=ratified,
    )
    return ratified


def decline_maintenance_proposal(
    *,
    bond_id: str,
    proposal_id: str,
    declined_utc: datetime,
    decline_reason_digest: str,
    store: MaintenanceProposals | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
) -> MaintenanceProposal:
    _coerce_utc(declined_utc, field_name="declined_utc")
    if not _is_digest(decline_reason_digest):
        raise ValueError("decline_reason_digest must be hmac-sha256")
    active_store = store or MaintenanceProposals()
    proposal = active_store.get(bond_id, proposal_id)
    declined = replace(
        proposal,
        status=ProposalStatus.DECLINED,
        ratified_utc=None,
        decline_reason_digest=decline_reason_digest,
    )
    active_store.update(declined)
    _emit(
        diagnostic_sink,
        event_type="MAINTENANCE_PROPOSAL_DECLINED",
        proposal=declined,
    )
    return declined


def _ratification_preference(proposal: MaintenanceProposal) -> AutonomyPreference:
    if proposal.ratified_utc is None:
        raise ValueError("ratified proposal requires ratified_utc")
    return AutonomyPreference(
        preference_id=f"maintenance-ratification:{proposal.proposal_id}",
        bond_id=proposal.bond_id,
        recorded_utc=proposal.ratified_utc,
        preference_class=PreferenceClass.MAINTENANCE_RATIFICATION,
        pattern_digest=proposal.diagnosis_digest,
        weight=1.0,
        expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT,
        relevance_decay_half_life_days=365.0,
        notes_digest=None,
        target_field="maintenance_proposal_ratified",
        encoded_modifier=1.0,
    )


def _emit(
    diagnostic_sink: DiagnosticSink | None,
    *,
    event_type: str,
    proposal: MaintenanceProposal,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": event_type,
            "bond_id": proposal.bond_id,
            "proposal_id": proposal.proposal_id,
            "proposal_scope_class": proposal.scope_class.value,
            "scope_class": proposal.scope_class.value,
            "proposal_status": proposal.status.value,
        }
    )


def _validate_proposal(proposal: MaintenanceProposal) -> None:
    proposal.__post_init__()


def _proposal_values(proposal: MaintenanceProposal) -> tuple:
    return (
        proposal.proposal_id,
        proposal.bond_id,
        proposal.emitted_utc.isoformat(),
        proposal.scope_class.value,
        proposal.diagnosis_digest,
        proposal.proposed_patch_ref,
        proposal.predicted_effect,
        _sandbox_to_json(proposal.sandbox_witness),
        json.dumps([_evidence_to_dict(ref) for ref in proposal.evidence_refs]),
        proposal.status.value,
        proposal.ratified_utc.isoformat() if proposal.ratified_utc else None,
        proposal.decline_reason_digest,
    )


def _sandbox_to_json(witness: SandboxWitness | None) -> str | None:
    if witness is None:
        return None
    return json.dumps(
        {
            "red_tests_passed": witness.red_tests_passed,
            "focused_tests_passed": witness.focused_tests_passed,
            "scratch_canary_passed": witness.scratch_canary_passed,
            "witness_digest": witness.witness_digest,
        },
        sort_keys=True,
    )


def _sandbox_from_json(raw: str | None) -> SandboxWitness | None:
    if raw is None:
        return None
    data = json.loads(raw)
    return SandboxWitness(
        red_tests_passed=bool(data["red_tests_passed"]),
        focused_tests_passed=bool(data["focused_tests_passed"]),
        scratch_canary_passed=bool(data["scratch_canary_passed"]),
        witness_digest=str(data["witness_digest"]),
    )


def _evidence_to_dict(ref: EvidenceRef) -> dict:
    return {
        "evidence_kind": ref.evidence_kind,
        "ref_digest": ref.ref_digest,
        "observed_utc": ref.observed_utc.isoformat(),
    }


def _evidence_from_dict(data: dict) -> EvidenceRef:
    return EvidenceRef(
        evidence_kind=str(data["evidence_kind"]),
        ref_digest=str(data["ref_digest"]),
        observed_utc=datetime.fromisoformat(str(data["observed_utc"])),
    )


def _row_to_proposal(row: sqlite3.Row) -> MaintenanceProposal:
    return MaintenanceProposal(
        proposal_id=str(row["proposal_id"]),
        bond_id=str(row["bond_id"]),
        emitted_utc=datetime.fromisoformat(str(row["emitted_utc"])),
        scope_class=ProposalScopeClass(str(row["scope_class"])),
        diagnosis_digest=str(row["diagnosis_digest"]),
        proposed_patch_ref=str(row["proposed_patch_ref"]),
        predicted_effect=str(row["predicted_effect"]),
        sandbox_witness=_sandbox_from_json(row["sandbox_witness_json"]),
        evidence_refs=tuple(
            _evidence_from_dict(item)
            for item in json.loads(str(row["evidence_refs_json"]))
        ),
        status=ProposalStatus(str(row["status"])),
        ratified_utc=datetime.fromisoformat(str(row["ratified_utc"]))
        if row["ratified_utc"]
        else None,
        decline_reason_digest=row["decline_reason_digest"],
    )


def _is_digest(value: str) -> bool:
    prefix = "hmac-sha256:"
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    digest = value.removeprefix(prefix)
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _coerce_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value.astimezone(UTC)
