"""Cockpit V2 Memory Room read model.

The Memory Room is an inspection surface. It composes already-durable receipt
stores into owner-readable summaries without creating missing stores and
without opening A7 private thought bodies.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from pathlib import Path
from typing import Any

from core.cockpit.readers import (
    CockpitSourcePaths,
    a2_continuity_health,
    a6_self_evidence_health,
    a7_interiority_health,
    interaction_preferences_health,
    narrative_health,
)
from core.infra.ro_sqlite import _ro_connect
from core.interaction_preferences.store import list_all_readonly
from core.learning.scar_tissue import ScarSidecar


_CORRECTION_RE = re.compile(r'The correction:\s*"([^"]*)"')
_SCAR_CLASS_RE = re.compile(r"Correction received \(([^,\)]*)")


def _table_exists(con, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _safe_json_list(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _episode_rows_by_id(path: Path, episode_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not episode_ids:
        return {}
    try:
        con = _ro_connect(path)
        if con is None:
            return {}
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            if not _table_exists(con, "episodes"):
                return {}
            placeholders = ",".join("?" for _ in episode_ids)
            rows = con.execute(
                f"""
                SELECT id, title, summary, source_memory_ids_json, source_kind,
                       occurred_at, created_at, status
                FROM episodes
                WHERE id IN ({placeholders})
                """,
                tuple(episode_ids),
            ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            data = dict(row)
            data["source_memory_ids"] = _safe_json_list(
                data.pop("source_memory_ids_json", "[]")
            )
            out[str(data["id"])] = data
        return out
    except Exception:
        return {}


def _scar_class_from(summary: str, row: dict[str, Any]) -> str:
    match = _SCAR_CLASS_RE.search(summary or "")
    if match:
        return match.group(1)
    dedup = str(row.get("dedup_key") or "")
    if ":" in dedup:
        return dedup.split(":", 1)[1]
    return "scar"


def _correction_quote(summary: str) -> str:
    match = _CORRECTION_RE.search(summary or "")
    return match.group(1) if match else ""


def _consequence_corrections_by_ref(path: Path, refs: list[str]) -> dict[str, str]:
    ids: list[int] = []
    ref_by_id: dict[int, str] = {}
    for ref in refs:
        if not ref.startswith("consequence:"):
            continue
        try:
            row_id = int(ref.split(":", 1)[1])
        except ValueError:
            continue
        ids.append(row_id)
        ref_by_id[row_id] = ref
    if not ids:
        return {}
    try:
        con = _ro_connect(path)
        if con is None:
            return {}
        with closing(con):
            con.execute("PRAGMA query_only=ON")
            if not _table_exists(con, "events"):
                return {}
            placeholders = ",".join("?" for _ in ids)
            rows = con.execute(
                f"SELECT id, outcome, feedback FROM events WHERE id IN ({placeholders})",
                tuple(ids),
            ).fetchall()
    except Exception:
        return {}
    out: dict[str, str] = {}
    for row in rows:
        ref = ref_by_id.get(int(row[0]))
        correction = str(row[2] or row[1] or "").strip()
        if ref and correction:
            out[ref] = correction
    return out


def scars_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    coverage = ScarSidecar.coverage_at(paths.scar_sidecar_db)
    sidecar_rows = ScarSidecar.list_all_at(paths.scar_sidecar_db)
    episode_ids = [str(row.get("active_episode_id") or "") for row in sidecar_rows]
    episodes = _episode_rows_by_id(paths.episodes_db, episode_ids)
    all_refs = [str(ref) for row in sidecar_rows for ref in (row.get("receipt_refs") or [])]
    consequence_corrections = _consequence_corrections_by_ref(
        paths.memory_dir / "consequence_memory.db",
        all_refs,
    )
    recent = []
    for row in sidecar_rows[-6:]:
        episode_id = str(row.get("active_episode_id") or "")
        episode = episodes.get(episode_id, {})
        summary = str(episode.get("summary") or "")
        receipt_refs = list(row.get("receipt_refs") or [])
        correction_quote = next(
            (
                consequence_corrections[ref]
                for ref in receipt_refs
                if ref in consequence_corrections
            ),
            _correction_quote(summary),
        )
        recent.append(
            {
                "episode_id": episode_id,
                "scar_class": _scar_class_from(summary, row),
                "correction_quote": correction_quote,
                "receipt_refs": receipt_refs,
                "occurred_at": episode.get("occurred_at") or row.get("last_ts"),
            }
        )
    return {
        "status": coverage.get("status", "unavailable"),
        "active_episodes": int(coverage.get("active_episodes") or 0),
        "total_occurrences": int(coverage.get("total_occurrences") or 0),
        "coverage": coverage.get("retention", "append_preserving_all_time"),
        "recent": recent,
    }


def narrative_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    health = narrative_health(paths)
    links = dict(health.get("links") or {})
    links.setdefault("strings", 0)
    links.setdefault("same_thread", 0)
    links.setdefault("because_of", 0)
    same_thread_state = "present" if int(links.get("same_thread") or 0) else "honest_empty"
    return {
        "status": health.get("status", "unavailable"),
        "links": links,
        "same_thread_state": same_thread_state,
        "empty_is_error": False,
    }


def self_evidence_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    health = a6_self_evidence_health(paths)
    return {
        "status": health.get("status", "unavailable"),
        "label": "integrity receipt count",
        "coverage_note": "third-person receipt counts; no grade",
        "merged_events": health.get("merged_events", {}),
        "sources": health.get("sources", {}),
    }


def interaction_preferences_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    health = interaction_preferences_health(paths)
    rows = list_all_readonly(paths.interaction_preferences_db)
    active_rows = [row for row in rows if row.status == "active"]
    retracted_rows = [row for row in rows if row.status == "retracted"]
    return {
        "status": health.get("status", "unavailable"),
        "active": len(active_rows),
        "retracted": len(retracted_rows),
        "total": len(rows),
        "receipt_path": "capture and retraction are T2-receipted relationship facts",
        "active_owner_statements": [row.owner_statement for row in active_rows],
    }


def continuity_section(paths: CockpitSourcePaths) -> dict[str, Any]:
    health = a2_continuity_health(paths)
    runs = int(health.get("probe_runs") or 0)
    latest_verdict = "insufficient_data" if runs < 2 else "available"
    return {
        "status": health.get("status", "unavailable"),
        "probe_runs": runs,
        "latest_verdict": latest_verdict,
    }


def metabolic_section(_paths: CockpitSourcePaths) -> dict[str, Any]:
    return {
        "status": "available",
        "quiet_day_stub_type": "quiet_day_stub",
        "durable_tier": "self_observed",
        "summary": "quiet glances stay RAM-only; durable self-observation is labeled self_observed",
    }


def build_memory_room(paths: CockpitSourcePaths | None = None) -> dict[str, Any]:
    source_paths = paths or CockpitSourcePaths.defaults()
    return {
        "kind": "cockpit_v2_memory_room",
        "narrative": narrative_section(source_paths),
        "scars": scars_section(source_paths),
        "self_evidence": self_evidence_section(source_paths),
        "interaction_preferences": interaction_preferences_section(source_paths),
        "continuity": continuity_section(source_paths),
        "metabolic": metabolic_section(source_paths),
        "a7_interiority": a7_interiority_health(source_paths),
    }


def render_memory_room_dom_text(memory_room: dict[str, Any]) -> str:
    """Return the exact safe text shape the v2 Memory panel is allowed to show.

    The browser renders richer markup, but it uses this same field vocabulary:
    counts, receipt labels, and quoted correction text. A7 content is sealed to
    counts by construction.
    """
    narrative = memory_room.get("narrative") or {}
    links = narrative.get("links") or {}
    scars = memory_room.get("scars") or {}
    evidence = memory_room.get("self_evidence") or {}
    merged = evidence.get("merged_events") or {}
    continuity = memory_room.get("continuity") or {}
    prefs = memory_room.get("interaction_preferences") or {}
    a7 = memory_room.get("a7_interiority") or {}

    lines = [
        "Narrative Spine",
        f"strings {int(links.get('strings') or 0)}",
        f"same_thread {int(links.get('same_thread') or 0)}",
        f"because_of {int(links.get('because_of') or 0)}",
        f"same_thread_state {narrative.get('same_thread_state', 'unknown')}",
        "A1 Scars",
        f"active scars {int(scars.get('active_episodes') or 0)}",
    ]
    for scar in scars.get("recent") or []:
        quote = str(scar.get("correction_quote") or "")
        refs = ", ".join(str(ref) for ref in (scar.get("receipt_refs") or []))
        lines.append(f'The correction: "{quote}"')
        lines.append(f"receipts {refs}")
    lines.extend(
        [
            "A6 Self-Evidence",
            str(evidence.get("label") or "integrity receipt count"),
            f"distinct integrity events {int(merged.get('distinct_integrity_events') or 0)}",
            "A2 Continuity",
            str(continuity.get("latest_verdict") or "insufficient_data"),
            "Interaction Preferences",
            f"active {int(prefs.get('active') or 0)} retracted {int(prefs.get('retracted') or 0)}",
            str(prefs.get("receipt_path") or ""),
            "A7 Interiority",
            f"private thought count {int(a7.get('private_thought_count') or 0)}",
            f"fresh moment receipt count {int(a7.get('fresh_moment_receipt_count') or 0)}",
            "content sealed" if a7.get("content_policy") == "sealed" else "content unavailable",
        ]
    )
    return "\n".join(line for line in lines if line)
