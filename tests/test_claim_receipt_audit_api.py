import os
import time
import unittest
from unittest.mock import patch

from core.safety.self_claim_audit import audit


class ClaimReceiptAuditApi(unittest.TestCase):
    def _fresh_screen_envelope(self):
        return {
            "claimable": [
                {
                    "kind": "screen_observation",
                    "state": "ok",
                    "observed_at": time.time() - 20,
                    "text": "[SCREEN - one unvalidated glance, 20s ago]\n  Looked like: Browsing",
                }
            ],
            "tool_results": [],
        }

    def test_flag_off_is_byte_identical(self):
        text = "(Initiating live search for recent UAP developments...)"
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "0",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ):
            result = audit(text, surface="test", evidence_envelope={"tool_results": []})

        self.assertFalse(result.rewritten)
        self.assertEqual(result.text, text)
        self.assertIsNone(result.action_mismatch)

    def test_shadow_returns_structured_mismatch_without_rewriting(self):
        text = "(Initiating live search for recent UAP developments...)"
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ):
            result = audit(text, surface="test", evidence_envelope={"tool_results": []})

        self.assertFalse(result.rewritten)
        self.assertEqual(result.text, text)
        self.assertEqual(result.mode, "action_claim_mismatch")
        self.assertIsNotNone(result.action_mismatch)
        self.assertEqual(result.action_mismatch.action_type, "web_search")
        self.assertEqual(result.action_mismatch.receipt_present, False)
        self.assertNotIn("I don't have a completed action", result.text)

    def test_matching_receipt_no_mismatch(self):
        text = "Here is what I found from the live web search."
        envelope = {
            "tool_results": [
                {
                    "name": "web_search",
                    "tool": "web_search",
                    "action_type": "web_search",
                    "status": "ok",
                    "summary": "web_search ok result_count=2",
                },
            ],
        }
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ):
            result = audit(text, surface="test", evidence_envelope=envelope)

        self.assertFalse(result.rewritten)
        self.assertIsNone(result.action_mismatch)
        self.assertEqual(result.text, text)

    def test_perception_claim_without_observation_logs_shadow_mismatch(self):
        text = (
            "I see the dark background of the terminal/chat window, the text of "
            "our recent exchange, and the cursor blinking at the end of my previous response."
        )
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ), self.assertLogs("maez.self_claim_audit", level="INFO") as logs:
            result = audit(text, surface="telegram_surface", evidence_envelope={"claimable": []})

        self.assertFalse(result.rewritten)
        self.assertEqual(result.mode, "action_claim_mismatch")
        self.assertIsNotNone(result.action_mismatch)
        self.assertEqual(result.action_mismatch.action_type, "screen_perception")
        self.assertEqual(result.action_mismatch.receipt_present, False)
        self.assertIn("action_type=screen_perception", "\n".join(logs.output))
        self.assertIn("mode=shadow", "\n".join(logs.output))

    def test_perception_claim_with_fresh_observation_has_no_mismatch(self):
        text = "I see you're browsing."
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ):
            result = audit(
                text,
                surface="telegram_surface",
                evidence_envelope=self._fresh_screen_envelope(),
            )

        self.assertFalse(result.rewritten)
        self.assertIsNone(result.action_mismatch)
        self.assertEqual(result.text, text)

    def test_metaphorical_seeing_is_not_a_claim_receipt_mismatch(self):
        text = "I see what you mean."
        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
                "MAEZ_SEMANTIC_AUDIT": "0",
            },
            clear=False,
        ):
            result = audit(text, surface="telegram_surface", evidence_envelope={"claimable": []})

        self.assertFalse(result.rewritten)
        self.assertIsNone(result.action_mismatch)
        self.assertEqual(result.text, text)


if __name__ == "__main__":
    unittest.main()
