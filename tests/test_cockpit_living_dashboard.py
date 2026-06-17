# Copyright (C) 2026 Rohit Ananthan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression checks for the browser-served cockpit prototype."""

from pathlib import Path
import unittest


COCKPIT_INDEX = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "index.html"
COCKPIT_UI = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "terminal-ui.jsx"
COCKPIT_SIM = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "sim.jsx"


class CockpitLivingDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = COCKPIT_INDEX.read_text(encoding="utf-8")
        cls.ui = COCKPIT_UI.read_text(encoding="utf-8")
        cls.sim = COCKPIT_SIM.read_text(encoding="utf-8")

    def test_living_and_technical_modes_are_available(self):
        self.assertIn("function LivingDashboard", self.html)
        self.assertIn("function TechnicalDashboard", self.html)
        self.assertIn("maez.cockpit.dashboardMode", self.html)
        self.assertIn("Technical Door", self.html)

    def test_living_organs_route_to_real_surfaces(self):
        expected_routes = {
            "Heart": "openSurface('daemon')",
            "Senses": "openSurface('signals')",
            "Mind": "openSurface('logs')",
            "Safety": "openSurface('approvals')",
            "Memory": "openSurface('memory')",
            "Voice": "openSurface('chat')",
        }
        for organ, route in expected_routes.items():
            with self.subTest(organ=organ):
                self.assertIn(f'title="{organ}"', self.html)
                self.assertIn(route, self.html)

    def test_living_copy_stays_plain_language_first(self):
        self.assertIn("A simple body map for understanding Maez", self.html)
        self.assertIn("Maez keeps continuity without deleting its past.", self.html)
        self.assertIn("No action should happen without the right boundary.", self.html)

    def test_memory_surface_explains_and_renders_all_tiers(self):
        self.assertIn("Core truths, daily summaries, and raw fragments", self.ui)
        self.assertIn("Always carried: identity, corrections", self.ui)
        self.assertIn("Compressed day summaries", self.ui)
        self.assertIn("Exact fragments", self.ui)
        self.assertIn("h.source", self.ui)

    def test_cognition_score_has_plain_language_explanation(self):
        self.assertIn("function cognitionLabel", self.ui)
        self.assertIn("function cognitionExplanation", self.ui)
        self.assertIn("It is not IQ or consciousness", self.ui)

    def test_living_dashboard_uses_runtime_services_not_active_inactive_flattening(self):
        self.assertIn("runtimeServices", self.sim)
        self.assertIn("state.runtimeServices", self.sim)
        self.assertIn("runtimeServiceEntries", self.html)
        self.assertIn("runtimeServiceStatus", self.html)
        self.assertNotIn("info.status === 'active' ? 'active' : 'inactive'", self.sim)
        self.assertNotIn("services active", self.html)


if __name__ == "__main__":
    unittest.main()
