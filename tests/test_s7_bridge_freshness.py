from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.audit_log import AuditLog
from core.decision.pending_cards import PendingCardStore, compute_state_hash


def _dream_state(testcase: unittest.TestCase) -> object:
    from core.evolution.dream_state import DreamState

    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    dream = DreamState(
        memory=None,
        telegram=None,
        action_engine=None,
        db_path=str(Path(tmp.name) / "dream.db"),
    )
    dream._test_tmp = tmp
    return dream


def _card(*, action: str, params: dict, state_fields: dict | None = None):
    return SimpleNamespace(
        action=action,
        params=params,
        state_hash=compute_state_hash(state_fields),
        request_id="card-1",
    )


class ProposalFingerprintTest(unittest.TestCase):
    def test_stable_for_unchanged_proposal(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")

        fp1 = dream.proposal_fingerprint(prop_id)
        fp2 = dream.proposal_fingerprint(prop_id)

        self.assertEqual(fp1, fp2)
        self.assertEqual(fp1["proposal_id"], prop_id)
        self.assertEqual(fp1["proposal_type"], "append")
        self.assertEqual(fp1["status"], "pending")
        self.assertIn("created_at", fp1)
        self.assertIn("content_hash", fp1)

    def test_changes_when_status_changes(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        before = dream.proposal_fingerprint(prop_id)

        dream.reject_proposal(prop_id)
        after = dream.proposal_fingerprint(prop_id)

        self.assertNotEqual(before, after)
        self.assertEqual(after["status"], "rejected")

    def test_changes_when_content_changes(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        before = dream.proposal_fingerprint(prop_id)

        with dream._lock, dream._conn() as conn:
            conn.execute(
                "UPDATE dream_proposals SET insight = ? WHERE id = ?",
                ("Maez notices a different pattern.", prop_id),
            )
            conn.commit()
        after = dream.proposal_fingerprint(prop_id)

        self.assertNotEqual(before["content_hash"], after["content_hash"])

    def test_missing_proposal_is_explicit(self):
        dream = _dream_state(self)

        self.assertEqual(
            dream.proposal_fingerprint(999),
            {"proposal_id": 999, "status": "absent"},
        )


class FingerprintSoulWriteBranchTest(unittest.TestCase):
    def test_soul_write_binds_proposal_fingerprint(self):
        from core.decision.decision_pipeline import _fingerprint_for_action

        fields = _fingerprint_for_action(
            "write_soul_note",
            {
                "note": "x",
                "_proposal_fingerprint": {
                    "proposal_id": 7,
                    "status": "pending",
                    "content_hash": "abc",
                },
            },
        )

        self.assertEqual(fields["proposal_fingerprint"]["proposal_id"], 7)

    def test_soul_write_changes_when_proposal_fingerprint_changes(self):
        from core.decision.decision_pipeline import _fingerprint_for_action

        a = _fingerprint_for_action(
            "write_soul_note",
            {"note": "x", "_proposal_fingerprint": {"status": "pending"}},
        )
        b = _fingerprint_for_action(
            "write_soul_note",
            {"note": "x", "_proposal_fingerprint": {"status": "rejected"}},
        )

        self.assertNotEqual(a, b)

    def test_edit_soul_section_binds_target_name(self):
        from core.decision.decision_pipeline import _fingerprint_for_action

        fields = _fingerprint_for_action(
            "edit_soul_section",
            {
                "target_name": "Values",
                "_proposal_fingerprint": {"status": "pending"},
            },
        )

        self.assertEqual(fields["target_section"], "Values")


class S7BridgeExecutionParamsTest(unittest.TestCase):
    def test_soul_write_execution_params_drop_proposal_meta(self):
        from core.decision.decision_pipeline import DecisionPipeline

        card = _card(
            action="write_soul_note",
            params={
                "note": "n",
                "_proposal_id": 7,
                "_proposal_fingerprint": {"status": "pending"},
            },
        )

        execute_params = DecisionPipeline._execution_params_for_card(card)

        self.assertEqual(execute_params, {"note": "n"})

    def test_edit_soul_section_execution_params_use_real_engine_keys(self):
        from core.decision.decision_pipeline import DecisionPipeline

        card = _card(
            action="edit_soul_section",
            params={
                "target": "wrong",
                "target_name": "Values",
                "new_body": "body",
                "rationale": "why",
                "_proposal_id": 9,
            },
        )

        execute_params = DecisionPipeline._execution_params_for_card(card)

        self.assertEqual(
            execute_params,
            {"target_name": "Values", "new_body": "body", "rationale": "why"},
        )
        self.assertNotIn("target", execute_params)


class S7BridgePreconditionFreshnessTest(unittest.TestCase):
    def test_stale_proposal_fails_precondition_by_re_reading_live_row(self):
        from core.decision.decision_pipeline import (
            DecisionPipeline,
            _drop_volatile,
            _fingerprint_for_action,
        )

        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        params = {
            "note": "[DREAM] Maez notices a pattern.",
            "_proposal_id": prop_id,
            "_proposal_fingerprint": dream.proposal_fingerprint(prop_id),
        }
        state_fields = _drop_volatile(_fingerprint_for_action("write_soul_note", params))
        card = _card(action="write_soul_note", params=params, state_fields=state_fields)
        pipeline = DecisionPipeline(
            action_engine=None,
            card_store=PendingCardStore(Path(dream._test_tmp.name) / "cards.db"),
            audit_log=AuditLog(Path(dream._test_tmp.name) / "audit.db"),
            dream=dream,
        )

        dream.reject_proposal(prop_id)

        self.assertFalse(pipeline._s7_card_precondition_fresh(card))

    def test_missing_dream_handle_fails_closed_for_proposal_bound_soul_card(self):
        from core.decision.decision_pipeline import (
            DecisionPipeline,
            _drop_volatile,
            _fingerprint_for_action,
        )

        params = {
            "note": "[DREAM] Maez notices a pattern.",
            "_proposal_id": 7,
            "_proposal_fingerprint": {"proposal_id": 7, "status": "pending"},
        }
        state_fields = _drop_volatile(_fingerprint_for_action("write_soul_note", params))
        card = _card(action="write_soul_note", params=params, state_fields=state_fields)
        pipeline = DecisionPipeline(
            action_engine=None,
            card_store=PendingCardStore(":memory:"),
            audit_log=AuditLog(":memory:"),
        )

        self.assertFalse(pipeline._s7_card_precondition_fresh(card))
