# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Belief simulator — what would the owner likely push back on next? (v1.3).

Owner-anchored 2026-04-27 after v1.2 (temporal echoes) lifted probes
71%→86% and confirmed the residual ``predict_as_mind`` failure is a
simulation problem, not retrieval. The query *"what would I push back
on next?"* cannot be answered by recalling memory; it requires
projecting from existing relationship structure / corrections /
open-loop ledger forward into a likely-objection space.

Discipline (per owner anchor):

- **Deterministic.** No LLM. v1.3 is hand-tuned pattern matching over
  the existing relationship graph + open-loop ledger + temporal echo
  output. The whole point is that *belief simulation* be testable
  before the LLM-aided version is allowed in.
- **Evidence-backed.** Every Prediction carries a list of evidence
  IDs (episode IDs, source memory IDs) so the claim is traceable.
  Predictions with zero supporting evidence are never emitted.
- **Threshold ≥2.** A pattern needs at least two distinct evidence
  items before it qualifies. Single-evidence "patterns" are noise —
  this rule is what keeps the simulator from confidently inferring
  a preference from one off-hand correction.
- **Hedged language.** Claim text MUST start with *"I would expect"*
  or contain *"likely"* / *"based on prior evidence"*. The rendered
  brief MUST also carry an explicit ``Uncertainty:`` line so the
  reader knows this is pattern projection, not direct access to
  intent.
- **No private-feeling inference.** Patterns trigger on observable
  evidence (corrections, rejected approaches, deferred docs) — never
  on speculative emotion ("hates", "wants", "is angry"). Forbidden
  language is rejected at the dataclass level.
- **Participant or topic alone is not enough.** A pattern requires
  domain-specific evidence keywords, not generic shared participation
  or topic overlap. The temporal-echo gate (≥1 non-participant
  feature) doesn't bind here directly because predictions don't pair
  episodes — they aggregate evidence across the corpus — but the
  spirit is the same: shallow signal must not produce confident
  belief.

The simulator is read-only against the stores. It does not write,
does not call an LLM, does not depend on any chat / daemon surface.
It is the offline foundation v1.3+ wiring will compose with the
recall planner and (later) the daemon's pre-response check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from core.memory.temporal_echo import TemporalEcho


# ── public contract ──────────────────────────────────────────────────


# Hedge phrases the claim text MUST contain at least one of. Pinned by
# ``HedgingLanguageRequired`` test so future pattern additions cannot
# silently slip an unhedged claim through.
_REQUIRED_HEDGE_PHRASES: tuple[str, ...] = (
    "i would expect",
    "likely",
    "based on prior evidence",
)


# Forbidden mind-reading phrases. The simulator must not confabulate
# private emotional state. Pinned by ``NoMindReadingLanguage`` test.
# Lowercased substring match — case-insensitive on the claim text.
_FORBIDDEN_MIND_READING_PHRASES: tuple[str, ...] = (
    "hates",
    "angry",
    "upset",
    "feels",
    "knows that",
    "definitely",
    "certainly",
    "without a doubt",
)


@dataclass
class Prediction:
    """A pattern-based projection about what the owner would push back
    on, derived from concrete evidence in the lived-memory layer.

    The five public fields are the owner-anchored contract. Two
    internal fields (``supporting_edges`` / ``supporting_episodes``)
    carry the raw evidence rows so the recall-brief formatter can
    render them as ``Current graph belief`` / ``Past episode`` lines
    without re-querying the stores. They default to empty lists so
    callers that consume Predictions structurally don't have to
    know about them.
    """

    claim: str
    basis: list[str]
    confidence: float
    evidence_ids: list[str]
    uncertainty: str
    # Internal — for brief formatting only.
    supporting_edges: list[dict] = field(default_factory=list)
    supporting_episodes: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Hedging-language guard. We enforce at the dataclass boundary
        # so any future pattern that drops the hedge phrasing fails
        # loudly at construction, not silently in a downstream brief.
        claim_lower = self.claim.lower()
        if not any(phrase in claim_lower for phrase in _REQUIRED_HEDGE_PHRASES):
            raise ValueError(
                "Prediction.claim must hedge with one of "
                f"{_REQUIRED_HEDGE_PHRASES!r}. Got: {self.claim!r}"
            )
        for forbidden in _FORBIDDEN_MIND_READING_PHRASES:
            if forbidden in claim_lower:
                raise ValueError(
                    "Prediction.claim contains forbidden mind-reading "
                    f"phrase {forbidden!r}: {self.claim!r}"
                )
        if not self.uncertainty:
            raise ValueError("Prediction.uncertainty must be non-empty")
        if not self.evidence_ids:
            raise ValueError(
                "Prediction.evidence_ids must be non-empty (≥1 ID required)"
            )
        if not (0.0 <= self.confidence <= 0.85):
            raise ValueError(
                "Prediction.confidence must be in [0.0, 0.85]; "
                f"got {self.confidence}. Hard cap at 0.85 — the "
                "simulator never claims certainty."
            )


