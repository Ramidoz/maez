import unittest

from scripts.claim_receipt_shadow_review import parse_lines, summarize, write_markdown


class ClaimReceiptShadowReview(unittest.TestCase):
    def test_parse_and_summarize_content_light_receipts(self):
        lines = [
            "2026-07-01 claim_receipt_rail surface=telegram_text action_type=web_search "
            "pattern_id=search_initiating receipt_present=False tense_class=present_progressive "
            "mode=shadow redo_outcome=none",
            "2026-07-01 claim_receipt_rail surface=telegram_text action_type=web_search "
            "pattern_id=past_excluded receipt_present=False tense_class=past "
            "mode=shadow redo_outcome=excluded",
        ]

        events = parse_lines(lines)
        summary = summarize(events)

        self.assertEqual(summary["catch_count"], 1)
        self.assertEqual(summary["tense_exclusion_count"], 1)
        self.assertEqual(summary["pattern_counts"]["search_initiating"], 1)

    def test_markdown_contains_gate_sentences(self):
        md = write_markdown(
            summarize(
                parse_lines(
                    [
                        "claim_receipt_rail surface=telegram_text action_type=web_search "
                        "pattern_id=search_initiating receipt_present=False "
                        "tense_class=present_progressive mode=shadow redo_outcome=none",
                    ],
                ),
            ),
            fabricated_probe_caught=True,
            honest_1745_probe_clean=True,
        )

        self.assertIn("fabricated turn MUST catch: PASS", md)
        self.assertIn("receipted 17:45 turn MUST NOT catch: PASS", md)
        self.assertNotIn("Initiating live search", md)


if __name__ == "__main__":
    unittest.main()
