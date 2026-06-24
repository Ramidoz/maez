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
            patch.dict(os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}),
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
            patch.dict(os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "0"}),
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

    def test_dispatcher_inventory_summary_uses_reserved_registry(self):
        from core import brain_loop
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            SourceAvailability,
            SubstrateSource,
        )

        summary = brain_loop._dispatcher_inventory_summary()

        self.assertEqual(
            summary["source_availability"][SubstrateSource.ENTITY_INDEX],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )
        self.assertEqual(
            summary["source_availability"][SubstrateSource.LIVED_EPISODES],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )
        self.assertIn(
            AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,
            summary["availability_limitations"],
        )

    def test_dispatcher_pipeline_uses_reddit_capable_fanout_budget(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanoutResult
        from core.dispatcher.layer1 import RecallItem
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[SubstrateSource.REDDIT_SOURCE],
            external_sources=[ExternalSource.LIVE_REDDIT],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={
                SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_UNKNOWN,
                ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        seen = {}
        recall_item = RecallItem(
            text="full recalled body",
            source_type="memory_context",
            durable_id="core-april-27",
            temporal_provenance={"method": "exact_date", "confirmed": True},
        )

        class FakeLayer0:
            def __init__(self, *, index):
                pass

            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                seen["branch_timeout_s"] = branch_timeout_s
                seen["global_deadline_s"] = global_deadline_s

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                seen["layer1_generation_id"] = fanout_generation_id
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                )

        class FakeExternalFanout:
            def __init__(self, **kwargs):
                seen["external_init"] = kwargs

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id):
                seen["external_generation_id"] = fanout_generation_id
                seen["external_conversation_state"] = conversation_state
                return ExternalFanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    branch_results=(),
                    fresh_blocks=(),
                    availability_limitations=(),
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]

            def record_completed_spec(self, **kwargs):
                seen["recorded_spec"] = kwargs["spec"]

        def fake_merge(spec_arg, layer1_result, external_result, **kwargs):
            seen["merge_generation_ids"] = (
                layer1_result.fanout_generation_id,
                external_result.fanout_generation_id,
            )
            return SimpleNamespace(
                prompt_block="MERGED",
                effective_spec=spec_arg,
                refusal_reason=None,
                audit_envelope={},
                recall_items=(recall_item,),
            )

        chat_history = [
            {
                "content": "rohit: What's the latest with Anthropic?\n"
                "maez: I don't have current web information yet.",
                "metadata": {"timestamp": "2026-06-12T16:34:00Z"},
            }
        ]
        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            patch("core.dispatcher.external_sources.ExternalFanout", FakeExternalFanout),
            patch("core.dispatcher.merge.merge_fanout_results", side_effect=fake_merge),
            patch("core.brain.brain_loop.uuid.uuid4", return_value=SimpleNamespace(hex="shared-seal")),
        ):
            result = brain_loop._run_dispatcher_pipeline(
                user_text="Check Reddit then",
                surface="telegram",
                bond_id="rohit",
                chat_id="budget-test",
                chat_history=chat_history,
            )

        self.assertEqual(result.transcript, "MERGED")
        self.assertFalse(result.should_run_jarvis)
        self.assertGreaterEqual(seen["branch_timeout_s"], 0.8)
        self.assertGreaterEqual(seen["global_deadline_s"], 1.0)
        self.assertEqual(seen["layer1_generation_id"], "shared-seal")
        self.assertEqual(seen["external_generation_id"], "shared-seal")
        self.assertEqual(seen["merge_generation_ids"], ("shared-seal", "shared-seal"))
        self.assertIs(seen["recorded_spec"], spec)
        self.assertEqual(result.recall_items, (recall_item,))
        self.assertEqual(seen["external_conversation_state"]["chat_history"], chat_history)

    def test_dispatcher_enabled_never_falls_through_to_jarvis_for_external_sources(self):
        from core import brain_loop

        with (
            patch.dict(os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}),
            patch.object(
                brain_loop,
                "_run_dispatcher_pipeline",
                return_value=brain_loop._DispatcherPathResult(
                    transcript="[no fresh evidence available: WEB_SEARCH:ERROR:AUTH_DENIED:FRESH_ATTEMPT_FAILED]",
                    should_run_jarvis=False,
                ),
            ),
            patch.object(
                brain_loop,
                "_should_run_jarvis_loop",
                side_effect=AssertionError("JARVIS gate should not run under dispatcher-enabled RenderedTurn"),
            ),
        ):
            result = run_brain_loop(
                "Search r/LocalLLaMA right now",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="web",
            )

        self.assertIn("[no fresh evidence available:", result)

    def test_structured_dispatcher_result_carries_recall_items(self):
        from core import brain_loop
        from core.dispatcher.layer1 import RecallItem

        item = RecallItem(
            text="full recalled body",
            source_type="memory_context",
            durable_id="core-april-27",
            temporal_provenance={"method": "exact_date", "confirmed": True},
        )
        with (
            patch.dict(os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}),
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
                    recall_items=(item,),
                ),
            ),
        ):
            result = run_brain_loop(
                "what did we note around April 27?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram",
                return_structured=True,
            )

        self.assertEqual(result.transcript, "DISPATCHER TRANSCRIPT")
        self.assertEqual(result.recall_items, (item,))

    def test_recovery_seed_bypasses_external_fanout(self):
        from core import brain_loop

        with (
            patch.dict(os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}),
            patch("core.dispatcher.external_sources.ExternalFanout.run") as external_run,
            patch.object(brain_loop, "_run_dispatcher_pipeline") as dispatcher,
            patch.object(brain_loop, "_llm_client") as llm_client,
        ):
            response = MagicMock()
            response.message.content = "NO_RECOVERY_FOUND"
            llm_client.chat.return_value = response
            result = run_brain_loop(
                "recover",
                action_engine=MagicMock(),
                get_pipeline=MagicMock(),
                recovery_seed={
                    "failed_action": "run_shell",
                    "failed_params": {"cmd": "false"},
                    "error": "exit=1",
                    "original_intent": "test recovery",
                    "recovery_depth": 1,
                },
                max_iters=1,
            )

        external_run.assert_not_called()
        dispatcher.assert_not_called()
        self.assertIsInstance(result, str)

    def test_dispatcher_logs_layer1_budget_limited_event(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanoutResult
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[ExternalSource.LIVE_REDDIT],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_UNKNOWN,
                ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )

        class FakeLayer0:
            def __init__(self, *, index):
                pass

            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                pass

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    budget_events=(
                        SimpleNamespace(
                            source=SubstrateSource.TELEGRAM_SEMANTIC,
                            truncated_blocks=1,
                            dropped_blocks=0,
                            original_chars=1300,
                            capped_chars=1200,
                        ),
                    ),
                )

        class FakeExternalFanout:
            def run(self, spec, *, utterance, conversation_state, fanout_generation_id):
                return ExternalFanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    branch_results=(),
                    fresh_blocks=(),
                    availability_limitations=(),
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]

            def record_completed_spec(self, **kwargs):
                pass

        def fake_merge(spec_arg, layer1_result, external_result, **kwargs):
            return SimpleNamespace(
                prompt_block="MERGED",
                effective_spec=spec_arg,
                refusal_reason=None,
                audit_envelope={},
            )

        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            patch("core.dispatcher.external_sources.ExternalFanout", return_value=FakeExternalFanout()),
            patch("core.dispatcher.merge.merge_fanout_results", side_effect=fake_merge),
            self.assertLogs("core.brain.brain_loop", level="INFO") as logs,
        ):
            result = brain_loop._run_dispatcher_pipeline(
                user_text="what were we talking about last evening?",
                surface="web",
                bond_id="rohit",
                chat_id="budget-test",
            )

        self.assertEqual(result.transcript, "MERGED")
        joined = "\n".join(logs.output)
        self.assertIn("dispatcher_layer1_budget_limited", joined)
        self.assertIn("source=TELEGRAM_SEMANTIC", joined)
        self.assertIn("truncated_blocks=1", joined)
        self.assertIn("dropped_blocks=0", joined)
        self.assertIn("original_chars=1300", joined)
        self.assertIn("capped_chars=1200", joined)

    def test_dispatcher_path_exit_distinguishes_refused_turn_seal_state(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanoutResult
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            CompositionHint,
            CompositionSpec,
            DispatcherRefusalReason,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        spec = CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )
        reconstructed = CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.UNKNOWN,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[AvailabilityLimitation.NO_RELEVANT_SUBSTRATE],
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
                pass

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    budget_events=(),
                )

        class FakeExternalFanout:
            def run(self, spec, *, utterance, conversation_state, fanout_generation_id):
                return ExternalFanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    branch_results=(),
                    fresh_blocks=(),
                    availability_limitations=(),
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]

            def record_completed_spec(self, **kwargs):
                seen["recorded"] = kwargs["spec"]

        def fake_merge(spec_arg, layer1_result, external_result, **kwargs):
            return SimpleNamespace(
                prompt_block="[no fresh evidence available: test]",
                effective_spec=reconstructed,
                refusal_reason=DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL,
                audit_envelope={},
            )

        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            patch("core.dispatcher.external_sources.ExternalFanout", return_value=FakeExternalFanout()),
            patch("core.dispatcher.merge.merge_fanout_results", side_effect=fake_merge),
            self.assertLogs("core.brain.brain_loop", level="INFO") as logs,
        ):
            result = brain_loop._run_dispatcher_pipeline(
                user_text="search live",
                surface="web",
                bond_id="rohit",
                chat_id="refused-test",
            )

        self.assertEqual(result.transcript, "[no fresh evidence available: test]")
        self.assertNotIn("recorded", seen)
        joined = "\n".join(logs.output)
        self.assertIn("dispatcher_path_exit", joined)
        self.assertIn("turn_seal_state=refused", joined)
        self.assertNotIn("turn_seal_state=reconstructed", joined)

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


