from __future__ import annotations

import math
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock


class RecencyFactorTests(unittest.TestCase):
    def test_gentle_half_life_decay(self):
        from memory.memory_manager import recency_factor

        self.assertEqual(recency_factor(0.0, half_life_days=90.0), 1.0)
        self.assertAlmostEqual(
            recency_factor(24.0, half_life_days=90.0),
            0.5 ** (1.0 / 90.0),
            places=6,
        )
        self.assertAlmostEqual(
            recency_factor(90.0 * 24.0, half_life_days=90.0),
            0.5,
            places=6,
        )
        self.assertGreater(
            recency_factor(24.0, half_life_days=90.0),
            recency_factor(30.0 * 24.0, half_life_days=90.0),
        )
        self.assertTrue(math.isfinite(recency_factor(365.0 * 24.0)))

    def test_negative_age_clamps_to_now(self):
        from memory.memory_manager import recency_factor

        self.assertEqual(recency_factor(-10.0, half_life_days=90.0), 1.0)


class _FakeCollection:
    def __init__(self, rows):
        self.rows = list(rows)

    def count(self):
        return len(self.rows)

    def query(self, query_texts, n_results):
        rows = self.rows[:n_results]
        return {
            "ids": [[r["id"] for r in rows]],
            "documents": [[r["content"] for r in rows]],
            "metadatas": [[r["metadata"] for r in rows]],
            "distances": [[r.get("distance") for r in rows]],
        }

    def get(self, where=None, include=None, limit=None):
        rows = self.rows
        if where:
            rows = [
                r for r in rows
                if all(r["metadata"].get(k) == v for k, v in where.items())
            ]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [r["id"] for r in rows],
            "documents": [r["content"] for r in rows],
            "metadatas": [r["metadata"] for r in rows],
        }


def _manager(*, raw_rows=None, daily_rows=None, core_rows=None):
    from memory.memory_manager import MemoryManager

    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection(raw_rows or [])
    mm.daily = _FakeCollection(daily_rows or [])
    mm.core = _FakeCollection(core_rows or [])
    mm.get_all_core = lambda: list(core_rows or [])
    return mm


def _row(row_id: str, *, content: str, days_ago: float, distance: float) -> dict:
    now = datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc)
    ts = now - timedelta(days=days_ago)
    return {
        "id": row_id,
        "content": content,
        "metadata": {"timestamp": ts.isoformat(), "type": "reasoning"},
        "distance": distance,
    }


def _partition_ids(partition: dict, tier: str) -> list[str]:
    return [row["id"] for row in partition.get(tier, [])]


def _partition_text(partition: dict) -> str:
    return " ".join(
        str(row.get("content", ""))
        for tier in ("raw", "daily", "core")
        for row in (partition.get(tier) or [])
    )


