from __future__ import annotations

import unittest

from scripts.recall_quality_shadow_review import (
    parse_type_floor_candidate,
    parse_type_floor_shadow,
    summarize_type_floor_rows,
)


class TypeFloorParserTests(unittest.TestCase):
    def test_parse_type_floor_candidate(self):
        line = (
            "recall_type_floor_candidate tier=daily id=daily-2026 kind=self_digest "
            "distance=0.7400 applied_floor=0.7200 would_drop=True "
            "query_memory_ask=False retained=False"
        )

        row = parse_type_floor_candidate(line)

        self.assertEqual(row["tier"], "daily")
        self.assertEqual(row["kind"], "self_digest")
        self.assertEqual(row["distance"], 0.74)
        self.assertEqual(row["applied_floor"], 0.72)
        self.assertTrue(row["would_drop"])
        self.assertFalse(row["query_memory_ask"])
        self.assertFalse(row["retained"])

    def test_parse_type_floor_shadow(self):
        line = (
            "recall_type_floor_shadow base_floor=0.7800 self_digest_floor=0.7200 "
            "query_memory_ask=False candidate_count=4 would_drop=2 "
            "dropped_self_digest=2 fallback_rescue_kind=None actuated=False"
        )

        row = parse_type_floor_shadow(line)

        self.assertEqual(row["candidate_count"], 4)
        self.assertEqual(row["dropped_self_digest"], 2)
        self.assertIsNone(row["fallback_rescue_kind"])
        self.assertFalse(row["actuated"])


class TypeFloorSummaryTests(unittest.TestCase):
    def test_summary_reports_both_crux_directions(self):
        rows = [
            {
                "kind": "self_digest",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
            },
            {
                "kind": "self_digest",
                "query_memory_ask": True,
                "would_drop": False,
                "retained": True,
            },
            {
                "kind": "telegram_exchange",
                "query_memory_ask": False,
                "would_drop": False,
                "retained": True,
            },
        ]

        summary = summarize_type_floor_rows(rows)

        self.assertEqual(summary["casual_self_digest_drop_count"], 1)
        self.assertEqual(summary["casual_self_digest_resurrected_count"], 0)
        self.assertEqual(summary["memory_ask_self_digest_drop_count"], 0)
        self.assertEqual(summary["memory_ask_self_digest_kept_count"], 1)
        self.assertEqual(summary["review_status"], "review_required")


if __name__ == "__main__":
    unittest.main()
