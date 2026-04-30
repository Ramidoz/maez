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


class TestLocalJudge(unittest.TestCase):
    """Local-LLM-as-judge — Session 2 deliverable. Replaces the
    token-overlap recall floor with a binary correctness label so
    aggregate numbers are comparable to the published GPT-4o judge.

    Tests stub the generate function so they're hermetic — no live
    llama-server required."""

    def test_judge_correct_returns_one(self):
        from core.eval.judge import judge_answer

        def fake(_prompt, **_kw):
            return "CORRECT — the prediction names the cat."

        score = judge_answer(
            question="What pet does the user have?",
            reference="a tabby cat named Marble",
            prediction="The user has a tabby cat named Marble.",
            generate_fn=fake,
        )
        self.assertEqual(score, 1)

    def test_judge_incorrect_returns_zero(self):
        from core.eval.judge import judge_answer

        def fake(_prompt, **_kw):
            return "INCORRECT — no mention of a cat."

        score = judge_answer(
            question="What pet does the user have?",
            reference="a tabby cat named Marble",
            prediction="They mentioned the weather.",
            generate_fn=fake,
        )
        self.assertEqual(score, 0)

    def test_judge_treats_unparseable_as_zero(self):
        """A judge that responds with garbage must NOT be counted as
        correct — failing closed is the safe direction for an eval
        report."""
        from core.eval.judge import judge_answer

        def fake(_prompt, **_kw):
            return "uhh I'm not sure honestly"

        score = judge_answer(
            question="x", reference="y", prediction="z",
            generate_fn=fake,
        )
        self.assertEqual(score, 0)

    def test_judge_handles_empty_prediction(self):
        """Empty prediction is unambiguously zero — no generate call
        needed."""
        from core.eval.judge import judge_answer

        called = {"n": 0}

        def fake(_prompt, **_kw):
            called["n"] += 1
            return "CORRECT"

        score = judge_answer(
            question="x", reference="y", prediction="",
            generate_fn=fake,
        )
        self.assertEqual(score, 0)
        self.assertEqual(called["n"], 0)

    def test_judge_recovers_from_generate_failure(self):
        """A backend timeout must not crash the eval driver — return
        None so run_subset can log the skip and continue."""
        from core.eval.judge import judge_answer

        def fake(_prompt, **_kw):
            raise RuntimeError("backend timed out")

        score = judge_answer(
            question="x", reference="y", prediction="z",
            generate_fn=fake,
        )
        self.assertIsNone(score)


class TestRunSubsetAdvanced(unittest.TestCase):
    """Integration coverage for run_subset's with_judge / with_surfaced
    / question_ids paths — added after Session 2 audits flagged that
    the closure that builds judge_fn was untested."""

    def _make_two_question_file(self, td: str) -> Path:
        q1 = _mini_question()
        q2 = dict(_mini_question())
        q2["question_id"] = "synth-002"
        q2["haystack_sessions"] = [
            [{"role": "user", "content": "I saw a falcon in the park."}]
        ]
        q2["haystack_dates"] = ["2026-04-20"]
        p = Path(td) / "qs.json"
        p.write_text(json.dumps([q1, q2]))
        return p

    def test_question_ids_filter_runs_only_matched(self):
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = self._make_two_question_file(td)
            out = run_subset(p, limit=10, question_ids={"synth-002"})
        ids = [r["question_id"] for r in out]
        self.assertEqual(ids, ["synth-002"])

    def test_with_surfaced_includes_recalled_text(self):
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = self._make_two_question_file(td)
            out = run_subset(p, limit=1, with_surfaced=True)
        self.assertIn("surfaced", out[0])
        self.assertNotIn("surfaced", {})  # sanity for the assertion below
        # Without with_surfaced the field must NOT be present.
        with tempfile.TemporaryDirectory() as td:
            p = self._make_two_question_file(td)
            out2 = run_subset(p, limit=1)
        self.assertNotIn("surfaced", out2[0])

    def test_with_judge_calls_judge_and_stamps_score(self):
        """End-to-end: with_judge=True must build the judge_fn closure
        and stamp judge_score on each record. Patches the underlying
        judge_answer to keep the test hermetic."""
        from unittest.mock import patch

        from core.eval import longmemeval as lme

        seen_calls = []

        def fake_judge(*, question, reference, prediction, model=None):
            seen_calls.append((question, reference, prediction, model))
            return 1

        with tempfile.TemporaryDirectory() as td:
            p = self._make_two_question_file(td)
            with patch.object(lme, "_resolve_judge_model",
                              return_value="test-model"), \
                 patch("core.eval.judge.judge_answer", new=fake_judge):
                out = lme.run_subset(p, limit=1, with_judge=True)
        self.assertEqual(out[0]["judge_score"], 1)
        self.assertEqual(len(seen_calls), 1)
        self.assertEqual(seen_calls[0][3], "test-model")

    def test_with_judge_restores_env_var_on_exit(self):
        """Audit fix: MAEZ_LLM_BACKEND override must be scoped to the
        run, never leak to subsequent tests."""
        import os
        from unittest.mock import patch

        from core.eval import longmemeval as lme

        os.environ.pop("MAEZ_LLM_BACKEND", None)
        with tempfile.TemporaryDirectory() as td:
            p = self._make_two_question_file(td)
            with patch.object(lme, "_resolve_judge_model",
                              return_value="m"), \
                 patch("core.eval.judge.judge_answer",
                       return_value=0):
                lme.run_subset(p, limit=1, with_judge=True)
        self.assertNotIn("MAEZ_LLM_BACKEND", os.environ)


