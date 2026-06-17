"""Regression guards for the cockpit real-chat submit path."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


SIM = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "sim.jsx"
TERMINAL_UI = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "terminal-ui.jsx"
INDEX = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "index.html"


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

    def test_suggestion_pills_use_real_cockpit_submit_path(self) -> None:
        """Quick suggestion buttons must not fall back to the simulator."""
        src = TERMINAL_UI.read_text(encoding="utf-8")

        self.assertIn("const submitText = async (text) =>", src)
        self.assertIn("onClick={() => submitText(s.t)}", src)
        self.assertNotIn("onClick={() => sim.sendMessage(s.t)}", src)

    def test_live_waiting_state_has_no_canned_vram_thinking(self) -> None:
        """The real waiting UI should not claim a VRAM check before the reply."""
        src = TERMINAL_UI.read_text(encoding="utf-8")

        self.assertNotIn("Checking working memory for the rgb context", src)
        self.assertNotIn("VRAM has headroom (1.6GB free)", src)

    def test_cockpit_assets_load_from_bare_and_slash_routes(self) -> None:
        """The /cockpit route must not resolve JSX assets at the web root."""
        src = INDEX.read_text(encoding="utf-8")

        self.assertIn('src="/cockpit/sim.jsx"', src)
        self.assertIn('src="/cockpit/terminal-ui.jsx"', src)
        self.assertNotIn('src="sim.jsx"', src)
        self.assertNotIn('src="terminal-ui.jsx"', src)

    def test_composer_does_not_render_unwired_prototype_controls(self) -> None:
        """The composer should not show knobs that do not affect the live request."""
        src = TERMINAL_UI.read_text(encoding="utf-8")

        self.assertNotIn("Extended Thinking", src)
        self.assertNotIn("ModelMenu", src)
        self.assertNotIn("ToolsMenu", src)
        self.assertNotIn("AttachMenu", src)
        self.assertNotIn("Shell commands", src)
        self.assertNotIn("Claude Opus", src)
        self.assertNotIn("Upload file", src)
        self.assertNotIn("Icon.mic(14)", src)

    def test_composer_shows_read_only_live_body_status(self) -> None:
        """The simplified composer should expose true state instead of fake switches."""
        src = TERMINAL_UI.read_text(encoding="utf-8")

        self.assertIn("Live bridge", src)
        self.assertIn("body state, not a control", src)


if __name__ == "__main__":
    unittest.main()
