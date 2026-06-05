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
from types import SimpleNamespace
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
        mm._recent_telegram_exchange_rows = lambda *a, **k: []
        mm._query_collection = lambda *a, **k: []
        mm.core = mock.Mock()
        mm.daily = mock.Mock()
        mm.raw = mock.Mock()
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

    def test_timing_uncertain_fallback_does_not_replace_empty_status(self):
        win = _window(7, 0)
        mm = self._mm(daily_in=[], raw_in=[])
        mm._query_collection = lambda *a, **k: [{
            "id": "fallback-daily",
            "content": "Related but older daily context.",
            "metadata": {"timestamp": "2026-01-01T00:00:00+00:00"},
        }]
        out = mm._relative_temporal_address_recall(
            "what were we working on last week?",
            win,
        )
        self.assertEqual(
            out["temporal_status"]["status"],
            "no_date_confirmed_event_memories",
        )
        self.assertEqual(out["daily"][0]["id"], "fallback-daily")
        self.assertFalse(out["daily"][0]["metadata"]["date_confirmed"])
        self.assertEqual(
            out["daily"][0]["metadata"]["temporal_match_label"],
            "semantic match, timing uncertain (not date-confirmed)",
        )


class RecallRoutingTests(unittest.TestCase):
    def _legacy_mm(self):
        from unittest import mock

        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        mm.get_all_core = lambda: [{"id": "core", "content": "core", "metadata": {}}]
        mm.daily = mock.Mock(name="daily")
        mm.raw = mock.Mock(name="raw")

        def _query(collection, query, n, **kwargs):
            if collection is mm.daily:
                return [{"id": "daily", "content": query, "metadata": {}}]
            if collection is mm.raw:
                return [{"id": "raw", "content": query, "metadata": {}}]
            return []

        mm._query_collection = _query
        mm._recent_reddit_source_rows = lambda *a, **k: []
        mm._recent_telegram_exchange_rows = lambda *a, **k: []
        mm._merge_recall_candidates = lambda rows, extra: list(rows) + list(extra)
        mm._topic_rerank = lambda query, raw, n: raw[:n]
        return mm

    def test_non_temporal_query_is_byte_identical_legacy(self):
        mm = self._legacy_mm()
        out = mm.recall_for_telegram("what is the capital of France?")
        self.assertEqual([row["id"] for row in out["core"]], ["core"])
        self.assertEqual([row["id"] for row in out["daily"]], ["daily"])
        self.assertEqual([row["id"] for row in out["raw"]], ["raw"])
        self.assertNotIn("temporal_status", out)

    def test_helper_unavailable_yields_status_not_semantic(self):
        from unittest import mock

        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        mm.get_all_core = lambda: []
        mm.daily = mock.Mock()
        mm.raw = mock.Mock()
        mm._query_collection = mock.Mock(side_effect=AssertionError("semantic called"))
        with mock.patch("core.memory.temporal_anchor_recall.detect_temporal_anchor") as detect:
            detect.return_value = SimpleNamespace(
                anchor_kind="last_week",
                anchor_detected=True,
                window_start=None,
                window_end=None,
                search_status="helper_unavailable",
            )
            out = mm.recall_for_telegram("what did we do last week?")
        self.assertEqual(out["daily"], [])
        self.assertEqual(out["raw"], [])
        self.assertEqual(out["temporal_status"]["status"], "temporal_helper_unavailable")

    def test_relative_anchor_routes_local_window_to_window_first_branch(self):
        from unittest import mock
        from zoneinfo import ZoneInfo

        from memory.memory_manager import MemoryManager

        zone = ZoneInfo("America/Chicago")
        start_local = datetime(2026, 6, 1, 0, 0, tzinfo=zone)
        end_local = datetime(2026, 6, 2, 0, 0, tzinfo=zone)
        mm = MemoryManager.__new__(MemoryManager)
        mm._relative_temporal_address_recall = mock.Mock(return_value={
            "core": [],
            "daily": [],
            "raw": [],
            "temporal_status": None,
        })
        with mock.patch("core.memory.temporal_anchor_recall.detect_temporal_anchor") as detect:
            detect.return_value = SimpleNamespace(
                anchor_kind="yesterday",
                anchor_detected=True,
                window_start=start_local,
                window_end=end_local,
                search_status="bounded_search_no_match",
            )
            mm.recall_for_telegram("what did we do yesterday?")
        window = mm._relative_temporal_address_recall.call_args.args[1]
        self.assertEqual(window.start_utc, start_local.astimezone(timezone.utc))
        self.assertEqual(window.end_utc, end_local.astimezone(timezone.utc))


class StatusRenderTests(unittest.TestCase):
    def _mm(self):
        from memory.memory_manager import MemoryManager

        return MemoryManager.__new__(MemoryManager)

    def test_empty_with_status_still_renders_typed_status_not_recalled_row(self):
        mm = self._mm()
        block = mm.format_for_prompt({
            "core": [],
            "daily": [],
            "raw": [],
            "temporal_status": {
                "label": "last week",
                "status": "no_date_confirmed_event_memories",
                "text": "No date-confirmed event memories found for last week.",
            },
        })
        self.assertIn("TEMPORAL_RECALL_STATUS", block)
        self.assertIn("last week", block)
        self.assertNotIn("<RECALLED", block)

    def test_no_status_and_no_rows_stays_empty(self):
        mm = self._mm()
        self.assertEqual(mm.format_for_prompt({"core": [], "daily": [], "raw": []}), "")


if __name__ == "__main__":
    unittest.main()
