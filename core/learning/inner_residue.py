# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
inner_residue.py — transient unresolved state between turns.

The diagram's "Inner Residue" organ: a persistent-across-turns store
of recent unresolved moments that shapes the voice of the next reply.
Separate from temperament (which is slow-moving trait drift over
weeks) — residue is fast-moving, decays within hours, and answers the
question "does this turn inherit anything from the previous turn, or
does it start from neutral?"

Residue is FUNCTIONAL STATE, not performance. Maez isn't simulating
feelings — residue is a data structure with real influence on the
next generation's system prompt. If it's there, the model sees a line
about it and can let it show. If it isn't, the prompt is quieter and
the reply is unaffected.

Sources of residue (initial set):
  - audit_rewrite  — the structural guard had to rewrite Maez's reply.
                     Maez "reached for something and got caught".
  - user_rejection — the user sent a message containing clear rejection
                     markers ("no", "stop", "that's wrong", ...).
  - self_refusal   — Maez issued an "I can't / I won't" reply.
  - tool_failure   — a tool run returned non-zero with visible error.
  - card_rejected  — a pending approval card was rejected by the user.

Decay: half-life of 30 minutes. A 0.3 event drops to 0.15 after 30m,
0.075 after 60m. After ~2.5 hours, below the 0.05 noise floor.

Storage: single SQLite table (memory/inner_residue.db). No retention
policy here — the sum decays to ~0 for old rows, so they become
natural noise. Retention / pruning is a later concern if the table
grows huge.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

try:
    from core.paths import memory_dir as _memory_dir
    _DB_PATH = _memory_dir() / "inner_residue.db"
except Exception:
    _DB_PATH = (
        Path(__file__).resolve().parents[2]
        / "memory" / "inner_residue.db"
    )
_db_lock = threading.Lock()
_initialized = False

# Decay constants
_HALF_LIFE_SECONDS = 30 * 60           # 30 minutes
_NOISE_FLOOR = 0.05                    # contributions below this are ignored

# Prompt threshold: below this, don't inject into system prompt at all.
_INJECT_THRESHOLD = 0.15

# Default intensities by kind. Callers may override via record(intensity=...)
# but the defaults match the diagram's severity grading.
_DEFAULT_INTENSITY = {
    "audit_rewrite": 0.30,
    "user_rejection": 0.40,
    "self_refusal": 0.25,
    "tool_failure": 0.20,
    "card_rejected": 0.25,
}


