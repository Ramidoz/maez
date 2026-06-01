import unittest
from unittest import mock
from pathlib import Path

from core.routing.cancellable_brain_call import BrainPreempted


class PreemptPropagationTest(unittest.TestCase):
    def test_audit_summarizer_does_not_swallow_brain_preempted(self):
        from core.cognition import audit

        with mock.patch.object(audit.llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                audit._summarize("payload", "nonce")

    def test_audit_judge_does_not_swallow_brain_preempted(self):
        from core.cognition import audit

        with mock.patch.object(audit.llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                audit._judge("summary", "payload", "nonce")

    def test_grounding_judge_does_not_convert_preempt_to_unavailable(self):
        from core.cognition import grounding_judge

        with (
            mock.patch.object(grounding_judge, "_JUDGE_BASE_URL", ""),
            mock.patch.object(grounding_judge._llm_client, "chat", side_effect=BrainPreempted),
        ):
            with self.assertRaises(BrainPreempted):
                grounding_judge.judge(
                    text="answer",
                    signals_present=[],
                    signals_absent=[],
                    few_shots=[],
                )

    def test_wondering_cycle_does_not_turn_preempt_into_empty_string(self):
        from daemon import wondering_cycle

        with mock.patch.object(wondering_cycle._llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                wondering_cycle._call_llm("system", "user", 8, "m")

    def test_daemon_reasoning_model_preempt_yields_cycle_without_optional_brain_work(self):
        src = (
            Path(__file__).resolve().parents[1] / "daemon" / "maez_daemon.py"
        ).read_text()
        block = src[
            src.index('self._mark_cycle_stage("reasoning_model")')
            : src.index('self._mark_cycle_stage("threshold_alerts")')
        ]

        self.assertIn("except BrainPreempted:", block)
        self.assertIn("cycle_preempted = True", block)
        self.assertIn("if not cycle_preempted", block)
        self.assertLess(
            block.index("except BrainPreempted:"),
            block.index("except Exception"),
        )


if __name__ == "__main__":
    unittest.main()
