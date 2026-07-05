"""Cockpit V2 Receipts Room read model.

The Receipts Room is an inspection surface over existing receipts. It never
creates missing stores and never turns receipt counts into first-person claims.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from core.cockpit.readers import CockpitSourcePaths
from core.infra.ro_sqlite import _ro_connect


_SYSTEM_SHAPE_RE = re.compile(r"daemon_system_part_shape .*?summary=(\{.*\})")
_FOCUSED_SHAPE_RE = re.compile(r"focused_cognition_prompt_shape .*?summary=(\{.*\})")
_RECALL_OUTCOME_PREFIX = "recall_outcome "


def _table_exists(con, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _empty_state(status: str, count: int) -> str:
    if status == "no_data":
        return "no_data"
    if count == 0:
        return "explicit_zero"
    return "present"


def _source_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "no_data", "bytes": 0}
    try:
        stat = path.stat()
    except Exception:
        return {"status": "unavailable", "bytes": 0, "error_code": "stat_failed"}
    return {"status": "ok", "bytes": int(stat.st_size)}


def _safe_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _tail_lines(path: Path, *, max_bytes: int = 256_000) -> tuple[str, list[str]]:
    if not path.exists():
        return "no_data", []
    try:
        with path.open("rb") as fh:
            try:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - max_bytes))
            except OSError:
                fh.seek(0)
            text = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return "unavailable", []
    return "ok", text.splitlines()


def fabrication_events_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    path = paths.memory_dir / "fabrication_log.db"
    try:
        con = _ro_connect(path)
        if con is None:
            return {
                "status": "no_data",
                "receipt_count": 0,
                "empty_state": "no_data",
                "label": "fabrication event receipts",
                "perspective": "third-person receipt labels; not first-person claims",
            }
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            if not _table_exists(con, "fabrication_events"):
                return {
                    "status": "no_data",
                    "receipt_count": 0,
                    "empty_state": "no_data",
                    "label": "fabrication event receipts",
                    "perspective": "third-person receipt labels; not first-person claims",
                }
            row = con.execute(
                "SELECT COUNT(*), MIN(ts), MAX(ts) FROM fabrication_events"
            ).fetchone()
            mode_rows = con.execute(
                "SELECT mode, COUNT(*) FROM fabrication_events GROUP BY mode"
            ).fetchall()
        count = int(row[0] or 0)
        return {
            "status": "ok",
            "receipt_count": count,
            "empty_state": _empty_state("ok", count),
            "label": "fabrication event receipts",
            "perspective": "third-person receipt labels; not first-person claims",
            "coverage": "90d_best_effort",
            "earliest_row_ts": row[1],
            "latest_row_ts": row[2],
            "by_mode": {str(mode): int(n or 0) for mode, n in mode_rows},
        }
    except Exception:
        return {
            "status": "unavailable",
            "receipt_count": 0,
            "empty_state": "no_data",
            "label": "fabrication event receipts",
            "perspective": "third-person receipt labels; not first-person claims",
            "error_code": "read_error",
        }


def claim_receipt_redo_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    path = paths.memory_dir / "consequence_memory.db"
    empty = {"accepted": 0, "floor": 0, "other": 0}
    outcome_labels = {
        "accepted": "corrected_before_send",
        "floor": "held_with_floor_notice",
    }
    try:
        con = _ro_connect(path)
        if con is None:
            return {
                "status": "no_data",
                "total": 0,
                "empty_state": "no_data",
                "outcomes": empty,
                "outcome_labels": outcome_labels,
            }
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            if not _table_exists(con, "events"):
                return {
                    "status": "no_data",
                    "total": 0,
                    "empty_state": "no_data",
                    "outcomes": empty,
                    "outcome_labels": outcome_labels,
                }
            rows = con.execute(
                """
                SELECT outcome, COUNT(*) FROM events
                WHERE class = 'claim_receipt_redo'
                GROUP BY outcome
                """
            ).fetchall()
        counts = Counter()
        for outcome, count in rows:
            value = str(outcome or "")
            if value in ("accepted", "floor"):
                counts[value] += int(count or 0)
            else:
                counts["other"] += int(count or 0)
        total = sum(counts.values())
        outcomes = {key: int(counts.get(key, 0)) for key in ("accepted", "floor", "other")}
        return {
            "status": "ok",
            "total": total,
            "empty_state": _empty_state("ok", total),
            "outcomes": outcomes,
            "outcome_labels": outcome_labels,
        }
    except Exception:
        return {
            "status": "unavailable",
            "total": 0,
            "empty_state": "no_data",
            "outcomes": empty,
            "outcome_labels": outcome_labels,
            "error_code": "read_error",
        }


def routing_veto_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    from core.routing import veto_ledger

    data = veto_ledger.coverage(_db_path=paths.memory_dir / "veto_ledger.db")
    status = str(data.get("status") or "unavailable")
    count = int(data.get("likely_wrong") or 0)
    return {
        "status": status,
        "likely_wrong_count": count,
        "total_veto_events": int(data.get("total_events") or 0),
        "empty_state": _empty_state(status, count),
        "coverage": data.get("retention", "all_time_verified"),
    }


def prompt_shape_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    status, lines = _tail_lines(paths.maez_log)
    if status != "ok":
        return {"status": status, "latest": None}
    for line in reversed(lines):
        match = _SYSTEM_SHAPE_RE.search(line)
        if match:
            summary = _safe_json(match.group(1))
            return {
                "status": "ok",
                "latest": {
                    "system_part_labels": str(summary.get("system_part_labels") or ""),
                    "system_part_count": int(summary.get("system_part_count") or 0),
                    "system_part_lengths": str(summary.get("system_part_lengths") or ""),
                },
            }
    return {"status": "no_data", "latest": None}


def grounding_meter_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    status, lines = _tail_lines(paths.maez_log)
    if status != "ok":
        return {"status": status, "latest": None}
    for line in reversed(lines):
        if _RECALL_OUTCOME_PREFIX not in line:
            continue
        fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
        return {
            "status": "ok",
            "latest": {
                "citation_coverage": _log_number_or_none(fields.get("citation_coverage")),
                "reply_grounding": _log_number_or_none(fields.get("reply_grounding")),
                "receipt_or_na": fields.get("receipt_or_na", "na"),
            },
        }
    return {"status": "no_data", "latest": None}


def focused_prompt_shape_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    status, lines = _tail_lines(paths.maez_log)
    if status != "ok":
        return {"status": status, "latest": None}
    for line in reversed(lines):
        match = _FOCUSED_SHAPE_RE.search(line)
        if match:
            summary = _safe_json(match.group(1))
            return {
                "status": "ok",
                "latest": {
                    "evidence_item_count": int(summary.get("evidence_item_count") or 0),
                    "source_types": str(summary.get("source_types") or ""),
                    "working_set_tokens_est": int(
                        summary.get("working_set_tokens_est") or 0
                    ),
                },
            }
    return {"status": "no_data", "latest": None}


def _log_number_or_none(raw: str | None) -> float | None:
    if raw in (None, "", "na", "none", "None"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def logs_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    grounding_shadow = paths.logs_dir / "grounding_shadow.jsonl"
    return {
        "maez": _source_health(paths.maez_log),
        "cognition": _source_health(paths.cognition_log),
        "grounding_shadow": _source_health(grounding_shadow),
    }


def build_receipts_room(paths: CockpitSourcePaths | None = None) -> dict[str, Any]:
    source_paths = paths or CockpitSourcePaths.defaults()
    return {
        "kind": "cockpit_v2_receipts_room",
        "fabrication_events": fabrication_events_section(source_paths),
        "claim_receipt_redo": claim_receipt_redo_section(source_paths),
        "routing_veto": routing_veto_section(source_paths),
        "prompt_shape": prompt_shape_section(source_paths),
        "focused_prompt_shape": focused_prompt_shape_section(source_paths),
        "grounding_meter": grounding_meter_section(source_paths),
        "logs": logs_section(source_paths),
    }


def render_receipts_room_dom_text(room: dict[str, Any]) -> str:
    fabrication = room.get("fabrication_events") or {}
    claim = room.get("claim_receipt_redo") or {}
    veto = room.get("routing_veto") or {}
    prompt = room.get("prompt_shape") or {}
    grounding = room.get("grounding_meter") or {}
    logs = room.get("logs") or {}
    outcomes = claim.get("outcomes") or {}
    lines = [
        "Receipts Room",
        str(fabrication.get("label") or "fabrication event receipts"),
        str(fabrication.get("perspective") or "third-person receipt labels"),
        f"fabrication receipts {int(fabrication.get('receipt_count') or 0)}",
        f"fabrication empty state {fabrication.get('empty_state', 'no_data')}",
        "claim-receipt redo",
        f"accepted {int(outcomes.get('accepted') or 0)}",
        f"floor {int(outcomes.get('floor') or 0)}",
        "accepted means corrected_before_send",
        "floor means held_with_floor_notice",
        f"routing likely_wrong {int(veto.get('likely_wrong_count') or 0)}",
        f"routing total {int(veto.get('total_veto_events') or 0)}",
        f"routing empty state {veto.get('empty_state', 'no_data')}",
        f"prompt shape {prompt.get('status', 'no_data')}",
        f"grounding meter {grounding.get('status', 'no_data')}",
        f"maez log {((logs.get('maez') or {}).get('status') or 'no_data')}",
        f"cognition log {((logs.get('cognition') or {}).get('status') or 'no_data')}",
    ]
    return "\n".join(lines)
