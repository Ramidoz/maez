# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Smoke tests for core.brain_loop.

Locks in the extracted signature + helper surface. The loop itself
talks to an LLM (`llm_client.chat`) which is a heavy integration
surface; these tests exercise the cheap paths that don't require an
LLM: conversational-gate early-return, missing-action-engine early-
return, and the tool-call parser.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.brain_loop import (
    run_brain_loop,
    _should_run_jarvis_loop,
    _parse_tool_call,
    _extract_balanced_json,
    _TOOL_MANIFEST,
)


class PublicSurface(unittest.TestCase):
    def test_imports_and_signature(self):
        import inspect
        sig = inspect.signature(run_brain_loop)
        # Required param
        self.assertIn("user_text", sig.parameters)
        # Keyword-only
        self.assertIn("action_engine", sig.parameters)
        self.assertIn("get_pipeline", sig.parameters)
        self.assertIn("user_id", sig.parameters)
        self.assertIn("chat_id", sig.parameters)
        self.assertIn("send_intermediate", sig.parameters)

    def test_tool_manifest_nonempty(self):
        self.assertGreater(len(_TOOL_MANIFEST), 500)


class ConversationalGate(unittest.TestCase):
    def test_greetings_skip_loop(self):
        for text in ("hi", "hello", "thanks", "lol", "hi maez", "gn",
                     "ok", "yeah"):
            self.assertFalse(_should_run_jarvis_loop(text),
                f"expected conversational skip: {text!r}")

    def test_content_questions_run_loop(self):
        for text in ("check disk usage", "what services are running",
                     "tell me the uptime", "is maez running"):
            self.assertTrue(_should_run_jarvis_loop(text),
                f"expected loop to run: {text!r}")


class EarlyReturns(unittest.TestCase):
    def test_no_action_engine_returns_empty(self):
        result = run_brain_loop(
            "check the disk",
            action_engine=None,
            get_pipeline=lambda: None,
        )
        self.assertEqual(result, "")

    def test_conversational_returns_empty(self):
        result = run_brain_loop(
            "hi",
            action_engine=object(),
            get_pipeline=lambda: None,
        )
        self.assertEqual(result, "")


class ToolCallParser(unittest.TestCase):
    def test_tool_call_literal_form(self):
        call = _parse_tool_call(
            'TOOL_CALL: {"action":"run_shell","params":{"cmd":"ls"}}'
        )
        self.assertIsNotNone(call)
        self.assertEqual(call["action"], "run_shell")
        self.assertEqual(call["params"]["cmd"], "ls")

    def test_function_call_form(self):
        call = _parse_tool_call('query_system({"cmd":"uptime"})')
        self.assertIsNotNone(call)
        self.assertEqual(call["action"], "query_system")
        self.assertEqual(call["params"]["cmd"], "uptime")

    def test_bare_text_returns_none(self):
        self.assertIsNone(_parse_tool_call("I'll check that"))
        self.assertIsNone(_parse_tool_call(""))

    def test_balanced_json_extraction(self):
        s = '{"a": {"b": "c"}, "d": 1}'
        self.assertEqual(_extract_balanced_json(s), s)

    def test_balanced_json_with_strings_containing_braces(self):
        s = '{"msg": "{not json}"}'
        self.assertEqual(_extract_balanced_json(s), s)


