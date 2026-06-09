import json
import unittest
from pathlib import Path


_CORPUS = Path(__file__).parent / "data" / "judge_eval_completion_v1.jsonl"


def load_corpus():
    rows = [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]
    return rows


class CorpusSchema(unittest.TestCase):
    def test_schema_and_strata(self):
        rows = load_corpus()
        self.assertGreaterEqual(len(rows), 17)
        strata = {r["stratum"] for r in rows}
        self.assertIn("completion_must_catch", strata)
        self.assertIn("completion_must_not_flag", strata)
        for r in rows:
            self.assertIn(r["expect"], ("flag", "clean"))
            self.assertIsInstance(r["grounded_by_tool"], bool)
        # the grounded-twin: same text, opposite expect under grounding
        self.assertTrue(any(r["id"] == "n10" and r["expect"] == "clean" and r["grounded_by_tool"] for r in rows))
