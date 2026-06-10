import unittest

from core.evolution.brain_audition.scorer import (
    score_latency,
    score_reasoning,
    score_voice_drift,
)


class BrainAuditionScorerTests(unittest.TestCase):
    def test_latency_scores_percentiles_and_mean(self):
        score = score_latency([0.1, 0.2, 0.3, 0.4])

        self.assertAlmostEqual(score["p50"], 0.25, places=2)
        self.assertIn("p95", score)
        self.assertAlmostEqual(score["mean"], 0.25, places=2)

    def test_reasoning_correct_rate_uses_expected_presence_in_integrated_output(self):
        rows = [
            {"expected": "15:45", "integrated_output": "15:45"},
            {"expected": "10:00", "integrated_output": "nope"},
        ]

        self.assertEqual(score_reasoning(rows)["correct_rate"], 0.5)

    def test_voice_drift_is_informational_only(self):
        score = score_voice_drift([("hi", "hello")], voice_judge=lambda a, b: 0.7)

        authority_keys = {
            "recommendation",
            "swap_decision",
            "hard_gate",
            "veto",
            "decision",
            "passed",
        }

        self.assertEqual(score["mean_similarity"], 0.7)
        self.assertEqual(set(score), {"mean_similarity", "note"})
        self.assertIn("informational only", score["note"])
        self.assertTrue(authority_keys.isdisjoint(score))


if __name__ == "__main__":
    unittest.main()
