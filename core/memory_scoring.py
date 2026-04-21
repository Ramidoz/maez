# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""memory_scoring.py — concept tags, recall statistics, 6-factor
promotion scoring for memories.

Borrowed 2026-04-21 from OpenClaw's extensions/memory-core/src/
short-term-promotion.ts (MIT). Scoped down to the data layer: Maez
gets the structures and the scorer function; dream-state integration
is a follow-up.

What this module provides:

  derive_concept_tags(text, max_tags=8)
      Returns up to max_tags short semantic tags extracted from the
      content. Stored in Chroma metadata at write time — lightweight
      complement to the existing 'wing' / 'cog_topic' categorical tag.

  RecallStats dataclass + record_recall() + get_stats()
      Per-memory recall tracking in a SQLite sidecar. Tracks how often
      a memory is actually used, how many distinct queries surfaced it,
      and across how many days — signals the current Chroma distance
      can't express. Diversity and frequency signals feed promotion.

  promotion_score(stats, weights=DEFAULT, now=None)
      6-factor weighted score in [0, 1]:
        frequency     0.24  (recall + daily counts)
        relevance     0.30  (max similarity score observed)
        diversity     0.15  (distinct query-hash count, saturating)
        recency       0.15  (exp decay, 14-day half-life)
        consolidation 0.10  (already-consolidated flag)
        conceptual    0.06  (concept-tag count, saturating)

  This module is OBSERVATIONAL in this commit: it records data and
  exposes the scorer. Dream-state does NOT yet call promotion_score()
  to gate consolidation; that integration lands separately once the
  recall distribution is observed. The current consolidation path is
  unchanged.

Fail-SAFE: every public entry point is wrapped so DB errors never
propagate into the recall/store path. If the sidecar DB is missing,
readers return empty stats and writers silently no-op.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.memory_scoring")

_DB_PATH = Path("/home/rohit/maez/memory/recall_stats.db")
_MAX_QUERY_HASHES = 32      # same ceiling as OpenClaw; caps diversity score
_MAX_RECALL_DAYS = 16       # ceiling for frequency-via-days
MAX_CONCEPT_TAGS = 8        # matches OpenClaw constant
_RECENCY_HALF_LIFE_DAYS = 14.0
_DAY_SECONDS = 86400.0


# ── weights ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PromotionWeights:
    frequency: float = 0.24
    relevance: float = 0.30
    diversity: float = 0.15
    recency: float = 0.15
    consolidation: float = 0.10
    conceptual: float = 0.06


DEFAULT_WEIGHTS = PromotionWeights()


# ── recall stats row ──────────────────────────────────────────────────

@dataclass
class RecallStats:
    memory_id: str
    recall_count: int = 0
    # Running max of relevance scores observed on recall (1 - distance).
    max_relevance: float = 0.0
    # Hashes of queries that surfaced this memory — bounded to _MAX_QUERY_HASHES.
    # Stored as comma-separated short hashes in the DB for cheap diff/dedup.
    query_hashes: list[str] = field(default_factory=list)
    # Distinct YYYY-MM-DD strings on which the memory was recalled.
    recall_days: list[str] = field(default_factory=list)
    # Concept tags; mirrored from the memory's metadata for scoring convenience.
    concept_tags: list[str] = field(default_factory=list)
    # Monotonic UNIX timestamp of most recent recall (for recency decay).
    last_recalled_at: float = 0.0
    # True once the memory has been consolidated to daily/core tier.
    consolidated: bool = False


# ── concept tag derivation ────────────────────────────────────────────

# Minimal English stopword list. Tagging is advisory — missing a few
# common words doesn't materially hurt the diversity/conceptual signal.
# Purposely short; a bigger list is premature until we see the signal
# in live data.
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "could", "may", "might", "can", "i", "you", "he", "she", "it", "we",
    "they", "me", "him", "her", "us", "them", "my", "your", "his", "its",
    "our", "their", "this", "that", "these", "those", "and", "or", "but",
    "so", "if", "then", "else", "when", "where", "why", "how", "what",
    "which", "who", "whom", "to", "of", "in", "on", "at", "by", "for",
    "from", "with", "about", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "not", "no", "yes", "ok",
    "okay", "just", "very", "much", "more", "most", "some", "any", "all",
    "every", "each", "one", "two", "three", "there", "here", "now",
    "today", "yesterday", "tomorrow",
})

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{2,}")


