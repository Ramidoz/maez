# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Entity sidecar substrate + deterministic query expansion (Step 5e
— prerequisite to multi-session entity linking).

This module is **substrate only**. It does NOT extract entities via
LLM, does NOT run at consolidation time, does NOT re-rank recall,
and does NOT mutate any other store. It provides:

  • A SQLite sidecar at ``memory/entity_index.db`` with three tables:
    - ``entities``         — canonical name + normalized name + kind
    - ``entity_mentions``  — pointer rows linking an entity to a
                             specific session/source/snippet
    - ``aliases``          — alternate surfaces that resolve to an
                             entity (per-entity, not globally unique;
                             ambiguous aliases divide confidence)

  • A pure deterministic extractor that emits multi-token capitalized
    runs (≥2 tokens) and refuses sentence-start junk; single-word
    entities are opt-in via an ``known_entities`` allowlist.

  • A query-expansion entry point that returns the union of session
    ids and source ids associated with the matched entities, ordered
    most-recent-first, capped at ``limit_sessions``.

Naming note: ``session_id`` in the schema is the container of a
mention. In v1 it is identical to an episode id (``ep-...``). The
field name is reserved for a future cross-store generalization;
callers should pass episode ids today.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── default DB location ───────────────────────────────────────────


def _default_index_path() -> Path:
    """Resolve the canonical index path under ``memory/entity_index.db``.

    Runtime data lives under ``memory/``; code lives under
    ``core/memory/``. Phase-5.A test_smoke_imports caught a regression
    where ``Path(__file__).parent.parent`` was used in moved modules,
    silently writing runtime DBs into the source tree. Going through
    ``core.paths`` here avoids the same trap."""
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "entity_index.db"
    except Exception:
        return Path("memory/entity_index.db")


# ── normalization ─────────────────────────────────────────────────


_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_entity_name(text: str) -> str:
    """Deterministic, idempotent normalization for matching/dedup.

    Steps: NFC-fold (so composed and decomposed unicode forms collide),
    lowercase, strip punctuation, collapse whitespace. The output is
    suitable as the unique-key column on ``entities``; the original
    surface is preserved separately as ``canonical_name`` for display.
    """
    if not text:
        return ""
    folded = unicodedata.normalize("NFC", text)
    lowered = folded.lower()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", no_punct).strip()


# ── deterministic extractor ───────────────────────────────────────


@dataclass
class EntityCandidate:
    """One extractor finding. ``confidence`` is heuristic-driven and
    bounded to [0, 1]; v1 returns 0.7 for multi-token runs and 0.5
    for single-token allowlist hits — values are conservative because
    the extractor never sees a model and must not pretend to."""
    surface: str
    normalized: str
    kind: str
    span_start: int
    span_end: int
    confidence: float


# Sentence-starting words that look capitalized but aren't entity
# starts. This is a closed set; novel sentence-start junk should
# accumulate here rather than expanding the heuristic.
_SENTENCE_START_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "today", "tomorrow", "yesterday", "tonight",
    "i", "we", "you", "he", "she", "it", "they",
    "my", "your", "our", "his", "her", "its", "their",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "but", "and", "or", "so", "yet",
    "when", "where", "what", "why", "how", "who", "which",
})


# Capitalized token: starts with uppercase letter, followed by
# lowercase or apostrophes / hyphens. "Maya", "O'Brien", "Smith-Jones".
_CAP_TOKEN = re.compile(r"\b[A-Z][a-zA-Z'\-]*\b")
# Any word-token (case-insensitive). Used by the matcher to also try
# lowercase tokens against the case-insensitive find_entities index.
# 2026-05-02: zero-fires investigation found _scan_query_for_matches
# only seeded Capital-case tokens, so natural-text Telegram traffic
# ("how is maez doing") never reached the data layer despite the
# index being case-insensitive. Length ≥ 2 skips trivial single-letter
# tokens that can't be entities.
#
# Unicode: \w with re.UNICODE catches diacritics ("josé" inside "did
# josé call") that the older ASCII-only `[a-zA-Z]` class would have
# silently dropped. normalize_entity_name does NFC-fold downstream so
# the data-layer comparison sees the same form regardless of whether
# the surface entered via canonical-store or natural query.
_WORD_TOKEN = re.compile(r"\b\w[\w'\-]+\b", re.UNICODE)
# Sentence-boundary detector. Permissive — false positives on
# abbreviations are tolerated because the only consequence is that
# the extractor checks one extra word against the stopword set.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _sentence_starts(text: str) -> list[int]:
    """Character indices at which a new sentence starts."""
    starts = [0]
    for m in _SENTENCE_BOUNDARY.finditer(text):
        starts.append(m.end())
    return starts


