# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""LongMemEval adapter tests (Slice 9 — field-standard memory eval).

Adapted from Wu et al. 2024 LongMemEval (arxiv 2410.10813, ICLR 2025,
github xiaowu0162/LongMemEval). Tests use a synthetic mini-fixture so
they never depend on the real ~hundreds-of-MB dataset on disk.

Pipeline under test:
  1. ``load_questions`` reads the official JSON shape.
  2. ``IsolatedMemoryHarness`` spins up a MemoryManager rooted at a
     tmpdir (monkeypatching ``BASE_DB``) so a benchmark run can
     never pollute the live store.
  3. ``ingest_haystack`` converts each session's user/assistant turns
     into raw archive entries, dated to ``haystack_dates``.
  4. ``recall_for_question`` runs Maez's recall path against the
     ingested store and returns the surfaced text.
  5. ``score_answer`` produces a simple substring/token-overlap
     correctness signal. Judge-based scoring is a follow-up — this
     gives a ground-truth-free "did anything from the reference
     answer surface" lower bound.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _mini_question() -> dict:
    """One synthetic question matching the official LongMemEval
    schema. Keeps tests hermetic + fast."""
    return {
        "question_id": "synth-001",
        "question_type": "single-session-user",
        "question": "What pet does the user have?",
        "answer": "a tabby cat named Marble",
        "question_date": "2026-04-15",
        "haystack_session_ids": [0, 1],
        "haystack_dates": ["2026-04-01", "2026-04-10"],
        "haystack_sessions": [
            [
                {"role": "user",
                 "content": "I just adopted a tabby cat named Marble."},
                {"role": "assistant",
                 "content": "Congratulations on the new pet."},
            ],
            [
                {"role": "user",
                 "content": "The weather has been gloomy this week."},
                {"role": "assistant",
                 "content": "Hope it clears up soon."},
            ],
        ],
        "answer_session_ids": [0],
    }


# ── loader ──────────────────────────────────────────────────────────


class TestLoader(unittest.TestCase):
    def test_loads_well_formed_questions(self):
        from core.eval.longmemeval import load_questions

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([_mini_question()]))
            qs = load_questions(p)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0]["question_id"], "synth-001")

    def test_rejects_missing_required_fields(self):
        from core.eval.longmemeval import load_questions

        bad = {"question_id": "x"}  # missing question/answer/haystack
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([bad]))
            with self.assertRaises(ValueError):
                load_questions(p)


# ── isolation harness ───────────────────────────────────────────────


class TestIsolatedHarness(unittest.TestCase):
    """The harness MUST root the MemoryManager at a tmpdir — a stray
    benchmark must never write into the live store."""

    def test_harness_uses_tmpdir_not_live_store(self):
        from core.eval.longmemeval import IsolatedMemoryHarness

        with IsolatedMemoryHarness() as h:
            db_root = Path(h.db_root)
            self.assertTrue(db_root.exists())
            # Must NOT be the live BASE_DB.
            live = Path("/home/rohit/maez/memory/db").resolve()
            self.assertNotEqual(db_root.resolve(), live)
            # Must be inside a tmpdir.
            self.assertIn("tmp", str(db_root).lower())

    def test_harness_restores_base_db_after_exit(self):
        import memory.memory_manager as mm_mod
        from core.eval.longmemeval import IsolatedMemoryHarness

        before = mm_mod.BASE_DB
        with IsolatedMemoryHarness():
            self.assertNotEqual(mm_mod.BASE_DB, before)
        self.assertEqual(mm_mod.BASE_DB, before)


# ── ingest + recall pipeline ────────────────────────────────────────


