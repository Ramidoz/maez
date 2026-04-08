"""
quality_tracker.py — Reasoning quality feedback loop for Maez

Every action Maez proposes is recorded here with its outcome.
Maez queries this data periodically to understand what it gets right,
what gets ignored, and where it should adjust.

Outcomes:
- executed   : Tier 0/1 action ran automatically, no objection
- approved   : Tier 2/3 action explicitly approved by Rohit
- cancelled  : Rohit cancelled within the window (Tier 2/3)
- rejected   : Tier 3 action timed out without approval
- superseded : Action became irrelevant before execution

This data is Maez's mirror. Over time it learns what Rohit values.
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("maez")

DB_PATH = '/home/rohit/maez/memory/quality.db'


class QualityTracker:
    """SQLite-backed tracker for Maez's action outcomes."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
        valid = {'executed', 'approved', 'cancelled', 'rejected', 'superseded'}
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
        """Generate a soul note if there's a meaningful pattern. Returns None if nothing."""
        stats = self.get_stats(days)
        if stats['total'] < 3:
            return None

        insights = []

        if stats['approval_rate'] < 0.4 and stats['total'] >= 3:
            insights.append(
                f"My action approval rate is {stats['approval_rate']*100:.0f}% "
                f"over {days} days. I am proposing too many actions Rohit "
                f"doesn't want. I should raise my threshold."
            )

        for atype, count in stats['top_ignored_types']:
            if count >= 3:
                insights.append(
                    f"Rohit has cancelled or rejected '{atype}' actions "
                    f"{count} times. I should stop proposing these unless "
                    f"the situation is clearly severe."
                )

        if stats['approval_rate'] > 0.8 and stats['total'] >= 20:
            insights.append(
                f"My approval rate is {stats['approval_rate']*100:.0f}% "
                f"over {days} days. Rohit trusts my judgment."
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
