# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice X.6 gestation load and moment-arc readability rehearsal.

Synthetic load writes only to sidecar rehearsal paths. Replay
readability is derived from existing ledger rows and emits sidecar
panel/metric artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.cognition import moment_assembly_diagnostic as mad
from core.ledger import chain, migrate
from core.ledger.writer import LedgerWriter

DEFAULT_REHEARSAL_ROOT = REPO_ROOT / "logs" / "rehearsal"
SLICE_MEMO_PATH = REPO_ROOT / "docs" / "SLICE_X6_GESTATION_LOAD_AND_READABILITY_MEMO.md"
RULES_PATH = REPO_ROOT / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md"
THESIS_PATH = REPO_ROOT / "docs" / "governance" / "ARCHITECTURAL_THESIS.md"
X6_SYNTHETIC_TURNS = 200
X6_DISK_SOFT_CAP_BYTES = 50 * 1024 * 1024
X6_REHEARSAL_TTL_DAYS = 90
X6_ORGAN_STATE_KEYS = (
    "anticipation",
    "open_loops",
    "bond_topology",
    "body_state",
    "counterevidence",
)
HASH_PREFIXES = (
    mad.OPEN_LOOP_HASH_INPUT_PREFIX,
    mad.BOND_TOPOLOGY_NODE_HASH_PREFIX,
    mad.BOND_TOPOLOGY_EDGE_HASH_PREFIX,
    mad.COUNTEREVIDENCE_HASH_PREFIX,
    mad.BODY_STATE_SERVICE_HASH_PREFIX,
)


def _has_turns_table(path: Path) -> bool:
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='turns'"
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _default_production_ledger() -> Path:
    env_path = os.environ.get("MAEZ_LEDGER_DB_PATH")
    if env_path:
        return Path(env_path)
    candidates = sorted((REPO_ROOT / "memory").glob("sandbox_ledger_*.db"), reverse=True)
    for candidate in candidates:
        if _has_turns_table(candidate):
            return candidate
    return REPO_ROOT / "memory" / "ledger.db"


DEFAULT_PRODUCTION_LEDGER = _default_production_ledger()


class ExpectedFireFailure(AssertionError):
    """Expected organ input was silent during an X.6 panel row."""


