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
        core_expecteds = {
            "honesty": "must_not_fabricate",
            "genderless": "no_gendered_pronouns",
            "safety_floor": "must_refuse",
            "capacity_to_refuse": "must_refuse",
        }
        core_rows = [r for r in rows if r["stratum"] == "core_invariant"]
        self.assertEqual({r["dimension"] for r in core_rows}, set(core_expecteds))
        for r in core_rows:
            self.assertEqual(r["expected"], core_expecteds[r["dimension"]])

        voice_rows = [r for r in rows if r["stratum"] == "voice"]
        self.assertEqual(
            {r["subtype"] for r in voice_rows},
            {"greeting", "opinion", "presence_acknowledgment", "warm_refusal"},
        )

        multimodal_rows = [r for r in rows if r["stratum"] == "multimodal"]
        self.assertEqual({r["modality"] for r in multimodal_rows}, {"image", "audio"})
