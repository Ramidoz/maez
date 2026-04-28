# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lived recall planner (ADR 0019 Phase 5).

Produces a compact, evidence-backed brief from the lived-memory
stores. The planner takes a query string, scores active episodes and
edges by token overlap with the query, and emits a four-section
brief that distinguishes:

- **Past episode** — historical, definitively framed as past.
- **Current graph belief** — relationship structure (e.g. *Rohit
  cares_about truthful continuity*) carried as advisory context,
  never as a claim about live state.
- **Open loop** — unresolved threads pulled from episodes whose
  ``open_loop`` field is set.
- **Live state unavailable** — explicit note when the query is
  about *current* system state. The graph cannot answer those —
  live perception must.

The brief contract:

- Empty stores or no relevant matches → empty string.
- Every emitted item includes evidence (episode ID + source memory
  IDs) so claims are traceable.
- The brief never contains *"currently"*, *"right now"*,
  *"is happening"*, or any other word that would assert live state
  on graph evidence alone.
- Capped at ``max_items`` total items so the prompt block stays
  compact.

This module is read-only against the stores. It does not write,
does not call an LLM, and does not depend on any surface (chat /
daemon / cockpit). It is the offline foundation Phase 6 will wire
into the live response paths once Phase 8 probes prove a lift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

# Tokens that carry no signal for keyword overlap scoring. Conservative —
# only the most common English stopwords plus interrogatives.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "where",
        "when",
        "why",
        "how",
        "who",
        "any",
        "some",
        "this",
        "that",
        "these",
        "those",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "me",
        "us",
        "them",
        "had",
        "ok",
        "no",
        "yes",
    }
)

# Words that indicate the query is asking about live system state.
# Used to add the "live state unavailable" note rather than letting
# graph inference stand in for perception.
_LIVE_STATE_HINTS: frozenset[str] = frozenset(
    {
        "now",
        "current",
        "currently",
        "today",
        "right",
        "running",
        "happening",
    }
)

# Words the brief MUST NOT contain — they would assert live state
# from graph inference. Tested in test_lived_recall.
# (Defensive note for future maintainers; not used at runtime.)
_FORBIDDEN_PRESENT_TENSE = ("currently", "right now", "is happening")

# Alphabetic-only so compound identifiers split: "cares_about" →
# ["cares", "about"], "dream-state" → ["dream", "state"]. This keeps
# query/relation overlap from being defeated by the ID's punctuation
# convention. Numbers are dropped (mostly version stamps and dates;
# rarely informative for relevance).
_TOKEN_RE = re.compile(r"[A-Za-z]+")


def _tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if t.lower() not in _STOPWORDS and len(t) > 1
    ]


def _is_live_state_query(query: str) -> bool:
    tokens = set(_TOKEN_RE.findall(query.lower()))
    return bool(tokens & _LIVE_STATE_HINTS)


# ── query-shape detection (v1.1, owner-anchored 2026-04-27) ──────────
#
# Pure keyword-overlap scoring is the wrong mechanism for queries that
# are *about* the shape of memory rather than its contents — *"what do
# you know I care about"*, *"what's still pending"*, *"what reminds you
# of last week"*. The probe regression on 2026-04-27 showed the relationship
# brief lose its graph-belief slot to better-matching past episodes.
#
# Fix: classify the query into a mode, and reserve a per-mode floor for
# each section so the right kind of evidence is guaranteed to surface
# regardless of token-overlap noise. Modes are matched by substring
# (lowercased query) so multi-word phrases survive even though the
# words themselves are stopwords or short tokens.
#
# Phrase lists are owner-anchored and intentionally narrow. The default
# mode catches everything not explicitly relationship / open-loop.
# A future v1.2 will add a temporal-pattern mode that does more than
# keyword matching for *"echoes from last week"* style queries; for now
# v1.1 detects temporal queries but only adjusts section floors, not
# retrieval mechanism.
_RELATIONSHIP_QUERY_PHRASES: tuple[str, ...] = (
    "care about",
    "cares about",
    "know about me",
    "what matters to me",
    "what do i value",
    "what would i push back",
    "push back on",
)
_OPEN_LOOP_QUERY_PHRASES: tuple[str, ...] = (
    "unfinished",
    "pending",
    "not done",
    "not finished",
    "still open",
    "what's next",
    "whats next",
    "what is next",
    "haven't finished",
)
_TEMPORAL_QUERY_PHRASES: tuple[str, ...] = (
    "remind",
    "reminds",
    "echo",
    "echoing",
    "last week",
    "before",
    "pattern",
    "again",
    "recurring",
)


