# Copyright (C) 2026 Rohit Ananthan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cockpit honesty guards: real, honestly empty, or unavailable."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "web" / "cockpit"
SIM = COCKPIT / "sim.jsx"
TERMINAL_UI = COCKPIT / "terminal-ui.jsx"
INDEX = COCKPIT / "index.html"
INNER_UI = COCKPIT / "inner-ui.jsx"
DESIGN_CANVAS = COCKPIT / "design-canvas.jsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CockpitHonestyRealStateTests(unittest.TestCase):
    def test_live_bundle_has_no_realistic_mock_identity_or_chat_seed(self):
        live_bundle = "\n".join(_read(path) for path in (SIM, TERMINAL_UI, INDEX))

        forbidden = [
            "his daughter's name is maya",
            "berkeley, CA",
            "Alienware RGB status",
            "Phenomenology of attention",
            "Weather source unavailable in demo mode",
            "continuity score ticking up",
            "demo conversation until live chat history loads",
            "Live history will replace this demo row",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, live_bundle)

    def test_live_polling_has_no_silent_mock_fallback_contract(self):
        sim = _read(SIM)

        forbidden = [
            "keep the fake data",
            "silent fallback",
            "overlay real numbers on top",
            "fake data (silent fallback)",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, sim)

    def test_owner_truth_polls_do_not_keep_previous_state_on_empty_success(self):
        sim = _read(SIM)

        forbidden_patterns = {
            "empty soul base must replace old state": r"if\s*\(\s*d\.base\s*\)\s*state\.soul\.base\s*=",
            "empty soul local must replace old state": r"if\s*\(\s*d\.local\s*\)\s*state\.soul\.local\s*=",
            "empty dreams must replace old state": r"Array\.isArray\(d\.dreams\)\s*&&\s*d\.dreams\.length",
            "empty router window must replace old state": r"Array\.isArray\(d\.window\)\s*&&\s*d\.window\.length",
            "empty logs must replace old state": r"Array\.isArray\(d\.lines\)\s*&&\s*d\.lines\.length",
            "empty chat sessions must replace old state": r"Array\.isArray\(d\.sessions\)\s*&&\s*d\.sessions\.length",
            "empty scratchpad must replace old state": r"Array\.isArray\(d\.scratchpad\)\s*&&\s*d\.scratchpad\.length",
            "cycle zero must replace old state": r"typeof\s+cycle\s*===\s*'number'\s*&&\s*cycle\s*>\s*0",
        }
        for label, pattern in forbidden_patterns.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, sim))

    def test_dead_daemon_cognition_score_display_removed_but_domain_scores_stay(self):
        live_ui = "\n".join(_read(path) for path in (SIM, TERMINAL_UI, INDEX))

        forbidden = [
            "live daemon score",
            "Cognition score is Maez's own cycle-quality signal",
            "It is not IQ or consciousness",
            "Thinking clearly enough",
            "Thinking carefully",
            "perceive \u2192 reason \u2192 score \u2192 evolve \u2192 message",
            "Rate response",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, live_ui)

        terminal = _read(TERMINAL_UI)
        index = _read(INDEX)
        keep_domain_scores = [
            (terminal, "echo.score"),
            (terminal, "h.score.toFixed(2)"),
            (terminal, "d.score.toFixed(2)"),
            (terminal, "median score"),
            (index, "h.score.toFixed(2)"),
            (index, "d.score.toFixed(2)"),
        ]
        for source, phrase in keep_domain_scores:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, source)

    def test_unused_cockpit_assets_are_explicitly_parked(self):
        for path in (INNER_UI, DESIGN_CANVAS):
            with self.subTest(path=path.name):
                self.assertIn("PARKED 2026-06-29: unused cockpit asset", _read(path))


if __name__ == "__main__":
    unittest.main()
