"""S7.1 daemon internal-channel authority-route tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch


class _StopServer(RuntimeError):
    pass


class _FakeSocket:
    def setsockopt(self, *_args):
        return None


class _FakeServer:
    socket = _FakeSocket()

    def serve_forever(self):
        raise _StopServer()

    def server_close(self):
        return None


class S71DaemonInternalChannelTests(unittest.TestCase):
    def _client(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon._health_server = None
        captured = {}

        def fake_make_server(_host, _port, app):
            captured["app"] = app
            return _FakeServer()

        with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
            with self.assertRaises(_StopServer):
                daemon._run_health_server()
        return captured["app"].test_client()

    def test_029_originless_local_curl_to_daemon_register_begin_is_rejected(self):
        with patch.dict(os.environ, {"S7_LIVE_WEBAUTHN_CEREMONY": "1"}, clear=False):
            response = self._client().post(
                "/internal/s7/webauthn/register/begin",
                json={"bootstrap_token": "bearer-secret"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "s7_internal_channel_untrusted")

    def test_030_originless_local_curl_to_daemon_authorize_begin_is_rejected(self):
        with patch.dict(os.environ, {"S7_LIVE_WEBAUTHN_CEREMONY": "1"}, clear=False):
            response = self._client().post(
                "/internal/s7/cards/req-1/webauthn/begin",
                json={"challenge": "please"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "s7_internal_channel_untrusted")

    def test_031_daemon_register_begin_accepts_valid_internal_channel_then_requires_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": f"{tmp}/memory/s7_1_webauthn",
            }
            with patch.dict(os.environ, env, clear=False):
                response = self._client().post(
                    "/internal/s7/webauthn/register/begin",
                    json={"bootstrap_token": "missing"},
                    headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "s7_bootstrap_required")

    def test_daemon_register_begin_delegates_to_core_ceremony_service(self):
        class Service:
            def __init__(self, **_kwargs):
                pass

            def register_begin(self, **_kwargs):
                class Result:
                    status_code = 409
                    body = {"ok": False, "error": "s7_service_probe"}

                return Result()

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                response = self._client().post(
                    "/internal/s7/webauthn/register/begin",
                    json={"bootstrap_token": "missing"},
                    headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "s7_service_probe")

    def test_daemon_register_finish_delegates_to_core_ceremony_service(self):
        class Service:
            def __init__(self, **_kwargs):
                pass

            def register_finish(self, **_kwargs):
                class Result:
                    status_code = 410
                    body = {"ok": False, "error": "s7_finish_probe"}

                return Result()

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                response = self._client().post(
                    "/internal/s7/webauthn/register/finish",
                    json={"challenge_id": "challenge"},
                    headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.get_json()["error"], "s7_finish_probe")

    def test_032_browser_presented_internal_channel_proof_is_rejected(self):
        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            response = self._client().post(
                "/internal/s7/webauthn/register/begin",
                json={"bootstrap_token": "bearer-secret"},
                headers={
                    "Origin": "http://localhost:11437",
                    "X-Maez-S7-Internal-Channel": "test-channel-secret",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "s7_internal_channel_untrusted")
