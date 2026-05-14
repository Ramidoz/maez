# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Pure post-ARS guard for temporal-memory reply fragments.

TRF v1 runs only after audit/ARS has already removed ungrounded model
claims. It does not call an LLM and does not weaken the audit. It replaces
clipped temporal-memory fragments with a fixed, council-ratified fallback plus
mechanical witness language for explicit first-person user self-reports.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from core.memory.temporal_anchor_recall import TemporalAnchorRecallResult

_NO_MATCH_FALLBACK = "I'm not finding that clearly right now."
_HELPER_UNAVAILABLE_FALLBACK = "I can't check that clearly right now."
_EVIDENCE_FOUND_FRAGMENT_FALLBACK = (
    "I found something from that window, but I need to answer it carefully."
)

_LEADING_CONNECTOR_RE = re.compile(
    r"^\s*(but|and|however|though|so|still|also)\b",
    re.IGNORECASE,
)

_APPROVED_RETRIEVAL_RE = re.compile(
    r"\b(i\s+found|i\s+am\s+finding|i'?m\s+finding|"
    r"i\s+am\s+not\s+finding|i'?m\s+not\s+finding|"
    r"i\s+cannot\s+check|i\s+can'?t\s+check|"
    r"memory\s+from\s+last\s+week|from\s+yesterday|from\s+this\s+morning|"
    r"from\s+earlier\s+today)\b",
    re.IGNORECASE,
)

_AFFECT_ONLY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*that'?s\s+the\s+gap[.!?]?\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*(but\s+)?i'?m\s+glad\s+to\s+hear\s+you'?re\s+feeling\s+better(?:\s+now|\s+today|\s+okay|\s+yes)*[.!?]?\s*$",
        re.IGNORECASE,
    ),
)

_MEMORY_CLAIM_RE = re.compile(
    r"^\s*i\s+(remember|recall)\b",
    re.IGNORECASE,
)

_ANCHOR_RE = r"(last week|yesterday|this morning|earlier today)"
_FEEL_COMPARED_RE = re.compile(
    rf"\bi\s+feel\s+(?P<phrase>[^.!?\n]+?)\s+compared\s+to\s+(?P<anchor>{_ANCHOR_RE})\b",
    re.IGNORECASE,
)
_FEEL_THAN_RE = re.compile(
    rf"\bi\s+feel\s+(?P<phrase>[^.!?\n]+?)\s+than\s+(?P<anchor>{_ANCHOR_RE})\b",
    re.IGNORECASE,
)
_FEELING_COMPARED_RE = re.compile(
    rf"\bi'?m\s+feeling\s+(?P<phrase>[^.!?\n]+?)\s+compared\s+to\s+(?P<anchor>{_ANCHOR_RE})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CurrentMessageContext:
    has_grounded_self_report: bool
    self_report_phrase: str
    anchor_kind: str | None


@dataclass(frozen=True)
class FragmentGuardResult:
    text: str
    guard_used: bool
    reason: Literal[
        "fragment_replaced",
        "not_fragment",
        "helper_unavailable_fallback",
        "guard_unavailable",
    ]


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _has_approved_retrieval(text: str) -> bool:
    return _APPROVED_RETRIEVAL_RE.search(text or "") is not None


def is_temporal_ars_fragment(
    text: str,
    *,
    temporal_question: bool,
    evidence_found: bool = False,
) -> bool:
    """Return True for clipped post-ARS temporal-memory non-answers."""
    if not temporal_question:
        return False
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _MEMORY_CLAIM_RE.search(stripped):
        return True
    if _has_approved_retrieval(stripped):
        return False
    if any(pattern.match(stripped) for pattern in _AFFECT_ONLY_PATTERNS):
        return True
    if _LEADING_CONNECTOR_RE.search(stripped):
        return True
    if _word_count(stripped) < 12 and re.search(
        r"\b(glad|better|gap|hear|okay|yes)\b",
        stripped,
        re.IGNORECASE,
    ):
        return True
    return False


def _anchor_kind(anchor: str) -> str:
    return anchor.lower().replace(" ", "_")


def _clean_phrase(phrase: str) -> str:
    cleaned = re.sub(r"\s+", " ", phrase).strip(" ,.;:!?")
    # Avoid preserving a whole second clause as a "feeling phrase".
    cleaned = re.split(r"\b(and|but|because|since)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip(" ,.;:!?")


def extract_current_message_context(user_message: str) -> CurrentMessageContext:
    """Extract only explicit first-person self-reports from the current message."""
    text = user_message or ""
    for pattern, connector in (
        (_FEEL_COMPARED_RE, "than"),
        (_FEELING_COMPARED_RE, "than"),
        (_FEEL_THAN_RE, "than"),
    ):
        match = pattern.search(text)
        if not match:
            continue
        phrase = _clean_phrase(match.group("phrase"))
        anchor = match.group("anchor").lower()
        if not phrase:
            continue
        return CurrentMessageContext(
            has_grounded_self_report=True,
            self_report_phrase=f"{phrase} {connector} {anchor}",
            anchor_kind=_anchor_kind(anchor),
        )
    return CurrentMessageContext(
        has_grounded_self_report=False,
        self_report_phrase="",
        anchor_kind=None,
    )


def _fallback_for(
    status: str,
) -> tuple[str, Literal["fragment_replaced", "helper_unavailable_fallback"]]:
    if status == "helper_unavailable":
        return _HELPER_UNAVAILABLE_FALLBACK, "helper_unavailable_fallback"
    if status == "evidence_found":
        return _EVIDENCE_FOUND_FRAGMENT_FALLBACK, "fragment_replaced"
    return _NO_MATCH_FALLBACK, "fragment_replaced"


def guard_temporal_ars_fragment(
    *,
    user_message: str,
    post_ars_text: str,
    temporal_result: TemporalAnchorRecallResult,
    current_context: CurrentMessageContext,
) -> FragmentGuardResult:
    """Replace temporal-memory fragments with a fixed honest fallback.

    Fail-neutral by construction: no external calls, no writes, no exceptions
    expected from normal inputs.
    """
    if not getattr(temporal_result, "anchor_detected", False):
        return FragmentGuardResult(
            text=post_ars_text,
            guard_used=False,
            reason="not_fragment",
        )
    if not is_temporal_ars_fragment(
        post_ars_text,
        temporal_question=True,
        evidence_found=getattr(temporal_result, "search_status", "") == "evidence_found",
    ):
        return FragmentGuardResult(
            text=post_ars_text,
            guard_used=False,
            reason="not_fragment",
        )
    fallback, reason = _fallback_for(getattr(temporal_result, "search_status", ""))
    pieces = [fallback]
    if (
        reason != "helper_unavailable_fallback"
        and current_context.has_grounded_self_report
        and current_context.self_report_phrase
    ):
        pieces.append(f"I hear that you feel {current_context.self_report_phrase}.")
    return FragmentGuardResult(
        text=" ".join(pieces),
        guard_used=True,
        reason=reason,
    )


__all__ = [
    "CurrentMessageContext",
    "FragmentGuardResult",
    "extract_current_message_context",
    "guard_temporal_ars_fragment",
    "is_temporal_ars_fragment",
]
