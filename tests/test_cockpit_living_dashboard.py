# Copyright (C) 2026 Rohit Ananthan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression checks for the browser-served cockpit prototype."""

from pathlib import Path
import unittest


COCKPIT_INDEX = Path(__file__).resolve().parents[1] / "web" / "cockpit" / "index.html"


class CockpitLivingDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = COCKPIT_INDEX.read_text(encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
