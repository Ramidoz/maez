from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from skills.surface import MaezMessageHandler, MessageEvent, Platform, SessionSource
from tests.test_surface_adapter import _FakeDaemon, _Pipe, _TelegramWithController

_SRC = Path("skills/surface/maez_adapter.py").read_text()


class _DreamStore:
    def __init__(self):
        self.applied: list[int] = []
        self.rejected: list[int] = []
        self.pending = [(24, "2026-06-12T00:00:00", "dream proposal")]

    def list_pending(self):
        return list(self.pending)

    def get_proposal(self, target_id):
        if target_id == 24:
            return {"id": 24, "status": "pending", "proposal_type": "append"}
        return None

    def apply_proposal(self, target_id):
        self.applied.append(target_id)
        return True, "dream applied"

    def apply_section_edit_proposal(self, target_id):
        self.applied.append(target_id)
        return True, "section edit applied"

    def reject_proposal(self, target_id):
        self.rejected.append(target_id)
        return True, "dream rejected"


class SurfaceProposalTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def _event(self, text: str) -> MessageEvent:
        return MessageEvent(
            text=text,
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )

    def _handler(self, daemon: _FakeDaemon | None = None) -> MaezMessageHandler:
        daemon = daemon or _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController()
        return MaezMessageHandler(daemon)

    def test_proposal_interceptor_is_after_cards_before_search_commitment(self):
        cards = _SRC.index("get_open_for_channel")
        proposal = _SRC.index("proposal_reply = await self._try_surface_parity_proposal_intent")
        search = _SRC.index("search_commitment_reply = await self._try_search_commitment_intent")
        self.assertLess(cards, proposal)
        self.assertLess(proposal, search)

    def test_flag_off_proposal_phrase_falls_through(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        daemon = _FakeDaemon(reply="general reply")
        handler = self._handler(daemon)
        handler._surface_parity_pending_evolution_candidates = lambda: [
            {"id": 5, "weakness": "candidate"}
        ]
        with patch("skills.evolution_engine.apply_candidate") as apply:
            result = asyncio.run(handler(self._event("approve #5")))

        self.assertEqual(result, "general reply")
        self.assertEqual(daemon.last_text, "approve #5")
        apply.assert_not_called()

    def test_card_precedence_beats_proposal_phrase(self):
        pipe = _Pipe(open_cards=[{"id": "card-1"}], dialog_reply="card handled")
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController(pipe=pipe)
        handler = MaezMessageHandler(daemon)
        handler._surface_parity_pending_evolution_candidates = lambda: [
            {"id": 5, "weakness": "candidate"}
        ]
        with patch("skills.evolution_engine.apply_candidate") as apply:
            result = asyncio.run(handler(self._event("approve #5")))

        self.assertEqual(result, "card handled")
        apply.assert_not_called()

    def test_approve_explicit_evolution_candidate_calls_existing_engine(self):
        handler = self._handler()
        handler._surface_parity_pending_evolution_candidates = lambda: [
            {"id": 5, "weakness": "candidate"}
        ]
        with patch("skills.evolution_engine.apply_candidate", return_value={}) as apply:
            result = asyncio.run(handler(self._event("approve #5")))

        apply.assert_called_once_with(5)
        self.assertIn("Proposal #5 is live", result)

    def test_show_then_bare_yes_binds_to_last_shown(self):
        handler = self._handler()
        handler._surface_parity_pending_evolution_candidates = lambda: [
            {"id": 5, "weakness": "candidate"}
        ]
        display = {
            "target_file": "config/soul.md",
            "intent": {
                "human_rationale": "try a small change",
                "target_name": "voice",
                "current_value": "old",
                "proposed_value": "new",
                "rationale": "test",
            },
            "usefulness": {"overall": "high", "reasoning": "safe"},
        }
        with patch("skills.evolution_engine.load_candidate_for_display", return_value=display):
            show = asyncio.run(handler(self._event("show #5")))
        self.assertIn("Proposal #5", show)

        with patch("skills.evolution_engine.apply_candidate", return_value={}) as apply:
            yes = asyncio.run(handler(self._event("yes")))

        apply.assert_called_once_with(5)
        self.assertIn("Proposal #5 is live", yes)

    def test_approve_explicit_dream_candidate_calls_existing_dream_engine(self):
        daemon = _FakeDaemon(reply="general reply")
        daemon.dream = _DreamStore()
        handler = self._handler(daemon)
        handler._surface_parity_pending_evolution_candidates = lambda: []

        result = asyncio.run(handler(self._event("approve #24")))

        self.assertEqual(daemon.dream.applied, [24])
        self.assertIn("#24: dream applied", result)
