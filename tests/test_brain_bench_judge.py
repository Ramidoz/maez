import dataclasses
import unittest

from scripts.brain_bench.judge import BlindAnswer, JudgeResult, judge_pairwise


def _answer(probe_id, sample_id, text, evidence="[E1] source"):
    return BlindAnswer(
        probe_id=probe_id,
        sample_id=sample_id,
        answer=text,
        evidence=evidence,
    )


class JudgeShapeTests(unittest.TestCase):
    def test_blind_answer_has_no_variant_label(self):
        names = {field.name for field in dataclasses.fields(BlindAnswer)}
        self.assertNotIn("label", names)
        self.assertNotIn("variant", names)
        self.assertIn("sample_id", names)

    def test_judge_result_cannot_gate(self):
        names = {field.name for field in dataclasses.fields(JudgeResult)}
        for gating in ("hard_pass", "fail", "gate", "screen_result", "passes"):
            self.assertNotIn(gating, names)


class PairwiseJudgeTests(unittest.TestCase):
    def test_no_label_reaches_prompt(self):
        prompts = []

        def call_judge(*, axis, first, second, prompt):
            prompts.append(prompt)
            return "A"

        judge_pairwise(
            {
                "secret-fast-model": (_answer("p", "s1", "A"),),
                "secret-slow-model": (_answer("p", "s1", "B"),),
            },
            call_judge=call_judge,
            seed=7,
        )

        joined = "\n".join(prompts)
        self.assertNotIn("secret-fast-model", joined)
        self.assertNotIn("secret-slow-model", joined)

    def test_counterbalanced_both_orders_issued_for_each_axis(self):
        calls = []

        def call_judge(*, axis, first, second, prompt):
            calls.append((axis, first.answer, second.answer))
            return "A"

        judge_pairwise(
            {"v1": (_answer("p", "s1", "left"),), "v2": (_answer("p", "s1", "right"),)},
            call_judge=call_judge,
            seed=1,
        )

        self.assertCountEqual(
            calls,
            [
                ("quality", "left", "right"),
                ("quality", "right", "left"),
                ("voice", "left", "right"),
                ("voice", "right", "left"),
            ],
        )

    def test_groups_by_probe_and_sample_id(self):
        calls = []

        def call_judge(*, axis, first, second, prompt):
            calls.append((axis, first.sample_id, first.answer, second.answer))
            return "TIE"

        judge_pairwise(
            {
                "v1": (_answer("p", "s1", "v1s1"), _answer("p", "s2", "v1s2")),
                "v2": (_answer("p", "s1", "v2s1"), _answer("p", "s2", "v2s2")),
            },
            call_judge=call_judge,
            seed=1,
        )

        self.assertEqual(len(calls), 8)
        self.assertTrue(all(left[-2:] != ("v1s1", "v2s2") for left in calls))
        self.assertTrue(all(left[-2:] != ("v1s2", "v2s1") for left in calls))

    def test_tie_and_invalid_score_no_win_but_count_games(self):
        verdicts = iter(["TIE", "INVALID", "nonsense", "B"])

        def call_judge(*, axis, first, second, prompt):
            return next(verdicts)

        result = judge_pairwise(
            {"v1": (_answer("p", "s1", "left"),), "v2": (_answer("p", "s1", "right"),)},
            call_judge=call_judge,
            seed=1,
        )

        self.assertEqual(result.quality_games, 2)
        self.assertEqual(result.voice_games, 2)
        self.assertEqual(result.quality_winrate["v1"], 0.0)
        self.assertEqual(result.quality_winrate["v2"], 0.0)
        self.assertEqual(result.voice_winrate["v1"], 0.5)
        self.assertEqual(result.voice_winrate["v2"], 0.0)
        self.assertEqual(result.invalid_verdicts, 2)


if __name__ == "__main__":
    unittest.main()
