from __future__ import annotations

from pathlib import Path
import unittest


class DaemonModeAWiring(unittest.TestCase):
    def setUp(self):
        self.src = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")

    def test_empty_search_flag_computed(self):
        self.assertIn("_empty_web_search", self.src)
        self.assertIn("is_empty_search_result", self.src)

    def test_false_premise_block_guarded_on_empty(self):
        self.assertIn("if web_context and not _empty_web_search:", self.src)

    def test_honest_empty_branch_and_telemetry(self):
        self.assertIn('"honest_empty"', self.src)
        self.assertIn("build_honest_empty_reply", self.src)
        self.assertIn("honest_empty_reply", self.src)


class VoiceModeBWiring(unittest.TestCase):
    def setUp(self):
        self.src = Path("skills/telegram_voice.py").read_text(encoding="utf-8")

    def test_detects_empty_search(self):
        self.assertIn("is_empty_search_result", self.src)
        self.assertIn("_tv_empty_search", self.src)

    def test_routes_to_honest_empty(self):
        self.assertIn("build_honest_empty_reply", self.src)


if __name__ == "__main__":
    unittest.main()
