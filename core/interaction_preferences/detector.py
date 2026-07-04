from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PreferenceAction = Literal["capture", "retract"]
PreferenceClass = Literal["question_cadence"]


@dataclass(frozen=True)
class PreferenceDetection:
    action: PreferenceAction
    preference_class: PreferenceClass
    owner_statement: str


_CAPTURE_PATTERNS = (
    re.compile(r"\bstop asking me so many questions\b", re.IGNORECASE),
    re.compile(r"\bplease stop asking so many questions\b", re.IGNORECASE),
    re.compile(r"\bask fewer questions\b", re.IGNORECASE),
    re.compile(r"\bdon['’]t ask so many follow-up questions\b", re.IGNORECASE),
)

_RETRACTION_PATTERNS = (
    re.compile(r"\bactually,\s*ask away\b", re.IGNORECASE),
    re.compile(r"\bit'?s okay to ask questions again\b", re.IGNORECASE),
    re.compile(r"\byou can ask questions again\b", re.IGNORECASE),
    re.compile(r"\bask away\b", re.IGNORECASE),
)

_ATTRIBUTION_MARKERS = (
    "transcript says",
    "transcript said",
    "log reads",
    "test fixture says",
    "fixture says",
    "someone said",
    "they told me",
    "in the log:",
)

_OWNERSHIP_MARKERS = (
    "i mean it",
    "my preference",
    "i want",
)


def _quote_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pairs = {'"': '"', "'": "'", "`": "`", "“": "”", "‘": "’"}
    i = 0
    while i < len(text):
        opener = text[i]
        closer = pairs.get(opener)
        if closer is None:
            i += 1
            continue
        if opener == "'" and 0 < i < len(text) - 1:
            if text[i - 1].isalpha() and text[i + 1].isalpha():
                i += 1
                continue
        end = text.find(closer, i + 1)
        if end == -1:
            i += 1
            continue
        spans.append((i, end + 1))
        i = end + 1
    return spans


def _inside_span(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def _attributed(text: str, start: int) -> bool:
    prefix = text[max(0, start - 80) : start].lower()
    marker_positions = [prefix.rfind(marker) for marker in _ATTRIBUTION_MARKERS]
    marker_positions = [pos for pos in marker_positions if pos >= 0]
    if not marker_positions:
        return False
    marker_pos = max(marker_positions)
    after_marker = prefix[marker_pos:]
    if any(marker in after_marker for marker in _OWNERSHIP_MARKERS):
        return False
    return True


def _rejected_trailing_context(text: str, end: int) -> bool:
    suffix = text[end : min(len(text), end + 40)].lower()
    return suffix.lstrip().startswith("in the test fixture")


def _match_unquoted_direct(text: str) -> str | None:
    spans = _quote_spans(text)
    for pattern in _CAPTURE_PATTERNS:
        for match in pattern.finditer(text):
            if _inside_span(match.start(), spans):
                continue
            if _attributed(text, match.start()):
                continue
            if _rejected_trailing_context(text, match.end()):
                continue
            return match.group(0)
    return None


def _match_retraction(text: str) -> str | None:
    spans = _quote_spans(text)
    for pattern in _RETRACTION_PATTERNS:
        for match in pattern.finditer(text):
            if _inside_span(match.start(), spans):
                continue
            return match.group(0)
    return None


def detect_interaction_preference(
    text: str,
    *,
    active_question_cadence: bool,
    surface: str,
) -> PreferenceDetection | None:
    del surface
    if not str(text or "").strip():
        return None
    if active_question_cadence:
        retraction = _match_retraction(text)
        if retraction:
            return PreferenceDetection(
                action="retract",
                preference_class="question_cadence",
                owner_statement=retraction,
            )
    capture = _match_unquoted_direct(text)
    if capture:
        return PreferenceDetection(
            action="capture",
            preference_class="question_cadence",
            owner_statement=capture,
        )
    return None