class RoutingComprehensionShadow(unittest.TestCase):
    def _web_spec(self):
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        return CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[ExternalSource.WEB_SEARCH],
            composition_hint=CompositionHint.PARALLEL,
            provenance_framing=(
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES
            ),
            inventory_witness=InventoryWitness.MIXED,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )

    def test_default_off_never_calls_comprehension_judge(self):
        from core import brain_loop

        seen = {}
        spec = self._web_spec()

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "0",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                side_effect=AssertionError("judge must not run"),
            ),
        ):
            result = brain_loop.run_brain_loop(
                "I did legs today",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])

    def test_shadow_logs_decision_but_external_search_still_runs(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["judge_context"] = context
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.96,
                    reason_code="owner_sharing_personal_state",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "0",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "I did legs today",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                    chat_history=[{"content": "rohit: Hey\nmaez: Hi"}],
                )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        joined = "\n".join(logs.output)
        self.assertIn("decision=personal_or_relational", joined)
        self.assertIn("enabled=False", joined)
        self.assertIn("veto_applied=False", joined)
        self.assertEqual(seen["judge_context"].current_turn, "I did legs today")
        self.assertEqual(
            seen["judge_context"].dialogue_tail,
            ("rohit: Hey\nmaez: Hi",),
        )
        self.assertEqual(seen["judge_context"].trigger.source, "WEB_SEARCH")
        self.assertIsNone(seen["judge_context"].prior_receipt)

    def test_enabled_personal_decision_removes_web_search_before_fanout(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.97,
                    reason_code="owner_sharing_personal_state",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "Pretty nice. I did legs today. I have always been insecure about my legs.",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], [])
        self.assertIn("veto_applied=True", "\n".join(logs.output))

    def test_enabled_external_info_decision_keeps_web_search(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_data",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            brain_loop.run_brain_loop(
                "I feel anxious about Nvidia stock today; check the latest price",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])

    def test_low_confidence_personal_decision_keeps_web_search(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.89,
                    reason_code="uncertain_personal",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "I did legs today",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        self.assertIn("veto_applied=False", "\n".join(logs.output))

    def test_thread_followup_veto_appends_prior_receipt_context(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["prior_receipt"] = context.prior_receipt
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.96,
                    reason_code="asks_about_prior_tool_use",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=rc.PriorToolReceipt(
                    kind="web_search",
                    query="Pretty nice. I did legs today.",
                    sources=("https://source.test/a",),
                    diagnostic_id="diag-3",
                ),
            ),
        ):
            result = brain_loop.run_brain_loop(
                "What did you check online for that?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])
        self.assertIn("PRIOR TOOL CONTEXT", result)
        self.assertIn("Pretty nice. I did legs today.", result)
        self.assertEqual(seen["prior_receipt"].diagnostic_id, "diag-3")

    def test_thread_followup_no_receipt_gets_honest_context_not_search(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["prior_receipt"] = context.prior_receipt
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.96,
                    reason_code="asks_about_prior_tool_use",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=None,
            ),
        ):
            result = brain_loop.run_brain_loop(
                "What did you check online for that?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])
        self.assertIsNone(seen["prior_receipt"])
        self.assertIn("No retained web receipt is available", result)

    def test_low_confidence_thread_followup_keeps_search_and_no_receipt_context(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["prior_receipt"] = context.prior_receipt
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.89,
                    reason_code="uncertain_followup",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=rc.PriorToolReceipt(
                    kind="web_search",
                    query="prior query",
                    sources=("https://source.test/a",),
                    diagnostic_id="diag-low",
                ),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "What did you check online for that?",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        self.assertEqual(seen["prior_receipt"].diagnostic_id, "diag-low")
        self.assertNotIn("PRIOR TOOL CONTEXT", result)
        self.assertIn("veto_applied=False", "\n".join(logs.output))

    def test_witness_personal_vulnerable_turn_vetoes(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        case = self
        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["current_turn"] = context.current_turn
                case.assertIn("insecure", context.current_turn)
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.97,
                    reason_code="owner_sharing_personal_state",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                brain_loop.run_brain_loop(
                    "I did legs today, I'm insecure about my legs",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(seen["current_turn"], "I did legs today, I'm insecure about my legs")
        self.assertEqual(seen["external_sources"], [])
        joined = "\n".join(logs.output)
        self.assertIn("decision=personal_or_relational", joined)
        self.assertIn("veto_applied=True", joined)

    def test_witness_thread_followup_vetoes_and_uses_receipt(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["prior_receipt"] = context.prior_receipt
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.97,
                    reason_code="asks_about_prior_tool_use",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=rc.PriorToolReceipt(
                    kind="web_search",
                    query="I did legs today, I'm insecure about my legs",
                    sources=("https://source.test/a",),
                    diagnostic_id="diag-4",
                ),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "What did you check online for that?",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(seen["external_sources"], [])
        self.assertEqual(seen["prior_receipt"].diagnostic_id, "diag-4")
        self.assertIn("Prior query: I did legs today", result)
        joined = "\n".join(logs.output)
        self.assertIn("decision=thread_followup_answerable", joined)
        self.assertIn("veto_applied=True", joined)

    def test_witness_latest_openai_still_searches(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["current_turn"] = context.current_turn
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_information",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                brain_loop.run_brain_loop(
                    "What's the latest on OpenAI today?",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(seen["current_turn"], "What's the latest on OpenAI today?")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        joined = "\n".join(logs.output)
        self.assertIn("decision=external_info_requested", joined)
        self.assertIn("veto_applied=False", joined)

    def test_witness_emotional_data_request_still_searches(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        case = self
        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["current_turn"] = context.current_turn
                case.assertIn("anxious", context.current_turn)
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_price",
                )

        with (
            self._patched_dispatcher(brain_loop, spec, seen),
            patch.dict(
                os.environ,
                {
                    "MAEZ_RECALL_TRIAD_ENABLED": "1",
                    "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                    "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
                },
            ),
            patch(
                "core.routing.routing_comprehension.default_judge",
                return_value=FakeJudge(),
            ),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                brain_loop.run_brain_loop(
                    "I feel anxious about Nvidia stock today; check the latest price",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(
            seen["current_turn"],
            "I feel anxious about Nvidia stock today; check the latest price",
        )
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        joined = "\n".join(logs.output)
        self.assertIn("decision=external_info_requested", joined)
        self.assertIn("veto_applied=False", joined)

    from contextlib import contextmanager

    @contextmanager
    def _patched_dispatcher(self, brain_loop, spec, seen):
        from core.dispatcher.external_sources import ExternalFanoutResult

        class FakeLayer0:
            def __init__(self, *, index):
                pass

            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                pass

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    budget_events=(),
                )

        class FakeExternalFanout:
            def run(self, spec, *, utterance, conversation_state, fanout_generation_id):
                seen["external_sources"] = [
                    source.value for source in spec.external_sources
                ]
                return ExternalFanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    branch_results=(),
                    fresh_blocks=(),
                    availability_limitations=(),
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]

            def record_completed_spec(self, **kwargs):
                seen["recorded_spec"] = kwargs["spec"]

        def fake_merge(spec_arg, layer1_result, external_result, **kwargs):
            return SimpleNamespace(
                prompt_block="MERGED",
                effective_spec=spec_arg,
                refusal_reason=None,
                audit_envelope={},
                recall_items=(),
                source_summaries=(),
                fresh_attempt_outcome="ALL_SUCCEEDED",
            )

        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            patch(
                "core.dispatcher.external_sources.ExternalFanout",
                return_value=FakeExternalFanout(),
            ),
            patch("core.dispatcher.merge.merge_fanout_results", side_effect=fake_merge),
            patch("core.routing.observation.record_dispatcher_turn_observation"),
        ):
            yield


if __name__ == "__main__":
    unittest.main()