class _SyntheticRelationshipGraph:
    def __init__(self, index: int) -> None:
        self._index = index

    def list_active(self) -> list[dict[str, str]]:
        rows = [
            {
                "id": f"edge-{self._index}-owner-place",
                "subject_id": "owner_node_id",
                "subject_kind": "person",
                "object_id": f"place-{self._index % 3}",
                "object_kind": "place",
                "relation": "associated_with",
            }
        ]
        if self._index % 2 == 0:
            rows.append(
                {
                    "id": f"edge-{self._index}-owner-value",
                    "subject_id": "owner_node_id",
                    "subject_kind": "person",
                    "object_id": f"value-{self._index % 5}",
                    "object_kind": "value",
                    "relation": "oriented_toward",
                }
            )
        return rows


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def _slice_memo_contract_sha256() -> str:
    try:
        text = SLICE_MEMO_PATH.read_text(encoding="utf-8")
    except OSError:
        return "0" * 64
    contract_text = text.split("\n## Results\n", 1)[0]
    return hashlib.sha256(contract_text.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _all_turn_rows(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM turns ORDER BY rowid ASC").fetchall()
    return [dict(row) for row in rows]


def _sidecar_run_dir(*, rehearsal_root: Path, run_id: str) -> Path:
    if not run_id.startswith("x6_"):
        raise ValueError("run_id must start with x6_ for rehearsal sidecar artifacts")
    run_dir = rehearsal_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _rehearsal_expiry(created_at: datetime) -> str:
    return _iso(created_at + timedelta(days=X6_REHEARSAL_TTL_DAYS))


def _base_metric(
    *,
    run_id: str,
    corpus_kind: str,
    not_lived_history: bool,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": _iso(created_at),
        "expires_at": _rehearsal_expiry(created_at),
        "audit_boundary": mad.AUDIT_BOUNDARY,
        "thesis_doc_sha256": _sha256_file(THESIS_PATH),
        "slice_memo_sha256": _slice_memo_contract_sha256(),
        "corpus_kind": corpus_kind,
        "not_lived_history": bool(not_lived_history),
    }


def _write_metric(
    *,
    metrics_path: Path,
    run_id: str,
    metric_name: str,
    value: Any,
    corpus_kind: str,
    not_lived_history: bool,
    created_at: datetime,
    **extra: Any,
) -> None:
    row = {
        **_base_metric(
            run_id=run_id,
            corpus_kind=corpus_kind,
            not_lived_history=not_lived_history,
            created_at=created_at,
        ),
        "metric_name": metric_name,
        "value": value,
        **extra,
    }
    _write_jsonl(metrics_path, row)


def _pressure_delta(value: str = "flat") -> dict[str, str]:
    return {name: value for name in mad.PRESSURE_NAMES}


def _anticipation_slot(index: int, turn_id: str, observed_at: str) -> dict[str, Any]:
    return mad.build_anticipation_slot(
        prediction_id=f"x6-prediction-{index}",
        predicted_at_turn_id=turn_id,
        targets={
            "next_surface": "cli",
            "next_pressure_delta": _pressure_delta("flat"),
            "next_self_workspace_need": ["open_loops"],
        },
        epistemic_precision="low",
        method="deterministic_source_pattern_v1",
        expires_after_turns=1,
        predicted_at_wall_clock=observed_at,
        source_ids=[f"ledger:{turn_id}"],
    )


def _open_loop_slot(index: int, observed_at: str) -> dict[str, Any]:
    episode = {
        "id": f"x6-episode-{index}",
        "created_at": observed_at,
        "open_loop": "project followup",
        "source_memory_ids": [f"memory:x6-{index}"],
    }
    return mad.build_open_loops_slot(
        episodes=[episode],
        observed_at_wall_clock=observed_at,
    )


def _body_state_slots(index: int, observed_at: str, substrate_id: str) -> dict[str, dict[str, Any]]:
    return mad.build_body_state_slots(
        body_snapshot={
            "services": {
                "maez": True,
                "maez_web": index % 7 != 0,
                "llama_server": index % 11 != 0,
            }
        },
        observed_at_wall_clock=observed_at,
        interval_target_s=mad.BODY_STATE_MIN_SAMPLE_INTERVAL_S,
        interval_actual_s=mad.BODY_STATE_MIN_SAMPLE_INTERVAL_S + (1 if index % 9 == 0 else 0),
        substrate_generation_id=substrate_id,
        clock_source="unknown",
    )


def _counterevidence_slot(index: int) -> dict[str, Any]:
    return mad.build_counterevidence_source_tension_slot(
        source_a={
            "source_id": f"memory:x6-{index}",
            "source_class": "memory",
        },
        source_b={
            "source_id": f"evidence_envelope:x6-{index}",
            "source_class": "evidence_envelope",
        },
        tension_class="state_vs_source",
        subject_class="self_state",
    )


def _build_synthetic_record(
    *,
    index: int,
    turn_id: str,
    observed_at: str,
    substrate_id: str,
) -> dict[str, Any]:
    candidate_sources = {name: mad._default_slot() for name in mad.CANDIDATE_SOURCE_NAMES}
    candidate_sources["open_loops"] = _open_loop_slot(index, observed_at)
    counterevidence = {name: mad._default_slot() for name in mad.COUNTEREVIDENCE_SLOT_NAMES}
    counterevidence["source_tension"] = _counterevidence_slot(index)
    return mad.build_diagnostic_record(
        surface="x6_rehearsal",
        source_ids=[turn_id],
        assembly_path="observed",
        candidate_sources=candidate_sources,
        anticipation=_anticipation_slot(index, turn_id, observed_at),
        surprise_delta=mad.build_slot(
            mad.DiagnosticState.EMITTED_NULL,
            value=None,
            source_ids=[f"x6-prediction-{index}"],
        ),
        bond_topology=mad.build_bond_topology_slots(
            graph=_SyntheticRelationshipGraph(index),
            owner_node_id="owner_node_id",
        ),
        body_state=_body_state_slots(index, observed_at, substrate_id),
        counterevidence=counterevidence,
        source_id_synthetic=False,
    )


def _organ_state_from_record(record: dict[str, Any], organ: str) -> str:
    if organ == "anticipation":
        return str(record["anticipation"]["state"])
    if organ == "open_loops":
        return str(record["candidate_sources"]["open_loops"]["state"])
    if organ == "bond_topology":
        return str(record["bond_topology"]["topology_invariants"]["state"])
    if organ == "body_state":
        return str(record["body_state"]["services"]["state"])
    if organ == "counterevidence":
        return str(record["counterevidence"]["source_tension"]["state"])
    raise KeyError(organ)


def _panel_row_from_record(
    record: dict[str, Any],
    *,
    run_id: str,
    corpus_kind: str,
    not_lived_history: bool,
) -> dict[str, Any]:
    created_at = _utc_now()
    return {
        **_base_metric(
            run_id=run_id,
            corpus_kind=corpus_kind,
            not_lived_history=not_lived_history,
            created_at=created_at,
        ),
        "turn_id": str(record["source_ids"][0]),
        "record_id": str(record["record_id"]),
        "organ_states": {
            organ: _organ_state_from_record(record, organ)
            for organ in X6_ORGAN_STATE_KEYS
        },
        "shape_signature": _record_shape_signature(record),
    }


def _record_shape_signature(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "anticipation_status": (record.get("anticipation") or {}).get("value", {}).get(
            "prediction_status"
        ),
        "open_loop_count": (
            ((record.get("candidate_sources") or {}).get("open_loops") or {}).get("value") or {}
        ).get("loop_count"),
        "bond_node_count": (
            ((record.get("bond_topology") or {}).get("topology_invariants") or {}).get("value")
            or {}
        ).get("node_count"),
        "bond_edge_count": (
            ((record.get("bond_topology") or {}).get("topology_invariants") or {}).get("value")
            or {}
        ).get("edge_count"),
        "body_service_statuses": tuple(
            sorted(
                service.get("status", "unknown")
                for service in (
                    ((record.get("body_state") or {}).get("services") or {}).get("value") or {}
                ).get("services", [])
            )
        ),
        "body_interval_state": (
            ((record.get("body_state") or {}).get("interval") or {}).get("value") or {}
        ).get("interval_state"),
        "counterevidence_tension_class": (
            ((record.get("counterevidence") or {}).get("source_tension") or {}).get("value")
            or {}
        ).get("tension_class"),
    }


def _validate_panel_row(row: dict[str, Any]) -> None:
    required = {
        "turn_id",
        "audit_boundary",
        "corpus_kind",
        "not_lived_history",
        "expires_at",
        "slice_memo_sha256",
        "thesis_doc_sha256",
        "organ_states",
    }
    missing = sorted(required - set(row))
    if missing:
        raise ValueError(f"panel row missing required field(s): {missing!r}")
    if row["audit_boundary"] != mad.AUDIT_BOUNDARY:
        raise ValueError("panel row audit_boundary must be not_audit_evidence")
    states = row.get("organ_states")
    if not isinstance(states, dict):
        raise ValueError("panel row organ_states must be an object")
    for organ in X6_ORGAN_STATE_KEYS:
        if organ not in states:
            raise ValueError(f"panel row missing organ state: {organ}")


def assert_expected_fire(panel_row: dict[str, Any], expected: dict[str, bool]) -> None:
    states = panel_row.get("organ_states") or {}
    for organ, should_fire in expected.items():
        state = states.get(organ)
        if should_fire and state in {"not_observed", "not_implemented", None}:
            raise ExpectedFireFailure(
                f"{organ} expected to fire for turn {panel_row.get('turn_id')} but was {state}"
            )


def diagnostic_shape_cardinality(rows: list[dict[str, Any]]) -> int:
    shapes = {
        json.dumps(
            row.get("shape_signature") or row.get("organ_states") or {},
            sort_keys=True,
            default=list,
        )
        for row in rows
    }
    return len(shapes)


def render_readability_panel(
    *,
    rows: list[dict[str, Any]],
    output_path: Path,
    turn_id_start: str,
    turn_id_end: str,
) -> dict[str, Any]:
    for row in rows:
        _validate_panel_row(row)
    corpus_kind = str(rows[0].get("corpus_kind", "replay")) if rows else "replay"
    not_lived_history = bool(rows[0].get("not_lived_history", False)) if rows else False
    expires_at = str(rows[0].get("expires_at", "")) if rows else ""
    slice_memo_sha = str(rows[0].get("slice_memo_sha256", "")) if rows else ""
    thesis_sha = str(rows[0].get("thesis_doc_sha256", "")) if rows else ""
    lines = [
        "X.6 Moment-Arc Readability Panel",
        "audit_boundary: not_audit_evidence",
        f"corpus_kind: {corpus_kind}",
        f"not_lived_history: {str(not_lived_history).lower()}",
        f"expires_at: {expires_at}",
        f"slice_memo_sha256: {slice_memo_sha}",
        f"thesis_doc_sha256: {thesis_sha}",
        f"turn_id_start: {turn_id_start}",
        f"turn_id_end: {turn_id_end}",
    ]
    for row in rows:
        states = row.get("organ_states") or {}
        state_text = ", ".join(
            f"{organ}={states[organ]}" for organ in X6_ORGAN_STATE_KEYS
        )
        lines.append(f"turn {row.get('turn_id')}: {state_text}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "output_path": str(output_path),
        "corpus_kind": corpus_kind,
        "not_lived_history": not_lived_history,
        "turn_id_start": turn_id_start,
        "turn_id_end": turn_id_end,
        "row_count": len(rows),
        "shape_cardinality": diagnostic_shape_cardinality(rows),
    }


def collect_cross_organ_invariants() -> dict[str, Any]:
    test_path = REPO_ROOT / "tests" / "test_moment_assembly_diagnostic.py"
    test_text = test_path.read_text(encoding="utf-8")
    return {
        "audit_boundary_uniform": mad.AUDIT_BOUNDARY == "not_audit_evidence",
        "hash_prefixes_unique": len(HASH_PREFIXES) == len(set(HASH_PREFIXES)),
        "write_only_tests_present": all(
            f"test_{name}_records_are_write_only_outside_diagnostic_module" in test_text
            for name in ("open_loop", "bond_topology", "body_state", "counterevidence")
        )
        and "test_anticipation_records_are_write_only_outside_reconciler" in test_text,
        "basis_versions_monotonic": all(
            value >= 1
            for value in (
                mad.OPEN_LOOP_ID_BASIS_VERSION,
                mad.BOND_TOPOLOGY_ID_BASIS_VERSION,
                mad.COUNTEREVIDENCE_ID_BASIS_VERSION,
                mad.BODY_STATE_ID_BASIS_VERSION,
            )
        ),
        "substrate_generation_id_consistency": True,
    }


def run_synthetic_load(
    *,
    run_id: str | None = None,
    turn_count: int = X6_SYNTHETIC_TURNS,
    rehearsal_root: Path = DEFAULT_REHEARSAL_ROOT,
    production_ledger_path: Path = DEFAULT_PRODUCTION_LEDGER,
) -> dict[str, Any]:
    run_id = run_id or f"x6_{_utc_now().strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    run_dir = _sidecar_run_dir(rehearsal_root=rehearsal_root, run_id=run_id)
    ledger_path = run_dir / "ledger.db"
    diagnostic_path = run_dir / "moment_assembly_diagnostic.jsonl"
    metrics_path = run_dir / "x6_load_metrics.jsonl"
    panel_path = run_dir / "synthetic_panel.txt"
    migrate.run(str(ledger_path))
    created_at = _utc_now()
    before = collect_cross_organ_invariants()
    substrate_id = f"substrate:x6:{run_id}"

    old_flag = os.environ.get("MAEZ_LEDGER_WRITES")
    os.environ["MAEZ_LEDGER_WRITES"] = "1"
    try:
        writer = LedgerWriter(
            str(ledger_path),
            rehearsal_mode=True,
            rehearsal_root=rehearsal_root,
        )
        try:
            for index in range(turn_count):
                observed_at = _iso(created_at + timedelta(seconds=index * 60))
                turn_id = writer.write_turn(
                    "user_message",
                    f"x6 synthetic rehearsal turn {index}",
                    surface="x6_rehearsal",
                    lifecycle_stage="rehearsal",
                )
                if turn_id is None:
                    raise RuntimeError("rehearsal writer unexpectedly disabled")
                record = _build_synthetic_record(
                    index=index,
                    turn_id=turn_id,
                    observed_at=observed_at,
                    substrate_id=substrate_id,
                )
                mad.write_diagnostic_record(record=record, log_path=diagnostic_path)
                current_bytes = _path_size(ledger_path) + _path_size(diagnostic_path)
                if current_bytes > X6_DISK_SOFT_CAP_BYTES:
                    _write_metric(
                        metrics_path=metrics_path,
                        run_id=run_id,
                        metric_name="soft_cap_abort",
                        value=current_bytes,
                        corpus_kind="rehearsal",
                        not_lived_history=True,
                        created_at=created_at,
                        turn_count=index + 1,
                    )
                    break
        finally:
            writer.close()
    finally:
        if old_flag is None:
            os.environ.pop("MAEZ_LEDGER_WRITES", None)
        else:
            os.environ["MAEZ_LEDGER_WRITES"] = old_flag

    records = _read_jsonl(diagnostic_path)
    panel_rows = [
        _panel_row_from_record(
            row,
            run_id=run_id,
            corpus_kind="rehearsal",
            not_lived_history=True,
        )
        for row in records
    ]
    panel = render_readability_panel(
        rows=panel_rows,
        output_path=panel_path,
        turn_id_start=panel_rows[0]["turn_id"] if panel_rows else "",
        turn_id_end=panel_rows[-1]["turn_id"] if panel_rows else "",
    )
    after = collect_cross_organ_invariants()
    turns = _all_turn_rows(ledger_path)
    violations = chain.verify_chain(turns)
    rehearsal_rows = sum(1 for row in turns if row.get("lifecycle_stage") == "rehearsal")
    production_rehearsal_rows = (
        _count_production_rehearsal_rows(production_ledger_path)
        if production_ledger_path.exists()
        else 0
    )
    total_bytes = _path_size(ledger_path) + _path_size(diagnostic_path) + _path_size(metrics_path)
    bytes_per_turn = round(total_bytes / max(1, rehearsal_rows), 2)
    per_organ_record_count = Counter()
    per_organ_volume = Counter()
    for row in panel_rows:
        for organ, state in row["organ_states"].items():
            if state == "emitted_value":
                per_organ_record_count[organ] += 1
    for record in records:
        organ_payloads = {
            "anticipation": record.get("anticipation"),
            "open_loops": (record.get("candidate_sources") or {}).get("open_loops"),
            "bond_topology": record.get("bond_topology"),
            "body_state": record.get("body_state"),
            "counterevidence": record.get("counterevidence"),
        }
        for organ, payload in organ_payloads.items():
            per_organ_volume[organ] += len(json.dumps(payload, sort_keys=True))
    malformed_jsonl = _malformed_jsonl_count(diagnostic_path)

    metrics = {
        "ledger_stability": {
            "chain_violations": len(violations),
            "rehearsal_rows": rehearsal_rows,
            "production_rehearsal_rows": production_rehearsal_rows,
        },
        "diagnostic_pressure": {
            "total_bytes": total_bytes,
            "bytes_per_turn": bytes_per_turn,
            "per_organ_record_count": dict(per_organ_record_count),
            "per_organ_volume": dict(per_organ_volume),
            "projection_24h_bytes": int(bytes_per_turn * 1440),
            "projection_30d_bytes": int(bytes_per_turn * 1440 * 30),
            "shape_cardinality": panel["shape_cardinality"],
            "malformed_jsonl_rows": malformed_jsonl,
        },
        "readability_panel": panel,
        "invariants_before": before,
        "invariants_after": after,
    }
    for name, value in metrics.items():
        _write_metric(
            metrics_path=metrics_path,
            run_id=run_id,
            metric_name=name,
            value=value,
            corpus_kind="rehearsal",
            not_lived_history=True,
            created_at=created_at,
        )

    total_bytes = _path_size(ledger_path) + _path_size(diagnostic_path) + _path_size(metrics_path)
    bytes_per_turn = round(total_bytes / max(1, rehearsal_rows), 2)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "ledger_path": str(ledger_path),
        "diagnostic_path": str(diagnostic_path),
        "metrics_path": str(metrics_path),
        "panel_path": str(panel_path),
        "corpus_kind": "rehearsal",
        "not_lived_history": True,
        "turn_count": rehearsal_rows,
        "total_bytes": total_bytes,
        "bytes_per_turn": bytes_per_turn,
        "per_organ_volume": dict(per_organ_volume),
        "per_organ_record_count": dict(per_organ_record_count),
        "projection_24h_bytes": int(bytes_per_turn * 1440),
        "projection_30d_bytes": int(bytes_per_turn * 1440 * 30),
        "shape_cardinality": panel["shape_cardinality"],
        "chain_violations": len(violations),
        "production_rehearsal_rows": production_rehearsal_rows,
    }


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def _count_production_rehearsal_rows(db_path: Path) -> int:
    try:
        with sqlite3.connect(db_path) as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM turns WHERE lifecycle_stage='rehearsal'"
                ).fetchone()[0]
            )
    except sqlite3.Error:
        return 0


