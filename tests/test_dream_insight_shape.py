from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class _DreamMemory:
    def recent_raw(self, *, n: int):
        return {"documents": [f"observation {i}: Rohit worked on temporal recall rails" for i in range(12)]}


class DreamInsightShapeTests(unittest.TestCase):
    def _run_cycle_with_response(self, text: str):
        from core.evolution import dream_state

        telemetry: list[dict] = []
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "dream_proposals.db"
            dream = dream_state.DreamState(
                memory=_DreamMemory(),
                telegram=None,
                action_engine=object(),
                db_path=str(db_path),
            )
            response = SimpleNamespace(message=SimpleNamespace(content=text))
            with mock.patch("core.llm_client.chat", return_value=response), mock.patch.object(
                dream_state,
                "_emit_dream_consolidation_telemetry",
                side_effect=lambda **kwargs: telemetry.append(kwargs),
            ), mock.patch.object(dream, "_is_novel", return_value=True):
                result = dream.run_dream_cycle(force=True)
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT insight, status FROM dream_proposals").fetchall()
        return result, rows, telemetry

    def test_proposal_60_exact_filler_is_rejected_as_not_insight_shaped(self):
        result, rows, telemetry = self._run_cycle_with_response("I'm not sure about that right now.")

        self.assertIsNone(result)
        self.assertEqual([], rows)
        self.assertEqual("skipped", telemetry[-1]["status"])
        self.assertEqual("not_insight_shaped", telemetry[-1]["reason"])

    def test_multi_sentence_i_notice_shape_with_specifics_passes(self):
        proposal_59_shape = (
            "I notice the dream loop keeps circling the same concrete seam: temporal recall "
            "and Telegram prompt assembly both carry past context forward. The useful pattern "
            "is that recall, body activity, and owner-contact rhythm need explicit labels so a "
            "morning greeting does not inherit yesterday's meeting as if it were still pending."
        )

        result, rows, telemetry = self._run_cycle_with_response(proposal_59_shape)

        self.assertEqual(proposal_59_shape, result)
        self.assertEqual([(proposal_59_shape, "pending")], rows)
        self.assertEqual("success", telemetry[-1]["status"])

    def test_nothing_sentinel_keeps_existing_filter_reason(self):
        result, rows, telemetry = self._run_cycle_with_response("NOTHING")

        self.assertIsNone(result)
        self.assertEqual([], rows)
        self.assertEqual("skipped", telemetry[-1]["status"])
        self.assertEqual("nothing", telemetry[-1]["reason"])


if __name__ == "__main__":
    unittest.main()
