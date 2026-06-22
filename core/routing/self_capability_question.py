from __future__ import annotations

import re

QUESTION_SHAPE_RE = re.compile(
    r"^\s*(what|who|when|where|why|how|is|are|do|does|did|can|could|should|has|have|tell me|any)\b|[?]",
    re.IGNORECASE,
)

SELF_CAPABILITY_RE = re.compile(
    r"\b(?:you|your|maez|yourself)\b.*\b(?:web search|search tools?|page read|page reading|"
    r"web sense|search sense|tools?|capabilit(?:y|ies))\b"
    r"|\b(?:web search|search tools?|page read|page reading|web sense|search sense|tools?|"
    r"capabilit(?:y|ies))\b.*\b(?:you|your|maez|yourself)\b",
    re.IGNORECASE,
)


def bodyish_self_capability_candidate(utterance: str) -> bool:
    """True when the text mentions Maez/body/tool capability terms.

    This is the leak witness, not the carve-out. It intentionally ignores
    question shape so shadow can reveal body-ish statements that would still
    be lean-eligible.
    """
    return bool(SELF_CAPABILITY_RE.search(utterance or ""))


def is_self_capability_question(utterance: str) -> bool:
    """Exact shared version of Layer0's self-capability question predicate."""
    if not QUESTION_SHAPE_RE.search(utterance or ""):
        return False
    return bodyish_self_capability_candidate(utterance)
