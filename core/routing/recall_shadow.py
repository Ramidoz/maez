"""Content-free shadow recall outcome records and derivations.

Shadow mode observes whether the recall carrier had dated material available.
It never stores or logs the user's text, recalled snippets, or a raw trace id.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from core.routing.recall_outcome import OutcomeClass, RecallOutcome, is_false_absence


class ShadowReach(Enum):
    GROUNDED_MATERIAL_AVAILABLE = "grounded_material_available"
    CONFIRMED_ABSENCE_WITNESSED = "confirmed_absence_witnessed"
    CARRIER_UNAVAILABLE = "carrier_unavailable"


class ShadowSkip(Enum):
    # Schema-only today: shadow soft-budget overruns are observed and logged,
    # not hard-skipped. Keep the closed value for future telemetry compatibility.
    BUDGET_EXCEEDED = "budget_exceeded"
    QUEUE_FULL = "queue_full"
    EXCEPTION = "exception"


class ShadowReceipt(Enum):
    CONSULTED = "consulted"
    NOT_CONSULTED = "not_consulted"


_LEGACY_RESCUABLE_FROM = frozenset(
    {
        OutcomeClass.DECLINED_UNAVAILABLE,
        OutcomeClass.DECLINED_FAILED,
        OutcomeClass.DECLINED_UNVERIFIED,
        OutcomeClass.ANSWERED_UNVERIFIABLE,
    }
)


@dataclass(frozen=True)
class ShadowOutcome:
    schema_version: ClassVar[str] = "shadow_outcome.v1"

    shadow_pair_id: str
    legacy_outcome: OutcomeClass
    shadow_reach: ShadowReach
    rescuable_candidate: bool
    false_absence_candidate: bool
    legacy_false_absence_rescuable: bool
    latency_delta_ms: int
    receipt_state: ShadowReceipt
    ts: int
    boot_id: str
    shadow_skipped: str = "na"


def compute_shadow_pair_id(*, boot_id: str, trace_id: str | None) -> str:
    """Return a derived join key for live/shadow telemetry, or ``na``.

    Raw trace ids are already join keys elsewhere, so shadow telemetry emits a
    digest instead. Missing trace provenance must degrade to ``na`` rather than
    inventing a plausible-looking key from empty strings.
    """
    if not trace_id:
        return "na"
    digest = hashlib.sha256(
        f"recall_shadow.v1\0{boot_id or ''}\0{trace_id}".encode("utf-8")
    )
    return digest.hexdigest()[:24]


def _item_confirmed_memory_context(item) -> bool:
    # Dated recall currently routes confirmed memories into memory_context only
    # (_absolute_date_recall keeps evidence empty). If that partition changes,
    # widen this with the assembler's confirmed memory_evidence behavior.
    if getattr(item, "source_type", None) != "memory_context":
        return False
    temporal_provenance = getattr(item, "temporal_provenance", None) or {}
    return bool(temporal_provenance.get("confirmed"))


def derive_shadow_reach(working_set, *, date_addressed: bool) -> ShadowReach:
    """Return assemble-stage reach, never answer quality."""
    if not date_addressed:
        return ShadowReach.CARRIER_UNAVAILABLE
    items = list(getattr(working_set, "items", ()) or []) if working_set is not None else []
    if working_set is None or not items:
        return ShadowReach.CARRIER_UNAVAILABLE
    if any(_item_confirmed_memory_context(item) for item in items):
        return ShadowReach.GROUNDED_MATERIAL_AVAILABLE
    return ShadowReach.CONFIRMED_ABSENCE_WITNESSED


def _legacy_was_decline(legacy_rec: RecallOutcome) -> bool:
    return str(legacy_rec.outcome_class.value).startswith("declined_")


def derive_shadow_outcome(
    *,
    legacy_rec: RecallOutcome,
    shadow_reach: ShadowReach,
    date_addressed: bool,
    shadow_pair_id: str,
    latency_delta_ms: int,
    ts: int,
    boot_id: str,
) -> ShadowOutcome:
    grounded = shadow_reach is ShadowReach.GROUNDED_MATERIAL_AVAILABLE
    false_absence = bool(
        date_addressed
        and shadow_reach is ShadowReach.CONFIRMED_ABSENCE_WITNESSED
        and not _legacy_was_decline(legacy_rec)
    )
    receipt_state = (
        ShadowReceipt.NOT_CONSULTED
        if shadow_reach is ShadowReach.CARRIER_UNAVAILABLE
        else ShadowReceipt.CONSULTED
    )
    return ShadowOutcome(
        shadow_pair_id=shadow_pair_id,
        legacy_outcome=legacy_rec.outcome_class,
        shadow_reach=shadow_reach,
        rescuable_candidate=bool(legacy_rec.outcome_class in _LEGACY_RESCUABLE_FROM and grounded),
        false_absence_candidate=false_absence,
        legacy_false_absence_rescuable=bool(is_false_absence(legacy_rec) and grounded),
        latency_delta_ms=latency_delta_ms,
        receipt_state=receipt_state,
        ts=ts,
        boot_id=boot_id,
    )


def derive_shadow_skipped(
    *,
    legacy_rec: RecallOutcome,
    skip_reason: ShadowSkip,
    shadow_pair_id: str,
    latency_delta_ms: int,
    ts: int,
    boot_id: str,
) -> ShadowOutcome:
    return ShadowOutcome(
        shadow_pair_id=shadow_pair_id,
        legacy_outcome=legacy_rec.outcome_class,
        shadow_reach=ShadowReach.CARRIER_UNAVAILABLE,
        rescuable_candidate=False,
        false_absence_candidate=False,
        legacy_false_absence_rescuable=False,
        latency_delta_ms=latency_delta_ms,
        receipt_state=ShadowReceipt.NOT_CONSULTED,
        ts=ts,
        boot_id=boot_id,
        shadow_skipped=skip_reason.value,
    )