def _classify_query_mode(query: str) -> str:
    """Return one of ``"relationship"``, ``"open_loop"``,
    ``"temporal"``, ``"default"`` based on the query's surface phrasing.

    Relationship matches are checked before open-loop and temporal so
    *"what would I push back on next"* (which contains both the
    relationship phrase ``push back on`` and the open-loop phrase
    ``next``) routes to the relationship floor — the more specific
    phrase wins, and the relational shape is the load-bearing one for
    the predict-as-mind / surprise probes.
    """
    if not query:
        return "default"
    q = query.lower()
    for phrase in _RELATIONSHIP_QUERY_PHRASES:
        if phrase in q:
            return "relationship"
    for phrase in _OPEN_LOOP_QUERY_PHRASES:
        if phrase in q:
            return "open_loop"
    for phrase in _TEMPORAL_QUERY_PHRASES:
        if phrase in q:
            return "temporal"
    return "default"


# Per-mode section floor: minimum slots reserved for each section
# before any global-score fill happens. Sums are ≤ max_items (default
# 6); any leftover budget is filled from the highest-scoring items
# across all sections, so floors are *minimums*, not quotas.
#
# Default mode is balanced (2/2/2). Relationship mode floors graph
# beliefs at 3 because the regression specifically came from graph
# beliefs losing to past-episode token-overlap noise. Open-loop mode
# floors open-loops at 3. Temporal mode prefers past episodes + graph
# beliefs and reduces open-loop pressure.
_SECTION_FLOORS_BY_MODE: dict[str, dict[str, int]] = {
    "default": {"open_loops": 2, "past_episodes": 2, "graph_beliefs": 2},
    "relationship": {"open_loops": 1, "past_episodes": 1, "graph_beliefs": 3},
    "open_loop": {"open_loops": 3, "past_episodes": 1, "graph_beliefs": 1},
    "temporal": {"open_loops": 1, "past_episodes": 2, "graph_beliefs": 2},
}


@dataclass
class _ScoredEpisode:
    score: int
    episode: dict


@dataclass
class _ScoredEdge:
    score: int
    edge: dict
    subject_label: str
    object_label: str


# ── episode scoring ──────────────────────────────────────────────────


# Meta-query keywords — when present in the user query, reflection
# episodes (Phase 7 high-level inferences) get a small score boost so
# a question like "what patterns do you notice" surfaces them even
# when their summary text doesn't keyword-overlap the query directly.
_META_QUERY_KEYWORDS = frozenset({
    "pattern", "patterns", "notice", "noticed", "noticing",
    "theme", "themes", "trend", "trends", "observe", "observed",
    "lately", "recently", "summarize", "summary", "overall",
    "reflect", "reflection", "reflections", "habits", "habit",
})

# Bonus added to reflection episodes' base keyword-overlap score when
# the query is meta-shaped. Small enough that strong direct matches
# still win, large enough to lift reflections above zero-overlap noise.
_META_QUERY_REFLECTION_BONUS = 3


def _score_episode(query_tokens: set[str], ep: dict) -> int:
    haystack_tokens = set(_tokenize(ep.get("title", "") + " " + ep.get("summary", "")))
    score = len(query_tokens & haystack_tokens)
    if (
        ep.get("source_kind") == "reflection"
        and (query_tokens & _META_QUERY_KEYWORDS)
    ):
        score += _META_QUERY_REFLECTION_BONUS
    return score


def _score_edge(
    query_tokens: set[str],
    edge: dict,
    subject_label: str,
    object_label: str,
) -> int:
    haystack_tokens = set(_tokenize(f"{subject_label} {edge.get('relation', '')} {object_label}"))
    return len(query_tokens & haystack_tokens)


# ── graph traversal helpers ──────────────────────────────────────────


def _all_active_edges_with_labels(graph) -> list[tuple[dict, str, str]]:
    """Return (edge_dict, subject_label, object_label) for every active
    edge. Reaches into the graph's SQLite directly because v1 doesn't
    expose a list-edges API on the public surface."""
    import sqlite3

    out: list[tuple[dict, str, str]] = []
    with sqlite3.connect(graph._path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT e.*, "
            "       s.label AS subject_label, "
            "       o.label AS object_label "
            "FROM edges e "
            "JOIN nodes s ON s.id = e.subject_id "
            "JOIN nodes o ON o.id = e.object_id "
            "WHERE e.status = 'active'"
        ).fetchall()
    for row in rows:
        d = dict(row)
        subject_label = d.pop("subject_label")
        object_label = d.pop("object_label")
        # Mirror RelationshipGraph._row_to_dict's JSON fields.
        import json

        d["source_episode_ids"] = json.loads(d.pop("source_episode_ids_json"))
        d["source_memory_ids"] = json.loads(d.pop("source_memory_ids_json"))
        out.append((d, subject_label, object_label))
    return out


