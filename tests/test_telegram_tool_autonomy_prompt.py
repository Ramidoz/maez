#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Rohit Ananthan

from pathlib import Path
import unittest


_REPO = Path(__file__).resolve().parents[1]


class TelegramToolAutonomyPrompt(unittest.TestCase):
    def test_no_tool_turn_does_not_imply_surface_lacks_tools(self):
        src = (_REPO / "skills" / "telegram_voice.py").read_text()
        self.assertIn("THIS TURN ONLY", src)
        self.assertIn("does not mean this Telegram surface", src)
        self.assertIn("lacks tools or that you lack a tool loop", src)
        self.assertIn("Do not say", src)
        self.assertIn("you are stuck in chat", src)
        self.assertIn("cannot execute tools from here", src)
        self.assertIn("need the action loop wired into this channel", src)

    def test_no_tool_self_denial_phrases_are_forbidden(self):
        src = (_REPO / "skills" / "telegram_voice.py").read_text()
        self.assertIn("I can't execute tools from here", src)
        self.assertIn("I don't have a tool loop on this channel", src)
        self.assertIn("I'm stuck in this chat surface", src)
        self.assertIn("the action loop needs to be wired into this channel", src)


if __name__ == "__main__":
    unittest.main()
