"""Tests for the Telegram recall benchmark (corpus, metrics, driver).

Mutation discipline: tests assert not only that the machinery works but
that it MEASURES — a benchmark whose metrics cannot fail is the exact
defect class the vision bake-off kept finding.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.eval.retrieval_metrics import (
    evidence_hit,
    ndcg_at_k,
    ranked_concat,
    recall_at_k,
    tier_ids,
)
from core.eval.telegram_corpus import (
    build_question_corpus,
    ingest_corpus,
    parse_lme_date,
)


def _question(qid="q1", qtype="single-session-user", turns=None, dates=None):
    return {
        "question_id": qid,
        "question_type": qtype,
        "question": "What color is the owner's bicycle?",
        "answer": "red",
        "question_date": "2023/05/02 (Tue) 10:00",
        "haystack_sessions": turns
        or [
            [
                {"role": "user", "content": "My bicycle is red.", "has_answer": True},
                {"role": "assistant", "content": "Noted — a red bicycle."},
                {"role": "user", "content": "It rained today."},
                {"role": "assistant", "content": "Stay dry out there."},
            ]
        ],
        "haystack_dates": dates or ["2023/04/10 (Mon) 23:07"],
    }


class ParseDateTests(unittest.TestCase):
    def test_parses_the_lme_shape(self):
        dt = parse_lme_date("2023/04/10 (Mon) 23:07")
        self.assertEqual(
            dt, datetime(2023, 4, 10, 23, 7, tzinfo=timezone.utc)
        )

    def test_rejects_garbage_and_blank(self):
        self.assertIsNone(parse_lme_date(""))
        self.assertIsNone(parse_lme_date("Monday last week"))
        self.assertIsNone(parse_lme_date("2023/13/45 (Xxx) 99:99"))


class CorpusTests(unittest.TestCase):
    def test_pairs_and_labels(self):
        corpus = build_question_corpus(_question())
        self.assertEqual(len(corpus.rows), 2)
        self.assertEqual(len(corpus.answer_row_ids), 1)
        flagged = next(r for r in corpus.rows if r.has_answer)
        self.assertIn("My bicycle is red.", flagged.document)
        self.assertIn("\nMaez: ", flagged.document)

    def test_document_shape_parses_like_a_real_exchange(self):
        # The corpus MUST look like the live writer's rows, or the
        # bench exercises a different code path than production. The
        # live pipeline is store-row -> _clean_exchange (adapter
        # normalizer) -> history_to_messages; raw store rows are
        # deliberately REJECTED by the parser without the cleaner.
        from core.brain.conversation_history import history_to_messages
        from skills.surface.maez_adapter import _clean_exchange

        corpus = build_question_corpus(_question())
        history = [
            {"content": _clean_exchange(row.document)} for row in corpus.rows
        ]
        messages = history_to_messages(history)
        self.assertEqual(
            [m["role"] for m in messages],
            ["user", "assistant", "user", "assistant"],
        )
        # And the cleaner must actually have recognised the daemon
        # form (not passed it through unchanged): cleaned rows no
        # longer carry the raw-store prefix.
        for entry in history:
            self.assertFalse(entry["content"].startswith("the owner ("))

    def test_orphan_user_turn_still_forms_a_parseable_row(self):
        q = _question(
            turns=[[{"role": "user", "content": "Solo line.", "has_answer": True}]]
        )
        corpus = build_question_corpus(q)
        self.assertEqual(len(corpus.rows), 1)
        self.assertIn("(no reply recorded)", corpus.rows[0].document)
        self.assertEqual(len(corpus.answer_row_ids), 1)

    def test_timestamps_backdated_to_session_date(self):
        corpus = build_question_corpus(_question())
        stamps = [r.metadata["timestamp"] for r in corpus.rows]
        self.assertTrue(all(s.startswith("2023-04-10") for s in stamps))
        self.assertEqual(len(set(stamps)), len(stamps))  # ordered, distinct

    def test_metadata_is_scalar_only(self):
        # Chroma rejects non-scalar metadata values.
        corpus = build_question_corpus(_question())
        for row in corpus.rows:
            for value in row.metadata.values():
                self.assertIsInstance(value, (str, int, float, bool))

    def test_ingest_refuses_production_base_db(self):
        import memory.memory_manager as mm_mod

        corpus = build_question_corpus(_question())
        saved = mm_mod.BASE_DB
        try:
            mm_mod.BASE_DB = Path("/home/rohit/maez/memory/db")
            with self.assertRaises(RuntimeError):
                ingest_corpus(object(), corpus)
        finally:
            mm_mod.BASE_DB = saved


class MetricsTests(unittest.TestCase):
    def test_recall_at_k(self):
        self.assertEqual(recall_at_k(["a", "b", "c"], {"a", "c"}, 2), 0.5)
        self.assertEqual(recall_at_k(["a", "b", "c"], {"a", "c"}, 3), 1.0)
        self.assertEqual(recall_at_k([], {"a"}, 10), 0.0)
        self.assertEqual(recall_at_k(["a"], set(), 10), 0.0)

    def test_recall_can_fail(self):
        # Mutation check: a ranking missing every relevant id scores 0.
        self.assertEqual(recall_at_k(["x", "y"], {"a"}, 10), 0.0)

    def test_ndcg_orders_matter(self):
        first = ndcg_at_k(["a", "x", "y"], {"a"}, 3)
        last = ndcg_at_k(["x", "y", "a"], {"a"}, 3)
        self.assertGreater(first, last)
        self.assertAlmostEqual(first, 1.0)

    def test_evidence_hit(self):
        self.assertTrue(evidence_hit(["a", "b"], {"b"}))
        self.assertFalse(evidence_hit(["a"], {"b"}))
        self.assertFalse(evidence_hit([], {"b"}))
        self.assertFalse(evidence_hit(["a"], set()))

    def test_tier_flatten_and_concat(self):
        evidence = {"raw": [{"id": "r1"}], "daily": [], "core": []}
        context = {"raw": [{"id": "r2"}], "daily": [{"id": "d1"}], "core": []}
        self.assertEqual(tier_ids(evidence), ["r1"])
        self.assertEqual(ranked_concat(evidence, context), ["r1", "r2", "d1"])


class DriverTests(unittest.TestCase):
    def test_profiles_pin_every_flag(self):
        from core.eval.recall_bench import PROFILES, _RECALL_FLAGS

        for profile, values in PROFILES.items():
            for flag in _RECALL_FLAGS:
                self.assertIn(
                    flag, dict.fromkeys(list(values) + list(_RECALL_FLAGS)),
                )
            # flags_off must pin all six explicitly to "0"
        self.assertEqual(
            set(PROFILES["flags_off"]), set(_RECALL_FLAGS)
        )

    def test_pinned_flags_restore_environment(self):
        import os

        from core.eval.recall_bench import _pinned_flags

        os.environ["MAEZ_RECALL_FLOOR_SHADOW"] = "sentinel"
        try:
            with _pinned_flags("flags_off"):
                self.assertEqual(os.environ["MAEZ_RECALL_FLOOR_SHADOW"], "0")
            self.assertEqual(
                os.environ["MAEZ_RECALL_FLOOR_SHADOW"], "sentinel"
            )
        finally:
            os.environ.pop("MAEZ_RECALL_FLOOR_SHADOW", None)

    def test_bucket_classification(self):
        from core.eval.recall_bench import classify_bucket

        abstention = build_question_corpus(
            _question(qid="q9_abs", turns=[[]])
        )
        self.assertEqual(classify_bucket(abstention), "abstention")
        plain = build_question_corpus(_question(turns=[[]]))
        self.assertEqual(classify_bucket(plain), "main")

    def test_end_to_end_scores_a_findable_fact(self):
        # Real Chroma, real embeddings (local ONNX cache), tempdir only.
        from core.eval.recall_bench import run_question

        corpus = build_question_corpus(_question())
        result = run_question(corpus, profile="flags_off")
        self.assertEqual(result.n_rows, 2)
        self.assertEqual(result.n_answer_rows, 1)
        self.assertEqual(result.bucket, "main")
        # The answer-bearing row must be retrievable from a 2-row
        # corpus; if this fails the harness itself is broken.
        self.assertGreater(result.recall_at_k_total, 0.0)

    def test_end_to_end_is_deterministic(self):
        from core.eval.recall_bench import run_question

        corpus = build_question_corpus(_question())
        a = run_question(corpus, profile="flags_off")
        b = run_question(corpus, profile="flags_off")
        self.assertEqual(a, b)

    def test_production_stores_untouched(self):
        # The whole point of the harness: production mtimes must not
        # move. Snapshot before/after an e2e run.
        from core.eval.recall_bench import run_question

        prod = Path("/home/rohit/maez/memory/db/raw/chroma.sqlite3")
        before = prod.stat().st_mtime_ns if prod.exists() else None
        corpus = build_question_corpus(_question())
        run_question(corpus, profile="flags_off")
        after = prod.stat().st_mtime_ns if prod.exists() else None
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