class LivingRecallRankingTests(unittest.TestCase):
    def test_query_echo_excluded_from_living_recall(self):
        query = "What did we note back about the infrastructure?"
        echo = _row(
            "echo-query",
            content=f"the owner (telegram_surface): {query}",
            days_ago=0,
            distance=0.01,
        )
        echo["metadata"]["type"] = "telegram_exchange"
        real_recent = _row(
            "real-recent",
            content="fresh living-memory implementation note",
            days_ago=1,
            distance=0.20,
        )
        mm = _manager(raw_rows=[echo, real_recent])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living(query)

        self.assertNotIn(query, _partition_text(evidence))
        self.assertNotIn(f"the owner (telegram_surface): {query}", _partition_text(evidence))
        self.assertNotIn(query, _partition_text(context))

    def test_old_repeat_question_is_not_treated_as_current_query_echo(self):
        query = "What did we note back about the infrastructure?"
        old_repeat = _row(
            "old-repeat",
            content=f"the owner (telegram_surface): {query}\nMaez: older answer from the archive",
            days_ago=30,
            distance=0.01,
        )
        old_repeat["metadata"]["type"] = "telegram_exchange"
        mm = _manager(raw_rows=[old_repeat])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living(query)

        self.assertNotIn("older answer from the archive", _partition_text(evidence))
        self.assertIn("older answer from the archive", _partition_text(context))

    def test_overfetch_surfaces_fresh_outside_age_blind_top20(self):
        stale_rows = [
            _row(
                f"stale-close-{i}",
                content=f"old meta note {i}",
                days_ago=120,
                distance=0.10 + (i * 0.001),
            )
            for i in range(25)
        ]
        fresh = _row(
            "fresh-outside-top20",
            content="fresh local AI discussion from today",
            days_ago=1,
            distance=0.18,
        )
        mm = _manager(raw_rows=stale_rows + [fresh])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("what have we discussed recently?")

        self.assertEqual(_partition_ids(evidence, "raw")[0], "fresh-outside-top20")
        self.assertIn("stale-close-0", _partition_ids(context, "raw"))

    def test_stale_strong_match_is_demoted_but_not_dropped(self):
        old_strong = _row(
            "old-strong",
            content="old but relevant architecture decision",
            days_ago=90,
            distance=0.35,
        )
        fresh_weaker = _row(
            "fresh-weaker",
            content="fresh nearby architecture note",
            days_ago=1,
            distance=0.40,
        )
        mm = _manager(raw_rows=[old_strong, fresh_weaker])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("architecture decision")

        self.assertIn("fresh-weaker", _partition_ids(evidence, "raw"))
        self.assertIn("old-strong", _partition_ids(context, "raw"))

    def test_partition_by_evidence_recency(self):
        fresh_daily = _row(
            "daily-fresh",
            content="fresh daily summary",
            days_ago=2,
            distance=0.20,
        )
        old_daily = _row(
            "daily-old",
            content="old daily summary",
            days_ago=40,
            distance=0.10,
        )
        fresh_raw = _row(
            "raw-fresh",
            content="fresh raw memory",
            days_ago=7,
            distance=0.30,
        )
        old_raw = _row(
            "raw-old",
            content="old raw memory",
            days_ago=30,
            distance=0.10,
        )
        mm = _manager(raw_rows=[old_raw, fresh_raw], daily_rows=[old_daily, fresh_daily])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("what is recent?")

        self.assertEqual(set(_partition_ids(evidence, "daily")), {"daily-fresh"})
        self.assertEqual(set(_partition_ids(evidence, "raw")), {"raw-fresh"})
        self.assertEqual(set(_partition_ids(context, "daily")), {"daily-old"})
        self.assertEqual(set(_partition_ids(context, "raw")), {"raw-old"})

    def test_core_memories_are_context_never_evidence(self):
        core = [{"id": "core-maez", "content": "I am Maez.", "metadata": {}}]
        mm = _manager(
            raw_rows=[
                _row("raw-fresh", content="fresh raw memory", days_ago=1, distance=0.20)
            ],
            core_rows=core,
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("who are you?")

        self.assertEqual(evidence["core"], [])
        self.assertEqual(_partition_ids(context, "core"), ["core-maez"])
        self.assertEqual(context["core"][0]["content"], "I am Maez.")

    def test_relevant_core_selected_into_context(self):
        april_core = {
            "id": "core-april-6",
            "content": "[Journal 2026-04-06] infrastructure ground-truth for the daemon witness.",
            "metadata": {},
            "distance": 0.02,
        }
        irrelevant_core = [
            {
                "id": f"core-irrelevant-{i}",
                "content": f"unrelated core identity note {i}",
                "metadata": {},
                "distance": 0.50 + (i * 0.01),
            }
            for i in range(8)
        ]
        mm = _manager(core_rows=[april_core, *irrelevant_core])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living(
                "What did we note back around April 6 about the infrastructure?"
            )

        self.assertIn("2026-04-06", _partition_text(context))
        self.assertLessEqual(len(context.get("core") or []), 5)
        self.assertNotIn("2026-04-06", _partition_text(evidence))

    def test_present_ask_keeps_old_core_out_of_evidence(self):
        april_core = {
            "id": "core-april-6",
            "content": "[Journal 2026-04-06] infrastructure ground-truth for the daemon witness.",
            "metadata": {},
            "distance": 0.02,
        }
        mm = _manager(core_rows=[april_core])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("How are you doing right now?")

        self.assertNotIn("2026-04-06", _partition_text(evidence))

    def test_missing_or_invalid_timestamps_are_context_never_evidence(self):
        missing_ts = _row(
            "raw-missing-ts",
            content="timestamp missing",
            days_ago=1,
            distance=0.20,
        )
        missing_ts["metadata"].pop("timestamp")
        invalid_ts = _row(
            "raw-invalid-ts",
            content="timestamp invalid",
            days_ago=1,
            distance=0.21,
        )
        invalid_ts["metadata"]["timestamp"] = "not-a-timestamp"
        mm = _manager(raw_rows=[missing_ts, invalid_ts])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("timestamp honesty")

        self.assertEqual(_partition_ids(evidence, "raw"), [])
        self.assertEqual(
            set(_partition_ids(context, "raw")),
            {"raw-missing-ts", "raw-invalid-ts"},
        )


class ContinuityFacultyTests(unittest.TestCase):
    def test_direct_continuity_uses_recent_thread_as_evidence_not_old_meta(self):
        old_meta_rows = [
            _row(
                f"old-meta-{i}",
                content="the owner (telegram_surface): What happened?\nMaez: old meta-memory answer",
                days_ago=43,
                distance=0.01 + (i * 0.001),
            )
            for i in range(12)
        ]
        for row in old_meta_rows:
            row["metadata"]["type"] = "telegram_exchange"

        recent_thread = _row(
            "recent-thread",
            content=(
                "the owner (telegram_surface): We fixed role hints.\n"
                "Maez: The carrier now keeps evidence and context separate."
            ),
            days_ago=0.05,
            distance=0.90,
        )
        recent_thread["metadata"]["type"] = "telegram_exchange"
        mm = _manager(raw_rows=old_meta_rows + [recent_thread])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("What were we talking about earlier?")

        self.assertIn("recent-thread", _partition_ids(evidence, "raw"))
        self.assertFalse(set(_partition_ids(evidence, "raw")) & {f"old-meta-{i}" for i in range(12)})
        self.assertIn("old-meta-0", _partition_ids(context, "raw"))

    def test_continuity_anchor_requires_parseable_timestamp(self):
        invalid_thread = _row(
            "invalid-thread",
            content="the owner (telegram_surface): stale malformed row\nMaez: old answer",
            days_ago=0.01,
            distance=0.01,
        )
        invalid_thread["metadata"]["type"] = "telegram_exchange"
        invalid_thread["metadata"]["timestamp"] = "not-a-timestamp"
        valid_thread = _row(
            "valid-thread",
            content="the owner (telegram_surface): newest valid row\nMaez: current answer",
            days_ago=0.05,
            distance=0.90,
        )
        valid_thread["metadata"]["type"] = "telegram_exchange"
        mm = _manager(raw_rows=[invalid_thread, valid_thread])

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
        ):
            evidence, context = mm.recall_for_telegram_living("What were we talking about earlier?")

        self.assertEqual(_partition_ids(evidence, "raw"), ["valid-thread"])
        self.assertIn("invalid-thread", _partition_ids(context, "raw"))


