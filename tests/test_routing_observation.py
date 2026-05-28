from __future__ import annotations

import json
import logging
import os
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from core.dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    InventoryWitness,
    ProvenanceFraming,
    SourceAvailability,
    SubstrateSource,
)


def _live_reddit_spec() -> CompositionSpec:
    return CompositionSpec(
        substrate_sources=[SubstrateSource.REDDIT_SOURCE],
        external_sources=[ExternalSource.LIVE_REDDIT],
        composition_hint=CompositionHint.PARALLEL,
        provenance_framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        inventory_witness=InventoryWitness.MIXED,
        source_availability={
            SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
            ExternalSource.LIVE_REDDIT: SourceAvailability.EXECUTABLE_PRESENT,
        },
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )


class RoutingObservationStoreTests(unittest.TestCase):
    def test_store_closes_sqlite_connections(self):
        from core.routing import observation
        from core.routing.observation import RoutingObservationStore

        connections = []

        class FakeConnection:
            row_factory = None

            def __init__(self):
                self.closed = False
                connections.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def close(self):
                self.closed = True

            def execute(self, *_args, **_kwargs):
                return self

            def fetchall(self):
                return []

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(observation.sqlite3, "connect", side_effect=lambda _path: FakeConnection()):
                store = RoutingObservationStore(db_path=Path(td) / "routing_observation.db")
                store.table_names()

        self.assertGreaterEqual(len(connections), 2)
        self.assertTrue(all(conn.closed for conn in connections))

    def test_routing_observation_store_creates_schema(self):
        from core.routing.observation import RoutingObservationStore

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "routing_observation.db"
            store = RoutingObservationStore(db_path=db_path)

            tables = store.table_names()
            indexes = store.index_names()

        self.assertIn("routing_observations", tables)
        self.assertIn("idx_routing_observations_created_at", indexes)
        self.assertIn("idx_routing_observations_path_created", indexes)
        self.assertIn("idx_routing_observations_sources", indexes)
        self.assertIn("idx_routing_observations_quality", indexes)
        self.assertIn("idx_routing_observations_shape", indexes)

    def test_record_dispatcher_observation_uses_closed_vocab(self):
        from core.routing.observation import RoutingObservationStore

        with tempfile.TemporaryDirectory() as td:
            store = RoutingObservationStore(db_path=Path(td) / "routing_observation.db")
            row_id = store.record_dispatcher_observation(
                user_text="Search r/LocalLLaMA right now",
                surface="telegram_surface",
                chat_id="12345",
                spec=_live_reddit_spec(),
                chosen_source=ExternalSource.LIVE_REDDIT,
                chosen_tool="live_reddit",
                execution_status="success",
                evidence_block_count=1,
                spec_match_score=1.0,
                spec_match_reason="matched_requested_source",
                outcome_quality="structured_evidence",
                latency_ms=42.5,
            )
            row = store.get(row_id)

        self.assertEqual(row["composition_hint"], "PARALLEL")
        self.assertEqual(
            row["provenance_framing"],
            "HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES",
        )
        self.assertEqual(json.loads(row["external_sources_json"]), ["LIVE_REDDIT"])
        self.assertEqual(row["chosen_source"], "LIVE_REDDIT")
        self.assertEqual(row["utterance_shape"], "contains_subreddit_anchor")
        self.assertNotIn("Search r/LocalLLaMA", json.dumps(dict(row)))

    def test_record_legacy_web_search_observation_has_no_spec(self):
        from core.routing.observation import RoutingObservationStore

        with tempfile.TemporaryDirectory() as td:
            store = RoutingObservationStore(db_path=Path(td) / "routing_observation.db")
            row_id = store.record_legacy_web_search_observation(
                user_text="Search r/LocalLLaMA right now",
                surface="telegram_surface",
                chat_id="12345",
                chosen_tool="web_search",
                execution_status="empty",
                evidence_block_count=1,
                outcome_quality="empty_but_honest",
                latency_ms=12.0,
            )
            row = store.get(row_id)

        self.assertEqual(row["path"], "legacy_daemon_web_search")
        self.assertEqual(row["spec_match_score"], 0.0)
        self.assertEqual(row["spec_match_reason"], "no_spec_available")
        self.assertEqual(row["chosen_tool"], "web_search")
        self.assertEqual(row["source_availability_json"], "{}")

    def test_routing_observation_log_line_is_compact(self):
        from core.routing.observation import RoutingObservationStore

        with tempfile.TemporaryDirectory() as td:
            store = RoutingObservationStore(db_path=Path(td) / "routing_observation.db")
            with self.assertLogs("core.routing.observation", level="INFO") as logs:
                store.record_dispatcher_observation(
                    user_text="Search r/LocalLLaMA right now",
                    surface="telegram_surface",
                    chat_id="12345",
                    spec=_live_reddit_spec(),
                    chosen_source=ExternalSource.LIVE_REDDIT,
                    chosen_tool="live_reddit",
                    execution_status="success",
                    evidence_block_count=1,
                    spec_match_score=1.0,
                    spec_match_reason="matched_requested_source",
                    outcome_quality="structured_evidence",
                    latency_ms=42.5,
                )

        joined = "\n".join(logs.output)
        self.assertIn("routing_observation", joined)
        self.assertIn("path=dispatcher", joined)
        self.assertIn("source=LIVE_REDDIT", joined)
        self.assertIn("status=success", joined)
        self.assertIn("spec_match_score=1.000", joined)
        self.assertIn("outcome_quality=structured_evidence", joined)
        self.assertNotIn("Search r/LocalLLaMA", joined)


