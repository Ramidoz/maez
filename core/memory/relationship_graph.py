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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["source_episode_ids"] = json.loads(d.pop("source_episode_ids_json"))
        d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
        return d
