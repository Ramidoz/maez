from __future__ import annotations

import unittest

from scripts.recall_quality_shadow_review import (
    parse_context_floor_candidate,
    parse_context_floor_shadow,
    summarize_context_floor_rows,
)


class ContextFloorParserTests(unittest.TestCase):
    def test_parse_context_floor_candidate_numeric_floor(self):
        line = (
            "recall_context_floor_candidate tier=daily id=daily-2026 kind=self_digest "
            "distance=0.7400 applied_floor=0.7200 base_floor=0.7800 casual_floor=0.7200 "
            "would_drop=True query_memory_ask=False retained=False preview=Daily system state"
        )

        row = parse_context_floor_candidate(line)

        self.assertEqual(row["tier"], "daily")
        self.assertEqual(row["kind"], "self_digest")
        self.assertEqual(row["distance"], 0.74)
        self.assertEqual(row["applied_floor"], 0.72)
        self.assertEqual(row["base_floor"], 0.78)
        self.assertEqual(row["casual_floor"], 0.72)
        self.assertTrue(row["would_drop"])
        self.assertFalse(row["query_memory_ask"])
        self.assertFalse(row["retained"])
        self.assertEqual(row["preview"], "Daily system state")

    def test_parse_context_floor_candidate_pass_through_floor(self):
        line = (
            "recall_context_floor_candidate tier=core id=core-high kind=unknown "
            "distance=0.9500 applied_floor=pass base_floor=0.7800 casual_floor=0.7200 "
            "would_drop=False query_memory_ask=False retained=True preview=Core pass-through row"
        )

        row = parse_context_floor_candidate(line)

        self.assertIsNone(row["applied_floor"])
        self.assertFalse(row["query_memory_ask"])
        self.assertTrue(row["retained"])
        self.assertEqual(row["preview"], "Core pass-through row")

    def test_parse_context_floor_shadow(self):
        line = (
            "recall_context_floor_shadow base_floor=0.7800 casual_floor=0.7200 "
            "query_memory_ask=False candidate_count=4 would_drop=2 "
            "fallback_rescue_kind=best_by_distance fallback_rescue_id=daily-best "
            "actuated=False"
        )

        row = parse_context_floor_shadow(line)

        self.assertEqual(row["candidate_count"], 4)
        self.assertEqual(row["would_drop"], 2)
        self.assertEqual(row["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(row["fallback_rescue_id"], "daily-best")
        self.assertFalse(row["actuated"])


class ContextFloorSummaryTests(unittest.TestCase):
    def test_summary_reports_raw_daily_relational_starvation_core_pass_through_and_memory_ask_tightening(self):
        rows = [
            {
                "kind": "telegram_exchange",
                "tier": "daily",
                "preview": "relational raw/daily sample",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
                "applied_floor": 0.72,
                "base_floor": 0.78,
            },
            {
                "kind": "self_digest",
                "tier": "daily",
                "preview": "daily journal sample",
                "query_memory_ask": False,
                "would_drop": True,
                "retained": False,
                "applied_floor": 0.72,
                "base_floor": 0.78,
            },
            {
                "kind": "unknown",
                "tier": "core",
                "preview": "core anchor pass-through sample",
                "query_memory_ask": False,
                "would_drop": False,
                "retained": True,
                "applied_floor": None,
                "base_floor": 0.78,
            },
            {
                "kind": "self_digest",
                "tier": "daily",
                "preview": "memory ask sample",
                "query_memory_ask": True,
                "would_drop": False,
                "retained": True,
                "applied_floor": 0.78,
                "base_floor": 0.78,
            },
        ]

        summary = summarize_context_floor_rows(rows)

        self.assertEqual(summary["casual_drop_count"], 2)
        self.assertEqual(summary["casual_drop_by_kind"]["telegram_exchange"], 1)
        self.assertEqual(summary["casual_drop_by_kind"]["self_digest"], 1)
        self.assertEqual(summary["casual_relational_tightened_count"], 1)
        self.assertEqual(summary["core_candidate_count"], 1)
        self.assertEqual(summary["core_drop_count"], 0)
        self.assertEqual(summary["core_pass_through_count"], 1)
        self.assertEqual(
            summary["sample_core_pass_through"][0]["preview"],
            "core anchor pass-through sample",
        )
        self.assertEqual(summary["memory_ask_tightened_count"], 0)
        self.assertEqual(summary["memory_ask_kept_count"], 1)
