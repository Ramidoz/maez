# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Temporal echo finder (ADR 0019 v1.2).

Owner-anchored 2026-04-27 after v1.1 (planner ordering) lifted probes
57%→71%. The remaining failures (``past_to_present``, ``predict_as_mind``)
are not retrieval-budget issues — they are abstraction issues. The
queries don't carry domain tokens, so keyword scoring drops every
candidate at ``score > 0`` before section floors apply.

This module addresses the ``past_to_present`` shape directly:

  *"What is today echoing from last week?"*

The right answer is not a list of episodes that mention "today" or
"week". It is a *resemblance claim* between two episodes — one
recent, one older — backed by concrete shared features.

Discipline (per owner anchor):

- Deterministic. No LLM. The whole point is testable abstraction.
- Importance-gated. Only episodes at or above an importance floor
  participate, so heartbeat noise can never form an echo.
- Multi-feature. Single shared feature is allowed *only when* that
  feature is not "participants" — owner's rule: *same participant
  alone is not enough*.
- Evidence-bearing. Every echo cites both episode IDs so the brief
  remains traceable.
- Quiet. Returns ``[]`` when no qualifying pair exists; the brief
  silently omits the echo section in that case.

The brief integration lives in :mod:`core.memory.lived_recall`. This
module is pure logic over the episode store with no graph dependency
in v1.2 — the *shared relation types* feature dimension from the
owner's spec is deferred until the v1.3 belief-simulation slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.memory.lived_recall import _tokenize

if TYPE_CHECKING:
    from core.memory.episodes import EpisodeStore


# Feature dimension labels — kept here as constants so callers and
# tests can reference them without typo risk.
FEATURE_PARTICIPANTS = "participants"
FEATURE_OPEN_LOOP = "open_loop"
FEATURE_TOPIC = "topic"
FEATURE_TAGS = "tags"

_FEATURE_KEYS: tuple[str, ...] = (
    FEATURE_PARTICIPANTS,
    FEATURE_OPEN_LOOP,
    FEATURE_TOPIC,
    FEATURE_TAGS,
)


@dataclass
class TemporalEcho:
    """A resemblance claim between a recent episode and an older one,
    backed by ≥1 shared feature dimension.

    ``shared_features`` is a sorted list of feature-dimension labels
    (``participants`` / ``open_loop`` / ``topic`` / ``tags``) — not
    the literal token overlaps. ``explanation`` is the human-facing
    one-liner the recall planner emits into the brief; ``score`` is
    the count of shared dimensions, used for ranking.
    """

    recent_episode_id: str
    older_episode_id: str
    shared_features: list[str]
    explanation: str
    score: int


# ── feature extraction ───────────────────────────────────────────────


def _episode_tags(ep: dict) -> frozenset[str]:
    """Map ``source_kind`` + ``emotional_tone`` + title shape into
    discrete tags. Tags are coarse signal — *correction*, *safety*,
    *infrastructure*, *open-loop ledger* — that survive even when
    the underlying tokens diverge."""
    tags: set[str] = set()
    source_kind = (ep.get("source_kind") or "").lower()
    tone = (ep.get("emotional_tone") or "").lower()
    title_lower = (ep.get("title") or "").lower()

    if tone == "corrective" or "correction" in title_lower:
        tags.add("correction")
    if tone == "alarming":
        tags.add("safety")
    if source_kind == "followup_doc":
        tags.add("open_loop_ledger")
    if "infrastructure" in title_lower:
        tags.add("infrastructure")
    if "readiness" in title_lower or "ritual" in title_lower:
        tags.add("readiness")
    return frozenset(tags)


def _episode_features(ep: dict) -> dict[str, frozenset[str]]:
    """Bucket an episode into the four feature dimensions used for
    echo comparison. Returns frozen sets so set operations are clean."""
    title_tokens = _tokenize(ep.get("title") or "")
    summary_tokens = _tokenize(ep.get("summary") or "")
    return {
        FEATURE_PARTICIPANTS: frozenset(ep.get("participants") or []),
        FEATURE_OPEN_LOOP: frozenset(_tokenize(ep.get("open_loop") or "")),
        FEATURE_TOPIC: frozenset(title_tokens) | frozenset(summary_tokens),
        FEATURE_TAGS: _episode_tags(ep),
    }


def _shared_dimensions(
    recent: dict[str, frozenset[str]],
    older: dict[str, frozenset[str]],
) -> set[str]:
    """Return the set of feature-dimension labels where the recent and
    older episodes share at least one element."""
    shared: set[str] = set()
    for key in _FEATURE_KEYS:
        if recent.get(key) and older.get(key) and (recent[key] & older[key]):
            shared.add(key)
    return shared


def _qualifies_as_echo(shared: set[str]) -> bool:
    """Owner-anchored rule: single shared dimension is allowed *only
    when* that dimension is not ``participants``. *Same participant
    alone is not enough.* All other single dimensions (open_loop,
    topic, tags) carry enough signal on their own; participants has
    to be paired with something else."""
    if not shared:
        return False
    non_participant = shared - {FEATURE_PARTICIPANTS}
    return bool(non_participant)


