# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.memory_scoring — concept tags, recall statistics,
promotion scoring.

Observational layer: the scorer function and sidecar DB are tested, but
no dream-state behavior change is asserted (dream integration is a
follow-up, per scope)."""
from __future__ import annotations

import time
import unittest

from core import memory_scoring as ms
from core.memory_scoring import (
    derive_concept_tags, record_recall, get_stats, mark_consolidated,
    promotion_score, RecallStats, PromotionWeights, MAX_CONCEPT_TAGS,
)


# ── concept tag derivation ────────────────────────────────────────────

class ConceptTags(unittest.TestCase):

    def test_empty_input(self):
        self.assertEqual(derive_concept_tags(""), [])
        self.assertEqual(derive_concept_tags(None or ""), [])

    def test_extracts_non_stopwords(self):
        tags = derive_concept_tags("The daemon is running the reasoning cycle")
        self.assertNotIn("the", tags)
        self.assertNotIn("is", tags)
        for expected in ("daemon", "running", "reasoning", "cycle"):
            self.assertIn(expected, tags)

    def test_caps_at_max(self):
        text = " ".join(f"word{i}" for i in range(50))
        tags = derive_concept_tags(text)
        self.assertLessEqual(len(tags), MAX_CONCEPT_TAGS)

    def test_deterministic(self):
        text = "disk usage is hovering around 70 percent on root"
        self.assertEqual(derive_concept_tags(text), derive_concept_tags(text))

    def test_dedupes_preserving_first_order(self):
        tags = derive_concept_tags("disk disk disk usage usage processes")
        self.assertEqual(tags, ["disk", "usage", "processes"])

    def test_respects_max_tags_arg(self):
        tags = derive_concept_tags("one two three four five six", max_tags=3)
        self.assertEqual(len(tags), 3)


# ── recall stats DB round-trip ────────────────────────────────────────

class RecallStatsRoundtrip(unittest.TestCase):

    def setUp(self):
        ms._diag_clear_for_test()

    def tearDown(self):
        ms._diag_clear_for_test()

    def test_first_recall_creates_row(self):
        record_recall("m1", query="disk usage", relevance=0.8,
                      concept_tags=["disk", "usage"])
        stats = get_stats("m1")
        self.assertEqual(stats.memory_id, "m1")
        self.assertEqual(stats.recall_count, 1)
        self.assertAlmostEqual(stats.max_relevance, 0.8, places=3)
        self.assertEqual(len(stats.query_hashes), 1)
        self.assertEqual(len(stats.recall_days), 1)
        self.assertEqual(stats.concept_tags, ["disk", "usage"])
        self.assertFalse(stats.consolidated)

    def test_repeated_same_query_only_counts_once_in_diversity(self):
        # Same query string surfaces the memory 5 times — diversity signal
        # should stay at 1, not grow.
        for _ in range(5):
            record_recall("m2", query="same query", relevance=0.5)
        stats = get_stats("m2")
        self.assertEqual(stats.recall_count, 5)
        self.assertEqual(len(stats.query_hashes), 1)

    def test_distinct_queries_add_diversity(self):
        for i in range(3):
            record_recall("m3", query=f"query {i}", relevance=0.5)
        stats = get_stats("m3")
        self.assertEqual(len(stats.query_hashes), 3)

    def test_max_relevance_only_grows(self):
        record_recall("m4", query="q", relevance=0.3)
        record_recall("m4", query="q", relevance=0.9)
        record_recall("m4", query="q", relevance=0.5)
        self.assertAlmostEqual(get_stats("m4").max_relevance, 0.9, places=3)

    def test_get_stats_missing_id_returns_empty(self):
        stats = get_stats("never-recorded")
        self.assertEqual(stats.recall_count, 0)
        self.assertEqual(stats.max_relevance, 0.0)
        self.assertEqual(stats.query_hashes, [])

    def test_mark_consolidated(self):
        record_recall("m5", query="q", relevance=0.5)
        self.assertFalse(get_stats("m5").consolidated)
        mark_consolidated("m5")
        self.assertTrue(get_stats("m5").consolidated)

    def test_query_hashes_bounded(self):
        for i in range(60):  # over MAX_QUERY_HASHES (32)
            record_recall("m6", query=f"q{i}", relevance=0.5)
        self.assertLessEqual(len(get_stats("m6").query_hashes),
                             ms._MAX_QUERY_HASHES)

    def test_never_raises_on_empty_id(self):
        # Should silently no-op, not raise.
        record_recall("", query="q", relevance=0.5)
        mark_consolidated("")
        stats = get_stats("")
        self.assertEqual(stats.recall_count, 0)


# ── promotion score ───────────────────────────────────────────────────

class PromotionScore(unittest.TestCase):

    def test_empty_stats_near_zero(self):
        score = promotion_score(RecallStats(memory_id="x"))
        self.assertLess(score, 0.05)

    def test_score_bounded_0_to_1(self):
        # Pathological: max everything.
        stats = RecallStats(
            memory_id="x",
            recall_count=999,
            max_relevance=1.0,
            query_hashes=["h"] * ms._MAX_QUERY_HASHES,
            recall_days=[f"d{i}" for i in range(ms._MAX_RECALL_DAYS)],
            concept_tags=["t"] * MAX_CONCEPT_TAGS,
            last_recalled_at=time.time(),
            consolidated=True,
        )
        score = promotion_score(stats, now=time.time())
        self.assertGreater(score, 0.99)
        self.assertLessEqual(score, 1.0)

    def test_recency_decays(self):
        stats = RecallStats(
            memory_id="x",
            recall_count=5,
            max_relevance=0.8,
            query_hashes=["a", "b", "c"],
            recall_days=["d1", "d2"],
            concept_tags=["t1", "t2"],
            last_recalled_at=1_000_000.0,
            consolidated=False,
        )
        fresh = promotion_score(stats, now=1_000_000.0)
        # 14 days later, recency should have halved
        day_s = 86400
        half = promotion_score(stats, now=1_000_000.0 + 14 * day_s)
        self.assertLess(half, fresh)

    def test_weight_knobs_respected(self):
        stats = RecallStats(
            memory_id="x", recall_count=10, max_relevance=0.5,
            query_hashes=["a"], recall_days=["d1"],
            last_recalled_at=time.time(),
        )
        # Relevance-dominant weights vs frequency-dominant should yield
        # different scores for this stats.
        w_rel = PromotionWeights(
            frequency=0.0, relevance=1.0, diversity=0.0,
            recency=0.0, consolidation=0.0, conceptual=0.0,
        )
        w_freq = PromotionWeights(
            frequency=1.0, relevance=0.0, diversity=0.0,
            recency=0.0, consolidation=0.0, conceptual=0.0,
        )
        self.assertNotAlmostEqual(
            promotion_score(stats, weights=w_rel),
            promotion_score(stats, weights=w_freq),
        )

    def test_consolidation_flag_contributes(self):
        base = RecallStats(memory_id="x", recall_count=1, max_relevance=0.5,
                           last_recalled_at=time.time())
        s_unconsolidated = promotion_score(base)
        base.consolidated = True
        s_consolidated = promotion_score(base)
        self.assertGreater(s_consolidated, s_unconsolidated)


# ── integration sanity ────────────────────────────────────────────────

class EndToEnd(unittest.TestCase):
    """Feed a real memory through record_recall multiple times and
    verify the scorer reads the accumulated signal correctly."""

    def setUp(self):
        ms._diag_clear_for_test()

    def tearDown(self):
        ms._diag_clear_for_test()

    def test_accumulating_recalls_raises_score(self):
        mem_id = "end2end-1"
        # No recall yet — score at floor.
        initial = promotion_score(get_stats(mem_id))

        # Simulate 10 recalls with varied queries.
        for i in range(10):
            record_recall(mem_id,
                          query=f"different query {i}",
                          relevance=0.5 + i * 0.03,
                          concept_tags=["disk", "usage"])

        final = promotion_score(get_stats(mem_id))
        self.assertGreater(final, initial + 0.2,
                           f"score didn't accumulate: {initial:.3f} → {final:.3f}")


class StaleNumberClaim(unittest.TestCase):
    """Stale specific-number recall penalty. Added 2026-04-22 to break
    the recall loop where memories quoting live-state numbers (CPU %,
    uncommitted count) get repeatedly surfaced and restated."""

    def test_patterns_match_real_fabrications(self):
        # These are actual strings seen in the raw memory store as of
        # 2026-04-22 — all caught at some point as ungrounded claims.
        for s in [
            "you have 66 uncommitted changes in the `maez` repo",
            "66 uncommitted files in maez",
            "The partition remains at 65.6% capacity, a persistent trend",
            "Root disk at 69.8% and climbing",
            "138% CPU spike from a python3 process",
            "memory is at 72% utilization right now",
            "load average of 2.5 over the last 5 minutes",
        ]:
            self.assertTrue(ms.has_stale_number_claim(s),
                            f"should have matched: {s!r}")

    def test_patterns_do_not_match_legit_numbers(self):
        for s in [
            "Rohit has 2 repos open on his desk",
            "Maez runs with 32k ctx",
            "I noticed you stepped away for 30 minutes",  # presence gap
            "the grandmother case is the origin story",
            "cycle 1234 completed",  # cycle counter, not live state
            "",
        ]:
            self.assertFalse(ms.has_stale_number_claim(s),
                             f"should NOT have matched: {s!r}")

    def test_none_input_is_safe(self):
        # self-dev review on 5d27884 flagged that `None or ""` in the
        # loop above evaluates to `""` at list-construction time, so
        # the None branch of has_stale_number_claim was never
        # exercised. Test it explicitly so a future refactor can't
        # silently break the None guard.
        self.assertFalse(ms.has_stale_number_claim(None))  # type: ignore[arg-type]
        self.assertEqual(ms.stale_number_weight(None, age_hours=24), 1.0)  # type: ignore[arg-type]

    def test_weight_at_zero_age_is_one(self):
        self.assertEqual(
            ms.stale_number_weight("66 uncommitted changes", age_hours=0),
            1.0,
        )

    def test_weight_halves_at_half_life(self):
        w = ms.stale_number_weight(
            "66 uncommitted changes",
            age_hours=ms._STALE_NUMBER_HALF_LIFE_HOURS,
        )
        self.assertAlmostEqual(w, 0.5, places=3)

    def test_weight_floors_for_very_old(self):
        w = ms.stale_number_weight("66 uncommitted", age_hours=10000)
        self.assertEqual(w, ms._STALE_NUMBER_MIN_WEIGHT)

    def test_clean_content_always_weight_one(self):
        for age in [0, 1, 24, 1000]:
            self.assertEqual(
                ms.stale_number_weight("the grandmother case", age_hours=age),
                1.0,
            )


if __name__ == "__main__":
    unittest.main()
