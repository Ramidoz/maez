# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 proper — evidence_envelope wiring through self_claim_audit.

The single production callsite of `grounding_judge.judge()` is
`self_claim_audit._find_flags`, which is in turn called by
`self_claim_audit.audit()` from daemon/handle_message, brain_loop, and
telegram_voice. Slice 3 proper extends `audit()` with an optional
`evidence_envelope` kwarg that flows through to the judge — the
envelope IS the canonical generation-time grounding context.

Backward compat is mandatory: callers that don't yet pass an envelope
must keep working unchanged.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
# Ensure the audit isn't disabled by env (some test runners set this).
os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)

from core.safety import self_claim_audit  # noqa: E402
from core.cognition import grounding_judge as gj  # noqa: E402


class _CapturingJudge:
    """Replacement for grounding_judge.judge that captures kwargs and
    returns a controllable flag list."""

    def __init__(self, return_value=None):
        self.calls: list[dict] = []
        self.return_value = return_value or []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return list(self.return_value)


class AuditEnvelopeFlowsThroughTests(unittest.TestCase):
    def setUp(self):
        # Patch the module reference _find_flags imports lazily.
        self.cap = _CapturingJudge(return_value=[])
        # The lazy import is `from core import grounding_judge as _judge_mod`
        # which resolves to the same object as core.cognition.grounding_judge
        # via the shim. Patch the canonical module.
        self._patch = patch.object(gj, "judge", self.cap)
        self._patch.start()
        # Make sure we have a fabrication_memory.few_shots_for that
        # returns []. The real one is fine.

    def tearDown(self):
        self._patch.stop()

    def test_audit_accepts_evidence_envelope_kwarg(self):
        env = {
            "signals_present": ["system stats"],
            "signals_absent": [],
            "tool_results": [],
            "self_history": [],
        }
        result = self_claim_audit.audit(
            text="The system seems healthy.",
            surface="test",
            evidence_envelope=env,
        )
        self.assertEqual(result.mode, "noop")  # judge returned []
        # judge() was called once and received the envelope.
        self.assertEqual(len(self.cap.calls), 1)
        self.assertIn("evidence_envelope", self.cap.calls[0])
        self.assertEqual(
            self.cap.calls[0]["evidence_envelope"], env,
        )

    def test_audit_without_envelope_backward_compatible(self):
        # No envelope kwarg — judge() still called with signals only.
        self_claim_audit.audit(
            text="The system seems healthy.",
            surface="test",
            signals_present=["system stats"],
            signals_absent=["screen"],
        )
        self.assertEqual(len(self.cap.calls), 1)
        kw = self.cap.calls[0]
        self.assertEqual(kw["signals_present"], ["system stats"])
        self.assertEqual(kw["signals_absent"], ["screen"])
        # evidence_envelope kwarg is either absent or None — both fine.
        self.assertIsNone(kw.get("evidence_envelope"))

    def test_audit_envelope_and_signals_both_passed(self):
        # Per the judge contract, when both are present the envelope
        # wins inside judge(). The audit layer doesn't pre-reconcile —
        # it just forwards both, lets judge() do the override.
        env = {
            "signals_present": ["FROM_ENVELOPE"],
            "signals_absent": [],
            "tool_results": [],
            "self_history": [],
        }
        self_claim_audit.audit(
            text="The system reports a clean state currently.",
            surface="test",
            signals_present=["LEGACY"],
            signals_absent=[],
            evidence_envelope=env,
        )
        self.assertEqual(len(self.cap.calls), 1)
        kw = self.cap.calls[0]
        # Both are forwarded; the override happens inside judge(),
        # not in self_claim_audit.
        self.assertEqual(kw["evidence_envelope"], env)


class AuditEnvelopeFabricationTests(unittest.TestCase):
    """When the judge flags a claim, the audit rewrite still works
    correctly with an envelope present (no regression on the rewrite
    path)."""

    def test_flagged_claim_rewritten(self):
        flagged = [{
            "text": "The toaster is haunted",
            "reason": "no signal supports paranormal claims",
            "rewrite": "",
        }]
        with patch.object(gj, "judge",
                          _CapturingJudge(return_value=flagged)):
            result = self_claim_audit.audit(
                text="The kettle is on. The toaster is haunted.",
                surface="test",
                evidence_envelope={
                    "signals_present": [],
                    "signals_absent": [],
                    "tool_results": [],
                    "self_history": [],
                },
            )
        self.assertTrue(result.rewritten)
        self.assertNotIn("haunted", result.text)
        self.assertEqual(result.flags[0].text, "The toaster is haunted")


class DisabledEnvelopePreservesLegacySignalsTests(unittest.TestCase):
    """Reviewer-flagged regression: when the envelope builder returns
    None (MAEZ_EVIDENCE_ENVELOPE_DISABLED=1), the audit chain MUST
    fall through to the legacy signals_present/signals_absent path
    rather than passing a degenerate empty envelope that would, under
    full-takeover semantics in judge(), erase those legacy signals.

    Callers (the upcoming wiring slice) will look like:
        env = builder.build(...)        # may be None when disabled
        audit(text, signals_present=sp, signals_absent=sa,
              evidence_envelope=env)

    With env=None, judge() must still see sp/sa.
    """

    def test_audit_with_envelope_none_uses_legacy_signals(self):
        cap = _CapturingJudge(return_value=[])
        with patch.object(gj, "judge", cap):
            self_claim_audit.audit(
                text="The system reports a clean state currently.",
                surface="test",
                signals_present=["LEGACY_PRESENT"],
                signals_absent=["LEGACY_ABSENT"],
                evidence_envelope=None,  # bypass mode
            )
        self.assertEqual(len(cap.calls), 1)
        kw = cap.calls[0]
        self.assertEqual(kw["signals_present"], ["LEGACY_PRESENT"])
        self.assertEqual(kw["signals_absent"], ["LEGACY_ABSENT"])
        self.assertIsNone(kw.get("evidence_envelope"))


class FindFlagsSignatureTests(unittest.TestCase):
    """Direct test of _find_flags with envelope kwarg."""

    def test_find_flags_forwards_envelope(self):
        cap = _CapturingJudge(return_value=[])
        with patch.object(gj, "judge", cap):
            flags, available = self_claim_audit._find_flags(
                "some text",
                signals_present=["sp"],
                signals_absent=["sa"],
                evidence_envelope={
                    "signals_present": ["sp"],
                    "signals_absent": ["sa"],
                    "tool_results": [{"tool": "ls"}],
                    "self_history": [],
                },
            )
        self.assertTrue(available)
        self.assertEqual(flags, [])
        self.assertEqual(len(cap.calls), 1)
        self.assertIn("evidence_envelope", cap.calls[0])
        self.assertEqual(
            cap.calls[0]["evidence_envelope"]["tool_results"],
            [{"tool": "ls"}],
        )


if __name__ == "__main__":
    unittest.main()
