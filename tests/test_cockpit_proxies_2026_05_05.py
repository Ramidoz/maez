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
from contextlib import contextmanager
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
        with patch.dict(
            os.environ,
            {
                "MAEZ_IPHONE_INGEST_TOKEN": "test-token",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            },
            clear=False,
        ):
            from skills import web_interface as wi
        self.client = wi.app.test_client()
        self.wi = wi

    @contextmanager
    def _owner_session(self):
        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            patch.object(
                self.wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
        ):
            yield

    def _set_owner_cookie(self):
        self.client.set_cookie("maez_token", "tok")

    def test_requires_owner_session_before_proxying(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("unauthenticated cockpit message reached daemon")

        with patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
            response = self.client.post(
                "/api/v1/cockpit/message",
                json={"text": "hi maez"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_valid_non_owner_cookie_does_not_authorize_message_proxy(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("non-owner cockpit message reached daemon")

        self._set_owner_cookie()
        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "guest", "display_name": "Guest"},
            ),
            patch.object(self.wi.accounts, "get_user_record", return_value={}),
            patch("urllib.request.urlopen", side_effect=fail_if_forwarded),
        ):
            response = self.client.post(
                "/api/v1/cockpit/message",
                json={"text": "hi maez"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_forwards_body_to_daemon_and_returns_reply(self):
        sent_body = json.dumps({"text": "hi maez"}).encode()
        daemon_reply = json.dumps({"reply": "hi rohit"}).encode()

        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["data"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.get_method()
            captured["timeout"] = timeout
            captured["headers"] = dict(req.header_items())
            return _make_urlopen_response(daemon_reply, status=200)

        with patch.object(self.wi, "_urlreq", create=True, new=None):
            pass  # no-op; the real import is inside the route, not module-level

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            r = self.client.post(
                "/api/v1/cockpit/message",
                data=sent_body,
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(), daemon_reply)
        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["data"], {"text": "hi maez", "surface": "cockpit"})
        self.assertEqual(
            captured["headers"].get("X-maez-s7-internal-channel"),
            "test-channel-secret",
        )
        self.assertIsNotNone(captured["timeout"])
        self.assertGreaterEqual(captured["timeout"], 60.0)

    def test_forces_cockpit_surface_even_if_browser_claims_web_owner(self):
        daemon_reply = json.dumps({"reply": "hi rohit"}).encode()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["data"] = json.loads(req.data.decode("utf-8"))
            return _make_urlopen_response(daemon_reply, status=200)

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            r = self.client.post(
                "/api/v1/cockpit/message",
                json={"text": "hi maez", "surface": "web_owner"},
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["data"]["text"], "hi maez")
        self.assertEqual(captured["data"]["surface"], "cockpit")

    def test_passes_through_daemon_4xx_response(self):
        """If daemon answers 400, the cockpit caller sees 400 + body."""
        daemon_err_body = json.dumps({"error": "bad request"}).encode()

        def fake_urlopen(req, timeout=None):
            raise HTTPError(
                req.full_url, 400, "Bad Request", {},
                fp=_FakeFile(daemon_err_body),
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self._set_owner_cookie()
            with (
                self._owner_session(),
                patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            ):
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

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
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
        with patch.dict(
            os.environ,
            {
                "MAEZ_IPHONE_INGEST_TOKEN": "test-token",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            },
            clear=False,
        ):
            from skills import web_interface as wi
        self.client = wi.app.test_client()
        self.wi = wi

    @contextmanager
    def _owner_session(self):
        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            patch.object(
                self.wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
        ):
            yield

    def _set_owner_cookie(self):
        self.client.set_cookie("maez_token", "tok")

    def test_requires_owner_session_before_proxying(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("unauthenticated card approval reached daemon")

        with patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
            response = self.client.post("/api/v1/cards/abc-123/approve")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_deny_requires_owner_session(self):
        response = self.client.post("/api/v1/cards/abc-123/deny")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_dream_action_requires_owner_session(self):
        response = self.client.post("/api/v1/dreams/10001/approve")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_valid_non_owner_cookie_does_not_authorize_card_approve_or_deny(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("non-owner card approval reached daemon")

        self._set_owner_cookie()
        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "guest", "display_name": "Guest"},
            ),
            patch.object(self.wi.accounts, "get_user_record", return_value={}),
            patch("urllib.request.urlopen", side_effect=fail_if_forwarded),
        ):
            approve = self.client.post("/api/v1/cards/abc-123/approve")
            deny = self.client.post("/api/v1/cards/abc-123/deny")
            dream = self.client.post("/api/v1/dreams/10001/approve")

        self.assertEqual(approve.status_code, 401)
        self.assertEqual(approve.get_json()["error"], "owner_auth_required")
        self.assertEqual(deny.status_code, 401)
        self.assertEqual(deny.get_json()["error"], "owner_auth_required")
        self.assertEqual(dream.status_code, 401)
        self.assertEqual(dream.get_json()["error"], "owner_auth_required")

    def test_query_token_does_not_authorize_privileged_cockpit_route(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("query-token card approval reached daemon")

        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            patch("urllib.request.urlopen", side_effect=fail_if_forwarded),
        ):
            response = self.client.post("/api/v1/cards/abc-123/approve?web_token=tok")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_forwards_request_id_to_daemon_path(self):
        daemon_reply = json.dumps({"ok": True, "status": "executed"}).encode()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.header_items())
            return _make_urlopen_response(daemon_reply, status=200)

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            r = self.client.post("/api/v1/cards/abc-123/approve")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(), daemon_reply)
        self.assertEqual(
            captured["url"],
            "http://127.0.0.1:11435/internal/approve_card/abc-123",
        )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(
            captured["headers"].get("X-maez-s7-internal-channel"),
            "test-channel-secret",
        )

    def test_url_encodes_unsafe_request_id_chars(self):
        """request_id with slashes/spaces must be URL-encoded so the
        daemon route matches and we don't accidentally hit a sibling
        path."""
        daemon_reply = b'{"ok": true}'
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _make_urlopen_response(daemon_reply, status=200)

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
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

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            r = self.client.post("/api/v1/cards/nonexistent/approve")
        self.assertEqual(r.status_code, 404)
        self.assertIn(b"no such card", r.get_data())

    def test_returns_502_when_daemon_unreachable(self):
        def fake_urlopen(req, timeout=None):
            raise URLError("connection refused")

        self._set_owner_cookie()
        with (
            self._owner_session(),
            patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            r = self.client.post("/api/v1/cards/x/approve")
        self.assertEqual(r.status_code, 502)
        body = json.loads(r.get_data())
        self.assertEqual(body["error"], "daemon_unreachable")


class CockpitS7WebAuthnDeferredProxy(unittest.TestCase):
    """S7 v1 exposes the founder ceremony as visibly deferred, not armed."""

    def setUp(self):
        with patch.dict(
            os.environ,
            {
                "MAEZ_IPHONE_INGEST_TOKEN": "test-token",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            },
            clear=False,
        ):
            from skills import web_interface as wi
        self.client = wi.app.test_client()
        self.wi = wi

    @contextmanager
    def _owner_session(self):
        with (
            patch.object(
                self.wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            patch.object(
                self.wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
        ):
            yield

    def _set_owner_cookie(self):
        self.client.set_cookie("maez_token", "tok")

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

        self._set_owner_cookie()
        with self._owner_session(), patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
            for path in paths:
                with self.subTest(path=path):
                    response = self.client.post(path, json={"sample": "payload"})
                    body = json.loads(response.get_data())

                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(body["error"], "s7_ceremony_deferred")
                    self.assertEqual(body["reason_code"], "s7_ceremony_deferred")
                    self.assertEqual(body["status"], "deferred")
                    self.assertEqual(body["surface"], "cockpit")

    def test_s7_write_proxies_require_owner_private_session(self):
        def fail_if_forwarded(*_args, **_kwargs):
            raise AssertionError("unauthenticated S7 proxy reached daemon")

        paths = (
            "/api/v1/s7/webauthn/register/begin",
            "/api/v1/s7/webauthn/register/finish",
            "/api/v1/s7/webauthn/register/backup-card",
            "/api/v1/s7/webauthn/proof/disable-card",
            "/api/v1/s7/webauthn/proof/disable-credential",
            "/api/v1/s7/cards/req-1/webauthn/begin",
            "/api/v1/s7/cards/req-1/webauthn/finish",
            "/api/v1/s7/cards/req-1/execute",
        )

        with (
            patch.dict(os.environ, {"S7_LIVE_WEBAUTHN_CEREMONY": "1"}, clear=False),
            patch("urllib.request.urlopen", side_effect=fail_if_forwarded),
        ):
            for path in paths:
                with self.subTest(path=path):
                    response = self.client.post(path, json={"sample": "payload"})
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json()["error"], "owner_auth_required")

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
        self._set_owner_cookie()
        with patch.dict(os.environ, env, clear=False):
            with self._owner_session(), patch("urllib.request.urlopen", side_effect=fake_urlopen):
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
        self._set_owner_cookie()
        with patch.dict(os.environ, env, clear=False):
            with self._owner_session(), patch("urllib.request.urlopen", side_effect=fake_urlopen):
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
        self._set_owner_cookie()
        with patch.dict(os.environ, env, clear=False):
            with self._owner_session(), patch("urllib.request.urlopen", side_effect=fake_urlopen):
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

        self._set_owner_cookie()
        with patch.dict(os.environ, {"S7_LIVE_WEBAUTHN_CEREMONY": "1"}, clear=False):
            with self._owner_session(), patch("urllib.request.urlopen", side_effect=fail_if_forwarded):
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