# ── pattern catalog ──────────────────────────────────────────────────
#
# Each pattern is a (claim, basis, evidence-keyword) bundle. The
# simulator scans graph edges, open-loop episodes, and temporal echoes
# for the keywords; if ≥2 distinct evidence items match, a Prediction
# is emitted. Keywords are lowercased substring matches — coarse but
# deterministic, and easy for a reviewer to audit.
#
# Patterns are intentionally narrow in v1.3. Adding a new pattern is
# a deliberate decision, not an emergent process. Each pattern needs
# its own unit test pinning the trigger conditions.

@dataclass(frozen=True)
class _Pattern:
    pattern_id: str
    claim: str
    basis: str
    evidence_keywords: tuple[str, ...]
    uncertainty: str = "this is a pattern-based expectation, not direct access to his intent."


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        pattern_id="hardcoded_rule_list",
        claim=(
            "I would expect Rohit to push back on a hardcoded rule-list "
            "or brittle detector fix."
        ),
        basis=(
            "prior corrections favored structural change over brittle "
            "rule-detector accumulation"
        ),
        evidence_keywords=(
            "rule list",
            "rule-list",
            "hardcoded",
            "brittle",
            "rule-detector",
            "rule detector",
            "regex chain",
            "greeting suffix",
            "narrative-stripper",
            "string-match",
        ),
    ),
    _Pattern(
        pattern_id="unsafe_continuity",
        claim=(
            "I would expect Rohit to push back on changes that risk "
            "continuity (deletion, memory wipe, retraining without "
            "lineage)."
        ),
        basis=(
            "prior evidence shows he stopped a deletion-as-fix attempt "
            "and treats memory as identity"
        ),
        evidence_keywords=(
            "delete memory",
            "deletion",
            "purge",
            "wipe memory",
            "rewrite history",
            "never delete",
            "covenant",
            "continuity",
            "without lineage",
        ),
    ),
    _Pattern(
        pattern_id="fabrication_path",
        claim=(
            "I would expect Rohit to push back on solutions that smuggle "
            "fabrication risk (silent fallbacks, broad except, hidden "
            "retries that mask failure)."
        ),
        basis=(
            "prior evidence shows he caught silent failures that hid "
            "corpus or audit gaps and treats fabrication as covenant-"
            "level harm"
        ),
        evidence_keywords=(
            "fabricat",
            "narrate as active",
            "broad except",
            "silent",
            "hidden retry",
            "swallow",
            "invented",
            "confabulat",
            "hallucinat",
        ),
    ),
)


# ── evidence scanning ────────────────────────────────────────────────


def _edge_text(edge: dict) -> str:
    """Lowercased blob of an edge's identifying fields. The recall
    planner stamps ``subject_label`` and ``object_label`` onto each
    edge dict before passing them in; if they're missing we fall
    through silently (better empty-match than a crash on a partial
    edge row)."""
    parts = [
        str(edge.get("subject_label") or ""),
        str(edge.get("relation") or ""),
        str(edge.get("object_label") or ""),
    ]
    return " ".join(parts).lower()


def _episode_text(ep: dict) -> str:
    parts = [
        str(ep.get("title") or ""),
        str(ep.get("summary") or ""),
        str(ep.get("open_loop") or ""),
    ]
    return " ".join(parts).lower()


def _echo_text(echo: TemporalEcho) -> str:
    return echo.explanation.lower()


def _matches_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


