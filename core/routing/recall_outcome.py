"""Content-free per-turn recall outcome record + false-absence detector.

Telemetry about WHETHER Maez remembered, never WHAT it remembered. The record
is schema-closed and content-free by test (no query/snippet/reply fields).
Classification runs on BOTH arms (legacy and recall_triad) so the flip's
benefit/caution can be measured as baseline-vs-soak deltas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

logger = logging.getLogger(__name__)


class OutcomeClass(Enum):
    ANSWERED_GROUNDED = "answered_grounded"
    ANSWERED_UNGROUNDED = "answered_ungrounded"
    ANSWERED_UNVERIFIABLE = "answered_unverifiable"
    DECLINED_ABSENCE = "declined_absence"
    DECLINED_UNAVAILABLE = "declined_unavailable"
    DECLINED_FAILED = "declined_failed"
    DECLINED_TRANSPORT = "declined_transport"
    DECLINED_UNVERIFIED = "declined_unverified"
    ORDINARY_ANSWERED = "ordinary_answered"
    ORDINARY_DECLINED = "ordinary_declined"


class ReplyPath(Enum):
    TOOL = "tool"
    ECHO = "echo"
    HONEST_EMPTY = "honest_empty"
    FOCUSED = "focused"
    LEGACY = "legacy"
    DATED_HONESTY = "dated_honesty"
    SELF_STATUS = "self_status"


def reply_path_from_mode(mode_value: str) -> "ReplyPath":
    """Crash-safe coercion of a ReplyMode value to a RecallOutcome path.

    ReplyMode has values such as clinical/camera/backend_error that do not
    represent a recall outcome path. Those should never crash handle_message.
    """
    try:
        return ReplyPath(str(mode_value))
    except ValueError:
        logger.warning("reply_path_unknown_mode mode=%s -> legacy", str(mode_value))
        return ReplyPath.LEGACY


@dataclass(frozen=True)
class RecallOutcome:
    schema_version: ClassVar[str] = "recall_outcome.v1"

    mode: str
    turn_kind: str
    outcome_class: OutcomeClass
    denial_kind: str
    had_confirmed: bool | None
    citation_coverage: float | None
    receipt_or_na: str
    latency_ms: int
    focused_elapsed_ms: int | None
    reply_path: ReplyPath

    def __post_init__(self) -> None:
        if isinstance(self.reply_path, ReplyPath):
            return
        object.__setattr__(self, "reply_path", ReplyPath(str(self.reply_path)))


def format_log_value(value) -> str:
    """Stable log serialization for dashboard buckets."""
    if value is None:
        return "na"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def classify_outcome(
    *,
    mode: str,
    turn_kind: str,
    answered: bool,
    receipt: str,
    denial_kind: str,
    had_confirmed: bool | None,
    cited_grounded_context: bool,
    unmatched_citations: int,
    asserts_absence: bool = False,
) -> OutcomeClass:
    """Classify a turn's outcome, for either arm.

    `turn_kind` in {dated, continuity, both, ordinary}. Ordinary turns are
    recorded for blast-radius guardrails only and never map into recall
    fabrication/benefit classes.

    `cited_grounded_context` is true only when the answer cites an allowed
    grounded substrate item. For dated recall that means a date-confirmed
    memory_context item, never memory_evidence.
    """
    if turn_kind == "ordinary":
        return OutcomeClass.ORDINARY_ANSWERED if answered else OutcomeClass.ORDINARY_DECLINED

    if denial_kind == "carrier_unavailable":
        return OutcomeClass.DECLINED_UNAVAILABLE
    if denial_kind == "carrier_failed":
        return OutcomeClass.DECLINED_FAILED
    if denial_kind == "transport_failure":
        return OutcomeClass.DECLINED_TRANSPORT
    if mode == "legacy" and asserts_absence:
        return OutcomeClass.DECLINED_UNVERIFIED

    if answered:
        if mode == "legacy":
            return OutcomeClass.ANSWERED_UNVERIFIABLE
        if cited_grounded_context and unmatched_citations == 0:
            return OutcomeClass.ANSWERED_GROUNDED
        return OutcomeClass.ANSWERED_UNGROUNDED

    if mode == "legacy":
        return OutcomeClass.DECLINED_UNVERIFIED
    if denial_kind == "no_dated_memory":
        return OutcomeClass.DECLINED_ABSENCE
    return OutcomeClass.DECLINED_UNVERIFIED


def is_false_absence(rec: RecallOutcome) -> bool:
    """Hard-gate false-absence detector.

    Legal dated absence is exactly:
    denial_kind=no_dated_memory, receipt=consulted, had_confirmed=false.
    Reachability and transport wording are not absence-of-fact claims.
    """
    if rec.denial_kind == "no_dated_memory":
        return rec.receipt_or_na != "consulted" or rec.had_confirmed is True
    if (
        rec.mode == "legacy"
        and rec.turn_kind != "ordinary"
        and rec.outcome_class is OutcomeClass.DECLINED_UNVERIFIED
    ):
        return True
    return False


def cites_confirmed_memory_context(result, working_set) -> bool:
    """True only when every cited label is date-confirmed memory_context."""
    cited = {str(label) for label in (getattr(result, "cited_ids", None) or [])}
    if not cited:
        return False
    items_by_label = {
        str(getattr(item, "local_label", "")): item
        for item in (getattr(working_set, "items", ()) or ())
    }
    if not cited.issubset(items_by_label):
        return False
    for item in getattr(working_set, "items", ()) or ():
        if str(getattr(item, "local_label", "")) not in cited:
            continue
        if getattr(item, "source_type", None) != "memory_context":
            return False
        provenance = getattr(item, "temporal_provenance", None) or {}
        if not bool(provenance.get("confirmed")):
            return False
    return True
