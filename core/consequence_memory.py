# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""consequence_memory.py — persistent record of Maez's non-audit mistakes.

`fabrication_memory` captures one specific failure class: the model
made a claim that the grounding judge rejected. This module widens
the surface: any outcome worth learning from gets a row, regardless
of who detected it.

Classes of event (extensible — listed here for discoverability,
enforced only by convention):

  tool_failure      A shell / HTTP / subprocess Maez ran returned
                    non-zero or malformed output. Context = the cmd,
                    outcome = the stderr + exit code, feedback = what
                    a reasonable future Maez should do differently.

  card_rejected     A proposal card the user (Rohit) rejected. Context
                    = the card's plain_english, outcome = rejection
                    reason or just "rejected", feedback = pattern to
                    avoid.

  user_correction   Explicit user feedback that contradicts Maez's
                    output or approach ("no, not that", "I told you
                    not to do X", etc). Context = what Maez said /
                    proposed, outcome = the correction, feedback =
                    the correction restated as an instruction.

  fixation_episode  Maez stuck on one topic across N cycles where
                    N > threshold. Context = the topic + cycle
                    excerpts, outcome = "fixation_detected",
                    feedback = "diversify off {topic} for M cycles".

  approval_timeout  Card sat unanswered past its stale threshold and
                    auto-expired. Context = the card details,
                    outcome = "no response", feedback = observational
                    — was the card important or ignorable?

Not in this module:

  - Retrieval-quality scoring (that's core.memory_scoring).
  - Grounding audit findings (that's core.fabrication_memory).
  - Cycle-level quality signals (that's core.cognition_quality).

Those three are class-specific record types with their own tuned
semantics. This module is the catch-all for everything else.

Fail-safe: every public entry point catches DB errors and logs
rather than propagating. Losing a consequence row is better than
breaking the caller's happy path.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.consequence_memory")

DB_PATH = Path(
    os.environ.get(
        "MAEZ_CONSEQUENCE_MEMORY_DB",
        "/home/rohit/maez/memory/consequence_memory.db",
    )
)

# Known classes — the producer-side code imports these constants
# rather than passing raw strings, so typos are caught at import time.
CLASS_TOOL_FAILURE = "tool_failure"
CLASS_CARD_REJECTED = "card_rejected"
CLASS_USER_CORRECTION = "user_correction"
CLASS_FIXATION_EPISODE = "fixation_episode"
CLASS_APPROVAL_TIMEOUT = "approval_timeout"

_KNOWN_CLASSES = frozenset({
    CLASS_TOOL_FAILURE, CLASS_CARD_REJECTED, CLASS_USER_CORRECTION,
    CLASS_FIXATION_EPISODE, CLASS_APPROVAL_TIMEOUT,
})


# ── connection / schema ───────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          REAL    NOT NULL,
            class       TEXT    NOT NULL,
            surface     TEXT    NOT NULL DEFAULT 'unknown',
            context     TEXT    NOT NULL DEFAULT '',
            outcome     TEXT    NOT NULL DEFAULT '',
            feedback    TEXT    NOT NULL DEFAULT '',
            tags        TEXT    NOT NULL DEFAULT '',
            extra_json  TEXT    NOT NULL DEFAULT '{}',
            heeded      INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_class_ts ON events(class, ts)"
    )
    con.commit()
    return con


# ── dataclass ─────────────────────────────────────────────────────────

@dataclass
class ConsequenceEvent:
    """One row from the events table. `tags` is a list[str] in the
    Python object (stored comma-separated in SQLite for cheap
    full-text-adjacent search). `extra` is a dict in the Python
    object (stored as JSON in SQLite). self-dev review on 261a8db
    (concern #3) corrected an earlier docstring that claimed the
    Python side was the comma-separated string."""
    id: int
    ts: float
    kind: str      # column is called `class` but that's a python keyword
    surface: str
    context: str
    outcome: str
    feedback: str
    tags: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    heeded: bool = False


def _row_to_event(row) -> ConsequenceEvent:
    try:
        extra = json.loads(row[8]) if row[8] else {}
    except Exception:
        extra = {}
    tags = [t for t in (row[7] or "").split(",") if t]
    return ConsequenceEvent(
        id=row[0], ts=row[1], kind=row[2], surface=row[3],
        context=row[4], outcome=row[5], feedback=row[6],
        tags=tags, extra=extra, heeded=bool(row[9]),
    )


# ── write path ────────────────────────────────────────────────────────

def record_event(
    *,
    kind: str,
    context: str,
    outcome: str,
    feedback: str = "",
    surface: str = "unknown",
    tags: Optional[list[str]] = None,
    extra: Optional[dict] = None,
) -> Optional[int]:
    """Persist one consequence event. Returns the row id, or None if
    the write failed (callers may not care).

    `kind` SHOULD be one of the CLASS_* constants but any string is
    accepted — this module stays out of the business of validating
    taxonomy. A warning logs for unknown classes so typos surface.
    """
    if kind not in _KNOWN_CLASSES:
        logger.warning(
            "consequence_memory: unknown kind %r (known: %s) — "
            "recording anyway",
            kind, sorted(_KNOWN_CLASSES),
        )
    try:
        # self-dev review on 261a8db (concern #1): sqlite3 context
        # manager only commits/rolls back — it does NOT close the
        # connection. Wrap in contextlib.closing so file descriptors
        # are deterministically released.
        with contextlib.closing(_connect()) as con:
            cur = con.execute(
                "INSERT INTO events (ts, class, surface, context, "
                "outcome, feedback, tags, extra_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(), kind, surface or "unknown",
                    context or "", outcome or "", feedback or "",
                    ",".join(tags or []),
                    json.dumps(extra or {}, default=str),
                ),
            )
            con.commit()
            return cur.lastrowid
    except Exception as e:
        logger.warning("consequence_memory: write failed: %s", e)
        return None


def mark_heeded(event_id: int) -> bool:
    """Set the `heeded` flag when a later decision explicitly
    incorporated this consequence (e.g. avoided a rejected-card
    pattern). Observability signal — not used for retrieval
    filtering today, but a future consumer that sees many unheeded
    events can report "Maez is ignoring its own past mistakes."
    """
    try:
        # self-dev review on 261a8db (concern #1): sqlite3 context
        # manager only commits/rolls back — it does NOT close the
        # connection. Wrap in contextlib.closing so file descriptors
        # are deterministically released.
        with contextlib.closing(_connect()) as con:
            cur = con.execute(
                "UPDATE events SET heeded = 1 WHERE id = ?",
                (event_id,),
            )
            con.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning("consequence_memory: mark_heeded failed: %s", e)
        return False


# ── read path ─────────────────────────────────────────────────────────

def recent(
    *,
    kind: Optional[str] = None,
    window_hours: Optional[int] = None,
    limit: int = 20,
) -> list[ConsequenceEvent]:
    """Most recent events, optionally filtered by class and time
    window. Returns [] on any error."""
    try:
        # self-dev review on 261a8db (concern #1): sqlite3 context
        # manager only commits/rolls back — it does NOT close the
        # connection. Wrap in contextlib.closing so file descriptors
        # are deterministically released.
        with contextlib.closing(_connect()) as con:
            q = (
                "SELECT id, ts, class, surface, context, outcome, "
                "feedback, tags, extra_json, heeded FROM events WHERE 1=1"
            )
            params: list = []
            if kind:
                q += " AND class = ?"
                params.append(kind)
            # self-dev review on 261a8db (concern #4): `if
            # window_hours:` treated 0 as "no filter", so a caller
            # passing 0 (meaning "events from the last zero hours"
            # → empty) silently got all events. Use `is not None`
            # so 0 is honored as a legitimate (if unusual) filter.
            if window_hours is not None:
                q += " AND ts >= ?"
                params.append(time.time() - window_hours * 3600)
            q += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            rows = con.execute(q, params).fetchall()
        return [_row_to_event(r) for r in rows]
    except Exception as e:
        logger.warning("consequence_memory: recent failed: %s", e)
        return []


def relevant(
    *,
    context_snippet: str,
    limit: int = 5,
    window_hours: int = 168,
) -> list[ConsequenceEvent]:
    """Naive retrieval: return recent events whose context, outcome,
    feedback, or tags share any whitespace-token with the query
    snippet. A real vector retrieval lands later once we see what
    consumers actually ask for.

    Deliberately token-based rather than substring so a query like
    "git commit" matches stored events about "git" or "commit"
    without requiring the exact phrase.

    self-dev review on 261a8db (concern #2): entire body is now
    wrapped in try/except to honor the module-level "never
    propagate" invariant. Prior version could propagate from the
    scoring/sort loop if a row had unexpected shape.
    """
    try:
        if not context_snippet or not context_snippet.strip():
            return []
        # 01-M1 / 09-B1: drop the `.isalnum()` filter — haystack-side
        # (below) does not apply it, so keeping it here silently hides
        # any stored event whose match tokens contain hyphens,
        # underscores, or dots ("git-push", "my_script.py",
        # "http://example.com"). The two sides must use the same
        # token predicate or recall is lossy without any error.
        query_tokens = {
            t.lower() for t in context_snippet.split()
            if len(t) > 2
        }
        if not query_tokens:
            return []

        # Pull a reasonable pool then filter in python — the DB doesn't
        # need to be clever here. Small corpora for a long time.
        pool = recent(
            window_hours=window_hours,
            limit=max(limit * 20, 100),
        )
        scored: list[tuple[int, ConsequenceEvent]] = []
        for e in pool:
            haystack = " ".join([e.context, e.outcome, e.feedback,
                                  " ".join(e.tags)]).lower()
            tokens = {t for t in haystack.split() if len(t) > 2}
            overlap = len(query_tokens & tokens)
            if overlap > 0:
                scored.append((overlap, e))
        # Higher overlap first; tie-break by recency
        scored.sort(key=lambda x: (-x[0], -x[1].ts))
        return [e for _, e in scored[:limit]]
    except Exception as e:
        logger.warning("consequence_memory: relevant failed: %s", e)
        return []


# ── stats (for cockpit / rollup) ──────────────────────────────────────

def stats(*, window_hours: Optional[int] = None) -> dict:
    """Summary for dashboards. Always returns a dict; empty on error
    so callers can dumbly render."""
    try:
        # self-dev review on 261a8db (concern #1): sqlite3 context
        # manager only commits/rolls back — it does NOT close the
        # connection. Wrap in contextlib.closing so file descriptors
        # are deterministically released.
        with contextlib.closing(_connect()) as con:
            where = ""
            params: tuple = ()
            # self-dev review on 261a8db (concern #4): `if
            # window_hours:` treated 0 as "no filter", so a caller
            # passing 0 (meaning "events from the last zero hours"
            # → empty) silently got all events. Use `is not None`
            # so 0 is honored as a legitimate (if unusual) filter.
            if window_hours is not None:
                where = " WHERE ts >= ?"
                params = (time.time() - window_hours * 3600,)
            total = con.execute(
                f"SELECT COUNT(*) FROM events{where}", params,
            ).fetchone()[0]
            by_class_rows = con.execute(
                "SELECT class, COUNT(*), SUM(heeded) FROM events"
                + (where if where else "")
                + " GROUP BY class",
                params,
            ).fetchall()
        return {
            "window_hours": window_hours,
            "total": int(total),
            "by_class": {
                row[0]: {
                    "count": int(row[1]),
                    "heeded": int(row[2] or 0),
                } for row in by_class_rows
            },
        }
    except Exception as e:
        logger.warning("consequence_memory: stats failed: %s", e)
        return {"error": str(e), "total": 0, "by_class": {}}


# ── convenience: prompt block for cycle / reason injection ────────────

def format_for_prompt(
    events: list[ConsequenceEvent], *, max_events: int = 5,
) -> str:
    """Render events as a compact prompt block for injection into
    the cycle / reasoning prompt. Empty string when no events so the
    caller can cleanly concatenate."""
    if not events:
        return ""
    lines = ["[LEARNED FROM PAST MISTAKES]"]
    for e in events[:max_events]:
        lines.append(
            f"- {e.kind}: {e.feedback or e.outcome}"
        )
    return "\n".join(lines)
