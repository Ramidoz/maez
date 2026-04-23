# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Test Fix 6 v3 follow-ups that still express testable behavior:

  1. Logs-intent regex tightening — "what happened?" must NOT match 'logs'.
  2. Recovery card reason propagation + single-card-per-recovery-pass
     discipline (both observable through one Jarvis-loop exercise).

Two source-level tests that pinned specific code markers (`break`
statement text, a pipeline-path comment) were removed 2026-04-21 — they
were implementation-detail assertions and had drifted from the actual
source as the code evolved. The behavior they were guarding is now
covered by the Jarvis-loop exercise in test_fix2_and_fix3.

All tests are deterministic (no LoRA, no real pipeline, no DB).
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Test-only owner identifier. Prefer a real id from the environment when
# this file runs in the owner's dev loop; otherwise fall back to a stable
# sentinel. These tests never cross-check the value, so any int works.
# Keeping the real id out of source prevents the placeholder-never-filled-in
# bug that previously left this file unparseable (SyntaxError on bare `<OWNER_TELEGRAM_ID>`).
_OWNER_TELEGRAM_ID = int(os.environ.get("OWNER_TELEGRAM_ID", "1"))


class Fix1LogsIntentTightening(unittest.TestCase):

    def test_what_happened_does_not_match_logs_intent(self):
        from skills.telegram_voice import _match_intent, MACHINE_INTENTS

        self.assertIsNone(
            _match_intent("what happened?"),
            "'what happened?' should NOT match any machine intent",
        )
        self.assertIsNone(_match_intent("What happened"))
        self.assertIsNone(_match_intent("what happened after the recovery?"))

        # Regression: legitimate log queries still route correctly.
        self.assertEqual(_match_intent("show logs"), "logs")
        self.assertEqual(_match_intent("check logs"), "logs")
        self.assertEqual(_match_intent("any errors in the logs?"), "logs")
        self.assertEqual(_match_intent("tail logs"), "logs")

        for phrase in MACHINE_INTENTS["logs"]:
            self.assertNotIn(
                "what happened", phrase,
                f"'logs' intent still contains dangerous phrase: {phrase!r}",
            )


class Fix2And3RecoveryCardDiscipline(unittest.TestCase):
    """One end-to-end exercise of _run_jarvis_loop with a recovery_seed
    observes both Fix 2 (reason propagation) and Fix 3 (single-card-
    per-pass) via mock_pipe's call record."""

    def test_reason_propagated_and_single_card_created(self):
        from skills import telegram_voice as tv_mod
        from core.decision_pipeline import PipelineStatus

        pending_result = types.SimpleNamespace(
            status=PipelineStatus.PENDING_APPROVAL,
            message="card created",
            execution_output=None,
            execution_success=None,
            execution_error=None,
        )

        mock_pipe = MagicMock()
        mock_pipe.handle_action.return_value = pending_result

        # Mock LLM emits a Lane 2 TOOL_CALL every iteration. Without Fix 3,
        # handle_action would be called max_iters times; with Fix 3, once.
        def fake_chat(*args, **kwargs):
            resp = types.SimpleNamespace()
            resp.message = types.SimpleNamespace(
                content='TOOL_CALL: {"action": "run_shell", "params": {"cmd": "apt-get install -y openrgb"}}'
            )
            return resp

        skill = tv_mod.TelegramVoice.__new__(tv_mod.TelegramVoice)
        skill.actions = MagicMock()
        skill.authorized_user = _OWNER_TELEGRAM_ID
        skill._get_pipeline = MagicMock(return_value=mock_pipe)

        recovery_seed = {
            "failed_action": "run_shell",
            "failed_params": {"cmd": "apt-get install openrgb"},
            "error": "exit=100 stderr=E: Unable to locate package openrgb",
            "original_intent": "install openrgb to control keyboard lighting",
            "recovery_depth": 1,
            "prior_attempts": [],
        }

        from core import llm_client as core_llm_client

        with patch.object(core_llm_client, "chat", fake_chat):
            try:
                skill._run_jarvis_loop(
                    user_text="",
                    max_iters=4,
                    recovery_seed=recovery_seed,
                )
            except Exception:
                # The loop may hit a mocked-out attribute after the card
                # is created — fine, assertions below read from mock_pipe.
                pass

        # Fix 2: reason propagated from recovery_seed
        self.assertTrue(
            mock_pipe.handle_action.called,
            "pipe.handle_action was never called — test setup broken",
        )
        first_call = mock_pipe.handle_action.call_args_list[0]
        reason = first_call.kwargs.get("reason")
        self.assertIsNotNone(reason, "reason kwarg missing from handle_action call")
        self.assertTrue(
            reason.startswith("recovery:"),
            f"Fix 2 broken — reason should start with 'recovery:', got {reason!r}",
        )
        self.assertIn(
            "install openrgb", reason,
            f"Fix 2 broken — original_intent not propagated, got {reason!r}",
        )
        self.assertFalse(
            reason.startswith("chat: "),
            f"Fix 2 broken — stale 'chat: ' prefix still present, got {reason!r}",
        )

        # Fix 3: exactly one handle_action call (single-card-per-pass)
        self.assertEqual(
            mock_pipe.handle_action.call_count, 1,
            "Fix 3 broken — expected exactly 1 handle_action call "
            "(single-card-per-pass); each extra call is an orphan card.",
        )


if __name__ == "__main__":
    unittest.main()
