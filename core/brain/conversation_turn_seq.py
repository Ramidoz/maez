"""Conversation turn-sequence store — Phase 2 action lane, commit A.

Design: docs/superpowers/specs/2026-08-20-phase2-action-lane-design.md
(pass 6, gate-approved). The ONLY authority for per-conversation turn
ordinals, used by referent freshness (OfferReceipt.created_turn_seq /
turns_since). One public mutation: ``advance_and_get``.

Gate-inherited contract (round 6 notes, verbatim intent):
- Two internal tables in one SQLite file: conversation state keyed by
  (channel, chat_id); event assignments keyed by (channel, chat_id,
  event_identity). Lookup, increment, assignment, commit inside ONE
  BEGIN IMMEDIATE transaction.
- IDEMPOTENT: the same event identity retried returns the SAME
  sequence — a Telegram redelivery can never double-count.
- Identities are source-tagged by the caller ("update:123" /
  "message:123") so numeric namespaces cannot alias.
- Path resolves through core.infra.paths.memory_dir() so MAEZ_DATA
  and disposable test roots are honored.
- FLAGS-OFF = FILESYSTEM UNTOUCHED: with neither action-lane flag set,
  no database is created, initialized, or opened for write.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger("maez")

_TRUE = ("1", "true", "yes", "on")


def action_lane_shadow_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_ACTION_LANE_SHADOW", "") or "").strip().lower() in _TRUE


def action_lane_enabled(env=os.environ) -> bool:
    return (env.get("MAEZ_ACTION_LANE_ENABLED", "") or "").strip().lower() in _TRUE


def _any_action_lane_flag(env=os.environ) -> bool:
    return action_lane_shadow_enabled(env) or action_lane_enabled(env)


def _db_path() -> Path:
    from core.infra.paths import memory_dir

    return Path(memory_dir()) / "conversation_turn_seq.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_seq (
    channel TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    current_seq INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (channel, chat_id)
) STRICT;
CREATE TABLE IF NOT EXISTS event_assignments (
    channel TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    event_identity TEXT NOT NULL,
    assigned_seq INTEGER NOT NULL,
    PRIMARY KEY (channel, chat_id, event_identity)
) STRICT;
"""


def advance_and_get(
    channel: str,
    chat_id: str,
    event_identity: str,
) -> "int | None":
    """Assign (or return the already-assigned) turn sequence for one
    admitted owner turn. Returns None when both action-lane flags are
    off (the store must not exist then) or on any storage failure —
    callers treat None as "no turn ordinal available" and fall back to
    time-only freshness (design P3b).
    """
    if not _any_action_lane_flag():
        return None
    if not channel or not chat_id or not event_identity:
        return None
    try:
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=5.0)
        try:
            conn.executescript(_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT assigned_seq FROM event_assignments "
                "WHERE channel=? AND chat_id=? AND event_identity=?",
                (channel, chat_id, event_identity),
            ).fetchone()
            if row is not None:
                conn.execute("COMMIT")
                return int(row[0])
            cur = conn.execute(
                "SELECT current_seq FROM conversation_seq "
                "WHERE channel=? AND chat_id=?",
                (channel, chat_id),
            ).fetchone()
            nxt = (int(cur[0]) if cur is not None else 0) + 1
            if cur is None:
                conn.execute(
                    "INSERT INTO conversation_seq (channel, chat_id, current_seq) "
                    "VALUES (?, ?, ?)",
                    (channel, chat_id, nxt),
                )
            else:
                conn.execute(
                    "UPDATE conversation_seq SET current_seq=? "
                    "WHERE channel=? AND chat_id=?",
                    (nxt, channel, chat_id),
                )
            conn.execute(
                "INSERT INTO event_assignments "
                "(channel, chat_id, event_identity, assigned_seq) "
                "VALUES (?, ?, ?, ?)",
                (channel, chat_id, event_identity, nxt),
            )
            conn.execute("COMMIT")
            return nxt
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("conversation_turn_seq advance failed: %s", exc)
        return None


def current_seq(channel: str, chat_id: str) -> "int | None":
    """Read-only current ordinal; None if flags off, absent, or error."""
    if not _any_action_lane_flag():
        return None
    try:
        path = _db_path()
        if not path.exists():
            return None
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
        try:
            row = conn.execute(
                "SELECT current_seq FROM conversation_seq "
                "WHERE channel=? AND chat_id=?",
                (channel, chat_id),
            ).fetchone()
            return int(row[0]) if row is not None else None
        finally:
            conn.close()
    except Exception:
        return None
