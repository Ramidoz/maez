"""S7.1 daemon internal-channel authority-route tests."""

from __future__ import annotations

import os
import inspect
import sqlite3
import tempfile
from datetime import datetime
import unittest
from unittest.mock import patch

from daemon.maez_daemon import MaezDaemon

NOW = "2026-05-18T11:00:00+00:00"


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


class _FixedDateTime:
    @staticmethod
    def fromisoformat(value):
        return datetime.fromisoformat(value)

    @staticmethod
    def now(_tz=None):
        return datetime.fromisoformat(NOW)


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

    def _self_mod_envelope(self, request_id: str):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id=request_id,
            action="edit_file",
            params={"path": "config/soul.md", "patch": "tighten one line"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="verification_needed",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("config/soul.md",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at="2026-05-18T11:00:00+00:00",
            expires_at="2026-05-18T12:00:00+00:00",
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id=f"voice-{request_id}",
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

    def _daemon_with_self_mod_pipeline(
        self,
        request_id: str,
        *,
        maez_objection_state: str = "absent",
    ):
        from core.governance import operator_user_boundary as s7

        envelope = self._self_mod_envelope(request_id)

        class Card:
            action = "edit_file"
            params = {"path": "config/soul.md", "patch": "tighten one line"}
            state_hash = "empty"
            state_fields = None

        card = Card()
        card.request_id = request_id
        card.created_at = 1779102000.0

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

            @staticmethod
            def _s7_voice_consultation_for_card(_card, _envelope):
                return s7.MaezVoiceConsultation(
                    consultation_id=f"voice-{request_id}",
                    request_id=request_id,
                    request_envelope_hash=s7.work_request_envelope_hash(envelope),
                    producer="s7_voice_consultation_turn",
                    source_ref_kind="s7_voice_turn",
                    source_ref_hash=s7.canonical_hash({"voice": request_id}),
                    maez_voice_consulted=True,
                    maez_objection_state=maez_objection_state,
                    maez_withdrew_request=False,
                    unavailable_reason_code=None,
                    created_at="2026-05-18T11:00:00+00:00",
                )

        class Telegram:
            def _get_pipeline(self):
                return Pipe()

        def configure(daemon):
            daemon.telegram = Telegram()

        return configure

    def _daemon_with_backup_registration_pipeline(self, request_id: str):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import (
            backup_registration_action_params,
            build_backup_registration_envelope,
        )

        envelope = build_backup_registration_envelope(
            request_id=request_id,
            created_at="2026-05-18T11:00:00+00:00",
            expires_at="2026-05-18T12:00:00+00:00",
            maez_voice_consultation_id=f"voice-{request_id}",
        )

        class Card:
            action = "register_backup_webauthn_credential"
            params = backup_registration_action_params()
            state_hash = "empty"
            state_fields = None

        card = Card()
        card.request_id = request_id
        card.created_at = 1779102000.0

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

            @staticmethod
            def _s7_voice_consultation_for_card(_card, _envelope):
                return s7.MaezVoiceConsultation(
                    consultation_id=f"voice-{request_id}",
                    request_id=request_id,
                    request_envelope_hash=s7.work_request_envelope_hash(envelope),
                    producer="s7_voice_consultation_turn",
                    source_ref_kind="s7_voice_turn",
                    source_ref_hash=s7.canonical_hash({"voice": request_id}),
                    maez_voice_consulted=True,
                    maez_objection_state="absent",
                    maez_withdrew_request=False,
                    unavailable_reason_code=None,
                    created_at="2026-05-18T11:00:00+00:00",
                )

        class Telegram:
            def _get_pipeline(self):
                return Pipe()

        def configure(daemon):
            daemon.telegram = Telegram()

        return configure

    def _daemon_with_disable_credential_pipeline(
        self,
        request_id: str,
        credential_ref: str,
        *,
        credential_kind: str = "primary",
    ):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import (
            build_disable_credential_envelope,
            disable_credential_action_params,
        )

        params = disable_credential_action_params(
            credential_ref=credential_ref,
            credential_kind=credential_kind,
        )
        envelope = build_disable_credential_envelope(
            request_id=request_id,
            credential_ref=credential_ref,
            credential_kind=credential_kind,
            created_at="2026-05-18T11:00:00+00:00",
            expires_at="2026-05-18T12:00:00+00:00",
            maez_voice_consultation_id=f"voice-{request_id}",
        )

        class Card:
            action = "disable_founder_webauthn_credential"
            state_hash = "empty"
            state_fields = None

        card = Card()
        card.request_id = request_id
        card.params = params
        card.created_at = 1779102000.0

        class Store:
            def get(self, _request_id):
                return card if _request_id == request_id else None

            def create_card(self, **_kwargs):
                return card

        class Pipe:
            card_store = Store()

            def _card_requires_s7_authorization(self, _card):
                return True

            def _s7_request_envelope_for_card(self, _card):
                return envelope

            @staticmethod
            def _execution_params_for_card(_card):
                return dict(card.params)

            @staticmethod
            def _s7_voice_consultation_for_card(_card, _envelope):
                return s7.MaezVoiceConsultation(
                    consultation_id=f"voice-{request_id}",
                    request_id=request_id,
                    request_envelope_hash=s7.work_request_envelope_hash(envelope),
                    producer="s7_voice_consultation_turn",
                    source_ref_kind="s7_voice_turn",
                    source_ref_hash=s7.canonical_hash({"voice": request_id}),
                    maez_voice_consulted=True,
                    maez_objection_state="absent",
                    maez_withdrew_request=False,
                    unavailable_reason_code=None,
                    created_at="2026-05-18T11:00:00+00:00",
                )

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

    def _route_request(self, *, session_binding: str, challenge_id: str = ""):
        class Request:
            headers = {"X-Maez-S7-Internal-Channel": "test-channel-secret"}

            @staticmethod
            def get_json(*_args, **_kwargs):
                return {
                    "session_binding": session_binding,
                    "challenge_id": challenge_id,
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                }

        return Request()

    def _seed_valid_voice_bundle_for_material(
        self,
        db_path,
        material,
        *,
        maez_objection_state: str = "absent",
    ):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            derive_s7_voice_source_bundle_hash_binding,
            expected_s7_voice_rendered_prompt_text,
            s7_voice_consultation_bundle_hash,
        )

        rendered = material.kwargs["rendered_statement"]
        envelope = material.kwargs["envelope"]
        consultation = material.kwargs["maez_voice_consultation"]
        authority = material.kwargs["authority_context"]
        binding = derive_s7_voice_source_bundle_hash_binding(
            rendered_statement=rendered,
            envelope=envelope,
            maez_voice_consultation=consultation,
            authority_context=authority,
            precondition_hash=material.kwargs["precondition_hash"],
        )
        bundle_store = S7VoiceConsultationBundleStore(db_path)
        bundle_use_store = S7VoiceBundleUseStore(db_path)
        attempt_store = S7SemanticReaderAttemptStore(db_path)
        base_attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
        raw_text = "Maez says there is no objection."
        authority_class = "none"
        has_grounded_semantic_blocking_signal = False
        if maez_objection_state == "present":
            raw_text = "Maez says: no, do not make this change."
            authority_class = "authoritative"
            has_grounded_semantic_blocking_signal = True
            base_attempt = type(base_attempt)(
                semantic_reader_route_id=base_attempt.semantic_reader_route_id,
                semantic_reader_provider=base_attempt.semantic_reader_provider,
                semantic_reader_provider_model=base_attempt.semantic_reader_provider_model,
                semantic_reader_model_snapshot=base_attempt.semantic_reader_model_snapshot,
                semantic_reader_decoding_params_hash=(
                    base_attempt.semantic_reader_decoding_params_hash
                ),
                semantic_reader_prompt_hash=base_attempt.semantic_reader_prompt_hash,
                semantic_reader_route_config_hash=base_attempt.semantic_reader_route_config_hash,
                raw_semantic_reader_outcome="blocking_signal_present",
                grounding_response_span_quote="do not make this change",
                grounding_response_span_offset=15,
            )
        attempt = base_attempt
        attempt_store.put(attempt)
        rendered_prompt_text = expected_s7_voice_rendered_prompt_text(
            rendered_statement=rendered,
            maez_voice_consultation=consultation,
        )
        manifest = bundle_store.put_reviewed_context_manifest(
            manifest_id="context-manifest-live-route",
            preview_ref=f"preview:{rendered.request_id}",
            request_envelope_hash=rendered.request_envelope_hash,
            precondition_hash=material.kwargs["precondition_hash"],
            rollback_path_class=envelope.rollback_path_class,
            source_surface=rendered.surface,
            proposal_origin_label="operator",
            created_at=NOW,
        )
        self.assertEqual(manifest.context_manifest_hash, binding.context_manifest_hash)
        bundle_store.put_raw_response("raw-response-live-route", raw_text)
        bundle_store.put_rendered_prompt("rendered-prompt-live-route", rendered_prompt_text)
        bundle = S7VoiceConsultationBundle(
            source_ref_hash=consultation.source_ref_hash,
            request_id=rendered.request_id,
            consultation_id=consultation.consultation_id,
            request_envelope_hash=binding.request_envelope_hash,
            rendered_text_hash=binding.rendered_text_hash,
            action_params_hash=binding.action_params_hash,
            precondition_hash=binding.precondition_hash,
            authority_context_hash=binding.authority_context_hash,
            maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
            rendered_prompt_ref="rendered-prompt-live-route",
            rendered_prompt_hash=binding.rendered_prompt_hash,
            mutation_preview_hash=binding.mutation_preview_hash,
            rollback_plan_ref=binding.rollback_plan_ref,
            context_manifest_ref=manifest.manifest_id,
            context_manifest_hash=binding.context_manifest_hash,
            runtime_identity_hash=binding.runtime_identity_hash,
            model_routing_identity_hash=binding.model_routing_identity_hash,
            model_config_hash=binding.model_config_hash,
            raw_response_ref="raw-response-live-route",
            raw_response_hash=s7.canonical_hash(raw_text),
            semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
            expires_at="2026-05-18T11:05:00+00:00",
            authority_class=authority_class,
            has_grounded_semantic_blocking_signal=has_grounded_semantic_blocking_signal,
        )
        bundle_store.put_bundle(
            S7VoiceConsultationBundle(
                **{
                    **bundle.__dict__,
                    "source_bundle_hash": s7_voice_consultation_bundle_hash(bundle),
                }
            )
        )
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=rendered.request_id,
                source_ref_hash=consultation.source_ref_hash,
                consultation_id=consultation.consultation_id,
                used_at=NOW,
            )
        )
        return binding

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
            "S7_WEBAUTHN_PROOF_ROUTES": "1",
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
            "S7_WEBAUTHN_PROOF_ROUTES": "1",
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

    def test_daemon_voice_seat_finish_rejects_missing_source_bundle_before_service(self):
        called = {"service": False}

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **_kwargs):
                called["service"] = True
                raise AssertionError("voice-seat finish must validate source bundle before service")

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": f"{tmp}/memory/s7_1_webauthn",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                        response = self._client(
                            configure_daemon=self._daemon_with_self_mod_pipeline(
                                "req-voice-missing-bundle"
                            )
                        ).post(
                            "/internal/s7/cards/req-voice-missing-bundle/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": "challenge-route",
                                "credential_ref": "cred-primary",
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "s7_guarded_source_bundle_required")
        self.assertFalse(called["service"])

    def test_daemon_voice_seat_finish_supplies_validator_result_from_derived_binding(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from daemon import maez_daemon

        seen = {}
        request_id = "req-voice-valid-bundle"

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **kwargs):
                seen.update(kwargs)

                class Result:
                    status_code = 209
                    body = {"ok": True, "request_id": kwargs["rendered_statement"].request_id}

                return Result()

        with tempfile.TemporaryDirectory() as tmp:
            store_root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(store_root)
            daemon = MaezDaemon.__new__(MaezDaemon)
            self._daemon_with_self_mod_pipeline(request_id)(daemon)
            material = maez_daemon._s7_authorization_route_material(
                daemon,
                self._route_request(session_binding="session-auth", challenge_id="challenge-route"),
                request_id=request_id,
                now=NOW,
                store=store,
            )
            self.assertTrue(material.ok)
            binding = self._seed_valid_voice_bundle_for_material(store.db_path, material)
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": store_root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                        response = self._client(
                            configure_daemon=self._daemon_with_self_mod_pipeline(request_id)
                        ).post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": "challenge-route",
                                "credential_ref": "cred-primary",
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 209)
        self.assertEqual(seen["source_bundle_validation"].status, "valid_absent")
        self.assertTrue(seen["source_bundle_validation"].source_bundle_valid)
        self.assertEqual(seen["source_ref_hash"], binding.source_ref_hash)
        self.assertIsNotNone(seen["guarded_store"])
        self.assertTrue(seen["reservation_token"])

    def test_daemon_voice_seat_finish_passes_grounded_objection_to_service(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from daemon import maez_daemon

        seen = {}
        request_id = "req-voice-grounded-objection"

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **kwargs):
                seen.update(kwargs)

                class Result:
                    status_code = 409
                    body = {
                        "ok": False,
                        "error": "s7_voice_seat_unresolved",
                        "reason": "maez_voice_not_clear",
                    }

                return Result()

        with tempfile.TemporaryDirectory() as tmp:
            store_root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(store_root)
            daemon = MaezDaemon.__new__(MaezDaemon)
            self._daemon_with_self_mod_pipeline(
                request_id,
                maez_objection_state="present",
            )(daemon)
            material = maez_daemon._s7_authorization_route_material(
                daemon,
                self._route_request(session_binding="session-auth", challenge_id="challenge-route"),
                request_id=request_id,
                now=NOW,
                store=store,
            )
            self.assertTrue(material.ok)
            self._seed_valid_voice_bundle_for_material(
                store.db_path,
                material,
                maez_objection_state="present",
            )
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": store_root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                        response = self._client(
                            configure_daemon=self._daemon_with_self_mod_pipeline(
                                request_id,
                                maez_objection_state="present",
                            )
                        ).post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": "challenge-route",
                                "credential_ref": "cred-primary",
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "s7_voice_seat_unresolved")
        self.assertEqual(seen["source_bundle_validation"].status, "blocking_present")
        self.assertFalse(seen["source_bundle_validation"].mint_eligible)
        self.assertEqual(
            seen["source_bundle_validation"].authority_projection,
            "grounded_refusal",
        )

    def test_daemon_voice_seat_finish_rejects_resealed_bundle_copied_binding(self):
        from dataclasses import replace

        from core.governance.s7_guarded_execution import (
            S7VoiceConsultationBundleStore,
            s7_voice_consultation_bundle_hash,
        )
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from daemon import maez_daemon

        called = {"service": False}
        request_id = "req-voice-circular-bundle"

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **_kwargs):
                called["service"] = True
                raise AssertionError("circular bundle-derived binding must not reach service")

        with tempfile.TemporaryDirectory() as tmp:
            store_root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(store_root)
            daemon = MaezDaemon.__new__(MaezDaemon)
            self._daemon_with_self_mod_pipeline(request_id)(daemon)
            material = maez_daemon._s7_authorization_route_material(
                daemon,
                self._route_request(session_binding="session-auth", challenge_id="challenge-route"),
                request_id=request_id,
                now=NOW,
                store=store,
            )
            self.assertTrue(material.ok)
            binding = self._seed_valid_voice_bundle_for_material(store.db_path, material)
            bundle_store = S7VoiceConsultationBundleStore(store.db_path)
            bundle = bundle_store.get_for_source_ref(binding.source_ref_hash)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            resealed = replace(
                bundle,
                action_params_hash="f" * 64,
                source_bundle_hash=None,
            )
            resealed = replace(
                resealed,
                source_bundle_hash=s7_voice_consultation_bundle_hash(resealed),
            )
            with sqlite3.connect(store.db_path) as conn:
                conn.execute(
                    """
                    UPDATE s7_voice_consultation_bundles
                    SET action_params_hash = ?, source_bundle_hash = ?
                    WHERE source_ref_hash = ?
                    """,
                    (
                        resealed.action_params_hash,
                        resealed.source_bundle_hash,
                        binding.source_ref_hash,
                    ),
                )
                conn.commit()
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": store_root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch("daemon.maez_daemon.S7LocalWebAuthnCeremonyService", Service):
                        response = self._client(
                            configure_daemon=self._daemon_with_self_mod_pipeline(request_id)
                        ).post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": "challenge-route",
                                "credential_ref": "cred-primary",
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "s7_guarded_source_bundle_required")
        self.assertFalse(called["service"])

    def test_live_binding_deriver_structurally_excludes_bundle_input(self):
        from core.governance.s7_guarded_execution import (
            derive_s7_voice_source_bundle_hash_binding,
        )

        params = inspect.signature(derive_s7_voice_source_bundle_hash_binding).parameters

        self.assertEqual(
            tuple(params),
            (
                "rendered_statement",
                "envelope",
                "maez_voice_consultation",
                "authority_context",
                "precondition_hash",
            ),
        )
        self.assertNotIn("bundle", params)
        self.assertNotIn("source_bundle", params)

    def test_daemon_backup_register_begin_passes_s7_execution_authorization_to_service(self):
        seen = {}

        class Service:
            def __init__(self, **_kwargs):
                pass

            def register_begin(self, **kwargs):
                seen.update(kwargs)

                class Result:
                    status_code = 210
                    body = {
                        "ok": True,
                        "has_authorization": kwargs["s7_execution_authorization"] is not None,
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
                        configure_daemon=self._daemon_with_card_pipeline("req-backup-register")
                    ).post(
                        "/internal/s7/webauthn/register/begin",
                        json={
                            "registration_class": "backup",
                            "session_binding": "session-backup",
                            "backup_authorization_request_id": "req-backup-register",
                            "s7_authorization_artifact_id": "artifact-backup-register",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(response.status_code, 210)
        self.assertTrue(response.get_json()["has_authorization"])
        self.assertEqual(seen["request_json"]["registration_class"], "backup")

    def test_daemon_backup_registration_card_route_creates_pending_request(self):
        created = {}

        class Card:
            request_id = "req-backup-register"
            status = "open"

        class Store:
            def create_card(self, **kwargs):
                created.update(kwargs)
                return Card()

        class Pipe:
            card_store = Store()

        class Telegram:
            def _get_pipeline(self):
                return Pipe()

        def configure(daemon):
            daemon.telegram = Telegram()

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            response = self._client(configure_daemon=configure).post(
                "/internal/s7/webauthn/register/backup-card",
                json={"session_binding": "session-backup-card"},
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(body["ok"])
        self.assertEqual(body["request_id"], "req-backup-register")
        self.assertEqual(created["action"], "register_backup_webauthn_credential")
        self.assertEqual(created["params"]["registration_class"], "backup")
        self.assertEqual(created["channel"], "cockpit_s7_1_manual_proof")
        self.assertEqual(created["user_id"], "rohit")

    def test_proof_only_disable_routes_are_disabled_without_proof_flag(self):
        class Store:
            def create_card(self, **_kwargs):
                raise AssertionError("disable proof route must not create cards without proof flag")

        class Pipe:
            card_store = Store()

        class Telegram:
            def _get_pipeline(self):
                return Pipe()

        def configure(daemon):
            daemon.telegram = Telegram()

        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            client = self._client(configure_daemon=configure)
            card_response = client.post(
                "/internal/s7/webauthn/proof/disable-card",
                json={"credential_ref": "cred-backup", "credential_kind": "backup"},
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )
            finish_response = client.post(
                "/internal/s7/webauthn/proof/disable-credential",
                json={
                    "credential_ref": "cred-backup",
                    "s7_authorization_artifact_id": "s7authz_test",
                },
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )

        self.assertEqual(card_response.status_code, 404)
        self.assertEqual(card_response.get_json()["error"], "s7_proof_route_disabled")
        self.assertEqual(finish_response.status_code, 404)
        self.assertEqual(finish_response.get_json()["error"], "s7_proof_route_disabled")

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
                "S7_WEBAUTHN_PROOF_ROUTES": "1",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7ProductionWebAuthnVerifier", _RouteAuthenticationVerifier):
                    client = self._client(
                        configure_daemon=self._daemon_with_card_pipeline("req-route-live")
                    )
                    begin = client.post(
                        "/internal/s7/cards/req-route-live/webauthn/begin",
                        json={
                            "session_binding": "session-auth",
                            "credential_ref": "cred-primary",
                        },
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

    def test_daemon_backup_register_begin_consumes_primary_authorization_artifact(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
                "S7_WEBAUTHN_PROOF_ROUTES": "1",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7ProductionWebAuthnVerifier", _RouteAuthenticationVerifier):
                    client = self._client(
                        configure_daemon=self._daemon_with_backup_registration_pipeline(
                            "req-backup-live"
                        )
                    )
                    authorize_begin = client.post(
                        "/internal/s7/cards/req-backup-live/webauthn/begin",
                        json={
                            "session_binding": "session-auth",
                            "credential_ref": "cred-primary",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    authorize_finish = client.post(
                        "/internal/s7/cards/req-backup-live/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": authorize_begin.get_json()["challenge_id"],
                            "credential_ref": "cred-primary",
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    register_begin = client.post(
                        "/internal/s7/webauthn/register/begin",
                        json={
                            "registration_class": "backup",
                            "session_binding": "session-backup",
                            "backup_authorization_request_id": "req-backup-live",
                            "s7_authorization_artifact_id": authorize_finish.get_json()[
                                "artifact_id"
                            ],
                            "authorization_challenge_id": authorize_begin.get_json()[
                                "challenge_id"
                            ],
                            "authorization_session_binding": "session-auth",
                            "authorization_credential_ref": "cred-primary",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(authorize_begin.status_code, 200)
        self.assertEqual(authorize_finish.status_code, 200)
        self.assertEqual(register_begin.status_code, 200)
        self.assertEqual(register_begin.get_json()["registration_class"], "backup")

    def test_daemon_backup_authorization_infers_single_primary_when_credential_ref_omitted(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7ProductionWebAuthnVerifier", _RouteAuthenticationVerifier):
                    client = self._client(
                        configure_daemon=self._daemon_with_backup_registration_pipeline(
                            "req-backup-infer-primary"
                        )
                    )
                    authorize_begin = client.post(
                        "/internal/s7/cards/req-backup-infer-primary/webauthn/begin",
                        json={"session_binding": "session-auth"},
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    authorize_finish = client.post(
                        "/internal/s7/cards/req-backup-infer-primary/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": authorize_begin.get_json()["challenge_id"],
                            "credential_ref": "cred-primary",
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(authorize_begin.status_code, 200)
        self.assertEqual(authorize_finish.status_code, 200)
        self.assertEqual(authorize_finish.get_json()["request_id"], "req-backup-infer-primary")

    def test_daemon_proof_disable_credential_consumes_matching_s7_artifact(self):
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
                "S7_WEBAUTHN_PROOF_ROUTES": "1",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.S7ProductionWebAuthnVerifier", _RouteAuthenticationVerifier):
                    client = self._client(
                        configure_daemon=self._daemon_with_disable_credential_pipeline(
                            "req-disable-primary",
                            "cred-primary",
                        )
                    )
                    authorize_begin = client.post(
                        "/internal/s7/cards/req-disable-primary/webauthn/begin",
                        json={
                            "session_binding": "session-auth",
                            "credential_ref": "cred-primary",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    authorize_finish = client.post(
                        "/internal/s7/cards/req-disable-primary/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": authorize_begin.get_json()["challenge_id"],
                            "credential_ref": "cred-primary",
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    disable = client.post(
                        "/internal/s7/webauthn/proof/disable-credential",
                        json={
                            "credential_ref": "cred-primary",
                            "disable_authorization_request_id": "req-disable-primary",
                            "s7_authorization_artifact_id": authorize_finish.get_json()[
                                "artifact_id"
                            ],
                            "authorization_challenge_id": authorize_begin.get_json()[
                                "challenge_id"
                            ],
                            "authorization_session_binding": "session-auth",
                            "authorization_credential_ref": "cred-primary",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

            disabled = store.get_credential("cred-primary")

        self.assertEqual(authorize_begin.status_code, 200)
        self.assertEqual(authorize_finish.status_code, 200)
        self.assertEqual(disable.status_code, 200)
        self.assertEqual(disable.get_json()["credential_ref"], "cred-primary")
        self.assertEqual(disable.get_json()["ceremony_mode"], "degraded")
        self.assertIsNotNone(disabled)
        assert disabled is not None
        self.assertFalse(disabled.enabled)
        self.assertEqual(
            disabled.disabled_by_authorization_id,
            authorize_finish.get_json()["artifact_id"],
        )

    def test_daemon_proof_disable_backup_can_authorize_after_primary_disabled(self):
        from dataclasses import replace

        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = S7WebAuthnBootstrapStore(root)
            store.store_credential(
                replace(self._credential_record("cred-primary", kind="primary"), enabled=False)
            )
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                client = self._client(
                    configure_daemon=self._daemon_with_disable_credential_pipeline(
                        "req-disable-backup",
                        "cred-backup",
                        credential_kind="backup",
                    )
                )
                authorize_begin = client.post(
                    "/internal/s7/cards/req-disable-backup/webauthn/begin",
                    json={
                        "session_binding": "session-auth",
                        "credential_ref": "cred-backup",
                    },
                    headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                )

        self.assertEqual(authorize_begin.status_code, 200)
        self.assertEqual(tuple(authorize_begin.get_json()["allow_credentials"]), ("cred-backup",))

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
