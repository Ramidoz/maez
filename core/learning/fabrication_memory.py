# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
fabrication_memory.py — immune memory for self-claim fabrications.

Every time the self_claim_audit detector rewrites a reply, something
real happened: the model reached for a fabricated name/path/schedule/
postcondition that doesn't ground to this system. V1 audit silently
caught and rewrote. Without memory of those catches, tomorrow's turn
can still reach for the same invented tokens — the detector rebuffs
the attempt but nothing is learned.

This module closes that loop. It persists every flagged event to a
small SQLite table and exposes a prompt snippet that surfaces the
most-fabricated tokens of the last week. Injected into the system
prompt (via capability_registry), this gives the model explicit
negative training-from-its-own-mistakes at generation time.

Not analytics: the goal is behavioral, not observability. The cockpit
fabrication pane already reads cognition.log for observability; this
table exists so the next turn's prompt can say "you tried to claim
X last week, that wasn't real, don't reach for it again."

Design choices:
  - Separate db (memory/fabrication_log.db) so rotation / archive
    policy can diverge from the operational dbs.
  - Lowercase token for grouping so "Maelstrom" and "maelstrom"
    count as the same attempt.
  - No user_question capture yet — audit doesn't receive it, and
    adding the plumbing is a separate follow-up.
  - Silent-on-failure. A broken fabrication log must never crash
    an audit call.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

try:
    from core.paths import memory_dir as _memory_dir
    _DB_PATH = _memory_dir() / "fabrication_log.db"
except Exception:
    _DB_PATH = (
        Path(__file__).resolve().parents[2]
        / "memory" / "fabrication_log.db"
    )
_db_lock = threading.Lock()
_initialized = False


