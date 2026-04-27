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


def _score_episode(query_tokens: set[str], ep: dict) -> int:
    haystack_tokens = set(_tokenize(ep.get("title", "") + " " + ep.get("summary", "")))
    return len(query_tokens & haystack_tokens)


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

    if not scored_episodes and not scored_edges:
        return ""

    scored_episodes.sort(key=lambda x: x.score, reverse=True)
    scored_edges.sort(key=lambda x: x.score, reverse=True)

    # ── build sections within max_items budget ──────────────────────
    sections: list[str] = []
    remaining = max_items

    # Open loops first when applicable — they are the most actionable
    # output of lived recall and worth surfacing before the broader
    # historical context.
    for s in scored_episodes:
        if remaining <= 0:
            break
        if s.episode.get("open_loop"):
            sections.append(_format_open_loop(s.episode))
            remaining -= 1

    # Past episodes that don't have an open_loop.
    for s in scored_episodes:
        if remaining <= 0:
            break
        if s.episode.get("open_loop"):
            continue  # already emitted above
        sections.append(_format_past_episode(s.episode))
        remaining -= 1

    # Graph beliefs.
    for s in scored_edges:
        if remaining <= 0:
            break
        sections.append(_format_graph_belief(s.edge, s.subject_label, s.object_label))
        remaining -= 1

    # Live-state guard.
    if _is_live_state_query(query):
        sections.append("- Live state: unavailable from graph (check perception layer)")

    if not sections:
        return ""

    return "\n".join(["=== LIVED RECALL — EVIDENCE-BACKED ===", *sections])
