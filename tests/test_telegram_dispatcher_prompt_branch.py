from __future__ import annotations

from pathlib import Path
import unittest
from unittest import mock


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

    def test_jarvis_block_state_logger_emits_closed_state_and_prefix(self):
        from skills import telegram_voice

        long_dispatcher_block = "[fresh evidence] " + ("x" * 140)

        with mock.patch.object(telegram_voice.logger, "info") as info:
            telegram_voice._telegram_log_jarvis_block_state(
                chat_id="owner-chat",
                jarvis_block=long_dispatcher_block,
            )

        info.assert_called_once()
        message, chat_id, state, prefix = info.call_args.args
        self.assertEqual(message, "telegram_jarvis_block_state chat_id=%s state=%s prefix=%r")
        self.assertEqual(chat_id, "owner-chat")
        self.assertEqual(state, "dispatcher")
        self.assertEqual(len(prefix), 100)
        self.assertTrue(prefix.startswith("[fresh evidence] "))

    def test_jarvis_block_state_logger_classifies_jarvis_and_empty(self):
        from skills import telegram_voice

        with mock.patch.object(telegram_voice.logger, "info") as info:
            telegram_voice._telegram_log_jarvis_block_state(
                chat_id="owner-chat",
                jarvis_block="✓ web_search: result",
            )
            telegram_voice._telegram_log_jarvis_block_state(
                chat_id="owner-chat",
                jarvis_block="",
            )

        states = [call.args[2] for call in info.call_args_list]
        self.assertEqual(states, ["jarvis", "empty"])


if __name__ == "__main__":
    unittest.main()
