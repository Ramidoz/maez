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
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
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

    def test_pulse_bridge_does_not_reintroduce_wildcard_cors(self):
        src = (_REPO / "ui" / "maez_pulse_bridge.py").read_text()
        self.assertIn("is_trusted_loopback_origin", src)
        self.assertNotIn("Access-Control-Allow-Origin', '*'", src)


class LiveHttpOriginGuardTests(unittest.TestCase):
    def test_real_http_request_rejects_bad_origin_and_echoes_loopback_origin(self):
        from flask import Flask, Response, request
        from werkzeug.serving import make_server

        from core.infra.http_security import (
            apply_local_cors_headers,
            reject_untrusted_browser_write,
        )

        app = Flask(__name__)

        @app.before_request
        def guard():
            return reject_untrusted_browser_write(request)

        @app.after_request
        def cors(response):
            return apply_local_cors_headers(response, request)

        @app.route("/write", methods=["POST", "OPTIONS"])
        def write():
            if request.method == "OPTIONS":
                return Response(status=204)
            return {"ok": True}

        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}/write"
        try:
            bad_req = Request(
                base_url,
                method="OPTIONS",
                headers={"Origin": "https://evil.example"},
            )
            with self.assertRaises(HTTPError) as raised:
                urlopen(bad_req, timeout=5)
            self.assertEqual(raised.exception.code, 403)
            self.assertIn("untrusted_origin", raised.exception.read().decode())
            raised.exception.close()

            good_req = Request(
                base_url,
                method="OPTIONS",
                headers={"Origin": "http://127.0.0.1:11437"},
            )
            with urlopen(good_req, timeout=5) as response:
                self.assertEqual(response.status, 204)
                self.assertEqual(
                    response.headers.get("Access-Control-Allow-Origin"),
                    "http://127.0.0.1:11437",
                )
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
