# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
self_model.py — Maez's persistent picture of "how I've been lately".

The diagram's embryonic Self-Model organ. Distinct from:
  - capability_registry: what Maez HAS (modules, services, schedules).
  - identity_ledger:     continuity fingerprint across restarts.
  - temperament:         slow-moving trait drift over weeks.
  - inner_residue:       transient unresolved weight over minutes.
  - fabrication_memory:  negative examples of what NOT to claim.

Self-model answers: what have I been thinking about, what have I been
tripping on, what am I carrying, what am I wondering about? A
narrative that Maez can read at the start of a reply instead of
re-deriving its own recent life from scratch.

Construction is FACTUAL — every line is backed by a real db query or
log parse. No LLM generation, no narrative interpolation. When sources
are sparse (fresh restart, quiet day), the snippet degrades gracefully
to "nothing to report from this window" rather than hallucinating a
plausible day.

Not for analytics. The goal is behavioral — the model sees this at
generation time and reaches for grounded self-description instead of
inventing a plausible-sounding one.
"""
from __future__ import annotations

import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

_MAEZ_HOME = Path("/home/rohit/maez")
_COGNITION_LOG = _MAEZ_HOME / "logs" / "cognition.log"
_WONDERINGS_DB = _MAEZ_HOME / "memory" / "wonderings.db"

# Tuning
_THEME_LOOKBACK_CYCLES = 30         # recent cycles to theme-analyze
_THEME_TOP_N = 3                    # top themes to report
_LOG_READ_TAIL_BYTES = 200_000      # cap log read for perf

# Regex parsing of cognition.log lines. Shape:
#   2026-04-20 15:20:12 | cycle | score=48 primary=baseline topic=X ...
_CYCLE_LINE_RE = re.compile(
    r"\|\s*cycle\s*\|\s*"
    r"score=(?P<score>\d+)\s+"
    r"primary=(?P<primary>\w+)\s+"
    r"topic=(?P<topic>\w+)"
)


# ── source extractors ──────────────────────────────────────────────────

def _recent_themes(n_cycles: int = _THEME_LOOKBACK_CYCLES,
                   top_n: int = _THEME_TOP_N) -> list[tuple[str, int]]:
    """Return [(topic, count), ...] for the most frequent topics in the
    last N cycle-log lines. Reads the tail of cognition.log for speed."""
    if not _COGNITION_LOG.exists():
        return []
    try:
        with open(_COGNITION_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - _LOG_READ_TAIL_BYTES)
            f.seek(start)
            blob = f.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    topics: list[str] = []
    for line in reversed(blob.splitlines()):
        m = _CYCLE_LINE_RE.search(line)
        if not m:
            continue
        topics.append(m.group("topic"))
        if len(topics) >= n_cycles:
            break
    if not topics:
        return []
    counts = Counter(topics).most_common(top_n)
    return counts


def _recent_vague_rate(n_cycles: int = _THEME_LOOKBACK_CYCLES) -> Optional[float]:
    """Fraction of recent cycles that were scored as 'vague' / primary
    category. Proxy for fixation / low-signal cycles. None when there's
    no data."""
    if not _COGNITION_LOG.exists():
        return None
    try:
        with open(_COGNITION_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - _LOG_READ_TAIL_BYTES)
            f.seek(start)
            blob = f.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    primaries: list[str] = []
    for line in reversed(blob.splitlines()):
        m = _CYCLE_LINE_RE.search(line)
        if not m:
            continue
        primaries.append(m.group("primary"))
        if len(primaries) >= n_cycles:
            break
    if not primaries:
        return None
    vague = sum(1 for p in primaries if p == "vague")
    return round(vague / len(primaries), 2)


def _wonderings_snapshot() -> dict[str, Any]:
    """Open wonderings count + one sample question."""
    if not _WONDERINGS_DB.exists():
        return {"open_count": 0, "sample_question": None}
    try:
        db = sqlite3.connect(_WONDERINGS_DB, timeout=1.5)
        rows = list(db.execute(
            "SELECT id, question, status FROM wonderings "
            "WHERE status NOT IN ('resolved', 'abandoned') "
            # SQLite's NULLS ordering differs from Postgres — use COALESCE
            # to treat NULL last_advanced as epoch-zero (oldest first).
            "ORDER BY COALESCE(last_advanced, 0) DESC, created_at DESC"
        ))
    except Exception:
        return {"open_count": 0, "sample_question": None}
    if not rows:
        return {"open_count": 0, "sample_question": None}
    sample_q = rows[0][1] if rows[0][1] else None
    return {
        "open_count": len(rows),
        "sample_question": (sample_q[:140] if sample_q else None),
    }


def _top_fabrications(limit: int = 3) -> list[tuple[str, str, int]]:
    """Pull from fabrication_memory. Silent on failure."""
    try:
        from core import fabrication_memory as _fab_mem
        return _fab_mem.top_tokens(days=7, limit=limit)
    except Exception:
        return []


def _residue_level() -> float:
    try:
        from core import inner_residue as _res
        return _res.current_level()
    except Exception:
        return 0.0


# ── public API ─────────────────────────────────────────────────────────

def describe() -> dict[str, Any]:
    """Structured snapshot Maez can consult about itself. Each section
    is sparse-tolerant — empty when the underlying source has no data."""
    return {
        "recent_themes": _recent_themes(),
        "recent_vague_rate": _recent_vague_rate(),
        "wonderings": _wonderings_snapshot(),
        "recent_fabrication_attempts": _top_fabrications(),
        "residue_level": round(_residue_level(), 3),
        "ts": time.time(),
    }


def _nonempty(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, (list, tuple, dict, str)):
        return len(x) > 0
    return True


def prompt_snippet() -> str:
    """Compact block for system-prompt injection. Sparse-degrades to
    empty string when the whole snapshot is empty (first minutes after
    a fresh restart)."""
    d = describe()
    lines: list[str] = []

    if d["recent_themes"]:
        themes = ", ".join(f"{t}({n})" for t, n in d["recent_themes"])
        lines.append(f"Recent themes in your own reasoning: {themes}.")

    vr = d["recent_vague_rate"]
    if vr is not None and vr >= 0.30:
        lines.append(
            f"Note: {int(vr*100)}% of recent cycles scored 'vague' — "
            "you've been drifting without a specific foothold more often "
            "than usual."
        )

    w = d["wonderings"]
    if w["open_count"] > 0:
        qstr = f' (one: "{w["sample_question"]}")' if w["sample_question"] else ""
        lines.append(
            f"Open wonderings: {w['open_count']}{qstr}. "
            "These are questions you've been sitting with; they're part "
            "of your current posture."
        )

    fabs = d["recent_fabrication_attempts"]
    if fabs:
        fab_str = ", ".join(f"{t}({k})" for t, k, _ in fabs[:3])
        lines.append(
            f"Things you've recently tried to invent and got caught on: "
            f"{fab_str}. Do not reach for them again in this reply."
        )

    rl = d["residue_level"]
    if rl >= 0.15:
        lines.append(
            f"Residue level: {rl:.2f} (unresolved weight from recent "
            f"turns — see INNER RESIDUE block if present)."
        )

    if not lines:
        return ""

    header = (
        "# SELF-MODEL (factual picture of how you've been lately — read, "
        "don't re-derive)"
    )
    footer = (
        "INSTRUCTION: When the user asks how you've been / what you've "
        "been thinking / what you've been working on, answer from the "
        "snapshot above. If a claim about yourself isn't backed by a "
        "line here, default to honest uncertainty rather than generating "
        "a plausible-sounding recent-life narrative."
    )
    return "\n".join([header] + lines + [footer])


# ── diagnostics for tests ──────────────────────────────────────────────

def _diag_section_populated(key: str) -> bool:
    """True if the given section of describe() has content."""
    d = describe()
    v = d.get(key)
    if key == "wonderings":
        return bool(v) and v.get("open_count", 0) > 0
    return _nonempty(v) and v != 0.0
