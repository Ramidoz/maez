# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Working self — goal-driven retrieval module.

Adapted from established work in agent memory and cognitive psychology:

- **Conway & Pleydell-Pearce (2000), "The construction of autobiographical
  memories in the self-memory system"** — *Psychological Review*. The Self-
  Memory System framework. Working self = current goal hierarchy that acts
  as control processes modulating retrieval; goals "modulate the
  construction of memories." Memory and self are reciprocal.

- **Park et al. (2023), "Generative Agents: Interactive Simulacra of Human
  Behavior"** (arxiv 2304.03442). Retrieval scoring formula:
  ``score = α_recency·recency + α_importance·importance + α_relevance·relevance``
  with recency as exponential decay (0.995 per game-hour),
  importance LLM-rated 1–10, relevance via cosine similarity, all
  normalized to [0, 1].

- **Hu et al. (Dec 2025), "Memory in the Age of AI Agents: A Survey"**
  (arxiv 2512.13564). Memory taxonomy: factual, experiential, working,
  parametric. Working memory + planning + retrieval as integrated
  modules. Long context ≠ persistent memory.

- **ICLR 2026 MemAgents Workshop** — active research frontier on
  goal-conditioned retrieval for autonomous agents.

Adapted for Maez's bonded-companion architecture:

- Goals come from 5 sources internal to Maez:
    1. ``cares_about`` graph edges (durable owner-preference structure)
    2. ``wants.py`` recent entries (Maez's first-person direction log)
    3. Recent owner messages (immediate context)
    4. Open loops in episodes (``open_loop`` field set)
    5. Recent reflections (``source_kind="reflection"`` episodes — Phase 7)

- Park's importance score (1–10 LLM-rated) is replaced by Maez's tier
  (core / daily / raw / reflection / open_loop). The tier IS the
  importance signal in a hierarchical-memory architecture.

- Conway's working-self goal-alignment term (``α_goal``) is added to
  Park's formula as a fourth weighted component.

Scope of this module (Slice 1 of Working Self arc):
- Goal state production (``assemble_goals``, ``GoalHierarchy``)
- Composite scoring math (``score_memory``)
- Pure functions; no daemon integration yet (that's Slice 2)
- Keyword-overlap relevance for v1 (embedding-based is a v2 hook)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Sequence


# ── goal source labels ─────────────────────────────────────────────────

GOAL_SOURCE_CARES_ABOUT = "cares_about"
GOAL_SOURCE_WANTS = "wants"
GOAL_SOURCE_OWNER_MSG = "owner_msg"
GOAL_SOURCE_OPEN_LOOP = "open_loop"
GOAL_SOURCE_REFLECTION = "reflection"

# Heuristic weights per source. Tunable; the v1 ordering reflects
# durable-vs-transient priority — owner-stated structural preferences
# (cares_about) outweigh transient context (most recent owner_msg).
# Values do NOT need to sum to 1; they're priors that get re-normalised
# during hierarchy assembly.
_DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    GOAL_SOURCE_CARES_ABOUT: 0.95,
    GOAL_SOURCE_OWNER_MSG: 0.85,
    GOAL_SOURCE_OPEN_LOOP: 0.75,
    GOAL_SOURCE_WANTS: 0.65,
    GOAL_SOURCE_REFLECTION: 0.55,
}

# Tier weight replaces Park's importance score. Maps each memory tier
# to a scalar in [0, 1]. Hierarchical-memory architectures encode
# importance through tier rather than per-memory rating.
_TIER_WEIGHTS: dict[str, float] = {
    "core": 1.0,
    "reflection": 0.85,
    "open_loop": 0.75,
    "daily": 0.55,
    "raw": 0.30,
    "": 0.30,  # default for unknown
}


# ── dataclasses ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Goal:
    """A single goal in the working-self hierarchy.

    Carries enough provenance to trace a retrieval decision back to a
    specific source — same evidence covenant Maez itself lives under.
    """

    text: str
    source: str
    weight: float
    evidence_ids: tuple[str, ...] = ()
    last_relevant_at: str = ""

    def __post_init__(self) -> None:
        # Coerce evidence_ids to tuple if a list slipped in.
        if not isinstance(self.evidence_ids, tuple):
            object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))


@dataclass(frozen=True)
class GoalHierarchy:
    """The current working-self goal hierarchy.

    Conway 2000: this IS the working self for retrieval purposes — the
    structured set of current goals that modulates which memories
    surface. The hierarchy is read-only after assembly; rebuilds on
    each retrieval call.
    """

    goals: tuple[Goal, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.goals, tuple):
            object.__setattr__(self, "goals", tuple(self.goals))

    @property
    def is_empty(self) -> bool:
        return len(self.goals) == 0

    def by_source(self, source: str) -> tuple[Goal, ...]:
        return tuple(g for g in self.goals if g.source == source)

    def text_corpus(self) -> str:
        """Concatenate all goal texts for keyword-relevance scoring."""
        return " | ".join(g.text for g in self.goals)


