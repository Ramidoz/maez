# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Append-only episode store for the lived-memory layer (ADR 0019).

An episode is a high-signal moment promoted out of raw / daily / core
memory: a correction, a promise, an unresolved thread, an emotional
signal. The store enforces two invariants at the data layer:

1. Every episode cites at least one source memory ID (no orphan
   narrative — fabrication cannot be smuggled in by direct insert).
2. No delete API. Corrections accumulate as new rows; history is
   structural, not optional.

This module is the v1 SQLite implementation. The interface
(``EpisodeStore.add`` / ``.get`` / ``.list_active``) is the abstraction
boundary that lets a future backend swap (Postgres, Graphiti, etc.)
land without touching callers.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    occurred_at TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    participants_json TEXT NOT NULL,
    emotional_tone TEXT,
    importance INTEGER NOT NULL DEFAULT 3,
    open_loop TEXT,
    source_memory_ids_json TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    authorship TEXT,
    memory_voice TEXT
);

CREATE INDEX IF NOT EXISTS episodes_status_idx ON episodes(status);
CREATE INDEX IF NOT EXISTS episodes_occurred_idx ON episodes(occurred_at);
CREATE INDEX IF NOT EXISTS episodes_created_idx ON episodes(created_at);
CREATE INDEX IF NOT EXISTS episodes_source_kind_idx ON episodes(source_kind);
"""

# Provenance columns added 2026-04-27 for followup-doc ingestion.
# Existing rows keep authorship/memory_voice NULL — readers must
# treat NULL as "Maez-authored, first-person" (the only mode that
# existed before).
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE episodes ADD COLUMN authorship TEXT",
    "ALTER TABLE episodes ADD COLUMN memory_voice TEXT",
)


def _now_iso() -> str:
    # Microsecond precision: two episodes added within the same
    # second must still sort deterministically by created_at, which
    # the temporal-echo finder relies on for the recent/older split.
    # Pre-2026-04-27 this was second-precision and silently ambiguous
    # for any ingestion burst.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class EpisodeStore:
    """Append-only episode store backed by SQLite (v1).

    Evidence-ID requirement is enforced in :meth:`add`. There is no
    delete / remove / drop API by design — the never-delete-Maez-memory
    covenant is structural here.
    """

    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as c:
            with c:
                c.executescript(_SCHEMA)
                for stmt in _MIGRATIONS:
                    try:
                        c.execute(stmt)
                    except sqlite3.OperationalError:
                        # Column already exists. Idempotent re-run.
                        pass

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self._path))
        c.row_factory = sqlite3.Row
        return c

    def add(
        self,
        *,
        title: str,
        summary: str,
        participants: Sequence[str],
        source_memory_ids: Sequence[str],
        source_kind: str,
        occurred_at: Optional[str] = None,
        emotional_tone: Optional[str] = None,
        importance: int = 3,
        open_loop: Optional[str] = None,
        authorship: Optional[str] = None,
        memory_voice: Optional[str] = None,
    ) -> str:
        if not source_memory_ids:
            raise ValueError(
                "Episode requires at least one source_memory_id (ADR 0019 evidence requirement)"
            )
        episode_id = f"ep-{uuid.uuid4().hex[:12]}"
        with closing(self._connect()) as c:
            with c:
                c.execute(
                    "INSERT INTO episodes ("
                    "id, created_at, occurred_at, title, summary, "
                    "participants_json, emotional_tone, importance, "
                    "open_loop, source_memory_ids_json, source_kind, status, "
                    "authorship, memory_voice"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        episode_id,
                        _now_iso(),
                        occurred_at,
                        title,
                        summary,
                        json.dumps(list(participants)),
                        emotional_tone,
                        int(importance),
                        open_loop,
                        json.dumps(list(source_memory_ids)),
                        source_kind,
                        "active",
                        authorship,
                        memory_voice,
                    ),
                )
        return episode_id

    def get(self, episode_id: str) -> Optional[dict]:
        with closing(self._connect()) as c:
            row = c.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        return None if row is None else self._row_to_dict(row)

    def list_active(self) -> list[dict]:
        with closing(self._connect()) as c:
            rows = c.execute(
                "SELECT * FROM episodes WHERE status = 'active' ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def active_count_and_newest_time(self) -> tuple[int, Optional[str]]:
        """Return active count and newest event/create timestamp without row scans."""
        with closing(self._connect()) as c:
            row = c.execute(
                "SELECT COUNT(*) AS n, MAX(COALESCE(occurred_at, created_at)) AS newest "
                "FROM episodes WHERE status = 'active'"
            ).fetchone()
        if row is None:
            return 0, None
        return int(row["n"] or 0), row["newest"]

    def list_active_in_window(
        self,
        *,
        window_start: str,
        window_end: str,
        limit: int,
        busy_timeout_ms: int = 150,
    ) -> list[dict]:
        """Return active episodes in a bounded wall-clock window.

        The query uses ``occurred_at`` when present and falls back to
        ``created_at`` for older rows. Callers pass ``limit=max_items + 1`` when
        they need truncation detection without materializing the whole store.
        """
        with closing(self._connect()) as c:
            timeout = max(0, int(busy_timeout_ms))
            c.execute(f"PRAGMA busy_timeout = {timeout}")
            rows = c.execute(
                "SELECT * FROM episodes "
                "WHERE status = 'active' "
                "AND ("
                "  (occurred_at IS NOT NULL AND occurred_at >= ? AND occurred_at < ?) "
                "  OR (occurred_at IS NULL AND created_at >= ? AND created_at < ?)"
                ") "
                "ORDER BY COALESCE(occurred_at, created_at) DESC "
                "LIMIT ?",
                (
                    window_start,
                    window_end,
                    window_start,
                    window_end,
                    int(limit),
                ),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["participants"] = json.loads(d.pop("participants_json"))
        d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
        return d
