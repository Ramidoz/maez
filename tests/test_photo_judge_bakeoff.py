import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "data" / "judge_eval_photo_contradiction_v1.jsonl"

STRATA = {
    "real_anchor", "numeric_ocr", "entity_title",
    "grounded_control", "uncertainty_control",
}


class CorpusSchema(unittest.TestCase):
    def setUp(self):
        from scripts.photo_judge_bakeoff import load_corpus
        self.rows = load_corpus(str(CORPUS))

    def test_required_fields_and_enums(self):
        for r in self.rows:
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                self.assertIn(f, r, f"{r.get('id')} missing {f}")
            self.assertIn(r["stratum"], STRATA, r["id"])
            self.assertIn(r["expected"], {"grounded", "contradicts"}, r["id"])
            self.assertIsInstance(r["must_catch"], bool, r["id"])

    def test_all_five_strata_present_from_field(self):
        seen = {r["stratum"] for r in self.rows}   # read from FIELD, never inferred
        self.assertEqual(seen, STRATA)

    def test_wwdc_anchor_present_and_must_catch(self):
        anchors = [r for r in self.rows if r["stratum"] == "real_anchor"]
        self.assertTrue(anchors)
        wwdc = [r for r in anchors if "wwdc" in r["id"].lower()]
        self.assertTrue(wwdc, "WWDC2024 anchor case must exist")
        self.assertTrue(wwdc[0]["must_catch"])
        self.assertEqual(wwdc[0]["expected"], "contradicts")

    def test_has_grounded_and_uncertainty_controls(self):
        exp = {r["expected"] for r in self.rows}
        self.assertIn("grounded", exp)  # false-flag guard exists
        self.assertGreaterEqual(
            sum(1 for r in self.rows if r["stratum"] == "uncertainty_control"), 1)


class ThresholdProtocol(unittest.TestCase):
    def test_grid_is_fixed_and_shared(self):
        from scripts.photo_judge_bakeoff_adapters import THRESHOLD_GRID
        self.assertEqual(THRESHOLD_GRID, (0.3, 0.4, 0.5, 0.6, 0.7))

    def test_score_maps_to_label_via_threshold(self):
        from scripts.photo_judge_bakeoff_adapters import score_to_label
        # convention: HIGHER score = more grounded; below threshold = contradicts
        self.assertEqual(score_to_label(0.8, 0.5), "grounded")
        self.assertEqual(score_to_label(0.2, 0.5), "contradicts")
        self.assertEqual(score_to_label(0.5, 0.5), "grounded")  # >= is grounded

    def test_verdict_carries_fields(self):
        from scripts.photo_judge_bakeoff_adapters import Verdict
        v = Verdict(label="contradicts", score=0.1, latency_s=0.02)
        self.assertEqual(v.label, "contradicts")
        self.assertEqual(v.score, 0.1)
        self.assertEqual(v.latency_s, 0.02)