class ShadowPromotionTests(unittest.TestCase):
    def test_promotion_score_is_logged_but_not_applied(self):
        rows = [
            _row("base-a", content="fresh candidate a", days_ago=1, distance=0.20),
            _row("base-b", content="fresh candidate b", days_ago=1, distance=0.21),
        ]

        def run_with(score_by_id):
            mm = _manager(raw_rows=rows)

            def fake_get_stats(memory_id):
                from core.memory_scoring import RecallStats

                return RecallStats(memory_id=memory_id)

            def fake_promotion(stats):
                return score_by_id[stats.memory_id]

            with (
                mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
                mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
                mock.patch("core.memory_scoring.get_stats", side_effect=fake_get_stats),
                mock.patch("core.memory_scoring.promotion_score", side_effect=fake_promotion),
                self.assertLogs("maez", level="INFO") as logs,
            ):
                evidence, context = mm.recall_for_telegram_living("fresh candidate")

            order = _partition_ids(evidence, "raw") + _partition_ids(context, "raw")
            return order, "\n".join(logs.output)

        order_a, logs_a = run_with({"base-a": 1.0, "base-b": 0.0})
        order_b, logs_b = run_with({"base-a": 0.0, "base-b": 1.0})

        self.assertEqual(order_a, ["base-a", "base-b"])
        self.assertEqual(order_b, ["base-a", "base-b"])
        self.assertIn("living_recall_candidate", logs_a)
        self.assertIn("shadow_promotion=1.0000", logs_a)
        self.assertIn("shadow_promotion=1.0000", logs_b)


class LivingRecallTelemetryTests(unittest.TestCase):
    def test_overfetch_does_not_record_unsurfaced_recall_stats(self):
        rows = [
            _row(
                f"stale-close-{i}",
                content=f"old unsurfaced note {i}",
                days_ago=120,
                distance=0.10 + (i * 0.001),
            )
            for i in range(25)
        ]
        fresh = _row(
            "fresh-winner",
            content="fresh topic",
            days_ago=1,
            distance=0.18,
        )
        mm = _manager(raw_rows=rows + [fresh])
        recorded: list[str] = []

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
            mock.patch("core.memory_scoring.record_recall", side_effect=lambda memory_id, **_: recorded.append(memory_id)),
        ):
            evidence, context = mm.recall_for_telegram_living("fresh topic")

        surfaced = set(_partition_ids(evidence, "raw") + _partition_ids(context, "raw"))
        self.assertLess(len(surfaced), 26)
        self.assertEqual(set(recorded), surfaced)


class FlagReaderTests(unittest.TestCase):
    def test_living_recall_flag_defaults_off(self):
        from core.brain.brain_loop import _living_recall_enabled

        os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
        self.assertFalse(_living_recall_enabled())

    def test_living_recall_flag_accepts_truthy_values(self):
        from core.brain.brain_loop import _living_recall_enabled

        for value in ("1", "true", "True"):
            os.environ["MAEZ_LIVING_RECALL_ENABLED"] = value
            try:
                self.assertTrue(_living_recall_enabled())
            finally:
                os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)


