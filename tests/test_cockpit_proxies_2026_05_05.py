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
from unittest import mock
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _make_urlopen_response(body: bytes, status: int = 200,
                           ctype: str = "application/json",
                           content_type: str | None = None):
    """Build a context-manager-shaped object that mimics urlopen().

    Accepts either ``ctype`` (legacy) or ``content_type`` (alias used by
    newer tests that drive a non-JSON daemon Content-Type)."""
    cm = MagicMock()
    response = MagicMock()
    response.read.return_value = body
    response.status = status
    response.headers = {"Content-Type": content_type or ctype}
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

        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
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

        from skills import web_interface as wi
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
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

        from skills import web_interface as wi
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
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
            "/api/v1/s7/webauthn/register/backup-card",
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

    def test_flag_on_backup_card_create_forwards_with_internal_channel(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["body"] = req.data
            return _make_urlopen_response(
                b'{"ok": true, "request_id": "req-backup-register"}',
                status=201,
            )

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                response = self.client.post(
                    "/api/v1/s7/webauthn/register/backup-card",
                    json={"session_binding": "session-backup-card"},
                )

        body = json.loads(response.get_data())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["request_id"], "req-backup-register")
        self.assertEqual(
            captured["url"],
            "http://127.0.0.1:11435/internal/s7/webauthn/register/backup-card",
        )
        self.assertEqual(captured["headers"]["X-maez-s7-internal-channel"], "test-channel-secret")
        self.assertEqual(captured["body"], b'{"session_binding": "session-backup-card"}')

    def test_flag_on_proof_disable_routes_forward_with_internal_channel(self):
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(
                {
                    "url": req.full_url,
                    "headers": dict(req.header_items()),
                    "body": req.data,
                }
            )
            return _make_urlopen_response(
                b'{"ok": true, "request_id": "req-disable-primary"}',
                status=200,
            )

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                card_response = self.client.post(
                    "/api/v1/s7/webauthn/proof/disable-card",
                    json={"credential_ref": "cred-primary", "credential_kind": "primary"},
                )
                disable_response = self.client.post(
                    "/api/v1/s7/webauthn/proof/disable-credential",
                    json={
                        "credential_ref": "cred-primary",
                        "disable_authorization_request_id": "req-disable-primary",
                        "s7_authorization_artifact_id": "s7authz-primary",
                    },
                )

        self.assertEqual(card_response.status_code, 200)
        self.assertEqual(disable_response.status_code, 200)
        self.assertEqual(
            captured[0]["url"],
            "http://127.0.0.1:11435/internal/s7/webauthn/proof/disable-card",
        )
        self.assertEqual(
            captured[1]["url"],
            "http://127.0.0.1:11435/internal/s7/webauthn/proof/disable-credential",
        )
        self.assertEqual(captured[0]["headers"]["X-maez-s7-internal-channel"], "test-channel-secret")
        self.assertEqual(captured[1]["headers"]["X-maez-s7-internal-channel"], "test-channel-secret")

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
        self.assertIn("/api/v1/s7/webauthn/register/backup-card", text)
        self.assertIn("/api/v1/s7/cards/", text)
        self.assertIn("backup_authorization_request_id", text)
        self.assertIn("authorization_challenge_id", text)
        self.assertIn("authorization_session_binding", text)
        self.assertIn("authorization_credential_ref", text)
        self.assertIn("backupAuthorizationChallengeId", text)
        self.assertIn("backupAuthorizationSessionBinding", text)
        self.assertIn("backupAuthorizationCredentialRef", text)
        self.assertIn("createBackupRegistrationCard", text)
        self.assertIn("maez_voice_raw_response_hash: begin.maez_voice_raw_response_hash", text)
        self.assertIn("Execute authorized guarded card", text)
        self.assertIn("executeAuthorizedCard", text)
        self.assertIn("s7_authorization_artifact_id: lastArtifactId.value", text)
        self.assertIn("lastArtifactRequestId", text)
        self.assertIn("finish.request_id || requestId", text)
        self.assertIn("artifact_request_mismatch", text)
        self.assertIn("return;", text)
        self.assertIn("register error", text)
        self.assertIn("authorize error", text)
        self.assertIn("err.payload", text)
        self.assertIn("Create primary-disable proof card", text)
        self.assertIn("Create backup-disable proof card", text)
        self.assertIn("/api/v1/s7/webauthn/proof/disable-card", text)
        self.assertIn("/api/v1/s7/webauthn/proof/disable-credential", text)
        self.assertIn("disableCredentialForProof", text)
        self.assertIn("bufferToB64url", text)
        self.assertIn("b64urlToBuffer", text)


