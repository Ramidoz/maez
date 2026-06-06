from __future__ import annotations

import unittest
from pathlib import Path

from core.body.desktop_presence_state import sample_desktop_presence


class DesktopPresenceHealthTests(unittest.TestCase):
    def test_default_disabled_health_shape(self):
        health = sample_desktop_presence({}).to_health()
        self.assertEqual(health["sensor_state"], "disabled")
        self.assertIsNone(health["app_class"])
        self.assertEqual(
            set(health.keys()),
            {"schema_version", "sensor_state", "app_class", "reason", "age_seconds"},
        )

    def test_enabled_unavailable_is_content_free(self):
        health = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"},
            availability_fn=lambda: ("unavailable", "wayland"),
        ).to_health()
        self.assertEqual(health["sensor_state"], "unavailable")
        self.assertEqual(health["reason"], "wayland")
        self.assertIsNone(health["app_class"])

    def test_daemon_body_health_threads_desktop_field(self):
        src = Path("daemon/maez_daemon.py").read_text()
        self.assertIn("sample_desktop_presence", src)
        self.assertIn("def _desktop_presence_health", src)
        self.assertIn('"desktop": {', src)
        self.assertIn("_desktop_presence = self._desktop_presence_health()", src)
        self.assertIn("desktop_presence=_desktop_presence", src)


if __name__ == "__main__":
    unittest.main()
