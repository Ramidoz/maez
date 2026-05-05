# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Schema + distribution guard for the Judge Bakeoff Corpus v1.

The corpus at tests/data/judge_eval_2026_05_05.jsonl is the gate
for choosing a smaller grounding-judge model. Its decision rule
(see README_judge_eval_2026_05_05.md) cites the exact case
distribution. If the JSONL drifts from the README — or loses
required fields — the decision rule is no longer auditable.

This test fails fast on:
  - JSONL parse error
  - missing required field
  - duplicate id
  - distribution drift from the documented counts
"""
from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests" / "data" / "judge_eval_2026_05_05.jsonl"

REQUIRED_FIELDS = frozenset({
    "id", "claim", "signals_present", "signals_absent",
    "expected", "label_source", "source_log", "notes",
})

VALID_EXPECTED = {"grounded", "ungrounded"}
VALID_LABEL_SOURCE = {"human", "prior_judge", "reconstructed"}

# Locked to the README distribution. If the corpus is intentionally
# revised, both the JSONL AND the README must be updated together,
# AND these constants. That coupling is the audit trail.
EXPECTED_TOTAL = 22
EXPECTED_GROUNDED = 7
EXPECTED_UNGROUNDED = 15
EXPECTED_HUMAN = 13
EXPECTED_PRIOR_JUDGE = 9


class JudgeEvalCorpusV1Schema(unittest.TestCase):

    def setUp(self):
        self.assertTrue(
            CORPUS.exists(),
            f"corpus missing at {CORPUS}",
        )
        self.rows = [
            json.loads(line)
            for line in CORPUS.read_text().splitlines()
            if line.strip()
        ]

    def test_total_count_matches_readme(self):
        self.assertEqual(len(self.rows), EXPECTED_TOTAL)

    def test_required_fields_present_on_every_row(self):
        for r in self.rows:
            missing = REQUIRED_FIELDS - r.keys()
            self.assertFalse(
                missing,
                f"row {r.get('id', '<noid>')} missing fields: {missing}",
            )

    def test_ids_are_unique(self):
        ids = [r["id"] for r in self.rows]
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        self.assertFalse(dupes, f"duplicate ids: {dupes}")

    def test_field_value_vocabulary(self):
        for r in self.rows:
            self.assertIn(r["expected"], VALID_EXPECTED, r["id"])
            self.assertIn(r["label_source"], VALID_LABEL_SOURCE, r["id"])
            self.assertIsInstance(r["signals_present"], list, r["id"])
            self.assertIsInstance(r["signals_absent"], list, r["id"])

    def test_expected_distribution_matches_readme(self):
        c = Counter(r["expected"] for r in self.rows)
        self.assertEqual(c["grounded"], EXPECTED_GROUNDED)
        self.assertEqual(c["ungrounded"], EXPECTED_UNGROUNDED)

    def test_label_source_distribution_matches_readme(self):
        c = Counter(r["label_source"] for r in self.rows)
        self.assertEqual(c["human"], EXPECTED_HUMAN)
        self.assertEqual(c["prior_judge"], EXPECTED_PRIOR_JUDGE)


if __name__ == "__main__":
    unittest.main()
