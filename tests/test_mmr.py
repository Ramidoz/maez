# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for memory/mmr.py — Maximal Marginal Relevance re-ranking.

Covers:
  - tokenize(): ASCII runs, case folding, hyphen splitting, number
    normalisation, CJK unigrams + adjacent bigrams, non-adjacent no-
    spurious-bigram, mixed content, punctuation-only edge case.
  - jaccard(): both-empty convention, one-empty, identical, fully-
    disjoint, partial-overlap fraction, symmetry, unit-interval bounds.
  - mmr_rerank(): k≤0 / empty-list guards, k > len(items) saturation,
    λ=1.0 pure-relevance shortcut, λ=0.7 diversity (unique item beats
    third near-duplicate), λ=0.0 pure-diversity second pick, missing /
    None distance default, missing content key, distance clamping
    above 1.0, custom content_key / distance_key, input non-mutation
    (list and individual dicts), determinism, exact-k return length,
    DEFAULT_LAMBDA constant value.

Deliberately skipped:
  - Chroma / embedding integration (requires live store; offline tests).
  - End-to-end recall pipeline (higher-level integration concern).
  - Performance / timing benchmarks.
  - No mocking, env patches, or tempdir fixtures are required — the
    module is pure computation with no I/O.
"""
import unittest

from memory.mmr import DEFAULT_LAMBDA, jaccard, mmr_rerank, tokenize


# ---------------------------------------------------------------------------
# tokenize()
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    """Tests for memory.mmr.tokenize()."""

    # ---- edge cases --------------------------------------------------------

    def test_empty_string_returns_empty_set(self):
        self.assertEqual(tokenize(""), set())

    def test_returns_set_type(self):
        self.assertIsInstance(tokenize("hello"), set)

    def test_punctuation_only_returns_empty_set(self):
        self.assertEqual(tokenize("!!! ???"), set())

    # ---- ASCII tokenisation ------------------------------------------------

    def test_basic_ascii_words(self):
        result = tokenize("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_uppercase_is_lowercased(self):
        result = tokenize("Maez DAEMON")
        self.assertIn("maez", result)
        self.assertIn("daemon", result)

    def test_hyphenated_word_splits_on_hyphen(self):
        result = tokenize("maez-daemon")
        self.assertIn("maez", result)
        self.assertIn("daemon", result)
        self.assertNotIn("maez-daemon", result)

    def test_underscore_kept_inside_token(self):
        result = tokenize("some_variable")
        self.assertIn("some_variable", result)

    # ---- number normalisation ----------------------------------------------

    def test_decimal_number_replaced_by_placeholder(self):
        result = tokenize("usage is 70.7%")
        self.assertIn("__num__", result)
        self.assertNotIn("70", result)
        self.assertNotIn("70.7", result)

    def test_integer_replaced_by_placeholder(self):
        result = tokenize("loaded 42 items")
        self.assertIn("__num__", result)
        self.assertNotIn("42", result)

    def test_two_numeric_snippets_collapse_to_same_token_set(self):
        """Disk-usage snippets differing only in percentage become identical."""
        a = tokenize("disk usage is 70.7%")
        b = tokenize("disk usage is 69.9%")
        self.assertEqual(a, b)

    # ---- CJK ---------------------------------------------------------------

    def test_cjk_unigrams_emitted(self):
        result = tokenize("我你好")
        self.assertIn("我", result)
        self.assertIn("你", result)
        self.assertIn("好", result)

    def test_cjk_adjacent_bigram_emitted(self):
        result = tokenize("你好")
        self.assertIn("你好", result)

    def test_cjk_non_adjacent_chars_produce_no_spurious_bigram(self):
        """CJK chars separated by ASCII must NOT form a cross-gap bigram."""
        result = tokenize("欢hello你")
        self.assertNotIn("欢你", result)
        self.assertIn("欢", result)
        self.assertIn("你", result)

    def test_mixed_ascii_and_cjk(self):
        result = tokenize("hello 你好 world")
        self.assertIn("hello", result)
        self.assertIn("world", result)
        self.assertIn("你", result)
        self.assertIn("好", result)
        self.assertIn("你好", result)


# ---------------------------------------------------------------------------
# jaccard()
# ---------------------------------------------------------------------------

class TestJaccard(unittest.TestCase):
    """Tests for memory.mmr.jaccard()."""

    def test_both_empty_sets_returns_one(self):
        self.assertEqual(jaccard(set(), set()), 1.0)

    def test_left_empty_returns_zero(self):
        self.assertEqual(jaccard(set(), {"a"}), 0.0)

    def test_right_empty_returns_zero(self):
        self.assertEqual(jaccard({"a"}, set()), 0.0)

    def test_identical_same_object(self):
        s = {"a", "b", "c"}
        self.assertEqual(jaccard(s, s), 1.0)

    def test_identical_copy_returns_one(self):
        self.assertEqual(jaccard({"x", "y"}, {"x", "y"}), 1.0)

    def test_fully_disjoint_returns_zero(self):
        self.assertEqual(jaccard({"a", "b"}, {"c", "d"}), 0.0)

    def test_partial_overlap_correct_fraction(self):
        # intersection={b}, union={a,b,c} → 1/3
        result = jaccard({"a", "b"}, {"b", "c"})
        self.assertAlmostEqual(result, 1 / 3)

    def test_result_in_unit_interval(self):
        pairs = [
            ({"x"}, {"x", "y"}),
            ({"a", "b", "c"}, {"b", "c", "d", "e"}),
        ]
        for a, b in pairs:
            r = jaccard(a, b)
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)

    def test_symmetry(self):
        a, b = {"foo", "bar"}, {"bar", "baz"}
        self.assertAlmostEqual(jaccard(a, b), jaccard(b, a))


# ---------------------------------------------------------------------------
# mmr_rerank()
# ---------------------------------------------------------------------------

class TestMmrRerank(unittest.TestCase):
    """Tests for memory.mmr.mmr_rerank()."""

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def _item(content: str, distance: float) -> dict:
        return {"content": content, "distance": distance}

    # ---- guard conditions --------------------------------------------------

    def test_k_zero_returns_empty_list(self):
        self.assertEqual(mmr_rerank([self._item("x", 0.1)], k=0), [])

    def test_k_negative_returns_empty_list(self):
        self.assertEqual(mmr_rerank([self._item("x", 0.1)], k=-3), [])

    def test_empty_items_returns_empty_list(self):
        self.assertEqual(mmr_rerank([], k=5), [])

    def test_k_larger_than_items_returns_all(self):
        items = [self._item("a", 0.2), self._item("b", 0.4)]
        result = mmr_rerank(items, k=100)
        self.assertEqual(len(result), 2)

    def test_single_item_list(self):
        items = [self._item("only one", 0.3)]
        result = mmr_rerank(items, k=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "only one")

    # ---- pure-relevance shortcut (λ ≥ 1.0) --------------------------------

    def test_lambda_one_orders_ascending_by_distance(self):
        items = [
            self._item("c", 0.5),
            self._item("a", 0.1),
            self._item("b", 0.3),
        ]
        result = mmr_rerank(items, k=3, lambda_=1.0)
        distances = [r["distance"] for r in result]
        self.assertEqual(distances, sorted(distances))

    def test_lambda_one_returns_top_k_by_distance(self):
        items = [
            self._item("far",   0.9),
            self._item("close", 0.1),
            self._item("mid",   0.5),
        ]
        result = mmr_rerank(items, k=2, lambda_=1.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["content"], "close")
        self.assertEqual(result[1]["content"], "mid")

    # ---- diversity ---------------------------------------------------------

    def test_mmr_favours_unique_item_over_third_near_duplicate(self):
        """λ=0.7: after picking the best disk snippet, the next pick should
        be the topically-distinct memory snippet, not another disk clone."""
        disk1  = self._item("disk usage is 70% high", 0.10)
        disk2  = self._item("disk usage is 71% high", 0.11)
        disk3  = self._item("disk usage is 72% high", 0.12)
        unique = self._item("memory allocation optimised", 0.30)
        items  = [disk1, disk2, disk3, unique]

        result = mmr_rerank(items, k=2, lambda_=0.7)
        self.assertEqual(result[0], disk1)  # most relevant first
        contents = {r["content"] for r in result}
        self.assertIn(unique["content"], contents)

    def test_lambda_zero_second_pick_maximises_diversity(self):
        """λ=0 ignores relevance; second pick must differ most from first."""
        a = self._item("disk usage high disk usage high", 0.05)
        b = self._item("disk usage high disk usage high", 0.06)
        c = self._item("network latency spike response slow", 0.90)
        items = [a, b, c]

        result = mmr_rerank(items, k=2, lambda_=0.0)
        # Second pick should be c, the most distinct item
        self.assertEqual(result[1]["content"], c["content"])

    # ---- missing / None keys -----------------------------------------------

    def test_missing_distance_key_treated_as_one(self):
        items = [
            {"content": "has distance", "distance": 0.2},
            {"content": "no distance"},
        ]
        result = mmr_rerank(items, k=2, lambda_=1.0)
        self.assertEqual(result[0]["content"], "has distance")
        self.assertEqual(result[1]["content"], "no distance")

    def test_none_distance_treated_as_one(self):
        items = [
            {"content": "a", "distance": None},
            {"content": "b", "distance": 0.2},
        ]
        result = mmr_rerank(items, k=2, lambda_=1.0)
        self.assertEqual(result[0]["content"], "b")

    def test_missing_content_key_does_not_raise(self):
        items = [
            {"distance": 0.1},
            {"content": "real content", "distance": 0.5},
        ]
        result = mmr_rerank(items, k=2)
        self.assertEqual(len(result), 2)

    # ---- distance clamping -------------------------------------------------

    def test_distance_above_one_clamped_to_one(self):
        """Chroma-style distances can exceed 1.0; they must be clamped."""
        items = [
            self._item("far",   2.5),   # clamped → relevance 0
            self._item("close", 0.1),   # relevance 0.9
        ]
        result = mmr_rerank(items, k=2, lambda_=1.0)
        self.assertEqual(result[0]["content"], "close")

    def test_distance_zero_means_maximum_relevance(self):
        items = [
            self._item("perfect",  0.0),
            self._item("mediocre", 0.5),
        ]
        result = mmr_rerank(items, k=1)
        self.assertEqual(result[0]["content"], "perfect")

    # ---- custom keys -------------------------------------------------------

    def test_custom_content_and_distance_keys(self):
        items = [
            {"text": "foo bar baz",        "score": 0.8},
            {"text": "alpha beta gamma",   "score": 0.2},
        ]
        result = mmr_rerank(
            items, k=2, content_key="text", distance_key="score", lambda_=1.0
        )
        self.assertEqual(result[0]["text"], "alpha beta gamma")
        self.assertEqual(result[1]["text"], "foo bar baz")

    # ---- non-mutation ------------------------------------------------------

    def test_input_list_not_mutated(self):
        items = [self._item("a", 0.1), self._item("b", 0.2), self._item("c", 0.3)]
        original_ids = [id(m) for m in items]
        _ = mmr_rerank(items, k=2)
        self.assertEqual(len(items), 3)
        self.assertEqual([id(m) for m in items], original_ids)

    def test_input_dicts_not_mutated(self):
        item = {"content": "hello", "distance": 0.1}
        original = dict(item)
        _ = mmr_rerank([item], k=1)
        self.assertEqual(item, original)

    # ---- determinism -------------------------------------------------------

    def test_same_input_produces_same_output(self):
        items = [
            self._item("alpha beta",    0.20),
            self._item("gamma delta",   0.30),
            self._item("epsilon zeta",  0.25),
        ]
        r1 = mmr_rerank(items, k=3)
        r2 = mmr_rerank(items, k=3)
        self.assertEqual(
            [i["content"] for i in r1],
            [i["content"] for i in r2],
        )

    # ---- return length -----------------------------------------------------

    def test_returns_exactly_k_items_when_pool_large_enough(self):
        items = [self._item(f"item {i}", i * 0.05) for i in range(10)]
        result = mmr_rerank(items, k=4)
        self.assertEqual(len(result), 4)

    # ---- DEFAULT_LAMBDA ----------------------------------------------------

    def test_default_lambda_constant_is_0_7(self):
        self.assertEqual(DEFAULT_LAMBDA, 0.7)

    def test_omitting_lambda_matches_explicit_0_7(self):
        items = [self._item(f"content {i}", 0.1 * i) for i in range(1, 6)]
        r_default  = mmr_rerank(items, k=3)
        r_explicit = mmr_rerank(items, k=3, lambda_=0.7)
        self.assertEqual(
            [i["content"] for i in r_default],
            [i["content"] for i in r_explicit],
        )


if __name__ == "__main__":
    unittest.main()