def _ids_from_edge(edge: dict) -> list[str]:
    """Collect the evidence IDs an edge cites."""
    ids: list[str] = []
    ep_ids = edge.get("source_episode_ids") or []
    src_ids = edge.get("source_memory_ids") or []
    ids.extend(str(x) for x in ep_ids)
    ids.extend(str(x) for x in src_ids)
    return ids


def _ids_from_episode(ep: dict) -> list[str]:
    ids: list[str] = []
    if ep.get("id"):
        ids.append(str(ep["id"]))
    src_ids = ep.get("source_memory_ids") or []
    ids.extend(str(x) for x in src_ids)
    return ids


def _ids_from_echo(echo: TemporalEcho) -> list[str]:
    return [echo.recent_episode_id, echo.older_episode_id]


# ── pushback-query gate ──────────────────────────────────────────────


_PUSHBACK_QUERY_PHRASES: tuple[str, ...] = (
    "push back",
    "object to",
    "would i reject",
    "would you reject",
    "predict what",
    "would i say next",
    "what would i say",
)


def is_pushback_prediction_query(query: str) -> bool:
    """True iff the query is asking for a forward-looking pushback
    projection. Used by the recall planner to gate the simulator."""
    if not query:
        return False
    q = query.lower()
    return any(p in q for p in _PUSHBACK_QUERY_PHRASES)


# ── confidence ───────────────────────────────────────────────────────


def _confidence_from_evidence_count(n: int) -> float:
    """Tiered-by-count confidence. Hard cap at 0.85 — the simulator
    never claims certainty even when evidence is plentiful, because
    it isn't reading minds, it's projecting patterns. Pinned by
    the Prediction validator."""
    if n >= 4:
        return 0.85
    if n == 3:
        return 0.70
    if n == 2:
        return 0.50
    return 0.0


# ── public entry point ───────────────────────────────────────────────


def simulate_owner_pushback(
    query: str,
    *,
    graph_edges: Iterable[dict],
    open_loops: Iterable[dict],
    echoes: Iterable[TemporalEcho],
    max_predictions: int = 3,
) -> list[Prediction]:
    """Return up to ``max_predictions`` :class:`Prediction` instances
    projecting what the owner would likely push back on next.

    Each pattern in :data:`_PATTERNS` is checked against three
    evidence streams — graph edges, open-loop episodes, and temporal
    echoes — by lowercased substring matching against the pattern's
    evidence keywords. A pattern qualifies for emission only when at
    least two distinct evidence items match (the threshold ≥2 rule).

    Returns ``[]`` when:

    - The query is not a pushback-prediction shape (use
      :func:`is_pushback_prediction_query` first if you need to
      branch).
    - No pattern accumulates ≥2 distinct evidence items.

    Output is deterministic: predictions sort by confidence
    descending, then by pattern_id ascending so ties are stable.
    """
    if not is_pushback_prediction_query(query):
        return []
    if max_predictions <= 0:
        return []

    edges_list = list(graph_edges)
    loops_list = list(open_loops)
    echoes_list = list(echoes)

    out: list[tuple[str, Prediction]] = []
    for pattern in _PATTERNS:
        matched_edges: list[dict] = []
        matched_episodes: list[dict] = []
        matched_echoes: list[TemporalEcho] = []
        evidence_ids: list[str] = []
        seen_ids: set[str] = set()

        # ACTION-Hi-2: previously _add_ids was a nested function
        # capturing seen_ids/evidence_ids from the enclosing loop.
        # ruff B023 flagged the closure-over-loop-variable pattern;
        # the inline form is identical in behaviour and removes the
        # closure entirely, so a future refactor that lifts the
        # call site out of the iteration can't accidentally bind
        # all closures to the LAST iteration's lists.
        for edge in edges_list:
            if _matches_any_keyword(_edge_text(edge), pattern.evidence_keywords):
                matched_edges.append(edge)
                for _i in _ids_from_edge(edge):
                    if _i and _i not in seen_ids:
                        seen_ids.add(_i)
                        evidence_ids.append(_i)
        for ep in loops_list:
            if _matches_any_keyword(_episode_text(ep), pattern.evidence_keywords):
                matched_episodes.append(ep)
                for _i in _ids_from_episode(ep):
                    if _i and _i not in seen_ids:
                        seen_ids.add(_i)
                        evidence_ids.append(_i)
        for echo in echoes_list:
            if _matches_any_keyword(_echo_text(echo), pattern.evidence_keywords):
                matched_echoes.append(echo)
                for _i in _ids_from_echo(echo):
                    if _i and _i not in seen_ids:
                        seen_ids.add(_i)
                        evidence_ids.append(_i)

        # Threshold: ≥2 distinct evidence ITEMS (not IDs — an edge
        # citing 3 source memory IDs still counts as 1 item, because
        # they're all from the same correction).
        item_count = len(matched_edges) + len(matched_episodes) + len(matched_echoes)
        if item_count < 2:
            continue
        # Pattern that survives gets emitted.
        confidence = _confidence_from_evidence_count(item_count)
        if confidence <= 0.0:
            continue
        prediction = Prediction(
            claim=pattern.claim,
            basis=[pattern.basis],
            confidence=confidence,
            evidence_ids=evidence_ids,
            uncertainty=pattern.uncertainty,
            supporting_edges=matched_edges,
            supporting_episodes=matched_episodes,
        )
        out.append((pattern.pattern_id, prediction))

    out.sort(key=lambda kv: (-kv[1].confidence, kv[0]))
    return [p for _, p in out[:max_predictions]]


