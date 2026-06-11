import time
import unittest

from core.cognition import grounding_shadow as gs
from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED, UNSUPPORTED


CLAIMABLE = [
    {
        "text": "f",
        "provenance": "memory",
        "evidence": "The recall flip was a No-Go on latency.",
    }
]


class SplitTests(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(gs.split_sentences("A b. C d! E f?"), ["A b.", "C d!", "E f?"])

    def test_split_empty(self):
        self.assertEqual(gs.split_sentences("   "), [])


class ComputeTests(unittest.TestCase):
    def test_no_claimable_calls_no_verifier(self):
        v = FakeSupportVerifier()
        out = gs.compute_shadow("A sentence.", [], v)
        self.assertEqual(out["status"], "no_claimable")
        self.assertEqual(v.calls, [])

    def test_no_sentences(self):
        out = gs.compute_shadow("   ", CLAIMABLE, FakeSupportVerifier())
        self.assertEqual(out["status"], "no_sentences")

    def test_ok_runs_per_sentence(self):
        v = FakeSupportVerifier(default=(SUPPORTED, 0.9))
        out = gs.compute_shadow("One. Two.", CLAIMABLE, v)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["sentences"]), 2)
        self.assertEqual(out["sentences"][0]["verdict"], SUPPORTED)

    def test_budget_exceeded_stops_and_counts(self):
        v = FakeSupportVerifier(sleep_s=0.2)
        out = gs.compute_shadow("One. Two. Three.", CLAIMABLE, v, per_job_budget_s=0.25)
        self.assertEqual(out["status"], "budget_exceeded")
        self.assertGreaterEqual(out["remaining_count"], 1)
        self.assertLess(out["shadowed_count"], 3)

    def test_verifier_error_marks_unavailable(self):
        v = FakeSupportVerifier(raises=RuntimeError("boom"))
        out = gs.compute_shadow("One.", CLAIMABLE, v)
        self.assertEqual(out["status"], "verifier_unavailable")


if __name__ == "__main__":
    unittest.main()
