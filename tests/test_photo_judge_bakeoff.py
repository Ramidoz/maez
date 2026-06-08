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


if __name__ == "__main__":
    unittest.main()
