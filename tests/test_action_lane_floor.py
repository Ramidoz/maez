"""Phase 2 commit C: deterministic-fact reflex + syntactic floor.
Gate fixtures F1-F4 verbatim; RED 3-precursor (intent reaches the
carrier); pre-dispatch bypass witness."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from core.brain.brain_loop import (
    _action_intent_syntactic_floor as floor,
    _deterministic_fact_candidate as det,
)

_ON = {"MAEZ_ACTION_LANE_ENABLED": "1", "MAEZ_ACTION_LANE_SHADOW": ""}


class FixtureTests(unittest.TestCase):
    def test_f1_negation_contrast(self):
        self.assertEqual(floor("Don't execute it — just propose it."), "none")

    def test_f2_idiom_cancellation(self):
        self.assertEqual(floor("Nah forget about that. How you been?"), "none")

    def test_f3_greeting_with_action_laden_history(self):
        # History NEVER creates intent: the floor sees only the turn.
        self.assertEqual(floor("Heyy maez!"), "none")

    def test_f4_mixed_emotional_stock_keeps_dispatcher(self):
        self.assertFalse(
            det("I feel anxious about Nvidia stock today; check the latest price")
        )

    def test_fabrication_night_positives(self):
        self.assertEqual(
            floor("Maez, please create a new file at docs/governance/x.md "
                  "with a one-line note"),
            "explicit_request",
        )
        self.assertEqual(
            floor("Yes — go ahead and create that file now. You have my "
                  "authorization."),
            "explicit_request",
        )

    def test_exclusions(self):
        for t in (
            "How do I create a new branch?",
            "What if you delete the wrong file?",
            'He said "run the tests" yesterday',
            "Can you explain what install does?",
        ):
            self.assertEqual(floor(t), "none", t)

    def test_deterministic_pinned_forms(self):
        self.assertTrue(det("What is the current INR to USD exchange rate?"))
        self.assertTrue(det("What is the SRXH stock price today?"))
        self.assertFalse(det("Tell me a story about the stock market"))


class WiringTests(unittest.TestCase):
    def test_intent_reaches_carrier_under_flag(self):
        # The dispatcher's normal construction derives True for an
        # explicit request with the flag on -- the nerve's first spark.
        from core.brain.brain_loop import make_dispatcher_result

        with mock.patch.dict(os.environ, _ON):
            r = make_dispatcher_result(
                transcript="x",
                action_intent=floor(
                    "Maez, please create a new file at docs/notes.md now"
                ),
            )
        self.assertTrue(r.should_run_jarvis)

    def test_pre_dispatch_branch_skips_dispatcher(self):
        # Deterministic-fact turn: _run_dispatcher_pipeline must NOT be
        # called even with the triad on (RED: remove the branch and
        # this fails).
        from core.brain import brain_loop as bl

        with mock.patch.object(
            bl, "_run_dispatcher_pipeline",
            side_effect=AssertionError("dispatcher must not run"),
        ), mock.patch.object(bl, "_dispatcher_enabled", return_value=True), \
             mock.patch.object(bl, "_should_run_jarvis_loop", return_value=False):
            out = bl.run_brain_loop(
                "What is the current INR to USD exchange rate?",
                action_engine=None,  # no engine -> empty early return AFTER routing
                get_pipeline=None,
                surface="telegram_surface",
            )
        self.assertEqual(out, "")

    def test_ordinary_turn_still_enters_dispatcher(self):
        from core.brain import brain_loop as bl

        called = {"n": 0}

        def _fake_pipeline(**kw):
            called["n"] += 1
            return bl._DispatcherPathResult(transcript="t")

        with mock.patch.object(
            bl, "_run_dispatcher_pipeline", side_effect=_fake_pipeline
        ), mock.patch.object(bl, "_dispatcher_enabled", return_value=True):
            bl.run_brain_loop(
                "Tell me something nice about gardens",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
            )
        self.assertEqual(called["n"], 1)


if __name__ == "__main__":
    unittest.main()