class RoutingSpecMatchTests(unittest.TestCase):
    def test_spec_match_score_matches_requested_live_reddit(self):
        from core.routing.observation import compute_spec_match

        match = compute_spec_match(
            spec=_live_reddit_spec(),
            chosen_source=ExternalSource.LIVE_REDDIT,
            chosen_tool="live_reddit",
            user_text="Search r/LocalLLaMA right now",
            execution_status="success",
        )

        self.assertEqual(match.score, 1.0)
        self.assertEqual(match.reason, "matched_requested_source")

    def test_spec_match_score_partial_legacy_reddit_web_search(self):
        from core.routing.observation import compute_spec_match

        match = compute_spec_match(
            spec=_live_reddit_spec(),
            chosen_source=None,
            chosen_tool="web_search",
            user_text="Search r/LocalLLaMA right now",
            execution_status="empty",
        )

        self.assertEqual(match.score, 0.5)
        self.assertEqual(match.reason, "partial_legacy_equivalent")


class RoutingObservationHookTests(unittest.TestCase):
    def test_dispatcher_path_records_observation_without_changing_rendered_turn(self):
        from core import brain_loop
        from core.dispatcher.external_sources import ExternalFanoutResult
        from core.dispatcher.layer1 import Layer1FanoutResult

        spec = _live_reddit_spec()

        class FakeLayer0:
            def __init__(self, *, index):
                pass

            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                pass

            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                return Layer1FanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    accepted_branch_ids=(),
                    branch_results=(),
                    recall_blocks=(),
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
                self.recorded = kwargs

        rendered_turn = types.SimpleNamespace(
            prompt_block="MERGED",
            effective_spec=spec,
            refusal_reason=None,
            audit_envelope={},
        )

        with (
            mock.patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            mock.patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            mock.patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            mock.patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            mock.patch("core.dispatcher.external_sources.ExternalFanout", return_value=FakeExternalFanout()),
            mock.patch("core.dispatcher.merge.merge_fanout_results", return_value=rendered_turn),
            mock.patch("core.routing.observation.record_dispatcher_turn_observation") as record,
        ):
            result = brain_loop._run_dispatcher_pipeline(
                user_text="Search r/LocalLLaMA right now",
                surface="telegram_surface",
                bond_id="rohit",
                chat_id="chat-1",
            )

        self.assertEqual(result.transcript, "MERGED")
        self.assertFalse(result.should_run_jarvis)
        record.assert_called_once()
        self.assertEqual(record.call_args.kwargs["user_text"], "Search r/LocalLLaMA right now")
        self.assertIs(record.call_args.kwargs["original_spec"], spec)
        self.assertIs(record.call_args.kwargs["rendered_turn"], rendered_turn)

    def test_daemon_legacy_web_search_records_observation_without_behavior_change(self):
        from daemon import maez_daemon

        class FakeMemory:
            def recall_for_telegram(self, _text):
                return {}

            def format_for_prompt(self, _recalled, max_chars=None):
                return ""

            def store_telegram(self, *_args, **_kwargs):
                return "raw-memory-id"

        class FreshState:
            def with_freshness(self):
                return self

        def fake_chat(*, model, messages, think, options):
            return types.SimpleNamespace(
                message=types.SimpleNamespace(content="I searched and found nothing.")
            )

        daemon = object.__new__(maez_daemon.MaezDaemon)
        daemon.system_prompt = "DAEMON SYSTEM"
        daemon.memory = FakeMemory()
        daemon.lived_episodes = types.SimpleNamespace(add=lambda *args, **kwargs: None)
        daemon.lived_graph = object()
        daemon._camera_presence_state = FreshState()
        daemon._last_screen_obs = None
        daemon._last_calendar_snap = None
        daemon.m1_promoter = None
        daemon._get_public_context = lambda: ""
        daemon._trf_apply_fragment_guard = lambda **kwargs: kwargs["reply"]
        daemon._ws_broadcast = lambda _payload: None

        trace = types.SimpleNamespace(audit=types.SimpleNamespace(), lived_recall_ids=[])

        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(
                os.environ,
                {
                    "MAEZ_LIVED_RECALL": "0",
                    "MAEZ_AMBIENT_BRIEF": "0",
                    "MAEZ_WORKING_SELF": "0",
                    "MAEZ_WONDERING_PURSUIT": "0",
                },
                clear=False,
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "guard_owner_text",
                return_value=types.SimpleNamespace(matched=False, answer_text=None),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "answer_camera_presence_question",
                return_value=None,
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "perception_snapshot",
                return_value=object(),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "format_snapshot",
                return_value="SYSTEM_STATE",
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "Trace",
                types.SimpleNamespace(start=lambda **_kwargs: trace),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "default_writer",
                return_value=types.SimpleNamespace(write=lambda _trace: None),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "_trace_hash_text",
                return_value="hash",
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "_trace_extract_evidence_ids",
                return_value=[],
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "build_temporal_anchor_recall_brief",
                return_value=types.SimpleNamespace(
                    anchor_detected=False,
                    brief_text="",
                    evidence_ids=[],
                ),
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.build_envelope",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.render_envelope_for_prompt",
                return_value="",
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.resolve_recall_cap_chars",
                return_value=1000,
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.needs_web_search",
                return_value=True,
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.is_news_query",
                return_value=False,
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.search",
                return_value={
                    "query": "Search r/LocalLLaMA right now",
                    "success": False,
                    "results": [],
                    "result_count": 0,
                },
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.format_for_context",
                return_value="[WEB SEARCH: 'Search r/LocalLLaMA right now'] No results found.",
            ))
            stack.enter_context(mock.patch(
                "core.safety.audited_output.audit_assistant_text",
                side_effect=lambda text, **_kwargs: text,
            ))
            stack.enter_context(mock.patch(
                "core.ledger.writer.try_write_turn",
                return_value="turn-1",
            ))
            stack.enter_context(mock.patch(
                "core.ledger.model_reply_persistence.persist_model_reply",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.llm_client.chat",
                side_effect=fake_chat,
            ))
            record = stack.enter_context(mock.patch(
                "core.routing.observation.record_legacy_web_search_observation"
            ))
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
            )

        self.assertEqual(reply, "I searched and found nothing.")
        record.assert_called_once()
        self.assertEqual(record.call_args.kwargs["user_text"], "Search r/LocalLLaMA right now")
        self.assertEqual(record.call_args.kwargs["surface"], "telegram_surface")
        self.assertEqual(record.call_args.kwargs["chosen_tool"], "web_search")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
