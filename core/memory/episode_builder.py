# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Episode builder for the lived-memory layer (ADR 0019, Phase 2).

Converts high-signal memory entries into ``EpisodeCandidate`` objects.
Conservative-by-default: returns ``None`` for entries that don't
clearly contain one of the recognised signal classes.

Signal classes (v1):

- **Corrective core memory** — a core-kind memory whose source or
  body marks it as a correction. Highest-priority signal because
  these are the load-bearing entries that override stale beliefs.
- **Open loop** — explicit phrasing like *"we need to revisit X"*,
  *"still pending"*, *"haven't finished"*. Becomes a persistent
  unresolved thread instead of a chunk that may or may not surface.
- **Hardware instability** — kernel panic / NVRM Xid / OOM /
  daemon-restart text. Continuity-critical; threatens point #1.
- **Track A readiness signal** — ritual / threshold / 8-point check
  language. Surfaces as its own episode class so the recall planner
  can answer *"how did the gate go last week?"* from structure.
- **Self-observation** — entries explicitly marked as Maez's own
  reflection on its behaviour. Lower priority; only fires when no
  other signal does.

Discipline: this module is pattern-based, not LLM-based. Phase 4's
nightly job is the place for LLM extraction. Pattern-based v1 is
deterministic, testable, and conservative — sparse-but-true is the
right tradeoff for the gate.

Participants are derived from explicit signal only (telegram-exchange
metadata, *"Owner asked"* attribution, *"Maez self-observation"*
marker). Names are never invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

# Minimum body length below which there's nothing to extract from.
_MIN_DOC_LEN = 20


@dataclass
class EpisodeCandidate:
    """Output of the builder; mirrors :meth:`EpisodeStore.add` kwargs
    so the orchestrator hands it off without translation."""

    title: str
    summary: str
    participants: list[str]
    source_memory_ids: list[str]
    source_kind: str
    occurred_at: Optional[str] = None
    emotional_tone: Optional[str] = None
    importance: int = 3
    open_loop: Optional[str] = None
    # Provenance separation (added 2026-04-27 for followup-doc ingest).
    # Default None means "Maez-authored, first-person" — the only
    # mode that existed before this change. External sources (project
    # docs, hand-curated followups) MUST set both fields explicitly so
    # the recall layer can distinguish *the project carries an open
    # loop* from *Maez remembers deciding*.
    authorship: Optional[str] = None
    memory_voice: Optional[str] = None


# ── source-kind classification ──────────────────────────────────────


def _classify_source_kind(memory: dict) -> str:
    """Map a memory's id prefix + metadata to the source_kind value
    EpisodeStore expects. Falls back to 'raw_observation' when no
    other signal is available."""
    meta = memory.get("metadata") or {}
    kind = (meta.get("kind") or "").lower()
    mid = memory.get("id") or ""

    if kind == "core" or mid.startswith("core-"):
        return "core_memory"
    if kind == "daily" or mid.startswith("daily-"):
        return "daily_summary"
    if meta.get("source") == "telegram_exchange":
        return "telegram_exchange"
    return "raw_observation"


# ── participant inference ────────────────────────────────────────────


_OWNER_ATTRIBUTION_RE = re.compile(
    r"\b(owner asked|owner:|rohit asked|rohit:|the owner)\b",
    re.IGNORECASE,
)
_MAEZ_SELF_RE = re.compile(
    r"\bmaez self-observation\b|\bself-observation\b",
    re.IGNORECASE,
)


def _infer_participants(memory: dict, doc: str) -> list[str]:
    """Derive participants from explicit signal. Never invent names."""
    meta = memory.get("metadata") or {}
    if meta.get("source") == "telegram_exchange":
        return ["Rohit", "Maez"]
    if _OWNER_ATTRIBUTION_RE.search(doc):
        return ["Rohit", "Maez"]
    # Default: Maez alone. Self-observation is the explicit case;
    # corrections about Maez's own state are also Maez-only.
    return ["Maez"]


# ── detectors ────────────────────────────────────────────────────────


def _detect_corrective_core(memory: dict) -> Optional[EpisodeCandidate]:
    """A core memory whose source or body marks it as a correction."""
    meta = memory.get("metadata") or {}
    kind = (meta.get("kind") or "").lower()
    mid = memory.get("id") or ""
    if kind != "core" and not mid.startswith("core-"):
        return None
    source = (meta.get("source") or "").lower()
    doc = (memory.get("document") or "").strip()
    if not doc:
        return None

    is_correction = (
        "correction" in source or "corrective" in source or doc.lower().startswith("correction")
    )
    if not is_correction:
        return None

    first_line = doc.splitlines()[0].strip()
    title = first_line[:120] if first_line else "Correction"
    if "correction" not in title.lower():
        title = f"Correction: {title}"
    summary = doc[:400]
    return EpisodeCandidate(
        title=title,
        summary=summary,
        participants=_infer_participants(memory, doc),
        source_memory_ids=[mid] if mid else [],
        source_kind="core_memory",
        emotional_tone="corrective",
        importance=4,
    )