class TestModelResolution(unittest.TestCase):
    """The fallback path was silent before the audit; tests pin both
    the OpenAI-canonical lookup and the fallback warning behavior."""

    def test_resolves_from_openai_data_shape(self):
        from unittest.mock import patch

        from core.eval import longmemeval as lme

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return json.dumps(
                    {"data": [{"id": "openai-canonical-model"}]}
                ).encode()

        # urllib's json.load takes a file-like object; provide read().
        def fake_urlopen(url, timeout=5):
            return FakeResp()

        # Patch json.load so it sees our fake response cleanly.
        with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("json.load",
                   return_value={"data": [{"id": "openai-canonical-model"}]}):
            self.assertEqual(
                lme._resolve_judge_model(),
                "openai-canonical-model",
            )

    def test_falls_back_when_lookup_fails(self):
        from unittest.mock import patch

        from core.eval import longmemeval as lme

        with patch("urllib.request.urlopen",
                   side_effect=RuntimeError("no server")):
            # Falls back to the historical default rather than raising.
            self.assertEqual(lme._resolve_judge_model(), "qwen36-27b")


class TestJudgeRegexLoose(unittest.TestCase):
    """Audit fix: judge regex was strict prefix-only; markdown-bold
    or prefixed verdicts were silently scored INCORRECT."""

    def test_markdown_bold_verdict_is_parsed(self):
        from core.eval.judge import judge_answer

        def fake(_p, **_kw):
            return "**CORRECT** — the prediction names the cat."

        score = judge_answer(
            question="x", reference="y", prediction="z",
            generate_fn=fake,
        )
        self.assertEqual(score, 1)

    def test_prefixed_verdict_is_parsed(self):
        from core.eval.judge import judge_answer

        def fake(_p, **_kw):
            return "Verdict: INCORRECT — no match."

        score = judge_answer(
            question="x", reference="y", prediction="z",
            generate_fn=fake,
        )
        self.assertEqual(score, 0)


class TestSynthesizeDailySummaries(unittest.TestCase):
    """Slice 9 Session 3: closing the consolidation fidelity gap.
    The daemon's recall_for_cycle reads core+daily+raw; the benchmark
    was previously feeding raw only, depressing multi-session and
    temporal scores."""

    def test_writes_one_daily_per_session(self):
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
            synthesize_daily_summaries,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            n = synthesize_daily_summaries(h.mm, q)
            daily_count = h.mm.daily.count()
        # _mini_question has 2 sessions → 2 synthetic dailies.
        self.assertEqual(n, 2)
        self.assertEqual(daily_count, 2)

    def test_daily_summary_content_is_user_substantive(self):
        """The synthetic summary must contain user-turn content
        verbatim — that's the substrate recall_for_cycle needs to
        surface for multi-session reasoning."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
            synthesize_daily_summaries,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            synthesize_daily_summaries(h.mm, q)
            got = h.mm.daily.get(include=["documents"])
        joined = " ".join(got["documents"] or [])
        # The pet evidence was a user turn — must reach the daily tier.
        self.assertIn("Marble", joined)

    def test_daily_metadata_carries_session_date(self):
        """Daily entries are dated to their session_idx's haystack
        date — temporal-reasoning recall depends on this."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
            synthesize_daily_summaries,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            synthesize_daily_summaries(h.mm, q)
            got = h.mm.daily.get(include=["metadatas"])
        dates = {m.get("date") for m in (got["metadatas"] or [])}
        self.assertIn("2026-04-01", dates)
        self.assertIn("2026-04-10", dates)

    def test_run_subset_consolidates_by_default(self):
        """End-to-end: run_subset must trigger daily synthesis between
        ingest and recall so the recall layer sees a daily tier."""
        from core.eval.longmemeval import run_subset

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qs.json"
            p.write_text(json.dumps([_mini_question()]))
            results = run_subset(p, limit=1, with_surfaced=True)
        # Surfaced text must include at least the daily-tier reach
        # (the user-turn content), proving the daily layer surfaced.
        self.assertIn("Marble", results[0]["surfaced"])