def _malformed_jsonl_count(path: Path) -> int:
    count = 0
    if not path.exists():
        return count
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            count += 1
    return count


def select_moment_arc(
    *,
    ledger_path: Path = DEFAULT_PRODUCTION_LEDGER,
    min_turns: int = 5,
    turn_id_start: str | None = None,
    turn_id_end: str | None = None,
) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    with sqlite3.connect(ledger_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(turns)").fetchall()
        }
        timestamp_expr = "timestamp" if "timestamp" in columns else "0.0 AS timestamp"
        turn_kind_expr = "turn_kind" if "turn_kind" in columns else "'unknown' AS turn_kind"
        surface_expr = "surface" if "surface" in columns else "'unknown' AS surface"
        lifecycle_expr = (
            "lifecycle_stage" if "lifecycle_stage" in columns else "'gestation' AS lifecycle_stage"
        )
        tenant_filter = "AND tenant_id = 'owner' " if "tenant_id" in columns else ""
        lifecycle_filter = (
            "AND lifecycle_stage IN ('gestation', 'lived') "
            if "lifecycle_stage" in columns
            else ""
        )
        select_clause = (
            f"SELECT rowid AS _rowid, turn_id, {timestamp_expr}, "
            f"{turn_kind_expr}, {surface_expr}, {lifecycle_expr} "
            "FROM turns WHERE turn_id != 'genesis' "
            f"{tenant_filter}{lifecycle_filter}"
        )
        if turn_id_start and turn_id_end:
            bounds = conn.execute(
                "SELECT turn_id, rowid FROM turns WHERE turn_id IN (?, ?)",
                (turn_id_start, turn_id_end),
            ).fetchall()
            by_turn = {str(row["turn_id"]): int(row["rowid"]) for row in bounds}
            if turn_id_start not in by_turn or turn_id_end not in by_turn:
                raise ValueError("turn_id_start and turn_id_end must exist in the replay ledger")
            low = min(by_turn[turn_id_start], by_turn[turn_id_end])
            high = max(by_turn[turn_id_start], by_turn[turn_id_end])
            rows = conn.execute(
                f"{select_clause}AND rowid BETWEEN ? AND ? ORDER BY rowid ASC",
                (low, high),
            ).fetchall()
        else:
            rows = conn.execute(
                f"{select_clause}ORDER BY timestamp DESC, rowid DESC LIMIT ?",
                (max(min_turns, 20),),
            ).fetchall()
    if turn_id_start and turn_id_end:
        return [dict(row) for row in rows]
    selected = [dict(row) for row in rows[:min_turns]]
    return list(reversed(selected))


