# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""self_dev_persistence.py — SQLite sidecar for self-dev review
results and their concerns.

Separated from core.self_dev so the primitive stays pure (caller
can review without writing if it wants dry-run behavior), and so
the store's schema can evolve independently of the review prompt.

Schema:
  reviews        — one row per review() invocation
  concerns       — one row per concern raised in that review
  concern_state  — per-concern user decisions (open / resolved /
                   rejected / wont_fix), separated from concerns so
                   the same concern surfaced twice (e.g. a blocker
                   that persists across commits) can accumulate
                   context without duplicating rows.

Design decisions:
  - No `ON CONFLICT` magic. Every review() writes a new reviews row
    and fresh concerns rows. Deduping across reviews is the caller's
    problem; this layer records what happened.
  - Status flow is linear but reversible:
      open  →  resolved  (Rohit fixed it)
      open  →  wont_fix  (not a real problem, or out of scope)
      open  →  rejected  (Claude was wrong)
    Any terminal state can be reverted to `open` by clearing
    resolution_notes.
  - Failing to persist NEVER breaks a review call. The primitive
    catches the DB error, logs it, and returns the in-memory result
    unchanged. Observability > correctness here — we don't want a
    disk-full condition to disable self-dev entirely.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.self_dev_persistence")

DB_PATH = Path(
    os.environ.get(
        "MAEZ_SELF_DEV_DB",
        "/home/rohit/maez/memory/self_dev.db",
    )
)


