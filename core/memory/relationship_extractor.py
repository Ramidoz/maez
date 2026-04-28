# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Relationship extractor for the lived-memory layer (ADR 0019, Phase 3).

Derives conservative :class:`EdgeProposal` objects from
:class:`EpisodeCandidate`. Rule-based, not LLM-based. Sparse-but-true:
if the signal isn't explicit, the extractor returns no edge for it.

The extractor only ever emits relations from
:data:`ALLOWED_RELATIONS`. Anything outside that vocabulary
(``is_anxious``, ``feels``, ``is_happy``…) is invention and is
forbidden by construction — there is no path from candidate text to
those relations through this module.

The orchestrator (Phase 4 nightly job) is responsible for:

- Resolving each proposal's labels to node IDs via
  :meth:`RelationshipGraph.upsert_node`.
- Stamping ``source_episode_ids`` once the originating episode has
  been stored.
- Detecting contradictions against the existing graph and calling
  :meth:`RelationshipGraph.supersede` (rather than ``add_edge``).

This module is intentionally state-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episode_builder import EpisodeCandidate

#: The complete v1 relation vocabulary. Ordered as in ADR 0019 /
#: the Phase 3 plan; the set is what the extractor enforces at
#: emit-time.
ALLOWED_RELATIONS: frozenset[str] = frozenset(
    {
        "cares_about",
        "promised",
        "corrected",
        "depends_on",
        "threatens",
        "supports",
        "blocked_by",
        "wants",
        "refuses",
        "role",
        "north_star",
        "open_loop_about",
    }
)


@dataclass
class EdgeProposal:
    """A proposed graph edge, not yet bound to node IDs.

    The orchestrator turns this into a real edge by calling
    :meth:`RelationshipGraph.upsert_node` for each label and then
    :meth:`RelationshipGraph.add_edge` with the resolved IDs and the
    originating episode ID stamped in.
    """

    subject_label: str
    subject_kind: str
    relation: str
    object_label: str
    object_kind: str
    source_memory_ids: list[str]
    confidence: float = 0.7


# ── helpers ──────────────────────────────────────────────────────────


def _strip_correction_prefix(title: str) -> str:
    """Pull the corrected subject out of a title like
    ``"Correction 2026-04-23: do not narrate vision as active"`` →
    ``"do not narrate vision as active"``."""
    # Drop everything up to and including the first colon, if any.
    parts = title.split(":", 1)
    return (parts[1] if len(parts) == 2 else title).strip()


def _strip_instability_prefix(title: str) -> str:
    """Pull the source of instability out of a title like
    ``"Hardware instability: kernel NULL pointer at 13:48"`` → the
    leading category, ``"Hardware instability"``. Conservative: we
    use the category, not the specific incident, so multiple
    incidents accrue evidence on the same edge."""
    parts = title.split(":", 1)
    return (parts[0] if len(parts) == 2 else title).strip()


_REVISIT_RE = re.compile(
    r"\b(?:we\s+need\s+to\s+revisit|need\s+to\s+revisit|revisit)\s+"
    r"(?P<obj>.+?)(?:\s+when\b|\s+after\b|[.!?]|$)",
    re.IGNORECASE,
)


def _extract_open_loop_object(open_loop_text: str) -> str:
    """Pull the noun phrase being deferred. Falls back to the full
    open-loop text when no clean phrase is detectable — preserving
    signal beats interpretive guessing."""
    m = _REVISIT_RE.search(open_loop_text)
    if m:
        return m.group("obj").strip()
    return open_loop_text.strip()


# ── per-signal extractors ────────────────────────────────────────────


def _extract_corrected_edges(c: "EpisodeCandidate") -> list[EdgeProposal]:
    """Corrective core memory → ``Maez --corrected--> <subject>``.

    The target is the *thing* being corrected. We try the title first,
    then fall back to the summary's first non-empty line — many real
    corrective core memories use a title like
    ``"INFRASTRUCTURE GROUND-TRUTH (... correction, overrides earlier
    beliefs):"`` whose split-on-colon target is empty. The actual
    corrected subject is on the next line in the body. 2026-04-26
    real-data run made this visible.
    """
    if c.emotional_tone != "corrective":
        return []
    if c.source_kind != "core_memory":
        return []
    target = _strip_correction_prefix(c.title)
    if not target:
        # Skip header-shaped lines (end in ":") — they're labels, not
        # the corrected subject. Walk the summary until we hit a real
        # content line.
        for line in (c.summary or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.endswith(":"):
                continue
            target = stripped[:160]
            break
    if not target:
        return []
    return [
        EdgeProposal(
            subject_label="Maez",
            subject_kind="being",
            relation="corrected",
            object_label=target,
            object_kind="concept",
            source_memory_ids=list(c.source_memory_ids),
            confidence=0.85,
        )
    ]


def _extract_threatens_edges(c: "EpisodeCandidate") -> list[EdgeProposal]:
    """Hardware-instability episode → ``<source> --threatens-->
    Track A continuity``."""
    if c.emotional_tone != "alarming":
        return []
    subject = _strip_instability_prefix(c.title)
    if not subject:
        return []
    return [
        EdgeProposal(
            subject_label=subject,
            subject_kind="category",
            relation="threatens",
            object_label="Track A continuity",
            object_kind="concept",
            source_memory_ids=list(c.source_memory_ids),
            confidence=0.7,
        )
    ]


def _extract_open_loop_edges(c: "EpisodeCandidate") -> list[EdgeProposal]:
    """Open-loop episode → ``Maez --open_loop_about--> <subject>``."""
    if not c.open_loop:
        return []
    target = _extract_open_loop_object(c.open_loop)
    if not target:
        return []
    return [
        EdgeProposal(
            subject_label="Maez",
            subject_kind="being",
            relation="open_loop_about",
            object_label=target,
            object_kind="concept",
            source_memory_ids=list(c.source_memory_ids),
            confidence=0.7,
        )
    ]


# ── owner-preference patterns (cares_about) ─────────────────────────


# Named cares-about: "<Name> cares about <X>". Subject in regex is a
# trigger; subject_label on the edge always resolves to identity's
# display_name() so the graph carries canonical owner identity.
# Object terminates at sentence-end, em-dash, or " more than " /
# " rather than " (the comparative tail belongs to the unwanted
# half of the preference, not the cared-about half).
_CARES_ABOUT_NAMED_RE = re.compile(
    r"\b(?P<subj>[A-Z][a-z]+)\s+cares\s+about\s+"
    r"(?P<obj>.+?)"
    r"(?:[.!?;\n]|\s+more\s+than\b|\s+rather\s+than\b|\s+—\s+|$)",
)

# "<X> matters more than <Y>" — the cared-about thing is X.
_MATTERS_MORE_THAN_RE = re.compile(
    r"\b(?P<obj>[^.!?;\n]+?)\s+matters\s+more\s+than\b",
    re.IGNORECASE,
)

# "what matters most is <X>" / "what I care about is <X>".
# Implicit subject; defaults to display_name().
_WHAT_MATTERS_MOST_RE = re.compile(
    r"\bwhat\s+matters\s+(?:most\s+)?is\s+(?P<obj>.+?)"
    r"(?:[.!?;\n]|\s+—\s+|$)",
    re.IGNORECASE,
)

# Negation window: words within ~30 chars before a "care" match that
# would invert it. Conservative — short list, low false-positive risk.
_NEGATION_WINDOW = 30
_NEGATION_TOKENS = ("don't", "doesn't", "didn't", "do not", "does not")


def _has_preceding_negation(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - _NEGATION_WINDOW) : match_start].lower()
    return any(tok in window for tok in _NEGATION_TOKENS)