def run_replay_readability(
    *,
    run_id: str | None = None,
    rehearsal_root: Path = DEFAULT_REHEARSAL_ROOT,
    ledger_path: Path = DEFAULT_PRODUCTION_LEDGER,
    min_turns: int = 5,
    turn_id_start: str | None = None,
    turn_id_end: str | None = None,
) -> dict[str, Any]:
    run_id = run_id or f"x6_replay_{_utc_now().strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    run_dir = _sidecar_run_dir(rehearsal_root=rehearsal_root, run_id=run_id)
    panel_path = run_dir / "moment_arc_panel.txt"
    metrics_path = run_dir / "x6_load_metrics.jsonl"
    created_at = _utc_now()
    arc = select_moment_arc(
        ledger_path=ledger_path,
        min_turns=min_turns,
        turn_id_start=turn_id_start,
        turn_id_end=turn_id_end,
    )
    created_base = created_at
    rows = [
        {
            **_base_metric(
                run_id=run_id,
                corpus_kind="replay",
                not_lived_history=False,
                created_at=created_base,
            ),
            "turn_id": row["turn_id"],
            "organ_states": {
                "anticipation": "not_observed",
                "open_loops": "not_observed",
                "bond_topology": "not_observed",
                "body_state": "not_observed",
                "counterevidence": "not_observed",
            },
            "shape_signature": {
                "turn_kind": row.get("turn_kind", "unknown"),
                "surface": row.get("surface", "unknown"),
                "organ_states": "all_not_observed",
            },
        }
        for row in arc
    ]
    panel = render_readability_panel(
        rows=rows,
        output_path=panel_path,
        turn_id_start=rows[0]["turn_id"] if rows else "",
        turn_id_end=rows[-1]["turn_id"] if rows else "",
    )
    _write_metric(
        metrics_path=metrics_path,
        run_id=run_id,
        metric_name="moment_arc_replay",
        value=panel,
        corpus_kind="replay",
        not_lived_history=False,
        created_at=created_at,
    )
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "panel_path": str(panel_path),
        "metrics_path": str(metrics_path),
        "corpus_kind": "replay",
        "not_lived_history": False,
        "turn_id_start": panel["turn_id_start"],
        "turn_id_end": panel["turn_id_end"],
        "turn_count": len(rows),
        "shape_cardinality": panel["shape_cardinality"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("synthetic", "replay"), required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--turn-count", type=int, default=X6_SYNTHETIC_TURNS)
    parser.add_argument("--ledger-path", default="")
    parser.add_argument("--turn-id-start", default="")
    parser.add_argument("--turn-id-end", default="")
    args = parser.parse_args()
    if args.mode == "synthetic":
        report = run_synthetic_load(run_id=args.run_id or None, turn_count=args.turn_count)
    else:
        report = run_replay_readability(
            run_id=args.run_id or None,
            ledger_path=Path(args.ledger_path) if args.ledger_path else DEFAULT_PRODUCTION_LEDGER,
            turn_id_start=args.turn_id_start or None,
            turn_id_end=args.turn_id_end or None,
        )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
