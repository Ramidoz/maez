# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.D.B2 — update_baseline as audited fresh introspection event.

The action_engine's ``update_baseline`` writes a core memory from
LLM-supplied text. Pre-5x.D.B2 it skipped both the provenance
schema AND the ``audit_assistant_text`` invariant that every other
core write of LLM-generated text honors.

Design call (post-grep): this is NOT a promotion of a specific
recalled memory row (the LLM's reasoning context is upstream and
ephemeral; there is no concrete ancestor list at the action layer).
It IS a fresh introspection event that records a baseline claim
the LLM synthesized — same shape as ``proactive_opinion`` and
``reasoning cycle`` (introspection/lived) and ``face_enrollment``
(no ``promoted_from``).

What this slice closes:
  - LLM-authored baseline text is now audited before storage,
    matching the audit-before-store invariant for every other
    LLM-text core write.
  - Provenance lineage carries on the resulting core entry.

What this slice deliberately does NOT close (same caveat the user
raised in the design conversation):
  - update_baseline is a Tier-0 action. The LLM can autonomously
    emit baselines without a covenant gate review of the
    DECISION. This fix audits CONTENT, not policy. Frequency /
    quality / aggregation governance is deferred.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _CapturingMemory:
    """Mirrors live MemoryManager.store_core signature so a future
    required-kwarg drift surfaces here rather than as silent pass."""

    def __init__(self):
        self.store_core_calls: list[dict] = []

    def store_core(self, content, source="reasoning", *,
                   provenance_source=None, trust_tier=None,
                   promoted_from=None,
                   allow_untrusted_ancestors=False):
        self.store_core_calls.append({
            "content": content,
            "source": source,
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "promoted_from": promoted_from,
            "allow_untrusted_ancestors": allow_untrusted_ancestors,
        })
        return "core-fake-id"


class UpdateBaselineProvenanceTests(unittest.TestCase):
    def _make_engine(self, mm):
        # Construct ActionEngine without going through __init__'s heavy
        # path (trust db, telegram client, etc.). The action method we
        # test only touches self.memory.
        from core.actions.action_engine import ActionEngine
        engine = ActionEngine.__new__(ActionEngine)
        engine.memory = mm
        return engine

    # ── audit invariant ─────────────────────────────────────────────

    def test_baseline_text_runs_through_audit_before_storage(self):
        """The audit invariant for LLM-authored text — pre-5x.D.B2,
        update_baseline was the one core-write LLM-text path that
        bypassed audit_assistant_text. After this slice, the
        observation text is audited before it lands."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="AUDITED",
        ) as audit_mock:
            engine._do_update_baseline("raw observation text")
        audit_mock.assert_called_once()
        # The surface must be a stable bucketable identifier per the
        # design conversation; locks the convention against drift.
        kwargs = audit_mock.call_args.kwargs
        self.assertEqual(
            kwargs.get("surface"), "action_baseline_update"
        )
        # Stored content carries the AUDITED text, not the raw
        # input. This is the load-bearing invariant: stored ==
        # audited, identical to the audited_output.py docstring
        # contract for chat replies.
        stored = mm.store_core_calls[0]["content"]
        self.assertIn("AUDITED", stored)
        self.assertNotIn("raw observation text", stored)

    def test_audit_rewrites_propagate_to_stored_text(self):
        """If the audit subsystem rewrites the observation (e.g.
        scrubs a fabricated claim), the rewritten form is what
        gets stored. Mirrors the audited_output.py contract."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="rewritten safer claim",
        ):
            engine._do_update_baseline("possibly fabricated claim")
        stored = mm.store_core_calls[0]["content"]
        self.assertIn("rewritten safer claim", stored)
        self.assertNotIn("possibly fabricated claim", stored)

    def test_audit_failure_does_not_block_storage(self):
        """audit_assistant_text fail-opens (returns original text +
        logs warning) on import / judge / exception failure. This
        slice deliberately preserves that contract — same as chat
        replies and proactive opinions; consistency is load-bearing.
        A future agent must not 'harden' this into a raise without
        revisiting the chat-reply behavior at the same time."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="raw observation text",  # fail-open: original
        ):
            engine._do_update_baseline("raw observation text")
        self.assertEqual(len(mm.store_core_calls), 1)
        self.assertIn("raw observation text",
                      mm.store_core_calls[0]["content"])

    # ── provenance tagging ──────────────────────────────────────────

    def test_baseline_writes_introspection_lived(self):
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        # Same pair as proactive_opinion (daemon:874) and the
        # reasoning cycle (daemon:3470) per 5x.B Pass 1 — Maez
        # synthesizing its own observation, not external ingress.
        self.assertEqual(call["provenance_source"], "introspection")
        self.assertEqual(call["trust_tier"], "lived")
        # Existing freeform `source` field preserved (5x.A non-
        # overload contract — `source` and `provenance_source` are
        # different keys serving different purposes).
        self.assertEqual(call["source"], "baseline_update")

    def test_baseline_does_not_invent_ancestors(self):
        """Same locking pattern as 5x.D.D face_enrollment: this is a
        FRESH introspection event, not a promotion. promoted_from
        must be None. A future agent must not 'fix' the absence by
        passing a stub ancestor — that would falsely run through the
        worst-wins gate on a non-promotion."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        self.assertIsNone(mm.store_core_calls[0]["promoted_from"])

    def test_baseline_does_not_opt_in_to_untrusted_ancestors(self):
        """Symmetry with 5x.D.B1 / 5x.D.D: the call site must never
        silently opt in to untrusted-ancestor promotion. Default
        (False) is the only acceptable value."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        self.assertFalse(
            mm.store_core_calls[0]["allow_untrusted_ancestors"]
        )

    # ── unchanged behavior ──────────────────────────────────────────

    def test_no_memory_short_circuit_unchanged(self):
        """The pre-existing `if not self.memory` short-circuit must
        survive — a daemon initialized without a memory manager
        still gets the safe no-op return string."""
        from core.actions.action_engine import ActionEngine
        engine = ActionEngine.__new__(ActionEngine)
        engine.memory = None
        out = engine._do_update_baseline("anything")
        self.assertEqual(out, "No memory manager")

    def test_returns_promotional_string_on_success(self):
        """Existing return-shape contract preserved: callers parse
        'Baseline stored as core memory: <id>'."""
        mm = _CapturingMemory()
        engine = self._make_engine(mm)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            out = engine._do_update_baseline("anything")
        self.assertTrue(out.startswith("Baseline stored as core memory:"))


if __name__ == "__main__":
    unittest.main()
