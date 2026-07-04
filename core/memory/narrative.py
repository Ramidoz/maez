# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Narrative links for the lived episode store.

This module stores only non-derivable autobiography structure. Time order is
derived from episode timestamps by readers; it is never stored as ``follows``.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

_DURABLE_LINK_TYPES = {"same_thread", "strings", "because_of"}
_LINK_TRUSTS = {"derived", "confirmed"}
_PROPOSAL_KINDS = {"same_story"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS narrative_links (
    link_id TEXT PRIMARY KEY,
    link_key TEXT UNIQUE NOT NULL,
    from_episode_id TEXT NOT NULL,
    to_episode_id TEXT NOT NULL,
    link_type TEXT NOT NULL CHECK(link_type IN ('same_thread','strings','because_of')),
    trust TEXT NOT NULL CHECK(trust IN ('derived','confirmed')),
    evidence_json TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_evidence_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS narrative_links_from_idx ON narrative_links(from_episode_id);
CREATE INDEX IF NOT EXISTS narrative_links_to_idx ON narrative_links(to_episode_id);
CREATE INDEX IF NOT EXISTS narrative_links_type_idx ON narrative_links(link_type);
CREATE INDEX IF NOT EXISTS narrative_links_trust_idx ON narrative_links(trust);
CREATE INDEX IF NOT EXISTS narrative_links_status_idx ON narrative_links(status);

CREATE TABLE IF NOT EXISTS narrative_proposals (
    proposal_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('same_story')),
    ep_a TEXT NOT NULL,
    ep_b TEXT NOT NULL,
    embedder_id TEXT NOT NULL,
    distance REAL NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','promoted')),
    promoted_link_id TEXT
);

CREATE INDEX IF NOT EXISTS narrative_proposals_status_idx ON narrative_proposals(status);
CREATE INDEX IF NOT EXISTS narrative_proposals_pair_idx ON narrative_proposals(ep_a, ep_b);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _ordered_unique(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def link_key_for(
    link_type: str,
    from_episode_id: str,
    to_episode_id: str,
    *,
    hook_class: str | None = None,
) -> str:
    if link_type not in _DURABLE_LINK_TYPES:
        raise ValueError(f"unsupported durable narrative link_type: {link_type}")
    if not from_episode_id or not to_episode_id:
        raise ValueError("narrative link endpoints are required")
    if link_type == "same_thread":
        a, b = sorted((str(from_episode_id), str(to_episode_id)))
        return f"same_thread|{a}|{b}"
    if link_type == "strings":
        return f"strings|{from_episode_id}|{to_episode_id}"
    if not hook_class:
        raise ValueError("because_of link_key requires hook_class")
    return f"because_of|{from_episode_id}|{to_episode_id}|{hook_class}"


class NarrativeStore:
    """SQLite-backed narrative links stored beside lived episodes."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con, con:
            con.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(str(self.path))) as con:
            con.row_factory = sqlite3.Row
            yield con

    def upsert_link(
        self,
        *,
        link_type: str,
        from_episode_id: str,
        to_episode_id: str,
        trust: str,
        evidence_ids: Sequence[str],
        detector_version: str,
        hook_class: str | None = None,
    ) -> str:
        if trust not in _LINK_TRUSTS:
            raise ValueError(f"unsupported durable narrative trust: {trust}")
        ids = _ordered_unique([str(item) for item in evidence_ids])
        if not ids:
            raise ValueError("narrative link requires evidence_ids")
        if not detector_version:
            raise ValueError("narrative link requires detector_version")
        key = link_key_for(
            link_type,
            from_episode_id,
            to_episode_id,
            hook_class=hook_class,
        )
        evidence_entry = {
            "ids": ids,
            "detector_version": str(detector_version),
        }
        now = _now_iso()
        with self._connect() as con, con:
            row = con.execute(
                "SELECT * FROM narrative_links WHERE link_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                link_id = f"nlink-{uuid.uuid4().hex[:12]}"
                con.execute(
                    "INSERT INTO narrative_links "
                    "(link_id, link_key, from_episode_id, to_episode_id, link_type, "
                    "trust, evidence_json, detector_version, created_at, "
                    "last_evidence_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        link_id,
                        key,
                        str(from_episode_id),
                        str(to_episode_id),
                        str(link_type),
                        str(trust),
                        json.dumps([{**evidence_entry, "at": now}], sort_keys=True),
                        str(detector_version),
                        now,
                        now,
                        "active",
                    ),
                )
                return link_id
            evidence = self._decode_evidence(row["evidence_json"])
            for entry in evidence:
                if (
                    entry.get("ids") == evidence_entry["ids"]
                    and entry.get("detector_version") == evidence_entry["detector_version"]
                ):
                    return str(row["link_id"])
            evidence.append({**evidence_entry, "at": now})
            con.execute(
                "UPDATE narrative_links SET evidence_json = ?, last_evidence_at = ? "
                "WHERE link_key = ?",
                (json.dumps(evidence, sort_keys=True), now, key),
            )
            return str(row["link_id"])

    def links_for(self, episode_id: str, trust_filter: str | None = None) -> list[dict]:
        params: list[str] = [episode_id, episode_id]
        where = "status = 'active' AND (from_episode_id = ? OR to_episode_id = ?)"
        if trust_filter is not None:
            where += " AND trust = ?"
            params.append(trust_filter)
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM narrative_links WHERE {where} ORDER BY created_at, link_id",
                params,
            ).fetchall()
        return [self._link_row_to_dict(row) for row in rows]

    def threads(self) -> list[list[str]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT from_episode_id, to_episode_id FROM narrative_links "
                "WHERE status = 'active' AND link_type = 'same_thread' "
                "ORDER BY from_episode_id, to_episode_id"
            ).fetchall()
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for row in rows:
            union(str(row["from_episode_id"]), str(row["to_episode_id"]))
        groups: dict[str, list[str]] = {}
        for node in list(parent):
            groups.setdefault(find(node), []).append(node)
        return [sorted(items) for items in groups.values()]

    def add_proposal(
        self,
        *,
        kind: str,
        ep_a: str,
        ep_b: str,
        embedder_id: str,
        distance: float,
    ) -> str:
        if kind not in _PROPOSAL_KINDS:
            raise ValueError(f"unsupported narrative proposal kind: {kind}")
        if not ep_a or not ep_b:
            raise ValueError("narrative proposal endpoints are required")
        if not embedder_id:
            raise ValueError("narrative proposal requires embedder_id")
        proposal_id = f"nprop-{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        with self._connect() as con, con:
            con.execute(
                "INSERT INTO narrative_proposals "
                "(proposal_id, kind, ep_a, ep_b, embedder_id, distance, "
                "created_at, status, promoted_link_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal_id,
                    str(kind),
                    str(ep_a),
                    str(ep_b),
                    str(embedder_id),
                    float(distance),
                    now,
                    "pending",
                    None,
                ),
            )
        return proposal_id

    def pending_proposals(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM narrative_proposals WHERE status = 'pending' "
                "ORDER BY created_at, proposal_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def promote_proposal(self, proposal_id: str, *, promoted_link_id: str) -> None:
        with self._connect() as con, con:
            con.execute(
                "UPDATE narrative_proposals SET status = 'promoted', promoted_link_id = ? "
                "WHERE proposal_id = ?",
                (promoted_link_id, proposal_id),
            )

    @staticmethod
    def _decode_evidence(value: str) -> list[dict]:
        try:
            data = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    @classmethod
    def _link_row_to_dict(cls, row: sqlite3.Row) -> dict:
        data = dict(row)
        data["evidence"] = cls._decode_evidence(data.pop("evidence_json"))
        return data
