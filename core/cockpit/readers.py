"""Read-only source health for Cockpit V2.

The cockpit is an inspection surface first. These helpers report source
availability without creating missing DBs and without opening private thought
content.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.infra.ro_sqlite import _ro_connect
from core.interaction_preferences.store import list_all_readonly
from core.learning.self_evidence import self_evidence_digest


@dataclass(frozen=True)
class CockpitSourcePaths:
    memory_dir: Path
    logs_dir: Path

    @classmethod
    def defaults(cls) -> "CockpitSourcePaths":
        from core.infra import paths

        return cls(memory_dir=paths.memory_dir(), logs_dir=paths.logs_dir())

    @property
    def scar_sidecar_db(self) -> Path:
        return self.memory_dir / "scar_tissue.db"

    @property
    def continuity_db(self) -> Path:
        return self.memory_dir / "continuity_fingerprint.db"

    @property
    def episodes_db(self) -> Path:
        return self.memory_dir / "lived_episodes.db"

    @property
    def interaction_preferences_db(self) -> Path:
        return self.memory_dir / "interaction_preferences.db"

    @property
    def private_thoughts_db(self) -> Path:
        return self.memory_dir / "private_thoughts.db"

    @property
    def fresh_moment_receipts_db(self) -> Path:
        return self.memory_dir / "fresh_moment_receipts.db"

    @property
    def maez_log(self) -> Path:
        return self.logs_dir / "maez.log"

    @property
    def cognition_log(self) -> Path:
        return self.logs_dir / "cognition.log"


def _table_exists(con, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(con, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}


def _table_count(path: Path, table: str) -> dict[str, Any]:
    try:
        con = _ro_connect(path)
        if con is None:
            return {
                "status": "no_data",
                "count": 0,
                "db_exists": False,
                "table_exists": False,
                "read_mode": "sqlite_ro_query_only",
            }
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            if not _table_exists(con, table):
                return {
                    "status": "no_data",
                    "count": 0,
                    "db_exists": True,
                    "table_exists": False,
                    "read_mode": "sqlite_ro_query_only",
                }
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return {
                "status": "ok",
                "count": int(row[0] or 0),
                "db_exists": True,
                "table_exists": True,
                "read_mode": "sqlite_ro_query_only",
            }
    except Exception:
        return {
            "status": "unavailable",
            "count": 0,
            "db_exists": path.exists(),
            "table_exists": False,
            "read_mode": "sqlite_ro_query_only",
            "error_code": "read_error",
        }


def _log_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "no_data", "bytes": 0}
    try:
        stat = path.stat()
    except Exception as e:
        return {"status": "unavailable", "bytes": 0, "error": str(e)}
    return {"status": "ok", "bytes": int(stat.st_size)}


def a1_scar_tissue_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    from core.learning.scar_tissue import ScarSidecar

    coverage = ScarSidecar.coverage_at(paths.scar_sidecar_db)
    return {
        "status": coverage.get("status", "unavailable"),
        "active_episodes": int(coverage.get("active_episodes") or 0),
        "total_occurrences": int(coverage.get("total_occurrences") or 0),
        "coverage": coverage.get("retention", "append_preserving_all_time"),
    }


def a2_continuity_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    count = _table_count(paths.continuity_db, "probe_runs")
    return {
        "status": count["status"],
        "probe_runs": count["count"],
    }


def a6_self_evidence_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    digest = self_evidence_digest(
        _sources={
            "scar_sidecar_db": paths.scar_sidecar_db,
            "consequence_db": paths.memory_dir / "consequence_memory.db",
            "fabrication_db": paths.memory_dir / "fabrication_memory.db",
            "veto_db": paths.memory_dir / "veto_ledger.db",
        }
    )
    source_statuses = [
        str(source.get("status", "unavailable"))
        for source in (digest.get("sources") or {}).values()
        if isinstance(source, dict)
    ]
    if source_statuses and all(status == "no_data" for status in source_statuses):
        status = "no_data"
    elif "unavailable" in source_statuses:
        status = "unavailable"
    else:
        status = "ok"
    return {
        "status": status,
        "sources": digest.get("sources", {}),
        "merged_events": digest.get("merged_events", {}),
    }


def narrative_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    try:
        con = _ro_connect(paths.episodes_db)
        if con is None:
            return {
                "status": "no_data",
                "links": {"same_thread": 0, "strings": 0, "because_of": 0},
            }
        with closing(con):
            if not _table_exists(con, "narrative_links"):
                return {
                    "status": "no_data",
                    "links": {"same_thread": 0, "strings": 0, "because_of": 0},
                }
            rows = con.execute(
                """
                SELECT link_type, COUNT(*) FROM narrative_links
                WHERE status = 'active'
                GROUP BY link_type
                """
            ).fetchall()
        counts = {"same_thread": 0, "strings": 0, "because_of": 0}
        for link_type, count in rows:
            if str(link_type) in counts:
                counts[str(link_type)] = int(count or 0)
        return {"status": "ok", "links": counts}
    except Exception as e:
        return {
            "status": "unavailable",
            "links": {"same_thread": 0, "strings": 0, "because_of": 0},
            "error": str(e),
        }


def interaction_preferences_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    con = _ro_connect(paths.interaction_preferences_db)
    if con is None:
        list_all_readonly(paths.interaction_preferences_db)
        return {"status": "no_data", "active": 0, "total": 0}
    try:
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            table_exists = _table_exists(con, "interaction_preferences")
            columns = (
                _table_columns(con, "interaction_preferences")
                if table_exists
                else set()
            )
    except Exception:
        return {"status": "unavailable", "active": 0, "total": 0}
    if not table_exists:
        list_all_readonly(paths.interaction_preferences_db)
        return {"status": "no_data", "active": 0, "total": 0}
    required = {
        "preference_id",
        "status",
        "preference_class",
        "owner_statement",
        "source_ref",
    }
    if not required.issubset(columns):
        return {"status": "unavailable", "active": 0, "total": 0}
    rows = list_all_readonly(paths.interaction_preferences_db)
    return {
        "status": "ok",
        "active": sum(1 for row in rows if row.status == "active"),
        "total": len(rows),
    }


def a7_interiority_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    private_count = _table_count(paths.private_thoughts_db, "private_thoughts")
    receipt_count = _table_count(
        paths.fresh_moment_receipts_db,
        "fresh_moment_receipts",
    )
    statuses = {private_count["status"], receipt_count["status"]}
    if "ok" in statuses:
        status = "ok"
    elif "unavailable" in statuses:
        status = "unavailable"
    else:
        status = "no_data"
    return {
        "status": status,
        "available": status == "ok",
        "private_thought_count": private_count["count"],
        "fresh_moment_receipt_count": receipt_count["count"],
        "stores": {
            "private_thoughts": {
                "status": private_count["status"],
                "db_exists": private_count["db_exists"],
                "table_exists": private_count["table_exists"],
                "row_count": private_count["count"],
                "read_mode": private_count["read_mode"],
            },
            "fresh_moment_receipts": {
                "status": receipt_count["status"],
                "db_exists": receipt_count["db_exists"],
                "table_exists": receipt_count["table_exists"],
                "row_count": receipt_count["count"],
                "read_mode": receipt_count["read_mode"],
            },
        },
        "raw_text_included": False,
        "content_policy": "sealed",
    }


def receipts_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    return {
        "fresh_moment_receipts": _table_count(
            paths.fresh_moment_receipts_db,
            "fresh_moment_receipts",
        ),
    }


def logs_health(paths: CockpitSourcePaths) -> dict[str, Any]:
    return {
        "maez": _log_health(paths.maez_log),
        "cognition": _log_health(paths.cognition_log),
    }


def source_health(paths: CockpitSourcePaths | None = None) -> dict[str, Any]:
    source_paths = paths or CockpitSourcePaths.defaults()
    return {
        "a1_scar_tissue": a1_scar_tissue_health(source_paths),
        "a2_continuity": a2_continuity_health(source_paths),
        "a6_self_evidence": a6_self_evidence_health(source_paths),
        "narrative": narrative_health(source_paths),
        "interaction_preferences": interaction_preferences_health(source_paths),
        "receipts": receipts_health(source_paths),
        "logs": logs_health(source_paths),
        "a7_interiority": a7_interiority_health(source_paths),
    }