def _ensure_db() -> Optional[sqlite3.Connection]:
    """Open / create the fabrication log db. Returns None on failure so
    callers can no-op silently."""
    global _initialized
    try:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(_DB_PATH, timeout=2.0, check_same_thread=False)
        if not _initialized:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fabrication_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts           REAL NOT NULL,
                    surface      TEXT NOT NULL,
                    kind         TEXT NOT NULL,
                    token        TEXT NOT NULL,
                    token_lower  TEXT NOT NULL,
                    mode         TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS fabrication_token_idx
                    ON fabrication_log(token_lower);
                CREATE INDEX IF NOT EXISTS fabrication_ts_idx
                    ON fabrication_log(ts);

                CREATE TABLE IF NOT EXISTS fabrication_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts              REAL NOT NULL,
                    surface         TEXT NOT NULL,
                    text            TEXT NOT NULL,
                    signals_absent  TEXT NOT NULL,
                    reason          TEXT NOT NULL,
                    mode            TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS fab_events_ts_idx
                    ON fabrication_events(ts);
            """)
            # Idempotent column add for existing DBs that pre-date the
            # signals_present field. Sampling that drives substrate
            # decisions ("real fabrication" vs "thin manifest") needs
            # both sides of the receipt: what the audit had AND what
            # it didn't have. Without signals_present, that
            # disambiguation is inferential.
            try:
                cols = {
                    r[1] for r in db.execute(
                        "PRAGMA table_info(fabrication_events)"
                    ).fetchall()
                }
                if "signals_present" not in cols:
                    db.execute(
                        "ALTER TABLE fabrication_events "
                        "ADD COLUMN signals_present TEXT NOT NULL DEFAULT '[]'"
                    )
                    db.commit()
            except Exception:
                # Schema migration must never block writes. Worst case:
                # the new column doesn't exist and record_event() falls
                # back to writing without it.
                pass
            _initialized = True
        return db
    except Exception:
        return None


# Soft retention cap. Without this the table grows unbounded —
# there's currently no rotation mechanism. 90 days × ~1K events/day
# = 90K rows = ~10 MB on disk. Enough for monthly-pattern analysis,
# bounded enough that the file doesn't become a problem.
_FAB_RETENTION_DAYS = 90


def _trim_old_events(db: sqlite3.Connection) -> None:
    """Best-effort delete of fabrication_events older than the
    retention cap. Called probabilistically (not every insert) so
    write-path cost stays near-zero. Silent on failure."""
    try:
        cutoff = time.time() - (_FAB_RETENTION_DAYS * 86400)
        db.execute(
            "DELETE FROM fabrication_events WHERE ts < ?",
            (cutoff,),
        )
    except Exception:
        return


def record(surface: str, flags: list, mode: str) -> None:
    """Persist one row per flag. Called from self_claim_audit._emit()
    after the cognition.log line is written. `flags` is a list of the
    audit's Flag dataclass — we duck-type the fields we need."""
    if not flags:
        return
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                ts = time.time()
                rows = []
                for f in flags:
                    kind = getattr(f, "kind", "unknown")
                    token = getattr(f, "ungrounded_token", "") or ""
                    if not token:
                        continue
                    rows.append((ts, surface, kind, token, token.lower(), mode))
                if rows:
                    db.executemany(
                        "INSERT INTO fabrication_log "
                        "(ts, surface, kind, token, token_lower, mode) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                    db.commit()
    except Exception:
        # Never let memory-write failure break an audit call.
        return


def top_tokens(days: int = 7, limit: int = 8) -> list[tuple[str, str, int]]:
    """Return [(token_display, kind, count), ...] for tokens fabricated
    most often in the last N days. Grouped by token_lower + kind so
    case-variants collapse.

    Returns empty list on any failure — consumers must not rely on
    this as a source-of-truth; it's advisory."""
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return []
            with contextlib.closing(db):
                since = time.time() - (days * 86400)
                rows = db.execute(
                    "SELECT token, kind, COUNT(*) as n "
                    "FROM fabrication_log "
                    "WHERE ts >= ? "
                    "GROUP BY token_lower, kind "
                    "ORDER BY n DESC, MAX(ts) DESC "
                    "LIMIT ?",
                    (since, limit),
                ).fetchall()
                return [(r[0], r[1], r[2]) for r in rows]
    except Exception:
        return []


def prompt_snippet(days: int = 7, limit: int = 6) -> str:
    """Compact prompt-suitable block. Empty string when there's nothing
    to report (first days of operation, fresh reset, etc.).

    Kept short (~200-400 chars) — injected into every reply-building
    prompt alongside the capability registry. The load-bearing part is
    the explicit 'don't reach for these again' instruction."""
    top = top_tokens(days=days, limit=limit)
    if not top:
        return ""
    lines = ["# FABRICATION MEMORY (things you've tried to invent recently)"]
    for token, kind, count in top:
        # Never echo fabricated paths/slashes — they could re-seed
        # a follow-on fabrication. Clip tokens with slashes to the
        # leaf, and always truncate.
        safe = token.replace("/", "·")[:50]
        lines.append(f"- {safe} ({kind}, flagged {count}x)")
    lines.append(
        "INSTRUCTION: The items above are things you previously asserted as "
        "real Maez internals but the structural audit had to rewrite because "
        "they don't ground to any file, service, schedule, or tool output on "
        "this system. Do NOT reach for them again — if asked about any of them, "
        "respond with honest uncertainty."
    )
    return "\n".join(lines)


def record_event(
    surface: str,
    text: str,
    signals_absent: list[str],
    reason: str,
    mode: str,
    signals_present: Optional[list[str]] = None,
) -> None:
    """Persist one per-response fabrication event with its signal context.
    Used to build few-shot examples for the semantic grounding judge.

    `signals_present` was added 2026-05-05 so post-hoc sampling can
    distinguish "judge was thin-manifested" (signals_present small,
    real receipts available but not passed) from "judge correctly
    flagged real fabrication" (signals_present rich and the claim
    still couldn't ground). Older events that pre-date the field
    will read as `[]`.
    """
    if not text:
        return
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                db.execute(
                    "INSERT INTO fabrication_events "
                    "(ts, surface, text, signals_absent, signals_present, "
                    "reason, mode) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.time(), surface, text[:2000],
                        json.dumps(signals_absent or []),
                        json.dumps(signals_present or []),
                        reason[:500], mode,
                    ),
                )
                # Probabilistic retention trim — once every ~100 inserts.
                # Cheap (one DELETE on indexed ts column), bounded.
                if int(time.time() * 1000) % 100 == 0:
                    _trim_old_events(db)
                db.commit()
    except Exception:
        return