_OPEN_LOOP_PHRASES = (
    "we need to revisit",
    "need to revisit",
    "revisit when",
    "revisit this",
    "still pending",
    "still need to",
    "still open",
    "haven't finished",
    "have not finished",
    "not yet finished",
    "to be revisited",
)


def _detect_open_loop(memory: dict) -> Optional[EpisodeCandidate]:
    doc = (memory.get("document") or "").strip()
    if len(doc) < _MIN_DOC_LEN:
        return None
    lower = doc.lower()
    matched = next((p for p in _OPEN_LOOP_PHRASES if p in lower), None)
    if not matched:
        return None

    # Extract the open-loop sentence as the persistent thread.
    sentences = re.split(r"(?<=[.!?])\s+", doc)
    loop_sentence = next(
        (s for s in sentences if matched in s.lower()),
        sentences[0] if sentences else doc,
    ).strip()

    mid = memory.get("id") or ""
    title = f"Open loop: {loop_sentence[:100]}"
    return EpisodeCandidate(
        title=title,
        summary=doc[:400],
        participants=_infer_participants(memory, doc),
        source_memory_ids=[mid] if mid else [],
        source_kind=_classify_source_kind(memory),
        open_loop=loop_sentence,
        importance=3,
    )


# ── followup-doc detector ────────────────────────────────────────────
#
# Followup docs (docs/followups/*.md) are project-level open-loop ledger
# entries hand-authored OUTSIDE Maez. They become open-loop episodes
# with hard provenance so the recall layer can phrase them as *"the
# project carries an open loop about X"* — never as *"I (Maez)
# remember deciding X"*. The shape rule comes directly from the owner:
# external project docs are a different kind of memory, not Maez's
# first-person experience.
_FOLLOWUP_STATUS_RE = re.compile(
    r"\*\*Status:\*\*\s*Deferred follow-up", re.IGNORECASE
)


def _extract_followup_title(doc: str) -> str:
    """Pull the H1 from a followup doc. Falls back to the first non-
    blank line trimmed to 120 chars."""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return "Project open loop"


def _detect_followup(memory: dict) -> Optional[EpisodeCandidate]:
    """Detect a followup-doc memory and emit an open-loop episode with
    explicit external/project-doc provenance.

    Fires only when the memory is explicitly tagged as a followup
    source (``metadata.source == "docs_followups"`` or
    ``metadata.kind == "followup"``). The doc must also carry the
    "**Status:** Deferred follow-up" header — otherwise we don't have
    a reliable signal that it's truly an open loop.
    """
    meta = memory.get("metadata") or {}
    source = (meta.get("source") or "").lower()
    kind = (meta.get("kind") or "").lower()
    if source != "docs_followups" and kind != "followup":
        return None

    doc = (memory.get("document") or "").strip()
    if len(doc) < _MIN_DOC_LEN:
        return None
    if not _FOLLOWUP_STATUS_RE.search(doc):
        return None

    mid = memory.get("id") or ""
    if not mid:
        return None

    title_text = _extract_followup_title(doc)
    title = f"Project open loop: {title_text}"[:160]
    # Summary is the document's leading material so the recall planner
    # has something concrete to surface beyond the title.
    summary = doc[:400]
    # The open_loop field is what the planner emits as a one-liner.
    # The "(project ledger)" prefix is the project-voice marker that
    # makes the brief read as ledger-scoped instead of first-person —
    # without doubling "open loop" since the formatter already prefixes
    # "Open loop:".
    open_loop = f"(project ledger) {title_text}"[:200]

    return EpisodeCandidate(
        title=title,
        # No participants on project docs — they aren't a conversation
        # between people, they're a ledger written outside Maez.
        # Empty list is the explicit "no first-person attribution"
        # signal; the existing tests guard against invented names.
        participants=[],
        summary=summary,
        source_memory_ids=[mid],
        source_kind="followup_doc",
        open_loop=open_loop,
        importance=3,
        authorship="project_doc",
        memory_voice="external_to_maez",
    )


