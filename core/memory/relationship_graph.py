# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Append-only temporal relationship graph (ADR 0019).

Nodes are entities (people, concepts, models, services, artefacts).
Edges are relationships between them with explicit validity windows
and evidence pointers. The store enforces three invariants at the
data layer:

1. Every edge cites at least one source episode ID OR one source
   memory ID (no claim without evidence — graph fabrication
   cannot be smuggled in by direct insert).
2. Corrections are :meth:`supersede`, never delete: the old edge
   stays with ``status='superseded'`` and a bounded ``valid_to``;
   a new edge is created.
3. ``upsert_node`` is idempotent on ``(label, kind)`` so the graph
   does not silently fragment across duplicate entities.

This module is the v1 SQLite implementation. The interface
(``RelationshipGraph.upsert_node`` / ``.add_edge`` / ``.get_edge`` /
``.supersede``) is the abstraction boundary that lets a future
backend swap (Postgres, Graphiti, etc.) land without touching
callers.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(label, kind)
);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    object_id TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'active',
    source_episode_ids_json TEXT NOT NULL,
    source_memory_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS edges_subject_idx ON edges(subject_id);
CREATE INDEX IF NOT EXISTS edges_object_idx ON edges(object_id);
CREATE INDEX IF NOT EXISTS edges_relation_idx ON edges(relation);
CREATE INDEX IF NOT EXISTS edges_status_idx ON edges(status);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonicalise_iso(value: Optional[str], *, field_name: str) -> Optional[str]:
    """Parse an ISO-8601 string and re-emit it in the canonical
    ``+00:00`` UTC form so string comparison is sound. Audit M1+M2
    fix from 2026-04-29: naive ``str`` comparison silently misordered
    ``Z``-suffixed vs ``+00:00`` vs naive timestamps. Now every
    timestamp that crosses the API boundary is normalised at entry.

    Raises ``ValueError`` on malformed input — caller error, not
    silent corruption (audit M2).

    Naive timestamps are interpreted as UTC for backward-compat with
    the existing ``_now_iso`` shape, which is timespec-second UTC.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Python 3.11+ ``datetime.fromisoformat`` accepts ``Z`` suffix.
    # On 3.10 we'd need a polyfill; Maez requires 3.12 so this is safe.
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name}: not a valid ISO-8601 timestamp: {text!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds")


class RelationshipGraph:
    """Append-only temporal relationship graph backed by SQLite (v1).

    Edges always carry evidence. Corrections supersede; they never
    delete. There is no delete / remove / drop API by design.
    """

    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.executescript(_SCHEMA)
            # Slice 4 backfill: pre-temporal-windows edges had
            # ``valid_from = NULL``. Adopt ``created_at`` as the
            # implicit lower bound so temporal queries can answer
            # "what was true at time T?" against the historical
            # record. Idempotent — ``WHERE valid_from IS NULL``
            # only updates rows that haven't been migrated yet.
            c.execute("UPDATE edges SET valid_from = created_at WHERE valid_from IS NULL")

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self._path))
        c.row_factory = sqlite3.Row
        return c

    def upsert_node(self, *, label: str, kind: str) -> str:
        now = _now_iso()
        with self._connect() as c:
            row = c.execute(
                "SELECT id FROM nodes WHERE label = ? AND kind = ?",
                (label, kind),
            ).fetchone()
            if row is not None:
                c.execute(
                    "UPDATE nodes SET updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                return row["id"]
            node_id = f"n-{uuid.uuid4().hex[:12]}"
            c.execute(
                "INSERT INTO nodes (id, label, kind, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (node_id, label, kind, now, now),
            )
            return node_id

    def add_edge(
        self,
        *,
        subject_id: str,
        relation: str,
        object_id: str,
        source_episode_ids: Sequence[str],
        source_memory_ids: Sequence[str],
        confidence: float = 0.7,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> str:
        if not source_episode_ids and not source_memory_ids:
            raise ValueError(
                "Edge requires at least one source_episode_id or "
                "source_memory_id (ADR 0019 evidence requirement)"
            )
        now = _now_iso()
        edge_id = f"e-{uuid.uuid4().hex[:12]}"
        # Slice 4: canonicalise + validate temporal bounds. Audit
        # M1+M2 fix (every timestamp crossing the API enters in the
        # same +00:00 form so string comparison is sound). Audit
        # essential-#8 fix (no logical contradictions like
        # ``valid_to <= valid_from`` get stored).
        valid_from = _canonicalise_iso(valid_from, field_name="valid_from")
        valid_to = _canonicalise_iso(valid_to, field_name="valid_to")
        if valid_from is None:
            # Default to ``created_at`` so temporal queries can
            # always answer about every edge.
            valid_from = now
        if valid_to is not None and valid_to <= valid_from:
            raise ValueError(
                f"valid_to ({valid_to}) must be strictly after "
                f"valid_from ({valid_from}); half-open interval "
                f"[valid_from, valid_to) requires valid_to > valid_from"
            )
        with self._connect() as c:
            c.execute(
                "INSERT INTO edges ("
                "id, subject_id, relation, object_id, valid_from, "
                "valid_to, confidence, status, "
                "source_episode_ids_json, source_memory_ids_json, "
                "created_at, updated_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    edge_id,
                    subject_id,
                    relation,
                    object_id,
                    valid_from,
                    valid_to,
                    float(confidence),
                    "active",
                    json.dumps(list(source_episode_ids)),
                    json.dumps(list(source_memory_ids)),
                    now,
                    now,
                ),
            )
        return edge_id

    def get_edge(self, edge_id: str) -> Optional[dict]:
        with self._connect() as c:
            row = c.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return None if row is None else self._row_to_dict(row)

    def supersede(
        self,
        old_edge_id: str,
        *,
        subject_id: str,
        relation: str,
        object_id: str,
        source_episode_ids: Sequence[str],
        source_memory_ids: Sequence[str],
        confidence: float = 0.7,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
    ) -> str:
        old = self.get_edge(old_edge_id)
        if old is None:
            raise KeyError(f"Cannot supersede unknown edge: {old_edge_id}")
        new_edge_id = self.add_edge(
            subject_id=subject_id,
            relation=relation,
            object_id=object_id,
            source_episode_ids=source_episode_ids,
            source_memory_ids=source_memory_ids,
            confidence=confidence,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        bound = valid_from or _now_iso()
        now = _now_iso()
        with self._connect() as c:
            c.execute(
                "UPDATE edges SET status = 'superseded', "
                "valid_to = COALESCE(valid_to, ?), updated_at = ? "
                "WHERE id = ?",
                (bound, now, old_edge_id),
            )
        return new_edge_id

    def list_active(self, *, at_time: Optional[str] = None) -> list[dict]:  # noqa: C901
        """Return active edges, joined with their subject + object
        labels.

        - ``at_time=None`` (default): edges with ``status='active'``
          — what is true NOW. Mirrors the original lived_recall
          direct-SQL pattern but as the canonical public method.
        - ``at_time=<ISO-8601 string>``: edges that were active at
          that timestamp, regardless of current status. Half-open
          interval semantics ``[valid_from, valid_to)``: at the
          supersede boundary, the successor edge is the active one.
          Closes the audit gap "what did Rohit care about three
          months ago?" (Zep / Graphiti temporal-validity pattern).
          Malformed ``at_time`` raises ``ValueError`` (audit M2);
          ``Z`` / naive / ``+00:00`` forms all canonicalise to the
          same instant (audit M1).

        Each returned dict carries the edge fields plus
        ``subject_label`` and ``object_label`` for display, with
        ``source_episode_ids`` and ``source_memory_ids`` decoded
        from JSON.
        """
        with self._connect() as c:
            base_sql = (
                "SELECT e.*, "
                "       s.label AS subject_label, "
                "       s.kind AS subject_kind, "
                "       o.label AS object_label, "
                "       o.kind AS object_kind "
                "FROM edges e "
                "JOIN nodes s ON s.id = e.subject_id "
                "JOIN nodes o ON o.id = e.object_id "
            )
            if at_time is None:
                rows = c.execute(base_sql + "WHERE e.status = 'active'").fetchall()
            else:
                # Audit M1+M2: canonicalise + validate at function
                # entry so the predicate operates on the same
                # +00:00 form the stored timestamps now use.
                at_time_canonical = _canonicalise_iso(at_time, field_name="at_time")
                rows = c.execute(
                    base_sql
                    + "WHERE (e.valid_from IS NULL OR e.valid_from <= ?) "
                    + "  AND (e.valid_to IS NULL OR e.valid_to > ?)",
                    (at_time_canonical, at_time_canonical),
                ).fetchall()
        out: list[dict] = []
        for row in rows:
            d = dict(row)
            subject_label = d.pop("subject_label")
            object_label = d.pop("object_label")
            subject_kind = d.pop("subject_kind")
            object_kind = d.pop("object_kind")
            # Audit N1: defensive per-row JSON decode. One corrupt
            # cell shouldn't break the whole query for every other
            # caller. Empty list is the fail-open semantic here.
            try:
                d["source_episode_ids"] = json.loads(d.pop("source_episode_ids_json"))
            except (json.JSONDecodeError, TypeError):
                d.pop("source_episode_ids_json", None)
                d["source_episode_ids"] = []
            try:
                d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
            except (json.JSONDecodeError, TypeError):
                d.pop("source_memory_ids_json", None)
                d["source_memory_ids"] = []
            d["subject_label"] = subject_label
            d["object_label"] = object_label
            d["subject_kind"] = subject_kind
            d["object_kind"] = object_kind
            out.append(d)
        return out

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["source_episode_ids"] = json.loads(d.pop("source_episode_ids_json"))
        d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
        return d
