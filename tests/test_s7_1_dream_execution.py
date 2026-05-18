"""S7.1 guarded dream-state execution tests."""

from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

NOW = "2026-05-18T12:00:00+00:00"
FUTURE = "2026-05-18T12:05:00+00:00"


class _RecordingActionEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def write_soul_note(self, note: str, *, s7_execution_grant: object | None = None):
        self.calls.append((note, s7_execution_grant))
        return "written"


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
        artifact = s7.S7AuthorizationArtifact(
            artifact_id="artifact-dream-1",
            request_id=rendered.request_id,
            request_envelope_hash=rendered.request_envelope_hash,
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=rendered.action_params_hash,
            precondition_hash=envelope.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-primary",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )
        store = s7.S7AuthorizationStore(db_path)
        store.put(artifact)
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact.artifact_id,
            rendered=rendered,
            action_params_hash=rendered.action_params_hash,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            now=NOW,
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
                    "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                    (authorization.artifact_id,),
                ).fetchone()[0]

        self.assertTrue(ok, message)
        self.assertEqual(len(action_engine.calls), 1)
        self.assertIsNotNone(action_engine.calls[0][1])
        self.assertIsNotNone(consumed_at)
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop["status"], "applied")


if __name__ == "__main__":
    unittest.main()
