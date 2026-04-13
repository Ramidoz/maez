"""
core/fast_conversation_log.py — Session 11d, staging-only.

Tiny SQLite-backed append-only conversation log for the fast reply prototype.
Lets consecutive fast_reply() calls stitch context across requests for the
same trust_scope without depending on any daemon-owned state.

Schema (one table, intentionally minimal):

  fast_turns
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    trust_scope TEXT    NOT NULL
    role        TEXT    NOT NULL CHECK (role IN ('user', 'maez'))
    text        TEXT    NOT NULL
    created_at  REAL    NOT NULL                  -- unix ts

  index: (trust_scope, id) for tail reads

Public API:
    log = FastConversationLog()                  -- default db path
    log.append('rohit', 'user', 'hi')
    log.append('rohit', 'maez', 'hey')
    log.recent('rohit', n=8) -> list[TurnRecord]  -- newest last (chronological)
    log.clear('rohit')
    log.count('rohit') -> int

Staging-only:
  • Default db path: /home/rohit/maez/memory/fast_conversation_log.db
    (separate file from any live daemon DB; daemon never opens this path)
  • Not imported by daemon/maez_daemon.py
  • Intended to be wiped freely while iterating
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from core.fast_prompt_builder import TurnRecord


DEFAULT_DB_PATH = '/home/rohit/maez/memory/fast_conversation_log.db'


class FastConversationLog:
    """Append-only per-trust-scope conversation log. Thread-safe."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        # Ensure parent dir exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        # check_same_thread=False because we hold our own RLock around all
        # access; sqlite3 itself is fine with multi-thread under that pattern.
        c = sqlite3.connect(self.db_path, check_same_thread=False)
        c.execute('PRAGMA journal_mode=WAL')
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS fast_turns (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trust_scope TEXT NOT NULL,
                    role        TEXT NOT NULL CHECK (role IN ('user', 'maez')),
                    text        TEXT NOT NULL,
                    created_at  REAL NOT NULL
                )
            ''')
            c.execute('''
                CREATE INDEX IF NOT EXISTS ix_fast_turns_scope_id
                ON fast_turns (trust_scope, id)
            ''')

    # ── writes ──────────────────────────────────────────────────────
    def append(self, trust_scope: str, role: str, text: str) -> int:
        if role not in ('user', 'maez'):
            raise ValueError(f"role must be 'user' or 'maez', got {role!r}")
        if not text:
            return -1
        with self._lock, self._conn() as c:
            cur = c.execute(
                'INSERT INTO fast_turns (trust_scope, role, text, created_at) '
                'VALUES (?, ?, ?, ?)',
                (trust_scope, role, text, time.time()),
            )
            return cur.lastrowid or -1

    def clear(self, trust_scope: str) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                'DELETE FROM fast_turns WHERE trust_scope = ?', (trust_scope,)
            )
            return cur.rowcount

    # ── reads ──────────────────────────────────────────────────────
    def recent(self, trust_scope: str, n: int = 8) -> list[TurnRecord]:
        """Return the most recent n turns in chronological order (oldest→newest)."""
        if n <= 0:
            return []
        with self._lock, self._conn() as c:
            rows = c.execute(
                'SELECT role, text FROM fast_turns '
                'WHERE trust_scope = ? '
                'ORDER BY id DESC '
                'LIMIT ?',
                (trust_scope, n),
            ).fetchall()
        # rows are newest-first; reverse for chronological order
        rows.reverse()
        return [TurnRecord(role=r, text=t) for (r, t) in rows]

    def count(self, trust_scope: str) -> int:
        with self._lock, self._conn() as c:
            row = c.execute(
                'SELECT COUNT(*) FROM fast_turns WHERE trust_scope = ?',
                (trust_scope,),
            ).fetchone()
            return int(row[0]) if row else 0


# ── module-level singleton ─────────────────────────────────────────────
_GLOBAL_LOG: Optional[FastConversationLog] = None
_GLOBAL_LOCK = threading.Lock()


def get_log() -> FastConversationLog:
    global _GLOBAL_LOG
    with _GLOBAL_LOCK:
        if _GLOBAL_LOG is None:
            _GLOBAL_LOG = FastConversationLog()
        return _GLOBAL_LOG
