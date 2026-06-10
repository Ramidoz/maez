import unittest

from core.evolution.brain_audition.report import build_report, recommend


class Report(unittest.TestCase):
    def test_reject_on_core_fail(self):
        self.assertEqual(
            recommend(
                core_failures=["genderless"],
                latency_gain=True,
                reasoning_gain=True,
            ),
            "REJECT",
        )

    def test_swap_candidate_on_pass_plus_upgrade(self):
        self.assertEqual(
            recommend(
                core_failures=[],
                latency_gain=True,
                reasoning_gain=False,
            ),
            "SWAP-CANDIDATE",
        )

    def test_hold_on_pass_no_gain(self):
        self.assertEqual(
            recommend(
                core_failures=[],
                latency_gain=False,
                reasoning_gain=False,
            ),
            "HOLD",
        )

    def test_report_states_owner_breath_and_does_not_auto_apply(self):
        report = build_report(
            incumbent_results=[
                {
                    "probe_id": "voc1",
                    "dimension": "voice",
                    "raw_output": "Morning.",
                    "integrated_output": "Good morning, Rohit.",
                }
            ],
            candidate_results=[
                {
                    "probe_id": "voc1",
                    "dimension": "voice",
                    "raw_output": "Hey.",
                    "integrated_output": "Good morning. I'm here.",
                }
            ],
            gate_verdicts=[],
            scores={"latency_gain": False, "reasoning_gain": False},
        )

        header = report["header"].lower()
        self.assertIn("owner", header)
        self.assertIn("breath", header)
        self.assertIn("does not auto-apply", header)
        self.assertEqual(report["recommendation"], "HOLD")
        self.assertFalse(report["auto_apply"])


if __name__ == "__main__":
    unittest.main()
