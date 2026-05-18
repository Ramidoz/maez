# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Cockpit proxy routes — Workstation v1 Session 1.

The cockpit previously called the daemon directly at :11435 from the
browser. Two thin maez-web proxy routes fix that:

  POST /api/v1/cockpit/message
       → forwards to daemon's /message
  POST /api/v1/cards/<id>/approve
       → forwards to daemon's /internal/approve_card/<id>

These tests lock in the proxy contract:

  - Forwards method + body + content-type header
  - Returns the daemon's response body and status code verbatim
  - On daemon-unreachable, returns 502 with structured error
  - On daemon HTTP error (4xx/5xx), passes through the daemon's
    response (status + body)
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _make_urlopen_response(body: bytes, status: int = 200,
                           ctype: str = "application/json"):
    """Build a context-manager-shaped object that mimics urlopen()."""
    cm = MagicMock()
    response = MagicMock()
    response.read.return_value = body
    response.status = status
    response.headers = {"Content-Type": ctype}
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


class CockpitMessageProxy(unittest.TestCase):
    """POST /api/v1/cockpit/message → daemon /message."""

    def setUp(self):
        from skills import web_interface as wi
        self.client = wi.app.test_client()

    def test_forwards_body_to_daemon_and_returns_reply(self):
        from skills import web_interface as wi
        sent_body = json.dumps({"text": "hi maez"}).encode()
        daemon_reply = json.dumps({"reply": "hi rohit"}).encode()

        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = req.data
            captured["method"] = req.get_method()
            captured["timeout"] = timeout
            return _make_urlopen_response(daemon_reply, status=200)

        with patch.object(wi, "_urlreq", create=True, new=None):
            pass  # no-op; the real import is inside the route, not module-level

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post(
                "/api/v1/cockpit/message",
                data=sent_body,
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(), daemon_reply)
        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["data"], sent_body)
        self.assertIsNotNone(captured["timeout"])
        self.assertGreaterEqual(captured["timeout"], 60.0)

    def test_passes_through_daemon_4xx_response(self):
        """If daemon answers 400, the cockpit caller sees 400 + body."""
        daemon_err_body = json.dumps({"error": "bad request"}).encode()

        def fake_urlopen(req, timeout=None):
            raise HTTPError(
                req.full_url, 400, "Bad Request", {},
                fp=_FakeFile(daemon_err_body),
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post(
                "/api/v1/cockpit/message",
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"bad request", r.get_data())

    def test_returns_502_when_daemon_unreachable(self):
        def fake_urlopen(req, timeout=None):
            raise URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post(
                "/api/v1/cockpit/message",
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 502)
        body = json.loads(r.get_data())
        self.assertEqual(body["error"], "daemon_unreachable")
        self.assertIn("connection refused", body["detail"])


class CockpitCardApproveProxy(unittest.TestCase):
    """POST /api/v1/cards/<id>/approve → daemon /internal/approve_card/<id>."""

    def setUp(self):
        from skills import web_interface as wi
        self.client = wi.app.test_client()

    def test_forwards_request_id_to_daemon_path(self):
        daemon_reply = json.dumps({"ok": True, "status": "executed"}).encode()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return _make_urlopen_response(daemon_reply, status=200)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cards/abc-123/approve")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(), daemon_reply)
        self.assertEqual(
            captured["url"],
            "http://127.0.0.1:11435/internal/approve_card/abc-123",
        )
        self.assertEqual(captured["method"], "POST")

    def test_url_encodes_unsafe_request_id_chars(self):
        """request_id with slashes/spaces must be URL-encoded so the
        daemon route matches and we don't accidentally hit a sibling
        path."""
        daemon_reply = b'{"ok": true}'
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _make_urlopen_response(daemon_reply, status=200)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.client.post("/api/v1/cards/has spaces/approve")
        self.assertIn(
            "/internal/approve_card/has%20spaces",
            captured["url"],
        )

    def test_passes_through_daemon_404(self):
        """Daemon returns 404 for unknown card; cockpit sees 404."""
        body = json.dumps({"ok": False, "error": "no such card"}).encode()

        def fake_urlopen(req, timeout=None):
            raise HTTPError(
                req.full_url, 404, "Not Found", {},
                fp=_FakeFile(body),
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cards/nonexistent/approve")
        self.assertEqual(r.status_code, 404)
        self.assertIn(b"no such card", r.get_data())

    def test_returns_502_when_daemon_unreachable(self):
        def fake_urlopen(req, timeout=None):
            raise URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cards/x/approve")
        self.assertEqual(r.status_code, 502)
        body = json.loads(r.get_data())
        self.assertEqual(body["error"], "daemon_unreachable")


class CockpitS7WebAuthnDeferredProxy(unittest.TestCase):
    """S7 v1 exposes the founder ceremony as visibly deferred, not armed."""

    def setUp(self):
        from skills import web_interface as wi
        self.client = wi.app.test_client()

    def test_webauthn_proxy_routes_return_structured_deferred_without_daemon_call(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("deferred S7 WebAuthn proxy route contacted daemon")

        paths = (
            "/api/v1/s7/webauthn/register/begin",
            "/api/v1/s7/webauthn/register/finish",
            "/api/v1/s7/cards/req-1/webauthn/begin",
            "/api/v1/s7/cards/req-1/webauthn/finish",
        )

        with patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
            for path in paths:
                with self.subTest(path=path):
                    response = self.client.post(path, json={"sample": "payload"})
                    body = json.loads(response.get_data())

                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(body["error"], "s7_ceremony_deferred")
                    self.assertEqual(body["reason_code"], "s7_ceremony_deferred")
                    self.assertEqual(body["status"], "deferred")
                    self.assertEqual(body["surface"], "cockpit")

    def test_status_route_proxies_to_daemon_even_when_ceremony_flag_off(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return _make_urlopen_response(
                b'{"ok": true, "live_flag_enabled": false}',
                status=200,
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.get("/api/v1/s7/webauthn/status")

        body = json.loads(response.get_data())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["live_flag_enabled"])
        self.assertEqual(captured["url"], "http://127.0.0.1:11435/internal/s7/webauthn/status")
        self.assertEqual(captured["method"], "GET")

    def test_flag_on_register_begin_forwards_with_internal_channel_not_browser_origin(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["body"] = req.data
            return _make_urlopen_response(
                b'{"ok": false, "error": "s7_bootstrap_required"}',
                status=401,
            )

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                response = self.client.post(
                    "/api/v1/s7/webauthn/register/begin",
                    json={"bootstrap_token": "token"},
                    headers={"Origin": "http://localhost:11437"},
                )

        body = json.loads(response.get_data())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["error"], "s7_bootstrap_required")
        self.assertEqual(
            captured["url"],
            "http://127.0.0.1:11435/internal/s7/webauthn/register/begin",
        )
        self.assertEqual(captured["headers"]["X-maez-s7-internal-channel"], "test-channel-secret")
        self.assertNotIn("Origin", captured["headers"])
        self.assertEqual(captured["body"], b'{"bootstrap_token": "token"}')

    def test_flag_on_malicious_origin_gets_s7_typed_error_before_forward(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("malicious browser origin reached daemon proxy")

        with patch.dict(os.environ, {"S7_LIVE_WEBAUTHN_CEREMONY": "1"}, clear=False):
            with patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
                response = self.client.post(
                    "/api/v1/s7/webauthn/register/begin",
                    json={"bootstrap_token": "token"},
                    headers={"Origin": "https://evil.example"},
                )

        body = json.loads(response.get_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["error"], "s7_untrusted_origin")

    def test_s7_webauthn_manual_proof_page_drives_browser_webauthn(self):
        response = self.client.get("/cockpit/s7-webauthn-proof")
        text = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("S7.1 Manual Physical-Key Proof", text)
        self.assertIn("navigator.credentials.create", text)
        self.assertIn("navigator.credentials.get", text)
        self.assertIn("/api/v1/s7/webauthn/register/begin", text)
        self.assertIn("/api/v1/s7/webauthn/register/finish", text)
        self.assertIn("/api/v1/s7/cards/", text)
        self.assertIn("bufferToB64url", text)
        self.assertIn("b64urlToBuffer", text)


class _FakeFile:
    """Tiny stand-in for the .read() interface HTTPError exposes via fp.

    Includes close() because Python's tempfile cleanup at destruction
    time calls it via HTTPError.__del__ — without close() the test run
    emits an AttributeError traceback at gc time. Cosmetic-only."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        return None


if __name__ == "__main__":
    unittest.main()
