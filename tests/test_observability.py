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
    def test_env_present_creates_trace(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "https://cloud.langfuse.com",
        }

        fake_client = MagicMock()
        fake_trace = MagicMock()
        fake_client.trace.return_value = fake_trace

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

        fake_client.trace.assert_called_once()
        call = fake_client.trace.call_args
        self.assertEqual(call.kwargs.get("name"), "test")
        self.assertTrue(fake_trace.generation.called,
                        "expected trace.generation() to be called for llm_call")
        self.assertTrue(fake_trace.span.called,
                        "expected trace.span() to be called for tool_call")


class ObserveTurnSwallowsSdkErrors(unittest.TestCase):
    def test_sdk_raise_does_not_propagate(self):
        from core import observability

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        }

        fake_client = MagicMock()
        fake_client.trace.side_effect = RuntimeError("network blip")

        observability._client_cache.clear()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(observability, "_get_client",
                          return_value=fake_client):
            with observability.observe_turn("test", input={}) as turn:
                turn.llm_call(name="x", model="y", input=[], output="")
                turn.tool_call(name="t", params={}, output="", ok=True)


if __name__ == "__main__":
    unittest.main()