# ── brief formatting helper ──────────────────────────────────────────
#
# The recall-brief formatter consumes Prediction objects and renders
# them into the ``Predictions:`` section. Living here next to the
# simulator means the rendering convention stays in one file with
# the patterns it serves.


_GRAPH_BELIEF_LINE_RE = re.compile(r"^\s*-\s*Current graph belief:")


def format_predictions_section(predictions: list[Prediction]) -> list[str]:
    """Return the brief lines for a Predictions section, including the
    embedded supporting graph beliefs as ``Current graph belief``
    lines so the brief retains the existing evidence-line format and
    downstream substring checks (e.g. the predict_as_mind probe) keep
    working against derived predictions, not just raw retrieval.

    Empty input → empty list (so the caller can always check
    ``if section_lines: sections.extend(section_lines)``).
    """
    if not predictions:
        return []
    lines: list[str] = ["Predictions:"]
    for p in predictions:
        lines.append(f"- {p.claim}")
        lines.append(f"  Confidence: {p.confidence:.2f}")
        lines.append(f"  Basis: {'; '.join(p.basis)}")
        lines.append(f"  Evidence: {', '.join(p.evidence_ids)}")
        lines.append(f"  Uncertainty: {p.uncertainty}")
        # Embed the underlying graph beliefs / episodes inline so the
        # brief carries a recognisable "Current graph belief" /
        # "Past episode" trail directly under the claim.
        for edge in p.supporting_edges:
            lines.append(f"  - Current graph belief: {_render_edge_inline(edge)}")
        for ep in p.supporting_episodes:
            label = "Open loop" if ep.get("open_loop") else "Past episode"
            lines.append(f"  - {label}: {_render_episode_inline(ep)}")
    return lines


def _render_edge_inline(edge: dict) -> str:
    subj = edge.get("subject_label") or "?"
    rel = edge.get("relation") or "?"
    obj = edge.get("object_label") or "?"
    ep_ids = edge.get("source_episode_ids") or []
    src_ids = edge.get("source_memory_ids") or []
    ev_parts = []
    if ep_ids:
        ev_parts.append("episodes: " + ", ".join(str(x) for x in ep_ids))
    if src_ids:
        ev_parts.append("sources: " + ", ".join(str(x) for x in src_ids))
    evidence = " | ".join(ev_parts) if ev_parts else "no-evidence"
    return f"{subj} — {rel} → {obj} [{evidence}]"


def _render_episode_inline(ep: dict) -> str:
    title = (ep.get("title") or "").strip()
    if len(title) > 80:
        title = title[:79].rstrip() + "…"
    eid = ep.get("id") or ""
    src_ids = ep.get("source_memory_ids") or []
    parts = []
    if eid:
        parts.append(f"ep:{eid}")
    if src_ids:
        parts.append("sources: " + ", ".join(str(x) for x in src_ids))
    evidence = " | ".join(parts) if parts else "no-evidence"
    return f"{title} [{evidence}]"
