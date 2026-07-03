"""Self-Evidence (A6): read-only integrity receipt index.

This module only reads existing receipt stores. It does not write, grade, or
turn counts into first-person claims.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_memory_dir() -> Path:
    from core.infra import paths

    return paths.memory_dir()


def _source_path(
    sources: dict[str, Any] | None,
    key: str,
    default: Path,
) -> Path:
    if sources and key in sources:
        return Path(sources[key])
    return default


def _safe_source(name: str, producer) -> dict:
    try:
        data = producer()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
    if not isinstance(data, dict):
        return {"status": "unavailable", "error": f"{name} returned non-dict"}
    return data


def _fabrication_source(sources: dict[str, Any] | None) -> dict:
    from core.learning import fabrication_memory

    path = _source_path(sources, "fabrication_db", fabrication_memory._DB_PATH)
    data = fabrication_memory._coverage_at(path)
    return {
        "status": data.get("status", "unavailable"),
        "retained_rows": int(data.get("retained_rows") or 0),
        "earliest_row_ts": data.get("earliest_row_ts"),
        "latest_row_ts": data.get("latest_row_ts"),
        "coverage": data.get("retention", "90d_best_effort"),
        "native_id_prefix": "fabrication",
    }


def _veto_source(sources: dict[str, Any] | None) -> dict:
    from core.routing import veto_ledger

    path = _source_path(sources, "veto_db", veto_ledger._default_db_path())
    data = veto_ledger.coverage(_db_path=path)
    return {
        "status": data.get("status", "unavailable"),
        "count": int(data.get("likely_wrong") or 0),
        "total_veto_events": int(data.get("total_events") or 0),
        "earliest_row_ts": data.get("earliest_row_ts"),
        "latest_row_ts": data.get("latest_row_ts"),
        "coverage": data.get("retention", "all_time_verified"),
        "native_id_prefix": "veto",
    }


def _consequence_source(sources: dict[str, Any] | None) -> dict:
    from core.learning import consequence_memory

    path = _source_path(sources, "consequence_db", consequence_memory.DB_PATH)
    data = consequence_memory.coverage(_db_path=path)
    return {
        "status": data.get("status", "unavailable"),
        "by_class": dict(data.get("by_class") or {}),
        "outcome_detail": {"claim_receipt_redo": "unstructured"},
        "earliest_row_ts": data.get("earliest_row_ts"),
        "latest_row_ts": data.get("latest_row_ts"),
        "coverage": data.get("retention", "all_time_verified"),
        "native_id_prefix": "consequence",
    }


def _scar_sidecar_source(sources: dict[str, Any] | None) -> dict:
    from core.learning.scar_tissue import ScarSidecar

    default = _default_memory_dir() / "scar_tissue.db"
    path = _source_path(sources, "scar_sidecar_db", default)
    data = ScarSidecar.coverage_at(path)
    return {
        "status": data.get("status", "unavailable"),
        "active_episodes": int(data.get("active_episodes") or 0),
        "total_occurrences": int(data.get("total_occurrences") or 0),
        "earliest_row_ts": data.get("earliest_row_ts"),
        "latest_row_ts": data.get("latest_row_ts"),
        "coverage": data.get("retention", "append_preserving_all_time"),
    }


def self_evidence_digest(
    window: dict | None = None,
    *,
    _sources: dict[str, Any] | None = None,
) -> dict:
    sources = {
        "fabrication_events": _safe_source(
            "fabrication_events", lambda: _fabrication_source(_sources)
        ),
        "veto_proven_wrong": _safe_source(
            "veto_proven_wrong", lambda: _veto_source(_sources)
        ),
        "consequence_scar_classes": _safe_source(
            "consequence_scar_classes", lambda: _consequence_source(_sources)
        ),
        "scar_sidecar": _safe_source(
            "scar_sidecar", lambda: _scar_sidecar_source(_sources)
        ),
    }
    return {
        "kind": "self_evidence_integrity_ledger",
        "generated_at": _now_iso(),
        "window": window,
        "sources": sources,
        "merged_events": {
            "distinct_integrity_events": 0,
            "by_class": {},
            "overlap_unified": 0,
        },
        "coverage_note": "per-source; no single all-time claim",
    }
