# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability gap matcher (Step 2 of the Decision-19/20 pipeline arc).

Takes a *felt limitation* string from the operator (or, eventually,
from Maez's own gap-sensing layer) and returns ranked manual entries
whose ``gap_signals`` overlap with the query.

V1 contract:
- Deterministic lexical only. No LLM, no embeddings, no field search.
- Stopword-filtered token overlap with phrase/subphrase boost and a
  small curated boost-term list.
- Score normalized to ``[0.0, 1.0]``.
- Stable ordering: score desc, capability_id asc.

The scoring function (``_score_entry``) is intentionally isolated so
v1.5 can swap in hybrid semantic scoring (against the same locally-
shipped Chroma embedder Maez already runs) without changing callers
or the ``CapabilityMatch`` shape. The ``test_known_lexical_miss_*``
test in ``tests/test_capability_gap_matcher.py`` documents the v1
limitation; flipping its assertion is the visible behavior change
when v1.5 ships.

Body markdown is intentionally NOT consulted for matching. It is
preserved on the entry for the proposal generator (Step 4) to use
when explaining a candidate to the owner.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.capability_manual import CapabilityEntry, ManualLoadResult

logger = logging.getLogger(__name__)


# ── stopwords + boost terms ────────────────────────────────────────


# Small curated stopword list. Without this, score > 0 is vacuous —
# every query overlaps with every entry through grammar glue. NOT
# pulled from NLTK because we don't want a runtime dep for ~100
# words; this list is the standard short English stopword set.
_STOPWORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "arent", "as", "at", "be", "because",
    "been", "before", "being", "below", "between", "both", "but",
    "by", "cant", "cannot", "could", "couldnt", "did", "didnt", "do",
    "does", "doesnt", "doing", "dont", "down", "during", "each",
    "few", "for", "from", "further", "had", "hadnt", "has", "hasnt",
    "have", "havent", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "isnt", "it", "its", "itself", "just", "lets", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "shouldnt", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was",
    "wasnt", "we", "were", "werent", "what", "when", "where", "which",
    "while", "who", "whose", "why", "with", "would", "wouldnt", "you",
    "your", "yours", "yourself", "yourselves", "us", "ourselves",
    "ll", "ve", "re", "d", "s", "t", "m",  # contraction tails
})

# Domain boost terms — tokens whose presence indicates topical
# weight in capability-manual context. These are NOT in stopwords;
# matched-stopword overlap doesn't help score, but matched-boost
# overlap adds a small fixed bonus.
_BOOST_TERMS: frozenset[str] = frozenset({
    "memory", "memories", "context", "temporal", "temporally",
    "entity", "entities", "session", "sessions", "recall", "audit",
    "repo", "repository", "codebase", "synthesis", "synthesize",
    "synthesizing", "synthesized", "consolidate", "consolidation",
    "preference", "preferences", "preferred", "before", "after",
    "since", "duration", "month", "months", "year", "years", "week",
    "weeks", "day", "days", "ago",
})
_BOOST_PER_TERM: float = 0.05  # cumulative cap is 1.0 via final clamp
_PHRASE_HIT_BONUS: float = 0.15

# Word-character regex used for tokenization. Matches alphanumeric
# runs; punctuation and apostrophes are dropped (so "can't" → "cant"
# which then hits the stopword list).
_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ── module-level lazy cache ────────────────────────────────────────


_CACHED_MANUAL: ManualLoadResult | None = None
_CACHE_LOCK = threading.Lock()


def clear_cache() -> None:
    """Drop any cached manual. Used by tests; in production the
    cache lasts the daemon's lifetime."""
    global _CACHED_MANUAL
    with _CACHE_LOCK:
        _CACHED_MANUAL = None


def _get_default_manual() -> ManualLoadResult:
    """Lazy-cached load of the default manual at
    ``docs/maez_manual/``. First call loads; subsequent calls reuse.
    Thread-safe via a coarse module-level lock."""
    global _CACHED_MANUAL
    with _CACHE_LOCK:
        if _CACHED_MANUAL is None:
            from core.capability_manual import load_manual
            _CACHED_MANUAL = load_manual()
        return _CACHED_MANUAL