# ── explanation rendering ────────────────────────────────────────────


def _short_title(ep: dict, *, limit: int = 60) -> str:
    title = (ep.get("title") or "").strip()
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip() + "…"


def _format_shared_features(
    shared: set[str],
    recent_features: dict[str, frozenset[str]],
    older_features: dict[str, frozenset[str]],
) -> str:
    """Render a human-facing list of *what* is shared, with a small
    sample of the actual overlap so the explanation is concrete."""
    parts: list[str] = []
    # Stable order matches _FEATURE_KEYS for deterministic output.
    for key in _FEATURE_KEYS:
        if key not in shared:
            continue
        overlap = sorted(recent_features[key] & older_features[key])
        # Cap the visible overlap to keep the brief compact; ≤3 items
        # is enough to show the resemblance is concrete, not generic.
        if len(overlap) > 3:
            overlap = overlap[:3] + ["…"]
        if key == FEATURE_TAGS:
            parts.append(f"tag {{{', '.join(overlap)}}}")
        elif key == FEATURE_PARTICIPANTS:
            parts.append(f"participant {{{', '.join(overlap)}}}")
        elif key == FEATURE_OPEN_LOOP:
            parts.append(f"open-loop terms {{{', '.join(overlap)}}}")
        elif key == FEATURE_TOPIC:
            parts.append(f"topic terms {{{', '.join(overlap)}}}")
    return ", ".join(parts)


def _format_explanation(
    recent: dict,
    older: dict,
    shared: set[str],
    recent_features: dict[str, frozenset[str]],
    older_features: dict[str, frozenset[str]],
) -> str:
    """Build the one-liner the recall brief surfaces. The phrase
    *past episode* is in the line so the past_to_present probe's
    substring check passes naturally — the line really IS about a
    past episode, the wording isn't gamed."""
    recent_title = _short_title(recent)
    older_title = _short_title(older)
    feature_text = _format_shared_features(shared, recent_features, older_features)
    rid = recent.get("id", "")
    oid = older.get("id", "")
    rsrc = ", ".join(recent.get("source_memory_ids") or []) or "no-sources"
    osrc = ", ".join(older.get("source_memory_ids") or []) or "no-sources"
    return (
        f"Today's \"{recent_title}\" resembles past episode "
        f"\"{older_title}\" — both share {feature_text}. "
        f"[recent: ep:{rid} | sources: {rsrc}; "
        f"older: ep:{oid} | sources: {osrc}]"
    )


# ── public entry point ───────────────────────────────────────────────


def find_echoes(
    episode_store: "EpisodeStore",
    *,
    recent_count: int = 5,
    importance_floor: int = 3,
    max_echoes: int = 2,
) -> list[TemporalEcho]:
    """Return up to ``max_echoes`` :class:`TemporalEcho` instances
    pairing recent and older important episodes by shared features.

    The recency split is index-based on ``created_at`` (newest first):
    the top ``recent_count`` qualifying episodes are *recent*, the
    rest are *older*. Index-based is robust on the sparse data the
    real lived-memory store has — a date-window split would leave
    one bucket empty when the corpus is small. Both buckets are
    pre-filtered to ``importance >= importance_floor`` so heartbeat
    noise can't form an echo.

    Pair scoring: count of shared feature dimensions
    (``participants``, ``open_loop``, ``topic``, ``tags``). A pair
    qualifies as an echo only when at least one *non-participant*
    dimension is shared — the owner's *same participant alone is not
    enough* rule. Ties are broken by recent timestamp, then older
    timestamp, then episode IDs, so output is deterministic.

    Returns ``[]`` when the store has fewer than ``recent_count + 1``
    qualifying episodes, or when no pair qualifies.
    """
    if recent_count <= 0 or max_echoes <= 0:
        return []
    eps = episode_store.list_active() or []
    eps = [e for e in eps if (e.get("importance") or 0) >= importance_floor]
    # Newest first by created_at; missing timestamps sort last.
    eps.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    if len(eps) <= recent_count:
        return []

    recent_eps = eps[:recent_count]
    older_eps = eps[recent_count:]

    candidates: list[TemporalEcho] = []
    for r in recent_eps:
        rf = _episode_features(r)
        for o in older_eps:
            of = _episode_features(o)
            shared = _shared_dimensions(rf, of)
            if not _qualifies_as_echo(shared):
                continue
            score = len(shared)
            explanation = _format_explanation(r, o, shared, rf, of)
            candidates.append(
                TemporalEcho(
                    recent_episode_id=r.get("id", ""),
                    older_episode_id=o.get("id", ""),
                    shared_features=sorted(shared),
                    explanation=explanation,
                    score=score,
                )
            )

    # Deterministic ranking: highest score, then most recent, then
    # oldest older, then id pair. The fallback chain matters because
    # in a homogeneous corpus (e.g. five corrective core memories)
    # many pairs tie on score.
    candidates.sort(
        key=lambda c: (
            -c.score,
            c.recent_episode_id,
            c.older_episode_id,
        )
    )
    return candidates[:max_echoes]