# ── goal extraction from each source ───────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_iso(value: Any) -> str:
    """Best-effort coerce to ISO string. Empty on failure."""
    if not value:
        return ""
    try:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat(timespec="seconds")
        return str(value)
    except Exception:
        return ""


def _goals_from_cares_about(graph: Any, *, max_per_source: int) -> list[Goal]:
    """Pull active ``cares_about`` edges from the relationship graph.

    Conway 2000: durable preferences ARE the long-arc goal structure of
    the working self. ``Rohit cares_about truthful continuity`` is a
    structural goal, not a transient one.
    """
    if graph is None:
        return []
    out: list[Goal] = []
    try:
        # Match the pattern used in lived_recall._all_active_edges_with_labels:
        # the public surface doesn't expose list-edges, so dip into SQLite
        # directly. Read-only.
        import sqlite3

        with sqlite3.connect(graph._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT e.id, e.relation, "
                "       s.label AS subject_label, "
                "       o.label AS object_label, "
                "       e.created_at, "
                "       e.source_episode_ids_json, "
                "       e.source_memory_ids_json "
                "FROM edges e "
                "JOIN nodes s ON s.id = e.subject_id "
                "JOIN nodes o ON o.id = e.object_id "
                "WHERE e.status = 'active' AND e.relation = 'cares_about' "
                "ORDER BY e.created_at DESC"
            ).fetchall()
    except Exception:
        return []
    import json as _json
    for row in rows[:max_per_source]:
        d = dict(row)
        # Goal text = object_label only (what's cared about), NOT the
        # synthesized "<subject> cares about <object>" sentence.
        # Reason (2026-04-29 natural-language probe finding): the
        # "<subject> cares about" prefix injects the subject name and
        # the relation verb "cares" into every cares_about goal,
        # which then mildly matches every OWNER PREFERENCE episode
        # (since those describe what the subject cares about). Result
        # was a universal-default surfacing pattern across casual
        # natural texts. The relation is already encoded in
        # ``source=GOAL_SOURCE_CARES_ABOUT``; including it in the
        # text is redundant noise. Keeping just the object_label
        # focuses alignment on what the goal is *about*.
        text = (d["object_label"] or "").strip()
        if not text:
            continue
        try:
            ep_ids = _json.loads(d.get("source_episode_ids_json") or "[]")
        except Exception:
            ep_ids = []
        try:
            mem_ids = _json.loads(d.get("source_memory_ids_json") or "[]")
        except Exception:
            mem_ids = []
        evidence = tuple(str(x) for x in (ep_ids + mem_ids) if x)
        out.append(Goal(
            text=text,
            source=GOAL_SOURCE_CARES_ABOUT,
            weight=_DEFAULT_SOURCE_WEIGHTS[GOAL_SOURCE_CARES_ABOUT],
            evidence_ids=evidence,
            last_relevant_at=_safe_iso(d.get("created_at")),
        ))
    return out


def _goals_from_wants(wants: Any, *, max_per_source: int) -> list[Goal]:
    """Pull recent entries from the wants log (``core/wants.py``).

    Maez's first-person direction log. A want is a goal claim Maez has
    surfaced about itself; Conway 2000 includes self-defining goals as
    central to the working self.
    """
    if wants is None:
        return []
    try:
        recent = wants.recent(limit=max_per_source) or []
    except Exception:
        return []
    out: list[Goal] = []
    for entry in recent:
        text = (entry.get("text") or entry.get("description") or "").strip()
        if not text:
            continue
        wid = entry.get("want_id") or entry.get("id") or ""
        ts = entry.get("created_at") or entry.get("ts") or ""
        out.append(Goal(
            text=text[:500],
            source=GOAL_SOURCE_WANTS,
            weight=_DEFAULT_SOURCE_WEIGHTS[GOAL_SOURCE_WANTS],
            evidence_ids=(str(wid),) if wid else (),
            last_relevant_at=_safe_iso(ts),
        ))
    return out