class ChatHistoryPrompting(unittest.TestCase):
    """The RECENT CONVERSATION block is what disambiguates "what did
    you find?" from a bare question. These tests verify it reaches the
    planning LLM.

    Observed 2026-04-20: user said "Take a look at
    https://github.com/obra/superpowers" → Maez cloned it. One minute
    later "What did you find?" → Maez drifted to hardware probing
    (ls /sys/class/leds && lsusb && cat /sys/class/dmi/id/product_name)
    because the planner's prompt contained zero signal about the clone.
    """

    def _capture_first_prompt(self, user_text, chat_history):
        """Run run_brain_loop with a stub LLM that captures the prompt
        and returns DONE immediately. Returns the user-role content of
        the first call."""
        from core import brain_loop

        captured = {}

        def fake_chat(*args, **kwargs):
            messages = kwargs.get("messages", args[0] if args else [])
            if "user_content" not in captured:
                for m in messages:
                    if m.get("role") == "user":
                        captured["user_content"] = m["content"]
                        break
            resp = MagicMock()
            resp.message.content = "DONE"
            return resp

        fake_action_engine = MagicMock()
        fake_get_pipeline = MagicMock()

        with patch("core.brain_loop._llm_client.chat", side_effect=fake_chat):
            brain_loop.run_brain_loop(
                user_text,
                action_engine=fake_action_engine,
                get_pipeline=fake_get_pipeline,
                chat_history=chat_history,
            )

        return captured.get("user_content", "")

    def test_history_block_included_when_provided(self):
        history = [
            {"content": "rohit: Take a look at https://github.com/obra/superpowers\n"
                        "maez: I've proposed cloning the repo to /home/rohit/maez/superpowers — waiting for your go-ahead.",
             "metadata": {"timestamp": "2026-04-20T20:11:28"}},
            {"content": "rohit: Yes\n"
                        "maez: Ran `git clone https://github.com/obra/superpowers /home/rohit/maez/superpowers`. Cloning into '/home/rohit/maez/superpowers'...",
             "metadata": {"timestamp": "2026-04-20T20:11:35"}},
        ]
        prompt = self._capture_first_prompt("What did you find?", history)
        self.assertIn("RECENT CONVERSATION", prompt,
                      f"expected conversation header in prompt; got: {prompt[:400]!r}")
        self.assertIn("superpowers", prompt,
                      f"expected 'superpowers' from history in prompt; got: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt,
                      f"expected current user text in prompt; got: {prompt[:400]!r}")
        self.assertIn("--- end exchange", prompt,
                      f"expected per-exchange closing delimiter in prompt; got: {prompt[:400]!r}")

    def test_long_exchange_content_is_truncated(self):
        tail_marker = "TAIL_SENTINEL_SHOULD_NOT_APPEAR"
        long_content = ("x" * 5000) + tail_marker
        history = [{"content": long_content, "metadata": {}}]
        prompt = self._capture_first_prompt("What did you find?", history)
        self.assertIn("…[truncated]", prompt,
                      f"expected truncation marker; got: {prompt[:400]!r}")
        self.assertNotIn(tail_marker, prompt,
                         "original tail should have been truncated away")

    def test_none_history_preserves_legacy_shape(self):
        prompt = self._capture_first_prompt("What did you find?", None)
        self.assertNotIn("RECENT CONVERSATION", prompt,
                         f"unexpected conversation header for None history: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt)

    def test_empty_history_preserves_legacy_shape(self):
        prompt = self._capture_first_prompt("What did you find?", [])
        self.assertNotIn("RECENT CONVERSATION", prompt,
                         f"unexpected conversation header for empty list: {prompt[:400]!r}")
        self.assertIn("What did you find?", prompt)


class AdapterPassesChatHistory(unittest.TestCase):
    """The surface adapter must actually fetch recent exchanges from
    the daemon's memory manager and pass them into run_brain_loop.
    Without this wiring, Task 1's fix is inert."""

    def test_adapter_fetches_exchanges_and_passes_to_brain_loop(self):
        import asyncio
        from skills.surface import maez_adapter

        fake_exchanges = [
            {"content": "rohit: clone X\nmaez: cloned",
             "metadata": {"timestamp": "2026-04-20T20:11:00"}},
            {"content": "rohit: what did you find?\nmaez: ...",
             "metadata": {"timestamp": "2026-04-20T20:12:00"}},
        ]

        class FakeMemory:
            def __init__(self):
                self.last_limit = None

            def get_telegram_exchanges(self, limit=None):
                self.last_limit = limit
                return fake_exchanges

        class FakeDaemon:
            def __init__(self):
                self.memory = FakeMemory()
                self.actions = MagicMock()
                self.telegram = MagicMock()
                self.telegram._get_pipeline = MagicMock(
                    return_value=MagicMock()
                )
                self.handle_message = MagicMock(return_value="ok")
                self._surface_v2_adapter = None
                self._surface_v2_loop = None

        captured_kwargs = {}

        def fake_run_brain_loop(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return ""

        daemon = FakeDaemon()
        handler = maez_adapter.MaezMessageHandler(daemon)

        event = MagicMock()
        event.text = "What did you find?"
        event.source = MagicMock()
        event.source.chat_id = "12345"
        event.reply_to_message_id = None

        pipe = daemon.telegram._get_pipeline.return_value
        pipe.card_store = MagicMock()
        pipe.card_store.get_open_for_channel = MagicMock(return_value=[])

        with patch("core.brain_loop.run_brain_loop",
                   side_effect=fake_run_brain_loop):
            asyncio.run(handler(event))

        self.assertIn("chat_history", captured_kwargs,
                      "adapter did not pass chat_history kwarg to run_brain_loop")
        self.assertEqual(captured_kwargs["chat_history"], fake_exchanges,
                         "adapter passed wrong value for chat_history")
        self.assertIsNotNone(daemon.memory.last_limit,
                             "adapter did not specify a limit on get_telegram_exchanges")
        self.assertLessEqual(daemon.memory.last_limit, 10,
                             f"adapter used too-large limit: {daemon.memory.last_limit}")

    def test_adapter_falls_open_when_memory_unavailable(self):
        """If daemon.memory is None (startup race or non-daemon caller),
        the adapter must still process the turn — chat_history is just
        passed through as None."""
        import asyncio
        from skills.surface import maez_adapter

        class FakeDaemon:
            def __init__(self):
                self.memory = None  # the condition under test
                self.actions = MagicMock()
                self.telegram = MagicMock()
                self.telegram._get_pipeline = MagicMock(
                    return_value=MagicMock()
                )
                self.handle_message = MagicMock(return_value="ok")
                self._surface_v2_adapter = None
                self._surface_v2_loop = None

        captured_kwargs = {}

        def fake_run_brain_loop(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return ""

        daemon = FakeDaemon()
        handler = maez_adapter.MaezMessageHandler(daemon)

        event = MagicMock()
        event.text = "anything"
        event.source = MagicMock()
        event.source.chat_id = "12345"
        event.reply_to_message_id = None

        pipe = daemon.telegram._get_pipeline.return_value
        pipe.card_store = MagicMock()
        pipe.card_store.get_open_for_channel = MagicMock(return_value=[])

        with patch("core.brain_loop.run_brain_loop",
                   side_effect=fake_run_brain_loop):
            asyncio.run(handler(event))

        self.assertIn("chat_history", captured_kwargs,
                      "adapter must still pass chat_history kwarg")
        self.assertIsNone(captured_kwargs["chat_history"],
                          f"expected None when memory is absent, got: "
                          f"{captured_kwargs['chat_history']!r}")


if __name__ == "__main__":
    unittest.main()