def _is_sentence_start(idx: int, sentence_starts: Sequence[int]) -> bool:
    """True iff ``idx`` is the first non-whitespace character of a
    sentence — used to apply stopword filtering only at boundary."""
    return idx in sentence_starts


def extract_deterministic_entities(
    text: str,
    *,
    known_entities: Iterable[str] | None = None,
) -> list[EntityCandidate]:
    """Pure heuristic entity extraction. No LLM, no network.

    Default behaviour: emit ≥2 consecutive capitalized tokens whose
    first token is not a sentence-start stopword. Single-token entities
    are emitted only when their surface (case-insensitive) appears in
    ``known_entities`` — this is the load-bearing precision rule from
    the Step 5e pushback round."""
    if not text:
        return []

    sentence_starts = _sentence_starts(text)
    candidates: list[EntityCandidate] = []
    matches = list(_CAP_TOKEN.finditer(text))

    i = 0
    used_spans: list[tuple[int, int]] = []
    while i < len(matches):
        run = [matches[i]]
        j = i + 1
        while j < len(matches):
            prev_end = run[-1].end()
            next_start = matches[j].start()
            between = text[prev_end:next_start]
            # Adjacent if separated by whitespace only.
            if between and between.isspace():
                run.append(matches[j])
                j += 1
            else:
                break

        if len(run) >= 2:
            first_norm = run[0].group(0).lower()
            if first_norm in _SENTENCE_START_STOPWORDS and _is_sentence_start(
                run[0].start(), sentence_starts,
            ):
                # Drop junk-start runs like "The Hospital",
                # "Tomorrow Maya" — but only when the stopword sits
                # at sentence boundary. "I met John F Kennedy" is
                # safe because the run starts at "John".
                if len(run) > 2:
                    # Trim the leading stopword and re-evaluate the
                    # remainder as its own run.
                    run = run[1:]
                    first_norm = run[0].group(0).lower()
                    if (
                        first_norm in _SENTENCE_START_STOPWORDS
                        or len(run) < 2
                    ):
                        i = j
                        continue
                else:
                    i = j
                    continue
            start = run[0].start()
            end = run[-1].end()
            surface = text[start:end]
            normalized = normalize_entity_name(surface)
            if normalized:
                candidates.append(EntityCandidate(
                    surface=surface,
                    normalized=normalized,
                    kind="unknown",
                    span_start=start,
                    span_end=end,
                    confidence=0.7,
                ))
                used_spans.append((start, end))
        i = j

    if known_entities:
        # Single-word allowlist pass. Skip any surface that already
        # landed inside a multi-token run (avoid double-emit).
        known_norm = {
            normalize_entity_name(k) for k in known_entities if k
        }

        def _inside_used(s: int, e: int) -> bool:
            for us, ue in used_spans:
                if us <= s and e <= ue:
                    return True
            return False

        for m in matches:
            surface = m.group(0)
            n = normalize_entity_name(surface)
            if n in known_norm and not _inside_used(m.start(), m.end()):
                candidates.append(EntityCandidate(
                    surface=surface,
                    normalized=n,
                    kind="unknown",
                    span_start=m.start(),
                    span_end=m.end(),
                    confidence=0.5,
                ))

    candidates.sort(key=lambda c: (c.span_start, c.span_end))
    return candidates


# ── result dataclasses ────────────────────────────────────────────


@dataclass
class EntityMatch:
    """One candidate entity for a query token, with ambiguity-aware
    confidence. ``confidence`` is divided by the number of entities
    sharing the matched surface (canonical OR alias) — so an
    ambiguous "Maya" returns each candidate at 1.0 / N rather than
    pretending only one entity is meant."""
    entity_id: str
    canonical_name: str
    kind: str
    confidence: float
    matched_via: str  # "canonical" | "alias"


@dataclass
class QueryExpansion:
    """Result of expanding a query through the entity index. The
    ``confidence`` is the max across matched entities — a strong
    canonical hit retains full confidence even when other matches
    are ambiguous."""
    original_query: str
    matched_entities: list[EntityMatch]
    session_ids: list[str]
    source_ids: list[str]
    explanation: str
    confidence: float = 0.0
    mentions: list[dict] = field(default_factory=list)


# ── store ─────────────────────────────────────────────────────────


