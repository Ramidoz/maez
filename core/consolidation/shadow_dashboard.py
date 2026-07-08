# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Content-light shadow-dashboard metrics for consolidation B2/G5."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from core.evolution.wonderings import _QUARANTINED_SOURCES

_DIALOGUE_TURN_KINDS = frozenset(
    ("user_message", "model_reply", "peer_message_in", "peer_message_out")
)
_TOOL_TURN_KINDS = frozenset(("tool_call", "tool_result"))


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    uri_path = quote(str(path.resolve()), safe="/")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _json_loads(value: Any, default: Any) -> Any:
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _load_ledger_rows(path: Path) -> list[dict[str, Any]]:
    conn = _connect_ro(path)
    if conn is None:
        return []
    try:
        if not _table_exists(conn, "turns"):
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM turns ORDER BY chain_position ASC"
            ).fetchall()
        ]
    finally:
        conn.close()


def _load_spans(path: Path) -> list[dict[str, Any]]:
    conn = _connect_ro(path)
    if conn is None:
        return []
    try:
        if not _table_exists(conn, "spans"):
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM spans ORDER BY created_at ASC, span_id ASC"
            ).fetchall()
        ]
    finally:
        conn.close()


def _load_state(path: Path) -> dict[str, str]:
    conn = _connect_ro(path)
    if conn is None:
        return {}
    try:
        if not _table_exists(conn, "state"):
            return {}
        return {
            str(row["key"]): str(row["value"])
            for row in conn.execute("SELECT key, value FROM state").fetchall()
        }
    finally:
        conn.close()


