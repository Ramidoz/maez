# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Intake Bus v0 — the admission doorway and its synthetic rider."""

from __future__ import annotations

import unittest

from core.intake_bus.contract import (
    IntakeFact,
    IntakeOutcome,
    PromotionPosture,
)
from memory.memory_manager import ProvenanceSource


class ContractShapeTests(unittest.TestCase):
    def test_promotion_posture_values(self):
        self.assertEqual(PromotionPosture.ADMIT_TO_BODY.value, "admit_to_body")
        self.assertEqual(PromotionPosture.STAGE_ONLY.value, "stage_only")

    def test_intake_fact_is_frozen(self):
        fact = IntakeFact(
            source_kind="synthetic.note",
            source_ref="synthetic:1",
            content="a note",
            provenance_source=ProvenanceSource.TOOL_OBSERVATION,
            egress_origin_class="memory",
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id="batch-1",
        )
        with self.assertRaises(Exception):
            fact.content = "mutated"

    def test_outcome_is_content_free(self):
        outcome = IntakeOutcome(
            status="refused",
            source_ref="synthetic:1",
            reason="unknown_origin_class",
        )
        self.assertEqual(
            set(vars(outcome).keys()),
            {"status", "source_ref", "reason"},
        )


if __name__ == "__main__":
    unittest.main()
