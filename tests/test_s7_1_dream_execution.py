"""S7.1 guarded dream-state execution tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class _RecordingActionEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def write_soul_note(self, note: str, *, s7_execution_grant: object | None = None):
        self.calls.append((note, s7_execution_grant))
        return "written"


class S71DreamExecutionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