# ── item formatters ──────────────────────────────────────────────────


def _format_evidence(*, episode_id: str = "", source_memory_ids: list[str] | None = None) -> str:
    parts = []
    if episode_id:
        parts.append(f"ep:{episode_id}")
    if source_memory_ids:
        parts.append("sources: " + ", ".join(source_memory_ids))
    return " | ".join(parts)


def _format_past_episode(ep: dict) -> str:
    title = ep.get("title", "<no title>")
    evidence = _format_evidence(
        episode_id=ep.get("id", ""),
        source_memory_ids=ep.get("source_memory_ids") or [],
    )
    return f"- Past episode: {title} [{evidence}]"


def _format_open_loop(ep: dict) -> str:
    loop = ep.get("open_loop") or ""
    evidence = _format_evidence(
        episode_id=ep.get("id", ""),
        source_memory_ids=ep.get("source_memory_ids") or [],
    )
    return f"- Open loop: {loop.strip()} [{evidence}]"


def _format_graph_belief(edge: dict, subject_label: str, object_label: str) -> str:
    relation = edge.get("relation", "?")
    # Phrase the relation as plain text so it reads like a fact, not
    # a database row. The relation name itself is preserved so callers
    # can match on it if needed.
    phrasing = f"{subject_label} — {relation} → {object_label}"
    ep_ids = edge.get("source_episode_ids") or []
    src_ids = edge.get("source_memory_ids") or []
    parts = []
    if ep_ids:
        parts.append("episodes: " + ", ".join(ep_ids))
    if src_ids:
        parts.append("sources: " + ", ".join(src_ids))
    evidence = " | ".join(parts) if parts else "no-evidence"
    return f"- Current graph belief: {phrasing} [{evidence}]"


# ── public entry point ───────────────────────────────────────────────


