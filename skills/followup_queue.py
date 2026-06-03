# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
followup_queue.py — Maez's promise tracker.

Session 11y: this used to scrape any "I'll check" / "will let you know"
phrase out of Maez's replies and queue it as a task. The delivery loop
then asked the LLM to "deliver on your promise" without any grounded
evidence, which produced fabricated completions like "I've finished
installing maez-cli" for work that never happened.

The table still exists for GROUNDED commitments — a caller that has
just queued a real action_engine task can commit a followup keyed to
that action's id, and the delivery loop will fetch the real action
result to report back. Text-promise extraction is dead.
"""

import logging
import os
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("maez")

try:
    from core.infra import paths as _paths
    DB_PATH = str(_paths.memory_dir() / "followup.db")
except Exception:
    from pathlib import Path as _Path
    DB_PATH = str(
        _Path(__file__).resolve().parent.parent
        / "memory" / "followup.db"
    )


class FollowUpQueue:

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS followups (
                    id          TEXT PRIMARY KEY,
                    task        TEXT NOT NULL,
                    original_msg TEXT,
                    created_at  REAL NOT NULL,
                    due_by      REAL NOT NULL,
                    status      TEXT DEFAULT 'pending',
                    delivered_at REAL,
                    action_id   TEXT
                )
            """)
            # Session 11y: add action_id column if the table was created
            # before this migration. SQLite throws on duplicate ADD COLUMN,
            # so we catch and ignore.
            try:
                conn.execute("ALTER TABLE followups ADD COLUMN action_id TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        logger.info("FollowUpQueue initialized")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:  # transaction: commit on success / rollback on error
                yield conn
        finally:
            conn.close()

    def add(self, task: str, original_msg: str = "", action_id: str = ""):
        """Register a commitment. In the post-11y world, callers SHOULD
        pass action_id pointing to a real action_engine entry — entries
        without one will not be auto-delivered.
        """
        fid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO followups (id, task, original_msg, created_at, due_by, action_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (fid, task, original_msg, now, now + 7200, action_id or None),
            )
            conn.commit()
        logger.info("[FOLLOWUP] Queued: %s (action_id=%s)", task[:80], action_id or "none")
        return fid

    def get_pending(self) -> list:
        """Return pending followups that are eligible for delivery.

        Session 11y: only returns entries with a non-null action_id. Legacy
        entries created by the old text-promise extractor have action_id
        NULL and are NEVER auto-delivered — they sit until expire_old()
        cleans them up.
        """
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, task, original_msg, created_at, action_id FROM followups "
                "WHERE status='pending' AND due_by > ? AND action_id IS NOT NULL",
                (now,),
            ).fetchall()
        return [
            {'id': r[0], 'task': r[1], 'original_msg': r[2],
             'created_at': r[3], 'action_id': r[4]}
            for r in rows
        ]

    def mark_delivered(self, fid: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE followups SET status='delivered', delivered_at=? WHERE id=?",
                (time.time(), fid),
            )
            conn.commit()
        logger.info("[FOLLOWUP] Delivered: %s", fid)

    def expire_old(self):
        now = time.time()
        with self._conn() as conn:
            count = conn.execute(
                "UPDATE followups SET status='expired' WHERE status='pending' AND due_by <= ?",
                (now,),
            ).rowcount
            conn.commit()
        if count:
            logger.info("[FOLLOWUP] Expired %d overdue followups", count)

    @staticmethod
    def extract_task(reply_text: str) -> str:
        """Session 11y: permanently neutered.

        Used to scrape phrases like "I'll check" out of reply text and
        queue them as tasks. The delivery loop then fabricated completions
        because there was no grounded action to reference. Always returns
        empty now. Callers should use FollowUpQueue().add() explicitly
        with an action_id that points to a real action_engine entry.
        """
        return ""
