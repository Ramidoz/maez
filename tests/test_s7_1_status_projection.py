"""S7.1 ceremony status projection tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


NOW = "2099-05-18T12:00:00+00:00"


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


def _daemon_client():
    from daemon.maez_daemon import MaezDaemon

    daemon = MaezDaemon.__new__(MaezDaemon)
    daemon._health_server = None
    captured = {}

    def fake_make_server(_host, _port, app):
        captured["app"] = app
        return _FakeServer()

    case = unittest.TestCase()
    with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
        with case.assertRaises(_StopServer):
            daemon._run_health_server()
    return captured["app"].test_client()


class _AvailableVerifier:
    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}


class S71StatusProjectionTests(unittest.TestCase):
    def test_035_daemon_status_route_mutates_no_bootstrap_or_challenge_state(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "memory" / "s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            intent = store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=10,
                now=NOW,
                effective_uid=os.getuid(),
                is_interactive=True,
                tty_path="/dev/pts/test",
                token_bytes=b"s" * 32,
            )
            store.create_challenge(
                challenge_id="challenge-status",
                challenge_kind="register_primary",
                expires_at="2099-05-18T12:05:00+00:00",
            )
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_WEBAUTHN_STORE_ROOT": str(root),
                "S7_INTERNAL_CHANNEL_TOKEN": "status-test-token",
            }

            with patch.dict(os.environ, env, clear=False):
                # 2026-08-14 (full-body audit): the status route was the ONE
                # internal S7 route without the channel check. Headerless is
                # now refused; the projection needs the reviewed channel.
                bare = _daemon_client().get("/internal/s7/webauthn/status")
                self.assertEqual(bare.status_code, 403)
                response = _daemon_client().get(
                    "/internal/s7/webauthn/status",
                    headers={"X-Maez-S7-Internal-Channel": "status-test-token"},
                )

            body = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body["bootstrap_state"], "issued")
            self.assertTrue(body["live_flag_enabled"])
            self.assertEqual(body["verifier_dependency_state"], "available")
            self.assertEqual(store.bootstrap_state(now=NOW), "issued")
            self.assertTrue(store.challenge_is_active("challenge-status", now=NOW))
            self.assertIsNone(store.get_credential(intent.intent_id))

    def test_service_status_reports_manual_recovery_when_registry_missing(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "missing" / "s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            store.db_path.unlink()
            service = S7LocalWebAuthnCeremonyService(
                verifier=_AvailableVerifier(),
                store_factory=lambda: store,
            )

            status = service.status(now=NOW).body

        self.assertEqual(status["ceremony_mode"], "manual_recovery_required")
        self.assertTrue(status["manual_recovery_required"])
        self.assertEqual(status["manual_recovery_cause"], "registry_missing")


if __name__ == "__main__":
    unittest.main()