def derive_concept_tags(text: str, max_tags: int = MAX_CONCEPT_TAGS) -> list[str]:
    """Extract up to max_tags lightweight concept tags from text.

    Strategy: lowercase tokenize (≥3 chars, alphabetic-starting), drop
    stopwords, dedupe preserving first-seen order, cap at max_tags.
    Deterministic — same input always returns same tags.

    Returns [] if text is empty or produces nothing useful.
    """
    if not text or not isinstance(text, str):
        return []
    lower = text.lower()
    tags: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(lower):
        tok = match.group(0)
        if tok in _STOPWORDS or tok in seen:
            continue
        seen.add(tok)
        tags.append(tok)
        if len(tags) >= max_tags:
            break
    return tags


# ── SQLite sidecar ────────────────────────────────────────────────────

def _ensure_db() -> Optional[sqlite3.Connection]:
    """Open or create the recall_stats DB. Returns None on any failure
    so callers fall back to a no-op."""
    try:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(_DB_PATH, timeout=2.0, check_same_thread=False)
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS recall_stats (
                memory_id TEXT PRIMARY KEY,
                recall_count INTEGER NOT NULL DEFAULT 0,
                max_relevance REAL NOT NULL DEFAULT 0.0,
                query_hashes TEXT NOT NULL DEFAULT '',
                recall_days TEXT NOT NULL DEFAULT '',
                concept_tags TEXT NOT NULL DEFAULT '',
                last_recalled_at REAL NOT NULL DEFAULT 0.0,
                consolidated INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.commit()
        return db
    except Exception as e:
        logger.debug("recall_stats db unavailable: %s", e)
        return None


def _hash_query(query: str) -> str:
    """12-char hash so the stored list stays cheap to compare/dedup."""
    return hashlib.md5((query or "").encode("utf-8")).hexdigest()[:12]


def record_recall(
    memory_id: str,
    *,
    query: str = "",
    relevance: float = 0.0,
    concept_tags: Optional[list[str]] = None,
    now: Optional[float] = None,
) -> None:
    """Record one recall of a memory. Updates counter, query-hash list
    (bounded), day list, max relevance, and last_recalled_at.

    Never raises. Advisory — dropping a record on DB failure doesn't
    corrupt anything."""
    if not memory_id:
        return
    db = _ensure_db()
    if db is None:
        return
    try:
        ts = now if now is not None else time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        qhash = _hash_query(query) if query else ""

        cur = db.execute(
            "SELECT recall_count, max_relevance, query_hashes, recall_days, "
            "concept_tags, last_recalled_at, consolidated FROM recall_stats "
            "WHERE memory_id = ?",
            (memory_id,),
        )
        row = cur.fetchone()

        if row is None:
            hashes = qhash
            days = day
            tags_str = ",".join(concept_tags or [])
            db.execute(
                "INSERT INTO recall_stats (memory_id, recall_count, max_relevance, "
                "query_hashes, recall_days, concept_tags, last_recalled_at, consolidated) "
                "VALUES (?, 1, ?, ?, ?, ?, ?, 0)",
                (memory_id, float(relevance), hashes, days, tags_str, ts),
            )
        else:
            rc, mr, hashes_s, days_s, tags_s, _last, _cons = row
            # Update bounded lists
            hashes_list = [h for h in hashes_s.split(",") if h]
            if qhash and qhash not in hashes_list:
                hashes_list.append(qhash)
                if len(hashes_list) > _MAX_QUERY_HASHES:
                    hashes_list = hashes_list[-_MAX_QUERY_HASHES:]
            days_list = [d for d in days_s.split(",") if d]
            if day not in days_list:
                days_list.append(day)
                if len(days_list) > _MAX_RECALL_DAYS:
                    days_list = days_list[-_MAX_RECALL_DAYS:]
            new_mr = max(float(mr), float(relevance))
            new_tags = tags_s
            if concept_tags and not new_tags:
                new_tags = ",".join(concept_tags)
            db.execute(
                "UPDATE recall_stats SET recall_count = ?, max_relevance = ?, "
                "query_hashes = ?, recall_days = ?, concept_tags = ?, "
                "last_recalled_at = ? WHERE memory_id = ?",
                (rc + 1, new_mr, ",".join(hashes_list), ",".join(days_list),
                 new_tags, ts, memory_id),
            )
        db.commit()
    except Exception as e:
        logger.debug("record_recall failed (ignored): %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_stats(memory_id: str) -> RecallStats:
    """Read stats for a memory. Returns an empty RecallStats on any failure
    or when no row exists — the promotion_score treats that as untracked."""
    stats = RecallStats(memory_id=memory_id)
    if not memory_id:
        return stats
    db = _ensure_db()
    if db is None:
        return stats
    try:
        cur = db.execute(
            "SELECT recall_count, max_relevance, query_hashes, recall_days, "
            "concept_tags, last_recalled_at, consolidated FROM recall_stats "
            "WHERE memory_id = ?",
            (memory_id,),
        )
        row = cur.fetchone()
        if row is None:
            return stats
        rc, mr, hashes_s, days_s, tags_s, last, cons = row
        stats.recall_count = int(rc)
        stats.max_relevance = float(mr)
        stats.query_hashes = [h for h in hashes_s.split(",") if h]
        stats.recall_days = [d for d in days_s.split(",") if d]
        stats.concept_tags = [t for t in tags_s.split(",") if t]
        stats.last_recalled_at = float(last)
        stats.consolidated = bool(cons)
    except Exception as e:
        logger.debug("get_stats failed (ignored): %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass
    return stats


def mark_consolidated(memory_id: str) -> None:
    """Set the consolidated flag for a memory. Called by dream-state
    once a memory has been summarized into daily/core. Never raises."""
    if not memory_id:
        return
    db = _ensure_db()
    if db is None:
        return
    try:
        db.execute(
            "UPDATE recall_stats SET consolidated = 1 WHERE memory_id = ?",
            (memory_id,),
        )
        db.commit()
    except Exception as e:
        logger.debug("mark_consolidated failed (ignored): %s", e)
    finally:
        try:
            db.close()
        except Exception:
            pass


# ── promotion score ───────────────────────────────────────────────────

def promotion_score(
    stats: RecallStats,
    *,
    weights: PromotionWeights = DEFAULT_WEIGHTS,
    now: Optional[float] = None,
) -> float:
    """6-factor weighted score in [0, 1]. Higher = stronger promotion
    candidate. Deterministic; never raises."""
    # Frequency: combines recall_count (saturating) with distinct days.
    # Saturates at 20 recalls or 16 days — beyond that, more noise than signal.
    freq_from_count = min(1.0, stats.recall_count / 20.0)
    freq_from_days = min(1.0, len(stats.recall_days) / float(_MAX_RECALL_DAYS))
    frequency = 0.5 * freq_from_count + 0.5 * freq_from_days

    # Relevance: max similarity score observed on recall.
    relevance = max(0.0, min(1.0, stats.max_relevance))

    # Diversity: how many distinct queries surfaced this memory.
    # Saturates at _MAX_QUERY_HASHES — a memory that matches 32+ distinct
    # queries is genuinely versatile and doesn't need more proof.
    diversity = min(1.0, len(stats.query_hashes) / float(_MAX_QUERY_HASHES))

    # Recency: exponential decay with 14-day half-life from last recall.
    # Untracked (last_recalled_at=0) → recency 0.
    if stats.last_recalled_at > 0:
        now_ts = now if now is not None else time.time()
        age_days = max(0.0, (now_ts - stats.last_recalled_at) / _DAY_SECONDS)
        recency = math.exp(-age_days * math.log(2.0) / _RECENCY_HALF_LIFE_DAYS)
    else:
        recency = 0.0

    # Consolidation: boolean flag.
    consolidation = 1.0 if stats.consolidated else 0.0

    # Conceptual: how rich the tag set is. Saturates at MAX_CONCEPT_TAGS.
    conceptual = min(1.0, len(stats.concept_tags) / float(MAX_CONCEPT_TAGS))

    total = (
        weights.frequency * frequency
        + weights.relevance * relevance
        + weights.diversity * diversity
        + weights.recency * recency
        + weights.consolidation * consolidation
        + weights.conceptual * conceptual
    )
    # Clamp to [0, 1] — weights should sum to 1 but numeric drift is possible.
    return max(0.0, min(1.0, total))


# ── diagnostics ───────────────────────────────────────────────────────

def _diag_db_path() -> Path:
    return _DB_PATH


def _diag_clear_for_test() -> None:
    """Test helper — wipe the recall_stats table."""
    db = _ensure_db()
    if db is None:
        return
    try:
        db.execute("DELETE FROM recall_stats")
        db.commit()
    finally:
        try:
            db.close()
        except Exception:
            pass
