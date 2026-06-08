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


if __name__ == "__main__":
    unittest.main()
