# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Owner approval of terminal want proposals closes the want, not just the card."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from core.audit_log import AuditLog
from core.decision_pipeline import DecisionPipeline, PipelineStatus
from core.evolution import want_pursuit_bridge as wpb
from core.evolution import wants as wants_mod
from core.pending_cards import CardStatus, PendingCardStore

_REPO = Path(__file__).resolve().parent.parent


class _ActionEngine:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def _execute_action(self, action, params, reason, **kwargs):
        self.calls.append((action, dict(params or {})))
        return SimpleNamespace(success=True, output=f"ran:{action}", error="")


class _Cls:
    source = "test"
    reasoning = "owner approved"


class _NoOpenWonderings:
    def list_open(self, limit=200):
        return []

    def list_by_source(self, source):
        return []


class _NoOpenCards:
    def list_open_by_action(self, action):
        return []


class WantsApprovalSatisfactionPipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.wants = wants_mod.Wants(self.root / "wants.db")
        self.cards = PendingCardStore(self.root / "cards.db")
        self.audit = AuditLog(self.root / "audit.db")
        self.engine = _ActionEngine()
        self.pipe = DecisionPipeline(
            action_engine=self.engine,
            card_store=self.cards,
            audit_log=self.audit,
            wants=self.wants,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _audit_row(self, *, action: str, params: dict) -> str:
        return self.audit.record(
            action=action,
            params=params,
            classification=None,
            injection_matches=[],
            verdict=None,
        )

    def _audit_outcome(self, request_id: str) -> str | None:
        with closing(sqlite3.connect(self.root / "audit.db")) as conn:
            row = conn.execute(
                "SELECT outcome FROM audit_log WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return row[0] if row else None

    def _create_want(self) -> str:
        return self.wants.record_event(
            statement="I want the recurring terminal proposal to stop."
        )

    def _terminal_card(self, want_id: str):
        params = {
            "want_id": want_id,
            "proposed": "satisfied",
            "conclusion": "The bounded pursuit reached a conclusion.",
            "wondering_id": 123,
        }
        audit_id = self._audit_row(action=wpb.TERMINAL_PROPOSAL_ACTION, params=params)
        return self.cards.create_card(
            action=wpb.TERMINAL_PROPOSAL_ACTION,
            params=params,
            reason="want terminal proposal",
            plain_english="Review whether this want should be marked satisfied.",
            audit_request_id=audit_id,
            user_id="owner",
        )

    def test_approving_terminal_proposal_satisfies_want_without_action_engine(self):
        want_id = self._create_want()
        card = self._terminal_card(want_id)

        result = self.pipe._on_approve(card, _Cls(), "owner")

        self.assertEqual(result.status, PipelineStatus.EXECUTED)
        self.assertTrue(result.execution_success)
        self.assertEqual(self.engine.calls, [])
        latest = self.wants.current_state(want_id)
        self.assertEqual(latest["event_type"], wants_mod.EVENT_SATISFIED)
        self.assertEqual(latest["evidence"]["basis"], "owner_confirmed")
        self.assertEqual(
            latest["evidence"]["external_object_ref"],
            f"pending_card:{card.request_id}",
        )
        self.assertNotIn("self_observed_resolution", latest["evidence"])
        done = self.cards.get(card.request_id)
        self.assertEqual(done.status, CardStatus.DONE.value)
        self.assertEqual(
            self._audit_outcome(card.audit_request_id),
            "want_satisfied_owner_confirmed",
        )

    def test_satisfied_want_is_no_longer_selected_for_reproposal(self):
        want_id = self._create_want()
        card = self._terminal_card(want_id)

        self.pipe._on_approve(card, _Cls(), "owner")

        selected = wpb.select_want(
            self.wants,
            _NoOpenWonderings(),
            _NoOpenCards(),
            cooldown_s=0.0,
            now=100.0,
            is_hard_want=lambda _: False,
        )
        self.assertIsNone(selected)

    def test_approving_other_card_does_not_satisfy_want(self):
        want_id = self._create_want()
        params = {"path": "README.md"}
        audit_id = self._audit_row(action="read_file", params=params)
        card = self.cards.create_card(
            action="read_file",
            params=params,
            reason="ordinary card",
            plain_english="Read a file.",
            audit_request_id=audit_id,
            user_id="owner",
        )

        result = self.pipe._on_approve(card, _Cls(), "owner")

        self.assertEqual(result.status, PipelineStatus.EXECUTED)
        self.assertEqual(self.engine.calls, [("read_file", params)])
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")

    def test_denying_terminal_proposal_leaves_want_active(self):
        want_id = self._create_want()
        card = self._terminal_card(want_id)

        result = self.pipe._on_deny(card, _Cls(), "owner")

        self.assertEqual(result.status, PipelineStatus.REFUSED_AUDIT)
        self.assertEqual(self.cards.get(card.request_id).status, CardStatus.DENIED.value)
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")
        self.assertIn(want_id, {row["want_id"] for row in self.wants.active_wants()})

    def test_terminal_proposal_without_wants_store_fails_without_execution(self):
        want_id = self._create_want()
        card = self._terminal_card(want_id)
        pipe = DecisionPipeline(
            action_engine=self.engine,
            card_store=self.cards,
            audit_log=self.audit,
            wants=None,
        )

        result = pipe._on_approve(card, _Cls(), "owner")

        self.assertEqual(result.status, PipelineStatus.EXECUTED)
        self.assertFalse(result.execution_success)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(self.wants.current_state(want_id)["event_type"], "created")
        failed = self.cards.get(card.request_id)
        self.assertEqual(failed.status, CardStatus.FAILED.value)


class TelegramPipelineConstructionTests(unittest.TestCase):
    def test_telegram_pipeline_threads_daemon_wants_store(self):
        source = (_REPO / "skills" / "telegram_voice.py").read_text()

        self.assertTrue(
            'wants=getattr(self.daemon, "wants", None)' in source,
            "_get_pipeline must pass daemon.wants into DecisionPipeline",
        )


if __name__ == "__main__":
    unittest.main()
