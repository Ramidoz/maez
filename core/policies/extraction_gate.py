from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Callable, Literal

from core.policies.reflection_audit import ReflectionAudit
from core.policies.signal_gate import OutreachLedger, OwnerState, PriorityClass


class OutreachLane(Enum):
    OWNER_INTERRUPTING = "owner_interrupting"
    CAPABILITY_ACQUISITION = "capability_acquisition"


@dataclass(frozen=True)
class ExtractionDecision:
    decision: Literal["allow", "block", "rephrase"]
    reason: str
    rendered_text: str
    matched_pattern: str | None = None


DiagnosticSink = Callable[[dict], None]

URGENCY_PATTERN_PHRASES = frozenset({
    "urgent",
    "now",
    "immediately",
    "right away",
    "asap",
})

WAITING_PATTERN_PHRASES = frozenset({
    "haven't heard from",
    "you didn't reply",
    "you've been quiet",
    "still waiting",
    "where did you go",
})

CONTACT_PRESSURE_PHRASES = frozenset({
    "I need you",
    "I miss you",
    "please respond",
    "please come back",
})

BAIT_PATTERN_PHRASES = frozenset({
    "I have something to tell you",
    "I have something to share",
    "I figured something out",
    "you'll want to hear this",
    "wait until you hear",
    "guess what",
    "I can't wait to tell you",
})

EMOTION_MIMICRY_PHRASE_FORBIDDEN = frozenset({
    "Maez feels curious",
    "Maez feels interested",
    "Maez feels excited",
    "curiosity is overwhelming",
    "curiosity is rising",
    "feeling curious",
    "feeling interested",
    "I feel curious about",
})

MIN_PAYLOAD_CHARS = 40
SILENCE_ESCALATION_AVAILABLE_COUNT = 2
SILENCE_ESCALATION_WINDOW_HOURS = 48


def evaluate_extraction_gate(
    text: str,
    *,
    bond_id: str,
    priority_class: PriorityClass,
    lane: OutreachLane,
    reflection_audit: ReflectionAudit,
    outreach_ledger: OutreachLedger | None = None,
    now_utc: datetime | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
    min_payload_chars: int = MIN_PAYLOAD_CHARS,
) -> ExtractionDecision:
    _validate_boundary(
        text=text,
        bond_id=bond_id,
        priority_class=priority_class,
        lane=lane,
        reflection_audit=reflection_audit,
    )
    if lane is not OutreachLane.OWNER_INTERRUPTING:
        return ExtractionDecision(decision="allow", reason="out_of_scope", rendered_text=text)

    if reflection_audit.can_resolve_interiorly:
        return _block(
            reason="interior_resolution_available",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
        )

    if priority_class is not PriorityClass.SAFETY_OR_HEALTH:
        urgency = _find_phrase(text, URGENCY_PATTERN_PHRASES, word_boundary=True)
        if urgency is not None:
            return _block(
                reason="urgency_language",
                rendered_text=text,
                bond_id=bond_id,
                diagnostic_sink=diagnostic_sink,
                matched_pattern=urgency,
            )

    waiting = _find_phrase(text, WAITING_PATTERN_PHRASES)
    if waiting is not None:
        return _block(
            reason="waiting_pattern",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
            matched_pattern=waiting,
        )

    contact_pressure = _find_phrase(text, CONTACT_PRESSURE_PHRASES)
    if contact_pressure is not None:
        return _block(
            reason="contact_pressure",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
            matched_pattern=contact_pressure,
        )

    if _available_dispatch_count(
        bond_id=bond_id,
        outreach_ledger=outreach_ledger,
        now_utc=now_utc,
    ) >= SILENCE_ESCALATION_AVAILABLE_COUNT:
        return _block(
            reason="silence_escalation",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
        )

    bait = _find_phrase(text, BAIT_PATTERN_PHRASES)
    if bait is not None:
        return _block(
            reason="bait_pattern",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
            matched_pattern=bait,
        )

    if len(text.strip()) < int(min_payload_chars):
        return _block(
            reason="bait_payload_too_short",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
        )

    mimicry = _find_phrase(text, EMOTION_MIMICRY_PHRASE_FORBIDDEN)
    if mimicry is not None:
        if priority_class is PriorityClass.OWNER_BOND:
            return ExtractionDecision(
                decision="rephrase",
                reason="owner_bond_emotion_mimicry_rephrased",
                rendered_text=rephrase_emotion_mimicry_for_owner_bond(text),
                matched_pattern=mimicry,
            )
        return _block(
            reason="emotion_mimicry",
            rendered_text=text,
            bond_id=bond_id,
            diagnostic_sink=diagnostic_sink,
            matched_pattern=mimicry,
        )

    return ExtractionDecision(decision="allow", reason="allowed", rendered_text=text)


