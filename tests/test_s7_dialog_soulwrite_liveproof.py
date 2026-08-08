from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.audit import AuditVerdict, Decision
from core.audit_log import AuditLog
from core.decision.decision_pipeline import DecisionPipeline
from core.decision.pending_cards import PendingCardStore
from tests.s7_store_fixture import fresh_store_at


NOW = "2026-06-12T17:00:00+00:00"
FUTURE = "2026-06-12T18:00:00+00:00"


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


class DialogSoulWriteLiveProof(unittest.TestCase):
    """GO/NO-GO: the real self-mod dialog ratify path must write the sandbox soul.

    This intentionally drives DecisionPipeline._handle_dialog_reply_for_card through
    a real ActionEngine and a real S7 execution authorization. The only fake is the
    filesystem: every known soul path resolver is redirected to a temporary soul
    layout, and the real soul files are hash-guarded in tearDown.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = self.root / "config"
        self.config.mkdir(parents=True, exist_ok=True)
        self.sandbox_base = self.config / "soul.base.md"
        self.sandbox_local = self.config / "soul.local.md"
        self.sandbox_soul = self.config / "soul.md"
        self.sandbox_base.write_text(
            "\n".join(
                (
                    "# sandbox soul",
                    "",
                    "HARD CONSTRAINTS",
                    "TRUST COVENANT",
                    "SYSTEM BASELINE",
                    "",
                    "## Values",
                    "Old value body.",
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.sandbox_local.write_text("", encoding="utf-8")
        self.sandbox_soul.write_text(self.sandbox_base.read_text(encoding="utf-8"), encoding="utf-8")

        from core.infra import paths

        self._guarded = {}
        for p in (paths.soul_combined_path(), paths.soul_base_path(), paths.soul_local_path()):
            path = Path(p)
            if path.exists():
                self._guarded[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()

        from core.actions import action_engine as ae
        from core.evolution import soul_editor, soul_loader

        self._patches = [
            patch.object(paths, "config_dir", return_value=self.config),
            patch.object(paths, "soul_base_path", return_value=self.sandbox_base),
            patch.object(paths, "soul_local_path", return_value=self.sandbox_local),
            patch.object(paths, "soul_combined_path", return_value=self.sandbox_soul),
            patch.object(ae, "SOUL_PATH", self.sandbox_soul),
            patch.object(soul_editor, "SOUL_PATH", self.sandbox_soul),
            patch.object(soul_editor, "BACKUP_DIR", self.config),
        ]
        for p in self._patches:
            p.start()
        soul_loader.reload()

        self.card_store = PendingCardStore(self.root / "cards.db")
        self.audit_log = AuditLog(self.root / "audit.db")
        self.dialog_db = self.root / "dialogs.db"

        from core.actions.action_engine import ActionEngine
        from skills.self_mod_dialog import SelfModDialogStore

        self.pipeline = DecisionPipeline(
            action_engine=ActionEngine(),
            card_store=self.card_store,
            audit_log=self.audit_log,
        )
        self.dialog_store = SelfModDialogStore(self.dialog_db)
        self.pipeline._dialog_store = self.dialog_store

    def tearDown(self):
        from core.evolution import soul_loader

        soul_loader.reload()
        for p in reversed(getattr(self, "_patches", [])):
            p.stop()
        for path, before in self._guarded.items():
            self.assertEqual(
                hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                before,
                f"REAL soul file {path} was modified by a hermetic test path leak",
            )
        self.tmp.cleanup()

    def _verdict(self) -> AuditVerdict:
        return AuditVerdict(
            decision=Decision.ESCALATE,
            confidence=0.99,
            reasoning="self-modification requires S7",
            concerns=["modifies soul"],
            mitigations=[],
            summary="self modification",
            answers={},
            nonce="s7-liveproof",
            latency_ms=1,
        )

    def _card(self, *, action: str, params: dict):
        return self.card_store.create_card(
            action=action,
            params=params,
            reason="0a live proof",
            audit_verdict=self._verdict(),
            audit_request_id=f"audit-{action}",
            classification={"intent_category": "SELF_MODIFICATION", "lane": "3"},
            channel="telegram_text",
            chat_id=f"chat-{action}",
            user_id="rohit",
        )

    def _open_dialog(self, card, *, request_hash: str):
        from skills.self_mod_dialog import open_dialog_for_card

        dialog, _ = open_dialog_for_card(
            store=self.dialog_store,
            card_action=card.action,
            card_params=card.params,
            card_request_id=card.request_id,
            audit_reasoning=card.audit_reasoning,
            concerns=list(card.audit_concerns or []),
            opener_llm_fn=lambda _ctx: "I want to change my soul through the reviewed S7 path.",
            require_s7_linkage=True,
            s7_request_envelope_hash=request_hash,
        )
        return dialog

    def _authority_context(self):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-primary",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

    def _voice_consultation(self, envelope):
        from core.governance import operator_user_boundary as s7

        return s7.MaezVoiceConsultation(
            consultation_id=envelope.maez_voice_consultation_id or f"voice-{envelope.request_id}",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

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

    def _authorization_for_card(self, card):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        envelope = self.pipeline._s7_request_envelope_for_card(card)
        authority = self._authority_context()
        consultation = self._voice_consultation(envelope)
        params_hash = s7.canonical_hash(self.pipeline._execution_params_for_card(card))
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=f"nonce-{card.request_id}",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        bootstrap_store = S7WebAuthnBootstrapStore(self.root / f"s7_store_{card.request_id}")
        bootstrap_store.store_credential(self._credential_record("cred-primary", kind="primary"))
        bootstrap_store.store_credential(self._credential_record("cred-backup", kind="backup"))
        service = S7LocalWebAuthnCeremonyService(
            verifier=_LiveAuthorizationVerifier(),
            store_factory=lambda: bootstrap_store,
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
            validate_s7_voice_source_bundle,
        )

        auth_store = fresh_store_at(bootstrap_store.db_path)
        bundle_store = S7VoiceConsultationBundleStore(bootstrap_store.db_path)
        bundle_use_store = S7VoiceBundleUseStore(bootstrap_store.db_path)
        attempt_store = S7SemanticReaderAttemptStore(bootstrap_store.db_path)
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
        bundle_store.put_raw_response(f"raw-response-{envelope.request_id}", raw_text)
        bundle_store.put_rendered_prompt(f"rendered-prompt-{envelope.request_id}", rendered_prompt_text)
        bundle_store.put_bundle(
            S7VoiceConsultationBundle(
                source_ref_hash=consultation.source_ref_hash,
                request_id=envelope.request_id,
                consultation_id=consultation.consultation_id,
                request_envelope_hash=binding.request_envelope_hash,
                rendered_text_hash=binding.rendered_text_hash,
                action_params_hash=binding.action_params_hash,
                precondition_hash=binding.precondition_hash,
                authority_context_hash=binding.authority_context_hash,
                maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                rendered_prompt_ref=f"rendered-prompt-{envelope.request_id}",
                rendered_prompt_hash=binding.rendered_prompt_hash,
                mutation_preview_hash=binding.mutation_preview_hash,
                rollback_plan_ref=binding.rollback_plan_ref,
                context_manifest_ref=manifest.manifest_id,
                context_manifest_hash=binding.context_manifest_hash,
                runtime_identity_hash=binding.runtime_identity_hash,
                model_routing_identity_hash=binding.model_routing_identity_hash,
                model_config_hash=binding.model_config_hash,
                raw_response_ref=f"raw-response-{envelope.request_id}",
                raw_response_hash=s7.canonical_hash(raw_text),
                semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
                expires_at=FUTURE,
            )
        )
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=envelope.request_id,
                source_ref_hash=consultation.source_ref_hash,
                consultation_id=consultation.consultation_id,
                used_at=NOW,
            )
        )
        validation = validate_s7_voice_source_bundle(
            consultation=consultation,
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )
        begin = service.authorize_begin(
            now=NOW,
            rendered_statement=rendered,
            precondition_hash=envelope.precondition_hash,
            session_binding=f"session-{card.request_id}",
            internal_channel_binding="internal-liveproof",
        )
        finish = service.authorize_finish(
            now=NOW,
            envelope=envelope,
            rendered_statement=rendered,
            precondition_hash=envelope.precondition_hash,
            maez_voice_consultation=consultation,
            session_binding=f"session-{card.request_id}",
            internal_channel_binding="internal-liveproof",
            request_json={
                "challenge_id": begin.body["challenge_id"],
                "credential_ref": "cred-primary",
                "authentication_response": {"clientDataJSON": "valid-auth"},
            },
            guarded_store=S7GuardedStateStore(
                authorization_store=auth_store,
                voice_bundle_use_store=bundle_use_store,
            ),
            source_bundle_validation=validation,
            source_ref_hash=consultation.source_ref_hash,
            reservation_token=f"reservation-token-{card.request_id}",
        )
        self.assertEqual(begin.status_code, 200, begin.body)
        self.assertEqual(finish.status_code, 200, finish.body)
        return (
            envelope,
            s7.S7ExecutionAuthorization(
                store=auth_store,
                artifact_id=finish.body["artifact_id"],
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=envelope.precondition_hash,
                derived_work_class=envelope.derived_work_class,
                derived_aggregation_group=envelope.derived_aggregation_group,
                now=NOW,
            ),
        )

    def _drive_dialog_execution(self, *, action: str, params: dict):
        card = self._card(action=action, params=params)
        _envelope, authorization = self._authorization_for_card(card)
        dialog = self._open_dialog(
            card,
            request_hash=authorization.rendered.request_envelope_hash,
        )

        result = self.pipeline._handle_pending_dialog_input(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "executed", result)
        self.assertTrue(result.execution_success, result.execution_error)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "executed")
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNotNone(consumed_at)
        return result

    def test_write_soul_note_executes_end_to_end(self):
        before = self.sandbox_local.read_text(encoding="utf-8")

        result = self._drive_dialog_execution(
            action="write_soul_note",
            params={"note": "0a live proof: soul note path executed."},
        )

        after = self.sandbox_local.read_text(encoding="utf-8")
        self.assertNotEqual(after, before)
        self.assertIn("0a live proof: soul note path executed.", after)
        self.assertIn("soul note appended", result.execution_output)

    def test_edit_soul_section_executes_end_to_end(self):
        before = self.sandbox_soul.read_text(encoding="utf-8")

        result = self._drive_dialog_execution(
            action="edit_soul_section",
            params={
                "target_name": "Values",
                "new_body": "New value body from 0a live proof.\n",
                "rationale": "prove the live S7 dialog soul section path",
            },
        )

        after = self.sandbox_soul.read_text(encoding="utf-8")
        self.assertNotEqual(after, before)
        self.assertIn("New value body from 0a live proof.", after)
        self.assertIn("replaced", result.execution_output.lower())


if __name__ == "__main__":
    unittest.main()
