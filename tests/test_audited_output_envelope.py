# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 wiring: audit_assistant_text() forwards evidence_envelope.

The daemon and telegram_voice both produce audited text via
core.safety.audited_output.audit_assistant_text. Slice 3 wiring adds
an evidence_envelope kwarg that flows through to
self_claim_audit.audit, which already accepts it. Tests pin:

  - the wrapper accepts the new kwarg without breaking any existing
    caller (kwarg is optional, defaults to None)
  - the wrapper forwards the envelope unchanged to the inner audit
  - when None is passed, behavior matches legacy (signals path)
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)

from core.safety import audited_output  # noqa: E402
from core.safety import self_claim_audit  # noqa: E402


class _FakeAuditResult:
    def __init__(self, text):
        self.text = text
        self.rewritten = False
        self.mode = "noop"
        self.flags = []


class _CapturingAudit:
    def __init__(self, return_text):
        self.calls = []
        self.return_text = return_text

    def __call__(self, text, **kwargs):
        self.calls.append({"text": text, **kwargs})
        return _FakeAuditResult(self.return_text)


class WrapperForwardsEnvelopeTests(unittest.TestCase):
    def test_envelope_flows_through_to_inner_audit(self):
        cap = _CapturingAudit("audited reply text")
        with patch.object(self_claim_audit, "audit", cap):
            env = {
                "schema_version": 1,
                "tool_results": [{"name": "ls", "status": "ok"}],
                "claimable": [], "forbidden": [],
                "self_history": [],
                "signals_present": ["system stats"],
                "signals_absent": [],
            }
            audited_output.audit_assistant_text(
                "the system is healthy according to stats",
                surface="test",
                signals_present=["system stats"],
                signals_absent=[],
                evidence_envelope=env,
            )
        self.assertEqual(len(cap.calls), 1)
        self.assertEqual(cap.calls[0].get("evidence_envelope"), env)

    def test_no_envelope_kwarg_backward_compatible(self):
        cap = _CapturingAudit("audited reply text")
        with patch.object(self_claim_audit, "audit", cap):
            audited_output.audit_assistant_text(
                "the system is healthy according to stats",
                surface="test",
                signals_present=["system stats"],
                signals_absent=[],
            )
        self.assertEqual(len(cap.calls), 1)
        self.assertIsNone(cap.calls[0].get("evidence_envelope"))
        self.assertEqual(cap.calls[0].get("signals_present"),
                         ["system stats"])

    def test_envelope_none_preserves_legacy_signals_path(self):
        # Disabled-mode contract: when builder returns None, callers
        # pass evidence_envelope=None. Audit chain MUST still see
        # signals_present/signals_absent so the legacy path runs.
        cap = _CapturingAudit("audited reply text")
        with patch.object(self_claim_audit, "audit", cap):
            audited_output.audit_assistant_text(
                "the system is healthy according to stats",
                surface="test",
                signals_present=["LEGACY_PRESENT"],
                signals_absent=["LEGACY_ABSENT"],
                evidence_envelope=None,
            )
        kw = cap.calls[0]
        self.assertIsNone(kw.get("evidence_envelope"))
        self.assertEqual(kw.get("signals_present"), ["LEGACY_PRESENT"])
        self.assertEqual(kw.get("signals_absent"), ["LEGACY_ABSENT"])


if __name__ == "__main__":
    unittest.main()