class TestIngestAndRecall(unittest.TestCase):
    def test_ingest_haystack_writes_one_entry_per_user_turn(self):
        """User turns are the substrate Maez would normally observe.
        Assistant replies are part of the conversational record but
        the question's answer is keyed to user-asserted facts."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            n = ingest_haystack(h.mm, q)
        # Two sessions × two turns each = 4 turns; we ingest the
        # whole conversation, so >= number of user turns.
        self.assertGreaterEqual(n, 2)

    def test_recall_surfaces_relevant_session_content(self):
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
            recall_for_question,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            surfaced = recall_for_question(h.mm, q["question"])
        text = " ".join(surfaced).lower()
        # The recall must surface SOMETHING containing "marble" or
        # "tabby" — the reference signal for this question.
        self.assertTrue(
            "marble" in text or "tabby" in text,
            f"recall did not surface pet evidence: {text[:200]!r}",
        )


# ── scoring ─────────────────────────────────────────────────────────


class TestScorer(unittest.TestCase):
    def test_exact_substring_scores_correct(self):
        from core.eval.longmemeval import score_answer

        score = score_answer(
            reference="a tabby cat named Marble",
            prediction="The user has a tabby cat named Marble at home.",
        )
        self.assertGreaterEqual(score, 0.5)

    def test_unrelated_prediction_scores_low(self):
        from core.eval.longmemeval import score_answer

        score = score_answer(
            reference="a tabby cat named Marble",
            prediction="They mentioned the weather has been gloomy.",
        )
        self.assertLess(score, 0.5)

    def test_empty_prediction_scores_zero(self):
        from core.eval.longmemeval import score_answer

        self.assertEqual(score_answer("anything", ""), 0.0)


# ── end-to-end driver ──────────────────────────────────────────────


class TestRunSubset(unittest.TestCase):
    def test_run_subset_produces_per_question_record(self):
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([_mini_question()]))
            results = run_subset(p, limit=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        for key in ("question_id", "question_type", "score",
                    "surfaced_chars", "answer", "elapsed_s"):
            self.assertIn(key, r)


class TestAuditFixes(unittest.TestCase):
    """Regressions for the parallel-audit pass (temporal backdating,
    schema validation, scorer edges, limit semantics)."""

    def test_haystack_entries_are_backdated_to_session_date(self):
        """Temporal-reasoning questions hinge on entries being dated
        to their haystack_date, not to wall-clock now."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            got = h.mm.raw.get(include=["metadatas"])
        ts_values = [m.get("timestamp", "") for m in (got["metadatas"] or [])]
        self.assertTrue(
            any(ts.startswith("2026-04-01") for ts in ts_values),
            f"no entry dated to first haystack_date; saw {ts_values!r}",
        )
        self.assertTrue(
            any(ts.startswith("2026-04-10") for ts in ts_values),
            f"no entry dated to second haystack_date; saw {ts_values!r}",
        )

    def test_loader_rejects_malformed_haystack_sessions(self):
        from core.eval.longmemeval import load_questions

        bad = dict(_mini_question())
        bad["haystack_sessions"] = "not-a-list"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([bad]))
            with self.assertRaises(ValueError):
                load_questions(p)

    def test_loader_rejects_malformed_haystack_dates(self):
        from core.eval.longmemeval import load_questions

        bad = dict(_mini_question())
        bad["haystack_dates"] = "2026-04-01"  # str, not list
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([bad]))
            with self.assertRaises(ValueError):
                load_questions(p)

    def test_loader_rejects_invalid_json(self):
        from core.eval.longmemeval import load_questions

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text("{not valid json")
            with self.assertRaises(ValueError):
                load_questions(p)

    def test_score_handles_non_string_inputs(self):
        from core.eval.longmemeval import score_answer

        self.assertEqual(score_answer(None, "anything"), 0.0)
        self.assertEqual(score_answer("anything", None), 0.0)
        self.assertEqual(score_answer(123, "anything"), 0.0)

    def test_score_short_answer_substring_fallback(self):
        """Single-token answers ('yes', 'no') tokenize to {} via
        lived_recall's tokenizer (length filter); the scorer must
        still credit their literal presence."""
        from core.eval.longmemeval import score_answer

        # "no" is len-2 but lived_recall._tokenize drops length<=2.
        self.assertEqual(
            score_answer("no", "The answer is no, definitely not."),
            1.0,
        )

    def test_run_subset_limit_zero_returns_empty(self):
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([_mini_question()]))
            self.assertEqual(run_subset(p, limit=0), [])

    def test_run_subset_limit_exceeds_length(self):
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([_mini_question()]))
            # limit >> len → returns all, not crash.
            results = run_subset(p, limit=999)
            self.assertEqual(len(results), 1)

    def test_sequential_harnesses_are_isolated(self):
        """Cross-question contamination check: two back-to-back
        harnesses must not see each other's haystack content."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
        )

        q1 = _mini_question()
        q2 = dict(_mini_question())
        q2["question_id"] = "synth-002"
        q2["haystack_sessions"] = [
            [{"role": "user", "content": "I saw a falcon in the park."}]
        ]
        q2["haystack_dates"] = ["2026-04-20"]

        with IsolatedMemoryHarness() as h1:
            ingest_haystack(h1.mm, q1)
            n1 = h1.mm.raw.count()
        with IsolatedMemoryHarness() as h2:
            # Brand-new harness — q1's content must NOT be visible.
            n_before = h2.mm.raw.count()
            ingest_haystack(h2.mm, q2)
            got = h2.mm.raw.get(include=["documents"])
        self.assertGreater(n1, 0)
        self.assertEqual(n_before, 0)
        docs = " ".join(got["documents"] or [])
        self.assertNotIn("Marble", docs)
        self.assertIn("falcon", docs)


if __name__ == "__main__":
    unittest.main()