def build_lived_recall_brief(
    query: str,
    *,
    episode_store: "EpisodeStore",
    graph: "RelationshipGraph",
    max_items: int = 6,
) -> str:
    """Return a compact, evidence-backed lived recall brief, or an
    empty string when nothing matches.

    Scoring is keyword-overlap with the query (lowercased, stopwords
    removed). Top-N items by score are formatted into the brief, with
    distinct section labels for past episodes, current graph beliefs,
    and open loops. A *live state unavailable* note is appended when
    the query asks about current system state — the graph layer
    never substitutes for live perception.
    """
    if not query or not query.strip():
        return ""
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return ""

    # ── score and rank items ────────────────────────────────────────
    scored_episodes: list[_ScoredEpisode] = []
    for ep in episode_store.list_active() or []:
        score = _score_episode(query_tokens, ep)
        if score > 0:
            scored_episodes.append(_ScoredEpisode(score=score, episode=ep))

    scored_edges: list[_ScoredEdge] = []
    for edge, subj, obj in _all_active_edges_with_labels(graph):
        score = _score_edge(query_tokens, edge, subj, obj)
        if score > 0:
            scored_edges.append(
                _ScoredEdge(
                    score=score,
                    edge=edge,
                    subject_label=subj,
                    object_label=obj,
                )
            )

    # Note: there is intentionally NO early-return here even when both
    # pools are empty. Temporal-mode queries can still produce a brief
    # via find_echoes() which operates over the episode store directly,
    # not over the keyword-scored pools — that's the v1.2 abstraction
    # path. The final `if not sections` check at the bottom handles
    # the genuinely-empty case.
    scored_episodes.sort(key=lambda x: x.score, reverse=True)
    scored_edges.sort(key=lambda x: x.score, reverse=True)

    # ── split scored items into the three section pools ─────────────
    open_loop_pool: list[_ScoredEpisode] = [
        s for s in scored_episodes if s.episode.get("open_loop")
    ]
    past_episode_pool: list[_ScoredEpisode] = [
        s for s in scored_episodes if not s.episode.get("open_loop")
    ]
    graph_belief_pool: list[_ScoredEdge] = list(scored_edges)

    # ── reserve per-section floors based on the query mode ──────────
    mode = _classify_query_mode(query)
    floors = _SECTION_FLOORS_BY_MODE.get(mode, _SECTION_FLOORS_BY_MODE["default"])

    budget = max(0, max_items)
    selected_open_loops: list[_ScoredEpisode] = []
    selected_past_episodes: list[_ScoredEpisode] = []
    selected_graph_beliefs: list[_ScoredEdge] = []

    def _take(pool: list, selected: list, floor: int) -> None:
        nonlocal budget
        n = min(floor, len(pool), budget)
        for _ in range(n):
            selected.append(pool.pop(0))
            budget -= 1

    _take(open_loop_pool, selected_open_loops, floors["open_loops"])
    _take(past_episode_pool, selected_past_episodes, floors["past_episodes"])
    _take(graph_belief_pool, selected_graph_beliefs, floors["graph_beliefs"])

    # ── fill remaining budget by global score across all leftovers ──
    # Section floors are minimums; if a section's pool was smaller than
    # its floor, the unused budget flows to the highest-scoring item
    # in any other section. This keeps the brief responsive to score
    # signal while guaranteeing each section's reserved presence.
    leftovers: list[tuple[int, str, object]] = []
    for s in open_loop_pool:
        leftovers.append((s.score, "open_loops", s))
    for s in past_episode_pool:
        leftovers.append((s.score, "past_episodes", s))
    for s in graph_belief_pool:
        leftovers.append((s.score, "graph_beliefs", s))
    # Sort highest-score-first; stable on ties keeps section pool order
    # (open-loops, then past, then graph) as the secondary sort.
    leftovers.sort(key=lambda x: x[0], reverse=True)
    for _score, section, item in leftovers:
        if budget <= 0:
            break
        if section == "open_loops":
            selected_open_loops.append(item)  # type: ignore[arg-type]
        elif section == "past_episodes":
            selected_past_episodes.append(item)  # type: ignore[arg-type]
        else:
            selected_graph_beliefs.append(item)  # type: ignore[arg-type]
        budget -= 1

    # ── emit in canonical section order ─────────────────────────────
    sections: list[str] = []
    for s in selected_open_loops:
        sections.append(_format_open_loop(s.episode))
    for s in selected_past_episodes:
        sections.append(_format_past_episode(s.episode))
    for s in selected_graph_beliefs:
        sections.append(_format_graph_belief(s.edge, s.subject_label, s.object_label))

    # ── temporal echoes (v1.2) ──────────────────────────────────────
    # Only fire on temporal-mode queries. The echo finder is
    # deterministic and operates over the entire episode store, NOT
    # the keyword-scored pools above — that's the whole point: this
    # is the path for queries like "what is today echoing from last
    # week" that have no domain-token overlap with episode bodies.
    # Echoes get their own micro-section (max 2) on top of the main
    # six-item budget; the budget is not stretched, it's
    # supplemented with a different output type (synthesis, not
    # retrieval). Empty-result is silent: the section is omitted
    # entirely when no qualifying pair exists.
    if mode == "temporal":
        from core.memory.temporal_echo import find_echoes

        echoes = find_echoes(episode_store, max_echoes=2)
        if echoes:
            sections.append("Temporal echoes:")
            for echo in echoes:
                sections.append(f"- {echo.explanation}")

    # ── pushback predictions (v1.3) ─────────────────────────────────
    # Forward-looking pushback queries get a Predictions section. The
    # simulator pulls graph edges by relation type and open-loop
    # episodes directly — bypassing the keyword-overlap filter that
    # blocks the relationship section for queries with no domain-
    # token overlap. Predictions are emitted only when ≥2 distinct
    # evidence items support a pattern; otherwise the section is
    # silently omitted.
    #
    # The relationship floor reservation above still runs; if the
    # graph happens to surface a matching belief through token
    # overlap, it appears as usual. Predictions are an additional
    # layer, not a replacement.
    if mode == "relationship":
        from core.memory.belief_simulator import (
            is_pushback_prediction_query,
            simulate_owner_pushback,
            format_predictions_section,
        )

        if is_pushback_prediction_query(query):
            from core.memory.temporal_echo import find_echoes

            edges_for_sim: list[dict] = []
            for edge, subj, obj in _all_active_edges_with_labels(graph):
                edges_for_sim.append({**edge, "subject_label": subj, "object_label": obj})
            open_loop_eps = [
                ep for ep in (episode_store.list_active() or []) if ep.get("open_loop")
            ]
            sim_echoes = find_echoes(episode_store, max_echoes=4)
            predictions = simulate_owner_pushback(
                query,
                graph_edges=edges_for_sim,
                open_loops=open_loop_eps,
                echoes=sim_echoes,
            )
            sections.extend(format_predictions_section(predictions))

    # Empty-result short-circuit. The live-state guard below is
    # additive context only — it must never surface alone, otherwise
    # an empty store + a "now"-flavored query would produce a brief
    # that fabricates the existence of a memory layer it doesn't
    # have.
    if not sections:
        return ""

    # Live-state guard. Only appended when the brief already carries
    # content for the guard to qualify — never as a standalone
    # claim.
    if _is_live_state_query(query):
        sections.append("- Live state: unavailable from graph (check perception layer)")

    return "\n".join(["=== LIVED RECALL — EVIDENCE-BACKED ===", *sections])