def few_shots_for(signals_absent: list[str], k: int = 3) -> list[dict]:
    """Return up to k few-shot examples from fabrication_events whose
    signal-absent shape most closely matches the provided list.

    Scoring: overlap count (how many signals_absent entries match), then
    recency as tie-breaker. Falls back to most-recent events when no
    shape overlap exists.
    """
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return []
            with contextlib.closing(db):
                rows = db.execute(
                    "SELECT text, signals_absent, reason FROM fabrication_events "
                    "ORDER BY ts DESC LIMIT 200"
                ).fetchall()
    except Exception:
        return []
    if not rows:
        return []

    query_set = set(signals_absent or [])

    def _score(row):
        try:
            stored = set(json.loads(row[1]))
        except Exception:
            stored = set()
        return len(query_set & stored)

    scored = sorted(rows, key=_score, reverse=True)
    result = []
    for text, sa_json, reason in scored[:k]:
        try:
            sa = json.loads(sa_json)
        except Exception:
            sa = []
        result.append({"text": text, "signals_absent": sa, "reason": reason})
    return result


# ── diagnostic helpers (for tests + CLI) ──────────────────────────────

def _diag_total_rows() -> int:
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return -1
            with contextlib.closing(db):
                return db.execute("SELECT COUNT(*) FROM fabrication_log").fetchone()[0]
    except Exception:
        return -1


def _assert_test_clear_allowed() -> None:
    """Belt-and-suspenders guard against accidentally wiping
    production fabrication memory.

    On 2026-05-05 we discovered _diag_clear_events_for_test had been
    run against the production memory/fabrication_log.db (likely a
    test ran without DB-path isolation), wiping ~14K accumulated
    fabrication events. This guard exists so it cannot happen again.

    Two conditions must BOTH hold for a clear to proceed:

      1. MAEZ_TEST_MODE=1 in the environment.
      2. _DB_PATH is NOT the same file as the production
         memory/fabrication_log.db.

    Production satisfies neither. Tests must satisfy both — meaning
    the test must (a) set the env and (b) redirect _DB_PATH to a
    temp file. That second requirement is what actually closes the
    footgun: even if the env leaks into a daemon process, the path
    check refuses to wipe the production DB."""
    import os as _os
    if _os.environ.get("MAEZ_TEST_MODE") != "1":
        raise RuntimeError(
            "fabrication_memory clear blocked: MAEZ_TEST_MODE!=1. "
            "These helpers wipe the database; they must only run "
            "in test mode with a redirected DB path."
        )
    # Resolve the production path the same way _DB_PATH is resolved
    # at module import time. If they're the same file (samefile
    # follows symlinks; identity-by-inode), refuse.
    try:
        prod_path = (
            _memory_dir() / "fabrication_log.db"
            if "_memory_dir" in globals() else None
        )
    except Exception:
        prod_path = None
    if prod_path is None:
        # Fallback: resolve against the canonical Maez install root.
        prod_path = (
            Path(__file__).resolve().parents[2]
            / "memory" / "fabrication_log.db"
        )
    try:
        if _DB_PATH.exists() and prod_path.exists() \
                and _DB_PATH.samefile(prod_path):
            raise RuntimeError(
                f"fabrication_memory clear blocked: _DB_PATH "
                f"({_DB_PATH}) is the production fabrication_log.db. "
                "Test helpers must redirect _DB_PATH to a temp file."
            )
    except FileNotFoundError:
        # Either path missing — by definition not the production
        # file the guard exists to protect; allow.
        pass


def _diag_clear_for_test() -> None:
    """Test-only. Wipes fabrication_log for test isolation.

    Refuses to run unless MAEZ_TEST_MODE=1 AND _DB_PATH has been
    redirected away from the production fabrication_log.db. See
    _assert_test_clear_allowed for the rationale."""
    _assert_test_clear_allowed()
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                db.execute("DELETE FROM fabrication_log")
                db.commit()
    except Exception:
        return


def _diag_clear_events_for_test() -> None:
    """Test-only. Wipes fabrication_events for test isolation.

    Refuses to run unless MAEZ_TEST_MODE=1 AND _DB_PATH has been
    redirected away from the production fabrication_log.db. See
    _assert_test_clear_allowed for the rationale."""
    _assert_test_clear_allowed()
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                db.execute("DELETE FROM fabrication_events")
                db.commit()
    except Exception:
        return
