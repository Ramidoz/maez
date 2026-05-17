"""Decision 34 / ADR 0039 — S7 execution-edge pipeline gates."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import unittest

from core.audit import AuditVerdict, Decision
from core.audit_log import AuditLog
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

    def _execute_action(self, action: str, params: dict, reason: str, *, tier: int):
        self.calls.append((action, dict(params or {}), reason, tier))
        return SimpleNamespace(success=self.success, output=self.output, error=self.error)


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
            action="write_any_file",
            params={"path": "notes.txt", "content": "ordinary"},
            reason="ordinary write",
            audit_verdict=AuditVerdict(
                decision=Decision.APPROVE_WITH_CARD,
                confidence=0.9,
                reasoning="ordinary card",
                concerns=[],
                mitigations=[],
                summary="ordinary",
                answers={},
                nonce="nonce-regular",
                latency_ms=1,
            ),
            audit_request_id="audit-regular",
            classification={"intent_category": "FILE_WRITE", "lane": "2"},
            channel="telegram_text",
            chat_id=chat_id,
            user_id="rohit",
        )

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
            maez_objection_present=False,
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
        params_hash = s7.canonical_hash(card.params)
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
        artifact = s7.S7AuthorizationArtifact(
            artifact_id=f"artifact-{card.request_id}",
            request_id=card.request_id,
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
        store = s7.S7AuthorizationStore(self.root / "s7_authorization.db")
        store.put(artifact)
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact.artifact_id,
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

    def test_mark_running_failure_does_not_consume_s7_artifact(self):
        card = self._card()
        authorization = self._authorization_bundle(card)
        dialog = self._open_dialog(
            card,
            require_s7_linkage=True,
            request_hash=authorization.rendered.request_envelope_hash,
        )

        def fail_mark_running(_request_id: str):
            raise CardStoreError("simulated racing transition")

        self.card_store.mark_running = fail_mark_running  # type: ignore[method-assign]

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


if __name__ == "__main__":
    unittest.main()
