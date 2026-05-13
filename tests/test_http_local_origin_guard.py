# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Seatbelt regression tests for local HTTP write surfaces.

The daemon and cockpit are bound to loopback, but browsers can still
send cross-origin requests to localhost. The guard therefore permits
owner-local origins and non-browser local clients, while rejecting
browser requests from arbitrary sites.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class LocalOriginPolicyTests(unittest.TestCase):
    def test_loopback_origins_are_trusted(self):
        from core.infra.http_security import is_trusted_loopback_origin

        self.assertTrue(is_trusted_loopback_origin("http://127.0.0.1:11437"))
        self.assertTrue(is_trusted_loopback_origin("http://localhost:11435/dashboard"))
        self.assertTrue(is_trusted_loopback_origin("http://[::1]:11437/app"))

    def test_external_and_null_origins_are_rejected(self):
        from core.infra.http_security import is_trusted_loopback_origin

        self.assertFalse(is_trusted_loopback_origin("https://evil.example"))
        self.assertFalse(is_trusted_loopback_origin("null"))
        self.assertFalse(is_trusted_loopback_origin("file://local"))

    def test_cors_header_echoes_only_trusted_origin(self):
        from core.infra.http_security import cors_allow_origin

        self.assertEqual(
            cors_allow_origin("http://127.0.0.1:11437"),
            "http://127.0.0.1:11437",
        )
        self.assertIsNone(cors_allow_origin("https://evil.example"))
        self.assertIsNone(cors_allow_origin(None))


class SourcePins(unittest.TestCase):
    def test_daemon_uses_local_origin_guard_and_no_wildcard_cors(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        self.assertIn("reject_untrusted_browser_write", src)
        self.assertIn("apply_local_cors_headers", src)
        self.assertNotIn('Access-Control-Allow-Origin"] = "*"', src)

    def test_web_uses_local_origin_guard_and_no_wildcard_cors(self):
        src = (_REPO / "skills" / "web_interface.py").read_text()
        self.assertIn("reject_untrusted_browser_write", src)
        self.assertIn("apply_local_cors_headers", src)
        self.assertNotIn('Access-Control-Allow-Origin"] = "*"', src)


if __name__ == "__main__":
    unittest.main()
