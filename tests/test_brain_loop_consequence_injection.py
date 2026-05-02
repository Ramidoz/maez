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


class CardRejectedProducer(_Base):
    """Rejecting a card via decision_pipeline._on_deny should produce
    a card_rejected row in consequence_memory."""

    def test_deny_records_rejection(self):
        """Direct producer smoke — call consequence_memory.record_event
        the way decision_pipeline does, verify retrieval."""
        from core import consequence_memory as cm
        cm.record_event(
            kind=cm.CLASS_CARD_REJECTED,
            context="action=run_shell cmd='sudo apt install telegram-cli'",
            outcome="rohit said: I don't want telegram-cli installed",
            surface="decision_pipeline",
            tags=["run_shell", "sudo"],
            extra={"request_id": "test-req-abc123"},
        )
        rows = self.cm.recent(kind=self.cm.CLASS_CARD_REJECTED)
        self.assertEqual(len(rows), 1)
        self.assertIn("sudo apt install", rows[0].context)
        self.assertIn("telegram-cli", rows[0].outcome)

    def test_rejected_surfaces_for_similar_future_request(self):
        """The whole point: later, when planner considers a similar
        proposal, retrieval should find the rejection."""
        from core import consequence_memory as cm
        cm.record_event(
            kind=cm.CLASS_CARD_REJECTED,
            context="action=run_shell cmd='sudo apt install telegram-cli'",
            outcome="rohit said: I don't want telegram-cli installed",
            surface="decision_pipeline",
        )
        hits = cm.relevant(
            context_snippet="install telegram-cli for me please",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].kind, "card_rejected")


class ApprovedAndFailedProducer(_Base):
    """REGRESSION GUARD for the gap surfaced by the drift report:
    _on_approve's failure branch was writing only to audit_log.db,
    not to consequence_memory. So when ``apt install openrgb`` was
    approved and failed 80+ times historically, NONE of those
    failures were learnable signal — Maez's planner had no memory
    of "I tried this and it doesn't work," so the same proposal
    kept resurfacing.

    The fix wires _on_approve's failure path to write
    CLASS_TOOL_FAILURE to consequence_memory, mirroring _on_deny's
    existing CLASS_CARD_REJECTED write. This test asserts the
    producer-side contract directly (the same shape
    decision_pipeline writes) so the retrieval path that already
    works for CLASS_CARD_REJECTED also works for the new
    failures."""

    def test_approve_then_failed_records_tool_failure(self):
        """Direct producer smoke — call consequence_memory.record_event
        the way decision_pipeline _on_approve's failure branch does
        post-fix, verify retrieval."""
        from core import consequence_memory as cm
        cm.record_event(
            kind=cm.CLASS_TOOL_FAILURE,
            context="action=run_shell cmd='sudo apt install openrgb'",
            outcome=(
                "exit=100; stderr: E: Unable to locate package openrgb"
            ),
            surface="decision_pipeline",
            tags=["run_shell", "sudo"],
            extra={"request_id": "test-req-fail-001"},
        )
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 1)
        self.assertIn("openrgb", rows[0].context)
        self.assertIn("Unable to locate", rows[0].outcome)
        self.assertIn("run_shell", rows[0].tags)

    def test_failure_surfaces_for_repeat_proposal(self):
        """The whole point: later, when planner considers proposing
        the same install again, retrieval should find the prior
        failure so Maez doesn't re-propose blindly."""
        from core import consequence_memory as cm
        cm.record_event(
            kind=cm.CLASS_TOOL_FAILURE,
            context="action=run_shell cmd='sudo apt install openrgb'",
            outcome="exit=100; stderr: E: Unable to locate package openrgb",
            surface="decision_pipeline",
            tags=["run_shell"],
        )
        hits = cm.relevant(
            context_snippet="install openrgb for the lighting",
        )
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0].kind, "tool_failure")

    def test_call_site_present_in_decision_pipeline(self):
        """REGRESSION GUARD for reviewer M2: producer-shape tests
        prove the contract but not that the call site EXISTS in
        decision_pipeline._on_approve's failure branch. A future
        refactor that deletes the new block would pass every
        producer test silently. AST-parse asserts the call site
        is present in the _on_approve method body."""
        import ast
        from pathlib import Path
        path = (
            Path(__file__).resolve().parent.parent
            / "core" / "decision" / "decision_pipeline.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # Walk to find the _on_approve method.
        on_approve_node = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef)
                    and node.name == "_on_approve"):
                on_approve_node = node
                break
        self.assertIsNotNone(
            on_approve_node, "_on_approve method missing",
        )
        # Search the method body for a `record_event(kind=CLASS_
        # TOOL_FAILURE, ...)` call. Any matching shape — positional
        # or keyword arg — counts.
        found = False
        for n in ast.walk(on_approve_node):
            if not isinstance(n, ast.Call):
                continue
            # Match `<...>.record_event(...)` calls.
            func = n.func
            if not (isinstance(func, ast.Attribute)
                    and func.attr == "record_event"):
                continue
            # Look for `kind=CLASS_TOOL_FAILURE` in keyword args
            # OR `<module>.CLASS_TOOL_FAILURE` as the kind kwarg
            # value.
            for kw in n.keywords:
                if kw.arg != "kind":
                    continue
                val = kw.value
                # Match `_cm.CLASS_TOOL_FAILURE` or
                # `consequence_memory.CLASS_TOOL_FAILURE`.
                if (isinstance(val, ast.Attribute)
                        and val.attr == "CLASS_TOOL_FAILURE"):
                    found = True
                    break
            if found:
                break
        self.assertTrue(
            found,
            "_on_approve must call record_event(kind=CLASS_TOOL_FAILURE) "
            "on the approved-and-failed path. Without this, planner "
            "loses the learning signal for repeat-failure patterns "
            "(see drift-report investigation surfacing 95 historical "
            "run_shell failures with no consequence_memory trail).",
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
