from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class S7BridgePipelineLifetimeTest(unittest.TestCase):
    def test_telegram_voice_pipeline_carries_dream_before_bridge_runs(self):
        from core.audit_log import AuditLog
        from core.decision.decision_pipeline import (
            _drop_volatile,
            _fingerprint_for_action,
        )
        from core.evolution.dream_state import DreamState
        from core.pending_cards import PendingCardStore
        from skills.telegram_voice import TelegramVoice

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dream = DreamState(
                memory=None,
                telegram=None,
                action_engine=None,
                db_path=str(root / "dream.db"),
            )
            prop_id = dream._store_proposal("Maez notices a pattern.")
            daemon = SimpleNamespace(dream=dream)
            params = {
                "note": "[DREAM] Maez notices a pattern.",
                "_proposal_id": prop_id,
                "_proposal_fingerprint": dream.proposal_fingerprint(prop_id),
            }
            state_fields = _drop_volatile(
                _fingerprint_for_action("write_soul_note", params)
            )
            card = SimpleNamespace(
                action="write_soul_note",
                params=params,
                state_hash=PendingCardStore(db_path=root / "tmp-cards.db").create_card(
                    action="write_soul_note",
                    params=params,
                    state_fields=state_fields,
                ).state_hash,
            )

            with patch.dict(
                "os.environ",
                {
                    "MAEZ_TELEGRAM_TOKEN": "dummy-token",
                    "MAEZ_TELEGRAM_USER_ID": "123",
                },
                clear=False,
            ):
                voice = TelegramVoice(memory=None, daemon=daemon)
            voice.actions = object()

            with patch(
                "core.pending_cards.PendingCardStore",
                side_effect=lambda: PendingCardStore(root / "cards.db"),
            ), patch(
                "core.audit_log.AuditLog",
                side_effect=lambda: AuditLog(root / "audit.db"),
            ):
                pipe = voice._get_pipeline()

            self.assertIs(pipe.dream, dream)
            self.assertTrue(pipe._s7_card_precondition_fresh(card))
