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
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

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
    memory_voice TEXT,
    superseded_at TEXT,
    superseded_reason TEXT,
    superseded_by TEXT,
    felt_value REAL,
    felt_elapsed_s REAL,
    felt_phrase TEXT,
    felt_compute_version INTEGER
);

CREATE INDEX IF NOT EXISTS episodes_status_idx ON episodes(status);
CREATE INDEX IF NOT EXISTS episodes_occurred_idx ON episodes(occurred_at);
CREATE INDEX IF NOT EXISTS episodes_created_idx ON episodes(created_at);
CREATE INDEX IF NOT EXISTS episodes_source_kind_idx ON episodes(source_kind);
"""

# Provenance columns added after the v1 schema:
# - 2026-04-27: authorship/memory_voice for followup-doc ingestion.
# - 2026-06-02: supersession provenance for labeled retirements.
# Existing rows keep new fields NULL — readers must preserve the
# historical meaning of NULL rather than inferring a fresh label.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE episodes ADD COLUMN authorship TEXT",
    "ALTER TABLE episodes ADD COLUMN memory_voice TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_at TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_reason TEXT",
    "ALTER TABLE episodes ADD COLUMN superseded_by TEXT",
    # 2026-06-20: Slice-2 felt-time index (continuous lived time-sense). Frozen point-in-time
    # readings from the substrate; NEVER a durable band/bucket. Existing rows stay NULL.
    "ALTER TABLE episodes ADD COLUMN felt_value REAL",
    "ALTER TABLE episodes ADD COLUMN felt_elapsed_s REAL",
    "ALTER TABLE episodes ADD COLUMN felt_phrase TEXT",
    "ALTER TABLE episodes ADD COLUMN felt_compute_version INTEGER",
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

    def __init__(self, db_path: str, *, felt_time_reader: "Optional[Callable[[], Optional[dict]]]" = None):
        self._path = Path(db_path)
        self._felt_time_reader = felt_time_reader
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            with c:
                c.executescript(_SCHEMA)
                for stmt in _MIGRATIONS:
                    try:
                        c.execute(stmt)
                    except sqlite3.OperationalError:
                        # Column already exists. Idempotent re-run.
                        pass

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(str(self._path))
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

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
        felt_value = felt_elapsed_s = felt_phrase = felt_compute_version = None
        if self._felt_time_reader is not None:
            try:
                ctx = self._felt_time_reader()
                if ctx:
                    felt_value = ctx.get("felt_value")
                    felt_elapsed_s = ctx.get("seconds_since_last_owner_contact", ctx.get("felt_elapsed_s"))
                    felt_phrase = ctx.get("felt_phrase")
                    felt_compute_version = ctx.get("felt_compute_version")
            except Exception:
                felt_value = felt_elapsed_s = felt_phrase = felt_compute_version = None
        with self._connect() as c:
            with c:
                c.execute(
                    "INSERT INTO episodes ("
                    "id, created_at, occurred_at, title, summary, "
                    "participants_json, emotional_tone, importance, "
                    "open_loop, source_memory_ids_json, source_kind, status, "
                    "authorship, memory_voice, "
                    "felt_value, felt_elapsed_s, felt_phrase, felt_compute_version"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                        felt_value,
                        felt_elapsed_s,
                        felt_phrase,
                        felt_compute_version,
                    ),
                )
        return episode_id

    def get(self, episode_id: str) -> Optional[dict]:
        with self._connect() as c:
            row = c.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        return None if row is None else self._row_to_dict(row)

    def supersede(
        self,
        episode_id: str,
        *,
        reason: str,
        superseded_by: Optional[str] = None,
    ) -> bool:
        """Retire an episode without deleting it.

        Returns True when an active row is newly superseded. Returns False when
        the row is already non-active, preserving its existing supersession
        provenance. Raises KeyError for an unknown episode, and ValueError for
        a blank reason or unverifiable successor.
        """
        row = self.get(episode_id)
        if row is None:
            raise KeyError(f"Cannot supersede unknown episode: {episode_id}")
        if row["status"] != "active":
            return False
        if not (reason or "").strip():
            raise ValueError("supersede requires a non-blank reason")
        if superseded_by is not None:
            if superseded_by == episode_id:
                raise ValueError("superseded_by must not be the episode itself")
            if self.get(superseded_by) is None:
                raise ValueError(
                    f"superseded_by must resolve to an existing episode: {superseded_by}"
                )
        with self._connect() as c:
            with c:
                c.execute(
                    "UPDATE episodes SET status = 'superseded', "
                    "superseded_at = ?, superseded_reason = ?, superseded_by = ? "
                    "WHERE id = ?",
                    (_now_iso(), reason, superseded_by, episode_id),
                )
        return True

    def list_active(self) -> list[dict]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT * FROM episodes WHERE status = 'active' ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def active_count_and_newest_time(self) -> tuple[int, Optional[str]]:
        """Return active count and newest event/create timestamp without row scans."""
        with self._connect() as c:
            row = c.execute(
                "SELECT COUNT(*) AS n, MAX(COALESCE(occurred_at, created_at)) AS newest "
                "FROM episodes WHERE status = 'active'"
            ).fetchone()
        if row is None:
            return 0, None
        return int(row["n"] or 0), row["newest"]

    def counts_by_status_and_source_kind(self) -> dict:
        """Return content-free aggregate counts for body/health surfaces."""
        with self._connect() as c:
            rows = c.execute(
                "SELECT status, source_kind, COUNT(*) AS n "
                "FROM episodes GROUP BY status, source_kind"
            ).fetchall()
        by_status: dict[str, int] = {}
        by_source_kind: dict[str, int] = {}
        total = 0
        for row in rows:
            status = str(row["status"] or "unknown")
            source_kind = str(row["source_kind"] or "unknown")
            n = int(row["n"] or 0)
            total += n
            by_status[status] = by_status.get(status, 0) + n
            by_source_kind[source_kind] = by_source_kind.get(source_kind, 0) + n
        return {
            "total": total,
            "active": by_status.get("active", 0),
            "superseded": by_status.get("superseded", 0),
            "reflection": by_source_kind.get("reflection", 0),
            "by_status": by_status,
            "by_source_kind": by_source_kind,
        }

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
        from core.time.temporal_spine import try_canonical_utc

        start_utc = try_canonical_utc(window_start, field_name="event_at")
        end_utc = try_canonical_utc(window_end, field_name="event_at")
        if start_utc is None or end_utc is None:
            return []
        candidate_start_day = (start_utc - timedelta(days=2)).date().isoformat()
        candidate_end_day = (end_utc + timedelta(days=2)).date().isoformat()
        with self._connect() as c:
            timeout = max(0, int(busy_timeout_ms))
            c.execute(f"PRAGMA busy_timeout = {timeout}")
            rows = c.execute(
                "SELECT * FROM episodes "
                "WHERE status = 'active' "
                "AND substr(COALESCE(occurred_at, created_at), 1, 10) >= ? "
                "AND substr(COALESCE(occurred_at, created_at), 1, 10) <= ? "
                "ORDER BY COALESCE(occurred_at, created_at) DESC",
                (candidate_start_day, candidate_end_day),
            ).fetchall()
        matches: list[tuple[datetime, dict]] = []
        for row in rows:
            item = self._row_to_dict(row)
            raw_time = item.get("occurred_at") or item.get("created_at")
            event_time = try_canonical_utc(raw_time, field_name="event_at")
            if event_time is None:
                continue
            if not start_utc <= event_time < end_utc:
                continue
            matches.append((event_time, item))
        matches.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in matches[: int(limit)]]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["participants"] = json.loads(d.pop("participants_json"))
        d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
        return d
