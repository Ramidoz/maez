import os
import unittest

from core.routing.memory_fresh_conflict import (
    MemoryFreshConflictReceipt,
    memory_fresh_conflict_sense_enabled,
)


class TestReceiptAndFlag(unittest.TestCase):
    def test_receipt_has_only_content_light_fields(self):
        r = MemoryFreshConflictReceipt(
            verdict="contradiction", mem_id="E2", mem_label="memory_evidence",
            fresh_id="E1", fresh_label="web_context", confidence=0.91,
            verifier="LocalNLIContradictionVerifier@rev1", mem_sha256="a" * 64,
            fresh_sha256="b" * 64, reason_code="trusted_clash",
        )
        forbidden = {"text", "mem_text", "fresh_text", "claim_text", "sense_note", "claim_details"}
        self.assertEqual(forbidden & set(vars(r)), set())
        self.assertEqual(r.verdict, "contradiction")

    def test_flag_off_by_default(self):
        self.assertFalse(memory_fresh_conflict_sense_enabled(env={}))

    def test_flag_on_when_set(self):
        self.assertTrue(
            memory_fresh_conflict_sense_enabled(env={"MAEZ_MEM_FRESH_CONFLICT_SENSE": "1"})
        )


if __name__ == "__main__":
    unittest.main()
