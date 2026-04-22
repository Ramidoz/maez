# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for brain_loop ↔ consequence_memory integration.

Doesn't exercise the full brain loop (that needs llm_client, an
action_engine, pipeline, ...) — just verifies that _record_tool_failure
talks to the right store and that the import path from brain_loop to
consequence_memory.{relevant, format_for_prompt, mark_heeded} works.
The actual prompt-injection behavior is verified indirectly via the
live daemon reading from the store after a real failure lands."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db = Path(self._tmp.name) / "cm.db"
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_CONSEQUENCE_MEMORY_DB": str(self._db)},
        )
        self._env.start()
        from core import consequence_memory
        importlib.reload(consequence_memory)
        self.cm = consequence_memory

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class RecordTriggeredFromBrainLoop(_Base):
    def test_helper_writes_to_current_cm_db(self):
        """_record_tool_failure in brain_loop should funnel to the
        same consequence_memory module (and thus the same DB) that
        everyone else uses."""
        from core.brain_loop import _record_tool_failure
        _record_tool_failure(
            "run_shell",
            {"cmd": "git push origin main", "reason": "test"},
            "exit=1: Permission denied (publickey)",
            surface="test",
        )
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertIn("git push", r.context)
        self.assertIn("publickey", r.outcome)
        # Tags seed cross-reference
        self.assertIn("run_shell", r.tags)
        self.assertIn("git", r.tags)


class RetrievalWiring(_Base):
    def test_relevant_finds_recorded_failure(self):
        """Simulates a later planner lookup for a similar user
        request — the stored tool_failure should surface."""
        from core.brain_loop import _record_tool_failure
        _record_tool_failure(
            "run_shell",
            {"cmd": "git push origin main"},
            "exit=1: publickey auth failed",
            surface="test",
        )

        # Later, user asks "push my changes"
        hits = self.cm.relevant(
            context_snippet="push my changes to github",
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("git push", hits[0].context)

    def test_format_for_prompt_renders_block(self):
        from core.brain_loop import _record_tool_failure
        _record_tool_failure(
            "run_shell", {"cmd": "apt install xyz"},
            "E: Unable to locate package xyz",
            surface="test",
        )
        events = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        block = self.cm.format_for_prompt(events)
        self.assertIn("LEARNED FROM PAST MISTAKES", block)
        self.assertIn("tool_failure", block)

    def test_empty_store_returns_nothing(self):
        """New install — no failures stored yet. Retrieval should
        gracefully return []."""
        self.assertEqual(
            self.cm.relevant(context_snippet="anything"), [],
        )


class MarkHeededRoundtrip(_Base):
    def test_heeded_flips_and_persists(self):
        from core.brain_loop import _record_tool_failure
        _record_tool_failure(
            "run_shell", {"cmd": "ls /tmp"},
            "exit=1",
            surface="test",
        )
        events = self.cm.recent()
        eid = events[0].id
        # Brain loop calls mark_heeded after surfacing to planner
        self.assertTrue(self.cm.mark_heeded(eid))
        events_after = self.cm.recent()
        self.assertTrue(events_after[0].heeded)


if __name__ == "__main__":
    unittest.main()
