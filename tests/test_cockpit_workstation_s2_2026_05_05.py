"""Workstation v1 / Session 2 source guards.

Session 1 made /cockpit structurally safe: browser -> maez-web only.
Session 2 changes the information architecture: chat remains center,
the right rail explains the selected reply, and the left rail shows a
compact Maez Now view instead of only a service/debug summary.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "cockpit" / "index.html"
TERMINAL_UI = ROOT / "web" / "cockpit" / "terminal-ui.jsx"


class CockpitWorkstationSession2Test(unittest.TestCase):
    def test_chat_pane_accepts_selected_turn_callbacks(self) -> None:
        src = TERMINAL_UI.read_text()

        self.assertIn(
            "function ChatPane({ tall, showSidebar = true, selectedTurn, onSelectTurn })",
            src,
        )
        self.assertIn("onSelectTurn?.(", src)
        self.assertIn("selected={selectedTurn?.key === key}", src)
        self.assertIn("Inspect why Maez said this", src)

    def test_chat_messages_are_clickable_only_for_maez_replies(self) -> None:
        src = TERMINAL_UI.read_text()

        self.assertIn("function ChatMessage({ m, selected = false, onSelect })", src)
        self.assertIn("role: 'assistant'", src)
        self.assertIn("cursor: onSelect ? 'pointer' : 'default'", src)

    def test_right_rail_is_why_reply_not_three_debug_panes(self) -> None:
        src = INDEX.read_text()

        self.assertIn("function WhyReplyPane({ selectedTurn })", src)
        self.assertIn("/api/v1/turn/latest", src)
        self.assertIn("Why this reply", src)

        right_rail = re.search(r"\{/\* right rail \*/\}(.*?)\n\s*</div>\n\s*</div>\n\s*\);", src, re.S)
        self.assertIsNotNone(right_rail)
        rail_src = right_rail.group(1)
        self.assertIn("<WhyReplyPane selectedTurn={selectedTurn} />", rail_src)
        self.assertNotIn("<ReadinessPane compact />", rail_src)
        self.assertNotIn("<DaemonPane compact />", rail_src)
        self.assertNotIn("<SignalsPane compact />", rail_src)

    def test_left_rail_contains_maez_now_summary(self) -> None:
        src = INDEX.read_text()

        self.assertIn("function MaezNowRail()", src)
        self.assertIn("/api/v1/now", src)
        self.assertIn("Maez Now", src)
        self.assertIn("<MaezNowRail />", src)

    def test_session_two_does_not_remove_expert_surfaces(self) -> None:
        src = INDEX.read_text()

        for surface in (
            "memory",
            "soul",
            "signals",
            "router",
            "daemon",
            "dreams",
            "judgment",
        ):
            self.assertIn(f"id: '{surface}'", src)


if __name__ == "__main__":
    unittest.main()
