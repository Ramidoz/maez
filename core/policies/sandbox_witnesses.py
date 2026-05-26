from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path

from core import paths


class SandboxWitnessKind(Enum):
    WORKTREE_RED_TEST = "worktree_red_test"
    WORKTREE_SCHEMA_DIFF = "worktree_schema_diff"
    SCRATCH_DB_TRANSFORM = "scratch_db_transform"
    DRY_RUN_OBSERVATION = "dry_run_observation"


class WitnessStatus(Enum):
    WITNESSED = "witnessed"
    UNWITNESSED_BY_POLICY = "unwitnessed_by_policy"
    UNWITNESSED_BY_OMISSION = "unwitnessed_by_omission"


class WitnessRefusalReason(Enum):
    CALLER_SUPPLIED_DIGEST = "caller_supplied_digest"
    ISOLATION_REFERENCE_INVALID = "isolation_reference_invalid"
    RED_TEST_REASON_MISSING = "red_test_reason_missing"
    PREDICTED_OBSERVED_UNBOUND = "predicted_observed_unbound"
    WITNESS_STALE = "witness_stale"
    INBOUND_TAINT_UNCLEARED = "inbound_taint_uncleared"
    SELF_RATIFICATION_DETECTED = "self_ratification_detected"
    LIVE_SUBSTRATE_MUTATION_DETECTED = "live_substrate_mutation_detected"
    WITNESS_KIND_NOT_YET_VOCABULARY = "witness_kind_not_yet_vocabulary"
    LEGACY_WITNESS_SHAPE_REFUSED = "legacy_witness_shape_refused"


class StalenessAnchorKind(Enum):
    COMMIT_HASH = "commit_hash"
    FILE_HASH_SET = "file_hash_set"
    DB_CURSOR = "db_cursor"
    DIAGNOSTIC_CURSOR = "diagnostic_cursor"


class WitnessRefused(ValueError):
    def __init__(self, reason: WitnessRefusalReason, message: str):
        self.reason = reason
        super().__init__(message)


@dataclass(frozen=True)
class StalenessAnchor:
    anchor_kind: StalenessAnchorKind
    anchor_name: str
    anchor_value: str

    def __post_init__(self) -> None:
        if not isinstance(self.anchor_kind, StalenessAnchorKind):
            raise ValueError("anchor_kind must be StalenessAnchorKind")
        if not _is_anchor_text(self.anchor_name):
            raise ValueError("anchor_name is required")
        if not self.anchor_value:
            raise ValueError("anchor_value is required")


@dataclass(frozen=True)
class WitnessArtifactBundle:
    witness_kind: SandboxWitnessKind
    artifacts: dict
    predicted_effect_digest: str
    captured_utc: datetime
    staleness_anchors: tuple[StalenessAnchor, ...] = ()
    narrative_fields: tuple[str, ...] = ()
    external_llm_tainted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.witness_kind, SandboxWitnessKind):
            raise ValueError("witness_kind must be SandboxWitnessKind")
        if not isinstance(self.artifacts, dict) or not self.artifacts:
            raise ValueError("artifacts are required")
        if not _is_digest(self.predicted_effect_digest):
            raise ValueError("predicted_effect_digest must be hmac-sha256")
        for anchor in self.staleness_anchors:
            anchor.__post_init__()
        for narrative in self.narrative_fields:
            if not isinstance(narrative, str):
                raise ValueError("narrative_fields must be strings")
        _coerce_utc(self.captured_utc, field_name="captured_utc")