class TestSession3AuditFixes(unittest.TestCase):
    """Pins behavior the Session 3 audit found unchecked: dedup
    actually firing across the synthetic-prefix gap, and the
    salience picker preferring the longest substantive turn."""

    def test_dedup_collapses_synthetic_and_raw_for_same_turn(self):
        """The fingerprint must strip the '[Session on …] user: '
        prefix so a synthetic daily summary built from a raw turn
        matches that raw turn — otherwise the dedup is a no-op
        (the failure mode the Session 3 audit caught)."""
        from core.eval.longmemeval import _dedup_fingerprint

        raw = "user: I just adopted a tabby cat named Marble."
        synthetic = (
            "[Session on 2026-04-01] user: I just adopted "
            "a tabby cat named Marble."
        )
        self.assertEqual(
            _dedup_fingerprint(raw),
            _dedup_fingerprint(synthetic),
        )

    def test_dedup_keeps_genuinely_different_entries(self):
        """Two entries that share a long common prefix but diverge
        late must NOT collide (length-prefixed fingerprint guards
        against this)."""
        from core.eval.longmemeval import _dedup_fingerprint

        a = "On Monday I went to the store and bought a kettle."
        b = "On Monday I went to the store and bought a hammer."
        self.assertNotEqual(_dedup_fingerprint(a), _dedup_fingerprint(b))

    def test_salience_picker_prefers_longest_substantive_turn(self):
        """Two user turns in one session: the longer one must win
        (audit found this was not pinned)."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            synthesize_daily_summaries,
        )

        q = {
            "question_id": "synth-pick",
            "question": "x",
            "answer": "y",
            "haystack_session_ids": [0],
            "haystack_dates": ["2026-04-01"],
            "haystack_sessions": [[
                {"role": "user", "content": "ok"},
                {"role": "user",
                 "content": "I have a vintage espresso machine"
                            " from 1962."},
            ]],
        }
        with IsolatedMemoryHarness() as h:
            synthesize_daily_summaries(h.mm, q)
            got = h.mm.daily.get(include=["documents"])
        joined = " ".join(got["documents"] or [])
        self.assertIn("vintage espresso machine", joined)
        # The "ok" turn is too short — must not be the picked turn.
        self.assertNotEqual(joined.strip(),
                            "[Session on 2026-04-01] user: ok")

    def test_synthesis_caps_at_600_chars(self):
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            synthesize_daily_summaries,
        )

        long_text = "x" * 1500
        q = {
            "question_id": "synth-cap",
            "question": "x",
            "answer": "y",
            "haystack_session_ids": [0],
            "haystack_dates": ["2026-04-01"],
            "haystack_sessions": [[
                {"role": "user", "content": long_text},
            ]],
        }
        with IsolatedMemoryHarness() as h:
            synthesize_daily_summaries(h.mm, q)
            doc = h.mm.daily.get(include=["documents"])["documents"][0]
        # Full substring won't fit; bounded form must be present.
        self.assertLess(len(doc), 1000)
        self.assertTrue(doc.endswith("…"),
                        f"truncation marker missing: {doc[-20:]!r}")

    def test_recall_dedup_actually_drops_duplicates(self):
        """End-to-end pin: recall_for_question MUST drop a synthetic
        daily entry whose fingerprint matches a raw entry. Removing
        the dedup block should fail this test."""
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            ingest_haystack,
            recall_for_question,
            synthesize_daily_summaries,
        )

        q = _mini_question()
        with IsolatedMemoryHarness() as h:
            ingest_haystack(h.mm, q)
            synthesize_daily_summaries(h.mm, q)
            surfaced = recall_for_question(h.mm, q["question"])
        # Marble appears in raw AND in the synthetic daily summary;
        # post-dedup it must show up exactly once.
        marble_count = sum(1 for s in surfaced if "Marble" in s)
        self.assertEqual(
            marble_count, 1,
            f"dedup did not collapse synthetic+raw: surfaced={surfaced!r}",
        )

    def test_empty_haystack_writes_no_daily_entries(self):
        from core.eval.longmemeval import (
            IsolatedMemoryHarness,
            synthesize_daily_summaries,
        )

        q = {
            "question_id": "synth-empty",
            "question": "x",
            "answer": "y",
            "haystack_session_ids": [],
            "haystack_dates": [],
            "haystack_sessions": [],
        }
        with IsolatedMemoryHarness() as h:
            n = synthesize_daily_summaries(h.mm, q)
            count = h.mm.daily.count()
        self.assertEqual(n, 0)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
