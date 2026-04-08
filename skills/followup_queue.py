"""
followup_queue.py — Maez's promise tracker.
When Maez says it will get back to Rohit, it stores the task here.
The reasoning cycle picks it up and delivers unprompted.
"""

import logging
import os
import re
import sqlite3
import time
import uuid

logger = logging.getLogger("maez")

DB_PATH = '/home/rohit/maez/memory/followup.db'

FOLLOWUP_SIGNALS = [
    "i'll check", "i'll look into", "i'll find out", "i'll get back",
    "let me check", "let me look", "i'll investigate", "i'll monitor",
    "i'll keep an eye", "i'll dig into", "i'll research", "will update you",
    "i'll update", "will let you know", "i'll let you know",
]


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
                    delivered_at REAL
                )
            """)
            conn.commit()
        logger.info("FollowUpQueue initialized")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def add(self, task: str, original_msg: str = ""):
        fid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO followups (id, task, original_msg, created_at, due_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (fid, task, original_msg, now, now + 7200),
            )
            conn.commit()
        logger.info("[FOLLOWUP] Queued: %s", task[:80])
        return fid

    def get_pending(self) -> list:
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, task, original_msg, created_at FROM followups "
                "WHERE status='pending' AND due_by > ?",
                (now,),
            ).fetchall()
        return [{'id': r[0], 'task': r[1], 'original_msg': r[2], 'created_at': r[3]} for r in rows]

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
        """Check if reply contains follow-up language. Returns task string or empty."""
        reply_lower = reply_text.lower()
        for signal in FOLLOWUP_SIGNALS:
            if signal in reply_lower:
                # Extract the sentence containing the signal
                for sentence in re.split(r'[.!?\n]', reply_text):
                    if signal in sentence.lower():
                        return sentence.strip()
                return signal
        return ""