@dataclass(frozen=True)
class SandboxWitnessRecord:
    witness_id: str
    generation: int
    bond_id: str
    proposal_id: str
    witness_kind: SandboxWitnessKind
    witness_status: WitnessStatus
    observed_effect_digest: str
    predicted_effect_digest: str
    artifact_digest: str
    captured_utc: datetime
    staleness_anchors: tuple[StalenessAnchor, ...] = ()
    refusal_reason: WitnessRefusalReason | None = None

    @classmethod
    def new(
        cls,
        *,
        bond_id: str,
        proposal_id: str,
        witness_kind: SandboxWitnessKind,
        observed_effect_digest: str,
        predicted_effect_digest: str,
        artifact_digest: str,
        captured_utc: datetime,
        staleness_anchors: tuple[StalenessAnchor, ...] = (),
    ) -> "SandboxWitnessRecord":
        return cls(
            witness_id="",
            generation=0,
            bond_id=bond_id,
            proposal_id=proposal_id,
            witness_kind=witness_kind,
            witness_status=WitnessStatus.WITNESSED,
            observed_effect_digest=observed_effect_digest,
            predicted_effect_digest=predicted_effect_digest,
            artifact_digest=artifact_digest,
            captured_utc=captured_utc,
            staleness_anchors=staleness_anchors,
            refusal_reason=None,
        )

    def __post_init__(self) -> None:
        if self.witness_id and not _is_slug(self.witness_id):
            raise ValueError("witness_id must be a lowercase opaque id")
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        if not self.bond_id:
            raise ValueError("bond_id is required")
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if not isinstance(self.witness_kind, SandboxWitnessKind):
            raise ValueError("witness_kind must be SandboxWitnessKind")
        if not isinstance(self.witness_status, WitnessStatus):
            raise ValueError("witness_status must be WitnessStatus")
        if self.refusal_reason is not None and not isinstance(
            self.refusal_reason,
            WitnessRefusalReason,
        ):
            raise ValueError("refusal_reason must be WitnessRefusalReason")
        for field_name in (
            "observed_effect_digest",
            "predicted_effect_digest",
            "artifact_digest",
        ):
            if not _is_digest(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be hmac-sha256")
        for anchor in self.staleness_anchors:
            anchor.__post_init__()
        _coerce_utc(self.captured_utc, field_name="captured_utc")


class SandboxWitnesses:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.sandbox_witnesses_db()
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
                CREATE TABLE IF NOT EXISTS sandbox_witnesses (
                    witness_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL,
                    bond_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    witness_kind TEXT NOT NULL,
                    witness_status TEXT NOT NULL,
                    observed_effect_digest TEXT NOT NULL,
                    predicted_effect_digest TEXT NOT NULL,
                    artifact_digest TEXT NOT NULL,
                    captured_utc TEXT NOT NULL,
                    staleness_anchors_json TEXT NOT NULL DEFAULT '[]',
                    refusal_reason TEXT,
                    created_utc TEXT NOT NULL,
                    UNIQUE (bond_id, proposal_id, generation)
                )
                """
            )
            columns = {
                row[1]
                for row in con.execute("PRAGMA table_info(sandbox_witnesses)").fetchall()
            }
            if "staleness_anchors_json" not in columns:
                con.execute(
                    """
                    ALTER TABLE sandbox_witnesses
                    ADD COLUMN staleness_anchors_json TEXT NOT NULL DEFAULT '[]'
                    """
                )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sandbox_witnesses_family
                ON sandbox_witnesses (bond_id, proposal_id, generation)
                """
            )

    def append(self, witness: SandboxWitnessRecord) -> SandboxWitnessRecord:
        witness.__post_init__()
        with self._lock, self._conn() as con:
            next_generation = (
                con.execute(
                    """
                    SELECT COALESCE(MAX(generation), 0) + 1
                    FROM sandbox_witnesses
                    WHERE bond_id = ? AND proposal_id = ?
                    """,
                    (witness.bond_id, witness.proposal_id),
                ).fetchone()[0]
            )
            stored = replace(
                witness,
                witness_id=witness.witness_id or f"witness-{uuid.uuid4().hex}",
                generation=int(next_generation),
            )
            con.execute(
                """
                INSERT INTO sandbox_witnesses (
                    witness_id,
                    generation,
                    bond_id,
                    proposal_id,
                    witness_kind,
                    witness_status,
                    observed_effect_digest,
                    predicted_effect_digest,
                    artifact_digest,
                    captured_utc,
                    staleness_anchors_json,
                    refusal_reason,
                    created_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _record_values(stored),
            )
        return stored

    def current_for_proposal(
        self,
        bond_id: str,
        proposal_id: str,
    ) -> SandboxWitnessRecord | None:
        if not bond_id:
            raise ValueError("bond_id is required")
        if not proposal_id:
            raise ValueError("proposal_id is required")
        with self._lock, self._conn() as con:
            row = con.execute(
                """
                SELECT *
                FROM sandbox_witnesses
                WHERE bond_id = ? AND proposal_id = ?
                ORDER BY generation DESC
                LIMIT 1
                """,
                (bond_id, proposal_id),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def family_for_proposal(
        self,
        bond_id: str,
        proposal_id: str,
    ) -> list[SandboxWitnessRecord]:
        if not bond_id:
            raise ValueError("bond_id is required")
        if not proposal_id:
            raise ValueError("proposal_id is required")
        with self._lock, self._conn() as con:
            rows = con.execute(
                """
                SELECT *
                FROM sandbox_witnesses
                WHERE bond_id = ? AND proposal_id = ?
                ORDER BY generation ASC
                """,
                (bond_id, proposal_id),
            ).fetchall()
        return [_row_to_record(row) for row in rows]


def construct_witness_record(
    *,
    bond_id: str,
    proposal_id: str,
    bundle: WitnessArtifactBundle,
    observed_effect_digest: str | None = None,
) -> SandboxWitnessRecord:
    bundle.__post_init__()
    if observed_effect_digest is not None:
        raise WitnessRefused(
            WitnessRefusalReason.CALLER_SUPPLIED_DIGEST,
            "observed_effect_digest must be substrate-computed from artifacts",
        )
    _refuse_tainted_narrative(bundle)
    artifact_digest = _digest_json(bundle.artifacts)
    observed_digest = _observed_effect_digest(bundle.witness_kind, bundle.artifacts)
    return SandboxWitnessRecord.new(
        bond_id=bond_id,
        proposal_id=proposal_id,
        witness_kind=bundle.witness_kind,
        observed_effect_digest=observed_digest,
        predicted_effect_digest=bundle.predicted_effect_digest,
        artifact_digest=artifact_digest,
        captured_utc=bundle.captured_utc,
        staleness_anchors=bundle.staleness_anchors,
    )


def _refuse_tainted_narrative(bundle: WitnessArtifactBundle) -> None:
    if not bundle.external_llm_tainted:
        return
    try:
        from core.safety.injection_patterns import scan
    except Exception as exc:
        raise WitnessRefused(
            WitnessRefusalReason.INBOUND_TAINT_UNCLEARED,
            "injection pattern scanner unavailable for tainted witness narrative",
        ) from exc
    for narrative in bundle.narrative_fields:
        if scan(narrative):
            raise WitnessRefused(
                WitnessRefusalReason.INBOUND_TAINT_UNCLEARED,
                "external-LLM-tainted witness narrative matched injection patterns",
            )


def _record_values(record: SandboxWitnessRecord) -> tuple:
    return (
        record.witness_id,
        record.generation,
        record.bond_id,
        record.proposal_id,
        record.witness_kind.value,
        record.witness_status.value,
        record.observed_effect_digest,
        record.predicted_effect_digest,
        record.artifact_digest,
        record.captured_utc.isoformat(),
        _anchors_to_json(record.staleness_anchors),
        record.refusal_reason.value if record.refusal_reason else None,
        datetime.now(UTC).isoformat(),
    )


def _row_to_record(row: sqlite3.Row) -> SandboxWitnessRecord:
    return SandboxWitnessRecord(
        witness_id=str(row["witness_id"]),
        generation=int(row["generation"]),
        bond_id=str(row["bond_id"]),
        proposal_id=str(row["proposal_id"]),
        witness_kind=SandboxWitnessKind(str(row["witness_kind"])),
        witness_status=WitnessStatus(str(row["witness_status"])),
        observed_effect_digest=str(row["observed_effect_digest"]),
        predicted_effect_digest=str(row["predicted_effect_digest"]),
        artifact_digest=str(row["artifact_digest"]),
        captured_utc=datetime.fromisoformat(str(row["captured_utc"])),
        staleness_anchors=_anchors_from_json(str(row["staleness_anchors_json"])),
        refusal_reason=WitnessRefusalReason(str(row["refusal_reason"]))
        if row["refusal_reason"]
        else None,
    )


def _anchors_to_json(anchors: tuple[StalenessAnchor, ...]) -> str:
    return json.dumps(
        [
            {
                "anchor_kind": anchor.anchor_kind.value,
                "anchor_name": anchor.anchor_name,
                "anchor_value": anchor.anchor_value,
            }
            for anchor in sorted(
                anchors,
                key=lambda item: (item.anchor_kind.value, item.anchor_name, item.anchor_value),
            )
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _anchors_from_json(raw: str) -> tuple[StalenessAnchor, ...]:
    data = json.loads(raw or "[]")
    return tuple(
        StalenessAnchor(
            anchor_kind=StalenessAnchorKind(str(item["anchor_kind"])),
            anchor_name=str(item["anchor_name"]),
            anchor_value=str(item["anchor_value"]),
        )
        for item in data
    )


def _observed_effect_digest(kind: SandboxWitnessKind, artifacts: dict) -> str:
    if kind is SandboxWitnessKind.WORKTREE_RED_TEST:
        return _digest_json(
            {
                "kind": kind.value,
                "command_argv": _required(artifacts, "command_argv"),
                "runner_version": artifacts.get("runner_version", ""),
                "source_hashes": artifacts.get("source_hashes", {}),
                "test_results": sorted(
                    (
                        _test_result_projection(item)
                        for item in _required(artifacts, "test_results")
                    ),
                    key=lambda item: item["test_id"],
                ),
            }
        )
    if kind is SandboxWitnessKind.WORKTREE_SCHEMA_DIFF:
        return _digest_json(
            {
                "kind": kind.value,
                "schema_objects": sorted(
                    _required(artifacts, "schema_objects"),
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            }
        )
    if kind is SandboxWitnessKind.SCRATCH_DB_TRANSFORM:
        return _digest_json(
            {
                "kind": kind.value,
                "rows": sorted(
                    _required(artifacts, "rows"),
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            }
        )
    if kind is SandboxWitnessKind.DRY_RUN_OBSERVATION:
        return _digest_json(
            {
                "kind": kind.value,
                "observations": sorted(
                    _required(artifacts, "observations"),
                    key=lambda item: json.dumps(
                        item,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            }
        )
    raise WitnessRefused(
        WitnessRefusalReason.WITNESS_KIND_NOT_YET_VOCABULARY,
        f"unsupported witness kind: {kind!r}",
    )


def _test_result_projection(item: dict) -> dict:
    required = {
        "test_id": str(item["test_id"]),
        "verdict": str(item["verdict"]),
        "assertion_reason_digest": str(item["assertion_reason_digest"]),
        "failure_class": str(item.get("failure_class", "")),
        "normalized_failure_location": str(item.get("normalized_failure_location", "")),
    }
    if not _is_digest(required["assertion_reason_digest"]):
        raise WitnessRefused(
            WitnessRefusalReason.RED_TEST_REASON_MISSING,
            "test result lacks AST-derived assertion_reason_digest",
        )
    return required


def _required(artifacts: dict, key: str):
    value = artifacts.get(key)
    if value in (None, "", [], {}):
        raise WitnessRefused(
            WitnessRefusalReason.PREDICTED_OBSERVED_UNBOUND,
            f"artifact key required for deterministic observed effect: {key}",
        )
    return value


def _digest_json(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "hmac-sha256:" + sha256(raw).hexdigest()


def _is_digest(value: str) -> bool:
    prefix = "hmac-sha256:"
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    digest = value.removeprefix(prefix)
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _is_slug(value: str) -> bool:
    return 1 <= len(value) <= 96 and all(
        char in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in value
    )


def _is_anchor_text(value: str) -> bool:
    return 1 <= len(value) <= 256 and all(
        char
        in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:./"
        for char in value
    )


def _coerce_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value.astimezone(UTC)
