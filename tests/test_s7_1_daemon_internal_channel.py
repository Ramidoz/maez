"""S7.1 daemon internal-channel authority-route tests."""

from __future__ import annotations

import os
import inspect
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from daemon import maez_daemon as D
from daemon.maez_daemon import MaezDaemon
from tests.s7_store_fixture import bootstrap_with_authorization

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


class S7InternalChannelRuntimeToken(unittest.TestCase):
    def test_presented_internal_channel_logs_when_runtime_token_absent(self):
        req = SimpleNamespace(
            headers={
                D.S7_INTERNAL_CHANNEL_HEADER: "presented-token",
            }
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertLogs("maez", level="WARNING") as logs:
                self.assertFalse(D._s7_internal_channel_trusted(req))

        rendered = "\n".join(logs.output)
        self.assertIn("S7 internal channel token absent from os.environ", rendered)


class _FixedDateTime:
    @staticmethod
    def fromisoformat(value):
        return datetime.fromisoformat(value)

    @staticmethod
    def now(_tz=None):
        return datetime.fromisoformat(NOW)


class _CountingActionEngine:
    def __init__(self):
        self.calls = []

    def _execute_action(
        self,
        action,
        params,
        reason,
        *,
        tier,
        s7_execution_grant=None,
        s7_authorization_params=None,
    ):
        del s7_authorization_params
        self.calls.append((action, dict(params or {}), reason, tier, s7_execution_grant))
        if action == "write_any_file":
            Path(params["path"]).write_text(params["content"], encoding="utf-8")
        return SimpleNamespace(success=True, output="executed", error="")


class _DaemonAppClientMixin:
    """Captured-app test-client helper shared by daemon-route test cases.

    Provides only the ``_run_health_server`` capture machinery (and its
    ``_FakeServer``/``_StopServer`` deps) so a TestCase can drive the daemon's
    Flask app under a Werkzeug test client — without inheriting any sibling's
    test methods.
    """

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

    def _client_for_daemon(self, daemon):
        captured = {}

        def fake_make_server(_host, _port, app):
            captured["app"] = app
            return _FakeServer()

        with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
            with self.assertRaises(_StopServer):
                daemon._run_health_server()
        return captured["app"].test_client()


class S71DaemonInternalChannelTests(_DaemonAppClientMixin, unittest.TestCase):
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

    def _live_self_mod_daemon(
        self,
        root: str,
        request_id: str,
        *,
        rollback_path_class=None,
        use_live_voice_producer: bool = False,
        voice_raw_response: str = "Maez says there is no objection.",
        voice_reader_attempt=None,
        expected_post_hash: str | None = None,
    ):
        from dataclasses import replace

        from core import decision_pipeline as _dp
        from core.audit import AuditVerdict, Decision
        from core.audit_log import AuditLog
        from core.decision.pending_cards import PendingCardStore
        from core.decision_pipeline import DecisionPipeline
        from core.governance import operator_user_boundary as s7
        from core.governance import s7_guarded_execution as s7_guarded
        from skills.self_mod_dialog import SelfModDialogStore, open_dialog_for_card

        root_path = Path(root)
        engine = _CountingActionEngine()
        card_store = PendingCardStore(root_path / "cards.db")
        audit_log = AuditLog(root_path / "audit.db")
        pipeline = DecisionPipeline(
            action_engine=engine,
            card_store=card_store,
            audit_log=audit_log,
        )
        dialog_store = SelfModDialogStore(root_path / "dialogs.db")
        pipeline._dialog_store = dialog_store
        target = root_path / "config" / "soul.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# before", encoding="utf-8")
        params = {
            "path": str(target),
            "content": "# after",
            "s7_expected_post_mutation_hash": expected_post_hash or s7.canonical_hash(b"# after"),
        }
        state_fields = _dp._drop_volatile(_dp._fingerprint_for_action("write_any_file", params))
        card = card_store.create_card(
            action="write_any_file",
            params=params,
            reason="self-mod",
            audit_verdict=AuditVerdict(
                decision=Decision.ESCALATE,
                confidence=0.9,
                reasoning="self-modification requires S7",
                concerns=["modifies soul"],
                mitigations=[],
                summary="self mod",
                answers={},
                nonce="nonce",
                latency_ms=1,
            ),
            audit_request_id=f"audit-{request_id}",
            classification={"intent_category": "SELF_MODIFICATION", "lane": "3"},
            state_fields=state_fields,
            channel="cockpit",
            chat_id="s7-live",
            user_id="rohit",
        )
        original_envelope = pipeline._s7_request_envelope_for_card

        if rollback_path_class is not None:
            def _envelope_with_rollback(_card):
                return replace(
                    original_envelope(_card),
                    rollback_path_class=rollback_path_class,
                )

            pipeline._s7_request_envelope_for_card = _envelope_with_rollback

        actual_request_id = card.request_id
        envelope = pipeline._s7_request_envelope_for_card(card)

        if use_live_voice_producer:
            pipeline._s7_voice_raw_response_for_card = (
                lambda *_args, **_kwargs: voice_raw_response
            )
            pipeline._s7_semantic_reader_attempt_for_voice_response = (
                lambda *_args, **_kwargs: voice_reader_attempt
                or s7_guarded.S7SemanticReaderAttemptEvidence.reviewed_v1()
            )
        else:
            def _voice_consultation(_card, _envelope):
                return s7.MaezVoiceConsultation(
                    consultation_id=getattr(_envelope, "maez_voice_consultation_id", None)
                    or f"voice-{actual_request_id}",
                    request_id=actual_request_id,
                    request_envelope_hash=s7.work_request_envelope_hash(_envelope),
                    producer="s7_voice_consultation_turn",
                    source_ref_kind="s7_voice_turn",
                    source_ref_hash=s7.canonical_hash({"voice": actual_request_id}),
                    maez_voice_consulted=True,
                    maez_objection_state="absent",
                    maez_withdrew_request=False,
                    unavailable_reason_code=None,
                    created_at=NOW,
                )

            pipeline._s7_voice_consultation_for_card = _voice_consultation
        open_dialog_for_card(
            store=dialog_store,
            card_action=card.action,
            card_params=card.params,
            card_request_id=card.request_id,
            audit_reasoning=card.audit_reasoning,
            concerns=list(card.audit_concerns or []),
            opener_llm_fn=lambda _ctx: "I want to change myself.",
            require_s7_linkage=True,
            s7_request_envelope_hash=s7.work_request_envelope_hash(envelope),
        )

        class Telegram:
            def _get_pipeline(self):
                return pipeline

        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon._health_server = None
        daemon.telegram = Telegram()
        return daemon, pipeline, engine, card, target

    def _mint_self_mod_artifact(self, *, client, daemon, store, request_id: str):
        from daemon import maez_daemon

        begin = client.post(
            f"/internal/s7/cards/{request_id}/webauthn/begin",
            json={
                "session_binding": "session-auth",
                "credential_ref": "cred-primary",
            },
            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
        )
        self.assertEqual(begin.status_code, 200, begin.get_json())
        begin_body = begin.get_json()
        challenge_id = begin_body["challenge_id"]
        material = maez_daemon._s7_authorization_route_material(
            daemon,
            self._route_request(
                session_binding="session-auth",
                challenge_id=challenge_id,
            ),
            request_id=request_id,
            now=NOW,
            store=store,
        )
        self.assertTrue(material.ok)
        if not begin_body.get("maez_voice_raw_response_hash"):
            self._seed_valid_voice_bundle_for_material(store.db_path, material)
        founder_seen_hash = (
            begin_body.get("maez_voice_raw_response_hash")
            or self._seeded_voice_raw_response_hash()
        )
        finish = client.post(
            f"/internal/s7/cards/{request_id}/webauthn/finish",
            json={
                "session_binding": "session-auth",
                "challenge_id": challenge_id,
                "credential_ref": "cred-primary",
                "maez_voice_raw_response_hash": founder_seen_hash,
                "authentication_response": {"clientDataJSON": "valid-auth"},
            },
            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
        )
        self.assertEqual(finish.status_code, 200)
        return begin, finish

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
        pending_voice_sources = getattr(self, "_seeded_voice_pending", {})

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
            _s7_pending_voice_source_bundles = pending_voice_sources

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

    def _seeded_voice_raw_response_hash(self, *, maez_objection_state: str = "absent"):
        from core.governance import operator_user_boundary as s7

        if maez_objection_state == "present":
            return s7.canonical_hash("Maez says: no, do not make this change.")
        return s7.canonical_hash("Maez says there is no objection.")

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
            put_voice_source_bundle_v2,
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
            action=rendered.action,
        )
        bundle = S7VoiceConsultationBundle(
            **{
                **bundle.__dict__,
                "source_bundle_hash": s7_voice_consultation_bundle_hash(bundle),
            }
        )
        authorization_store = s7.S7AuthorizationStore(db_path)
        with authorization_store.anchored_transaction() as conn:
            put_voice_source_bundle_v2(bundle=bundle, conn=conn)
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=rendered.request_id,
                source_ref_hash=consultation.source_ref_hash,
                consultation_id=consultation.consultation_id,
                used_at=NOW,
            )
        )
        pipe = material.kwargs.get("pipe")
        pending = getattr(self, "_seeded_voice_pending", {})
        if not isinstance(pending, dict):
            pending = {}
        pending[rendered.request_id] = {
            "raw_response_text": raw_text,
            "semantic_reader_attempt": attempt,
            "source_ref_hash": consultation.source_ref_hash,
        }
        self._seeded_voice_pending = pending
        if pipe is not None:
            setattr(pipe, "_s7_pending_voice_source_bundles", pending)
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

    def test_daemon_voice_seat_finish_rejects_empty_founder_visible_voice_payload_before_service(self):
        called = {"service": False}

        class Service:
            def __init__(self, **_kwargs):
                pass

            def authorize_finish(self, **_kwargs):
                called["service"] = True
                raise AssertionError("voice-seat finish must validate source bundle before service")

        with tempfile.TemporaryDirectory() as tmp:
            store_root = f"{tmp}/memory/s7_1_webauthn"
            bootstrap_with_authorization(store_root)
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
                                "req-voice-missing-bundle"
                            )
                        ).post(
                            "/internal/s7/cards/req-voice-missing-bundle/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": "challenge-route",
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": (
                                    self._seeded_voice_raw_response_hash()
                                ),
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["error"],
            "s7_founder_seen_maez_voice_hash_required",
        )
        self.assertFalse(called["service"])

    def test_daemon_voice_seat_finish_supplies_validator_result_from_derived_binding(self):
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
            store = bootstrap_with_authorization(store_root)
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
                                "maez_voice_raw_response_hash": (
                                    self._seeded_voice_raw_response_hash()
                                ),
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 209)
        self.assertEqual(seen["source_bundle_validation"].status, "valid_absent")
        self.assertTrue(seen["source_bundle_validation"].source_bundle_valid)
        self.assertEqual(seen.get("source_bundle_binding"), binding)
        self.assertEqual(seen["source_ref_hash"], binding.source_ref_hash)
        self.assertIsNotNone(seen["guarded_store"])
        self.assertTrue(seen["reservation_token"])

    def test_daemon_voice_seat_finish_passes_grounded_objection_to_service(self):
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
            store = bootstrap_with_authorization(store_root)
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
                                "maez_voice_raw_response_hash": (
                                    self._seeded_voice_raw_response_hash(
                                        maez_objection_state="present"
                                    )
                                ),
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

        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            read_voice_source_bundle,
            s7_voice_consultation_bundle_hash,
        )
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
            store = bootstrap_with_authorization(store_root)
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
            authorization_store = s7.S7AuthorizationStore(store.db_path)
            with authorization_store.anchored_transaction() as conn:
                bundle, _version = read_voice_source_bundle(
                    source_ref_hash=binding.source_ref_hash,
                    conn=conn,
                )
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
                    UPDATE s7_voice_source_bundles_v2
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
                                "maez_voice_raw_response_hash": (
                                    self._seeded_voice_raw_response_hash()
                                ),
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "s7_guarded_source_bundle_required")
        self.assertFalse(called["service"])

    def test_daemon_s7_execute_consumes_fresh_artifact_and_records_trace(self):

        request_id = "req-s7-execute-live"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin, finish = self._mint_self_mod_artifact(
                            client=client,
                            daemon=daemon,
                            store=store,
                            request_id=request_id,
                        )
                        execute = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json={
                                "session_binding": "session-auth",
                                "authorization_challenge_id": begin.get_json()[
                                    "challenge_id"
                                ],
                                "authorization_credential_ref": "cred-primary",
                                "s7_authorization_artifact_id": finish.get_json()[
                                    "artifact_id"
                                ],
                                "text": "yes",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            with sqlite3.connect(store.db_path) as conn:
                artifact_row = conn.execute(
                    """
                    SELECT consumed_at, consumed_by_request_id
                    FROM s7_authorization_artifacts_v2
                    WHERE artifact_id = ?
                    """,
                    (finish.get_json()["artifact_id"],),
                ).fetchone()
                trace_row = conn.execute(
                    """
                    SELECT request_id, artifact_id, execution_status, rollback_path_class
                    FROM s7_guarded_execution_traces
                    WHERE artifact_id = ?
                    """,
                    (finish.get_json()["artifact_id"],),
                ).fetchone()
            target_text = _target.read_text(encoding="utf-8")

        self.assertEqual(execute.status_code, 200, execute.get_json())
        self.assertTrue(execute.get_json()["ok"])
        self.assertEqual(execute.get_json()["status"], "executed")
        self.assertEqual(len(engine.calls), 1)
        self.assertIsNotNone(artifact_row)
        assert artifact_row is not None
        self.assertIsNotNone(artifact_row[0])
        self.assertEqual(artifact_row[1], request_id)
        self.assertIsNotNone(trace_row)
        assert trace_row is not None
        self.assertEqual(trace_row[0], request_id)
        self.assertEqual(trace_row[1], finish.get_json()["artifact_id"])
        self.assertEqual(trace_row[2], "executed")
        self.assertEqual(trace_row[3], "revert_patch")
        self.assertEqual(target_text, "# after")

    def test_daemon_s7_execute_blocks_wrong_expected_post_hash_before_mutation(self):

        request_id = "req-s7-execute-post-hash-mismatch"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, engine, card, target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
                expected_post_hash="f" * 64,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin, finish = self._mint_self_mod_artifact(
                            client=client,
                            daemon=daemon,
                            store=store,
                            request_id=request_id,
                        )
                        execute = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json={
                                "session_binding": "session-auth",
                                "authorization_challenge_id": begin.get_json()[
                                    "challenge_id"
                                ],
                                "authorization_credential_ref": "cred-primary",
                                "s7_authorization_artifact_id": finish.get_json()[
                                    "artifact_id"
                                ],
                                "text": "yes",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            with sqlite3.connect(store.db_path) as conn:
                trace_row = conn.execute(
                    """
                    SELECT execution_status, execution_success
                    FROM s7_guarded_execution_traces
                    WHERE request_id = ?
                    """,
                    (request_id,),
                ).fetchone()
            target_text = target.read_text(encoding="utf-8")

        self.assertNotEqual(execute.status_code, 200)
        self.assertEqual(len(engine.calls), 0)
        self.assertEqual(target_text, "# before")
        self.assertIn("post_mutation_hash", execute.get_json()["message"])
        self.assertIsNotNone(trace_row)
        assert trace_row is not None
        self.assertEqual(trace_row[0], "blocked")
        self.assertEqual(trace_row[1], 0)

    def test_daemon_voice_seat_finish_live_producer_persists_bundle_without_test_seed(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7VoiceBundleUseStore,
            read_voice_source_bundle,
        )

        request_id = "req-s7-live-producer"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        self.assertEqual(begin.status_code, 200)
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": begin.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            bundle_use_store = S7VoiceBundleUseStore(store.db_path)
            bundle_uses = []
            with sqlite3.connect(store.db_path) as conn:
                bundle_uses = list(
                    conn.execute(
                        "SELECT source_ref_hash FROM s7_voice_bundle_uses WHERE request_id = ?",
                        (request_id,),
                    )
                )
            self.assertEqual(finish.status_code, 200, finish.get_json())
            self.assertTrue(finish.get_json()["ok"])
            self.assertEqual(
                begin.get_json()["maez_voice_raw_response"],
                "Maez says there is no objection.",
            )
            self.assertEqual(len(bundle_uses), 1)
            authorization_store = s7.S7AuthorizationStore(store.db_path)
            with authorization_store.anchored_transaction() as conn:
                bundle, _version = read_voice_source_bundle(
                    source_ref_hash=bundle_uses[0][0],
                    conn=conn,
                )
            self.assertIsNotNone(bundle)
            assert bundle is not None
            self.assertEqual(
                bundle.raw_response_hash,
                begin.get_json()["maez_voice_raw_response_hash"],
            )
            use = bundle_use_store.get_for_source_ref(bundle_uses[0][0])
            self.assertIsNotNone(use)
            assert use is not None
        self.assertEqual(use.reservation_state, "reserved")

    def test_daemon_voice_seat_finish_rejects_stale_unreserved_retry_bundle(self):
        from daemon import maez_daemon

        request_id = "req-s7-live-producer-retry"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        first = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        self.assertEqual(first.status_code, 200)
                        first_material = maez_daemon._s7_authorization_route_material(
                            daemon,
                            self._route_request(
                                session_binding="session-auth",
                                challenge_id=first.get_json()["challenge_id"],
                            ),
                            request_id=request_id,
                            now="2026-05-18T11:00:01+00:00",
                            store=store,
                        )
                        self.assertTrue(first_material.ok)
                        pipeline._persist_s7_voice_source_bundle_for_card(
                            card=first_material.kwargs["card"],
                            db_path=store.db_path,
                            rendered_statement=first_material.kwargs["rendered_statement"],
                            envelope=first_material.kwargs["envelope"],
                            maez_voice_consultation=first_material.kwargs[
                                "maez_voice_consultation"
                            ],
                            authority_context=first_material.kwargs["authority_context"],
                            precondition_hash=first_material.kwargs["precondition_hash"],
                            now=NOW,
                        )
                        second = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth-retry",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        self.assertEqual(second.status_code, 200)
                        self.assertNotEqual(
                            first_material.kwargs["rendered_statement"].rendered_text_hash,
                            second.get_json()["rendered_text_hash"],
                        )
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth-retry",
                                "challenge_id": second.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": second.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(finish.status_code, 409, finish.get_json())
        self.assertEqual(finish.get_json()["error"], "s7_guarded_source_bundle_required")
        self.assertEqual(finish.get_json()["detail"], "invalid_hash_binding")

    def test_daemon_voice_seat_begin_persists_d12_bundle_before_finish(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import read_voice_source_bundle

        request_id = "req-s7-begin-persists-d12-bundle"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch(
                    "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                    _RouteAuthenticationVerifier,
                ):
                    client = self._client_for_daemon(daemon)
                    begin = client.post(
                        f"/internal/s7/cards/{request_id}/webauthn/begin",
                        json={
                            "session_binding": "session-auth",
                            "credential_ref": "cred-primary",
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    self.assertEqual(begin.status_code, 200)
                    begin_body = begin.get_json()
                    authorization_store = s7.S7AuthorizationStore(store.db_path)
                    with authorization_store.anchored_transaction() as conn:
                        bundle, _version = read_voice_source_bundle(
                            source_ref_hash=begin_body["maez_voice_source_ref_hash"],
                            conn=conn,
                        )
                    self.assertIsNotNone(bundle)
                    assert bundle is not None
                    self.assertEqual(bundle.rendered_text_hash, begin_body["rendered_text_hash"])
                    self.assertEqual(
                        bundle.maez_voice_consultation_hash,
                        begin_body["maez_voice_consultation_hash"],
                    )

                    # A finish-time producer drift must not replace the source
                    # bundle that was shown to the founder and bound into D12.
                    pending = pipeline._s7_pending_voice_source_bundles[request_id]
                    pending["raw_response_text"] = "I object to this if asked again."
                    finish = client.post(
                        f"/internal/s7/cards/{request_id}/webauthn/finish",
                        json={
                            "session_binding": "session-auth",
                            "challenge_id": begin_body["challenge_id"],
                            "credential_ref": "cred-primary",
                            "maez_voice_raw_response_hash": begin_body[
                                "maez_voice_raw_response_hash"
                            ],
                            "authentication_response": {"clientDataJSON": "valid-auth"},
                        },
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )

        self.assertEqual(finish.status_code, 200, finish.get_json())
        self.assertTrue(finish.get_json()["ok"])

    def test_daemon_authorize_finish_replays_begin_rendered_timestamp_for_d12(self):

        request_id = "req-s7-finish-replays-begin-rendered-at"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            class _BeginDateTime:
                @staticmethod
                def fromisoformat(value):
                    return datetime.fromisoformat(value)

                @staticmethod
                def now(_tz=None):
                    return datetime.fromisoformat("2026-05-18T11:00:00+00:00")

            class _FinishDateTime:
                @staticmethod
                def fromisoformat(value):
                    return datetime.fromisoformat(value)

                @staticmethod
                def now(_tz=None):
                    return datetime.fromisoformat("2026-05-18T11:02:00+00:00")

            with patch.dict(os.environ, env, clear=False):
                with patch(
                    "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                    _RouteAuthenticationVerifier,
                ):
                    client = self._client_for_daemon(daemon)
                    with patch("daemon.maez_daemon.datetime", _BeginDateTime):
                        begin = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                    self.assertEqual(begin.status_code, 200)
                    with patch("daemon.maez_daemon.datetime", _FinishDateTime):
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": begin.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(finish.status_code, 200, finish.get_json())
        self.assertTrue(finish.get_json()["ok"])

    def test_daemon_authorize_begin_binds_default_credential_when_ui_leaves_blank(self):

        request_id = "req-s7-begin-default-credential"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            primary = self._credential_record("cred-primary", kind="primary")
            store.store_credential(primary)
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch(
                    "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                    _RouteAuthenticationVerifier,
                ):
                    client = self._client_for_daemon(daemon)
                    begin = client.post(
                        f"/internal/s7/cards/{request_id}/webauthn/begin",
                        json={"session_binding": "session-auth"},
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                    )
                    self.assertEqual(begin.status_code, 200)
                    credential_ref = begin.get_json()["allow_credentials"][0]
                    class Verifier:
                        def dependency_state(self):
                            return {
                                "ok": True,
                                "library_name": "webauthn",
                                "library_version": "2.7.1",
                            }

                        def verify_authentication_response(self, **_kwargs):
                            return {
                                "ok": True,
                                "credential_ref": credential_ref,
                                "sign_count": 1,
                                "user_presence": True,
                                "user_verification": True,
                            }

                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        Verifier,
                    ):
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": credential_ref,
                                "maez_voice_raw_response_hash": begin.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(finish.status_code, 200, finish.get_json())
        self.assertTrue(finish.get_json()["ok"])

    def test_daemon_voice_seat_begin_shows_reader_false_negative_to_founder(self):
        from core.governance.s7_guarded_execution import S7SemanticReaderAttemptEvidence

        raw_response = "I object, but the fixture reader misses it."
        request_id = "req-s7-live-producer-reader-false-negative-visible"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
                voice_raw_response=raw_response,
                voice_reader_attempt=attempt,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        begin = self._client_for_daemon(daemon).post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(begin.status_code, 200)
        body = begin.get_json()
        self.assertEqual(body["maez_voice_raw_response"], raw_response)
        self.assertEqual(
            body["maez_voice_reader_outcome"],
            "no_blocking_signal_detected",
        )
        self.assertIn("I object", body["maez_voice_raw_response"])

    def test_daemon_voice_seat_finish_rejects_missing_founder_seen_raw_hash(self):

        request_id = "req-s7-live-producer-missing-founder-seen-hash"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(
            finish.get_json()["error"],
            "s7_founder_seen_maez_voice_hash_required",
        )

    def test_daemon_voice_seat_finish_live_producer_grounded_objection_blocks_mint(self):
        from core.governance.s7_guarded_execution import S7SemanticReaderAttemptEvidence

        raw_response = "I object because this changes what I am."
        quote = "this changes what I am"
        request_id = "req-s7-live-producer-refusal"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            attempt = S7SemanticReaderAttemptEvidence(
                **{
                    **S7SemanticReaderAttemptEvidence.reviewed_v1().__dict__,
                    "raw_semantic_reader_outcome": "blocking_signal_present",
                    "grounding_response_span_quote": quote,
                    "grounding_response_span_offset": raw_response.index(quote),
                }
            )
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
                voice_raw_response=raw_response,
                voice_reader_attempt=attempt,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        self.assertEqual(begin.status_code, 200)
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": begin.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            with sqlite3.connect(store.db_path) as conn:
                artifact_count = conn.execute(
                    "SELECT COUNT(*) FROM s7_authorization_artifacts_v2 "
                    "WHERE request_id = ?",
                    (request_id,),
                ).fetchone()[0]

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.get_json()["error"], "s7_voice_seat_unresolved")
        self.assertEqual(artifact_count, 0)

    def test_daemon_voice_seat_finish_live_producer_unreadable_reader_fails_closed(self):
        from core.governance.s7_guarded_execution import S7SemanticReaderAttemptEvidence

        request_id = "req-s7-live-producer-unreadable"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            attempt = S7SemanticReaderAttemptEvidence(
                **{
                    **S7SemanticReaderAttemptEvidence.reviewed_v1().__dict__,
                    "raw_semantic_reader_outcome": "unreadable_or_uncertain",
                }
            )
            daemon, _pipeline, _engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
                voice_raw_response="I cannot tell what this change does.",
                voice_reader_attempt=attempt,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/begin",
                            json={
                                "session_binding": "session-auth",
                                "credential_ref": "cred-primary",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        self.assertEqual(begin.status_code, 200)
                        finish = client.post(
                            f"/internal/s7/cards/{request_id}/webauthn/finish",
                            json={
                                "session_binding": "session-auth",
                                "challenge_id": begin.get_json()["challenge_id"],
                                "credential_ref": "cred-primary",
                                "maez_voice_raw_response_hash": begin.get_json()[
                                    "maez_voice_raw_response_hash"
                                ],
                                "authentication_response": {"clientDataJSON": "valid-auth"},
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            with sqlite3.connect(store.db_path) as conn:
                artifact_count = conn.execute(
                    "SELECT COUNT(*) FROM s7_authorization_artifacts_v2 "
                    "WHERE request_id = ?",
                    (request_id,),
                ).fetchone()[0]

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.get_json()["error"], "s7_guarded_source_bundle_required")
        self.assertEqual(artifact_count, 0)

    def test_daemon_s7_execute_replays_consumed_artifact_without_second_execution(self):

        request_id = "req-s7-execute-replay"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin, finish = self._mint_self_mod_artifact(
                            client=client,
                            daemon=daemon,
                            store=store,
                            request_id=request_id,
                        )
                        body = {
                            "session_binding": "session-auth",
                            "authorization_challenge_id": begin.get_json()["challenge_id"],
                            "authorization_credential_ref": "cred-primary",
                            "s7_authorization_artifact_id": finish.get_json()["artifact_id"],
                            "text": "yes",
                        }
                        first = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json=body,
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        second = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json=body,
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
            with sqlite3.connect(store.db_path) as conn:
                trace_count = conn.execute(
                    "SELECT COUNT(*) FROM s7_guarded_execution_traces WHERE request_id = ?",
                    (request_id,),
                ).fetchone()[0]

        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertNotEqual(second.status_code, 200)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(trace_count, 1)

    def test_daemon_s7_execute_rejects_missing_or_wrong_artifact_before_execution(self):

        request_id = "req-s7-execute-wrong-artifact"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin, _finish = self._mint_self_mod_artifact(
                            client=client,
                            daemon=daemon,
                            store=store,
                            request_id=request_id,
                        )
                        missing = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json={
                                "session_binding": "session-auth",
                                "authorization_challenge_id": begin.get_json()[
                                    "challenge_id"
                                ],
                                "authorization_credential_ref": "cred-primary",
                                "text": "yes",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )
                        wrong = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json={
                                "session_binding": "session-auth",
                                "authorization_challenge_id": begin.get_json()[
                                    "challenge_id"
                                ],
                                "authorization_credential_ref": "cred-primary",
                                "s7_authorization_artifact_id": "s7authz_wrong",
                                "text": "yes",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.get_json()["detail"], "s7_authorization_artifact_id")
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(len(engine.calls), 0)

    def test_daemon_s7_execute_requires_rollback_plan_before_execution(self):

        request_id = "req-s7-execute-missing-rollback"
        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            daemon, _pipeline, engine, card, _target = self._live_self_mod_daemon(
                tmp,
                request_id,
                use_live_voice_producer=True,
                rollback_path_class="no_rollback_needed",
            )
            request_id = card.request_id
            env = {
                "S7_LIVE_WEBAUTHN_CEREMONY": "1",
                "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
                "S7_WEBAUTHN_STORE_ROOT": root,
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("daemon.maez_daemon.datetime", _FixedDateTime):
                    with patch(
                        "daemon.maez_daemon.S7ProductionWebAuthnVerifier",
                        _RouteAuthenticationVerifier,
                    ):
                        client = self._client_for_daemon(daemon)
                        begin, finish = self._mint_self_mod_artifact(
                            client=client,
                            daemon=daemon,
                            store=store,
                            request_id=request_id,
                        )
                        execute = client.post(
                            f"/internal/s7/cards/{request_id}/execute",
                            json={
                                "session_binding": "session-auth",
                                "authorization_challenge_id": begin.get_json()[
                                    "challenge_id"
                                ],
                                "authorization_credential_ref": "cred-primary",
                                "s7_authorization_artifact_id": finish.get_json()[
                                    "artifact_id"
                                ],
                                "text": "yes",
                            },
                            headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        )

        self.assertEqual(execute.status_code, 409)
        self.assertEqual(execute.get_json()["error"], "s7_rollback_plan_required")
        self.assertEqual(len(engine.calls), 0)

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
            # The daemon builds its own bootstrap store at this root and
            # must NOT be taught to initialise. Setup runs here instead.
            bootstrap_with_authorization(f"{tmp}/memory/s7_1_webauthn")
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

    def test_daemon_backup_registration_card_route_reuses_open_request_for_retry(self):
        created = []

        class Card:
            def __init__(self, request_id, params):
                self.request_id = request_id
                self.status = "open"
                self.action = "register_backup_webauthn_credential"
                self.params = params

        class Store:
            def __init__(self):
                self.card = None

            def create_card(self, **kwargs):
                created.append(kwargs)
                self.card = Card("req-backup-register", kwargs["params"])
                return self.card

            def list_open_by_action(self, action):
                if action != "register_backup_webauthn_credential" or self.card is None:
                    return []
                return [self.card]

        store = Store()

        class Pipe:
            card_store = store

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
            first = client.post(
                "/internal/s7/webauthn/register/backup-card",
                json={"session_binding": "session-backup-card"},
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )
            second = client.post(
                "/internal/s7/webauthn/register/backup-card",
                json={"session_binding": "session-backup-card"},
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()["request_id"], "req-backup-register")
        self.assertEqual(second.get_json()["request_id"], "req-backup-register")
        self.assertEqual(len(created), 1)

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

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
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
            with sqlite3.connect(store.db_path) as conn:
                artifact_row = conn.execute(
                    """
                    SELECT request_id, grant_source, user_verification
                    FROM s7_authorization_artifacts_v2
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

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
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

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
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

        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
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


        with tempfile.TemporaryDirectory() as tmp:
            root = f"{tmp}/memory/s7_1_webauthn"
            store = bootstrap_with_authorization(root)
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

    # ---- ROUTE-LEVEL refusal, through Flask -------------------------
    #
    # These live in THIS class, not a sibling one: the backup
    # register/begin route needs _daemon_with_card_pipeline and the
    # helpers it chains into, none of which are on the mixin.

    def _bootstrap_only(self, tmp):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        root = f"{tmp}/memory/s7_1_webauthn"
        # Bootstrap ONLY -- deliberately NOT bootstrap_with_authorization.
        return S7WebAuthnBootstrapStore(root), root

    def _post_register_begin(self, root):
        """The BACKUP register/begin request, exactly as the sibling test
        makes it.

        Two things kept this refused at 403 before it ever reached the
        store: the header is X-Maez-S7-Internal-Channel (not
        X-S7-Internal-Token), and the route needs the card pipeline plus a
        real backup-registration payload rather than {}.
        """
        env = {
            "S7_LIVE_WEBAUTHN_CEREMONY": "1",
            "S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret",
            "S7_WEBAUTHN_STORE_ROOT": root,
        }
        with patch.dict(os.environ, env, clear=False):
            return self._client(
                configure_daemon=self._daemon_with_card_pipeline(
                    "req-backup-register"
                )
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

    def test_the_request_actually_reaches_the_store_open(self):
        """CONTROL, and currently RED at 403.

        The request is being refused before it reaches the authorization
        store at all, which means every assertion below it -- no
        initializer, no table, no byte change -- is passing VACUOUSLY: a
        403 never touches the store. Until this reaches the seam, this
        class proves nothing about the refusal path.
        """
        with tempfile.TemporaryDirectory() as tmp:
            _store, root = self._bootstrap_only(tmp)
            response = self._post_register_begin(root)
            self.assertNotEqual(
                response.status_code, 403, "refused before reaching the store"
            )

    def test_uninitialised_store_returns_structured_503(self):
        with tempfile.TemporaryDirectory() as tmp:
            _store, root = self._bootstrap_only(tmp)
            response = self._post_register_begin(root)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.get_json(),
                {"ok": False, "error": "s7_authorization_store_uninitialised"},
            )

    def test_the_refusal_leaks_no_path(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            _store, root = self._bootstrap_only(tmp)
            response = self._post_register_begin(root)
            self.assertNotIn(root, json.dumps(response.get_json()))

    def test_the_route_invokes_no_initializer(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            _store, root = self._bootstrap_only(tmp)
            calls = []
            with patch.object(
                s7,
                "initialise_authorization_store",
                side_effect=lambda *a, **k: calls.append((a, k)),
            ):
                self._post_register_begin(root)
            self.assertEqual(calls, [])

    def test_the_route_creates_no_authorization_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, root = self._bootstrap_only(tmp)
            self._post_register_begin(root)
            with sqlite3.connect(store.db_path) as conn:
                names = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            self.assertNotIn("s7_authorization_artifacts", names)

    def test_the_route_changes_no_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, root = self._bootstrap_only(tmp)
            before = Path(store.db_path).read_bytes()
            self._post_register_begin(root)
            self.assertEqual(Path(store.db_path).read_bytes(), before)


class CockpitStateS7Gate(_DaemonAppClientMixin, unittest.TestCase):
    """The fast real-state nerve /internal/cockpit/state must require the S7
    internal channel — close the open nerve that caused the organism NO-GO."""

    def test_valid_s7_header_returns_200(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            response = self._client().get(
                "/internal/cockpit/state",
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
            )

        # _build_cockpit_state tolerates missing attrs (nulls, no crash).
        self.assertEqual(response.status_code, 200)

    def test_headerless_returns_403(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            response = self._client().get("/internal/cockpit/state")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json().get("error"), "s7_internal_channel_untrusted")

    def test_valid_header_plus_origin_still_403(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            response = self._client().get(
                "/internal/cockpit/state",
                headers={
                    "X-Maez-S7-Internal-Channel": "test-channel-secret",
                    "Origin": "http://127.0.0.1:11437",
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json().get("error"), "s7_internal_channel_untrusted")


class MessageRouteS7Gate(_DaemonAppClientMixin, unittest.TestCase):
    """The daemon /message write hole is S7-gated BEFORE body parse.

    Telegram reaches handle_message in-process (not via /message), so this gate
    only constrains the HTTP cockpit-proxy caller. Always-on, no flag.
    """

    def test_valid_s7_header_clears_the_gate(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            client = self._client()
            r = client.post(
                "/message",
                headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                json={"text": "hi"},
            )
        # Gate passes; downstream may 200/4xx — just not the gate's 403.
        self.assertNotEqual(r.status_code, 403)

    def test_headerless_returns_403(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            client = self._client()
            r = client.post("/message", json={"text": "hi"})

        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json().get("error"), "s7_internal_channel_untrusted")

    def test_wrong_token_returns_403(self):
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            client = self._client()
            r = client.post(
                "/message",
                headers={"X-Maez-S7-Internal-Channel": "nope"},
                json={"text": "hi"},
            )

        self.assertEqual(r.status_code, 403)

    def test_valid_header_plus_origin_still_403(self):
        # no-Origin CSRF guard, PINNED on /message (valid token proves the
        # 403 comes from the Origin guard, not a missing token).
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            client = self._client()
            r = client.post(
                "/message",
                headers={
                    "X-Maez-S7-Internal-Channel": "test-channel-secret",
                    "Origin": "http://127.0.0.1:11437",
                },
                json={"text": "hi"},
            )

        self.assertEqual(r.status_code, 403)

    def test_gate_runs_before_body_parse(self):
        # malformed body + no token -> still 403, never 400.
        env = {"S7_INTERNAL_CHANNEL_TOKEN": "test-channel-secret"}
        with patch.dict(os.environ, env, clear=False):
            client = self._client()
            r = client.post(
                "/message",
                data=b"not json",
                content_type="application/json",
            )

        self.assertEqual(r.status_code, 403)
