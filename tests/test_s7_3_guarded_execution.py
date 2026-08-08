"""S7.3 guarded self-modification execution tests."""

from __future__ import annotations

from contextlib import closing
import inspect
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tests.s7_store_fixture import fresh_store_at


NOW = "2026-05-21T16:00:00+00:00"
FUTURE = "2026-05-21T17:00:00+00:00"


class S73ReviewedReaderRouteTests(unittest.TestCase):
    def test_reviewed_prompt_hashes_are_literal_pins_matching_file_bytes(self):
        from core.governance import operator_user_boundary as s7
        from core.governance import s7_guarded_execution as guarded

        reader_prompt_path = Path("prompts/s7.voice.semantic_reader_v1.md")
        consultation_prompt_path = Path("prompts/s7.voice.consultation.v1.md")
        self.assertTrue(reader_prompt_path.exists())
        self.assertTrue(consultation_prompt_path.exists())
        self.assertEqual(
            guarded.S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            "a5675bbaf5b0681184eeea1ed859ae5763132d5c8a7809eff31821052194c53f",
        )
        self.assertEqual(
            guarded.S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH,
            "5cbf2702ab477d14e948215f1c902abbaf1bedfd9976f49516c2a66ff6e3e0b8",
        )
        self.assertEqual(
            guarded.S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            s7.canonical_hash(reader_prompt_path.read_bytes()),
        )
        self.assertEqual(
            guarded.S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH,
            s7.canonical_hash(consultation_prompt_path.read_bytes()),
        )
        self.assertNotEqual(
            guarded.S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            s7.canonical_hash(str(reader_prompt_path)),
        )
        source = inspect.getsource(guarded)
        self.assertNotIn(
            "S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH = _hash_file_bytes",
            source,
        )
        self.assertNotIn(
            "S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH = _hash_file_bytes",
            source,
        )

    def test_reviewed_reader_route_is_local_only_not_subscription_proxy(self):
        from core.governance import s7_guarded_execution as guarded

        self.assertNotEqual(
            guarded.S7_VOICE_SEMANTIC_READER_PROVIDER,
            "subscription_proxy",
        )
        self.assertIn("local", guarded.S7_VOICE_SEMANTIC_READER_PROVIDER)

    def test_tampered_consultation_prompt_fails_before_model_call(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from core.decision.decision_pipeline import DecisionPipeline
        from core.governance import s7_guarded_execution as guarded

        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "consultation.md"
            prompt_path.write_text("tampered", encoding="utf-8")
            pipe = DecisionPipeline.__new__(DecisionPipeline)
            with patch.object(guarded, "S7_VOICE_CONSULTATION_PROMPT_PATH", prompt_path):
                with self.assertRaisesRegex(ValueError, "prompt hash mismatch"):
                    pipe._s7_voice_raw_response_for_card(
                        SimpleNamespace(action="write_any_file", params={}),
                        SimpleNamespace(
                            affected_refs=(),
                            derived_work_class="self_modification",
                            request_id="req",
                        ),
                    )

    def test_tampered_reader_prompt_fails_before_model_call(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from core.decision.decision_pipeline import DecisionPipeline
        from core.governance import s7_guarded_execution as guarded

        with tempfile.TemporaryDirectory() as tmp:
            prompt_path = Path(tmp) / "reader.md"
            prompt_path.write_text("tampered", encoding="utf-8")
            pipe = DecisionPipeline.__new__(DecisionPipeline)
            with patch.object(guarded, "S7_VOICE_SEMANTIC_READER_PROMPT_PATH", prompt_path):
                with self.assertRaisesRegex(ValueError, "prompt hash mismatch"):
                    pipe._s7_semantic_reader_attempt_for_voice_response(
                        "raw response",
                        SimpleNamespace(action="write_any_file", params={}),
                        SimpleNamespace(request_id="req"),
                    )

    def test_semantic_reader_prompt_includes_proposal_and_raw_response(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from core.decision.decision_pipeline import DecisionPipeline

        captured = {}

        class Response:
            message = SimpleNamespace(
                content='{"status":"no_blocking_signal_detected","quote":null,"start":null,"end":null,"reason":"fixture"}'
            )

        def fake_chat(**kwargs):
            captured.update(kwargs)
            return Response()

        pipe = DecisionPipeline.__new__(DecisionPipeline)
        card = SimpleNamespace(
            action="write_any_file",
            params={"path": "config/soul.md", "content": "# after"},
        )
        envelope = SimpleNamespace(
            affected_refs=("file:config/soul.md",),
            derived_work_class="self_modification",
            request_id="req-reader-proposal",
        )
        with patch("core.routing.llm_client.chat", side_effect=fake_chat):
            pipe._s7_semantic_reader_attempt_for_voice_response(
                "I object because the proposal changes config/soul.md",
                card,
                envelope,
            )

        prompt = captured["messages"][0]["content"]
        self.assertIn("proposal:", prompt)
        self.assertIn("raw_response:", prompt)
        self.assertIn("config/soul.md", prompt)
        self.assertIn("I object because", prompt)

    def test_semantic_reader_proposal_only_quote_fails_closed(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from core.decision.decision_pipeline import DecisionPipeline

        class Response:
            message = SimpleNamespace(
                content=(
                    '{"status":"blocking_signal_present",'
                    '"quote":"config/soul.md","start":0,"end":14,'
                    '"reason":"fixture quoted from proposal"}'
                )
            )

        pipe = DecisionPipeline.__new__(DecisionPipeline)
        card = SimpleNamespace(
            action="write_any_file",
            params={"path": "config/soul.md", "content": "# after"},
        )
        envelope = SimpleNamespace(
            affected_refs=("file:config/soul.md",),
            derived_work_class="self_modification",
            request_id="req-reader-proposal-only-quote",
        )
        with patch("core.routing.llm_client.chat", return_value=Response()):
            attempt = pipe._s7_semantic_reader_attempt_for_voice_response(
                "I have no objection.",
                card,
                envelope,
            )

        self.assertEqual(
            attempt.raw_semantic_reader_outcome,
            "unreadable_or_uncertain",
        )
        self.assertIsNone(attempt.grounding_response_span_quote)
        self.assertIsNone(attempt.grounding_response_span_offset)


class S73GuardedMintPreconditionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _db_path(self) -> Path:
        return Path(self._tmp.name) / "s7_3_guarded.db"

    def _artifact(self, *, artifact_id: str = "artifact-s7-3-1"):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id=f"req-{artifact_id}",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content_hash": "d" * 64},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
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
            maez_voice_consultation_id=f"voice-{artifact_id}",
            free_text_ref_hash="b" * 64,
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
        consultation = s7.MaezVoiceConsultation(
            consultation_id=f"voice-{artifact_id}",
            request_id=env.request_id,
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
        params_hash = s7.canonical_hash({"path": "config/soul.md", "content_hash": "d" * 64})
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=f"nonce-{artifact_id}",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        return s7.S7AuthorizationArtifact(
            artifact_id=artifact_id,
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=params_hash,
            precondition_hash=env.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )

    def _artifact_count(self) -> int:
        with closing(sqlite3.connect(self._db_path())) as conn:
            return conn.execute("SELECT COUNT(*) FROM s7_authorization_artifacts").fetchone()[0]

    def _valid_source_bundle_validation(self, artifact, *, source_ref_hash: str = "c" * 64):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
            S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
            S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
            S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
            S7_VOICE_SEMANTIC_READER_PROVIDER,
            S7_VOICE_SEMANTIC_READER_ROUTE_ID,
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            S7VoiceSourceBundleHashBinding,
            validate_s7_voice_source_bundle,
        )

        bundle_store = S7VoiceConsultationBundleStore(self._db_path())
        attempt_store = S7SemanticReaderAttemptStore(self._db_path())
        attempt = S7SemanticReaderAttemptEvidence(
            semantic_reader_route_id=S7_VOICE_SEMANTIC_READER_ROUTE_ID,
            semantic_reader_provider=S7_VOICE_SEMANTIC_READER_PROVIDER,
            semantic_reader_provider_model=S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
            semantic_reader_model_snapshot=S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
            semantic_reader_decoding_params_hash=S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
            semantic_reader_prompt_hash=S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            semantic_reader_route_config_hash=S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
        )
        attempt_store.put(attempt)
        raw_text = "Maez says there is no objection."
        rendered_prompt_text = f"S7 voice consultation prompt for {artifact.request_id}"
        rendered_prompt_hash = s7.canonical_hash(rendered_prompt_text)
        manifest = bundle_store.put_reviewed_context_manifest(
            manifest_id=f"context-{artifact.artifact_id}",
            preview_ref=f"preview-{artifact.artifact_id}",
            request_envelope_hash=artifact.request_envelope_hash,
            precondition_hash=artifact.precondition_hash,
            created_at=NOW,
        )
        binding = S7VoiceSourceBundleHashBinding(
            request_id=artifact.request_id,
            consultation_id=f"voice-{artifact.artifact_id}",
            source_ref_hash=source_ref_hash,
            request_envelope_hash=artifact.request_envelope_hash,
            rendered_text_hash=artifact.rendered_text_hash,
            action_params_hash=artifact.action_params_hash,
            precondition_hash=artifact.precondition_hash,
            authority_context_hash=artifact.authority_context_hash,
            maez_voice_consultation_hash="6" * 64,
            rendered_prompt_hash=rendered_prompt_hash,
            mutation_preview_hash="8" * 64,
            rollback_plan_ref="9" * 64,
            context_manifest_hash=manifest.context_manifest_hash,
            runtime_identity_hash="b" * 64,
            model_routing_identity_hash="d" * 64,
            model_config_hash="e" * 64,
        )
        bundle_store.put_raw_response(f"raw-{artifact.artifact_id}", raw_text)
        bundle_store.put_rendered_prompt(
            f"prompt-{artifact.artifact_id}",
            rendered_prompt_text,
        )
        bundle_store.put_bundle(
            S7VoiceConsultationBundle(
                source_ref_hash=source_ref_hash,
                request_id=artifact.request_id,
                consultation_id=f"voice-{artifact.artifact_id}",
                request_envelope_hash=binding.request_envelope_hash,
                rendered_text_hash=binding.rendered_text_hash,
                action_params_hash=binding.action_params_hash,
                precondition_hash=binding.precondition_hash,
                authority_context_hash=binding.authority_context_hash,
                maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                rendered_prompt_ref=f"prompt-{artifact.artifact_id}",
                rendered_prompt_hash=binding.rendered_prompt_hash,
                mutation_preview_hash=binding.mutation_preview_hash,
                rollback_plan_ref=binding.rollback_plan_ref,
                context_manifest_ref=manifest.manifest_id,
                context_manifest_hash=binding.context_manifest_hash,
                runtime_identity_hash=binding.runtime_identity_hash,
                model_routing_identity_hash=binding.model_routing_identity_hash,
                model_config_hash=binding.model_config_hash,
                raw_response_ref=f"raw-{artifact.artifact_id}",
                raw_response_hash=s7.canonical_hash(raw_text),
                semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
                expires_at=FUTURE,
            )
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id=f"voice-{artifact.artifact_id}",
            request_id=artifact.request_id,
            request_envelope_hash=artifact.request_envelope_hash,
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash=source_ref_hash,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        return validate_s7_voice_source_bundle(
            consultation=consultation,
            bundle_store=bundle_store,
            bundle_use_store=S7VoiceBundleUseStore(self._db_path()),
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

    def test_mint_refuses_to_skip_voice_source_bundle_validation(self):
        from core.governance.s7_guarded_execution import S7GuardedStateStore

        auth_store = fresh_store_at(self._db_path())
        guarded_store = S7GuardedStateStore(authorization_store=auth_store)

        with self.assertRaisesRegex(ValueError, "source-bundle validation"):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=self._artifact(),
                source_bundle_validation=None,
            )

        self.assertEqual(self._artifact_count(), 0)

    def test_mint_refuses_invalid_voice_source_bundle_validation(self):
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceSourceBundleValidationResult,
        )

        auth_store = fresh_store_at(self._db_path())
        guarded_store = S7GuardedStateStore(authorization_store=auth_store)
        invalid_validation = S7VoiceSourceBundleValidationResult(
            status="raw_response_hash_mismatch",
            source_bundle_valid=False,
            mint_eligible=False,
            authority_projection="operational_block",
            failure_reason_code="raw_response_hash_mismatch",
        )

        with self.assertRaisesRegex(ValueError, "valid absent"):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=self._artifact(),
                source_bundle_validation=invalid_validation,
            )

        self.assertEqual(self._artifact_count(), 0)

    def test_mint_reserves_voice_bundle_use_and_persists_only_token_hash(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
        )

        artifact = self._artifact()
        auth_store = fresh_store_at(self._db_path())
        bundle_use_store = S7VoiceBundleUseStore(self._db_path())
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=artifact.request_id,
                source_ref_hash="c" * 64,
                consultation_id=f"voice-{artifact.artifact_id}",
                used_at=NOW,
            )
        )
        guarded_store = S7GuardedStateStore(
            authorization_store=auth_store,
            voice_bundle_use_store=bundle_use_store,
        )
        validation = self._valid_source_bundle_validation(artifact)

        guarded_store.put_artifact_with_bundle_reservation(
            artifact=artifact,
            source_bundle_validation=validation,
            source_ref_hash="c" * 64,
            reservation_token="runtime-token-not-persisted",
            now=NOW,
        )

        self.assertEqual(self._artifact_count(), 1)
        reserved = bundle_use_store.get_for_source_ref("c" * 64)
        self.assertIsNotNone(reserved)
        assert reserved is not None
        self.assertEqual(reserved.reservation_state, "reserved")
        self.assertEqual(reserved.artifact_id, artifact.artifact_id)
        self.assertEqual(reserved.reservation_token_hash, s7.canonical_hash("runtime-token-not-persisted"))
        self.assertEqual(reserved.reserved_at, NOW)
        self.assertIsNone(reserved.consumed_at)
        with closing(sqlite3.connect(self._db_path())) as conn:
            stored_values = conn.execute(
                "SELECT request_id, artifact_id, source_ref_hash, consultation_id, "
                "bundle_use_hash, reservation_token_hash, reservation_state, "
                "reserved_at, consumed_at, used_at FROM s7_voice_bundle_uses"
            ).fetchone()
        self.assertNotIn("runtime-token-not-persisted", tuple(str(value) for value in stored_values))

    def test_mint_refuses_already_reserved_voice_bundle_use_before_artifact_write(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
        )

        first_artifact = self._artifact(artifact_id="artifact-s7-3-first")
        second_artifact = self._artifact(artifact_id="artifact-s7-3-second")
        auth_store = fresh_store_at(self._db_path())
        bundle_use_store = S7VoiceBundleUseStore(self._db_path())
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=first_artifact.request_id,
                source_ref_hash="c" * 64,
                consultation_id=f"voice-{first_artifact.artifact_id}",
                used_at=NOW,
            )
        )
        guarded_store = S7GuardedStateStore(
            authorization_store=auth_store,
            voice_bundle_use_store=bundle_use_store,
        )
        validation = self._valid_source_bundle_validation(first_artifact)
        guarded_store.put_artifact_with_bundle_reservation(
            artifact=first_artifact,
            source_bundle_validation=validation,
            source_ref_hash="c" * 64,
            reservation_token="first-token",
            now=NOW,
        )

        with self.assertRaisesRegex(ValueError, "unreserved"):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=second_artifact,
                source_bundle_validation=validation,
                source_ref_hash="c" * 64,
                reservation_token="second-token",
                now=NOW,
            )

        self.assertEqual(self._artifact_count(), 1)
        reserved = bundle_use_store.get_for_source_ref("c" * 64)
        self.assertIsNotNone(reserved)
        assert reserved is not None
        self.assertEqual(reserved.artifact_id, first_artifact.artifact_id)
        self.assertEqual(reserved.reservation_token_hash, s7.canonical_hash("first-token"))

    def test_mint_rolls_back_reservation_when_artifact_write_fails(self):
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
        )

        artifact = self._artifact()
        auth_store = fresh_store_at(self._db_path())
        auth_store.put(artifact)
        bundle_use_store = S7VoiceBundleUseStore(self._db_path())
        bundle_use_store.put_unreserved(
            S7VoiceBundleUse.new_unreserved(
                request_id=artifact.request_id,
                source_ref_hash="c" * 64,
                consultation_id=f"voice-{artifact.artifact_id}",
                used_at=NOW,
            )
        )
        guarded_store = S7GuardedStateStore(
            authorization_store=auth_store,
            voice_bundle_use_store=bundle_use_store,
        )
        validation = self._valid_source_bundle_validation(artifact)

        with self.assertRaises(sqlite3.IntegrityError):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=artifact,
                source_bundle_validation=validation,
                source_ref_hash="c" * 64,
                reservation_token="runtime-token-rolled-back",
                now=NOW,
            )

        self.assertEqual(self._artifact_count(), 1)
        bundle_use = bundle_use_store.get_for_source_ref("c" * 64)
        self.assertIsNotNone(bundle_use)
        assert bundle_use is not None
        self.assertEqual(bundle_use.reservation_state, "unreserved")
        self.assertIsNone(bundle_use.artifact_id)
        self.assertIsNone(bundle_use.reservation_token_hash)
        self.assertIsNone(bundle_use.reserved_at)


class S73VoiceSourceBundleValidatorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _db_path(self) -> Path:
        return Path(self._tmp.name) / "s7_3_validator.db"

    def _persistable_voice_material(self, *, nonce: str = "nonce-validator-1"):
        from core.governance import operator_user_boundary as s7

        envelope = s7.build_work_request_envelope(
            request_id="req-validator-1",
            action="write_any_file",
            params={"path": "config/soul.md", "content_hash": "d" * 64},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="4" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id="voice-validator-1",
            free_text_ref_hash="b" * 64,
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
        consultation = self._consultation(
            source_ref_hash="c" * 64,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
        )
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash({"path": "config/soul.md", "content_hash": "d" * 64}),
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=nonce,
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        return rendered, envelope, consultation, authority

    def _consultation(
        self,
        *,
        source_ref_hash: str = "c" * 64,
        request_envelope_hash: str = "1" * 64,
        maez_objection_state: str = "absent",
        maez_withdrew_request: bool = False,
    ):
        from core.governance import operator_user_boundary as s7

        return s7.MaezVoiceConsultation(
            consultation_id="voice-validator-1",
            request_id="req-validator-1",
            request_envelope_hash=request_envelope_hash,
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash=source_ref_hash,
            maez_voice_consulted=True,
            maez_objection_state=maez_objection_state,
            maez_withdrew_request=maez_withdrew_request,
            unavailable_reason_code=None,
            created_at=NOW,
        )

    def _expected_binding(self, **overrides):
        from core.governance.s7_guarded_execution import S7VoiceSourceBundleHashBinding

        values = {
            "request_id": "req-validator-1",
            "consultation_id": "voice-validator-1",
            "source_ref_hash": "c" * 64,
            "request_envelope_hash": "1" * 64,
            "rendered_text_hash": "2" * 64,
            "action_params_hash": "3" * 64,
            "precondition_hash": "4" * 64,
            "authority_context_hash": "5" * 64,
            "maez_voice_consultation_hash": "6" * 64,
            "rendered_prompt_hash": "7" * 64,
            "mutation_preview_hash": "8" * 64,
            "rollback_plan_ref": "9" * 64,
            "context_manifest_hash": "a" * 64,
            "runtime_identity_hash": "b" * 64,
            "model_routing_identity_hash": "d" * 64,
            "model_config_hash": "e" * 64,
        }
        values.update(overrides)
        return S7VoiceSourceBundleHashBinding(**values)

    def _reviewed_attempt(self):
        from core.governance.s7_guarded_execution import (
            S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
            S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
            S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
            S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
            S7_VOICE_SEMANTIC_READER_PROVIDER,
            S7_VOICE_SEMANTIC_READER_ROUTE_ID,
            S7SemanticReaderAttemptEvidence,
        )

        return S7SemanticReaderAttemptEvidence(
            semantic_reader_route_id=S7_VOICE_SEMANTIC_READER_ROUTE_ID,
            semantic_reader_provider=S7_VOICE_SEMANTIC_READER_PROVIDER,
            semantic_reader_provider_model=S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
            semantic_reader_model_snapshot=S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
            semantic_reader_decoding_params_hash=S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
            semantic_reader_prompt_hash=S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            semantic_reader_route_config_hash=S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
        )

    def _reviewed_blocking_attempt(
        self,
        *,
        grounding_quote: str | None = "do not make this change",
        grounding_offset: int | None = 15,
    ):
        attempt = self._reviewed_attempt()
        return type(attempt)(
            semantic_reader_route_id=attempt.semantic_reader_route_id,
            semantic_reader_provider=attempt.semantic_reader_provider,
            semantic_reader_provider_model=attempt.semantic_reader_provider_model,
            semantic_reader_model_snapshot=attempt.semantic_reader_model_snapshot,
            semantic_reader_decoding_params_hash=attempt.semantic_reader_decoding_params_hash,
            semantic_reader_prompt_hash=attempt.semantic_reader_prompt_hash,
            semantic_reader_route_config_hash=attempt.semantic_reader_route_config_hash,
            raw_semantic_reader_outcome="blocking_signal_present",
            grounding_response_span_quote=grounding_quote,
            grounding_response_span_offset=grounding_offset,
        )

    def _unreviewed_attempt(self):
        return type(self._reviewed_attempt())(
            semantic_reader_route_id="unreviewed_reader",
            semantic_reader_provider="subscription_proxy",
            semantic_reader_provider_model="unreviewed-model",
            semantic_reader_model_snapshot="unreviewed-snapshot",
            semantic_reader_decoding_params_hash="1" * 64,
            semantic_reader_prompt_hash="2" * 64,
            semantic_reader_route_config_hash="3" * 64,
        )

    def _seed_validator_inputs(
        self,
        *,
        raw_text: str = "Maez says there is no objection.",
        stored_raw_hash: str | None = None,
        rendered_prompt_text: str = "S7 voice consultation prompt for req-validator-1",
        stored_rendered_prompt_hash: str | None = None,
        store_rendered_prompt: bool = True,
        binding_overrides: dict | None = None,
        attempt=None,
        source_ref_hash: str = "c" * 64,
        policy_reviewed: bool = True,
        bundle_expires_at: str = FUTURE,
        authority_class: str = "none",
        has_grounded_semantic_blocking_signal: bool = False,
    ):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES,
            S7ContextManifest,
            S7ContextManifestPolicy,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            s7_voice_consultation_bundle_hash,
        )

        bundle_store = S7VoiceConsultationBundleStore(self._db_path())
        bundle_use_store = S7VoiceBundleUseStore(self._db_path())
        attempt_store = S7SemanticReaderAttemptStore(self._db_path())
        attempt = attempt or self._reviewed_attempt()
        attempt_store.put(attempt)
        if store_rendered_prompt:
            bundle_store.put_rendered_prompt("rendered-prompt-1", rendered_prompt_text)
        policy = S7ContextManifestPolicy(
            policy_id="s7-context-policy-v1",
            schema_version="1",
            allowed_fields=("preview_ref", "dialog_context_ref", "rollback_path_class"),
            dialog_context_rules=("no_private_raw_text",),
            reviewed_at="2026-05-21T00:00:00+00:00",
            policy_body_hash="f" * 64 if policy_reviewed else "0" * 64,
        )
        if policy_reviewed:
            self.assertIn(policy.policy_hash, REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES)
        bundle_store.put_context_manifest_policy(policy)
        manifest = S7ContextManifest(
            schema_version="1",
            manifest_id="context-manifest-1",
            preview_ref="preview-ref-1",
            dialog_context_ref=None,
            request_envelope_hash="1" * 64,
            precondition_hash="4" * 64,
            rollback_path_class="revert_patch",
            source_surface="cockpit",
            proposal_origin_label="operator",
            policy_id=policy.policy_id,
            policy_hash=policy.policy_hash,
            created_at=NOW,
        )
        bundle_store.put_context_manifest(manifest)
        binding = self._expected_binding(
            source_ref_hash=source_ref_hash,
            rendered_prompt_hash=stored_rendered_prompt_hash
            or s7.canonical_hash(rendered_prompt_text),
            context_manifest_hash=manifest.context_manifest_hash,
            **(binding_overrides or {}),
        )
        bundle_store.put_raw_response("raw-response-1", raw_text)
        bundle = S7VoiceConsultationBundle(
            source_ref_hash=source_ref_hash,
            request_id="req-validator-1",
            consultation_id="voice-validator-1",
            request_envelope_hash=binding.request_envelope_hash,
            rendered_text_hash=binding.rendered_text_hash,
            action_params_hash=binding.action_params_hash,
            precondition_hash=binding.precondition_hash,
            authority_context_hash=binding.authority_context_hash,
            maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
            rendered_prompt_ref="rendered-prompt-1",
            rendered_prompt_hash=binding.rendered_prompt_hash,
            mutation_preview_hash=binding.mutation_preview_hash,
            rollback_plan_ref=binding.rollback_plan_ref,
            context_manifest_ref=manifest.manifest_id,
            context_manifest_hash=binding.context_manifest_hash,
            runtime_identity_hash=binding.runtime_identity_hash,
            model_routing_identity_hash=binding.model_routing_identity_hash,
            model_config_hash=binding.model_config_hash,
            raw_response_ref="raw-response-1",
            raw_response_hash=stored_raw_hash or s7.canonical_hash(raw_text),
            semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
            expires_at=bundle_expires_at,
            authority_class=authority_class,
            has_grounded_semantic_blocking_signal=has_grounded_semantic_blocking_signal,
            source_bundle_hash=None,
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
                request_id="req-validator-1",
                source_ref_hash=source_ref_hash,
                consultation_id="voice-validator-1",
                used_at=NOW,
            )
        )
        return bundle_store, bundle_use_store, attempt_store, binding

    def test_valid_absent_cannot_be_caller_constructed(self):
        from core.governance.s7_guarded_execution import S7VoiceSourceBundleValidationResult

        with self.assertRaisesRegex(ValueError, "validator"):
            S7VoiceSourceBundleValidationResult(
                status="valid_absent",
                source_bundle_valid=True,
                mint_eligible=True,
                authority_projection="valid_absent",
                failure_reason_code=None,
            )

    def test_validator_produces_valid_absent_after_raw_response_and_reader_replay(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs()

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "valid_absent")
        self.assertTrue(result.source_bundle_valid)
        self.assertTrue(result.mint_eligible)
        self.assertEqual(result.authority_projection, "valid_absent")
        self.assertIsNone(result.failure_reason_code)

    def test_persist_voice_source_bundle_is_write_once_for_unreserved_bundle(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7VoiceConsultationBundleStore,
            persist_s7_voice_source_bundle_for_material,
        )

        rendered, envelope, consultation, authority = self._persistable_voice_material(
            nonce="nonce-validator-first",
        )
        first_binding = persist_s7_voice_source_bundle_for_material(
            db_path=self._db_path(),
            rendered_statement=rendered,
            envelope=envelope,
            maez_voice_consultation=consultation,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            raw_response_text="Maez says there is no objection.",
            semantic_reader_attempt=self._reviewed_attempt(),
            now=NOW,
        )

        second_rendered, _, _, _ = self._persistable_voice_material(
            nonce="nonce-validator-second",
        )
        persist_s7_voice_source_bundle_for_material(
            db_path=self._db_path(),
            rendered_statement=second_rendered,
            envelope=envelope,
            maez_voice_consultation=consultation,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            raw_response_text="Maez says a different thing later.",
            semantic_reader_attempt=self._reviewed_attempt(),
            now=NOW,
        )

        bundle_store = S7VoiceConsultationBundleStore(self._db_path())
        bundle = bundle_store.get_for_source_ref(first_binding.source_ref_hash)
        self.assertIsNotNone(bundle)
        assert bundle is not None
        self.assertEqual(bundle.rendered_text_hash, first_binding.rendered_text_hash)
        self.assertEqual(
            bundle_store.read_raw_response(bundle.raw_response_ref),
            "Maez says there is no objection.",
        )
        self.assertEqual(bundle.raw_response_hash, s7.canonical_hash("Maez says there is no objection."))

    def test_validator_rejects_mismatched_raw_response_hash(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            stored_raw_hash="d" * 64,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "raw_response_hash_mismatch")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_mismatched_rendered_prompt_hash(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            stored_rendered_prompt_hash="e" * 64,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_prompt_integrity")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_missing_rendered_prompt_bytes(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            store_rendered_prompt=False,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_prompt_integrity")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_bundle_bound_to_different_action_params_hash(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs()

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=self._expected_binding(
                rendered_prompt_hash=binding.rendered_prompt_hash,
                action_params_hash="f" * 64,
            ),
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_hash_binding")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_self_consistent_prompt_bound_to_different_rendered_request(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs()

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=self._expected_binding(
                action_params_hash=binding.action_params_hash,
                rendered_prompt_hash="f" * 64,
            ),
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_hash_binding")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_bundle_row_mutated_after_persisted_hash(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs()
        with closing(sqlite3.connect(self._db_path())) as conn:
            conn.execute(
                """
                UPDATE s7_voice_consultation_bundles
                SET action_params_hash = ?
                WHERE source_ref_hash = ?
                """,
                ("f" * 64, "c" * 64),
            )
            conn.commit()

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_hash_binding")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_unreviewed_context_manifest_policy(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            policy_reviewed=False,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_context_manifest_policy")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_expired_source_bundle_before_content_checks(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            bundle_expires_at="2026-05-21T15:59:59+00:00",
            stored_raw_hash="d" * 64,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_expired")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_consultation_bound_to_different_request_hash(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs()

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(request_envelope_hash="f" * 64),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_cross_field_state")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_present_objection_not_replayed_by_reader_output(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            raw_text="Maez says: no, do not make this change.",
            authority_class="operational",
            has_grounded_semantic_blocking_signal=False,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(maez_objection_state="present"),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_reducer_replay")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_claimed_grounding_that_does_not_replay_from_raw_response(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        raw_text = "Maez says: no, do not make this change."
        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            raw_text=raw_text,
            attempt=self._reviewed_blocking_attempt(
                grounding_quote="different words",
                grounding_offset=11,
            ),
            authority_class="authoritative",
            has_grounded_semantic_blocking_signal=True,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(maez_objection_state="present"),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_reducer_replay")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_authority_flag_that_disagrees_with_replayed_grounding(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        raw_text = "Maez says: no, do not make this change."
        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            raw_text=raw_text,
            attempt=self._reviewed_blocking_attempt(),
            authority_class="operational",
            has_grounded_semantic_blocking_signal=False,
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(maez_objection_state="present"),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "invalid_authority_class_replay")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)

    def test_validator_rejects_unreviewed_semantic_reader_identity(self):
        from core.governance.s7_guarded_execution import validate_s7_voice_source_bundle

        bundle_store, bundle_use_store, attempt_store, binding = self._seed_validator_inputs(
            attempt=self._unreviewed_attempt(),
        )

        result = validate_s7_voice_source_bundle(
            consultation=self._consultation(),
            bundle_store=bundle_store,
            bundle_use_store=bundle_use_store,
            semantic_reader_attempt_store=attempt_store,
            expected_binding=binding,
            now=NOW,
        )

        self.assertEqual(result.status, "reader_route_mismatch")
        self.assertFalse(result.source_bundle_valid)
        self.assertFalse(result.mint_eligible)


