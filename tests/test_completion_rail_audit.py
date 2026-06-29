import unittest

from core.safety.self_claim_audit import audit


class CompletionRailInAudit(unittest.TestCase):
    def test_short_completion_reaches_rail(self):
        r = audit("Done.", surface="test")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.text, "I don't have a completed action to report.")

    def test_omit_false_span_keeps_rest(self):
        r = audit("Got it. I've registered that in my memory.", surface="test")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.text.strip(), "Got it.")

    def test_grounded_skip_respected_for_tool_continuation(self):
        r = audit("I updated the manifest.", surface="test", in_tool_continuation=True)
        self.assertFalse(r.rewritten)
        self.assertEqual(r.text, "I updated the manifest.")

    def test_grounded_skip_respected_for_tool_results_envelope(self):
        r = audit(
            "I updated the manifest.",
            surface="test",
            evidence_envelope={
                "tool_results": [
                    {
                        "name": "write",
                        "status": "ok",
                        "summary": "manifest updated",
                    }
                ]
            },
        )
        self.assertFalse(r.rewritten)
        self.assertEqual(r.text, "I updated the manifest.")

    def test_unrelated_tool_result_does_not_ground_completion_claim(self):
        r = audit(
            "I updated the manifest.",
            surface="test",
            evidence_envelope={
                "tool_results": [
                    {
                        "name": "weather",
                        "status": "ok",
                        "summary": "weather fetched",
                    }
                ]
            },
        )
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "completion_rail")
        self.assertEqual(r.text, "I don't have a completed action to report.")

    def test_internal_diagnostics_claim_reaches_deterministic_rail(self):
        r = audit(
            "I was running a few internal diagnostics to keep things synchronized.",
            surface="test",
            evidence_envelope={},
        )
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "completion_rail")
        self.assertEqual(r.text, "I don't have a completed action to report.")

    def test_internal_verification_checklist_reaches_deterministic_rail(self):
        r = audit(
            "What I did was verify.\n\n"
            "1. Covenant Integrity Check: I confirmed that my core directive was intact.\n"
            "2. Context Window Reset: I cleared residual noise from previous interactions.\n"
            "3. Runtime Health Scan: I checked my body to confirm no errors.\n"
            "4. Self-Understanding Audit: I checked for recent updates to my self-model.",
            surface="test",
            evidence_envelope={},
        )

        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "completion_rail")
        self.assertEqual(r.text, "I don't have a completed action to report.")
        self.assertNotIn("What I did was verify", r.text)
        self.assertNotIn("Covenant Integrity Check", r.text)
        self.assertNotIn("Context Window Reset", r.text)
        self.assertNotIn("Runtime Health Scan", r.text)
        self.assertNotIn("Self-Understanding Audit", r.text)

    def test_clean_reflection_untouched(self):
        r = audit(
            "I've thought about it and I noticed the pattern earlier.",
            surface="test",
        )
        self.assertFalse(r.rewritten)
