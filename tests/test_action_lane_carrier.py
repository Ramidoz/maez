"""Phase 2 commit B: the typed carrier. RED set 1, 2, and 6 (partial)
from the gate-approved design, plus carrier-invariant pins."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from core.brain.brain_loop import (
    _ACTION_INTENTS,
    _DispatcherPathResult,
    make_dispatcher_result,
)

_ON = {"MAEZ_ACTION_LANE_ENABLED": "1", "MAEZ_ACTION_LANE_SHADOW": ""}
_OFF = {"MAEZ_ACTION_LANE_ENABLED": "", "MAEZ_ACTION_LANE_SHADOW": ""}


class CarrierTests(unittest.TestCase):
    def test_derivation_truth_table(self):
        # RED 1: explicit intent + flag snapshot -> True; all else False.
        for intent in _ACTION_INTENTS:
            for snap in (True, False):
                r = _DispatcherPathResult(
                    action_intent=intent, action_lane_enabled_snapshot=snap
                )
                expected = intent == "explicit_request" and snap
                self.assertEqual(r.should_run_jarvis, expected)

    def test_disagreement_is_structurally_impossible(self):
        # No constructor path can set should_run_jarvis independently.
        with self.assertRaises(TypeError):
            _DispatcherPathResult(should_run_jarvis=True)  # type: ignore

    def test_invalid_intent_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            _DispatcherPathResult(action_intent="do_crimes")

    def test_factory_snapshots_flag_on(self):
        with mock.patch.dict(os.environ, _ON):
            r = make_dispatcher_result(action_intent="explicit_request")
        self.assertTrue(r.action_lane_enabled_snapshot)
        self.assertTrue(r.should_run_jarvis)
        # snapshot is frozen: flipping env later changes nothing
        with mock.patch.dict(os.environ, _OFF):
            self.assertTrue(r.should_run_jarvis)

    def test_factory_snapshots_flag_off(self):
        # RED 6 (carrier half): flags off -> derivation False even for
        # explicit intent; defaults byte-identical to pre-phase2.
        with mock.patch.dict(os.environ, _OFF):
            r = make_dispatcher_result(action_intent="explicit_request")
        self.assertFalse(r.should_run_jarvis)
        d = make_dispatcher_result()
        self.assertEqual(
            (d.transcript, d.recall_items, d.action_intent,
             d.should_run_jarvis),
            ("", (), "none", False),
        )

    def test_repair_refusal_site_suppresses_continuation(self):
        # RED 2: the refusal constructor in production carries intent
        # none -- verified via AST (the site must call the factory with
        # action_intent="none" and empty transcript).
        import ast
        from pathlib import Path

        src = Path("core/brain/brain_loop.py").read_text()
        self.assertIn(
            'make_dispatcher_result(transcript="", action_intent="none")',
            src,
        )
        # and exactly two production factory callsites exist
        tree = ast.parse(src)
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "make_dispatcher_result"
        ]
        self.assertEqual(len(calls), 2)

    def test_shadow_flag_alone_does_not_derive_true(self):
        env = {"MAEZ_ACTION_LANE_SHADOW": "1", "MAEZ_ACTION_LANE_ENABLED": ""}
        with mock.patch.dict(os.environ, env):
            r = make_dispatcher_result(action_intent="explicit_request")
        self.assertFalse(r.should_run_jarvis)  # shadow observes, never acts


if __name__ == "__main__":
    unittest.main()
