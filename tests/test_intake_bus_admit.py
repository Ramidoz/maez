# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Intake Bus v0 — the admission doorway and its synthetic rider."""

from __future__ import annotations

import unittest

from core.intake_bus.admit import admit
from core.intake_bus.contract import (
    IntakeFact,
    IntakeOutcome,
    PromotionPosture,
    StoreAdapter,  # noqa: F401 - documents the fake adapter's contract
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


class _FakeMemory:
    def __init__(self, existing=None, raise_on_lookup=False):
        self.stored = []
        self._existing = dict(existing or {})
        self._raise_on_lookup = raise_on_lookup

    def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
        if self._raise_on_lookup:
            raise RuntimeError("backend down")
        return self._existing.get((source_ref, egress_origin_class))

    def store(
        self,
        content,
        cycle,
        snapshot=None,
        metadata=None,
        *,
        provenance_source=None,
        trust_tier=None,
        egress_origin_class=None,
    ):
        body_id = f"body-{len(self.stored) + 1}"
        self.stored.append({
            "content": content,
            "cycle": cycle,
            "snapshot": snapshot,
            "metadata": dict(metadata or {}),
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "egress_origin_class": egress_origin_class,
        })
        return body_id


class _FakeLimbStoreAdapter:
    def __init__(self, fact):
        self._fact = fact
        self.admitted = []

    def oldest_pending(self):
        return self._fact

    def mark_admitted(self, source_ref, *, body_memory_id):
        self.admitted.append((source_ref, body_memory_id))


def _synthetic_fact(**overrides):
    base = dict(
        source_kind="synthetic.note",
        source_ref="synthetic:1",
        content="a synthetic note for the owner",
        provenance_source=ProvenanceSource.TOOL_OBSERVATION,
        egress_origin_class="memory",
        promotion_posture=PromotionPosture.ADMIT_TO_BODY,
        fetch_batch_id="batch-1",
    )
    base.update(overrides)
    return IntakeFact(**base)


class AdmitDoorwayTests(unittest.TestCase):
    def test_admits_a_non_owner_fact_with_taint_and_content_blind(self):
        fact = _synthetic_fact()
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)

        outcome = admit(adapter, memory)

        self.assertEqual(outcome.status, "admitted")
        self.assertEqual(len(memory.stored), 1)
        row = memory.stored[0]
        self.assertEqual(row["content"], "a synthetic note for the owner")
        self.assertEqual(row["egress_origin_class"], "memory")
        self.assertEqual(row["provenance_source"], ProvenanceSource.TOOL_OBSERVATION)
        self.assertIsNone(row["trust_tier"])
        self.assertEqual(row["metadata"]["source_ref"], "synthetic:1")
        self.assertEqual(row["metadata"]["fetch_batch_id"], "batch-1")
        self.assertEqual(adapter.admitted, [("synthetic:1", "body-1")])

    def test_idempotent_already_admitted_no_second_write(self):
        fact = _synthetic_fact()
        memory = _FakeMemory(existing={("synthetic:1", "memory"): "pre-existing-id"})
        adapter = _FakeLimbStoreAdapter(fact)

        outcome = admit(adapter, memory)

        self.assertEqual(outcome.status, "already_admitted")
        self.assertEqual(memory.stored, [])
        self.assertEqual(adapter.admitted, [("synthetic:1", "pre-existing-id")])

    def test_stage_only_posture_does_not_write_body(self):
        fact = _synthetic_fact(promotion_posture=PromotionPosture.STAGE_ONLY)
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)

        outcome = admit(adapter, memory)

        self.assertEqual(outcome.status, "staged_not_admitted")
        self.assertEqual(memory.stored, [])
        self.assertEqual(adapter.admitted, [])

    def test_refused_on_unknown_origin_is_a_verdict_not_a_raise(self):
        fact = _synthetic_fact(egress_origin_class="totally_made_up")
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)

        outcome = admit(adapter, memory)

        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "unknown_origin_class")
        self.assertEqual(memory.stored, [])

    def test_refused_on_unclassified_origin(self):
        fact = _synthetic_fact(egress_origin_class="unclassified")

        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())

        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "unclassified_origin")

    def test_refused_on_missing_source_ref(self):
        fact = _synthetic_fact(source_ref="")

        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())

        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "missing_source_ref")

    def test_refused_on_empty_content(self):
        fact = _synthetic_fact(content="")

        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())

        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "missing_content")

    def test_substrate_uncertainty_raises_and_does_not_write(self):
        fact = _synthetic_fact()
        memory = _FakeMemory(raise_on_lookup=True)
        adapter = _FakeLimbStoreAdapter(fact)

        with self.assertRaises(RuntimeError):
            admit(adapter, memory)

        self.assertEqual(memory.stored, [])
        self.assertEqual(adapter.admitted, [])

    def test_nothing_pending_is_a_clean_noop(self):
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(None)

        outcome = admit(adapter, memory)

        self.assertEqual(outcome.status, "nothing_pending")
        self.assertEqual(memory.stored, [])


if __name__ == "__main__":
    unittest.main()
