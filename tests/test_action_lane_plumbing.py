"""Phase 2 commit F: plumbing pins — kill-switch guard, web bridge
fields, continuation survival (RED 3-5), flag registry."""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
_ON = {"MAEZ_ACTION_LANE_ENABLED": "1", "MAEZ_ACTION_LANE_SHADOW": ""}


class KillSwitchGuardTests(unittest.TestCase):
    def test_kill_switch_path_can_never_produce_combined_mode(self):
        # Gate P2 ruling: the non-structured rollback path
        # (telegram_voice._run_jarvis_loop) returns a plain string and
        # must never call run_brain_loop with return_structured=True.
        src = (_REPO / "skills" / "telegram_voice.py").read_text()
        tree = ast.parse(src)
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_run_jarvis_loop"
        )
        # AST-hardened (round-1 blocker 7): inspect the actual call
        # keywords -- ANY return_structured kwarg (whatever its value
        # or spelling of truthiness) and any **kwargs splat are
        # forbidden on this rollback path.
        calls = [
            n for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and (
                getattr(n.func, "attr", "") == "run_brain_loop"
                or getattr(n.func, "id", "") == "run_brain_loop"
            )
        ]
        self.assertTrue(calls, "kill-switch path must still call run_brain_loop")
        for call in calls:
            kw_names = [k.arg for k in call.keywords]
            self.assertNotIn("return_structured", kw_names)
            self.assertNotIn(None, kw_names)  # no **kwargs splat
        fn_src = ast.get_source_segment(src, fn) or ""
        self.assertNotIn("combined_mode", fn_src)


class WebBridgeTests(unittest.TestCase):
    def test_bridge_json_carries_combined_fields(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        self.assertIn('"dispatcher_transcript": getattr(', src)
        self.assertIn('"combined_mode": bool(', src)

    def test_web_consumer_selects_by_flag_not_marker(self):
        src = (_REPO / "skills" / "web_interface.py").read_text()
        self.assertIn("_web_combined and _web_dispatcher_ctx", src)


class ContinuationTests(unittest.TestCase):
    """RED 3-5: the rejoined nerve, witnessed through run_brain_loop."""

    def _run(self, intent_env, transcript="recall block"):
        from types import SimpleNamespace

        from core.brain import brain_loop as bl

        def _fake_pipeline(**kw):
            return bl.make_dispatcher_result(
                transcript=transcript,
                action_intent="explicit_request",
                recall_items=("r1",),
            )

        planner = {"messages": None}

        def _fake_chat(**kw):
            planner["messages"] = kw.get("messages")
            # planner emits no TOOL_CALL -> loop ends cleanly
            return SimpleNamespace(
                message=SimpleNamespace(content="NO_TOOL_NEEDED")
            )

        with mock.patch.dict(os.environ, intent_env), mock.patch.object(
            bl, "_run_dispatcher_pipeline", side_effect=_fake_pipeline
        ), mock.patch.object(
            bl, "_dispatcher_enabled", return_value=True
        ), mock.patch.object(bl._llm_client, "chat", side_effect=_fake_chat):
            out = bl.run_brain_loop(
                "please create the file we discussed",
                action_engine=object(),  # truthy: past the engine guard
                get_pipeline=lambda: None,
                surface="telegram_surface",
                return_structured=True,
            )
        return out, planner

    def test_red3_red4_continues_and_context_survives(self):
        # ENABLED: derivation True -> the early return must NOT fire;
        # the planner runs (witnessed) with the dispatcher context as
        # its own labeled block, and the final result carries the
        # combined state + dispatcher recall_items (RED 4).
        out, planner = self._run(_ON)
        self.assertTrue(out.combined_mode)
        self.assertEqual(out.dispatcher_transcript, "recall block")
        self.assertEqual(out.recall_items, ("r1",))
        self.assertIsNotNone(planner["messages"])  # jarvis planner ran
        joined = "\n".join(
            str(m.get("content", "")) for m in planner["messages"]
        )
        self.assertIn("DISPATCHER RECALL CONTEXT", joined)
        self.assertIn("recall block", joined)

    def test_red5_flag_off_restores_early_return(self):
        env = {"MAEZ_ACTION_LANE_ENABLED": "", "MAEZ_ACTION_LANE_SHADOW": ""}
        out, planner = self._run(env)
        # derivation False -> dispatcher transcript returned as today,
        # and the jarvis planner never ran.
        self.assertEqual(out.transcript, "recall block")
        self.assertEqual(out.recall_items, ("r1",))
        self.assertFalse(out.combined_mode)
        self.assertIsNone(planner["messages"])


class FlagRegistryTests(unittest.TestCase):
    def test_action_lane_flags_registered(self):
        from core.cockpit.flags import default_registry

        reg = default_registry()
        self.assertEqual(reg["MAEZ_ACTION_LANE_SHADOW"].tier, "T1")
        self.assertEqual(reg["MAEZ_ACTION_LANE_ENABLED"].tier, "T2")
        for name in ("MAEZ_ACTION_LANE_SHADOW", "MAEZ_ACTION_LANE_ENABLED"):
            self.assertTrue(reg[name].witness_recipe)


if __name__ == "__main__":
    unittest.main()