def _load_digests(path: Path, span_id: str) -> list[dict[str, Any]]:
    conn = _connect_ro(path)
    if conn is None:
        return []
    try:
        if not _table_exists(conn, "episode_digest_shadow"):
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM episode_digest_shadow "
                "WHERE span_id = ? ORDER BY id ASC",
                (span_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


def _load_outcomes(path: Path, span_id: str) -> list[dict[str, Any]]:
    conn = _connect_ro(path)
    if conn is None:
        return []
    try:
        if not _table_exists(conn, "episode_outcomes"):
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM episode_outcomes "
                "WHERE span_id = ? ORDER BY id ASC",
                (span_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


def _row_taints(row: Mapping[str, Any]) -> set[str]:
    labels = _json_loads(row.get("taint_labels_json"), [])
    if not isinstance(labels, list):
        return set()
    return {label for label in labels if isinstance(label, str)}


def _rows_for_digest(
    ledger_rows: list[dict[str, Any]],
    digest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    start = int(digest["start_chain_position"])
    end = int(digest["end_chain_position"])
    return [
        row
        for row in ledger_rows
        if start <= int(row.get("chain_position", -1)) <= end
    ]


def _deep_episode_composition(
    *,
    ledger_rows: list[dict[str, Any]],
    digests: list[dict[str, Any]],
) -> dict[str, float | int]:
    deep = [row for row in digests if row.get("selection_depth") == "deep"]
    tool_heavy = 0
    dialogue_heavy = 0
    for digest in deep:
        episode_rows = _rows_for_digest(ledger_rows, digest)
        tool_count = sum(
            1 for row in episode_rows if row.get("turn_kind") in _TOOL_TURN_KINDS
        )
        dialogue_count = sum(
            1 for row in episode_rows if row.get("turn_kind") in _DIALOGUE_TURN_KINDS
        )
        if tool_count > dialogue_count:
            tool_heavy += 1
        else:
            dialogue_heavy += 1
    denominator = len(deep) or 1
    return {
        "deep_episode_count": len(deep),
        "tool_heavy_fraction": tool_heavy / denominator,
        "dialogue_heavy_fraction": dialogue_heavy / denominator,
    }


def _citation_coverage(digests: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for digest in digests:
        citations = _json_loads(digest.get("row_citations_json"), [])
        if not isinstance(citations, list):
            citations = []
        out[str(digest["episode_key"])] = {
            "cited_rows": len(citations),
            "episode_rows": int(digest["row_count"]),
        }
    return out


def _taint_gap_count(
    *,
    ledger_rows: list[dict[str, Any]],
    digests: list[dict[str, Any]],
) -> int:
    rows_by_id = {str(row.get("turn_id", "")): row for row in ledger_rows}
    gap_count = 0
    for digest in digests:
        artifact_taint = set(_json_loads(digest.get("taint_labels_json"), []))
        citations = _json_loads(digest.get("row_citations_json"), [])
        if not isinstance(citations, list):
            citations = []
        cited_taint: set[str] = set()
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            row = rows_by_id.get(str(citation.get("turn_id", "")))
            if row is not None:
                cited_taint.update(_row_taints(row))
        if artifact_taint != cited_taint:
            gap_count += 1
    return gap_count


def _refusals_by_code_and_outcome(
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in outcomes:
        code = str(row.get("refusal_code", "") or "")
        if not code:
            continue
        outcome = str(row.get("outcome", "") or "")
        out.setdefault(code, {})
        out[code][outcome] = out[code].get(outcome, 0) + 1
    return out


def _digestion_wonderings_in_pursuit_count(path: Path | None) -> int:
    if path is None:
        return 0
    conn = _connect_ro(path)
    if conn is None:
        return 0
    try:
        if not _table_exists(conn, "wonderings"):
            return 0
        placeholders = ",".join("?" for _ in _QUARANTINED_SOURCES)
        rows = conn.execute(
            "SELECT source FROM wonderings "
            "WHERE status IN ('open', 'active') "
            f"AND COALESCE(source, '') NOT IN ({placeholders})",
            tuple(_QUARANTINED_SOURCES),
        ).fetchall()
        return sum(
            1
            for row in rows
            if str(row["source"] or "") in _QUARANTINED_SOURCES
        )
    finally:
        conn.close()


def _backlog_depth(
    *,
    ledger_rows: list[dict[str, Any]],
    state: Mapping[str, str],
) -> int:
    try:
        last = int(state.get("last_digested_chain_position", "-1"))
    except ValueError:
        last = -1
    return sum(1 for row in ledger_rows if int(row.get("chain_position", -1)) > last)


def build_shadow_metrics(paths: Any) -> dict[str, Any]:
    """Build content-light per-span shadow metrics from committed state."""
    ledger_rows = _load_ledger_rows(Path(paths.ledger_db_path))
    state = _load_state(Path(paths.spine_db_path))
    spans = []
    for span in _load_spans(Path(paths.spine_db_path)):
        span_id = str(span["span_id"])
        digests = _load_digests(Path(paths.episode_digests_db_path), span_id)
        outcomes = _load_outcomes(Path(paths.spine_db_path), span_id)
        spans.append(
            {
                "span_id": span_id,
                "status": str(span["status"]),
                "after_chain_position": int(span["after_chain_position"]),
                "high_water": int(span["high_water"]),
                "row_count": int(span["row_count"]),
                "deep_episode_composition": _deep_episode_composition(
                    ledger_rows=ledger_rows,
                    digests=digests,
                ),
                "citation_coverage": _citation_coverage(digests),
                "artifact_taint_cited_taint_gap_count": _taint_gap_count(
                    ledger_rows=ledger_rows,
                    digests=digests,
                ),
                "refusals_by_code_and_outcome": _refusals_by_code_and_outcome(
                    outcomes
                ),
                "digestion_wonderings_in_pursuit_count": (
                    _digestion_wonderings_in_pursuit_count(
                        getattr(paths, "live_wonderings_db_path", None)
                    )
                ),
                "backlog_depth": _backlog_depth(
                    ledger_rows=ledger_rows,
                    state=state,
                ),
            }
        )
    return {"schema_version": 1, "spans": spans}