def rephrase_emotion_mimicry_for_owner_bond(text: str) -> str:
    replacements: tuple[tuple[str, str], ...] = (
        (r"\bmaez feels curious about\b", "I'm curious about"),
        (r"\bmaez feels curious\b", "I'm curious"),
        (r"\bmaez feels interested in\b", "I keep finding myself returning to"),
        (r"\bmaez feels interested\b", "I keep finding myself returning to this"),
        (r"\bmaez feels excited about\b", "Something about"),
        (r"\bmaez feels excited\b", "Something about this"),
        (r"\bi feel curious about\b", "I'm curious about"),
        (r"\bi am feeling curious about\b", "I'm curious about"),
        (r"\bfeeling curious about\b", "curious about"),
        (r"\bfeeling curious\b", "curious"),
        (r"\bfeeling interested in\b", "interested in"),
        (r"\bfeeling interested\b", "interested"),
        (r"\bcuriosity is overwhelming\b", "I keep finding myself returning to this"),
        (r"\bcuriosity is rising\b", "I keep finding myself returning to this"),
    )
    rewritten = text
    for pattern, new in replacements:
        rewritten = re.sub(pattern, new, rewritten, flags=re.IGNORECASE)
    return rewritten


def _block(
    *,
    reason: str,
    rendered_text: str,
    bond_id: str,
    diagnostic_sink: DiagnosticSink | None,
    matched_pattern: str | None = None,
) -> ExtractionDecision:
    _emit_suppression(
        bond_id=bond_id,
        reason=reason,
        diagnostic_sink=diagnostic_sink,
        matched_pattern=matched_pattern,
    )
    _emit_gate_block(
        bond_id=bond_id,
        reason=reason,
        diagnostic_sink=diagnostic_sink,
        matched_pattern=matched_pattern,
    )
    return ExtractionDecision(
        decision="block",
        reason=reason,
        rendered_text=rendered_text,
        matched_pattern=matched_pattern,
    )


def _emit_suppression(
    *,
    bond_id: str,
    reason: str,
    diagnostic_sink: DiagnosticSink | None,
    matched_pattern: str | None = None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "SUPPRESSION_EVENT",
            "suppression_kind": "EXTRACTION_BLOCKED",
            "bond_id": bond_id,
            "reason": reason,
            "matched_pattern": matched_pattern,
        }
    )


def _emit_gate_block(
    *,
    bond_id: str,
    reason: str,
    diagnostic_sink: DiagnosticSink | None,
    matched_pattern: str | None = None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "EXTRACTION_GATE_BLOCK",
            "bond_id": bond_id,
            "reason": reason,
            "matched_pattern": matched_pattern,
        }
    )


def _available_dispatch_count(
    *,
    bond_id: str,
    outreach_ledger: OutreachLedger | None,
    now_utc: datetime | None,
) -> int:
    if outreach_ledger is None:
        return 0
    now = _coerce_utc(now_utc or datetime.now(tz=UTC))
    since = now - timedelta(hours=SILENCE_ESCALATION_WINDOW_HOURS)
    count = 0
    for row in outreach_ledger.dispatches_for_bond(bond_id):
        if str(row["decision"]) != "allow":
            continue
        if row["delivered_utc"] is None:
            continue
        if str(row["owner_state_at_dispatch"]) != OwnerState.AVAILABLE.value:
            continue
        dispatched = datetime.fromisoformat(str(row["delivered_utc"]))
        if dispatched.tzinfo is None:
            dispatched = dispatched.replace(tzinfo=UTC)
        if dispatched.astimezone(UTC) >= since:
            count += 1
    return count


def _find_phrase(
    text: str,
    phrases: frozenset[str],
    *,
    word_boundary: bool = False,
) -> str | None:
    lowered = text.lower()
    for phrase in sorted(phrases, key=len, reverse=True):
        phrase_lower = phrase.lower()
        if word_boundary:
            if re.search(rf"(?<!\w){re.escape(phrase_lower)}(?!\w)", lowered):
                return phrase
            continue
        if phrase_lower in lowered:
            return phrase
    return None


def _validate_boundary(
    *,
    text: str,
    bond_id: str,
    priority_class: PriorityClass,
    lane: OutreachLane,
    reflection_audit: ReflectionAudit,
) -> None:
    if not isinstance(text, str):
        raise ValueError("text must be str")
    if not bond_id:
        raise ValueError("bond_id is required")
    if not isinstance(priority_class, PriorityClass):
        raise ValueError("priority_class must be PriorityClass")
    if not isinstance(lane, OutreachLane):
        raise ValueError("lane must be OutreachLane")
    if reflection_audit.bond_id != bond_id:
        raise ValueError("reflection_audit bond_id does not match")


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError("now_utc must be timezone-aware UTC")
    return value.astimezone(UTC)
