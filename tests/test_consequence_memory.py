# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.consequence_memory — non-audit mistake storage."""
from __future__ import annotations

import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "cm.db"
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_CONSEQUENCE_MEMORY_DB": str(self._db_path)},
        )
        self._env.start()
        from core import consequence_memory
        importlib.reload(consequence_memory)
        self.cm = consequence_memory

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class WriteAndRead(_Base):
    def test_record_and_recent(self):
        rid = self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE,
            context="git push origin",
            outcome="non-zero exit 128: auth failed",
            feedback="check that git remote uses SSH not HTTPS token",
            surface="daemon",
            tags=["git", "push"],
            extra={"cwd": "/home/rohit/maez"},
        )
        self.assertIsInstance(rid, int)
        rows = self.cm.recent()
        self.assertEqual(len(rows), 1)
        e = rows[0]
        self.assertEqual(e.kind, "tool_failure")
        self.assertIn("git", e.context)
        self.assertEqual(e.tags, ["git", "push"])
        self.assertEqual(e.extra, {"cwd": "/home/rohit/maez"})
        self.assertFalse(e.heeded)

    def test_unknown_kind_is_warned_but_stored(self):
        """Any string is accepted; unknown kinds log a warning but
        still write — so novel classes can be explored without a
        schema change."""
        with self.assertLogs("maez.consequence_memory", level="WARNING"):
            rid = self.cm.record_event(
                kind="novel_class",
                context="x", outcome="y",
            )
        self.assertIsInstance(rid, int)
        events = self.cm.recent()
        self.assertEqual(events[0].kind, "novel_class")

    def test_recent_filters_by_kind(self):
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="a", outcome="b",
        )
        self.cm.record_event(
            kind=self.cm.CLASS_CARD_REJECTED, context="c", outcome="d",
        )
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="e", outcome="f",
        )
        all_events = self.cm.recent()
        self.assertEqual(len(all_events), 3)
        tool_only = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(tool_only), 2)
        for e in tool_only:
            self.assertEqual(e.kind, "tool_failure")

    def test_recent_filters_by_window(self):
        # Insert a "recent" and an "old" event, then query with a
        # short window.
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="fresh", outcome="f",
        )
        import sqlite3
        # Back-date the row we just inserted beyond any realistic window
        with sqlite3.connect(self._db_path) as con:
            con.execute("UPDATE events SET ts = ?", (time.time() - 48 * 3600,))
            con.commit()
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="fresh2", outcome="f",
        )
        recent_6h = self.cm.recent(window_hours=6)
        self.assertEqual(len(recent_6h), 1)
        self.assertEqual(recent_6h[0].context, "fresh2")

        all_events = self.cm.recent(window_hours=200)
        self.assertEqual(len(all_events), 2)


class HeededFlag(_Base):
    def test_mark_heeded_flips_flag(self):
        rid = self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="x", outcome="y",
        )
        self.assertFalse(self.cm.recent()[0].heeded)
        self.assertTrue(self.cm.mark_heeded(rid))
        self.assertTrue(self.cm.recent()[0].heeded)

    def test_mark_heeded_unknown_id_returns_false(self):
        self.assertFalse(self.cm.mark_heeded(99999))


class Relevant(_Base):
    def test_token_overlap_retrieval(self):
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE,
            context="git push to origin failed with auth error",
            outcome="128",
            feedback="use ssh remote",
            tags=["git", "auth"],
        )
        self.cm.record_event(
            kind=self.cm.CLASS_USER_CORRECTION,
            context="do not restart the daemon without consent",
            outcome="corrected",
            feedback="always ask before restart",
            tags=["daemon", "restart"],
        )

        hits = self.cm.relevant(
            context_snippet="git push origin main",
        )
        self.assertGreaterEqual(len(hits), 1)
        # Most relevant should be the git event
        self.assertEqual(hits[0].kind, "tool_failure")

        # A query about restart should prefer the correction event
        hits2 = self.cm.relevant(
            context_snippet="maybe we should restart the daemon now",
        )
        self.assertGreaterEqual(len(hits2), 1)
        self.assertEqual(hits2[0].kind, "user_correction")

    def test_empty_query_returns_empty(self):
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="any", outcome="any",
        )
        self.assertEqual(self.cm.relevant(context_snippet=""), [])
        self.assertEqual(self.cm.relevant(context_snippet="   "), [])
        # Query with only stopword-short tokens should also return []
        self.assertEqual(self.cm.relevant(context_snippet="a b c"), [])


class Stats(_Base):
    def test_stats_buckets_by_class_and_heeded(self):
        r1 = self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="a", outcome="b",
        )
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="c", outcome="d",
        )
        self.cm.record_event(
            kind=self.cm.CLASS_CARD_REJECTED, context="e", outcome="f",
        )
        self.cm.mark_heeded(r1)

        s = self.cm.stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_class"]["tool_failure"]["count"], 2)
        self.assertEqual(s["by_class"]["tool_failure"]["heeded"], 1)
        self.assertEqual(s["by_class"]["card_rejected"]["count"], 1)
        self.assertEqual(s["by_class"]["card_rejected"]["heeded"], 0)

    def test_stats_empty_db(self):
        s = self.cm.stats()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["by_class"], {})


class PromptBlock(_Base):
    def test_format_for_prompt_renders(self):
        self.cm.record_event(
            kind=self.cm.CLASS_TOOL_FAILURE, context="git push",
            outcome="auth err", feedback="use ssh remote",
        )
        events = self.cm.recent()
        block = self.cm.format_for_prompt(events)
        self.assertIn("LEARNED FROM PAST MISTAKES", block)
        self.assertIn("tool_failure", block)
        # Feedback preferred over outcome when both present
        self.assertIn("use ssh remote", block)

    def test_format_for_prompt_empty_returns_empty_string(self):
        self.assertEqual(self.cm.format_for_prompt([]), "")

    def test_format_caps_at_max_events(self):
        for i in range(10):
            self.cm.record_event(
                kind=self.cm.CLASS_TOOL_FAILURE,
                context=f"x{i}", outcome="y",
                feedback=f"note-{i}",
            )
        events = self.cm.recent(limit=10)
        block = self.cm.format_for_prompt(events, max_events=3)
        self.assertEqual(block.count("- "), 3)


if __name__ == "__main__":
    unittest.main()
