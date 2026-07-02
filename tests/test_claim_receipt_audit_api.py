import os
import unittest
from unittest.mock import patch

from core.safety.self_claim_audit import audit


class ClaimReceiptAuditApi(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
