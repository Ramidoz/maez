"""S7.1 daemon internal-channel authority-route tests."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from daemon.maez_daemon import MaezDaemon


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


class _RouteAuthenticationVerifier:
    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}

    def verify_authentication_response(self, **_kwargs):
        return {
            "ok": True,
            "credential_ref": "cred-primary",
            "sign_count": 1,
            "user_presence": True,
            "user_verification": True,
        }


class S71DaemonInternalChannelTests(unittest.TestCase):
    def _client(self, configure_daemon=None):
        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon._health_server = None
        if configure_daemon is not None:
            configure_daemon(daemon)
        captured = {}

        def fake_make_server(_host, _port, app):
            captured["app"] = app
            return _FakeServer()

        with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
            with self.assertRaises(_StopServer):
                daemon._run_health_server()
        return captured["app"].test_client()

    def _destructive_envelope(self, request_id: str):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id=request_id,
            action="run_shell",
            params={"cmd": "rm -f /tmp/maez-s7-route-probe"},
            claimed_work_class="destructive_user_action",
            requesting_subsystem="unit",
            closed_symptom_code="verification_needed",
            proposed_change_class="unknown_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("shell:rm -f /tmp/maez-s7-route-probe",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at="2026-05-18T11:00:00+00:00",
            expires_at="2026-05-18T12:00:00+00:00",
            predicted_effect_class="behavior_change",
            rollback_path_class="manual_review",
            maez_voice_consultation_id=None,
            free_text_ref_hash=None,
        )

    def _daemon_with_card_pipeline(self, request_id: str):
        envelope = self._destructive_envelope(request_id)

        class Card:
            action = "run_shell"
            params = {"cmd": "rm -f /tmp/maez-s7-route-probe"}
            state_hash = "empty"
            state_fields = None

        card = Card()
        card.request_id = request_id

        class Store:
            def get(self, _request_id):
                return card if _request_id == request_id else None

        class Pipe:
            card_store = Store()

            def _card_requires_s7_authorization(self, _card):
                return True

            def _s7_request_envelope_for_card(self, _card):
                return envelope

            @staticmethod
            def _execution_params_for_card(_card):
                return dict(card.params)

        class Telegram:
            def _get_pipeline(self):
                return Pipe()

        def configure(daemon):
            daemon.telegram = Telegram()

        return configure

    def _credential_record(self, credential_ref: str, *, kind: str):
        from core.governance.s7_webauthn_bootstrap import FounderWebAuthnCredentialRecord

        return FounderWebAuthnCredentialRecord.build(
            credential_ref=credential_ref,
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user",),
            public_key=f"public-key-{credential_ref}",
            sign_count=0,
            rp_id="localhost",
            origin="http://localhost:11437",
            created_at="2026-05-18T11:00:00+00:00",
            backup_credential=(kind == "backup"),
            enabled=True,
            credential_kind=kind,
            label=f"{kind} key",
            registration_challenge_id=f"challenge-{credential_ref}",
            attestation_format="packed",
            aaguid="00112233-4455-6677-8899-aabbccddeeff",
            authenticator_attachment="cross-platform",
            backup_eligible=False,
            backed_up=False,
            transports=("usb",),
            library_name="webauthn",
            library_version="2.7.1",
            sign_count_mode="advancing",
            uv_capable=True,
            uv_required_for_guarded=True,
            distinct_device_confidence="confirmed_distinct",
        )

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

    def test_daemon_authorize_begin_delegates_to_core_ceremony_service(self):
        seen = {}

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_begin(self, **kwargs):
                seen.update(kwargs)

                class Result:
                    status_code = 208
                    body = {
                        "ok": True,
                        "request_id": kwargs["rendered_statement"].request_id,
                    }

                return Result()

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": f"{tmp}/memory/s7_1_webauthn",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                    response = self._client(
                        configure_daemon=self._daemon_with_card_pipeline("req-route-begin")
                    ).post(
                        "/internal/s7/cards/req-route-begin/webauthn/begin",
                        json={"session_binding": "session-auth"},
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(response.status_code, 208)
        self.assertEqual(response.get_json()["request_id"], "req-route-begin")
        self.assertEqual(seen["session_binding"], "session-auth")
        self.assertEqual(seen["rendered_statement"].request_id, "req-route-begin")

    def test_daemon_authorize_finish_delegates_to_core_ceremony_service(self):
        seen = {}

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **kwargs):
                seen.update(kwargs)

                class Result:
                    status_code = 209
                    body = {
                        "ok": True,
                        "request_id": kwargs["rendered_statement"].request_id,
                    }

                return Result()

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": f"{tmp}/memory/s7_1_webauthn",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                    response = self._client(
                        configure_daemon=self._daemon_with_card_pipeline("req-route-finish")
                    ).post(
                        "/internal/s7/cards/req-route-finish/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": "challenge-route",
                            "credential_ref": "cred-primary",
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(response.status_code, 209)
        self.assertEqual(response.get_json()["request_id"], "req-route-finish")
        self.assertEqual(seen["request_json"]["challenge_id"], "challenge-route")
        self.assertEqual(seen["rendered_statement"].request_id, "req-route-finish")

    def test_daemon_authorize_routes_mint_artifact_through_real_service(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7ProductionWebAuthnVerifier", _RouteAuthenticationVerifier):
                    client = self._client(
                        configure_daemon=self._daemon_with_card_pipeline("req-route-live")
                    )
                    begin = client.post(
                        "/internal/s7/cards/req-route-live/webauthn/begin",
                        json={"session_binding": "session-auth"},
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    finish = client.post(
                        "/internal/s7/cards/req-route-live/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": begin.get_json()["challenge_id"],
                            "credential_ref": "cred-primary",
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
            s7.S7AuthorizationStore(store.db_path)
            with sqlite3.connect(store.db_path) as conn:
                artifact_row = conn.execute(
                    """
                    SELECT request_id, grant_source, user_verification
                    FROM s7_authorization_artifacts
                    WHERE artifact_id = ?
                    """,
                    (finish.get_json()["artifact_id"],),
                ).fetchone()

        self.assertEqual(begin.status_code, 200)
        self.assertEqual(begin.get_json()["challenge_kind"], "authorize_guarded_request")
        self.assertEqual(finish.status_code, 200)
        self.assertEqual(finish.get_json()["request_id"], "req-route-live")
        self.assertIsNotNone(artifact_row)
        assert artifact_row is not None
        self.assertEqual(artifact_row[0], "req-route-live")
        self.assertEqual(artifact_row[1], "founder_webauthn")
        self.assertEqual(artifact_row[2], 1)

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
