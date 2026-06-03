# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
quality_tracker.py — Reasoning quality feedback loop for Maez

Every action Maez proposes is recorded here with its outcome.
Maez queries this data periodically to understand what it gets right,
what gets ignored, and where it should adjust.

Outcomes:
- executed   : Tier 0/1 action ran automatically, no objection
- approved   : Tier 2/3 action explicitly approved by the owner
- cancelled  : the owner cancelled within the window (Tier 2/3)
- rejected   : Tier 3 action timed out without approval
- superseded : Action became irrelevant before execution

This data is Maez's mirror. Over time it learns what the owner values.
"""

import json
import logging
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("maez")

def _default_quality_db_path() -> str:
    """Resolve the quality DB default at call time. Phase-2 hygiene:
    core.paths.home() auto-detects the repo root on any install (dev
    box, CI runner, fresh clone). Fallback to the legacy hardcode is
    only reached if core.paths is unimportable for some exotic reason.
    """
    try:
        from core.paths import memory_dir as _memory_dir
        return str(_memory_dir() / "quality.db")
    except Exception:
        return '/home/rohit/maez/memory/quality.db'


DB_PATH = _default_quality_db_path()


def _approval_rate_from_audit_log(days: int) -> Optional[float]:
    """G.A.2: read owner approval rate from audit_log.db (where
    cockpit/decision-pipeline approvals actually land), not from
    quality.db (which only sees ActionEngine internal lifecycle
    outcomes).

    Returns the rate as a float in [0.0, 1.0], or None when the
    audit_log is missing / empty / has fewer than 3 decided rows
    in the window. ``format_insight_for_soul`` falls back to
    quality.db's rate on None to preserve the function's working
    contract during fresh deploys.

    Outcome mapping mirrors scripts/probe/maez_drift_report.py
    (G.A.1 commit): approved_and_ran + approved_and_failed →
    approved; rohit_rejected → rejected. Other outcomes
    (refused_by_will, expired, etc.) are ignored for rate
    computation."""
    try:
        from core import paths as _paths
        audit_db = _paths.memory_dir() / "audit_log.db"
    except Exception:
        audit_db = "/home/rohit/maez/memory/audit_log.db"
    if not os.path.exists(audit_db):
        return None
    cutoff = time.time() - days * 86400.0
    try:
        with closing(sqlite3.connect(audit_db)) as con, con:
            rows = con.execute(
                "SELECT outcome, COUNT(*) FROM audit_log "
                "WHERE outcome IS NOT NULL AND outcome_ts >= ? "
                "GROUP BY outcome",
                (cutoff,),
            ).fetchall()
    except sqlite3.Error:
        return None
    counts = {(o or ""): int(n) for o, n in rows}
    approved = (
        counts.get("approved_and_ran", 0)
        + counts.get("approved_and_failed", 0)
    )
    rejected = counts.get("rohit_rejected", 0)
    decided = approved + rejected
    if decided < 3:
        return None
    return approved / decided


class QualityTracker:
    """SQLite-backed tracker for Maez's action outcomes."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:  # transaction: commit on success / rollback on error
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_outcomes (
                    action_id       TEXT PRIMARY KEY,
                    tier            INTEGER NOT NULL,
                    action_type     TEXT NOT NULL,
                    reasoning       TEXT,
                    parameters      TEXT,
                    proposed_at     REAL NOT NULL,
                    outcome         TEXT,
                    resolved_at     REAL,
                    rohit_feedback  TEXT,
                    screen_activity TEXT,
                    focus_level     TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcome
                ON action_outcomes(outcome)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_type
                ON action_outcomes(action_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proposed_at
                ON action_outcomes(proposed_at)
            """)
            conn.commit()
        logger.info("QualityTracker initialized at %s", self.db_path)

    def record_proposed(self, action_id: str, tier: int, action_type: str,
                        reasoning: str, parameters: dict,
                        screen_activity: str = "", focus_level: str = ""):
        """Record an action the moment it is proposed."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO action_outcomes
                (action_id, tier, action_type, reasoning, parameters,
                 proposed_at, screen_activity, focus_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action_id, tier, action_type, reasoning,
                json.dumps(parameters), time.time(),
                screen_activity, focus_level,
            ))
            conn.commit()
        logger.debug("Quality: proposed %s (%s T%d)", action_id, action_type, tier)

    def record_outcome(self, action_id: str, outcome: str,
                       rohit_feedback: str = ""):
        """Record the outcome of an action."""
        valid = {'executed', 'approved', 'cancelled', 'rejected', 'superseded', 'failed'}
        if outcome not in valid:
            logger.warning("Invalid outcome '%s' for %s", outcome, action_id)
            return
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE action_outcomes
                SET outcome = ?, resolved_at = ?, rohit_feedback = ?
                WHERE action_id = ?
            """, (outcome, time.time(), rohit_feedback, action_id))
            conn.commit()
        logger.debug("Quality: %s → %s", action_id, outcome)

    def get_outcome(self, action_id: str) -> dict | None:
        """Session 11y: fetch a single action's recorded outcome for the
        grounded followup delivery path. Returns None if not found or the
        action has no recorded outcome yet.

        Shape matches what maez_daemon's followup delivery expects:
            {"status": "executed"|"cancelled"|"rejected"|...,
             "action_type": "...", "output": "", "error": ""}

        The action_outcomes table doesn't currently persist command output
        text — only the status label — so output/error come back empty.
        That's fine for now: the followup delivery message falls back to
        "Done — {description}" with no output detail, which is honest.
        When we need real output text (to say "install finished with exit
        0 and the new binary at /usr/bin/openrgb"), we can extend the
        schema to carry it."""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT action_type, outcome, resolved_at
                FROM action_outcomes
                WHERE action_id = ?
            """, (action_id,)).fetchone()
        if not row or not row['outcome']:
            return None
        return {
            'status': row['outcome'],
            'action_type': row['action_type'],
            'resolved_at': row['resolved_at'],
            'output': '',
            'error': '',
        }

    def get_stats(self, days: int = 7) -> dict:
        """Return outcome statistics for the last N days."""
        since = time.time() - (days * 86400)
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT outcome, action_type, COUNT(*) as count
                FROM action_outcomes
                WHERE proposed_at > ? AND outcome IS NOT NULL
                GROUP BY outcome, action_type
                ORDER BY count DESC
            """, (since,)).fetchall()

        stats = {
            'period_days': days,
            'by_outcome': {},
            'by_type': {},
            'total': 0,
            'approval_rate': 0.0,
            'top_ignored_types': [],
        }

        for row in rows:
            outcome, atype, count = row['outcome'], row['action_type'], row['count']
            stats['by_outcome'][outcome] = stats['by_outcome'].get(outcome, 0) + count
            if atype not in stats['by_type']:
                stats['by_type'][atype] = {}
            stats['by_type'][atype][outcome] = count
            stats['total'] += count

        decided = (stats['by_outcome'].get('approved', 0) +
                   stats['by_outcome'].get('cancelled', 0) +
                   stats['by_outcome'].get('rejected', 0))
        if decided > 0:
            stats['approval_rate'] = stats['by_outcome'].get('approved', 0) / decided

        ignored_by_type = {
            atype: counts.get('cancelled', 0) + counts.get('rejected', 0)
            for atype, counts in stats['by_type'].items()
        }
        stats['top_ignored_types'] = sorted(
            ignored_by_type.items(), key=lambda x: x[1], reverse=True
        )[:3]

        return stats

    def format_for_context(self, days: int = 7) -> str:
        """Format quality stats for injection into reasoning prompt."""
        stats = self.get_stats(days)
        if stats['total'] == 0:
            return "[SELF-REFLECTION] No action history yet. Still learning."

        lines = [f"[SELF-REFLECTION — last {days} days]"]
        lines.append(f"  Actions proposed: {stats['total']}")

        parts = []
        for outcome in ['executed', 'approved', 'cancelled', 'rejected']:
            if outcome in stats['by_outcome']:
                parts.append(f"{outcome}: {stats['by_outcome'][outcome]}")
        if parts:
            lines.append(f"  Outcomes: {', '.join(parts)}")

        if stats['approval_rate'] > 0:
            lines.append(f"  Approval rate: {stats['approval_rate']*100:.0f}%")

        ignored = [t for t, c in stats['top_ignored_types'] if c > 0]
        if ignored:
            lines.append(f"  Most ignored/cancelled: {', '.join(ignored)}")

        return "\n".join(lines)

    def format_insight_for_soul(self, days: int = 30) -> Optional[str]:
        """Generate a soul note if there's a meaningful pattern. Returns None if nothing.

        G.A.2 fix: ``approval_rate`` was originally read from this
        module's own ``get_stats`` which queries quality.db.
        Cockpit/decision-pipeline approvals don't write there —
        they write to ``memory/audit_log.db``. The original code
        therefore always saw 0% approval and either fired the
        soul-note constantly OR not at all (depending on
        ``total >= 3`` evaluation against quality.db's executed
        rows). Either way, Maez's self-reflection was reading the
        wrong source. This pulls the approval-rate signal from
        the right place; ``top_ignored_types`` continues to read
        from quality.db because that's the correct source for
        per-action-type rejection patterns at the ActionEngine
        layer.
        """
        stats = self.get_stats(days)
        # Override approval_rate with the audit_log-derived value.
        # `total` here is for the existing >=3 / >=20 thresholds
        # (action volume); the rate itself comes from the right DB.
        approval_rate = _approval_rate_from_audit_log(days)
        if approval_rate is None:
            # Fall back to quality.db rate when audit_log is
            # unavailable / empty — preserves the function's
            # working contract during deploys where audit_log
            # hasn't accumulated yet.
            approval_rate = stats['approval_rate']

        if stats['total'] < 3:
            return None

        insights = []

        if approval_rate < 0.4 and stats['total'] >= 3:
            insights.append(
                f"My action approval rate is {approval_rate*100:.0f}% "
                f"over {days} days. I am proposing too many actions the owner "
                f"doesn't want. I should raise my threshold."
            )

        for atype, count in stats['top_ignored_types']:
            if count >= 3:
                insights.append(
                    f"the owner has cancelled or rejected '{atype}' actions "
                    f"{count} times. I should stop proposing these unless "
                    f"the situation is clearly severe."
                )

        if approval_rate > 0.8 and stats['total'] >= 20:
            insights.append(
                f"My approval rate is {approval_rate*100:.0f}% "
                f"over {days} days. the owner trusts my judgment."
            )

        if not insights:
            return None

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return (
            f"[Self-observed pattern — {timestamp}]\n" +
            "\n".join(f"- {i}" for i in insights)
        )


def test():
    import tempfile
    db = tempfile.mktemp(suffix='.db')
    qt = QualityTracker(db_path=db)
    print("Testing QualityTracker...")

    qt.record_proposed('act_001', 1, 'clean_temp_files',
                       'Temp files over 2GB', {}, 'coding in VS Code', 'deep_work')
    qt.record_proposed('act_002', 2, 'restart_service',
                       'Service degraded', {}, 'idle', 'idle')
    qt.record_proposed('act_003', 3, 'install_package',
                       'Missing dependency', {}, 'coding', 'deep_work')

    qt.record_outcome('act_001', 'executed')
    qt.record_outcome('act_002', 'cancelled', 'not now')
    qt.record_outcome('act_003', 'approved', 'yes go ahead')

    print(qt.format_for_context())
    print()
    print(f"Stats: {qt.get_stats()}")
    print()
    print(f"Soul insight: {qt.format_insight_for_soul()}")

    os.unlink(db)
    print("\nSUCCESS")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
