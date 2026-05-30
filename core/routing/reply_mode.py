"""Single declared-precedence resolver for MaezDaemon.handle_message reply modes.

resolve_reply_mode encodes the current declared precedence. Date-addressed turns
prefer FOCUSED over HONEST_EMPTY so the temporal recall/status path can answer
instead of being pre-empted by a zero-result web search.

DATED_HONESTY and BACKEND_ERROR are execution outcomes of FOCUSED / LEGACY, not
initial resolver winners; resolve_reply_mode never returns them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReplyMode(Enum):
    CLINICAL = "CLINICAL"
    CAMERA = "CAMERA"
    TOOL = "TOOL"
    ECHO = "ECHO"
    HONEST_EMPTY = "HONEST_EMPTY"
    FOCUSED = "FOCUSED"
    LEGACY = "LEGACY"
    DATED_HONESTY = "DATED_HONESTY"
    BACKEND_ERROR = "BACKEND_ERROR"


@dataclass(frozen=True)
class ReplyDecisionSignals:
    clinical_matched: bool = False
    camera_answer: str | None = None
    authoritative_tool_reply: bool = False
    echo_reply: bool = False
    honest_empty_candidate: bool = False
    focused_candidate: bool = False
    date_addressed: bool = False


@dataclass(frozen=True)
class ReplyDecision:
    mode: ReplyMode
    call_purpose: str
    skip_tail: bool = False
    skip_reason: str | None = None


_CALL_PURPOSE = {
    ReplyMode.CLINICAL: "clinical_boundary",
    ReplyMode.CAMERA: "camera_direct",
    ReplyMode.TOOL: "authoritative_tool",
    ReplyMode.ECHO: "echo_reply",
    ReplyMode.HONEST_EMPTY: "honest_empty",
    ReplyMode.FOCUSED: "legacy_candidate",
    ReplyMode.LEGACY: "llm_synthesis",
}


def resolve_reply_mode(signals: ReplyDecisionSignals) -> ReplyDecision:
    """Return today's top-level reply mode.

    Order is the behavior contract. HONEST_EMPTY excludes date-addressed turns;
    date-addressed misses are handled by focused temporal status/honesty.
    """
    if signals.clinical_matched:
        return ReplyDecision(
            ReplyMode.CLINICAL,
            _CALL_PURPOSE[ReplyMode.CLINICAL],
            skip_tail=True,
            skip_reason="deterministic_policy_reply",
        )
    if signals.camera_answer is not None:
        return ReplyDecision(
            ReplyMode.CAMERA,
            _CALL_PURPOSE[ReplyMode.CAMERA],
            skip_tail=True,
            skip_reason="deterministic_policy_reply",
        )
    if signals.authoritative_tool_reply:
        return ReplyDecision(ReplyMode.TOOL, _CALL_PURPOSE[ReplyMode.TOOL])
    if signals.echo_reply:
        return ReplyDecision(ReplyMode.ECHO, _CALL_PURPOSE[ReplyMode.ECHO])
    if signals.focused_candidate:
        return ReplyDecision(ReplyMode.FOCUSED, _CALL_PURPOSE[ReplyMode.FOCUSED])
    if signals.honest_empty_candidate and not signals.date_addressed:
        return ReplyDecision(
            ReplyMode.HONEST_EMPTY,
            _CALL_PURPOSE[ReplyMode.HONEST_EMPTY],
        )
    return ReplyDecision(ReplyMode.LEGACY, _CALL_PURPOSE[ReplyMode.LEGACY])