class S73MintRouteStoreHygieneTests(unittest.TestCase):
    """Store hygiene: a guarded work-class artifact may not be minted via the raw store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _db_path(self) -> Path:
        return Path(self._tmp.name) / "s7_3_route.db"

    def _artifact_count(self) -> int:
        with closing(sqlite3.connect(self._db_path())) as conn:
            return conn.execute("SELECT COUNT(*) FROM s7_authorization_artifacts").fetchone()[0]

    def _artifact(self, *, work_class: str, artifact_id: str = "artifact-route-1"):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id=f"req-{artifact_id}",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content_hash": "d" * 64},
            claimed_work_class=work_class,
            requesting_subsystem="unit",
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
            maez_voice_consultation_id=f"voice-{artifact_id}",
            free_text_ref_hash="b" * 64,
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
        consultation = s7.MaezVoiceConsultation(
            consultation_id=f"voice-{artifact_id}",
            request_id=env.request_id,
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
        params_hash = s7.canonical_hash({"path": "config/soul.md", "content_hash": "d" * 64})
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=f"nonce-{artifact_id}",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        return s7.S7AuthorizationArtifact(
            artifact_id=artifact_id,
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=params_hash,
            precondition_hash=env.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )

    def test_guarded_work_class_artifact_cannot_be_minted_with_only_raw_store(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import mint_authorization_artifact

        artifact = self._artifact(work_class="self_modification")
        self.assertIn(artifact.derived_work_class, s7.VOICE_SEAT_WORK_CLASSES)
        auth_store = fresh_store_at(self._db_path())

        # Wired with ONLY the raw authorization store (no guarded state store):
        # a guarded work-class artifact must fail closed before any persistence.
        with self.assertRaisesRegex(ValueError, "guarded"):
            mint_authorization_artifact(
                artifact=artifact,
                authorization_store=auth_store,
                guarded_store=None,
            )

        self.assertEqual(self._artifact_count(), 0)


if __name__ == "__main__":
    unittest.main()
