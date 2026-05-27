from __future__ import annotations

from pathlib import Path
import unittest


class TelegramDispatcherPromptBranchTests(unittest.TestCase):
    def test_dispatcher_marker_set_is_module_constant(self):
        from skills import telegram_voice

        self.assertIsInstance(telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS, tuple)
        self.assertIn("[memory evidence]", telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS)
        self.assertIn("[memory context]", telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS)
        self.assertIn("[fresh evidence]", telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS)
        self.assertIn("[no fresh evidence available:", telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS)
        self.assertIn("[dispatcher refusal:", telegram_voice.DISPATCHER_TRANSCRIPT_MARKERS)

    def test_dispatcher_shaped_jarvis_block_uses_dispatcher_hard_instruction(self):
        from skills import telegram_voice

        prompt = telegram_voice._telegram_hard_instruction_for_jarvis_block(
            "[memory evidence] TELEGRAM_SEMANTIC: remembered context"
        )

        self.assertIn("dispatcher-emitted grounding", prompt)
        self.assertIn("[fresh evidence]", prompt)
        self.assertIn("THIS turn's substrate and external fan-out", prompt)
        self.assertIn("Do not invent internal-architecture descriptions", prompt)
        self.assertNotIn("Memory recall blocks (the [RECALLED MEMORY] section", prompt)

    def test_jarvis_shaped_jarvis_block_uses_existing_jarvis_hard_instruction(self):
        from skills import telegram_voice

        prompt = telegram_voice._telegram_hard_instruction_for_jarvis_block(
            "✓ web_search: found relevant output"
        )

        self.assertIn("How to read the transcript:", prompt)
        self.assertIn("✓ line — the tool RAN", prompt)
        self.assertIn("Memory recall blocks (the [RECALLED MEMORY] section", prompt)
        self.assertNotIn("dispatcher-emitted grounding", prompt)

    def test_empty_jarvis_block_uses_no_tools_ran_branch(self):
        source = Path("skills/telegram_voice.py").read_text(encoding="utf-8")

        self.assertIn("[TURN STATE — NO TOOLS RAN THIS TURN]", source)
        self.assertIn("if jarvis_block:", source)
        self.assertIn("else:\n            # Track A fabrication fix", source)


if __name__ == "__main__":
    unittest.main()
