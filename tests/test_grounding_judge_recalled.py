import os
import unittest

from core.cognition.grounding_judge import (
    _BUILTIN_FEW_SHOTS,
    _build_judge_prompt,
    judge,
)


class RecalledAsPresentFewShot(unittest.TestCase):
    def test_builtin_fewshot_covers_recalled_value_as_present(self):
        texts = {shot.get("text") for shot in _BUILTIN_FEW_SHOTS}
        self.assertIn("still generating errors", texts)
        self.assertIn("the disk is at 92%", texts)

    def test_recalled_value_fewshot_renders_into_prompt(self):
        prompt = _build_judge_prompt(
            text="The disk is at 92% right now.",
            signals_present=[],
            signals_absent=["system_stats"],
            few_shots=[],
        )
        self.assertIn("still generating errors", prompt)
        self.assertIn("the disk is at 92%", prompt)
        self.assertIn("recalled", prompt.lower())


@unittest.skipUnless(os.environ.get("MAEZ_JUDGE_LIVE") == "1", "live judge integration")
class RecalledAsPresentLive(unittest.TestCase):
    def test_recalled_value_as_present_is_flagged(self):
        ungrounded = judge(
            text="The disk is at 92% right now.",
            signals_present=[],
            signals_absent=["system_stats"],
        )
        self.assertTrue(any("92%" in (u.get("text", "")) for u in ungrounded))


if __name__ == "__main__":
    unittest.main()
