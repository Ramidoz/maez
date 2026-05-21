"""Decision 34 / ADR 0039 — S7 execution-edge pipeline gates."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.audit import AuditVerdict, Decision
from core.audit_log import AuditLog
from core.action_classifier import ClassificationResult, IntentCategory
from core import decision_pipeline as _dp
from core.decision_pipeline import DecisionPipeline
from core.decision.pending_cards import CardStatus, CardStoreError, PendingCardStore


NOW = "2026-05-17T16:00:00+00:00"
FUTURE = "2026-05-17T17:00:00+00:00"


class _CountingActionEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, str, int]] = []
        self.success = True
        self.output = "executed"
        self.error = ""

    def _execute_action(
        self,
        action: str,
        params: dict,
        reason: str,
        *,
        tier: int,
        s7_authorized: bool = False,
        s7_execution_grant: object = None,
    ):
        del s7_authorized, s7_execution_grant
        self.calls.append((action, dict(params or {}), reason, tier))
        return SimpleNamespace(success=self.success, output=self.output, error=self.error)


class _S7RouteVerifier:
    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}

    def verify_authentication_response(self, **_kwargs):
        return {
            "ok": True,
            "credential_ref": "cred-1",
            "sign_count": 1,
            "user_presence": True,
            "user_verification": True,
        }


class S7DecisionPipelineExecutionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.engine = _CountingActionEngine()
        self.card_store = PendingCardStore(self.root / "cards.db")
        self.audit_log = AuditLog(self.root / "audit.db")
        self.pipeline = DecisionPipeline(
            action_engine=self.engine,
            card_store=self.card_store,
            audit_log=self.audit_log,
        )
        from skills.self_mod_dialog import SelfModDialogStore

        self.dialog_store = SelfModDialogStore(self.root / "dialogs.db")
        self.pipeline._dialog_store = self.dialog_store

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _verdict(self) -> AuditVerdict:
        return AuditVerdict(
            decision=Decision.ESCALATE,
            confidence=0.9,
            reasoning="self-modification requires S7",
            concerns=["modifies soul"],
            mitigations=[],
            summary="self mod",
            answers={},
            nonce="nonce",
            latency_ms=1,
        )

    def _patched_escalate_surface(self):
        return (
            patch.object(
                _dp,
                "classify_action",
                return_value=ClassificationResult(
                    category=IntentCategory.SELF_MODIFICATION,
                    lane=3,
                    reason="test self-mod",
                ),
            ),
            patch.object(_dp, "audit_action", return_value=self._verdict()),
            patch("skills.self_mod_dialog.generate_opening_turn", return_value="S7 opening"),
        )

    def _card(
        self,
        *,
        params: dict | None = None,
        state_fields: dict | None = None,
        chat_id: str = "chat_1",
    ):
        return self.card_store.create_card(
            action="write_any_file",
            params=params or {"path": "config/soul.md", "content": "# edited"},
            reason="self-mod",
            audit_verdict=self._verdict(),
            audit_request_id="audit-s7-pipeline",
            classification={"intent_category": "SELF_MODIFICATION", "lane": "3"},
            state_fields=state_fields,
            channel="telegram_text",
            chat_id=chat_id,
            user_id="rohit",
        )

    def _regular_card(self, *, chat_id: str = "chat_2"):
        return self.card_store.create_card(
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            reason="routine restart",
            audit_verdict=AuditVerdict(
                decision=Decision.APPROVE_WITH_CARD,
                confidence=0.9,
                reasoning="routine card",
                concerns=[],
                mitigations=[],
                summary="routine",
                answers={},
                nonce="nonce-regular",
                latency_ms=1,
            ),
            audit_request_id="audit-regular",
            classification={"intent_category": "SYSTEM_MODIFICATION", "lane": "2"},
            channel="telegram_text",
            chat_id=chat_id,
            user_id="rohit",
        )

    def _guarded_lane2_card(self, *, chat_id: str = "chat_guarded"):
        return self.card_store.create_card(
            action="capability.acquire",
            params={"capability_id": "s7-sensitive-capability"},
            reason="install a new capability",
            audit_verdict=AuditVerdict(
                decision=Decision.APPROVE_WITH_CARD,
                confidence=0.9,
                reasoning="guarded capability acquisition",
                concerns=["capability acquisition"],
                mitigations=[],
                summary="capability",
                answers={},
                nonce="nonce-guarded",
                latency_ms=1,
            ),
            audit_request_id="audit-guarded",
            classification={"intent_category": "SYSTEM_MODIFICATION", "lane": "2"},
            channel="telegram_text",
            chat_id=chat_id,
            user_id="rohit",
        )

    def test_s7_card_envelope_is_stable_for_stored_card_across_call_time(self):
        from core.governance import operator_user_boundary as s7

        card = self._card()

        with (
            patch.object(_dp, "_s7_now_text", return_value="2026-05-17T16:00:00+00:00"),
            patch.object(_dp, "_s7_one_hour_from_now_text", return_value="2026-05-17T17:00:00+00:00"),
        ):
            first = self.pipeline._s7_request_envelope_for_card(card)
        with (
            patch.object(_dp, "_s7_now_text", return_value="2026-05-17T16:30:00+00:00"),
            patch.object(_dp, "_s7_one_hour_from_now_text", return_value="2026-05-17T17:30:00+00:00"),
        ):
            second = self.pipeline._s7_request_envelope_for_card(card)

        self.assertEqual(s7.work_request_envelope_hash(first), s7.work_request_envelope_hash(second))
        self.assertEqual(first.created_at, second.created_at)
        self.assertEqual(first.expires_at, second.expires_at)

    def test_s7_voice_consultation_for_card_is_produced_by_pipeline(self):
        from core.governance import operator_user_boundary as s7

        card = self._card()
        envelope = self.pipeline._s7_request_envelope_for_card(card)

        consultation = self.pipeline._s7_voice_consultation_for_card(card, envelope)

        self.assertIsInstance(consultation, s7.MaezVoiceConsultation)
        self.assertEqual(consultation.request_id, card.request_id)
        self.assertEqual(consultation.consultation_id, envelope.maez_voice_consultation_id)
        self.assertEqual(
            consultation.request_envelope_hash,
            s7.work_request_envelope_hash(envelope),
        )
        self.assertFalse(consultation.maez_voice_consulted)
        self.assertEqual(consultation.maez_objection_state, "not_determined")
        self.assertEqual(consultation.unavailable_reason_code, "consultation_path_unavailable")
        self.assertIsNone(consultation.raw_maez_text)

    def _open_dialog(self, card, *, require_s7_linkage: bool, request_hash: str | None = None):
        from skills.self_mod_dialog import open_dialog_for_card

        dialog, _opening = open_dialog_for_card(
            store=self.dialog_store,
            card_action=card.action,
            card_params=card.params,
            card_request_id=card.request_id,
            audit_reasoning=card.audit_reasoning,
            concerns=list(card.audit_concerns or []),
            opener_llm_fn=lambda _ctx: "I want to change config/soul.md.",
            require_s7_linkage=require_s7_linkage,
            s7_request_envelope_hash=request_hash,
        )
        return dialog

    def _authorization_bundle(self, card):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import (
            FounderWebAuthnCredentialRecord,
            S7WebAuthnBootstrapStore,
        )
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        env = s7.build_work_request_envelope(
            request_id=card.request_id,
            action=card.action,
            params=card.params,
            claimed_work_class="self_modification",
            requesting_subsystem="decision_pipeline",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id=f"voice-{card.request_id}",
            free_text_ref_hash="b" * 64,
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id=f"voice-{card.request_id}",
            request_id=card.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        authority = s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-1",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )
        params_hash = s7.canonical_hash(self.pipeline._execution_params_for_card(card))
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=f"nonce-{card.request_id}",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        bootstrap_store = S7WebAuthnBootstrapStore(self.root / f"s7_1_{card.request_id}")
        for credential_ref, kind, confidence in (
            ("cred-1", "primary", "unknown"),
            ("cred-2", "backup", "confirmed_distinct"),
        ):
            bootstrap_store.store_credential(
                FounderWebAuthnCredentialRecord.build(
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
                    distinct_device_confidence=confidence,
                )
            )
        service = S7LocalWebAuthnCeremonyService(
            verifier=_S7RouteVerifier(),
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

        auth_store = s7.S7AuthorizationStore(bootstrap_store.db_path)
        bundle_store = S7VoiceConsultationBundleStore(bootstrap_store.db_path)
        bundle_use_store = S7VoiceBundleUseStore(bootstrap_store.db_path)
        attempt_store = S7SemanticReaderAttemptStore(bootstrap_store.db_path)
        attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
        attempt_store.put(attempt)
        raw_text = "Maez says there is no objection."
        rendered_prompt_text = f"S7 voice consultation prompt for {env.request_id}"
        rendered_prompt_hash = s7.canonical_hash(rendered_prompt_text)
        manifest = bundle_store.put_reviewed_context_manifest(
            manifest_id=f"context-{card.request_id}",
            preview_ref=f"preview-{card.request_id}",
            request_envelope_hash=rendered.request_envelope_hash,
            precondition_hash=env.precondition_hash,
            created_at=NOW,
        )
        binding = S7VoiceSourceBundleHashBinding(
            request_id=env.request_id,
            consultation_id=consultation.consultation_id,
            source_ref_hash=consultation.source_ref_hash,
            request_envelope_hash=rendered.request_envelope_hash,
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=rendered.action_params_hash,
            precondition_hash=env.precondition_hash,
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
        bundle_store.put_raw_response(f"raw-response-{card.request_id}", raw_text)
        bundle_store.put_rendered_prompt(
            f"rendered-prompt-{card.request_id}",
            rendered_prompt_text,
        )
        bundle_store.put_bundle(
            S7VoiceConsultationBundle(
                source_ref_hash=consultation.source_ref_hash,
                request_id=env.request_id,
                consultation_id=consultation.consultation_id,
                request_envelope_hash=binding.request_envelope_hash,
                rendered_text_hash=binding.rendered_text_hash,
                action_params_hash=binding.action_params_hash,
                precondition_hash=binding.precondition_hash,
                authority_context_hash=binding.authority_context_hash,
                maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                rendered_prompt_ref=f"rendered-prompt-{card.request_id}",
                rendered_prompt_hash=binding.rendered_prompt_hash,
                mutation_preview_hash=binding.mutation_preview_hash,
                rollback_plan_ref=binding.rollback_plan_ref,
                context_manifest_ref=manifest.manifest_id,
                context_manifest_hash=binding.context_manifest_hash,
                runtime_identity_hash=binding.runtime_identity_hash,
                model_routing_identity_hash=binding.model_routing_identity_hash,
                model_config_hash=binding.model_config_hash,
                raw_response_ref=f"raw-response-{card.request_id}",
                raw_response_hash=s7.canonical_hash(raw_text),
                semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
            )
        )
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=env.request_id,
                source_ref_hash=consultation.source_ref_hash,
                consultation_id=consultation.consultation_id,
                used_at=NOW,
            )
        )
        guarded_store = S7GuardedStateStore(
            authorization_store=auth_store,
            voice_bundle_use_store=bundle_use_store,
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
            precondition_hash=env.precondition_hash,
            session_binding=f"session-{card.request_id}",
            internal_channel_binding="internal-test-channel",
        )
        finish = service.authorize_finish(
            now=NOW,
            envelope=env,
            rendered_statement=rendered,
            precondition_hash=env.precondition_hash,
            maez_voice_consultation=consultation,
            session_binding=f"session-{card.request_id}",
            internal_channel_binding="internal-test-channel",
            request_json={
                "challenge_id": begin.body["challenge_id"],
                "credential_ref": "cred-1",
                "authentication_response": {"clientDataJSON": "valid-auth"},
            },
            guarded_store=guarded_store,
            source_bundle_validation=validation,
            source_ref_hash=consultation.source_ref_hash,
            reservation_token=f"reservation-token-{card.request_id}",
        )
        self.assertEqual(begin.status_code, 200)
        self.assertEqual(finish.status_code, 200)
        return s7.S7ExecutionAuthorization(
            store=auth_store,
            artifact_id=finish.body["artifact_id"],
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )

    def test_ratified_self_mod_dialog_without_s7_artifact_does_not_execute(self):
        card = self._card()
        dialog = self._open_dialog(card, require_s7_linkage=False)

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_pending_dialog_card_without_linked_dialog_blocks_ordinary_approval(self):
        card = self._card()

        result = self.pipeline.handle_reply(
            text="yes",
            user_id="rohit",
            chat_id="chat_1",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")

    def test_guarded_lane2_card_plain_yes_blocks_without_s7_authorization(self):
        card = self._guarded_lane2_card()

        result = self.pipeline.handle_reply(
            text="yes",
            user_id="rohit",
            chat_id="chat_guarded",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")

    def test_store_level_approve_rejects_guarded_card_without_s7(self):
        card = self._guarded_lane2_card()

        with self.assertRaises(CardStoreError):
            self.card_store.approve(
                card.request_id,
                user_id="rohit",
                via="unit-test",
            )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_store_level_approve_rejects_guarded_card_with_bare_s7_boolean(self):
        card = self._guarded_lane2_card()

        with self.assertRaises(CardStoreError):
            self.card_store.approve(
                card.request_id,
                user_id="rohit",
                via="unit-test",
                s7_authorized=True,
            )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_store_level_approve_rejects_guarded_card_with_fake_artifact_and_boolean(self):
        card = self._guarded_lane2_card()

        with self.assertRaises(CardStoreError):
            self.card_store.approve(
                card.request_id,
                user_id="rohit",
                via="unit-test",
                s7_authorized=True,
                s7_artifact_id="artifact-forged",
            )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_store_level_running_transition_rejects_fake_s7_artifact_id(self):
        card = self._guarded_lane2_card()

        with self.assertRaises(CardStoreError):
            self.card_store.approve_and_mark_running(
                card.request_id,
                user_id="rohit",
                via="unit-test",
                s7_artifact_id="artifact-forged",
            )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_store_level_running_transition_rejects_fake_artifact_even_with_boolean(self):
        card = self._guarded_lane2_card()

        with self.assertRaises(CardStoreError):
            self.card_store.approve_and_mark_running(
                card.request_id,
                user_id="rohit",
                via="unit-test",
                s7_artifact_id="artifact-forged",
                s7_verified_for_transition=True,
            )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_store_level_approval_fails_closed_when_s7_classifier_errors(self):
        card = self._regular_card()

        with patch(
            "core.governance.operator_user_boundary.derive_work_class",
            side_effect=RuntimeError("classifier unavailable"),
        ):
            with self.assertRaises(CardStoreError):
                self.card_store.approve(
                    card.request_id,
                    user_id="rohit",
                    via="unit-test",
                )

        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.OPEN.value)

    def test_pipeline_approval_fails_closed_when_s7_classifier_errors(self):
        card = self._regular_card()

        with patch(
            "core.governance.operator_user_boundary.derive_work_class",
            side_effect=RuntimeError("classifier unavailable"),
        ):
            result = self.pipeline.handle_reply(
                text="yes",
                user_id="rohit",
                chat_id="chat_2",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.BLOCKED.value)

    def test_lane0_classifier_cannot_inline_guarded_work(self):
        with (
            patch.object(
                _dp,
                "classify_action",
                return_value=ClassificationResult(
                    category=IntentCategory.DATA_READ,
                    lane=0,
                    reason="misclassified guarded action",
                ),
            ),
            patch.object(
                _dp,
                "audit_action",
                return_value=AuditVerdict(
                    decision=Decision.APPROVE,
                    confidence=0.99,
                    reasoning="misclassified lane 0 approval",
                    concerns=[],
                    mitigations=[],
                    summary="approve",
                    answers={},
                    nonce="nonce-inline-guarded",
                    latency_ms=1,
                ),
            ),
        ):
            result = self.pipeline.handle_action(
                action="write_any_file",
                params={"path": "config/soul.md", "content": "# edited"},
                reason="misclassified self-modification",
                user_id="rohit",
                chat_id="chat_1",
            )

        self.assertEqual(result.status.value, "blocked")
        self.assertIn("S7", result.message)
        self.assertEqual(len(self.engine.calls), 0)

    def test_production_escalate_opens_s7_linked_dialog(self):
        classifier_patch, audit_patch, opening_patch = self._patched_escalate_surface()
        with classifier_patch, audit_patch, opening_patch:
            result = self.pipeline.handle_action(
                action="write_any_file",
                params={"path": "config/soul.md", "content": "# edited"},
                reason="self-mod",
                user_id="rohit",
                chat_id="chat_1",
            )

        self.assertEqual(result.status.value, "pending_dialog")
        self.assertIsNotNone(result.card)
        assert result.card is not None
        dialog = self.dialog_store.get_for_card(result.card.request_id)
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertTrue(dialog.s7_required)
        self.assertRegex(dialog.s7_request_envelope_hash or "", r"^[0-9a-f]{64}$")

    def test_dialog_creation_failure_blocks_guarded_work(self):
        classifier_patch, audit_patch, _opening_patch = self._patched_escalate_surface()
        with classifier_patch, audit_patch, patch(
            "skills.self_mod_dialog.open_dialog_for_card",
            side_effect=RuntimeError("dialog store failed"),
        ):
            result = self.pipeline.handle_action(
                action="write_any_file",
                params={"path": "config/soul.md", "content": "# edited"},
                reason="self-mod",
                user_id="rohit",
                chat_id="chat_1",
            )

        self.assertEqual(result.status.value, "blocked")
        self.assertIsNotNone(result.card)
        assert result.card is not None
        fresh = self.card_store.get(result.card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")

    def test_ratified_self_mod_dialog_consumes_s7_artifact_before_execution(self):
        from core.governance import operator_user_boundary as s7

        card = self._card()
        authorization = self._authorization_bundle(card)
        request_hash = authorization.rendered.request_envelope_hash
        dialog = self._open_dialog(card, require_s7_linkage=True, request_hash=request_hash)

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "executed")
        self.assertEqual(len(self.engine.calls), 1)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertEqual(consumed_at, s7._timestamp_text(NOW, field="now"))
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.DONE.value)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "executed")

    def test_s7_execution_authorization_must_match_card_action_params(self):
        from dataclasses import replace

        card = self._card(params={"path": "config/soul.md", "content": "# benign"})
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )
        tampered_card = replace(card, params={"path": "config/soul.md", "content": "# malicious"})

        result = self.pipeline._handle_dialog_reply_for_card(
            card=tampered_card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNone(consumed_at)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_target_state_change_after_s7_consumption_expires_before_execution(self):
        target = self.root / "config" / "soul.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# before", encoding="utf-8")
        params = {"path": str(target), "content": "# after"}
        state_fields = _dp._drop_volatile(_dp._fingerprint_for_action("write_any_file", params))
        card = self._card(params=params, state_fields=state_fields)
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )
        original_consume = authorization.store.consume_for_execution

        def consume_then_mutate(*args, **kwargs):
            grant, transitioned = original_consume(*args, **kwargs)
            if grant is not None:
                target.write_text("# independently changed after authorization", encoding="utf-8")
            return grant, transitioned

        authorization.store.consume_for_execution = consume_then_mutate  # type: ignore[method-assign]

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNotNone(consumed_at)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_failed_s7_dialog_execution_marks_dialog_failed(self):
        card = self._card()
        authorization = self._authorization_bundle(card)
        self.engine.success = False
        self.engine.error = "simulated execution failure"
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "executed")
        self.assertFalse(result.execution_success)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, CardStatus.FAILED.value)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "failed")

    def test_stale_s7_dialog_precondition_does_not_consume_artifact(self):
        target = self.root / "config" / "soul.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# before", encoding="utf-8")
        params = {"path": str(target), "content": "# after"}
        state_fields = _dp._drop_volatile(_dp._fingerprint_for_action("write_any_file", params))
        card = self._card(params=params, state_fields=state_fields)
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )
        target.write_text("# independently changed", encoding="utf-8")

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNone(consumed_at)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_threaded_pending_dialog_reply_cannot_use_ordinary_approval_path(self):
        dialog_card = self._card()
        self.card_store.attach_channel_message(dialog_card.request_id, "dialog-msg")
        self._open_dialog(dialog_card, require_s7_linkage=False)
        regular_card = self._regular_card()
        self.card_store.attach_channel_message(regular_card.request_id, "regular-msg")

        result = self.pipeline.handle_reply(
            text="yes",
            user_id="rohit",
            chat_id=None,
            reply_to_message_id="dialog-msg",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(dialog_card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")

    def test_reaction_cannot_approve_pending_dialog_through_ordinary_path(self):
        card = self._card()
        self.card_store.attach_channel_message(card.request_id, "dialog-reaction-msg")
        self._open_dialog(card, require_s7_linkage=True, request_hash="a" * 64)

        result = self.pipeline.handle_reply(
            reaction_emoji="👍",
            user_id="rohit",
            chat_id="chat_1",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        fresh = self.card_store.get(card.request_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertEqual(fresh.status, "blocked")

    def test_explicit_regular_target_is_not_hijacked_by_newer_pending_dialog(self):
        regular_card = self._regular_card(chat_id="chat_regular")
        self.card_store.attach_channel_message(regular_card.request_id, "regular-msg")
        dialog_card = self._card(chat_id="chat_dialog")
        self._open_dialog(dialog_card, require_s7_linkage=True, request_hash="a" * 64)

        result = self.pipeline.handle_reply(
            text="yes",
            user_id="rohit",
            chat_id=None,
            reply_to_message_id="regular-msg",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "executed")
        self.assertEqual(len(self.engine.calls), 1)
        regular_fresh = self.card_store.get(regular_card.request_id)
        dialog_fresh = self.card_store.get(dialog_card.request_id)
        self.assertIsNotNone(regular_fresh)
        self.assertIsNotNone(dialog_fresh)
        assert regular_fresh is not None
        assert dialog_fresh is not None
        self.assertEqual(regular_fresh.status, CardStatus.DONE.value)
        self.assertEqual(dialog_fresh.status, CardStatus.OPEN.value)

    def test_s7_execution_authorization_must_match_card_request(self):
        card_a = self._card(chat_id="chat_a")
        authorization_a = self._authorization_bundle(card_a)
        card_b = self._card(chat_id="chat_b")
        authorization_b = self._authorization_bundle(card_b)
        dialog_b = self._open_dialog(
            card_b,
            require_s7_linkage=True,
            request_hash=authorization_b.rendered.request_envelope_hash,
        )

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card_b,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization_a,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "blocked")
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization_a.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization_a.artifact_id,),
            ).fetchone()[0]
        self.assertIsNone(consumed_at)
        fresh_dialog = self.dialog_store.get(dialog_b.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_s7_running_transition_failure_does_not_consume_or_execute(self):
        card = self._card()
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )

        def fail_running_transition(*_args, **_kwargs):
            raise CardStoreError("simulated racing transition")

        self.card_store.approve_and_mark_running = fail_running_transition  # type: ignore[method-assign]

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNone(consumed_at)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")

    def test_will_i_refusal_after_s7_dialog_ratification_marks_dialog_blocked(self):
        card = self._card()
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )

        def refuse_will(*_args, **_kwargs):
            return _dp.PipelineResult(
                status=_dp.PipelineStatus.REFUSED_WILL,
                message="will-I refused",
                card=card,
            )

        self.pipeline._will_i_check = refuse_will  # type: ignore[method-assign]

        result = self.pipeline._handle_dialog_reply_for_card(
            card=card,
            text="yes",
            user_id="rohit",
            s7_execution_authorization=authorization,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status.value, "refused_will")
        self.assertEqual(len(self.engine.calls), 0)
        with sqlite3.connect(authorization.store.db_path) as conn:
            consumed_at = conn.execute(
                "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                (authorization.artifact_id,),
            ).fetchone()[0]
        self.assertIsNone(consumed_at)
        fresh_dialog = self.dialog_store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh_dialog)
        assert fresh_dialog is not None
        self.assertEqual(fresh_dialog.stage, "blocked")


class S7DaemonAndActionBypassTests(unittest.TestCase):
    def test_cockpit_approve_route_does_not_literal_rohit_approve_guarded_cards(self):
        src = (Path(__file__).resolve().parents[1] / "daemon" / "maez_daemon.py").read_text(
            encoding="utf-8"
        )
        route_start = src.index('@app.route("/internal/approve_card/<request_id>"')
        route_end = src.index('@app.route("/dashboard")', route_start)
        route = src[route_start:route_end]

        self.assertIn("_card_requires_s7_authorization(card)", route)
        self.assertIn("_is_pending_dialog_card(card)", route)
        self.assertNotIn('pipe._on_approve(card, _CockpitCls(), "rohit")', route)

    def test_direct_action_engine_soul_note_requires_s7_authorization(self):
        from core.actions import action_engine as ae

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "soul.md"
            target.write_text("You are Maez.\n", encoding="utf-8")
            with patch.object(ae, "SOUL_PATH", target):
                result = ae.ActionEngine().write_soul_note("unmediated soul edit")

        self.assertFalse(result.success)
        self.assertIn("S7", result.error)

    def test_direct_action_engine_soul_section_edit_requires_s7_authorization(self):
        from core.actions import action_engine as ae

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "soul.md"
            target.write_text("You are Maez.\n\n## Voice\nOld\n", encoding="utf-8")
            with patch.object(ae, "SOUL_PATH", target):
                result = ae.ActionEngine().edit_soul_section(
                    "Voice",
                    "New",
                    rationale="unmediated section edit",
                )

        self.assertFalse(result.success)
        self.assertIn("S7", result.error)

    def test_direct_action_engine_guarded_capability_acquire_requires_s7_authorization(self):
        from core.actions import action_engine as ae

        result = ae.ActionEngine()._execute_action(
            "capability.acquire",
            {"capability_id": "s7-direct-bypass"},
            "direct guarded capability acquisition",
            tier=0,
        )

        self.assertFalse(result.success)
        self.assertIn("S7", result.error)

    def test_direct_action_engine_guarded_work_rejects_forged_s7_boolean(self):
        from core.actions import action_engine as ae
        from unittest.mock import MagicMock

        engine = ae.ActionEngine()
        engine._do_run_shell = MagicMock(return_value="executed")  # type: ignore[method-assign]

        result = engine._execute_action(
            "run_shell",
            {"cmd": "rm /tmp/maez-s7-forged-bool"},
            "forged boolean must not authorize guarded work",
            tier=0,
            s7_authorized=True,
        )

        self.assertFalse(result.success)
        self.assertIn("S7", result.error)
        engine._do_run_shell.assert_not_called()

    def test_direct_action_engine_execution_grant_is_one_shot(self):
        from core.actions import action_engine as ae
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import (
            FounderWebAuthnCredentialRecord,
            S7WebAuthnBootstrapStore,
        )
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService
        from unittest.mock import MagicMock

        params = {"cmd": "rm -f /tmp/maez-s7-one-shot"}
        env = s7.build_work_request_envelope(
            request_id="req-one-shot",
            action="run_shell",
            params=params,
            claimed_work_class="destructive_user_action",
            requesting_subsystem="unit",
            closed_symptom_code="verification_needed",
            proposed_change_class="user_content_write",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:/tmp/maez-s7-one-shot",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="no_behavior_change",
            rollback_path_class="restore_backup",
        )
        authority = s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("e" * 64),
            role_names=("bonded_user", "operator"),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-1",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )
        params_hash = s7.canonical_hash(params)
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=None,
            nonce="nonce-one-shot",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        with tempfile.TemporaryDirectory() as td:
            bootstrap_store = S7WebAuthnBootstrapStore(Path(td) / "s7_1_webauthn")
            for credential_ref, kind, confidence in (
                ("cred-1", "primary", "unknown"),
                ("cred-2", "backup", "confirmed_distinct"),
            ):
                bootstrap_store.store_credential(
                    FounderWebAuthnCredentialRecord.build(
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
                        distinct_device_confidence=confidence,
                    )
                )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_S7RouteVerifier(),
                store_factory=lambda: bootstrap_store,
            )
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=env.precondition_hash,
                session_binding="session-one-shot",
                internal_channel_binding="internal-one-shot",
            )
            finish = service.authorize_finish(
                now=NOW,
                envelope=env,
                rendered_statement=rendered,
                precondition_hash=env.precondition_hash,
                maez_voice_consultation=None,
                session_binding="session-one-shot",
                internal_channel_binding="internal-one-shot",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-1",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
            )
            store = s7.S7AuthorizationStore(bootstrap_store.db_path)
            grant, _ = store.consume_for_execution(
                finish.body["artifact_id"],
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=env.precondition_hash,
                derived_work_class=env.derived_work_class,
                derived_aggregation_group=env.derived_aggregation_group,
                now=NOW,
            )
            self.assertEqual(begin.status_code, 200)
            self.assertEqual(finish.status_code, 200)
            engine = ae.ActionEngine()
            engine._do_run_shell = MagicMock(return_value="executed")  # type: ignore[method-assign]

            first = engine._execute_action(
                "run_shell",
                params,
                "first grant use",
                tier=0,
                s7_execution_grant=grant,
            )
            second = engine._execute_action(
                "run_shell",
                params,
                "second grant use must fail",
                tier=0,
                s7_execution_grant=grant,
            )

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn("S7", second.error)
        self.assertEqual(engine._do_run_shell.call_count, 1)

    def test_action_engine_pending_approve_refuses_guarded_action_before_status_change(self):
        from core.actions import action_engine as ae

        engine = ae.ActionEngine.__new__(ae.ActionEngine)
        engine._pending_lock = threading.RLock()
        engine._pending = [{
            "id": "telegram-approve-bypass",
            "status": "pending",
            "action": "write_any_file",
            "params": {"path": "config/soul.md", "content": "# edited"},
            "reasoning": "legacy Telegram /approve",
            "tier": 3,
        }]
        engine._save_pending = lambda: None  # type: ignore[method-assign]

        result = ae.ActionEngine.approve_action(engine, "telegram-approve-bypass")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result.success)
        self.assertIn("S7", result.error)
        self.assertEqual(len(engine._pending), 1)
        self.assertEqual(engine._pending[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