def _owner_label() -> str:
    """Resolve the owner's display name from identity. Falls back to
    'Rohit' so the extractor still emits sensible edges if identity
    is unavailable in a test or partial-init context."""
    try:
        from core.identity import display_name

        name = (display_name() or "").strip()
        return name or "Rohit"
    except Exception:
        return "Rohit"


def _clean_object(text: str, max_len: int = 200) -> str:
    """Trim, strip trailing punctuation, bound length. Never returns
    empty for non-empty input — caller checks falsy separately."""
    obj = (text or "").strip().rstrip(".,;:—-")
    return obj[:max_len]


def _extract_cares_about_edges(
    c: "EpisodeCandidate",
) -> list[EdgeProposal]:
    """Owner-preference statement in a core-memory candidate →
    ``<owner> --cares_about--> <X>``.

    Closes the relationship-probe quality gap from the 2026-04-27
    real-data read: the v1 graph had zero ``cares_about`` edges
    because the existing extractors only produced corrected /
    threatens / open_loop_about. The relationship probe passed
    mechanically (brief contained "Rohit") but didn't actually
    answer the question it asked.

    Three patterns, in priority order. Only fires on
    ``source_kind == "core_memory"`` — raw observations and daily
    summaries are too noisy for v1.
    """
    if c.source_kind != "core_memory":
        return []

    text = (c.summary or "") + "\n" + (c.title or "")
    owner = _owner_label()
    seen_objects: set[str] = set()  # dedup within one candidate
    edges: list[EdgeProposal] = []

    def _emit(obj: str) -> None:
        cleaned = _clean_object(obj)
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen_objects:
            return
        seen_objects.add(key)
        edges.append(
            EdgeProposal(
                subject_label=owner,
                subject_kind="person",
                relation="cares_about",
                object_label=cleaned,
                object_kind="concept",
                source_memory_ids=list(c.source_memory_ids),
                confidence=0.85,
            )
        )

    # Pattern 1: "<Name> cares about <X>" — named-subject trigger.
    for m in _CARES_ABOUT_NAMED_RE.finditer(text):
        if _has_preceding_negation(text, m.start()):
            continue
        _emit(m.group("obj"))

    # Pattern 2: "<X> matters more than <Y>" — implicit owner subject.
    for m in _MATTERS_MORE_THAN_RE.finditer(text):
        _emit(m.group("obj"))

    # Pattern 3: "what matters most is <X>" — implicit owner subject.
    for m in _WHAT_MATTERS_MOST_RE.finditer(text):
        _emit(m.group("obj"))

    return edges


_EXTRACTORS = (
    _extract_corrected_edges,
    _extract_threatens_edges,
    _extract_open_loop_edges,
    _extract_cares_about_edges,
)


# ── public entry point ───────────────────────────────────────────────


def extract_edges(candidate: "EpisodeCandidate") -> list[EdgeProposal]:
    """Return zero or more :class:`EdgeProposal` objects derived from
    ``candidate``.

    The extractor is conservative-by-default: when the signal isn't
    explicit, no edge is produced. Every emitted relation is in
    :data:`ALLOWED_RELATIONS`; anything outside that set is invention
    and structurally cannot be produced by this module.
    """
    edges: list[EdgeProposal] = []
    for extractor in _EXTRACTORS:
        for proposal in extractor(candidate):
            # Guardrail — a defensive check that mirrors the
            # forbidden-relation invariant. If a future extractor
            # tries to emit an unknown relation, fail loudly.
            if proposal.relation not in ALLOWED_RELATIONS:
                raise AssertionError(
                    f"extractor emitted disallowed relation "
                    f"{proposal.relation!r}; only "
                    f"{sorted(ALLOWED_RELATIONS)} are permitted"
                )
            edges.append(proposal)
    return edges
