from __future__ import annotations

import re
import unittest
from pathlib import Path


class DesktopPresenceDashboardTests(unittest.TestCase):
    def test_dashboard_has_content_free_desktop_tile(self):
        src = Path("ui/dashboard_local.html").read_text()
        match = re.search(
            r"\['desktop','Desktop','desktop',\s*d=>\{(?P<body>.*?)\n  \}\],",
            src,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "dashboard must expose a Desktop organ tile")
        body = match.group("body")

        self.assertIn("d.app_class", body)
        self.assertIn("d.sensor_state==='disabled'", body)
        self.assertIn("d.sensor_state==='unavailable'", body)
        self.assertIn("d.age_seconds", body)

        forbidden = "Re: confidential salary -- Gmail"
        self.assertNotIn("title", body.lower())
        self.assertNotIn("window", body.lower())
        self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