# ── dataclass ──────────────────────────────────────────────────────


@dataclass
class CapabilityMatch:
    """One ranked match. Exposes both the score and the explanation
    surface (matched_signals, matched_terms) so a future v1.5 can
    add semantic similarity alongside without breaking callers.

    ``entry`` is the full ``CapabilityEntry`` so downstream consumers
    (Step 3 evaluator, Step 4 proposal generator) can read the body
    markdown without re-loading.
    """
    capability_id: str
    title: str
    score: float
    matched_signals: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    status: str = ""
    source_path: Path | None = None
    entry: object | None = None  # CapabilityEntry; typed loose to avoid cycle


# ── tokenization + scoring (the swappable seam) ────────────────────


def _tokenize(text: str) -> list[str]:
    """Lowercase, drop punctuation, split on word boundaries."""
    return _TOKEN_RE.findall((text or "").lower())


def _content_tokens(tokens: list[str]) -> set[str]:
    """Filter out stopwords. Returns a set so overlap counts are
    membership-based (no double-counting repeated content words)."""
    return {t for t in tokens if t and t not in _STOPWORDS}


def _phrase_hit(query_tokens: list[str], signal_tokens: list[str]) -> bool:
    """Detect a shared n-gram of ≥2 consecutive content tokens.

    A naive substring check is too permissive — "ing th" appears
    inside both "forgetting things" and "thing they've", which is
    a spurious match (suffix/prefix collision, not a real phrase).
    This implementation requires the overlap to be n consecutive
    NON-STOPWORD tokens in BOTH the query and the signal, which is
    what "phrase/subphrase" actually means.
    """
    q_content = [t for t in query_tokens if t and t not in _STOPWORDS]
    s_content = [t for t in signal_tokens if t and t not in _STOPWORDS]
    if len(q_content) < 2 or len(s_content) < 2:
        return False
    # Try larger n first to prefer longer matched phrases.
    max_n = min(4, len(q_content), len(s_content))
    for n in range(max_n, 1, -1):
        q_ngrams = {
            tuple(q_content[i:i + n])
            for i in range(len(q_content) - n + 1)
        }
        s_ngrams = {
            tuple(s_content[i:i + n])
            for i in range(len(s_content) - n + 1)
        }
        if q_ngrams & s_ngrams:
            return True
    return False


def _score_entry(
    felt_limitation: str, entry: CapabilityEntry,
) -> CapabilityMatch | None:
    """Score one entry against the query. Returns None if the entry
    doesn't pass the score>0 threshold.

    SWAPPABLE SEAM: v1.5 (planned) replaces this function's body
    with hybrid lexical+semantic scoring against locally-shipped
    Chroma embeddings. The CapabilityMatch shape and the public API
    don't change. The ``test_known_lexical_miss_natural_phrasing``
    test documents what v1 misses; flipping its assertion is the
    visible upgrade contract.
    """
    query_tokens = _tokenize(felt_limitation)
    if not query_tokens:
        return None
    query_content = _content_tokens(query_tokens)
    if not query_content:
        return None

    matched_signals: list[str] = []
    matched_terms: set[str] = set()
    best_signal_overlap = 0
    phrase_hits = 0
    boost_hits: set[str] = set()

    for signal in entry.gap_signals:
        sig_tokens = _tokenize(signal)
        sig_content = _content_tokens(sig_tokens)
        overlap = query_content & sig_content
        phrase_hit = _phrase_hit(query_tokens, sig_tokens)

        if overlap:
            matched_signals.append(signal)
            matched_terms |= overlap
            best_signal_overlap = max(best_signal_overlap, len(overlap))
            for t in overlap:
                if t in _BOOST_TERMS:
                    boost_hits.add(t)
        elif phrase_hit:
            # Phrase-hit-only signals also count as matched for
            # explainability — there's a real overlap span even
            # without token-set intersection.
            matched_signals.append(signal)

        if phrase_hit:
            phrase_hits += 1

    if not matched_signals:
        return None

    # Normalize: best signal's content overlap fraction. Then add
    # boost-term and phrase bonuses, clamping to 1.0 at the end.
    # Denominator is the larger of the two content-token sets to
    # keep scores comparable across query/signal lengths.
    base = 0.0
    if best_signal_overlap:
        # Find the signal that achieved the best overlap to use as
        # denominator anchor.
        max_denom = 1
        for signal in entry.gap_signals:
            sig_content = _content_tokens(_tokenize(signal))
            denom = max(len(query_content), len(sig_content))
            if denom > max_denom:
                max_denom = denom
        base = best_signal_overlap / max_denom

    score = base + (_BOOST_PER_TERM * len(boost_hits))
    score += (_PHRASE_HIT_BONUS * phrase_hits)
    if score <= 0.0:
        return None
    score = min(score, 1.0)

    return CapabilityMatch(
        capability_id=entry.capability_id,
        title=entry.title,
        score=score,
        matched_signals=matched_signals,
        matched_terms=sorted(matched_terms),
        status=entry.status,
        source_path=entry.source_path,
        entry=entry,
    )


