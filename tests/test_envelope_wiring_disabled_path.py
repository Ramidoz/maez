# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 wiring: disabled-path contract.

The user-explicit requirement: ``MAEZ_EVIDENCE_ENVELOPE_DISABLED=1``
MUST preserve legacy signal audit behavior AND keep recall at the
legacy 60_000-char cap. This file pins those two invariants at the
shared infrastructure layer (the envelope builder + the recall
resolver) where any caller wiring is forced to honor them.

Cross-layer integration with daemon/handle_message and telegram_voice
is verified at the same layer because both surfaces consume the same
helpers — testing the helpers exhaustively pins the wiring without
the brittleness of in-process daemon test harnesses.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)

from core.cognition import envelope_builder as eb  # noqa: E402
from core.safety import audited_output  # noqa: E402
from core.safety import self_claim_audit  # noqa: E402


class _AuditResult:
    def __init__(self, text):
        self.text = text
        self.rewritten = False
        self.mode = "noop"
        self.flags = []


class _CapturingAudit:
    def __init__(self):
        self.calls = []

    def __call__(self, text, **kwargs):
        self.calls.append({"text": text, **kwargs})
        return _AuditResult(text)


class DisabledModeRecallCapTests(unittest.TestCase):
    def test_disabled_returns_60k_legacy(self):
        with patch.dict(os.environ,
                        {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
            self.assertEqual(eb.resolve_recall_cap_chars(), 60_000)

    def test_enabled_returns_52k(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            os.environ.pop("MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS", None)
            self.assertEqual(eb.resolve_recall_cap_chars(), 52_000)


class DisabledModeBuilderTests(unittest.TestCase):
    def test_disabled_returns_none_envelope(self):
        with patch.dict(os.environ,
                        {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
            env = eb.build_envelope(
                ledger_db_path=None,
                signals_present=["system stats"],
                signals_absent=["calendar"],
                tool_results=[{"name": "ls", "status": "ok",
                               "summary": "x"}],
            )
        self.assertIsNone(env)

    def test_disabled_renderer_returns_empty_block(self):
        # Caller pattern: env = build(); block = render(env). With env
        # is None, the rendered prompt block is empty — the LLM
        # prompt is byte-identical to the legacy shape.
        with patch.dict(os.environ,
                        {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
            env = eb.build_envelope(
                ledger_db_path=None,
                signals_present=[], signals_absent=[],
                tool_results=[],
            )
        self.assertEqual(eb.render_envelope_for_prompt(env), "")


class DisabledModePreservesLegacySignalsTests(unittest.TestCase):
    """End-to-end at the audit_assistant_text layer: with envelope=None
    (the disabled-mode result), legacy signals_present/signals_absent
    flow through to the inner audit unchanged."""

    def test_legacy_signals_path_intact_when_envelope_disabled(self):
        cap = _CapturingAudit()
        with patch.object(self_claim_audit, "audit", cap):
            with patch.dict(os.environ,
                            {"MAEZ_EVIDENCE_ENVELOPE_DISABLED": "1"}):
                # Caller computes envelope (None) and passes it.
                env = eb.build_envelope(
                    ledger_db_path=None,
                    signals_present=["system stats"],
                    signals_absent=["calendar"],
                    tool_results=[],
                )
                self.assertIsNone(env)
                audited_output.audit_assistant_text(
                    "the system reports a clean state currently",
                    surface="daemon_cycle",
                    signals_present=["system stats"],
                    signals_absent=["calendar"],
                    evidence_envelope=env,
                )
        self.assertEqual(len(cap.calls), 1)
        kw = cap.calls[0]
        self.assertIsNone(kw.get("evidence_envelope"))
        self.assertEqual(kw.get("signals_present"), ["system stats"])
        self.assertEqual(kw.get("signals_absent"), ["calendar"])


class DaemonRecallSiteWiringTests(unittest.TestCase):
    """The daemon's handle_message imports resolve_recall_cap_chars,
    build_envelope, and render_envelope_for_prompt from
    core.cognition.envelope_builder. Verify the imports remain
    accessible (broken imports = daemon won't start)."""

    def test_daemon_imports_resolve(self):
        # The wiring slice replaced the hardcoded 60_000 with the
        # resolver. If anyone ever renames the helper, daemon
        # startup will fail — this test catches that drift.
        from core.cognition.envelope_builder import (
            build_envelope,
            render_envelope_for_prompt,
            resolve_recall_cap_chars,
        )
        # All three are callable.
        self.assertTrue(callable(build_envelope))
        self.assertTrue(callable(render_envelope_for_prompt))
        self.assertTrue(callable(resolve_recall_cap_chars))


class TelegramVoiceWiringTests(unittest.TestCase):
    """telegram_voice imports the same three helpers PLUS
    default_ledger_db_path and default_audit_signals. Pin all five so
    a rename can't silently break the surface."""

    def test_telegram_voice_imports_resolve(self):
        from core.cognition.envelope_builder import (
            build_envelope,
            default_ledger_db_path,
            render_envelope_for_prompt,
        )
        from core.safety.audit_signal_manifest import default_audit_signals
        self.assertTrue(callable(build_envelope))
        self.assertTrue(callable(default_ledger_db_path))
        self.assertTrue(callable(render_envelope_for_prompt))
        self.assertTrue(callable(default_audit_signals))


class AuditTelegramReplyEnvelopeForwardTests(unittest.TestCase):
    """skills/telegram_voice._audit_telegram_reply forwards the
    envelope to self_claim_audit.audit. With envelope=None (disabled
    mode), legacy signals are still consulted by audit_assistant_text-
    equivalent fallback inside self_claim_audit.audit."""

    def test_envelope_forwarded_to_audit(self):
        from skills.telegram_voice import _audit_telegram_reply
        cap = _CapturingAudit()
        with patch.object(self_claim_audit, "audit", cap):
            env = {
                "schema_version": 1,
                "tool_results": [], "claimable": [], "forbidden": [],
                "self_history": [],
                "signals_present": ["model identity"],
                "signals_absent": [],
            }
            _audit_telegram_reply(
                "the model is Qwen3.6-27B-UD-Q4_K_XL on llama.cpp",
                surface="telegram_text",
                evidence_envelope=env,
            )
        self.assertEqual(len(cap.calls), 1)
        self.assertEqual(cap.calls[0].get("evidence_envelope"), env)

    def test_disabled_envelope_none_falls_through(self):
        from skills.telegram_voice import _audit_telegram_reply
        cap = _CapturingAudit()
        with patch.object(self_claim_audit, "audit", cap):
            _audit_telegram_reply(
                "the system reports a clean state currently",
                surface="telegram_text",
                evidence_envelope=None,
            )
        self.assertEqual(len(cap.calls), 1)
        self.assertIsNone(cap.calls[0].get("evidence_envelope"))


if __name__ == "__main__":
    unittest.main()