class AdapterBase(unittest.TestCase):
    def test_predict_applies_threshold_and_times(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter, Verdict

        class FakeScore(CandidateAdapter):
            name = "fake"
            score_based = True
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return 0.2  # low → contradicts

        a = FakeScore(threshold=0.5)
        v = a.predict("p", "h")
        self.assertIsInstance(v, Verdict)
        self.assertEqual(v.label, "contradicts")
        self.assertGreaterEqual(v.latency_s, 0.0)

    def test_unavailable_on_load_failure(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class Broken(CandidateAdapter):
            name = "broken"
            score_based = True
            def _load(self): raise RuntimeError("no weights")
            def _raw_predict(self, premise, hypothesis): return 0.9

        a = Broken(threshold=0.5)
        v = a.predict("p", "h")
        self.assertEqual(v.label, "unavailable")
        self.assertIn("no weights", a.unavailable_reason)


class ConcreteAdapters(unittest.TestCase):
    def test_all_adapters_registered(self):
        from scripts.photo_judge_bakeoff_adapters import ALL_ADAPTERS
        names = {a.name for a in ALL_ADAPTERS}
        self.assertEqual(names, {
            "hhem", "minicheck", "thinkncheck", "nli", "reranker", "chatjudge"})

    def test_score_based_vs_label_native_flags(self):
        from scripts.photo_judge_bakeoff_adapters import (
            HHEMAdapter, RerankerAdapter, NLIAdapter,
            MiniCheckAdapter, ThinknCheckAdapter, ChatJudgeAdapter)
        self.assertTrue(HHEMAdapter.score_based)
        self.assertTrue(RerankerAdapter.score_based)
        self.assertTrue(NLIAdapter.score_based)
        self.assertFalse(MiniCheckAdapter.score_based)   # label-native 0/1
        self.assertFalse(ThinknCheckAdapter.score_based) # verdict
        self.assertFalse(ChatJudgeAdapter.score_based)   # yes/no

    def test_hhem_low_score_is_contradiction(self):
        from scripts.photo_judge_bakeoff_adapters import HHEMAdapter
        # Patch _load at the CLASS level BEFORE instantiation so __init__'s
        # _load() never imports transformers or touches disk.
        with mock.patch.object(HHEMAdapter, "_load", return_value=object()), \
             mock.patch.object(HHEMAdapter, "_raw_predict", return_value=0.05):
            a = HHEMAdapter(threshold=0.5)
            self.assertEqual(a.predict("p", "h").label, "contradicts")

    def test_minicheck_label_native(self):
        from scripts.photo_judge_bakeoff_adapters import MiniCheckAdapter
        with mock.patch.object(MiniCheckAdapter, "_load", return_value=object()), \
             mock.patch.object(MiniCheckAdapter, "_raw_predict",
                               return_value="contradicts"):
            a = MiniCheckAdapter()
            v = a.predict("p", "h")
            self.assertEqual(v.label, "contradicts")
            self.assertIsNone(v.score)  # no threshold for label-native


class Aggregator(unittest.TestCase):
    def _rows(self):
        return [
            {"id": "c1", "stratum": "numeric_ocr", "expected": "contradicts", "must_catch": True},
            {"id": "c2", "stratum": "entity_title", "expected": "contradicts", "must_catch": False},
            {"id": "g1", "stratum": "grounded_control", "expected": "grounded", "must_catch": False},
        ]

    def test_catch_falseflag_and_must_catch(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        # verdicts: c1 caught, c2 MISSED (graded grounded), g1 correct
        verdicts = {
            "c1": ("contradicts", 0.10),
            "c2": ("grounded", 0.30),
            "g1": ("grounded", 0.40),
        }
        agg = aggregate_candidate("hhem", rows, verdicts,
                                  meta={"threshold": 0.5})
        self.assertAlmostEqual(agg["catch_rate"], 0.5)        # 1 of 2 contradicts caught
        self.assertEqual(agg["false_flag_rate"], 0.0)         # g1 not flagged
        self.assertEqual(agg["missed_must_catch"], [])        # c1 (must_catch) WAS caught
        self.assertEqual(agg["meta"]["threshold"], 0.5)
        ps = agg["per_stratum"]
        self.assertEqual(ps["numeric_ocr"]["contradiction_n"], 1)
        self.assertEqual(ps["numeric_ocr"]["caught"], 1)
        self.assertEqual(ps["numeric_ocr"]["catch_rate"], 1.0)
        self.assertEqual(ps["entity_title"]["caught"], 0)       # c2 missed
        self.assertEqual(ps["grounded_control"]["grounded_n"], 1)
        self.assertEqual(ps["grounded_control"]["false_flags"], 0)
        self.assertEqual(ps["grounded_control"]["false_flag_rate"], 0.0)

    def test_missed_must_catch_is_loud(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        verdicts = {"c1": ("grounded", 0.9), "c2": ("contradicts", 0.1),
                    "g1": ("grounded", 0.4)}  # c1 is must_catch and MISSED
        agg = aggregate_candidate("x", rows, verdicts, meta={})
        self.assertEqual(agg["missed_must_catch"], ["c1"])

    def test_error_grade_missed_not_false_flag_and_counted(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()  # c1 numeric/contradicts/must, c2 entity/contra, g1 grounded
        verdicts = {"c1": ("error", 0.1),       # contradiction + error → missed
                    "c2": ("contradicts", 0.2),  # caught
                    "g1": ("error", 0.3)}         # grounded + error → NOT a false flag
        agg = aggregate_candidate("x", rows, verdicts, meta={})
        self.assertEqual(agg["error_count"], 2)
        self.assertEqual(agg["catch_rate"], 0.5)        # c2 caught; c1 errored = missed
        self.assertEqual(agg["false_flag_rate"], 0.0)   # g1 error is NOT a false flag
        self.assertIn("c1", agg["missed_must_catch"])   # must_catch + errored = missed
        self.assertEqual(agg["per_stratum"]["grounded_control"]["errors"], 1)

    def test_zero_candidates_report(self):
        from scripts.photo_judge_bakeoff import build_report
        report = build_report([])   # no candidate aggregates
        self.assertIn("RECOMMENDATION: none", report["text"])
        self.assertEqual(report["aggregates"], [])

    def test_unavailable_candidate_in_report(self):
        from scripts.photo_judge_bakeoff import build_report
        agg = {"name": "hhem", "runnable": False,
               "meta": {"unavailable_reason": "no weights"},
               "catch_rate": None, "false_flag_rate": None,
               "missed_must_catch": [], "per_stratum": {}, "latency": {}}
        report = build_report([agg])
        self.assertIn("no weights", report["text"])
        self.assertIn("RECOMMENDATION: none", report["text"])  # 0 runnable


if __name__ == "__main__":
    unittest.main()
