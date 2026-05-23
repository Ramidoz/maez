from __future__ import annotations

import unittest


class ModelOutputPolicyTests(unittest.TestCase):
    def test_model_output_has_own_conservative_bucket(self):
        from core.egress import gate

        self.assertIn("model_output", gate.UNTRUSTED_EXTERNAL_OUTPUT)
        self.assertNotIn("model_output", gate.NON_PRIVATE)
        self.assertNotIn("model_output", gate.MINIMIZABLE_PRIVATE_CONTEXT)
        self.assertEqual(gate.UNTRUSTED_EXTERNAL_OUTPUT, {"model_output"})
        self.assertIn("model_output", gate.KNOWN_ORIGINS)

    def test_model_output_redacts_if_reused_for_cloud_egress(self):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        decision = decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="subscription_proxy:claude",
                caller="test",
                request_id="model-output-reuse",
                segments=[
                    EgressSegment(
                        text="external model claim with rohit@example.com",
                        origin_class="model_output",
                        source_ref="claude_router:cloud_consult",
                        redaction_allowed=True,
                    )
                ],
            )
        )

        self.assertEqual(decision.decision, "redact")
        self.assertIn("minimized_untrusted_model_output", decision.reason_codes)
        self.assertNotIn("minimized_private_context", decision.reason_codes)
        self.assertNotIn("rohit@example.com", decision.sanitized_text())

    def test_model_output_factory_does_not_upgrade_to_public_or_memory(self):
        from core.egress.provenance import ProvenancedText

        text = ProvenancedText.model_output(
            "external model reasoning",
            source_ref="claude_router:cloud_consult",
        )

        self.assertEqual(text.spans[0].origin_class, "model_output")
        self.assertTrue(text.spans[0].redaction_allowed)

        reused = ProvenancedText.derived_output(
            "local synthesis using external reasoning",
            source=text,
            source_ref="local_maez:cloud_context",
        )
        self.assertEqual(reused.spans[0].origin_class, "model_output")


if __name__ == "__main__":
    unittest.main()
