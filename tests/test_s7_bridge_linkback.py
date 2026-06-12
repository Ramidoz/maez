from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.audit_log import AuditLog
from core.decision.pending_cards import PendingCardStore


def _dream_state(testcase: unittest.TestCase) -> object:
    from core.evolution.dream_state import DreamState

    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    return DreamState(
        memory=None,
        telegram=None,
        action_engine=None,
        db_path=str(Path(tmp.name) / "dream.db"),
    )


class DreamProposalLinkbackTest(unittest.TestCase):
    def test_mark_applied_moves_pending_row_to_applied(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")

        ok, message = dream.mark_applied(prop_id, source="s7_ceremony_bridge")

        self.assertTrue(ok, message)
        proposal = dream.get_proposal(prop_id)
        self.assertEqual(proposal["status"], "applied")
        self.assertIsNotNone(proposal["applied_at"])

    def test_mark_applied_fails_closed_for_non_pending_row(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        dream.reject_proposal(prop_id)

        ok, message = dream.mark_applied(prop_id, source="s7_ceremony_bridge")

        self.assertFalse(ok)
        self.assertIn("already rejected", message)


class PipelineS7BridgeLinkbackTest(unittest.TestCase):
    def _pipeline(self, dream):
        from core.decision.decision_pipeline import DecisionPipeline

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return DecisionPipeline(
            action_engine=None,
            card_store=PendingCardStore(Path(tmp.name) / "cards.db"),
            audit_log=AuditLog(Path(tmp.name) / "audit.db"),
            dream=dream,
        )

    def test_successful_s7_soul_execution_marks_originating_proposal_applied(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        pipeline = self._pipeline(dream)
        card = SimpleNamespace(
            action="write_soul_note",
            params={"_proposal_id": prop_id},
            request_id="card-1",
        )

        pipeline._mark_s7_bridge_proposal_applied(card)

        self.assertEqual(dream.get_proposal(prop_id)["status"], "applied")

    def test_non_proposal_card_does_not_mutate_dream_state(self):
        dream = _dream_state(self)
        prop_id = dream._store_proposal("Maez notices a pattern.")
        pipeline = self._pipeline(dream)
        card = SimpleNamespace(
            action="write_soul_note",
            params={},
            request_id="card-1",
        )

        pipeline._mark_s7_bridge_proposal_applied(card)

        self.assertEqual(dream.get_proposal(prop_id)["status"], "pending")

    def test_missing_dream_handle_is_nonfatal(self):
        pipeline = self._pipeline(None)
        card = SimpleNamespace(
            action="write_soul_note",
            params={"_proposal_id": 7},
            request_id="card-1",
        )

        pipeline._mark_s7_bridge_proposal_applied(card)

    def test_linkback_call_is_after_successful_executed_dialog_stage(self):
        src = Path("core/decision/decision_pipeline.py").read_text()

        success_stage = src.index("DialogStage.EXECUTED.value")
        linkback = src.index("_mark_s7_bridge_proposal_applied(card)")

        self.assertLess(success_stage, linkback)
