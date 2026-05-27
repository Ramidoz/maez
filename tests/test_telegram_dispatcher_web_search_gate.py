from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest import mock


class TelegramDispatcherWebSearchGateTests(unittest.TestCase):
    def test_pipeline_a_web_search_gate_follows_dispatcher_flag(self):
        from skills import telegram_voice

        with mock.patch.dict(os.environ, {"MAEZ_DISPATCHER_ENABLED": "1"}, clear=False):
            self.assertFalse(telegram_voice._telegram_pipeline_a_web_search_enabled())

        with mock.patch.dict(os.environ, {"MAEZ_DISPATCHER_ENABLED": "0"}, clear=False):
            self.assertTrue(telegram_voice._telegram_pipeline_a_web_search_enabled())

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(telegram_voice._telegram_pipeline_a_web_search_enabled())

    def test_pipeline_a_needs_web_search_is_gated_under_dispatcher_flag(self):
        source = Path("skills/telegram_voice.py").read_text(encoding="utf-8")

        self.assertIn(
            "if _telegram_pipeline_a_web_search_enabled() and needs_web_search(user_text):",
            source,
        )


if __name__ == "__main__":
    unittest.main()