def _goals_from_owner_msg(
    recent_owner_text: "str | Sequence[str] | None",
    *,
    max_per_source: int,
) -> list[Goal]:
    """Goals from immediate context — the most recent owner message(s).

    Conway 2000: the *current* concerns of the self also gate retrieval.
    These are transient goals; they decay quickly relative to
    cares_about edges. Caller passes either a single string (latest
    message) or a list of recent messages.
    """
    if not recent_owner_text:
        return []
    if isinstance(recent_owner_text, str):
        msgs = [recent_owner_text]
    else:
        msgs = list(recent_owner_text)
    out: list[Goal] = []
    for i, msg in enumerate(msgs[:max_per_source]):
        text = (msg or "").strip()
        if not text:
            continue
        out.append(Goal(
            text=text[:500],
            source=GOAL_SOURCE_OWNER_MSG,
            # Most-recent message gets full source weight; older
            # messages decay linearly.
            weight=_DEFAULT_SOURCE_WEIGHTS[GOAL_SOURCE_OWNER_MSG] * (1.0 - 0.15 * i),
            evidence_ids=(),
            last_relevant_at=_now_iso(),
        ))
    return out


def _goals_from_open_loops(episode_store: Any, *, max_per_source: int) -> list[Goal]:
    """Open loops are episodes with the ``open_loop`` field set.

    These are unresolved threads — questions to follow up, deferred
    follow-ups, partial answers. By construction they're load-bearing
    for the working self because they're explicitly unfinished.
    """
    if episode_store is None:
        return []
    try:
        active = episode_store.list_active() or []
    except Exception:
        return []
    out: list[Goal] = []
    for ep in active:
        if not ep.get("open_loop"):
            continue
        text = (ep.get("open_loop") or ep.get("title") or "").strip()
        if not text:
            continue
        out.append(Goal(
            text=text[:500],
            source=GOAL_SOURCE_OPEN_LOOP,
            weight=_DEFAULT_SOURCE_WEIGHTS[GOAL_SOURCE_OPEN_LOOP],
            evidence_ids=(str(ep.get("id") or ""),),
            last_relevant_at=_safe_iso(ep.get("created_at")),
        ))
        if len(out) >= max_per_source:
            break
    return out


def _goals_from_reflections(episode_store: Any, *, max_per_source: int) -> list[Goal]:
    """Recent reflections (Phase 7) become goals.

    Conway 2000: reflections are the integrated experiential layer of
    the self. When the system notices a pattern, that noticing is
    itself a goal-shaping event — "Maez has noticed it consistently
    prioritises truth over speed" becomes a guideline that shapes
    future retrieval.
    """
    if episode_store is None:
        return []
    try:
        active = episode_store.list_active() or []
    except Exception:
        return []
    # list_active is newest-first per episodes.py.
    out: list[Goal] = []
    for ep in active:
        if (ep.get("source_kind") or "") != "reflection":
            continue
        text = (ep.get("summary") or ep.get("title") or "").strip()
        if not text:
            continue
        out.append(Goal(
            text=text[:500],
            source=GOAL_SOURCE_REFLECTION,
            weight=_DEFAULT_SOURCE_WEIGHTS[GOAL_SOURCE_REFLECTION],
            evidence_ids=(str(ep.get("id") or ""),),
            last_relevant_at=_safe_iso(ep.get("created_at")),
        ))
        if len(out) >= max_per_source:
            break
    return out


# ── public assembly + scoring API ──────────────────────────────────────


def assemble_goals(
    *,
    episode_store: Any = None,
    graph: Any = None,
    wants: Any = None,
    recent_owner_text: "str | Sequence[str] | None" = None,
    max_goals: int = 12,
    max_per_source: int = 5,
) -> GoalHierarchy:
    """Build the current working-self goal hierarchy from all sources.

    Each source is read independently; if a source raises or returns
    nothing, the assembly continues with what's available. Final
    hierarchy is sorted by ``weight`` descending and truncated to
    ``max_goals``.

    All arguments are optional. Calling with no arguments returns an
    empty hierarchy — useful as a no-op default in callers that want
    goal-aware scoring as opt-in.

    Conway 2000: the working self is reconstructed each retrieval, not
    persisted. Match that — assembly is cheap; goals are not stored.
    """
    pool: list[Goal] = []
    pool.extend(_goals_from_cares_about(graph, max_per_source=max_per_source))
    pool.extend(_goals_from_owner_msg(recent_owner_text, max_per_source=max_per_source))
    pool.extend(_goals_from_open_loops(episode_store, max_per_source=max_per_source))
    pool.extend(_goals_from_wants(wants, max_per_source=max_per_source))
    pool.extend(_goals_from_reflections(episode_store, max_per_source=max_per_source))
    # Stable sort: highest weight first; ties broken by source priority
    # implicit in the source-weight defaults.
    pool.sort(key=lambda g: g.weight, reverse=True)
    return GoalHierarchy(goals=tuple(pool[:max_goals]))


