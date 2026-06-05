# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The Intake Bus admission doorway.

A limb brings a sealed, labeled package; the doorway decides whether it may
enter the body, what trust it gets, and whether it only stays staged. Ordered,
fail-closed. ``refused`` is a returned content-free verdict; substrate
uncertainty raises rather than being laundered into "absent, admit."
"""

from __future__ import annotations

from core.egress.gate import KNOWN_ORIGINS
from core.intake_bus.contract import IntakeFact, IntakeOutcome, PromotionPosture


def _validate(fact: IntakeFact) -> str | None:
    """Return a content-free refusal code, or None if the fact may proceed."""
    if not fact.source_ref:
        return "missing_source_ref"
    if not fact.content:
        return "missing_content"
    if fact.egress_origin_class == "unclassified":
        return "unclassified_origin"
    if fact.egress_origin_class not in KNOWN_ORIGINS:
        return "unknown_origin_class"
    return None


def admit(store_adapter, memory) -> IntakeOutcome:
    """Admit, refuse, stage, or no-op the limb's oldest pending fact."""
    fact = store_adapter.oldest_pending()
    if fact is None:
        return IntakeOutcome(status="nothing_pending", source_ref=None)

    reason = _validate(fact)
    if reason is not None:
        return IntakeOutcome(status="refused", source_ref=fact.source_ref, reason=reason)

    if fact.promotion_posture is PromotionPosture.STAGE_ONLY:
        return IntakeOutcome(status="staged_not_admitted", source_ref=fact.source_ref)

    existing = memory.body_row_id_by_source_ref(
        fact.source_ref,
        egress_origin_class=fact.egress_origin_class,
    )
    if existing is not None:
        store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(existing))
        return IntakeOutcome(status="already_admitted", source_ref=fact.source_ref)

    body_id = memory.store(
        content=fact.content,
        cycle=0,
        provenance_source=fact.provenance_source,
        egress_origin_class=fact.egress_origin_class,
        metadata={
            "source_ref": fact.source_ref,
            "fetch_batch_id": fact.fetch_batch_id,
            **dict(fact.metadata),
        },
    )
    store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(body_id))
    return IntakeOutcome(status="admitted", source_ref=fact.source_ref)