class AdapterRoleHintTests(unittest.TestCase):
    class _FakeMemory:
        def __init__(self):
            self.calls: list[str] = []
            self.recorded: list[str] = []

        def recall_for_telegram(self, query):
            self.calls.append(f"legacy:{query}")
            return {"core": [], "daily": [], "raw": [{"id": "legacy"}]}

        def recall_for_telegram_living(self, query, *, record_recalls=True):
            self.calls.append(f"living:{query}")
            evidence = (
                {"core": [], "daily": [], "raw": [{"id": "ev"}]},
            )
            context = (
                {"core": [], "daily": [], "raw": [{"id": "ctx"}]},
            )
            if record_recalls:
                self._record_living_recall(query, evidence[0], context[0])
            return evidence[0], context[0]

        def _record_living_recall(self, query, *partitions):
            for partition in partitions:
                for tier in ("daily", "raw"):
                    for row in partition.get(tier, []) or []:
                        self.recorded.append(row["id"])

        def format_for_prompt(self, recalled, max_chars=None):
            raw_ids = [row["id"] for row in recalled.get("raw", [])]
            if raw_ids == ["ev"]:
                return "evidence text"
            if raw_ids == ["ctx"]:
                return "context text"
            if raw_ids == ["legacy"]:
                return "legacy text"
            return ""

        def format_living_context(self, recalled, max_chars=None):
            return self.format_for_prompt(recalled, max_chars=max_chars)

    class _BudgetDroppingMemory(_FakeMemory):
        def recall_for_telegram_living(self, query, *, record_recalls=True):
            self.calls.append(f"living:{query}")
            evidence = {
                "core": [],
                "daily": [],
                "raw": [{"id": "ev-visible"}, {"id": "ev-hidden"}],
            }
            context = {"core": [], "daily": [], "raw": []}
            if record_recalls:
                self._record_living_recall(query, evidence, context)
            return evidence, context

        def format_for_prompt(self, recalled, max_chars=None):
            raw_ids = [row["id"] for row in recalled.get("raw", [])]
            if raw_ids == ["ev-visible", "ev-hidden"]:
                return '<RECALLED tier="raw" id="ev-visible">visible</RECALLED>'
            return super().format_for_prompt(recalled, max_chars=max_chars)

    class _AllDroppedPromptMemory(_FakeMemory):
        def recall_for_telegram_living(self, query, *, record_recalls=True):
            self.calls.append(f"living:{query}")
            evidence = {"core": [], "daily": [], "raw": [{"id": "ev-hidden"}]}
            context = {
                "core": [
                    {
                        "id": "core-april",
                        "content": "April infrastructure note",
                        "metadata": {},
                    }
                ],
                "daily": [],
                "raw": [],
            }
            if record_recalls:
                self._record_living_recall(query, evidence, context)
            return evidence, context

        def format_for_prompt(self, recalled, max_chars=None):
            raw_ids = [row["id"] for row in recalled.get("raw", [])]
            core_ids = [row["id"] for row in recalled.get("core", [])]
            if raw_ids == ["ev-hidden"]:
                return (
                    "=== PAST OBSERVATIONS — NOT CURRENT STATE ===\n"
                    "[1 additional raw memory entry truncated to fit prompt budget]"
                )
            if core_ids == ["core-april"]:
                return '<RECALLED tier="core" id="core-april">April infrastructure note</RECALLED>'
            return super().format_for_prompt(recalled, max_chars=max_chars)

    class _OverlongPromptMemory(_FakeMemory):
        def format_for_prompt(self, recalled, max_chars=None):
            raw_ids = [row["id"] for row in recalled.get("raw", [])]
            if raw_ids == ["ev"]:
                return '<RECALLED tier="raw" id="ev">' + ("E" * 2000) + "</RECALLED>"
            if raw_ids == ["ctx"]:
                return '<RECALLED tier="raw" id="ctx">' + ("C" * 2000) + "</RECALLED>"
            return super().format_for_prompt(recalled, max_chars=max_chars)

    class _ContinuityFallbackMemory(_FakeMemory):
        def recall_for_telegram_living(self, query, *, record_recalls=True):
            self.calls.append(f"living:{query}")
            evidence = {"core": [], "daily": [], "raw": [{"id": "old-health"}]}
            context = {"core": [], "daily": [], "raw": [{"id": "old-meta"}]}
            if record_recalls:
                self._record_living_recall(query, evidence, context)
            return evidence, context

        def format_for_prompt(self, recalled, max_chars=None):
            raw_ids = [row["id"] for row in recalled.get("raw", [])]
            if raw_ids == ["old-health"]:
                return "two-day health check"
            if raw_ids == ["old-meta"]:
                return "old meta-memory"
            return super().format_for_prompt(recalled, max_chars=max_chars)

    class _DeepContextMemory(_FakeMemory):
        def recall_for_telegram_living(self, query, *, record_recalls=True):
            self.calls.append(f"living:{query}")
            evidence = {"core": [], "daily": [], "raw": []}
            context = {
                "core": [
                    {
                        "id": "core-april",
                        "content": "April infrastructure note",
                        "metadata": {},
                    }
                ],
                "daily": [],
                "raw": [],
            }
            if record_recalls:
                self._record_living_recall(query, evidence, context)
            return evidence, context

        def format_for_prompt(self, recalled, max_chars=None):
            core_ids = [row["id"] for row in recalled.get("core", [])]
            if core_ids == ["core-april"]:
                return '<RECALLED tier="core" id="core-april">April infrastructure note</RECALLED>'
            return super().format_for_prompt(recalled, max_chars=max_chars)

    def test_flag_off_semantic_adapter_returns_single_none_hint_block(self):
        from core import brain_loop
        from core.dispatcher.spec import SubstrateSource

        fake = self._FakeMemory()
        os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
        with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
            blocks = brain_loop._dispatcher_recall_adapters("hello")[
                SubstrateSource.TELEGRAM_SEMANTIC
            ](SubstrateSource.TELEGRAM_SEMANTIC)

        self.assertEqual(fake.calls, ["legacy:hello"])
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0].role_hint)
        self.assertEqual(blocks[0].rationale, "recall_for_telegram")

    def test_flag_on_semantic_adapter_emits_evidence_then_context(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters("hello", surface="telegram")[
                    SubstrateSource.TELEGRAM_SEMANTIC
                ](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(fake.calls, ["living:hello"])
        self.assertEqual([block.role_hint for block in blocks], [
            SourceRole.SUBSTRATE_EVIDENCE,
            SourceRole.SUBSTRATE_CONTEXT,
        ])
        self.assertEqual([block.text for block in blocks], ["evidence text", "context text"])

    def test_flag_on_non_telegram_surface_stays_legacy(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters("hello", surface="web")[
                    SubstrateSource.TELEGRAM_SEMANTIC
                ](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(fake.calls, ["legacy:hello"])
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0].role_hint)
        self.assertNotIn(SourceRole.SUBSTRATE_EVIDENCE, [block.role_hint for block in blocks])

    def test_flag_on_temporal_adapter_emits_living_blocks(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters("last evening", surface="telegram")[
                    SubstrateSource.TELEGRAM_TEMPORAL
                ](SubstrateSource.TELEGRAM_TEMPORAL)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(fake.calls, ["living:last evening"])
        self.assertEqual([block.role_hint for block in blocks], [
            SourceRole.SUBSTRATE_EVIDENCE,
            SourceRole.SUBSTRATE_CONTEXT,
        ])

    def test_flag_on_hybrid_semantic_adapter_emits_context_only(self):
        from core import brain_loop
        from core.dispatcher.spec import (
            ExternalSource,
            ProvenanceFraming,
            SourceRole,
            SubstrateSource,
        )

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "fresh plus memory",
                    spec=_substrate_semantic_spec(
                        framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                        external_sources=[ExternalSource.WEB_SEARCH],
                    ),
                    surface="telegram",
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_CONTEXT])
        self.assertIn("evidence text", blocks[0].text)
        self.assertIn("context text", blocks[0].text)

    def test_flag_on_evidence_only_framing_does_not_relabel_context_as_evidence(self):
        from core import brain_loop
        from core.dispatcher.spec import (
            ProvenanceFraming,
            SourceRole,
            SubstrateSource,
        )

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "fresh validates memory",
                    spec=_substrate_semantic_spec(
                        framing=ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
                    ),
                    surface="telegram",
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_EVIDENCE])
        self.assertEqual(blocks[0].text, "evidence text")
        self.assertNotIn("context text", blocks[0].text)
        self.assertEqual(fake.recorded, ["ev"])

    def test_recording_tracks_rendered_rows_after_prompt_budget_drop(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._BudgetDroppingMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters("budgeted", surface="telegram")[
                    SubstrateSource.TELEGRAM_SEMANTIC
                ](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_EVIDENCE])
        self.assertIn("ev-visible", blocks[0].text)
        self.assertNotIn("ev-hidden", blocks[0].text)
        self.assertEqual(fake.recorded, ["ev-visible"])

    def test_recording_does_not_credit_all_dropped_real_prompt_rows(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._AllDroppedPromptMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "What did we note back around April 6 about the infrastructure?",
                    surface="telegram",
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_CONTEXT])
        self.assertEqual(fake.recorded, [])

    def test_layer1_budget_preserves_context_role_for_both_telegram_sources(self):
        from core import brain_loop
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SourceRole,
            SubstrateSource,
        )

        fake = self._OverlongPromptMemory()
        spec = CompositionSpec(
            substrate_sources=[
                SubstrateSource.TELEGRAM_TEMPORAL,
                SubstrateSource.TELEGRAM_SEMANTIC,
            ],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.PRESENT,
            source_availability={
                SubstrateSource.TELEGRAM_TEMPORAL: SourceAvailability.EXECUTABLE_PRESENT,
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                layer1 = Layer1Fanout(
                    adapters=brain_loop._dispatcher_recall_adapters(
                        "what have we discussed recently?",
                        spec=spec,
                        surface="telegram_surface",
                    ),
                    branch_timeout_s=1.0,
                    global_deadline_s=1.0,
                )
                result = layer1.run(
                    spec,
                    utterance="what have we discussed recently?",
                    conversation_state={},
                    fanout_generation_id="living-budget",
                )
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        roles_by_source = [
            (block.source, block.role_hint)
            for block in result.recall_blocks
        ]
        self.assertIn(
            (SubstrateSource.TELEGRAM_TEMPORAL, SourceRole.SUBSTRATE_CONTEXT),
            roles_by_source,
        )
        self.assertIn(
            (SubstrateSource.TELEGRAM_SEMANTIC, SourceRole.SUBSTRATE_CONTEXT),
            roles_by_source,
        )
        rendered = brain_loop._render_dispatcher_transcript(
            spec,
            result,
            user_text="what have we discussed recently?",
            surface="telegram_surface",
        )
        self.assertIn("[memory evidence]", rendered)
        self.assertIn("[memory context]", rendered)

    def test_continuity_uses_chat_history_anchor_before_stale_semantic_recall(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._ContinuityFallbackMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "What were we talking about earlier?",
                    spec=_substrate_semantic_spec(),
                    surface="telegram_surface",
                    chat_history=[
                        {
                            "content": (
                                "Rohit: We were testing the living memory split.\n"
                                "Maez: The context role failed to render."
                            )
                        }
                    ],
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(blocks[0].role_hint, SourceRole.SUBSTRATE_EVIDENCE)
        self.assertIn("living memory split", blocks[0].text)
        self.assertNotIn("two-day health check", blocks[0].text)
        self.assertEqual(blocks[1].role_hint, SourceRole.SUBSTRATE_CONTEXT)
        self.assertIn("two-day health check", blocks[1].text)

    def test_date_address_adapter_does_not_inject_dialogue_anchor(self):
        from core import brain_loop
        from core.dispatcher.spec import SubstrateSource

        fake = self._DeepContextMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "remind me what we were doing around April 27",
                    spec=_substrate_semantic_spec(),
                    surface="telegram_surface",
                    chat_history=[
                        {
                            "content": (
                                "Rohit: What about January 3?\n"
                                "Maez: I don't have a dated memory for that window."
                            )
                        }
                    ],
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        text = "\n".join(block.text for block in blocks)
        self.assertIn("April infrastructure note", text)
        self.assertNotIn("Recent dialogue anchor", text)

    def test_chat_history_anchor_does_not_record_unrendered_memory_evidence(self):
        from core import brain_loop
        from core.dispatcher.spec import (
            ProvenanceFraming,
            SourceRole,
            SubstrateSource,
        )

        fake = self._ContinuityFallbackMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "What were we talking about earlier?",
                    spec=_substrate_semantic_spec(
                        framing=ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
                    ),
                    surface="telegram_surface",
                    chat_history=[
                        {
                            "content": (
                                "Rohit: We were testing the living memory split.\n"
                                "Maez: The context role failed to render."
                            )
                        }
                    ],
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_EVIDENCE])
        self.assertIn("living memory split", blocks[0].text)
        self.assertNotIn("two-day health check", blocks[0].text)
        self.assertEqual(fake.recorded, [])

    def test_deep_context_renders_selected_core_context(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole, SubstrateSource

        fake = self._DeepContextMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "What did we note back around April 6 about the infrastructure?",
                    spec=_substrate_semantic_spec(),
                    surface="telegram_surface",
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual([block.role_hint for block in blocks], [SourceRole.SUBSTRATE_CONTEXT])
        self.assertIn("April infrastructure note", blocks[0].text)

    def test_flag_on_unsupported_substrate_framing_emits_no_illegal_blocks(self):
        from core import brain_loop
        from core.dispatcher.spec import ProvenanceFraming, SubstrateSource

        fake = self._FakeMemory()
        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=fake):
                blocks = brain_loop._dispatcher_recall_adapters(
                    "fresh only",
                    spec=SimpleNamespace(provenance_framing=ProvenanceFraming.FRESH_ONLY),
                    surface="telegram",
                )[SubstrateSource.TELEGRAM_SEMANTIC](SubstrateSource.TELEGRAM_SEMANTIC)
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(blocks, [])
        self.assertEqual(fake.recorded, [])


def _substrate_semantic_spec(*, framing=None, external_sources=None, hint=None):
    from core.dispatcher.spec import (
        CompositionHint,
        CompositionSpec,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
        SubstrateSource,
    )

    if framing is None:
        framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
    if external_sources is None:
        external_sources = []
    if hint is None:
        hint = (
            CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE
            if external_sources
            else CompositionHint.SUBSTRATE_ONLY
        )
    return CompositionSpec(
        substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
        external_sources=external_sources,
        composition_hint=hint,
        provenance_framing=framing,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability={
            SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
            **{
                source: SourceAvailability.EXECUTABLE_PRESENT
                for source in external_sources
            },
        },
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )


class LivingRecallFramingTests(unittest.TestCase):
    def test_substrate_only_framing_renders_living_evidence_and_context(self):
        from core import brain_loop
        from core.dispatcher.layer1 import RecallBlock
        from core.dispatcher.spec import SourceRole, SubstrateSource

        result = SimpleNamespace(
            recall_blocks=(
                RecallBlock(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    text="new memory",
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_evidence",
                    prompt_cost=10,
                    role_hint=SourceRole.SUBSTRATE_EVIDENCE,
                ),
                RecallBlock(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    text="old memory",
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_context",
                    prompt_cost=10,
                    role_hint=SourceRole.SUBSTRATE_CONTEXT,
                ),
            ),
            branch_results=(),
        )

        rendered = brain_loop._render_dispatcher_transcript(
            _substrate_semantic_spec(),
            result,
            user_text="what have we discussed recently?",
            surface="telegram",
        )

        self.assertIn("[memory evidence]", rendered)
        self.assertIn("[memory context]", rendered)
        self.assertLess(rendered.index("[memory evidence]"), rendered.index("[memory context]"))

    def test_focused_working_set_receives_april_core_context(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.merge import merge_fanout_results
        from core.routing.focused_cognition import assemble_working_set

        query = "What did we note back around April 6 about the infrastructure?"
        april_core = {
            "id": "core-april-6",
            "content": "[Journal 2026-04-06] infrastructure ground-truth for the daemon witness.",
            "metadata": {},
            "distance": 0.02,
        }
        irrelevant_core = [
            {
                "id": f"core-irrelevant-{i}",
                "content": f"unrelated core identity note {i}",
                "metadata": {},
                "distance": 0.50 + (i * 0.01),
            }
            for i in range(8)
        ]
        fresh_raw = _row(
            "fresh-implementation",
            content="fresh living-memory implementation note",
            days_ago=1,
            distance=0.20,
        )
        old_raw = _row(
            "old-background",
            content="old background context that is not the April core",
            days_ago=40,
            distance=0.10,
        )
        mm = _manager(
            raw_rows=[old_raw, fresh_raw],
            core_rows=[april_core, *irrelevant_core],
        )
        spec = _substrate_semantic_spec()

        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with (
                mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=mm),
                mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
                mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
            ):
                layer1 = Layer1Fanout(
                    adapters=brain_loop._dispatcher_recall_adapters(
                        query,
                        spec=spec,
                        surface="telegram_surface",
                    ),
                    branch_timeout_s=1.0,
                    global_deadline_s=1.0,
                )
                layer1_result = layer1.run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="living-april",
                )
                external_result = ExternalFanout().run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="living-april",
                )
                rendered = merge_fanout_results(
                    spec,
                    layer1_result,
                    external_result,
                    utterance=query,
                    surface="telegram_surface",
                    timestamp="2026-05-29T12:00:00Z",
                )
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        transcript = rendered.prompt_block
        self.assertIn("[memory context]", transcript)
        self.assertIn("2026-04-06", transcript)
        working_set = assemble_working_set(
            transcript=transcript,
            web_context="",
            owner_question=query,
        )
        self.assertIsNotNone(working_set)
        self.assertTrue(
            any(
                item.source_type == "memory_context"
                and ("2026-04" in item.text or "april" in item.text.lower())
                for item in working_set.items
            )
        )

    def test_absolute_date_label_survives_to_working_set(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.merge import merge_fanout_results
        from core.routing.focused_cognition import assemble_working_set

        query = "what did we note around April 6 about the infrastructure?"
        april_core = {
            "id": "core-april-date",
            "content": "[Journal 2026-04-06] infrastructure ground-truth fabrication-class incident.",
            "metadata": {
                "type": "core_memory",
                "source": "nightly_journal",
                "timestamp": "2026-04-07T04:00:02+00:00",
            },
            "distance": 0.02,
        }
        may_core = {
            "id": "core-may",
            "content": "[Journal 2026-05-20] May progress on living recall.",
            "metadata": {
                "type": "core_memory",
                "source": "nightly_journal",
                "timestamp": "2026-05-20T04:00:00+00:00",
            },
            "distance": 0.05,
        }
        mm = _manager(core_rows=[april_core, may_core])
        spec = _substrate_semantic_spec()

        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with (
                mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=mm),
                mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
                mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
            ):
                layer1 = Layer1Fanout(
                    adapters=brain_loop._dispatcher_recall_adapters(
                        query,
                        spec=spec,
                        surface="telegram_surface",
                    ),
                    branch_timeout_s=1.0,
                    global_deadline_s=1.0,
                )
                layer1_result = layer1.run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="absolute-date",
                )
                external_result = ExternalFanout().run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="absolute-date",
                )
                rendered = merge_fanout_results(
                    spec,
                    layer1_result,
                    external_result,
                    utterance=query,
                    surface="telegram_surface",
                    timestamp="2026-05-29T12:00:00Z",
                )
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        transcript = rendered.prompt_block
        self.assertIn("[memory context]", transcript)
        self.assertIn('date_match="exact_date"', transcript)
        self.assertIn("2026-04-06", transcript)
        self.assertIn("fabrication-class", transcript)
        self.assertNotIn("May progress", transcript)

        working_set = assemble_working_set(
            transcript=transcript,
            web_context="",
            owner_question=query,
        )
        self.assertIsNotNone(working_set)
        assert working_set is not None
        self.assertTrue(
            any(
                item.source_type == "memory_context"
                and 'date_match="exact_date"' in item.text
                and "fabrication-class" in item.text
                for item in working_set.items
            )
        )

    def test_content_anchored_deep_context_renders_and_is_seen(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.layer1 import Layer1Fanout
        from core.dispatcher.merge import merge_fanout_results
        from core.routing.focused_cognition import assemble_working_set

        query = "What's the infrastructure ground-truth you noted earlier?"
        core_note = {
            "id": "core-infra-ground-truth",
            "content": "Infrastructure ground-truth: the daemon witness must prove selected memory reaches context.",
            "metadata": {},
            "distance": 0.02,
        }
        fresh_daily = _row(
            "daily-implementation",
            content="fresh living-memory implementation note",
            days_ago=1,
            distance=0.20,
        )
        mm = _manager(daily_rows=[fresh_daily], core_rows=[core_note])
        spec = _substrate_semantic_spec()

        os.environ["MAEZ_LIVING_RECALL_ENABLED"] = "1"
        try:
            with (
                mock.patch("core.brain.brain_loop._dispatcher_memory_manager", return_value=mm),
                mock.patch("memory.memory_manager._now_seconds", return_value=datetime(2026, 5, 29, 12, 0, tzinfo=timezone.utc).timestamp()),
                mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
            ):
                layer1 = Layer1Fanout(
                    adapters=brain_loop._dispatcher_recall_adapters(
                        query,
                        spec=spec,
                        surface="telegram_surface",
                    ),
                    branch_timeout_s=1.0,
                    global_deadline_s=1.0,
                )
                layer1_result = layer1.run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="living-content",
                )
                external_result = ExternalFanout().run(
                    spec,
                    utterance=query,
                    conversation_state={"surface": "telegram_surface"},
                    fanout_generation_id="living-content",
                )
                rendered = merge_fanout_results(
                    spec,
                    layer1_result,
                    external_result,
                    utterance=query,
                    surface="telegram_surface",
                    timestamp="2026-05-29T12:00:00Z",
                )
        finally:
            os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        transcript = rendered.prompt_block
        self.assertIn("[memory context]", transcript)
        self.assertIn("infrastructure ground-truth", transcript.lower())
        working_set = assemble_working_set(
            transcript=transcript,
            web_context="",
            owner_question=query,
        )
        self.assertIsNotNone(working_set)
        self.assertTrue(
            any(
                item.source_type == "memory_context"
                and "infrastructure ground-truth" in item.text.lower()
                for item in working_set.items
            )
        )


class ScopeParityTests(unittest.TestCase):
    def test_recall_for_cycle_is_identical_with_living_flag_on_or_off(self):
        rows = [
            _row("cycle-a", content="cycle memory a", days_ago=1, distance=0.20),
            _row("cycle-b", content="cycle memory b", days_ago=30, distance=0.10),
        ]
        core = [{"id": "core", "content": "core memory", "metadata": {}}]

        def run(flag_value: str | None):
            mm = _manager(raw_rows=rows, daily_rows=[], core_rows=core)
            if flag_value is None:
                os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)
            else:
                os.environ["MAEZ_LIVING_RECALL_ENABLED"] = flag_value
            try:
                with (
                    mock.patch("core.memory_scoring.record_recall", side_effect=lambda *a, **k: None),
                    mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
                ):
                    return mm.recall_for_cycle("cycle memory")
            finally:
                os.environ.pop("MAEZ_LIVING_RECALL_ENABLED", None)

        self.assertEqual(run(None), run("1"))


if __name__ == "__main__":
    unittest.main()