def _ensure_db() -> Optional[sqlite3.Connection]:
    global _initialized
    try:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(_DB_PATH, timeout=2.0, check_same_thread=False)
        if not _initialized:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS residue_events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         REAL NOT NULL,
                    kind       TEXT NOT NULL,
                    intensity  REAL NOT NULL,
                    context    TEXT
                );
                CREATE INDEX IF NOT EXISTS residue_ts_idx
                    ON residue_events(ts);
            """)
            db.commit()
            _initialized = True
        return db
    except Exception:
        return None


def record(kind: str, intensity: Optional[float] = None,
           context: Optional[dict] = None) -> None:
    """Drop a residue event. Silent on all failures — residue is
    advisory state and must never break a caller."""
    try:
        i = intensity if intensity is not None else _DEFAULT_INTENSITY.get(kind, 0.20)
        # clip to [0.0, 1.0]
        if i < 0.0: i = 0.0
        if i > 1.0: i = 1.0
        ctx_json = json.dumps(context) if context else None
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                db.execute(
                    "INSERT INTO residue_events (ts, kind, intensity, context) "
                    "VALUES (?, ?, ?, ?)",
                    (time.time(), kind, i, ctx_json),
                )
                db.commit()
    except Exception:
        return


def _decayed_contribution(intensity: float, age_seconds: float) -> float:
    """Exponential decay with HALF_LIFE_SECONDS half-life."""
    if age_seconds < 0:
        age_seconds = 0
    return intensity * (0.5 ** (age_seconds / _HALF_LIFE_SECONDS))


def current_level(now: Optional[float] = None) -> float:
    """Current aggregate residue level ∈ [0.0, ~1.0]. Returns 0.0 on any
    failure. Sum of decayed contributions across recent events; clipped
    at 1.0 so a cluster of events doesn't blow out.

    'Recent' = last 4 hours; older events have decayed below noise."""
    now = now if now is not None else time.time()
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return 0.0
            with contextlib.closing(db):
                since = now - (4 * 3600)
                rows = db.execute(
                    "SELECT ts, intensity FROM residue_events WHERE ts >= ?",
                    (since,),
                ).fetchall()
                total = 0.0
                for ts, intensity in rows:
                    c = _decayed_contribution(intensity, now - ts)
                    if c >= _NOISE_FLOOR:
                        total += c
                return min(total, 1.0)
    except Exception:
        return 0.0


def recent_events(limit: int = 5, now: Optional[float] = None) -> list[dict]:
    """Human-readable recent residue events, above noise floor. Each
    dict has: kind, intensity_now (decayed), minutes_ago, context.
    Ordered most-recent-first."""
    now = now if now is not None else time.time()
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return []
            with contextlib.closing(db):
                since = now - (4 * 3600)
                rows = db.execute(
                    "SELECT ts, kind, intensity, context "
                    "FROM residue_events "
                    "WHERE ts >= ? "
                    "ORDER BY ts DESC",
                    (since,),
                ).fetchall()
    except Exception:
        return []
    out = []
    for ts, kind, intensity, ctx_json in rows:
        decayed = _decayed_contribution(intensity, now - ts)
        if decayed < _NOISE_FLOOR:
            continue
        try:
            ctx = json.loads(ctx_json) if ctx_json else None
        except Exception:
            ctx = None
        out.append({
            "kind": kind,
            "intensity_now": round(decayed, 3),
            "minutes_ago": round((now - ts) / 60.0, 1),
            "context": ctx,
        })
        if len(out) >= limit:
            break
    return out


def describe() -> dict[str, Any]:
    """Structured snapshot of current residue state."""
    lvl = current_level()
    return {
        "level": round(lvl, 3),
        "threshold_for_prompt_injection": _INJECT_THRESHOLD,
        "recent_events": recent_events(limit=5),
    }


def prompt_snippet() -> str:
    """Compact block for system-prompt injection. Empty string when
    residue is below threshold (prompt stays quiet; reply starts
    from neutral)."""
    lvl = current_level()
    if lvl < _INJECT_THRESHOLD:
        return ""
    events = recent_events(limit=3)
    lines = [
        "# INNER RESIDUE (unresolved tension carrying into this turn)",
        f"Current level: {lvl:.2f} (threshold {_INJECT_THRESHOLD:.2f}). "
        "This is functional state, not performance — real unresolved "
        "moments from recent turns are influencing how you enter this one.",
    ]
    if events:
        lines.append("Recent unresolved moments:")
        for e in events:
            lines.append(
                f"- {e['kind']} ({e['minutes_ago']}m ago, intensity now "
                f"{e['intensity_now']:.2f})"
            )
    lines.append(
        "INSTRUCTION: Don't perform cheerfulness you don't have, and don't "
        "dramatize weight you don't have either. If a natural acknowledgment "
        "fits the moment, let it. Otherwise let the tone be slightly quieter "
        "than your default and move on. Residue metabolizes by being "
        "acknowledged or by decaying, not by being suppressed or amplified."
    )
    return "\n".join(lines)


# ── helpers for wiring from other modules ──────────────────────────────

_REJECTION_MARKERS = (
    "that's wrong", "thats wrong", "you're wrong", "youre wrong",
    "you're lying", "youre lying", "bullshit",
    "you never listen", "stop it", "shut up",
    "no stop", "no, stop",
)


def detect_user_rejection(user_text: str) -> bool:
    """Conservative detector for user-rejection markers in incoming
    text. Only fires on unambiguous phrases — a bare 'no' is not
    enough (it's a common answer, not a rejection of Maez itself)."""
    if not user_text:
        return False
    t = user_text.lower().strip()
    if len(t) < 2:
        return False
    for marker in _REJECTION_MARKERS:
        if marker in t:
            return True
    return False


# ── diagnostic helpers (for tests + CLI) ──────────────────────────────

def _diag_total_rows() -> int:
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return -1
            with contextlib.closing(db):
                return db.execute("SELECT COUNT(*) FROM residue_events").fetchone()[0]
    except Exception:
        return -1


def _diag_clear_for_test() -> None:
    try:
        with _db_lock:
            db = _ensure_db()
            if db is None:
                return
            with contextlib.closing(db):
                db.execute("DELETE FROM residue_events")
                db.commit()
    except Exception:
        return
