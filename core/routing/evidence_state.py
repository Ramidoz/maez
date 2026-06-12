# Copyright (C) 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Evidence Precedence Steer helpers.

This module is intentionally pure: no I/O, no LLM calls, no daemon imports.
Callers must pass the raw dispatcher transcript, never the composed transcript
context with instruction examples appended.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.routing.search_context import WEB_NO_RESULTS as _WEB_NO_RESULTS


_POSITIVE_MARKERS: tuple[str, ...] = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
)

_SOURCE_HINTS: dict[str, str] = {
    "memory evidence": "substrate recall",
    "memory context": "substrate recall",
    "fresh evidence": "fresh evidence",
    "web search results": "web search results",
}

@dataclass(frozen=True)
class EvidenceState:
    evidence_present: bool
    marker_labels: tuple[str, ...] = ()
    source_hint: tuple[str, ...] = ()
    descriptions: tuple[str, ...] = ()


def _label_for_marker(marker: str) -> str:
    return marker.strip("[]")


def _first_line_after(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    tail = text[index + len(marker) :].lstrip()
    lines = tail.splitlines()
    if not lines:
        return ""
    return lines[0][:120]


def turn_evidence_state(*, transcript: str, web_context: str) -> EvidenceState:
    """Return whether this turn is holding query evidence.

    Background lived/ambient/temporal context intentionally does not flow
    through this API; only current-turn dispatcher transcript markers and real
    legacy web results count.
    """

    transcript = transcript or ""
    web_context = web_context or ""
    labels: list[str] = []
    hints: list[str] = []
    descriptions: list[str] = []

    for marker in _POSITIVE_MARKERS:
        if marker in transcript:
            label = _label_for_marker(marker)
            labels.append(label)
            hints.append(_SOURCE_HINTS[label])
            descriptions.append(_first_line_after(transcript, marker))

    web_context = web_context.strip()
    if web_context and _WEB_NO_RESULTS not in web_context:
        labels.append("web search results")
        hints.append(_SOURCE_HINTS["web search results"])
        lines = web_context.splitlines()
        descriptions.append(lines[0][:120] if lines else "")

    return EvidenceState(
        evidence_present=bool(labels),
        marker_labels=tuple(labels),
        source_hint=tuple(hints),
        descriptions=tuple(descriptions),
    )


def build_evidence_precedence_directive(state: EvidenceState) -> str:
    """Build the final-tail instruction for evidence-present turns."""

    lines = [
        "EVIDENCE PRESENT THIS TURN.",
        "You are holding real evidence for the owner's question right now:",
    ]
    for label, description in zip(
        state.marker_labels,
        state.descriptions,
        strict=True,
    ):
        if description:
            lines.append(f"  - {label}: {description}")
        else:
            lines.append(f"  - {label}")
    lines.append(
        "Answer from this evidence. If a live/fresh fetch failed but substrate "
        "evidence exists, say that distinction plainly."
    )
    lines.append(
        "You may NOT claim the relevant source is blocked, missing, unavailable, "
        "or not-wired this turn - the evidence above contradicts that."
    )
    try:
        from core.cognition.capability_card import evidence_precedence_enabled

        if evidence_precedence_enabled():
            lines.append(
                "Recalled memories may CONTEXTUALIZE the fresh evidence above; they "
                "may not CONTRADICT it. Your memory of past failures with similar "
                "pages or searches is not evidence about THIS evidence."
            )
            lines.append(
                "Before you claim the evidence lacks or truncates something, re-read "
                "the evidence text itself - the detail you remember missing before "
                "may be present now."
            )
    except Exception:
        pass
    return "\n".join(lines)


def build_turn_final_context(transcript_context: str, evidence_directive: str) -> str:
    """Return the true final system tail for the turn."""

    transcript_context = transcript_context or ""
    evidence_directive = evidence_directive or ""
    if not evidence_directive:
        return transcript_context
    if transcript_context.strip():
        return f"{transcript_context}\n\n{evidence_directive}"
    return evidence_directive
