import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import daemon.maez_daemon as md
from core.safety.self_claim_audit import ActionClaimMismatch


class DaemonClaimReceiptRedo(unittest.TestCase):
    def _mismatch(self):
        return ActionClaimMismatch(
            action_type="web_search",
            pattern_id="search_initiating",
            claim_text="Initiating live search",
            receipt_present=False,
            tense_class="present_progressive",
            reason="claims a this-turn search/action with no type-matched receipt",
        )

    def test_floor_notice_is_substrate_labeled_and_content_light(self):
        text = md._claim_receipt_floor_notice(self._mismatch())
        self.assertIn("Substrate notice:", text)
        self.assertIn("unreceipted action claim", text)
        self.assertNotIn("Initiating live search", text)
        self.assertNotIn("UAP", text)

    def test_redo_messages_include_facts_not_script(self):
        messages = [
            {"role": "system", "content": "base"},
            {"role": "user", "content": "search?"},
        ]
        redo = md._claim_receipt_redo_messages(
            messages,
            mismatch=self._mismatch(),
            owner_text="you can search if you need to",
        )

        self.assertEqual(redo[:-1], messages)
        content = redo[-1]["content"]
        self.assertIn("No web_search receipt exists for this turn", content)
        self.assertIn("Search tools are live", content)
        self.assertIn("Answer in your own words", content)
        self.assertNotIn("Say:", content)
        self.assertNotIn("Sorry", content)

    def test_audit_helper_requests_redo_only_when_enforce_enabled(self):
        mismatch = self._mismatch()
        fake_result = SimpleNamespace(
            text="(Initiating live search...)",
            rewritten=False,
            mode="action_claim_mismatch",
            action_mismatch=mismatch,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "0",
            },
            clear=False,
        ), patch("core.self_claim_audit.audit", return_value=fake_result) as audit:
            out = md._audit_daemon_reply_for_claim_receipts(
                "(Initiating live search...)",
                surface="telegram_surface",
                evidence_envelope={"tool_results": []},
            )
        self.assertFalse(out.needs_redo)
        self.assertEqual(out.text, "(Initiating live search...)")
        audit.assert_not_called()

        with patch.dict(
            os.environ,
            {
                "MAEZ_CLAIM_RECEIPT_SHADOW": "1",
                "MAEZ_CLAIM_RECEIPT_ENFORCE": "1",
            },
            clear=False,
        ), patch("core.self_claim_audit.audit", return_value=fake_result):
            out = md._audit_daemon_reply_for_claim_receipts(
                "(Initiating live search...)",
                surface="telegram_surface",
                evidence_envelope={"tool_results": []},
            )
        self.assertTrue(out.needs_redo)
        self.assertIs(out.action_mismatch, mismatch)


if __name__ == "__main__":
    unittest.main()