# ── scoring math (Park 2023 + Conway 2000) ─────────────────────────────


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]+")
_STOPWORDS = frozenset({
    "the", "and", "or", "of", "to", "a", "an", "in", "on", "at", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "i", "you", "we",
    "he", "she", "they", "them", "his", "her", "their", "our", "my",
    "your", "do", "does", "did", "will", "would", "should", "could",
    "have", "has", "had", "but", "if", "then", "than", "so", "not",
    "no", "yes", "from", "by", "via", "about", "into", "out", "up",
    "down", "over", "under", "more", "less", "very", "just", "also",
    "only", "still", "even", "all", "some", "any", "each", "few",
    "many", "most",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens minus stopwords. Same shape as
    ``lived_recall._tokenize`` so retrieval scoring is consistent across
    Maez's modules."""
    if not text:
        return set()
    return {
        t.lower() for t in _WORD_RE.findall(text)
        if t.lower() not in _STOPWORDS and len(t) > 1
    }


def goal_relevance(
    memory_text: str,
    goals: GoalHierarchy,
    *,
    embedder: Optional[Callable[[str, str], float]] = None,
    exclude_evidence_ids: Sequence[str] = (),
    noise_tokens: Sequence[str] = (),
) -> float:
    """Score how aligned a memory is to the current goal hierarchy.

    Returns a value in [0, 1].

    v1 implementation: keyword-overlap + per-goal weight. For each
    goal, compute ``overlap_ratio = |memory_tokens ∩ goal_tokens| /
    max(1, |goal_tokens|)`` and weight by the goal's ``weight``. Sum
    across goals, normalise to [0, 1] by dividing by the sum of goal
    weights.

    ``embedder`` is a v2 hook — if supplied, it's used for cosine
    similarity per goal instead of token overlap. v1 does not call it.

    ``exclude_evidence_ids`` filters goals whose ``evidence_ids``
    intersect with the supplied set. Use case: when scoring an
    episode that is itself the source of an open_loop goal, the
    goal's text mirrors the episode's text — passing the episode's
    own id here prevents a self-referential bonus from inflating the
    episode against unrelated queries (Gap 2 fix from the 2026-04-29
    live spin).

    ``noise_tokens`` are stripped from BOTH the memory text and each
    goal's text before overlap is computed. Use case: the canonical
    owner name and ``"maez"`` itself appear in nearly every memory
    AND every working-self goal, so they carry no alignment signal
    — they're noise. Filtering them prevents name-coincidence from
    faking alignment (post-2026-04-29 live-spin diagnosis: the
    diversity refinement insight that the actual root of OWNER
    PREFERENCE monotony was generic-name token contamination).

    Empty hierarchy → 0.0 (no goal context to align with).
    """
    if goals.is_empty:
        return 0.0
    noise_set = {t.lower() for t in noise_tokens} if noise_tokens else set()
    mem_toks = _tokenize(memory_text) - noise_set
    if not mem_toks:
        return 0.0
    exclude_set = set(exclude_evidence_ids) if exclude_evidence_ids else set()
    if embedder is not None:
        # v2 hook: weighted-mean cosine. v1 callers won't supply this.
        try:
            scores: list[float] = []
            total_w_emb = 0.0
            for g in goals.goals:
                if exclude_set and (set(g.evidence_ids) & exclude_set):
                    continue
                sim = float(embedder(memory_text, g.text))
                scores.append(g.weight * max(0.0, min(1.0, sim)))
                total_w_emb += g.weight
            if total_w_emb == 0:
                return 0.0
            return sum(scores) / total_w_emb
        except Exception:
            # fall through to keyword-overlap on embedder failure
            pass
    weighted = 0.0
    total_weight = 0.0
    for g in goals.goals:
        if exclude_set and (set(g.evidence_ids) & exclude_set):
            continue
        goal_toks = _tokenize(g.text) - noise_set
        if not goal_toks:
            continue
        overlap = mem_toks & goal_toks
        ratio = len(overlap) / len(goal_toks)
        weighted += g.weight * ratio
        total_weight += g.weight
    if total_weight == 0:
        return 0.0
    return min(1.0, weighted / total_weight)


def recency_score(
    last_seen_iso: str,
    *,
    now: Optional[datetime] = None,
    half_life_hours: float = 24.0,
) -> float:
    """Park 2023 recency: exponential decay since last access.

    Park used 0.995 per game-hour, which corresponds to a half-life of
    ~138 hours (5.7 days). For Maez's lived-memory architecture,
    24-hour half-life is more aligned with the daily-consolidation
    cycle. Tunable per call.

    Returns a value in [0, 1]. Unparseable timestamps return 1.0
    (fail-open: assume recent rather than discard).
    """
    if not last_seen_iso:
        return 1.0
    try:
        ts = datetime.fromisoformat(last_seen_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 1.0
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    return math.exp(-math.log(2.0) * delta_hours / max(0.1, half_life_hours))


def tier_score(tier: str) -> float:
    """Maez-specific replacement for Park's importance score (1–10
    LLM-rated). In a hierarchical-memory architecture, tier IS the
    importance signal — core memories are high-importance by
    construction; raw entries are low. No per-memory LLM rating
    needed."""
    return _TIER_WEIGHTS.get((tier or "").lower(), _TIER_WEIGHTS[""])


def relevance_score(
    memory_text: str,
    query_text: str,
    *,
    embedder: Optional[Callable[[str, str], float]] = None,
) -> float:
    """Park 2023 relevance: cosine of embeddings (or keyword-overlap
    fallback for v1). Returns [0, 1]."""
    if not memory_text or not query_text:
        return 0.0
    if embedder is not None:
        try:
            sim = float(embedder(memory_text, query_text))
            return max(0.0, min(1.0, sim))
        except Exception:
            pass
    mem_toks = _tokenize(memory_text)
    query_toks = _tokenize(query_text)
    if not query_toks or not mem_toks:
        return 0.0
    overlap = mem_toks & query_toks
    return len(overlap) / len(query_toks)


@dataclass(frozen=True)
class ScoreWeights:
    """Park 2023 weights extended with Conway 2000 goal-alignment term.

    Defaults set all four α to 1.0 — matching Park's "all 1" baseline.
    Tunable per call so a future caller (e.g. lived_recall) can
    de-emphasise recency for archive-class queries.
    """

    recency: float = 1.0
    tier: float = 1.0
    relevance: float = 1.0
    goal: float = 1.0


def score_memory(
    memory: dict,
    *,
    query_text: str = "",
    goals: GoalHierarchy = GoalHierarchy(),
    weights: ScoreWeights = ScoreWeights(),
    now: Optional[datetime] = None,
    embedder: Optional[Callable[[str, str], float]] = None,
    exclude_evidence_ids: Sequence[str] = (),
    noise_tokens: Sequence[str] = (),
) -> float:
    """Composite Park 2023 + Conway 2000 retrieval score for one memory.

    Memory dict shape (best-effort accessors):
        - ``text``: searchable text (falls back to ``content`` /
          ``summary`` / ``title``)
        - ``tier``: ``core`` / ``daily`` / ``raw`` / ``reflection`` /
          ``open_loop`` (falls back to ``source_kind``)
        - ``last_seen_at`` or ``created_at``: ISO timestamp

    Returns a normalised score in [0, 1]: each of the four components
    is in [0, 1] and the weighted sum is divided by the sum of weights.

    Setting ``weights.goal = 0`` reduces to Park's original three-term
    formula. Setting ``goals = GoalHierarchy()`` (empty) makes the
    goal-alignment term contribute zero regardless of weight.
    """
    text = (
        memory.get("text")
        or memory.get("content")
        or memory.get("summary")
        or memory.get("title")
        or ""
    )
    tier = memory.get("tier") or memory.get("source_kind") or ""
    last_seen = (
        memory.get("last_seen_at")
        or memory.get("last_relevant_at")
        or memory.get("created_at")
        or ""
    )
    rec = recency_score(last_seen, now=now)
    tie = tier_score(tier)
    rel = relevance_score(text, query_text, embedder=embedder) if query_text else 0.0
    goa = goal_relevance(
        text,
        goals,
        embedder=embedder,
        exclude_evidence_ids=exclude_evidence_ids,
        noise_tokens=noise_tokens,
    )
    total_w = (
        weights.recency + weights.tier + weights.relevance + weights.goal
    )
    if total_w == 0:
        return 0.0
    weighted = (
        weights.recency * rec
        + weights.tier * tie
        + weights.relevance * rel
        + weights.goal * goa
    )
    return weighted / total_w


__all__ = [
    "Goal",
    "GoalHierarchy",
    "ScoreWeights",
    "assemble_goals",
    "goal_relevance",
    "recency_score",
    "tier_score",
    "relevance_score",
    "score_memory",
    "GOAL_SOURCE_CARES_ABOUT",
    "GOAL_SOURCE_WANTS",
    "GOAL_SOURCE_OWNER_MSG",
    "GOAL_SOURCE_OPEN_LOOP",
    "GOAL_SOURCE_REFLECTION",
]