class EntityIndex:
    """SQLite-backed entity sidecar.

    All writes go through ``upsert_entity`` / ``add_alias`` /
    ``add_mention``. There is no public delete API — the never-delete
    covenant applies here too: entities that turn out to be wrong are
    superseded or marked low-confidence at mention time, never
    removed."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS entities (
        id              TEXT PRIMARY KEY,
        canonical_name  TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        kind            TEXT NOT NULL,
        created_at      REAL NOT NULL,
        UNIQUE(normalized_name, kind)
    );

    CREATE TABLE IF NOT EXISTS aliases (
        id               TEXT PRIMARY KEY,
        entity_id        TEXT NOT NULL,
        alias            TEXT NOT NULL,
        normalized_alias TEXT NOT NULL,
        created_at       REAL NOT NULL,
        UNIQUE(entity_id, normalized_alias),
        FOREIGN KEY(entity_id) REFERENCES entities(id)
    );
    CREATE INDEX IF NOT EXISTS idx_aliases_norm
        ON aliases(normalized_alias);

    CREATE TABLE IF NOT EXISTS entity_mentions (
        id            TEXT PRIMARY KEY,
        entity_id     TEXT NOT NULL,
        session_id    TEXT NOT NULL,
        source_id     TEXT NOT NULL,
        source_kind   TEXT NOT NULL,
        observed_at   TEXT NOT NULL,
        snippet       TEXT,
        confidence    REAL NOT NULL,
        created_at    REAL NOT NULL,
        UNIQUE(entity_id, session_id, source_id),
        FOREIGN KEY(entity_id) REFERENCES entities(id)
    );
    CREATE INDEX IF NOT EXISTS idx_mentions_entity
        ON entity_mentions(entity_id);
    CREATE INDEX IF NOT EXISTS idx_mentions_observed
        ON entity_mentions(observed_at);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path == ":memory:":
            self.db_path = ":memory:"
            # Use a single shared connection for in-memory DBs so
            # writes from different methods see each other; otherwise
            # each call opens a fresh empty memory database.
            self._memory_con: sqlite3.Connection | None = sqlite3.connect(
                ":memory:", isolation_level=None,
            )
            self._memory_con.row_factory = sqlite3.Row
            self._memory_con.executescript(self._SCHEMA)
        else:
            self.db_path = (
                Path(db_path) if db_path else _default_index_path()
            )
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._memory_con = None
            with self._connect() as con:
                con.executescript(self._SCHEMA)
                con.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # Dual-mode: in-memory stores share ONE long-lived connection
        # (closing it would discard the database), so yield it WITHOUT
        # closing. File-mode opens a fresh connection per call and must
        # close it deterministically — leaving it open was the FD leak.
        if self._memory_con is not None:
            yield self._memory_con
            return
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    # ── writes ────────────────────────────────────────────────────

    def upsert_entity(
        self,
        canonical_name: str,
        *,
        kind: str,
        aliases: Iterable[str] | None = None,
    ) -> str:
        """Insert or fetch the entity keyed by
        ``(normalized_name, kind)``. Callers do not need to
        pre-normalize. Aliases passed here are ``add_alias``-d
        idempotently."""
        if not canonical_name or not canonical_name.strip():
            raise ValueError("canonical_name is required")
        if not kind:
            raise ValueError("kind is required")
        normalized = normalize_entity_name(canonical_name)
        if not normalized:
            raise ValueError(
                f"canonical_name {canonical_name!r} normalizes to empty"
            )

        with self._connect() as con:
            existing = con.execute(
                "SELECT id FROM entities "
                "WHERE normalized_name = ? AND kind = ?",
                (normalized, kind),
            ).fetchone()
            if existing is not None:
                entity_id = existing["id"]
            else:
                entity_id = "ent-" + uuid4().hex[:12]
                con.execute(
                    "INSERT INTO entities ("
                    "id, canonical_name, normalized_name, kind, created_at"
                    ") VALUES (?,?,?,?,?)",
                    (entity_id, canonical_name.strip(), normalized,
                     kind, time.time()),
                )
                if self._memory_con is None:
                    con.commit()

        if aliases:
            for a in aliases:
                if a:
                    self.add_alias(entity_id, a)

        return entity_id

    def add_alias(self, entity_id: str, alias: str) -> None:
        """Idempotent alias upsert. Aliases are unique per entity
        (a single entity cannot list 'Maya' twice), but the same
        alias may legitimately map to multiple entities — that is
        the load-bearing ambiguity ``find_entities`` exposes via
        confidence division."""
        if not alias or not alias.strip():
            return
        normalized = normalize_entity_name(alias)
        if not normalized:
            return
        with self._connect() as con:
            existing = con.execute(
                "SELECT id FROM aliases "
                "WHERE entity_id = ? AND normalized_alias = ?",
                (entity_id, normalized),
            ).fetchone()
            if existing is not None:
                return
            con.execute(
                "INSERT INTO aliases ("
                "id, entity_id, alias, normalized_alias, created_at"
                ") VALUES (?,?,?,?,?)",
                ("ali-" + uuid4().hex[:12], entity_id, alias.strip(),
                 normalized, time.time()),
            )
            if self._memory_con is None:
                con.commit()

    def add_mention(
        self,
        *,
        entity_id: str,
        session_id: str,
        source_id: str,
        source_kind: str,
        observed_at: str,
        snippet: str | None,
        confidence: float,
    ) -> str:
        """Idempotent on ``(entity_id, session_id, source_id)``. The
        same evidence pointer being asserted twice does not produce
        a second row; the first write wins."""
        if not all([entity_id, session_id, source_id, source_kind]):
            raise ValueError(
                "entity_id, session_id, source_id, source_kind all required"
            )
        with self._connect() as con:
            existing = con.execute(
                "SELECT id FROM entity_mentions "
                "WHERE entity_id = ? AND session_id = ? AND source_id = ?",
                (entity_id, session_id, source_id),
            ).fetchone()
            if existing is not None:
                return existing["id"]
            mid = "men-" + uuid4().hex[:12]
            con.execute(
                "INSERT INTO entity_mentions ("
                "id, entity_id, session_id, source_id, source_kind, "
                "observed_at, snippet, confidence, created_at"
                ") VALUES (?,?,?,?,?,?,?,?,?)",
                (mid, entity_id, session_id, source_id, source_kind,
                 observed_at, snippet, float(confidence), time.time()),
            )
            if self._memory_con is None:
                con.commit()
            return mid

    # ── reads ─────────────────────────────────────────────────────

    def get_entity(self, entity_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_aliases(self, entity_id: str) -> list[str]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT alias FROM aliases WHERE entity_id = ?",
                (entity_id,),
            ).fetchall()
        return [r["alias"] for r in rows]

    def list_mentions(self, entity_id: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM entity_mentions WHERE entity_id = ? "
                "ORDER BY observed_at DESC",
                (entity_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_entities(self, query: str) -> list[EntityMatch]:
        """Return all entities whose canonical name OR any alias
        normalizes equal to the query. Confidence is divided by the
        number of entities sharing the matched surface — ambiguous
        "Maya" returns each candidate at 1/N rather than picking one
        arbitrarily."""
        if not query or not query.strip():
            return []
        normalized = normalize_entity_name(query)
        if not normalized:
            return []
        with self._connect() as con:
            canonical_hits = con.execute(
                "SELECT id, canonical_name, kind FROM entities "
                "WHERE normalized_name = ?",
                (normalized,),
            ).fetchall()

            alias_hits = con.execute(
                "SELECT e.id AS id, e.canonical_name AS canonical_name, "
                "e.kind AS kind "
                "FROM aliases a JOIN entities e ON a.entity_id = e.id "
                "WHERE a.normalized_alias = ?",
                (normalized,),
            ).fetchall()

        # Merge by entity_id, preserving canonical match precedence.
        matched_via: dict[str, str] = {}
        details: dict[str, sqlite3.Row] = {}
        for r in canonical_hits:
            details[r["id"]] = r
            matched_via[r["id"]] = "canonical"
        for r in alias_hits:
            if r["id"] not in details:
                details[r["id"]] = r
                matched_via[r["id"]] = "alias"

        n = len(details)
        if n == 0:
            return []
        share = 1.0 / n
        out: list[EntityMatch] = []
        for eid, row in details.items():
            out.append(EntityMatch(
                entity_id=eid,
                canonical_name=row["canonical_name"],
                kind=row["kind"],
                confidence=share,
                matched_via=matched_via[eid],
            ))
        out.sort(key=lambda m: m.entity_id)
        return out

    def expand(
        self, query: str, *, limit_sessions: int = 20,
    ) -> QueryExpansion:
        """Bound entry to ``expand_query``: callers can use either
        ``index.expand(...)`` or the module-level ``expand_query(...,
        ix=index)``. Keeps tests' module-level wiring simple while
        the instance method stays available for direct callers."""
        return _expand(self, query, limit_sessions=limit_sessions)


# ── module-level expand_query ─────────────────────────────────────


def _scan_query_for_matches(
    ix: EntityIndex, query: str,
) -> list[EntityMatch]:
    """Find every entity whose normalized canonical OR alias matches
    a token-aligned slice of the query. Strategy:

      1. Whole-query (catches an exact canonical match).
      2. Multi-word capitalized runs the extractor would emit
         (catches "Maya Ananthan" inside a longer query).
      3. Each individual word-token, any case (catches lowercase
         natural-text canonicals + aliases — production Telegram
         traffic is overwhelmingly lowercase, e.g. "how is maez
         doing"). The data layer's ``find_entities`` is the gate:
         it does normalized exact lookup against canonical_name and
         alias, returning [] for any token that isn't a registered
         entity — no false-positive risk from feeding stopwords
         through.

    Explicit non-goal: multi-word LOWERCASE aliases (e.g. an alias
    "the portfolio" registered against an entity) are not caught
    when buried inside a longer query. Strategy 1 catches them only
    when the alias *is* the whole query. The Capital-case extractor
    handles capitalized n-gram aliases. A lowercase n-gram pass would
    add cost for a precision case we don't need yet — defer until a
    real entity exposes the gap.
    """
    seen: dict[str, EntityMatch] = {}
    candidates_to_try: list[str] = [query]
    for cand in extract_deterministic_entities(query):
        candidates_to_try.append(cand.surface)
    for tok in _WORD_TOKEN.findall(query):
        candidates_to_try.append(tok)

    for surface in candidates_to_try:
        for m in ix.find_entities(surface):
            prior = seen.get(m.entity_id)
            if prior is None or m.confidence > prior.confidence:
                seen[m.entity_id] = m
    return list(seen.values())


def _expand(
    ix: EntityIndex, query: str, *, limit_sessions: int,
) -> QueryExpansion:
    if not query or not query.strip():
        return QueryExpansion(
            original_query=query or "",
            matched_entities=[],
            session_ids=[],
            source_ids=[],
            explanation="empty query — no expansion",
            confidence=0.0,
            mentions=[],
        )

    matches = _scan_query_for_matches(ix, query)
    if not matches:
        return QueryExpansion(
            original_query=query,
            matched_entities=[],
            session_ids=[],
            source_ids=[],
            explanation="no matching entities",
            confidence=0.0,
            mentions=[],
        )

    # Pull mentions for every matched entity, ordered most-recent-
    # first across the union, capped at limit_sessions distinct
    # session_ids.
    placeholders = ",".join("?" for _ in matches)
    with ix._connect() as con:
        rows = con.execute(
            f"SELECT * FROM entity_mentions "
            f"WHERE entity_id IN ({placeholders}) "
            "ORDER BY observed_at DESC",
            tuple(m.entity_id for m in matches),
        ).fetchall()

    seen_sessions: list[str] = []
    seen_sources: list[str] = []
    mentions_out: list[dict] = []
    for row in rows:
        if row["session_id"] in seen_sessions:
            # Same session can carry multiple mentions; only the
            # first (most-recent observed_at) counts toward the cap.
            continue
        seen_sessions.append(row["session_id"])
        seen_sources.append(row["source_id"])
        mentions_out.append(dict(row))
        if len(seen_sessions) >= limit_sessions:
            break

    surfaces = ", ".join(sorted({m.canonical_name for m in matches}))
    explanation = (
        f"matched {len(matches)} entit{'y' if len(matches) == 1 else 'ies'}"
        f" ({surfaces}); pulled {len(seen_sessions)} session(s) by "
        "observed_at DESC"
    )
    confidence = max(m.confidence for m in matches)
    return QueryExpansion(
        original_query=query,
        matched_entities=matches,
        session_ids=seen_sessions,
        source_ids=seen_sources,
        explanation=explanation,
        confidence=confidence,
        mentions=mentions_out,
    )


def expand_query(
    query: str, *, ix: EntityIndex, limit_sessions: int = 20,
) -> QueryExpansion:
    """Module-level wrapper. Tests use this shape so the entry-point
    can be patched/swapped without instance plumbing."""
    return _expand(ix, query, limit_sessions=limit_sessions)


__all__ = [
    "EntityCandidate",
    "EntityIndex",
    "EntityMatch",
    "QueryExpansion",
    "expand_query",
    "extract_deterministic_entities",
    "normalize_entity_name",
]