# ── public API ─────────────────────────────────────────────────────


def rank_capabilities(
    felt_limitation: str,
    entries: list[CapabilityEntry],
    *,
    include_deprecated: bool = False,
    limit: int = 5,
) -> list[CapabilityMatch]:
    """Rank a list of entries against a felt-limitation query.
    Returns matches with score > 0, sorted by (-score, capability_id).
    Tie-break is deterministic.
    """
    if not (felt_limitation or "").strip():
        return []
    matches: list[CapabilityMatch] = []
    for entry in entries:
        if entry.status == "deprecated" and not include_deprecated:
            continue
        m = _score_entry(felt_limitation, entry)
        if m is not None and m.score > 0:
            matches.append(m)
    matches.sort(key=lambda m: (-m.score, m.capability_id))
    if limit and limit > 0:
        matches = matches[:limit]
    return matches


def match_gap(
    felt_limitation: str,
    manual: ManualLoadResult | None = None,
    *,
    include_deprecated: bool = False,
    limit: int = 5,
) -> list[CapabilityMatch]:
    """Match a felt limitation against the manual.

    ``manual=None`` triggers a lazy-cached load of the default
    manual at ``docs/maez_manual/``. Tests use ``clear_cache()`` to
    force a reload.
    """
    if manual is None:
        manual = _get_default_manual()
    matches = rank_capabilities(
        felt_limitation, manual.entries,
        include_deprecated=include_deprecated, limit=limit,
    )
    _record_telemetry(felt_limitation, matches)
    return matches


# ── telemetry (best-effort; never breaks matching) ─────────────────


def _telemetry_path() -> Path:
    """Resolve the telemetry log path through ``core.paths`` so it
    lands in the canonical ``logs/`` directory regardless of cwd."""
    try:
        from core import paths as _paths
        return _paths.logs_dir() / "capability_matcher.jsonl"
    except Exception:  # pragma: no cover — defensive fallback
        return Path("logs/capability_matcher.jsonl")


def _record_telemetry(
    felt_limitation: str,
    matches: list[CapabilityMatch],
) -> None:
    """Best-effort telemetry: write one JSON line per call. ANY
    failure here is swallowed — matching must never fail because
    the log file is unwritable, the disk is full, or the path
    helper raised."""
    try:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": felt_limitation,
            "matched_count": len(matches),
            "top_score": matches[0].score if matches else None,
            "top_capability_id": (
                matches[0].capability_id if matches else None
            ),
        }
        _append_telemetry(payload)
    except Exception as e:
        # Never raise from the telemetry path. Log at debug; the
        # caller's match result is unaffected.
        logger.debug("capability_matcher telemetry suppressed: %s", e)


def _append_telemetry(payload: dict) -> None:
    """Append one JSON line to the telemetry log. Patched in tests
    to simulate write failure. Production callers go through
    ``_record_telemetry`` which catches everything this raises."""
    log_path = _telemetry_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


__all__ = [
    "CapabilityMatch",
    "_get_default_manual",  # exposed for test cache verification
    "clear_cache",
    "match_gap",
    "rank_capabilities",
]