class CockpitMessageGate(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi
        wi.app.config["TESTING"] = True
        self.client = wi.app.test_client()

    def test_non_owner_gets_401_before_body(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=False):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json().get("error"), "owner_auth_required")

    def test_owner_no_token_is_502_failed_send(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=AssertionError("must not send without token")) as up:
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json(), {"ok": False, "error": "s7_internal_channel_untrusted"})
        up.assert_not_called()

    def test_owner_with_token_sends_s7_header(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return _make_urlopen_response(b'{"reply":"ok"}', status=200)
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok-123"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["req"].get_header("X-maez-s7-internal-channel"), "tok-123")

    def test_preserves_daemon_content_type(self):
        def fake_urlopen(req, timeout=None):
            return _make_urlopen_response(b"plain reply", status=200, content_type="text/plain")
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.headers.get("Content-Type"), "text/plain")

    def test_daemon_down_is_502_unreachable(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json().get("error"), "daemon_unreachable")


class CockpitOwnerMarker(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi
        wi.app.config["TESTING"] = True
        self.client = wi.app.test_client()

    def _send_capturing(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return _make_urlopen_response(b'{"reply":"ok"}', status=200)
        return captured, fake_urlopen

    def test_claimed_owner_cookie_stamps_marker(self):
        captured, fake = self._send_capturing()
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.object(self.wi, "_request_has_web_owner_cookie", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["req"].get_header("X-maez-owner-authenticated"), "1")

    def test_local_recovery_send_allowed_marker_absent(self):
        captured, fake = self._send_capturing()
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.object(self.wi, "_request_has_web_owner_cookie", return_value=False), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(captured["req"].get_header("X-maez-owner-authenticated"))

    def test_non_owner_401_no_send(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=False):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 401)


class RequestHasWebOwnerCookie(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi

    def test_unclaimed_returns_false(self):
        with self.wi.app.test_request_context("/"):
            with mock.patch.object(self.wi.accounts, "owner_claimed", return_value=False):
                self.assertFalse(self.wi._request_has_web_owner_cookie())

    def test_store_error_returns_false(self):
        with self.wi.app.test_request_context("/"):
            with mock.patch.object(self.wi.accounts, "owner_claimed", side_effect=RuntimeError("db down")):
                self.assertFalse(self.wi._request_has_web_owner_cookie())

    def test_no_cookie_returns_false(self):
        with self.wi.app.test_request_context("/"):
            with mock.patch.object(self.wi.accounts, "owner_claimed", return_value=True):
                self.assertFalse(self.wi._request_has_web_owner_cookie())

    def test_claimed_owner_cookie_returns_true(self):
        with self.wi.app.test_request_context("/", headers={"Cookie": f"{self.wi.AUTH_COOKIE}=tok"}):
            with mock.patch.object(self.wi.accounts, "owner_claimed", return_value=True), \
                 mock.patch.object(self.wi.accounts, "get_by_token", return_value={"uuid": "u1"}), \
                 mock.patch.object(self.wi.accounts, "get_user_record", return_value={"web_owner": 1}), \
                 mock.patch.object(self.wi, "_is_owner", return_value=True):
                self.assertTrue(self.wi._request_has_web_owner_cookie())


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
