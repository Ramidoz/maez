# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for memory/mmr.py — maximal marginal relevance re-ranking."""
from __future__ import annotations

import unittest

from memory.mmr import tokenize, jaccard, mmr_rerank


class Tokenize(unittest.TestCase):

    def test_lowercases_and_splits_ascii(self):
        # Numbers collapse to __num__ placeholder so near-duplicates
        # register as similar (see dedicated test below).
        self.assertEqual(
            tokenize("Disk at 70% on /home"),
            {"disk", "at", "__num__", "on", "home"},
        )

    def test_empty_text_yields_empty_set(self):
        self.assertEqual(tokenize(""), set())
        self.assertEqual(tokenize(None or ""), set())

    def test_compound_identifier_splits_on_punctuation(self):
        # `maez-daemon` should yield both halves.
        tokens = tokenize("running maez-daemon cycle")
        self.assertIn("maez", tokens)
        self.assertIn("daemon", tokens)
        self.assertIn("cycle", tokens)

    def test_numbers_collapse_to_placeholder_so_near_duplicates_look_similar(self):
        # "disk 70.7%" and "disk 69.9%" are semantically near-duplicates;
        # without number normalization their digit tokens make them look
        # distinct and MMR's disk-fixation defense fails.
        self.assertEqual(tokenize("disk 70.7%"), tokenize("disk 69.9%"))
        self.assertIn("__num__", tokenize("disk 70.7%"))

    def test_no_spurious_cjk_bigrams_across_gaps(self):
        # Mixed CJK + ASCII: 欢 and 你 are not adjacent in the source so
        # no "欢你" bigram should appear.
        tokens = tokenize("我喜欢hello你好")
        self.assertIn("hello", tokens)
        self.assertIn("我喜", tokens)  # adjacent CJK → bigram
        self.assertIn("你好", tokens)  # adjacent CJK → bigram
        self.assertNotIn("欢你", tokens)  # NOT adjacent (hello between)


class Jaccard(unittest.TestCase):

    def test_identical_sets_are_one(self):
        a = {"x", "y", "z"}
        self.assertEqual(jaccard(a, a), 1.0)

    def test_disjoint_sets_are_zero(self):
        self.assertEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_empty_sets_are_one_by_convention(self):
        self.assertEqual(jaccard(set(), set()), 1.0)

    def test_half_overlap_is_one_third(self):
        # |{a,b} ∩ {b,c}| / |{a,b,c}| = 1/3
        self.assertAlmostEqual(jaccard({"a", "b"}, {"b", "c"}), 1 / 3)


class MmrRerank(unittest.TestCase):

    def _mk(self, content: str, distance: float) -> dict:
        return {"content": content, "distance": distance}

    def test_empty_input_returns_empty(self):
        self.assertEqual(mmr_rerank([], k=5), [])

    def test_k_zero_returns_empty(self):
        items = [self._mk("x", 0.2)]
        self.assertEqual(mmr_rerank(items, k=0), [])

    def test_lambda_one_is_pure_relevance(self):
        items = [
            self._mk("alpha beta gamma", 0.3),
            self._mk("alpha beta gamma", 0.1),  # best distance
            self._mk("alpha beta gamma", 0.5),
        ]
        out = mmr_rerank(items, k=3, lambda_=1.0)
        # Pure relevance ignores diversity — sorted by distance ascending.
        self.assertEqual([m["distance"] for m in out], [0.1, 0.3, 0.5])

    def test_diversity_breaks_duplicate_cluster(self):
        # Three near-duplicates about disk, one outlier about network.
        # MMR with λ=0.5 should pick one disk + the network result
        # before returning the second disk.
        items = [
            self._mk("disk usage at 70 percent", 0.10),
            self._mk("disk usage at 71 percent", 0.11),
            self._mk("disk usage at 69 percent", 0.12),
            self._mk("network latency spike to llm server", 0.30),
        ]
        out = mmr_rerank(items, k=2, lambda_=0.5)
        contents = [m["content"] for m in out]
        # First pick is the most relevant disk result.
        self.assertIn("disk usage at 70 percent", contents[0])
        # Second pick should be the network outlier, NOT another disk line.
        self.assertIn("network latency", contents[1])

    def test_disk_fixation_scenario_with_default_lambda(self):
        """The actual drift pattern Maez exhibits: 5 disk near-dupes +
        2 outliers. Default λ (0.7) must promote at least one non-disk
        result into the top-3 so the reasoning cycle sees non-disk
        context."""
        items = [
            self._mk("disk usage at 70.7% on /", 0.10),
            self._mk("disk usage 71.0% on /", 0.11),
            self._mk("disk 69.9% on /", 0.12),
            self._mk("disk at 70.4 percent on root", 0.13),
            self._mk("disk 70.2%", 0.14),
            self._mk("CPU briefly spiked on claude process", 0.25),
            self._mk("telegram message from Rohit about groceries", 0.35),
        ]
        out = mmr_rerank(items, k=3, lambda_=0.7)
        contents = [m["content"] for m in out]
        # First must be the most-relevant disk snippet.
        self.assertIn("disk usage at 70.7%", contents[0])
        # At least one of the next two must be a non-disk outlier.
        non_disk_in_top3 = any(
            "CPU" in c or "telegram" in c for c in contents[1:]
        )
        self.assertTrue(
            non_disk_in_top3,
            f"MMR failed to break disk-fixation with default λ; got {contents}",
        )

    def test_missing_distance_treated_as_neutral(self):
        items = [{"content": "a b c"}, {"content": "d e f"}]
        # Should not crash; returns something of length 2.
        out = mmr_rerank(items, k=2)
        self.assertEqual(len(out), 2)

    def test_does_not_mutate_input(self):
        items = [self._mk("x y z", 0.2), self._mk("p q r", 0.4)]
        original = [dict(m) for m in items]
        mmr_rerank(items, k=2, lambda_=0.5)
        self.assertEqual(items, original)

    def test_k_larger_than_available_returns_all(self):
        items = [self._mk("a", 0.1), self._mk("b", 0.2)]
        out = mmr_rerank(items, k=10)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
