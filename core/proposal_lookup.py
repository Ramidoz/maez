# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""proposal_lookup.py — structured lookup for Maez's proposal stores.

Built 2026-04-20 after a Telegram turn where the user asked "what is
proposal #25?" and the brain_loop fell back to `grep -r 'proposal 25'
/home/rohit/maez/` which hit vocab.json tokenizer noise. Proposals
live in SQLite, not markdown — the planner needed a dedicated surface.

Two stores are queried:
  - memory/evolution_track.db::candidates — self-edit proposals (the
    evolution system's candidate patches, e.g. candidate #25 that
    proposes lowering POLICY_EXPLORATORY_THRESHOLD from 0.7 to 0.6).
  - memory/dream_proposals.db::dream_proposals — soul / consolidation
    proposals emitted by the dream-state subsystem.

The ID space is independent across the two tables. A given ID may
exist in both, one, or neither. The return shape always includes a
`sources` list naming where the ID was found.

Read-only by construction. Fails open (found=False, no crash) when
either DB is missing or unreadable — a missing DB is a valid state
on a freshly-provisioned box.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_MAEZ_HOME = Path("/home/rohit/maez")

# Module-level paths so tests can monkey-patch them without touching
# the real prod DBs.
_EVOLUTION_DB = str(_MAEZ_HOME / "memory" / "evolution_track.db")
_DREAM_DB = str(_MAEZ_HOME / "memory" / "dream_proposals.db")


def _fetch_evolution_candidate(proposal_id: int) -> dict | None:
    """Query candidates table. Returns None on any failure — the caller
    treats that as 'not found in this source', not a crash."""
    # Pre-check: sqlite3.connect() on a nonexistent path silently
    # creates an empty file. Skip outright if the DB isn't there so
    # we don't leave zero-byte stray files on a freshly-provisioned
    # box (which would mask the missing-DB condition on later runs).
    if not Path(_EVOLUTION_DB).exists():
        return None
    try:
        conn = sqlite3.connect(_EVOLUTION_DB, timeout=1.5)
    except sqlite3.Error:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, state, target_file, weakness_description, "
            "diff_text, justification, created_at, validated_at, "
            "applied_at, resolved_at "
            "FROM candidates WHERE id = ?",
            (proposal_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    return dict(row)


def _fetch_dream_proposal(proposal_id: int) -> dict | None:
    if not Path(_DREAM_DB).exists():
        return None
    try:
        conn = sqlite3.connect(_DREAM_DB, timeout=1.5)
    except sqlite3.Error:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, created_at, insight, status, proposal_type, "
            "target_section, applied_at, reject_reason, unified_diff "
            "FROM dream_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    return dict(row)


def _render_evolution_summary(r: dict) -> str:
    """Compact multi-line rendering of an evolution candidate row.
    Diff is truncated to keep the tool-transcript tight."""
    lines = [
        f"evolution candidate #{r.get('id')}: state={r.get('state')}",
        f"  target_file: {r.get('target_file')}",
        f"  weakness: {r.get('weakness_description')}",
        f"  created_at: {r.get('created_at')}",
    ]
    if r.get("validated_at"):
        lines.append(f"  validated_at: {r.get('validated_at')}")
    if r.get("applied_at"):
        lines.append(f"  applied_at: {r.get('applied_at')}")
    diff = r.get("diff_text") or ""
    if diff:
        if len(diff) > 500:
            diff = diff[:500] + "\n  ...[diff truncated]"
        lines.append("  diff:")
        for dl in diff.splitlines():
            lines.append(f"    {dl}")
    return "\n".join(lines)


def _render_dream_summary(r: dict) -> str:
    lines = [
        f"dream proposal #{r.get('id')}: status={r.get('status')}",
        f"  proposal_type: {r.get('proposal_type')}",
        f"  target_section: {r.get('target_section')}",
        f"  created_at: {r.get('created_at')}",
    ]
    insight = r.get("insight") or ""
    if insight:
        if len(insight) > 300:
            insight = insight[:300] + "…"
        lines.append(f"  insight: {insight}")
    return "\n".join(lines)


def lookup(proposal_id: Any) -> dict:
    """Look up a proposal by ID across both stores.

    Returns a dict:
      {
        "found": bool,
        "sources": list[str],   # subset of {"evolution_candidates",
                                #             "dream_proposals"}
        "summary": str,         # human-readable rendering
      }
    """
    try:
        pid = int(proposal_id)
    except (TypeError, ValueError):
        return {
            "found": False,
            "sources": [],
            "summary": f"invalid proposal_id {proposal_id!r} "
                       f"— must be an integer.",
        }

    sources: list[str] = []
    summary_parts: list[str] = []

    evo = _fetch_evolution_candidate(pid)
    if evo is not None:
        sources.append("evolution_candidates")
        summary_parts.append(_render_evolution_summary(evo))

    dream = _fetch_dream_proposal(pid)
    if dream is not None:
        sources.append("dream_proposals")
        summary_parts.append(_render_dream_summary(dream))

    if not sources:
        return {
            "found": False,
            "sources": [],
            "summary": f"proposal #{pid} not found in "
                       f"evolution_track.db or dream_proposals.db.",
        }

    return {
        "found": True,
        "sources": sources,
        "summary": "\n\n".join(summary_parts),
    }
