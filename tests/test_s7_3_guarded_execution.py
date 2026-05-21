"""S7.3 guarded self-modification execution tests."""

from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path


NOW = "2026-05-21T16:00:00+00:00"
FUTURE = "2026-05-21T17:00:00+00:00"


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

    def test_mint_refuses_to_skip_voice_source_bundle_validation(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import S7GuardedStateStore

        auth_store = s7.S7AuthorizationStore(self._db_path())
        guarded_store = S7GuardedStateStore(authorization_store=auth_store)

        with self.assertRaisesRegex(ValueError, "source-bundle validation"):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=self._artifact(),
                source_bundle_validation=None,
            )

        self.assertEqual(self._artifact_count(), 0)

    def test_mint_refuses_invalid_voice_source_bundle_validation(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceSourceBundleValidationResult,
        )

        auth_store = s7.S7AuthorizationStore(self._db_path())
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

    def test_mint_accepts_literal_valid_absent_voice_source_bundle_validation(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7VoiceSourceBundleValidationResult,
        )

        auth_store = s7.S7AuthorizationStore(self._db_path())
        guarded_store = S7GuardedStateStore(authorization_store=auth_store)
        validation = S7VoiceSourceBundleValidationResult(
            status="valid_absent",
            source_bundle_valid=True,
            mint_eligible=True,
            authority_projection="valid_absent",
            failure_reason_code=None,
        )

        guarded_store.put_artifact_with_bundle_reservation(
            artifact=self._artifact(),
            source_bundle_validation=validation,
        )

        self.assertEqual(self._artifact_count(), 1)


if __name__ == "__main__":
    unittest.main()
