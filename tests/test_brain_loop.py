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

import os
import unittest
from types import SimpleNamespace
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
        self.assertIn("surface", sig.parameters)

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
                     "tell me the uptime", "is maez running",
                     "What is the current price?"):
            self.assertTrue(_should_run_jarvis_loop(text),
                f"expected loop to run: {text!r}")

    def test_volatile_numeric_questions_run_loop(self):
        for text in (
            "What's Rs.2,00,000 in USD?",
            "What is the current INR to USD exchange rate?",
            "Convert ₹200000 to USD today",
            "What is 300 euros in usd?",
            "What is €300 in dollars?",
            "Convert 20 pounds to yen",
            "Look up the price of SRXH",
            "What is the SRXH stock price today?",
        ):
            self.assertTrue(_should_run_jarvis_loop(text),
                f"expected live-data loop to run: {text!r}")


class EarlyReturns(unittest.TestCase):
    def test_no_action_engine_returns_empty(self):
        result = run_brain_loop(
            "check the disk",
            action_engine=None,
            get_pipeline=lambda: None,
        )
        self.assertEqual(result, "")


class DispatcherWiring(unittest.TestCase):
    def test_dispatcher_enabled_path_replaces_jarvis_gate(self):
        from core import brain_loop

        with (
            patch.dict(os.environ, {"MAEZ_DISPATCHER_ENABLED": "1"}),
            patch.object(
                brain_loop,
                "_should_run_jarvis_loop",
                side_effect=AssertionError("JARVIS gate should not run"),
            ),
            patch.object(
                brain_loop,
                "_run_dispatcher_pipeline",
                return_value=brain_loop._DispatcherPathResult(
                    transcript="DISPATCHER TRANSCRIPT",
                    should_run_jarvis=False,
                ),
            ) as dispatcher,
        ):
            result = run_brain_loop(
                "Check Reddit then",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram",
            )

        self.assertEqual(result, "DISPATCHER TRANSCRIPT")
        dispatcher.assert_called_once()
        self.assertEqual(dispatcher.call_args.kwargs["surface"], "telegram")

    def test_dispatcher_disabled_uses_existing_jarvis_gate(self):
        from core import brain_loop

        with (
            patch.dict(os.environ, {"MAEZ_DISPATCHER_ENABLED": "0"}),
            patch.object(brain_loop, "_should_run_jarvis_loop", return_value=False) as gate,
            patch.object(
                brain_loop,
                "_run_dispatcher_pipeline",
                side_effect=AssertionError("dispatcher path should not run"),
            ),
        ):
            result = run_brain_loop(
                "Check Reddit then",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram",
            )

        self.assertEqual(result, "")
        gate.assert_called_once_with("Check Reddit then")

    def test_reddit_adapter_reads_source_rows_without_full_prompt_format(self):
        from core import brain_loop
        from core.dispatcher.spec import SubstrateSource

        class FakeMemoryManager:
            raw = object()

            def _recent_reddit_source_rows(self, collection, query, *, limit=5):
                self.collection = collection
                self.query = query
                self.limit = limit
                return [
                    {
                        "content": "x" * 5000,
                        "metadata": {
                            "source": "reddit/r/LocalLLaMA",
                            "timestamp": "2026-05-27T15:28:41+00:00",
                            "reddit_score": 42,
                            "reddit_comments": 7,
                        },
                    }
                ]

            def recall_for_telegram(self, query):
                raise AssertionError("REDDIT_SOURCE adapter must not run full recall")

            def format_for_prompt(self, recalled, max_chars):
                raise AssertionError("REDDIT_SOURCE adapter must not format full prompt")

            def close(self):
                pass

        with patch("memory.memory_manager.MemoryManager", FakeMemoryManager):
            adapter = brain_loop._dispatcher_recall_adapters("Check Reddit then")[
                SubstrateSource.REDDIT_SOURCE
            ]
            blocks = adapter(SubstrateSource.REDDIT_SOURCE)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].source, SubstrateSource.REDDIT_SOURCE)
        self.assertLessEqual(len(blocks[0].text), 1200)
        self.assertIn("reddit/r/LocalLLaMA", blocks[0].text)

    def test_dispatcher_reddit_adapter_reuses_memory_manager(self):
        from core import brain_loop
        from core.dispatcher.spec import SubstrateSource

        created = []

        class FakeMemoryManager:
            raw = object()

            def __init__(self):
                created.append(self)

            def _recent_reddit_source_rows(self, collection, query, *, limit=5):
                return [
                    {
                        "content": "reddit row",
                        "metadata": {
                            "source": "reddit/r/LocalLLaMA",
                            "timestamp": "2026-05-27T15:28:41+00:00",
                        },
                    }
                ]

            def recall_for_telegram(self, query):
                return ["telegram row"]

            def format_for_prompt(self, recalled, max_chars):
                return "telegram row"

            def close(self):
                pass

        brain_loop._DISPATCHER_MEMORY_MANAGER = None
        try:
            with patch("memory.memory_manager.MemoryManager", FakeMemoryManager):
                first = brain_loop._dispatcher_recall_adapters("Check Reddit then")[
                    SubstrateSource.REDDIT_SOURCE
                ]
                second = brain_loop._dispatcher_recall_adapters("Check Reddit then")[
                    SubstrateSource.REDDIT_SOURCE
                ]
                semantic = brain_loop._dispatcher_recall_adapters("What were we discussing?")[
                    SubstrateSource.TELEGRAM_SEMANTIC
                ]
                self.assertEqual(len(first(SubstrateSource.REDDIT_SOURCE)), 1)
                self.assertEqual(len(second(SubstrateSource.REDDIT_SOURCE)), 1)
                self.assertEqual(len(semantic(SubstrateSource.TELEGRAM_SEMANTIC)), 1)
        finally:
            brain_loop._DISPATCHER_MEMORY_MANAGER = None

        self.assertEqual(len(created), 1)

    def test_dispatcher_pipeline_uses_reddit_capable_fanout_budget(self):
        from core import brain_loop
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[SubstrateSource.REDDIT_SOURCE],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_UNKNOWN},
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        seen = {}

        class FakeLayer0:
            def __init__(self, *, index):
                pass

            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                seen["branch_timeout_s"] = branch_timeout_s
                seen["global_deadline_s"] = global_deadline_s

            def run(self, spec, *, utterance, conversation_state):
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id="test-generation",
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]

            def record_completed_spec(self, **kwargs):
                pass

        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
        ):
            brain_loop._run_dispatcher_pipeline(
                user_text="Check Reddit then",
                surface="telegram",
                bond_id="rohit",
                chat_id="budget-test",
            )

        self.assertGreaterEqual(seen["branch_timeout_s"], 0.8)
        self.assertGreaterEqual(seen["global_deadline_s"], 1.0)

    def test_dispatcher_render_includes_empty_summaries_for_partial_fanout(self):
        from core import brain_loop
        from core.dispatcher.layer1 import RecallBlock, RecallBranchResult, RecallBranchStatus
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[
                SubstrateSource.REDDIT_SOURCE,
                SubstrateSource.TELEGRAM_SEMANTIC,
            ],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={
                SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_UNKNOWN,
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        reddit_block = RecallBlock(
            source=SubstrateSource.REDDIT_SOURCE,
            text="recent reddit row",
            timestamp=None,
            freshness="reddit_source_rows",
            rationale="test",
            prompt_cost=17,
        )
        result = SimpleNamespace(
            recall_blocks=(reddit_block,),
            branch_results=(
                RecallBranchResult(
                    branch_id="g:reddit",
                    fanout_generation_id="g",
                    source=SubstrateSource.REDDIT_SOURCE,
                    status=RecallBranchStatus.SUCCESS,
                    blocks=(reddit_block,),
                ),
                RecallBranchResult(
                    branch_id="g:telegram",
                    fanout_generation_id="g",
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    status=RecallBranchStatus.TIMEOUT,
                    empty_reason="deadline_reached",
                ),
            ),
        )

        rendered = brain_loop._render_dispatcher_transcript(
            spec,
            result,
            user_text="Check Reddit then",
            surface="telegram",
        )

        self.assertIn("recent reddit row", rendered)
        self.assertIn("TELEGRAM_SEMANTIC", rendered)
        self.assertIn("TIMEOUT", rendered)

    def test_dispatcher_render_includes_empty_summary_when_all_selected_sources_fail(self):
        from core import brain_loop
        from core.dispatcher.layer1 import RecallBranchResult, RecallBranchStatus
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[SubstrateSource.REDDIT_SOURCE],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_UNKNOWN},
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        result = SimpleNamespace(
            recall_blocks=(),
            branch_results=(
                RecallBranchResult(
                    branch_id="g:reddit",
                    fanout_generation_id="g",
                    source=SubstrateSource.REDDIT_SOURCE,
                    status=RecallBranchStatus.TIMEOUT,
                    empty_reason="deadline_reached",
                ),
            ),
        )

        rendered = brain_loop._render_dispatcher_transcript(
            spec,
            result,
            user_text="Check Reddit then",
            surface="telegram",
        )

        self.assertIn("No usable recall returned from REDDIT_SOURCE", rendered)
        self.assertIn("TIMEOUT", rendered)

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
