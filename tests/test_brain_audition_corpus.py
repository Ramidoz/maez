import json
import unittest
from pathlib import Path


_CORPUS = Path(__file__).parent / "data" / "brain_audition_probes_v1.jsonl"


def load_probes():
    return [json.loads(l) for l in _CORPUS.read_text().splitlines() if l.strip()]


class CorpusSchema(unittest.TestCase):
    def test_strata_and_core_expecteds(self):
        rows = load_probes()
        strata = {r["stratum"] for r in rows}
        self.assertEqual(strata, {"core_invariant", "voice", "reasoning", "multimodal"})
        dims = {r["dimension"] for r in rows if r["stratum"] == "core_invariant"}
        self.assertEqual(dims, {"honesty", "genderless", "safety_floor", "capacity_to_refuse"})
        for r in rows:
            if r["stratum"] == "core_invariant":
                self.assertIn(r["expected"], ("must_not_fabricate", "no_gendered_pronouns", "must_refuse"))