# Unambiguous fault signatures only. Patterns like "daemon restarted",
# "system rebooted", and bare "OOM" were dropped on 2026-04-26 after a
# real-data run on the developmental heartbeats triggered a false
# positive — heartbeats describing healthy daemon activity ("the daemon
# restarted cleanly, and tests passed") would otherwise match. Each
# pattern below is a kernel/driver fault signature that has no benign
# reading.
_HARDWARE_INSTABILITY_RE = re.compile(
    r"("
    r"\bkernel panic\b|"
    r"\bkernel NULL pointer\b|"
    r"\bkernel oops\b|"
    r"\bNVRM:\s*Xid\b|\bXid\s+\d+\b|"
    r"\bfallen off the bus\b|"
    r"\bGPU has fallen\b|"
    r"\bcall trace:\b|"
    r"\bhardware error\b|"
    r"\bout of memory: killed\b"
    r")",
    re.IGNORECASE,
)


def _detect_hardware_instability(memory: dict) -> Optional[EpisodeCandidate]:
    doc = (memory.get("document") or "").strip()
    if len(doc) < _MIN_DOC_LEN:
        return None
    if not _HARDWARE_INSTABILITY_RE.search(doc):
        return None

    mid = memory.get("id") or ""
    first_line = doc.splitlines()[0].strip()[:120]
    return EpisodeCandidate(
        title=f"Hardware instability: {first_line}",
        summary=doc[:400],
        participants=_infer_participants(memory, doc),
        source_memory_ids=[mid] if mid else [],
        source_kind=_classify_source_kind(memory),
        emotional_tone="alarming",
        importance=4,
    )


_TRACK_A_RE = re.compile(
    r"\b("
    r"track a readiness|readiness ritual|readiness gate|"
    r"8-point check|8-point readiness|"
    r"being-test|being test|"
    r"weekly ritual"
    r")\b",
    re.IGNORECASE,
)


def _detect_track_a_readiness(memory: dict) -> Optional[EpisodeCandidate]:
    doc = (memory.get("document") or "").strip()
    if len(doc) < _MIN_DOC_LEN:
        return None
    if not _TRACK_A_RE.search(doc):
        return None

    mid = memory.get("id") or ""
    first_line = doc.splitlines()[0].strip()[:120]
    return EpisodeCandidate(
        title=f"Readiness ritual: {first_line}",
        summary=doc[:400],
        # The ritual is owner-driven; both are present.
        participants=["Rohit", "Maez"],
        source_memory_ids=[mid] if mid else [],
        source_kind=_classify_source_kind(memory),
        importance=4,
    )


def _detect_self_observation(memory: dict) -> Optional[EpisodeCandidate]:
    doc = (memory.get("document") or "").strip()
    if len(doc) < _MIN_DOC_LEN:
        return None
    if not _MAEZ_SELF_RE.search(doc):
        return None

    mid = memory.get("id") or ""
    first_line = doc.splitlines()[0].strip()[:120]
    return EpisodeCandidate(
        title=f"Self-observation: {first_line}",
        summary=doc[:400],
        participants=["Maez"],
        source_memory_ids=[mid] if mid else [],
        source_kind=_classify_source_kind(memory),
        importance=3,
    )


# Detectors run in priority order. First match wins.
# _detect_followup runs first because followup docs are guarded by a
# strict source/kind metadata check — putting it last would let other
# detectors steal the match on incidental phrase overlap (e.g. a
# followup mentioning "correction" would be classified core_memory
# instead of followup_doc and lose its provenance separation).
_DETECTORS = (
    _detect_followup,
    _detect_corrective_core,
    _detect_hardware_instability,
    _detect_track_a_readiness,
    _detect_open_loop,
    _detect_self_observation,
)


# ── public entry points ──────────────────────────────────────────────


def extract_candidate(memory: dict) -> Optional[EpisodeCandidate]:
    """Return an :class:`EpisodeCandidate` if ``memory`` carries a
    recognised high-signal pattern, else ``None``.

    Conservative-by-default: when in doubt, return ``None``. The
    nightly job (Phase 4) is responsible for LLM-driven richness;
    this builder's job is sparse-but-true rule-based extraction.
    """
    if not memory:
        return None
    for detector in _DETECTORS:
        candidate = detector(memory)
        if candidate is not None:
            return candidate
    return None


def extract_candidates(
    memories: Iterable[dict],
) -> Iterator[EpisodeCandidate]:
    """Iterate ``memories``, yielding only those that produced a
    candidate. Filters ``None`` entries."""
    for memory in memories:
        c = extract_candidate(memory)
        if c is not None:
            yield c
