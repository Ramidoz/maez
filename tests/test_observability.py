# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.observability — the Langfuse-wrapping abstraction
that gives every Telegram turn a hierarchical trace viewable in a real
UI instead of 30KB of journalctl output.

Core design constraint: code MUST load and run with no Langfuse env
vars set, because the daemon defaults are 'observability off'. Turning
it on is a user action (signup + env vars + restart)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch, MagicMock


class ObserveTurnNoOpWhenEnvMissing(unittest.TestCase):
    """When LANGFUSE_PUBLIC_KEY is not set, observe_turn returns a
    no-op context that accepts all the same calls but does nothing.
    This is the default state for anyone who hasn't signed up."""

    def test_observe_turn_is_noop_without_env(self):
        from core import observability
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            # Clear any cached client so the env change takes effect
            observability._client_cache.clear()
            with observability.observe_turn(
                "test_turn", input={"text": "hi"}, metadata={"x": 1}
            ) as turn:
                turn.llm_call(
                    name="planner", model="fake-model",
                    input=[{"role": "user", "content": "hi"}],
                    output="DONE",
                )
                turn.tool_call(
                    name="run_shell",
                    params={"cmd": "ls"},
                    output="file1\nfile2",
                    ok=True,
                )
                turn.event("something_happened", {"k": "v"})
                turn.update(output="final reply")

    def test_noop_turn_safe_for_nested_calls(self):
        from core import observability
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        os.environ.pop("LANGFUSE_SECRET_KEY", None)
        observability._client_cache.clear()
        with observability.observe_turn("loop", input={}) as turn:
            for i in range(10):
                turn.llm_call(
                    name=f"iter_{i}", model="x",
                    input=[], output="",
                )
                turn.tool_call(
                    name="t", params={}, output="", ok=True,
                )


class ObserveTurnActiveWhenEnvPresent(unittest.TestCase):
    """Langfuse v4+ API: `client.start_observation(as_type="agent", ...)`
    creates the root observation; child observations come from the
    root span's own `start_observation(as_type=...)`. No `trace()`
    method exists in v4."""

    def test_env_present_creates_root_and_children(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "https://cloud.langfuse.com",
        }

        fake_client = MagicMock()
        fake_root = MagicMock()
        fake_client.start_observation.return_value = fake_root

        observability._client_cache.clear()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            with observability.observe_turn(
                "test", input={"q": "x"}, metadata={"u": "rohit"}
            ) as turn:
                turn.llm_call(
                    name="planner", model="gemma-4-26b",
                    input=[{"role": "user", "content": "x"}],
                    output="DONE",
                )
                turn.tool_call(
                    name="run_shell",
                    params={"cmd": "ls"},
                    output="out", ok=True,
                )
                turn.update(output="reply")

        # Root observation created once, as_type="agent":
        fake_client.start_observation.assert_called_once()
        root_call = fake_client.start_observation.call_args
        self.assertEqual(root_call.kwargs.get("as_type"), "agent")
        self.assertEqual(root_call.kwargs.get("name"), "test")

        # Children observations created on the root (not the client):
        child_calls = fake_root.start_observation.call_args_list
        as_types = [c.kwargs.get("as_type") for c in child_calls]
        self.assertIn("generation", as_types,
                      f"expected a 'generation' child for llm_call; got {as_types}")
        self.assertIn("tool", as_types,
                      f"expected a 'tool' child for tool_call; got {as_types}")
        # update routed to root.update():
        self.assertTrue(fake_root.update.called,
                        "expected root.update() to be called for turn.update")


class ObserveTurnSwallowsSdkErrors(unittest.TestCase):
    def test_sdk_raise_does_not_propagate(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        }

        fake_client = MagicMock()
        fake_client.start_observation.side_effect = RuntimeError("network blip")

        observability._client_cache.clear()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            # Root obs fails → we get a _NoopTurn → child calls are noop.
            with observability.observe_turn("test", input={}) as turn:
                turn.llm_call(name="x", model="y", input=[], output="")
                turn.tool_call(name="t", params={}, output="", ok=True)

    def test_child_observation_raise_does_not_propagate(self):
        """Even if child observation creation raises (e.g. OTel span
        rejected mid-turn), the turn must keep working silently."""
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        }

        fake_client = MagicMock()
        fake_root = MagicMock()
        fake_root.start_observation.side_effect = RuntimeError("child failed")
        fake_client.start_observation.return_value = fake_root

        observability._client_cache.clear()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            with observability.observe_turn("test", input={}) as turn:
                turn.llm_call(name="x", model="y", input=[], output="")
                turn.tool_call(name="t", params={}, output="", ok=True)
                turn.event("happened", {"k": "v"})


class BrainLoopAcceptsTurnKwarg(unittest.TestCase):
    """run_brain_loop must accept an optional `turn` kwarg and forward
    llm + tool-call events into it. Without this wiring, Task 1's
    abstraction is inert."""

    def test_brain_loop_calls_llm_call_and_tool_call(self):
        """Smoke: planner emits TOOL_CALL once, tool runs, planner
        emits DONE. We expect:
          - 1+ llm_call invocations on the turn
          - 1+ tool_call invocations on the turn
        """
        from core import brain_loop

        recorded = {"llm_calls": [], "tool_calls": []}

        class FakeTurn:
            def llm_call(self, **kwargs):
                recorded["llm_calls"].append(kwargs)

            def tool_call(self, **kwargs):
                recorded["tool_calls"].append(kwargs)

            def event(self, *a, **k):
                pass

            def update(self, **k):
                pass

        responses = iter([
            'TOOL_CALL: {"action":"run_shell","params":'
            '{"cmd":"echo hi","reason":"greet"}}',
            "DONE",
        ])

        def fake_chat(*args, **kwargs):
            resp = MagicMock()
            resp.message.content = next(responses)
            return resp

        fake_engine = MagicMock()
        fake_pipeline = MagicMock()
        fake_pipeline.handle_action = MagicMock(
            return_value=MagicMock(
                status=MagicMock(value="executed"),
                message="hi",
                card=None,
            )
        )

        with patch("core.brain_loop._llm_client.chat",
                   side_effect=fake_chat):
            brain_loop.run_brain_loop(
                "say hi",
                action_engine=fake_engine,
                get_pipeline=lambda: fake_pipeline,
                turn=FakeTurn(),
            )

        self.assertGreaterEqual(
            len(recorded["llm_calls"]), 1,
            f"expected at least one llm_call; got {recorded['llm_calls']!r}"
        )
        self.assertGreaterEqual(
            len(recorded["tool_calls"]), 1,
            f"expected at least one tool_call; got {recorded['tool_calls']!r}"
        )

    def test_brain_loop_turn_none_is_safe(self):
        """Without a turn kwarg, brain_loop must default to a no-op
        and NOT crash. This is the default path for callers that
        haven't adopted observability yet."""
        from core import brain_loop

        def fake_chat(*args, **kwargs):
            resp = MagicMock()
            resp.message.content = "DONE"
            return resp

        fake_engine = MagicMock()
        fake_pipeline = MagicMock()

        with patch("core.brain_loop._llm_client.chat",
                   side_effect=fake_chat):
            # turn=None (default) must not raise.
            brain_loop.run_brain_loop(
                "say hi",
                action_engine=fake_engine,
                get_pipeline=lambda: fake_pipeline,
            )


if __name__ == "__main__":
    unittest.main()
