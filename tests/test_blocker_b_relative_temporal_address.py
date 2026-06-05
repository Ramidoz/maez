# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Blocker-B v1: Relative Temporal Address Recall.

Covenant law: for a relative temporal address, every row reaching the brain is
window-confirmed / timeless-context(core) / explicitly-not-from-window / or
absent-with-an-honest-status. "Empty" is over daily/raw event memories only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from core.routing.temporal_cue import AbsoluteRecallWindow


def _window(days_back_start: int, days_back_end: int) -> AbsoluteRecallWindow:
    now = datetime.now(timezone.utc)
    return AbsoluteRecallWindow(
        start_utc=now - timedelta(days=days_back_start),
        end_utc=now - timedelta(days=days_back_end),
        method="relative_last_week",
        confidence="high",
        label="last week",
    )


class RawWindowHelperProofTests(unittest.TestCase):
    """The MUST-PROVE: raw timestamp ranges degrade honestly in this Chroma."""

    def _mm_with_raw(self, rows):
        # rows: list of (id, iso_timestamp). Build a fake raw collection that
        # exercises the helper against a controllable backend.
        from unittest import mock

        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        raw = mock.Mock()

        def _get(where=None, include=None, **kw):
            return {
                "ids": [r[0] for r in rows],
                "metadatas": [{"timestamp": r[1]} for r in rows],
                "documents": [r[0] for r in rows],
            }

        raw.get.side_effect = _get
        mm.raw = raw
        return mm

    def test_degrades_to_no_raw_rows_when_timestamp_range_is_unsupported(self):
        now = datetime.now(timezone.utc)
        in_win = (now - timedelta(days=4)).isoformat()
        out_win = (now - timedelta(days=53)).isoformat()
        mm = self._mm_with_raw([("in", in_win), ("out", out_win)])
        win = _window(7, 0)
        rows = mm._raw_rows_in_window(win)
        self.assertEqual(rows, [])


class RelativeAddressRecallTests(unittest.TestCase):
    def _mm(self, daily_in=(), raw_in=(), core_in=()):
        from unittest import mock

        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        mm.get_all_core = lambda: [
            {"id": row_id, "content": row_id, "metadata": {"timestamp": ts}}
            for row_id, ts in core_in
        ]
        mm._all_daily_rows = lambda: [
            {"id": row_id, "content": row_id, "metadata": {"timestamp": ts}}
            for row_id, ts in daily_in
        ]
        mm._raw_rows_in_window = lambda window: [
            {"id": row_id, "content": row_id, "metadata": {"timestamp": ts}}
            for row_id, ts in raw_in
        ]
        mm._query_collection = lambda *a, **k: []
        mm.core = mock.Mock()
        mm.daily = mock.Mock()
        return mm

    def test_in_window_daily_surfaces_and_empty_status_is_absent(self):
        now = datetime.now(timezone.utc)
        win = _window(7, 0)
        mm = self._mm(daily_in=[("d_in", (now - timedelta(days=4)).isoformat())])
        out = mm._relative_temporal_address_recall(
            "what did we do last week?",
            win,
        )
        self.assertTrue(any(r.get("id") == "d_in" for r in out["daily"]))
        self.assertEqual(out["temporal_status"], None)

    def test_empty_window_yields_typed_empty_status_over_event_memories(self):
        win = _window(7, 0)
        mm = self._mm(daily_in=[], raw_in=[])
        out = mm._relative_temporal_address_recall(
            "what did we do last week?",
            win,
        )
        self.assertEqual(out["daily"], [])
        self.assertEqual(out["raw"], [])
        self.assertEqual(
            out["temporal_status"]["status"],
            "no_date_confirmed_event_memories",
        )
        self.assertIn("last week", out["temporal_status"]["label"])

    def test_core_in_window_does_not_fill_address_or_suppress_empty(self):
        now = datetime.now(timezone.utc)
        win = _window(7, 0)
        mm = self._mm(core_in=[("c1", (now - timedelta(days=3)).isoformat())])
        out = mm._relative_temporal_address_recall(
            "what did we do last week?",
            win,
        )
        self.assertEqual(
            out["temporal_status"]["status"],
            "no_date_confirmed_event_memories",
        )
        self.assertTrue(all(r.get("id") != "c1" for r in out["daily"] + out["raw"]))


if __name__ == "__main__":
    unittest.main()
