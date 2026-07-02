from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class RecallQualityShadowReviewTests(unittest.TestCase):
    def test_parse_living_candidate_with_kind_and_type_weight(self):
        from scripts.recall_quality_shadow_review import parse_living_candidate

        line = (
            "INFO living_recall_candidate id=abc123 base_distance=0.4400 "
            "recency_factor=0.9900 effective_distance=0.4444 "
            "shadow_promotion=0.1200 kind=reflection type_weight=0.25"
        )
        parsed = parse_living_candidate(line)
        self.assertEqual(parsed["id"], "abc123")
        self.assertAlmostEqual(parsed["base_distance"], 0.44)
        self.assertAlmostEqual(parsed["shadow_promotion"], 0.12)
        self.assertEqual(parsed["kind"], "reflection")
        self.assertAlmostEqual(parsed["type_weight"], 0.25)

    def test_parse_floor_shadow_counts(self):
        from scripts.recall_quality_shadow_review import parse_floor_shadow

        line = (
            "INFO recall_floor_shadow floor=0.7800 raw_n=10 raw_would_drop=7 "
            "daily_n=3 daily_would_drop=1 would_empty=False actuated=False"
        )
        parsed = parse_floor_shadow(line)
        self.assertEqual(parsed["floor"], 0.78)
        self.assertEqual(parsed["raw_would_drop"], 7)
        self.assertFalse(parsed["would_empty"])

    def test_summarize_logs_computes_kind_shares_from_shadow_logs(self):
        from scripts.recall_quality_shadow_review import summarize_logs

        log = "\n".join([
            (
                "INFO living_recall_candidate id=a base_distance=0.9000 "
                "recency_factor=1.0000 effective_distance=0.9000 "
                "shadow_promotion=0.1000 kind=unknown type_weight=1.00"
            ),
            (
                "INFO living_recall_candidate id=b base_distance=0.3000 "
                "recency_factor=1.0000 effective_distance=0.3000 "
                "shadow_promotion=0.2000 kind=reflection type_weight=0.25"
            ),
            (
                "INFO recall_floor_shadow floor=0.7800 raw_n=2 raw_would_drop=1 "
                "daily_n=0 daily_would_drop=0 would_empty=False actuated=False"
            ),
        ])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "maez.log"
            path.write_text(log)
            summary = summarize_logs(path)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["kinded_candidate_count"], 2)
        self.assertAlmostEqual(summary["unknown_share"], 0.5)
        self.assertAlmostEqual(summary["reflection_share"], 0.5)
        self.assertEqual(summary["floor_receipt_count"], 1)

    def test_parse_reflection_bonus_shadow(self):
        from scripts.recall_quality_shadow_review import (
            parse_reflection_bonus_shadow,
        )

        line = (
            "reflection_bonus_shadow query_meta=True changed_ranking=True "
            "with_bonus_top=ep-reflection without_bonus_top=ep-direct "
            "candidate_count=2"
        )

        parsed = parse_reflection_bonus_shadow(line)

        self.assertTrue(parsed["query_meta"])
        self.assertTrue(parsed["changed_ranking"])
        self.assertEqual(parsed["with_bonus_top"], "ep-reflection")
        self.assertEqual(parsed["without_bonus_top"], "ep-direct")
        self.assertEqual(parsed["candidate_count"], 2)

    def test_summarize_reflection_bonus_rows(self):
        from scripts.recall_quality_shadow_review import (
            summarize_reflection_bonus_rows,
        )

        summary = summarize_reflection_bonus_rows([
            {"changed_ranking": True, "with_bonus_top": "a"},
            {"changed_ranking": False, "with_bonus_top": "b"},
        ])

        self.assertEqual(summary["telemetry_count"], 2)
        self.assertEqual(summary["changed_ranking_count"], 1)
        self.assertEqual(summary["review_status"], "review_required")

    def test_probe_query_defaults_are_used_only_when_args_empty(self):
        from scripts.recall_quality_shadow_review import (
            DEFAULT_PROBE_QUERIES,
            _probe_queries_from_args,
        )

        self.assertEqual(_probe_queries_from_args([]), list(DEFAULT_PROBE_QUERIES))
        self.assertEqual(_probe_queries_from_args(["custom"]), ["custom"])

    def test_main_uses_default_probe_queries_without_opening_memory_manager(self):
        from scripts import recall_quality_shadow_review as review

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "review.md"
            with mock.patch.object(
                review,
                "probe_live_candidate_kinds",
                return_value=[],
            ) as probe:
                with mock.patch.object(
                    review,
                    "probe_live_context_floor_rows",
                    return_value=[],
                ) as context_probe:
                    with mock.patch.object(
                        review,
                        "probe_live_reflection_bonus_rows",
                        return_value=[],
                    ) as reflection_probe:
                        rc = review.main([
                            "--log",
                            str(Path(td) / "missing.log"),
                            "--out",
                            str(out),
                        ])

            self.assertEqual(rc, 0)
            probe.assert_called_once_with(list(review.DEFAULT_PROBE_QUERIES))
            context_probe.assert_called_once_with(list(review.DEFAULT_PROBE_QUERIES))
            reflection_probe.assert_called_once_with(
                list(review.DEFAULT_PROBE_QUERIES)
            )
            self.assertIn("## Live Probe Summary", out.read_text())

    def test_main_uses_custom_probe_queries_without_opening_memory_manager(self):
        from scripts import recall_quality_shadow_review as review

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "review.md"
            with mock.patch.object(
                review,
                "probe_live_candidate_kinds",
                return_value=[],
            ) as probe:
                with mock.patch.object(
                    review,
                    "probe_live_context_floor_rows",
                    return_value=[],
                ) as context_probe:
                    with mock.patch.object(
                        review,
                        "probe_live_reflection_bonus_rows",
                        return_value=[],
                    ) as reflection_probe:
                        rc = review.main([
                            "--log",
                            str(Path(td) / "missing.log"),
                            "--probe-query",
                            "custom",
                            "--out",
                            str(out),
                        ])

            self.assertEqual(rc, 0)
            probe.assert_called_once_with(["custom"])
            context_probe.assert_called_once_with(["custom"])
            reflection_probe.assert_called_once_with(["custom"])

    def test_write_markdown_includes_live_probe_summary(self):
        from scripts.recall_quality_shadow_review import (
            summarize_context_floor_rows,
            summarize_reflection_bonus_rows,
            summarize_replay_rows,
            write_markdown,
        )

        rows = [
            {
                "id": "r1",
                "distance": 0.90,
                "kind": "reflection",
                "would_drop": True,
                "preview": "self-reflection candidate preview",
            },
            {
                "id": "r2",
                "distance": 0.30,
                "kind": "telegram_exchange",
                "would_drop": False,
            },
            {"id": "r3", "distance": 0.82, "kind": "unknown", "would_drop": True},
        ]
        summary = summarize_replay_rows(rows)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "review.md"
            write_markdown(
                out,
                log_summary={"candidate_count": 2},
                live_probe_summary=summary,
                context_floor_summary=summarize_context_floor_rows([]),
                reflection_bonus_summary=summarize_reflection_bonus_rows([]),
                replay_jsonl_summary=summarize_replay_rows([]),
            )
            text = out.read_text()
        self.assertIn("## Live Probe Summary", text)
        self.assertIn("## Context Floor Summary", text)
        self.assertIn("## Reflection Bonus Summary", text)
        self.assertIn("## Replay JSONL Summary", text)
        self.assertIn("unknown_share", text)
        self.assertIn("reflection_drop_share", text)
        self.assertIn("review_status", text)
        self.assertIn("self-reflection candidate preview", text)
        self.assertLess(
            text.index("## Live Probe Summary"),
            text.index('"unknown_share": 0.3333333333333333'),
        )

    def test_probe_live_candidate_kinds_accepts_injected_manager(self):
        from scripts.recall_quality_shadow_review import probe_live_candidate_kinds

        class FakeManager:
            def recall_for_telegram_living(self, query, *, record_recalls=True):
                self.record_recalls = record_recalls
                evidence = {"daily": [], "raw": []}
                context = {
                    "daily": [],
                    "raw": [{
                        "id": "reflection-row",
                        "content": "  Reflection content\nwith extra   spacing  ",
                        "distance": 0.90,
                        "metadata": {"source_kind": "reflection"},
                    }],
                }
                return evidence, context

        manager = FakeManager()
        rows = probe_live_candidate_kinds(["how are you"], manager=manager)
        self.assertFalse(manager.record_recalls)
        self.assertEqual(rows[0]["source"], "live_probe")
        self.assertEqual(rows[0]["query"], "how are you")
        self.assertEqual(rows[0]["partition"], "context")
        self.assertEqual(rows[0]["tier"], "raw")
        self.assertEqual(rows[0]["id"], "reflection-row")
        self.assertEqual(rows[0]["kind"], "reflection")
        self.assertEqual(rows[0]["preview"], "Reflection content with extra spacing")
        self.assertTrue(rows[0]["would_drop"])