# ── low-level connection ──────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              REAL    NOT NULL,
            target_ref      TEXT    NOT NULL,
            diff_size_chars INTEGER NOT NULL,
            overall         TEXT    NOT NULL,
            model_used      TEXT    NOT NULL,
            input_tokens    INTEGER NOT NULL DEFAULT 0,
            output_tokens   INTEGER NOT NULL DEFAULT 0,
            parse_error     TEXT    NOT NULL DEFAULT '',
            caller          TEXT    NOT NULL DEFAULT 'unknown'
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_ts
            ON reviews(ts);
        CREATE INDEX IF NOT EXISTS idx_reviews_target
            ON reviews(target_ref);

        CREATE TABLE IF NOT EXISTS concerns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id       INTEGER NOT NULL
                                REFERENCES reviews(id) ON DELETE CASCADE,
            file            TEXT    NOT NULL,
            line            INTEGER,
            severity        TEXT    NOT NULL,
            text            TEXT    NOT NULL,
            suggestion      TEXT,
            status          TEXT    NOT NULL DEFAULT 'open',
            resolved_at     REAL,
            resolution_notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_concerns_review
            ON concerns(review_id);
        CREATE INDEX IF NOT EXISTS idx_concerns_status_severity
            ON concerns(status, severity);
    """)
    con.commit()
    return con


# ── dataclasses (convenience for query consumers) ─────────────────────

@dataclass
class StoredReview:
    id: int
    ts: float
    target_ref: str
    overall: str
    model_used: str
    input_tokens: int
    output_tokens: int
    diff_size_chars: int
    parse_error: str
    caller: str


@dataclass
class StoredConcern:
    id: int
    review_id: int
    file: str
    line: Optional[int]
    severity: str
    text: str
    suggestion: Optional[str]
    status: str
    resolved_at: Optional[float]
    resolution_notes: Optional[str]


# ── write path ────────────────────────────────────────────────────────

def store_review(review_result, *, caller: str = "unknown") -> Optional[int]:
    """Persist a core.self_dev.ReviewResult and its concerns. Returns
    the review_id, or None if the DB write failed (caller keeps the
    in-memory result regardless)."""
    try:
        with _connect() as con:
            cur = con.execute(
                "INSERT INTO reviews (ts, target_ref, diff_size_chars, "
                "overall, model_used, input_tokens, output_tokens, "
                "parse_error, caller) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(), review_result.target_ref,
                    review_result.diff_size_chars,
                    review_result.overall, review_result.model_used,
                    review_result.input_tokens, review_result.output_tokens,
                    review_result.parse_error, caller,
                ),
            )
            review_id = cur.lastrowid
            for c in review_result.concerns:
                con.execute(
                    "INSERT INTO concerns (review_id, file, line, severity, "
                    "text, suggestion) VALUES (?, ?, ?, ?, ?, ?)",
                    (review_id, c.file, c.line, c.severity, c.text,
                     c.suggestion),
                )
            con.commit()
            return review_id
    except Exception as e:
        logger.warning("self_dev_persistence: store_review failed: %s", e)
        return None


# ── read path ─────────────────────────────────────────────────────────

def _row_to_review(row) -> StoredReview:
    return StoredReview(
        id=row[0], ts=row[1], target_ref=row[2], diff_size_chars=row[3],
        overall=row[4], model_used=row[5], input_tokens=row[6],
        output_tokens=row[7], parse_error=row[8], caller=row[9],
    )


def _row_to_concern(row) -> StoredConcern:
    return StoredConcern(
        id=row[0], review_id=row[1], file=row[2], line=row[3],
        severity=row[4], text=row[5], suggestion=row[6], status=row[7],
        resolved_at=row[8], resolution_notes=row[9],
    )


def list_reviews(*, limit: int = 20) -> list[StoredReview]:
    """Most recent reviews first."""
    try:
        with _connect() as con:
            rows = con.execute(
                "SELECT id, ts, target_ref, diff_size_chars, overall, "
                "model_used, input_tokens, output_tokens, parse_error, "
                "caller FROM reviews ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_review(r) for r in rows]
    except Exception as e:
        logger.warning("self_dev_persistence: list_reviews failed: %s", e)
        return []


def list_concerns(
    *,
    status: Optional[str] = None,
    severity_at_least: Optional[str] = None,
    limit: int = 50,
) -> list[StoredConcern]:
    """Query concerns. `status` filters exact match; `severity_at_least`
    filters by ordered severity (blocker > major > minor > nit). Default
    returns the most recent `limit` across all states."""
    sev_order = {"blocker": 3, "major": 2, "minor": 1, "nit": 0}
    try:
        with _connect() as con:
            q = (
                "SELECT c.id, c.review_id, c.file, c.line, c.severity, "
                "c.text, c.suggestion, c.status, c.resolved_at, "
                "c.resolution_notes FROM concerns c "
                "JOIN reviews r ON c.review_id = r.id WHERE 1=1"
            )
            params: list = []
            if status:
                q += " AND c.status = ?"
                params.append(status)
            q += " ORDER BY r.ts DESC, c.id DESC LIMIT ?"
            params.append(limit * 3)  # fetch more, filter by severity below
            rows = con.execute(q, params).fetchall()
        concerns = [_row_to_concern(r) for r in rows]
        if severity_at_least:
            threshold = sev_order.get(severity_at_least.lower(), 0)
            concerns = [
                c for c in concerns
                if sev_order.get(c.severity.lower(), 0) >= threshold
            ]
        return concerns[:limit]
    except Exception as e:
        logger.warning("self_dev_persistence: list_concerns failed: %s", e)
        return []


def get_review_with_concerns(
    review_id: int,
) -> Optional[tuple[StoredReview, list[StoredConcern]]]:
    """Load one review and all its concerns."""
    try:
        with _connect() as con:
            row = con.execute(
                "SELECT id, ts, target_ref, diff_size_chars, overall, "
                "model_used, input_tokens, output_tokens, parse_error, "
                "caller FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            if not row:
                return None
            concern_rows = con.execute(
                "SELECT id, review_id, file, line, severity, text, "
                "suggestion, status, resolved_at, resolution_notes "
                "FROM concerns WHERE review_id = ? ORDER BY id",
                (review_id,),
            ).fetchall()
        return (
            _row_to_review(row),
            [_row_to_concern(r) for r in concern_rows],
        )
    except Exception as e:
        logger.warning("self_dev_persistence: get_review failed: %s", e)
        return None


# ── state transitions ─────────────────────────────────────────────────

_VALID_STATES = {"open", "resolved", "wont_fix", "rejected"}


def set_concern_status(
    concern_id: int,
    status: str,
    *,
    notes: Optional[str] = None,
) -> bool:
    """Transition a concern to a new status. Returns True on success.

    Setting status='open' clears resolved_at and resolution_notes,
    so a mistakenly-resolved concern can be reopened cleanly.
    """
    if status not in _VALID_STATES:
        raise ValueError(
            f"status must be one of {sorted(_VALID_STATES)}; got {status!r}"
        )
    try:
        with _connect() as con:
            if status == "open":
                cur = con.execute(
                    "UPDATE concerns SET status = 'open', "
                    "resolved_at = NULL, resolution_notes = NULL "
                    "WHERE id = ?",
                    (concern_id,),
                )
            else:
                cur = con.execute(
                    "UPDATE concerns SET status = ?, resolved_at = ?, "
                    "resolution_notes = ? WHERE id = ?",
                    (status, time.time(), notes, concern_id),
                )
            con.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning(
            "self_dev_persistence: set_concern_status(%s) failed: %s",
            concern_id, e,
        )
        return False


# ── summary helpers (for dashboards / cockpit) ────────────────────────

def stats(*, window_hours: Optional[int] = None) -> dict:
    """High-level usage stats.

    If window_hours is given, restricts counts to that trailing
    window. Otherwise spans all history.
    """
    try:
        with _connect() as con:
            where = ""
            params: tuple = ()
            if window_hours:
                where = " WHERE ts >= ?"
                params = (time.time() - window_hours * 3600,)
            total_reviews = con.execute(
                f"SELECT COUNT(*) FROM reviews{where}", params,
            ).fetchone()[0]
            tokens = con.execute(
                f"SELECT COALESCE(SUM(input_tokens), 0), "
                f"COALESCE(SUM(output_tokens), 0) FROM reviews{where}",
                params,
            ).fetchone()
            sev_rows = con.execute(
                "SELECT c.severity, c.status, COUNT(*) "
                "FROM concerns c JOIN reviews r ON c.review_id = r.id"
                + (where.replace("ts", "r.ts") if where else "")
                + " GROUP BY c.severity, c.status",
                params,
            ).fetchall()
        by_severity: dict[str, dict[str, int]] = {}
        for sev, status, n in sev_rows:
            by_severity.setdefault(sev, {})[status] = n
        return {
            "window_hours": window_hours,
            "total_reviews": total_reviews,
            "total_input_tokens": tokens[0],
            "total_output_tokens": tokens[1],
            "concerns_by_severity_and_status": by_severity,
        }
    except Exception as e:
        logger.warning("self_dev_persistence: stats failed: %s", e)
        return {"error": str(e)}
