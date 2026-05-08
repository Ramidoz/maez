"""Regression guards for the cockpit real-chat submit path."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


SIM = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "sim.jsx"


class CockpitPushUserTurnTests(unittest.TestCase):
    def test_push_user_turn_returns_defined_turn_object(self) -> None:
        """Submitting from cockpit must not throw before fetch() runs."""
        src = SIM.read_text(encoding="utf-8")
        match = re.search(
            r"pushUserTurn:\s*\(text\)\s*=>\s*\{(?P<body>.*?)\n\s*\},\n\s*pushAssistantTurn:",
            src,
            re.S,
        )
        self.assertIsNotNone(match)
        body = match.group("body")

        self.assertIn("const userTurn =", body)
        self.assertIn("sess.history.push(userTurn)", body)
        self.assertIn("return userTurn;", body)
        self.assertLess(body.index("const userTurn ="), body.index("sess.history.push(userTurn)"))


if __name__ == "__main__":
    unittest.main()
