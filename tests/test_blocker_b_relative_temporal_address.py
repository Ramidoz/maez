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


if __name__ == "__main__":
    unittest.main()
