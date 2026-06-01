import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
