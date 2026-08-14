"""S7.1 guarded dream-state execution tests."""

from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from tests.s7_store_fixture import fresh_v2_store_at

NOW = "2026-05-18T12:00:00+00:00"
FUTURE = "2026-05-18T12:05:00+00:00"


class _RecordingActionEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []
        self.section_calls: list[tuple[str, str, str, object | None]] = []

    def write_soul_note(self, note: str, *, s7_execution_grant: object | None = None):
        self.calls.append((note, s7_execution_grant))
        return "written"

    def edit_soul_section(
        self,
        *,
        target_name: str,
        new_body: str,
        rationale: str = "",
        s7_execution_grant: object | None = None,
    ):
        self.section_calls.append((target_name, new_body, rationale, s7_execution_grant))
        return SimpleNamespace(success=True, output="edited", error="")


class _RefusingActionEngine(_RecordingActionEngine):
    def write_soul_note(self, note: str, *, s7_execution_grant: object | None = None):
        self.calls.append((note, s7_execution_grant))
        return SimpleNamespace(
            success=False,
            output="",
            error="S7 authorization required before direct write_soul_note invocation",
        )


class _LiveAuthorizationVerifier:
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


class S71DreamExecutionTests(unittest.TestCase):
    def _authority_context(self):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user",),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-primary",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
            verification_reason="s7_1_test",
        )

    def _voice_consultation(self, envelope):
        from core.governance import operator_user_boundary as s7

        return s7.MaezVoiceConsultation(
            consultation_id=envelope.maez_voice_consultation_id or "",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="s7_voice_consultation_turn",
            source_ref_kind="s7_voice_turn",
            source_ref_hash="b" * 64,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

    def _authorization_for_dream(self, dream, prop_id: int, db_path: Path):
        from core.governance import operator_user_boundary as s7

        envelope = dream.build_apply_s7_envelope(
            prop_id,
        )
        params = dream.s7_apply_action_params(prop_id)
        authority = self._authority_context()
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash(params),
            authority_context=authority,
            maez_voice_consultation=self._voice_consultation(envelope),
            nonce="nonce-dream-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        store, artifact_id = self._mint_authorization_through_service(
            db_path=db_path,
            envelope=envelope,
            rendered=rendered,
            authority=authority,
        )
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact_id,
            rendered=rendered,
            action_params_hash=rendered.action_params_hash,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            now=NOW,
        )

    def _authorization_for_section_edit(self, dream, prop_id: int, db_path: Path):
        from core.governance import operator_user_boundary as s7

        envelope = dream.build_section_edit_s7_envelope(prop_id)
        params = dream.s7_section_edit_action_params(prop_id)
        authority = self._authority_context()
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash(params),
            authority_context=authority,
            maez_voice_consultation=self._voice_consultation(envelope),
            nonce="nonce-edit-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        store, artifact_id = self._mint_authorization_through_service(
            db_path=db_path,
            envelope=envelope,
            rendered=rendered,
            authority=authority,
        )
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact_id,
            rendered=rendered,
            action_params_hash=rendered.action_params_hash,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            now=NOW,
        )

    def _mint_authorization_through_service(self, *, db_path: Path, envelope, rendered, authority):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        store = S7WebAuthnBootstrapStore(db_path.parent / f"{db_path.stem}_store")
        store.store_credential(self._credential_record("cred-primary", kind="primary"))
        store.store_credential(self._credential_record("cred-backup", kind="backup"))
        service = S7LocalWebAuthnCeremonyService(
            verifier=_LiveAuthorizationVerifier(),
            store_factory=lambda: store,
        )
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            S7VoiceSourceBundleHashBinding,
            put_voice_source_bundle_v2,
            read_voice_source_bundle,
            s7_voice_consultation_bundle_hash,
            validate_voice_source_bundle,
        )

        auth_store = fresh_v2_store_at(store.db_path)
        bundle_store = S7VoiceConsultationBundleStore(store.db_path)
        bundle_use_store = S7VoiceBundleUseStore(store.db_path)
        attempt_store = S7SemanticReaderAttemptStore(store.db_path)
        consultation = self._voice_consultation(envelope)
        attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
        attempt_store.put(attempt)
        raw_text = "Maez says there is no objection."
        rendered_prompt_text = f"S7 voice consultation prompt for {envelope.request_id}"
        rendered_prompt_hash = s7.canonical_hash(rendered_prompt_text)
        manifest = bundle_store.put_reviewed_context_manifest(
            manifest_id=f"context-{envelope.request_id}",
            preview_ref=f"preview-{envelope.request_id}",
            request_envelope_hash=rendered.request_envelope_hash,
            precondition_hash=envelope.precondition_hash,
            created_at=NOW,
        )
        binding = S7VoiceSourceBundleHashBinding(
            request_id=envelope.request_id,
            consultation_id=consultation.consultation_id,
            source_ref_hash=consultation.source_ref_hash,
            request_envelope_hash=rendered.request_envelope_hash,
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=rendered.action_params_hash,
            precondition_hash=envelope.precondition_hash,
            authority_context_hash=rendered.authority_context_hash,
            maez_voice_consultation_hash=rendered.maez_voice_consultation_hash or "6" * 64,
            rendered_prompt_hash=rendered_prompt_hash,
            mutation_preview_hash="8" * 64,
            rollback_plan_ref="9" * 64,
            context_manifest_hash=manifest.context_manifest_hash,
            runtime_identity_hash="b" * 64,
            model_routing_identity_hash="d" * 64,
            model_config_hash="e" * 64,
        )
        bundle_store.put_raw_response(f"raw-response-{rendered.request_id}", raw_text)
        bundle_store.put_rendered_prompt(
            f"rendered-prompt-{rendered.request_id}",
            rendered_prompt_text,
        )
        bundle = S7VoiceConsultationBundle(
            source_ref_hash=consultation.source_ref_hash,
            request_id=envelope.request_id,
            consultation_id=consultation.consultation_id,
            request_envelope_hash=binding.request_envelope_hash,
            rendered_text_hash=binding.rendered_text_hash,
            action_params_hash=binding.action_params_hash,
            precondition_hash=binding.precondition_hash,
            authority_context_hash=binding.authority_context_hash,
            maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
            rendered_prompt_ref=f"rendered-prompt-{rendered.request_id}",
            rendered_prompt_hash=binding.rendered_prompt_hash,
            mutation_preview_hash=binding.mutation_preview_hash,
            rollback_plan_ref=binding.rollback_plan_ref,
            context_manifest_ref=manifest.manifest_id,
            context_manifest_hash=binding.context_manifest_hash,
            runtime_identity_hash=binding.runtime_identity_hash,
            model_routing_identity_hash=binding.model_routing_identity_hash,
            model_config_hash=binding.model_config_hash,
            raw_response_ref=f"raw-response-{rendered.request_id}",
            raw_response_hash=s7.canonical_hash(raw_text),
            semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
            expires_at=FUTURE,
            action=rendered.action,
        )
        bundle = replace(
            bundle,
            source_bundle_hash=s7_voice_consultation_bundle_hash(bundle),
        )
        with auth_store.anchored_transaction() as conn:
            put_voice_source_bundle_v2(bundle=bundle, conn=conn)
            persisted_bundle, version = read_voice_source_bundle(
                source_ref_hash=consultation.source_ref_hash,
                conn=conn,
            )
            validation = validate_voice_source_bundle(
                bundle=persisted_bundle,
                version=version,
                purpose="execution",
            )
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=envelope.request_id,
                source_ref_hash=consultation.source_ref_hash,
                consultation_id=consultation.consultation_id,
                used_at=NOW,
            )
        )
        guarded_store = S7GuardedStateStore(
            authorization_store=auth_store,
            voice_bundle_use_store=bundle_use_store,
        )
        begin = service.authorize_begin(
            now=NOW,
            rendered_statement=rendered,
            precondition_hash=envelope.precondition_hash,
            session_binding=f"session-{rendered.request_id}",
            internal_channel_binding="internal-dream",
        )
        finish = service.authorize_finish(
            now=NOW,
            envelope=envelope,
            rendered_statement=rendered,
            precondition_hash=envelope.precondition_hash,
            maez_voice_consultation=consultation,
            session_binding=f"session-{rendered.request_id}",
            internal_channel_binding="internal-dream",
            request_json={
                "challenge_id": begin.body["challenge_id"],
                "credential_ref": "cred-primary",
                "authentication_response": {"clientDataJSON": "valid-auth"},
            },
            guarded_store=guarded_store,
            source_bundle_binding=binding,
            source_bundle_validation=validation,
            source_ref_hash=consultation.source_ref_hash,
            reservation_token=f"reservation-token-{rendered.request_id}",
        )
        self.assertEqual(begin.status_code, 200)
        self.assertEqual(finish.status_code, 200)
        return auth_store, finish.body["artifact_id"]

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
            created_at=NOW,
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

    def test_apply_dream_without_s7_execution_authorization_fails_closed(self):
        from core.evolution.dream_state import DreamState

        with tempfile.TemporaryDirectory() as tmp:
            action_engine = _RecordingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(Path(tmp) / "dream_proposals.db"),
            )
            prop_id = dream._store_proposal("Maez noticed a durable pattern.")

            ok, message = dream.apply_proposal(prop_id)
            prop = dream.get_proposal(prop_id)

        self.assertFalse(ok)
        self.assertIn("S7 execution authorization", message)
        self.assertEqual(action_engine.calls, [])
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "pending")

    def test_apply_dream_consumes_matching_s7_artifact_before_soul_write(self):
        from core.evolution.dream_state import DreamState

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            action_engine = _RecordingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(tmp_path / "dream_proposals.db"),
            )
            prop_id = dream._store_proposal("Maez noticed a durable pattern.")
            authorization = self._authorization_for_dream(
                dream,
                prop_id,
                tmp_path / "s7_authorization.db",
            )

            ok, message = dream.apply_proposal(
                prop_id,
                s7_execution_authorization=authorization,
            )
            prop = dream.get_proposal(prop_id)
            with sqlite3.connect(authorization.store.db_path) as conn:
                consumed_at = conn.execute(
                    "SELECT consumed_at FROM s7_authorization_artifacts_v2 WHERE artifact_id = ?",
                    (authorization.artifact_id,),
                ).fetchone()[0]

        self.assertTrue(ok, message)
        self.assertEqual(len(action_engine.calls), 1)
        self.assertIsNotNone(action_engine.calls[0][1])
        self.assertIsNotNone(consumed_at)
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "applied")

    def test_apply_dream_does_not_mark_applied_when_action_result_failed(self):
        from core.evolution.dream_state import DreamState

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            action_engine = _RefusingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(tmp_path / "dream_proposals.db"),
            )
            prop_id = dream._store_proposal("Maez noticed a durable pattern.")
            authorization = self._authorization_for_dream(
                dream,
                prop_id,
                tmp_path / "s7_authorization.db",
            )

            ok, message = dream.apply_proposal(
                prop_id,
                s7_execution_authorization=authorization,
            )
            prop = dream.get_proposal(prop_id)

        self.assertFalse(ok)
        self.assertIn("soul write rejected", message)
        self.assertEqual(len(action_engine.calls), 1)
        self.assertIsNotNone(action_engine.calls[0][1])
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "pending")
        self.assertIsNone(prop["applied_at"])

    def test_apply_dream_accepts_artifact_minted_by_s7_1_authorize_finish(self):
        from core.evolution.dream_state import DreamState
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            action_engine = _RecordingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(tmp_path / "dream_proposals.db"),
            )
            prop_id = dream._store_proposal("Maez noticed a durable pattern.")
            envelope = dream.build_apply_s7_envelope(prop_id)
            params = dream.s7_apply_action_params(prop_id)
            authority = self._authority_context()
            rendered = s7.render_request_statement(
                envelope=envelope,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=s7.canonical_hash(params),
                authority_context=authority,
                maez_voice_consultation=self._voice_consultation(envelope),
                nonce="nonce-dream-live",
                expires_at=FUTURE,
                rendered_at=NOW,
            )
            store, artifact_id = self._mint_authorization_through_service(
                db_path=tmp_path / "s7_authorization_live.db",
                envelope=envelope,
                rendered=rendered,
                authority=authority,
            )
            authorization = s7.S7ExecutionAuthorization(
                store=store,
                artifact_id=artifact_id,
                rendered=rendered,
                action_params_hash=rendered.action_params_hash,
                authority_context=authority,
                precondition_hash=envelope.precondition_hash,
                derived_work_class=rendered.derived_work_class,
                derived_aggregation_group=rendered.derived_aggregation_group,
                now=NOW,
            )

            ok, message = dream.apply_proposal(
                prop_id,
                s7_execution_authorization=authorization,
            )

        self.assertTrue(ok, message)
        self.assertEqual(len(action_engine.calls), 1)
        self.assertIsNotNone(action_engine.calls[0][1])

    def test_apply_section_edit_without_s7_execution_authorization_fails_closed(self):
        from core.evolution.dream_state import DreamState

        with tempfile.TemporaryDirectory() as tmp:
            action_engine = _RecordingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(Path(tmp) / "dream_proposals.db"),
            )
            prop_id = dream.store_section_edit_proposal(
                insight="tighten the covenant wording",
                target_section="Trust Covenant",
                proposed_new_body="new covenant body",
                unified_diff="--- old\n+++ new",
            )

            ok, message = dream.apply_section_edit_proposal(prop_id)
            prop = dream.get_proposal(prop_id)

        self.assertFalse(ok)
        self.assertIn("S7 execution authorization", message)
        self.assertEqual(action_engine.section_calls, [])
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "pending")

    def test_apply_section_edit_consumes_matching_s7_artifact_before_write(self):
        from core.evolution.dream_state import DreamState

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            action_engine = _RecordingActionEngine()
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=action_engine,
                db_path=str(tmp_path / "dream_proposals.db"),
            )
            prop_id = dream.store_section_edit_proposal(
                insight="tighten the covenant wording",
                target_section="Trust Covenant",
                proposed_new_body="new covenant body",
                unified_diff="--- old\n+++ new",
            )
            authorization = self._authorization_for_section_edit(
                dream,
                prop_id,
                tmp_path / "s7_edit_authorization.db",
            )

            ok, message = dream.apply_section_edit_proposal(
                prop_id,
                s7_execution_authorization=authorization,
            )
            prop = dream.get_proposal(prop_id)
            with sqlite3.connect(authorization.store.db_path) as conn:
                consumed_at = conn.execute(
                    "SELECT consumed_at FROM s7_authorization_artifacts_v2 WHERE artifact_id = ?",
                    (authorization.artifact_id,),
                ).fetchone()[0]

        self.assertTrue(ok, message)
        self.assertEqual(len(action_engine.section_calls), 1)
        self.assertIsNotNone(action_engine.section_calls[0][3])
        self.assertIsNotNone(consumed_at)
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "applied")


if __name__ == "__main__":
    unittest.main()
