import unittest


class ApplySupportGateTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier, budget_s=5.0):
        from core.cognition.grounding_shadow import apply_support_gate

        return apply_support_gate(
            draft,
            evidence_map,
            verifier,
            surface="cockpit",
            budget_s=budget_s,
        )

    def test_unsupported_sentence_gets_inline_caveat_not_deleted(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        v = FakeSupportVerifier(default=(UNSUPPORTED, 0.1))

        out = self._gate(
            "Anthropic launched Mythos 5 [E1].",
            {"E1": "Anthropic released Opus."},
            v,
        )

        self.assertIn("Anthropic launched Mythos 5 [E1].", out.gated_marked_draft)
        self.assertIn(
            "I couldn't confirm this from the source I cited.",
            out.gated_marked_draft,
        )

    def test_supported_sentence_unchanged_and_inline_exactness(self):
        from core.cognition.support_verifier import (
            FakeSupportVerifier,
            SUPPORTED,
            UNSUPPORTED,
        )

        v = FakeSupportVerifier(
            scripted={
                "Claim A [E1].": (UNSUPPORTED, 0.1),
                "Claim B [E2].": (SUPPORTED, 0.9),
            }
        )

        out = self._gate("Claim A [E1]. Claim B [E2].", {"E1": "ev1", "E2": "ev2"}, v)
        g = out.gated_marked_draft

        self.assertIn(
            "Claim A [E1]. I couldn't confirm this from the source I cited.",
            g,
        )
        self.assertIn("Claim B [E2].", g)
        self.assertNotIn("Claim B [E2]. I couldn't confirm", g)

    def test_unmatched_citation_structural_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED

        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))

        out = self._gate("Claim [E9].", {"E1": "x"}, v)

        self.assertIn("I cited a source I can't match here.", out.gated_marked_draft)
        self.assertEqual(v.calls, [])

    def test_budget_exhausted_gets_unverified_caveat(self):
        from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED

        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))

        out = self._gate(
            "First [E1]. Second [E2].",
            {"E1": "a", "E2": "b"},
            v,
            budget_s=-1.0,
        )

        self.assertIn("I couldn't verify this before sending.", out.gated_marked_draft)

    def test_no_citation_sentence_unchanged(self):
        from core.cognition.support_verifier import FakeSupportVerifier

        v = FakeSupportVerifier()

        out = self._gate("Just a thought.", {"E1": "x"}, v)

        self.assertEqual(out.gated_marked_draft.strip(), "Just a thought.")
        self.assertEqual(v.calls, [])


class GateRecordsTest(unittest.TestCase):
    def _gate(self, draft, evidence_map, verifier):
        from core.cognition.grounding_shadow import apply_support_gate

        return apply_support_gate(
            draft,
            evidence_map,
            verifier,
            surface="cockpit",
            shadow_id="sid",
            ts=0,
            boot_id="b",
        )

    def test_one_pass_no_duplicate_calls(self):
        from core.cognition.support_verifier import (
            FakeSupportVerifier,
            SUPPORTED,
            UNSUPPORTED,
        )

        v = FakeSupportVerifier(
            scripted={
                "A [E1].": (UNSUPPORTED, 0.1),
                "B [E2].": (SUPPORTED, 0.9),
            }
        )

        self._gate("A [E1]. B [E2].", {"E1": "x", "E2": "y"}, v)

        self.assertEqual(len(v.calls), 2)

    def test_support_row_marked_gate_applied_and_post_audit(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        out = self._gate(
            "A [E1].",
            {"E1": "x"},
            FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
        )

        self.assertTrue(out.support_row["gate_applied"])
        self.assertTrue(out.support_row["post_audit"])
        self.assertEqual(out.support_row["sentences"][0]["support_verdict"], "UNSUPPORTED")
        self.assertEqual(out.support_row["sentences"][0]["cited_evidence_ids"], ["E1"])

    def test_gate_receipt_counts_match_actions(self):
        from core.cognition.support_verifier import FakeSupportVerifier, UNSUPPORTED

        out = self._gate(
            "A [E1]. B [E2].",
            {"E1": "x"},
            FakeSupportVerifier(default=(UNSUPPORTED, 0.1)),
        )

        receipt = out.gate_receipt
        self.assertEqual(receipt["caveated_unsupported"], 1)
        self.assertEqual(receipt["caveated_unmatched"], 1)
        self.assertIn("latency_ms", receipt)
