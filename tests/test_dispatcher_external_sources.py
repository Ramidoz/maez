from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _spec(*sources):
    from core.dispatcher.spec import (
        CompositionHint,
        CompositionSpec,
        ExternalSource,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
    )

    return CompositionSpec(
        substrate_sources=[],
        external_sources=list(sources),
        composition_hint=CompositionHint.FRESH_ONLY,
        provenance_framing=ProvenanceFraming.FRESH_ONLY,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability={
            source: SourceAvailability.EXECUTABLE_PRESENT
            for source in sources
            if source is not ExternalSource.FRONTIER_CONSULT
        }
        | {
            source: SourceAvailability.RESERVED_UNAVAILABLE
            for source in sources
            if source is ExternalSource.FRONTIER_CONSULT
        },
        availability_limitations=[],
        freshness_window={"requested": "live"},
        trust_scope_union=None,
    )


class DispatcherExternalSourceFanoutTests(unittest.TestCase):
    def test_external_fanout_empty_sources_is_noop(self):
        from core.dispatcher.external_sources import ExternalFanout

        result = ExternalFanout(adapters={}).run(
            _spec(),
            utterance="nothing fresh",
            conversation_state={},
            fanout_generation_id="seal-1",
        )

        self.assertEqual(result.fanout_generation_id, "seal-1")
        self.assertEqual(result.branch_results, ())
        self.assertEqual(result.fresh_blocks, ())
        self.assertEqual(result.availability_limitations, ())

    def test_frontier_consult_reserved_never_executes(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            ExternalEmptyReason,
            ExternalSource,
            ExternalBranchStatus,
        )

        called = []

        def forbidden(*_args, **_kwargs):
            called.append("called")
            raise AssertionError("frontier executed")

        result = ExternalFanout(
            adapters={ExternalSource.FRONTIER_CONSULT: forbidden}
        ).run(
            _spec(ExternalSource.FRONTIER_CONSULT),
            utterance="ask a frontier model",
            conversation_state={},
            fanout_generation_id="seal-2",
        )

        self.assertEqual(called, [])
        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.RESERVED_UNAVAILABLE)
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.RESERVED_SOURCE_UNAVAILABLE,
        )
        self.assertEqual(
            result.availability_limitations,
            (AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,),
        )

    def test_paperclip_reserved_without_audited_route(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            ExternalEmptyReason,
            ExternalSource,
            ExternalBranchStatus,
        )

        result = ExternalFanout().run(
            _spec(ExternalSource.ARXIV_OR_PAPERCLIP),
            utterance="paperclip search transformers",
            conversation_state={},
            fanout_generation_id="seal-3",
        )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.RESERVED_UNAVAILABLE)
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.RESERVED_SOURCE_UNAVAILABLE,
        )
        self.assertEqual(
            result.availability_limitations,
            (AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE,),
        )

    def test_live_reddit_adapter_uses_external_fetch_only(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        fetched = SimpleNamespace(
            ok=True,
            text=json.dumps(
                {
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "id": "abc123",
                                    "title": "fresh reddit rows",
                                }
                            }
                        ]
                    }
                }
            ),
            request_id="diag-live-reddit",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ) as fetch_text:
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-4",
            )

        self.assertEqual(fetch_text.call_count, 1)
        self.assertEqual(fetch_text.call_args.kwargs["fetch_type"], "live_reddit")
        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
        self.assertEqual(result.fresh_blocks[0].egress_diagnostic_id, "diag-live-reddit")

    def test_live_reddit_adapter_rejects_html_block_page(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            ExternalEmptyReason,
            ExternalSource,
            ExternalBranchStatus,
        )

        block_page = "<body class=theme-beta><div><style>.x{}</style></div></body>"
        fetched = SimpleNamespace(
            ok=True,
            text=block_page,
            request_id="diag-block",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-block",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.EMPTY)
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.PARSED_BUT_NO_USABLE_FIELDS,
        )
        self.assertEqual(result.fresh_blocks, ())

    def test_live_reddit_adapter_empty_children_is_no_results(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            ExternalEmptyReason,
            ExternalSource,
            ExternalBranchStatus,
        )

        empty_listing = json.dumps({"data": {"children": []}})
        fetched = SimpleNamespace(
            ok=True,
            text=empty_listing,
            request_id="diag-empty",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/EmptySubreddit right now",
                conversation_state={},
                fanout_generation_id="seal-empty",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.EMPTY)
        self.assertEqual(
            result.branch_results[0].empty_reason,
            ExternalEmptyReason.NO_RESULTS,
        )

    def test_live_reddit_adapter_accepts_valid_listing(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        listing = json.dumps(
            {
                "data": {
                    "children": [
                        {"data": {"id": "abc123", "title": "A real local LLM post"}}
                    ]
                }
            }
        )
        fetched = SimpleNamespace(
            ok=True,
            text=listing,
            request_id="diag-valid",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-valid",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
        self.assertEqual(
            result.fresh_blocks[0].egress_diagnostic_id,
            "diag-valid",
        )

    def test_live_reddit_adapter_validates_full_body_not_truncated(self):
        from core.dispatcher.external_sources import (
            ExternalFanout,
            MAX_FRESH_CHARS_PER_SOURCE,
        )
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        listing = json.dumps(
            {
                "data": {
                    "children": [
                        {"data": {"id": f"p{i}", "title": "x" * 100}}
                        for i in range(40)
                    ]
                }
            }
        )
        self.assertGreater(len(listing), MAX_FRESH_CHARS_PER_SOURCE)
        fetched = SimpleNamespace(
            ok=True,
            text=listing,
            request_id="diag-large",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-large",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
        self.assertLessEqual(
            len(result.fresh_blocks[0].text),
            MAX_FRESH_CHARS_PER_SOURCE,
        )

    def test_live_reddit_adapter_transport_failure_stays_error(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        fetched = SimpleNamespace(
            ok=False,
            text="<html><body>503 Service Unavailable</body></html>",
            request_id="diag-503",
            status_code=503,
            reason_codes=("upstream_unavailable",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-503",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.ERROR)

    def test_dispatcher_live_reddit_block_records_honest_axes(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalSource
        from core.routing.observation import (
            RoutingObservationStore,
            record_dispatcher_turn_observation,
        )

        block_page = "<body class=theme-beta><div><style>.x{}</style></div></body>"
        fetched = SimpleNamespace(
            ok=True,
            text=block_page,
            request_id="diag-orth",
            status_code=200,
            reason_codes=("public_lookup_allowed",),
        )
        spec = _spec(ExternalSource.LIVE_REDDIT)

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            external_result = ExternalFanout().run(
                spec,
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-orth",
            )

        layer1_result = SimpleNamespace(branch_results=(), recall_blocks=())
        rendered_turn = SimpleNamespace(
            refusal_reason=None,
            effective_spec=spec,
            prompt_block="",
        )

        row_id = record_dispatcher_turn_observation(
            user_text="Search r/LocalLLaMA right now",
            surface="test_orth",
            chat_id=None,
            original_spec=spec,
            effective_spec=spec,
            layer1_result=layer1_result,
            external_result=external_result,
            rendered_turn=rendered_turn,
            turn_seal_state="clean",
            elapsed_ms=1.0,
        )

        row = RoutingObservationStore().get(row_id)
        self.assertEqual(row["spec_match_score"], 1.0)
        self.assertEqual(row["spec_match_reason"], "matched_requested_source")
        self.assertEqual(row["outcome_quality"], "empty_but_honest")
        self.assertEqual(row["evidence_block_count"], 0)
        self.assertEqual(row["empty_reason"], "PARSED_BUT_NO_USABLE_FIELDS")

    def test_fetch_url_refuses_model_invented_url(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            DispatcherRefusalReason,
            ExternalErrorClass,
            ExternalSource,
            ExternalBranchStatus,
        )

        result = ExternalFanout().run(
            _spec(ExternalSource.FETCH_URL),
            utterance="read the source you found",
            conversation_state={"model_suggested_url": "https://example.com/model"},
            fanout_generation_id="seal-5",
        )

        branch = result.branch_results[0]
        self.assertEqual(branch.status, ExternalBranchStatus.PREFLIGHT_BLOCKED)
        self.assertEqual(branch.error_class, ExternalErrorClass.PREFLIGHT_REFUSED)
        self.assertEqual(branch.refusal_reason, DispatcherRefusalReason.MODEL_INVENTED_URL)
        self.assertEqual(result.fresh_blocks, ())

    def test_credential_query_string_refused_before_egress(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalErrorClass, ExternalSource, ExternalBranchStatus

        called = []

        def forbidden(*_args, **_kwargs):
            called.append("called")
            raise AssertionError("credential-bearing URL reached egress")

        result = ExternalFanout(adapters={ExternalSource.FETCH_URL: forbidden}).run(
            _spec(ExternalSource.FETCH_URL),
            utterance="read https://example.com/data?api_token=secret",
            conversation_state={},
            fanout_generation_id="seal-6",
        )

        self.assertEqual(called, [])
        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.PREFLIGHT_BLOCKED)
        self.assertEqual(result.branch_results[0].error_class, ExternalErrorClass.PREFLIGHT_REFUSED)

    def test_third_party_named_subject_blocks_at_external_construction(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            ExternalErrorClass,
            ExternalSource,
            ExternalBranchStatus,
        )

        result = ExternalFanout(
            subject_boundary_predicate=lambda *_args, **_kwargs: True
        ).run(
            _spec(ExternalSource.WEB_SEARCH),
            utterance="research Jane Doe",
            conversation_state={},
            fanout_generation_id="seal-7",
        )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.PREFLIGHT_BLOCKED)
        self.assertEqual(
            result.branch_results[0].error_class,
            ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED,
        )
        self.assertEqual(
            result.availability_limitations,
            (AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY,),
        )

    def test_external_fetch_error_classes_map_to_availability_limitations(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            ExternalErrorClass,
            ExternalSource,
            ExternalBranchStatus,
        )

        fetched = SimpleNamespace(
            ok=False,
            text="",
            request_id="diag-auth-denied",
            status_code=403,
            reason_codes=("http_non_2xx",),
        )

        with mock.patch(
            "core.dispatcher.external_sources.external_fetch.fetch_text",
            return_value=fetched,
        ):
            result = ExternalFanout().run(
                _spec(ExternalSource.LIVE_REDDIT),
                utterance="Search r/LocalLLaMA right now",
                conversation_state={},
                fanout_generation_id="seal-8",
            )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.ERROR)
        self.assertEqual(result.branch_results[0].error_class, ExternalErrorClass.AUTH_DENIED)
        self.assertEqual(
            result.availability_limitations,
            (AvailabilityLimitation.FRESH_ATTEMPT_FAILED,),
        )

    def test_external_success_uses_existing_egress_diagnostics(self):
        from core.dispatcher.external_sources import ExternalAdapterPayload, ExternalFanout
        from core.dispatcher.spec import ExternalSource, FreshnessClass, ExternalBranchStatus

        result = ExternalFanout(
            adapters={
                ExternalSource.WEB_SEARCH: lambda *_args, **_kwargs: ExternalAdapterPayload(
                    text="fresh search context",
                    egress_diagnostic_id="diag-web",
                )
            }
        ).run(
            _spec(ExternalSource.WEB_SEARCH),
            utterance="search the web",
            conversation_state={},
            fanout_generation_id="seal-9",
        )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
        block = result.fresh_blocks[0]
        self.assertEqual(block.source, ExternalSource.WEB_SEARCH)
        self.assertEqual(block.text, "fresh search context")
        self.assertEqual(block.freshness, FreshnessClass.LIVE_FETCH)
        self.assertEqual(block.egress_diagnostic_id, "diag-web")
        self.assertFalse(hasattr(block, "rationale"))

    def test_default_web_search_success_uses_diagnostic_row_not_synthetic_id(self):
        from core.dispatcher.external_sources import (
            ExternalFanout,
            diagnostics_match_fresh_block,
        )
        from core.dispatcher.spec import ExternalBranchStatus, ExternalSource

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "external_fetch.jsonl"

            def witnessed_search(_query, max_results=3):
                self.assertEqual(max_results, 3)
                log_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "external-fetch-diagnostic-v1",
                            "request_id": "diag-web-real",
                            "caller": "skills.web_search.search.instant_answer",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return {
                    "success": True,
                    "results": [{"title": "Result", "snippet": "Fresh", "url": "https://example.com"}],
                    "result_count": 1,
                    "query": "search the web",
                }

            with (
                mock.patch.dict(
                    "os.environ",
                    {"MAEZ_EXTERNAL_FETCH_LOG": str(log_path)},
                ),
                mock.patch("skills.web_search.search", side_effect=witnessed_search),
                mock.patch(
                    "skills.web_search.format_for_context",
                    return_value="[WEB SEARCH] Fresh result",
                ),
            ):
                result = ExternalFanout().run(
                    _spec(ExternalSource.WEB_SEARCH),
                    utterance="search the web",
                    conversation_state={},
                    fanout_generation_id="seal-web-real",
                )

            self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
            self.assertEqual(result.fresh_blocks[0].egress_diagnostic_id, "diag-web-real")
            self.assertTrue(
                diagnostics_match_fresh_block(result.fresh_blocks[0], log_path=log_path)
            )
            self.assertFalse(result.fresh_blocks[0].egress_diagnostic_id.startswith("web_search:"))

    def test_default_web_search_meta_instruction_uses_recent_owner_question(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalBranchStatus, ExternalSource

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "external_fetch.jsonl"
            seen = {}

            def witnessed_search(query, max_results=3):
                seen["query"] = query
                self.assertEqual(max_results, 3)
                log_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "external-fetch-diagnostic-v1",
                            "request_id": "diag-web-derived",
                            "caller": "skills.web_search.search.searxng",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return {
                    "success": True,
                    "results": [{"title": "Result", "snippet": "Fresh", "url": "https://example.com"}],
                    "result_count": 1,
                    "query": query,
                }

            with (
                mock.patch.dict(
                    "os.environ",
                    {"MAEZ_EXTERNAL_FETCH_LOG": str(log_path)},
                ),
                mock.patch("skills.web_search.search", side_effect=witnessed_search),
                mock.patch(
                    "skills.web_search.format_for_context",
                    return_value="[WEB SEARCH] Fresh result",
                ),
            ):
                result = ExternalFanout().run(
                    _spec(ExternalSource.WEB_SEARCH),
                    utterance="Search the internet if you don't have the latest information",
                    conversation_state={
                        "chat_history": [
                            {
                                "content": "rohit: What's the latest with Anthropic?\n"
                                "maez: I don't have current web information yet.",
                                "metadata": {"timestamp": "2026-06-12T16:34:00Z"},
                            }
                        ]
                    },
                    fanout_generation_id="seal-web-derived",
                )

            self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
            self.assertEqual(seen["query"], "What's the latest with Anthropic?")

    def test_every_fresh_block_has_matching_egress_diagnostic(self):
        from core.dispatcher.external_sources import (
            ExternalAdapterPayload,
            ExternalFanout,
            diagnostics_match_fresh_block,
        )
        from core.dispatcher.spec import ExternalSource

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "external_fetch.jsonl"
            log_path.write_text(
                json.dumps(
                    {
                        "schema_version": "external-fetch-diagnostic-v1",
                        "request_id": "diag-match",
                        "response_digest": "hmac-sha256:test",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = ExternalFanout(
                adapters={
                    ExternalSource.WEB_SEARCH: lambda *_args, **_kwargs: ExternalAdapterPayload(
                        text="fresh search context",
                        egress_diagnostic_id="diag-match",
                    )
                }
            ).run(
                _spec(ExternalSource.WEB_SEARCH),
                utterance="search the web",
                conversation_state={},
                fanout_generation_id="seal-10",
            )

            self.assertTrue(
                all(
                    diagnostics_match_fresh_block(block, log_path=log_path)
                    for block in result.fresh_blocks
                )
            )

    def test_external_fanout_seals_late_results_by_generation_id(self):
        from core.dispatcher.external_sources import ExternalAdapterPayload, ExternalFanout
        from core.dispatcher.spec import DeadlineKind, ExternalSource, ExternalBranchStatus

        release = threading.Event()

        def slow_adapter(*_args, **_kwargs):
            release.wait(timeout=1.0)
            return ExternalAdapterPayload(
                text="late fresh evidence",
                egress_diagnostic_id="diag-late",
            )

        result = ExternalFanout(
            adapters={ExternalSource.WEB_SEARCH: slow_adapter},
            branch_timeout_s=0.02,
            global_deadline_s=0.05,
            cleanup_grace_s=0.005,
        ).run(
            _spec(ExternalSource.WEB_SEARCH),
            utterance="search the web",
            conversation_state={},
            fanout_generation_id="seal-11",
        )
        before = result.to_dict()

        release.set()
        time.sleep(0.05)

        self.assertEqual(result.to_dict(), before)
        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.TIMEOUT)
        self.assertEqual(result.branch_results[0].deadline_kind, DeadlineKind.BRANCH)
        self.assertTrue(result.branch_results[0].late_result_ignored)
        self.assertEqual(result.fresh_blocks, ())

    def test_unmapped_adapter_exception_uses_unclassified_not_network_error(self):
        from core.dispatcher.external_sources import ExternalFanout
        from core.dispatcher.spec import ExternalErrorClass, ExternalSource, ExternalBranchStatus

        def raw_exception_adapter(*_args, **_kwargs):
            raise RuntimeError("SECRET RAW EXCEPTION TEXT")

        result = ExternalFanout(
            adapters={ExternalSource.WEB_SEARCH: raw_exception_adapter}
        ).run(
            _spec(ExternalSource.WEB_SEARCH),
            utterance="search the web",
            conversation_state={},
            fanout_generation_id="seal-12",
        )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.ERROR)
        self.assertEqual(result.branch_results[0].error_class, ExternalErrorClass.UNCLASSIFIED)
        self.assertNotIn("SECRET RAW", json.dumps(result.to_dict(), sort_keys=True))

    def test_fresh_block_timestamp_uses_adapter_request_timestamp(self):
        from core.dispatcher.external_sources import ExternalAdapterPayload, ExternalFanout
        from core.dispatcher.spec import ExternalSource, ExternalBranchStatus

        seen_request_timestamp = []

        def adapter(_source, request):
            seen_request_timestamp.append(request.retrieval_timestamp)
            time.sleep(0.01)
            return ExternalAdapterPayload(
                text="fresh evidence",
                egress_diagnostic_id="diag-timestamp",
                retrieval_timestamp=request.retrieval_timestamp,
            )

        result = ExternalFanout(
            adapters={ExternalSource.WEB_SEARCH: adapter}
        ).run(
            _spec(ExternalSource.WEB_SEARCH),
            utterance="search the web",
            conversation_state={},
            fanout_generation_id="seal-timestamp",
        )

        self.assertEqual(result.branch_results[0].status, ExternalBranchStatus.SUCCESS)
        self.assertEqual(result.fresh_blocks[0].retrieval_timestamp, seen_request_timestamp[0])

    def test_external_sources_does_not_import_embedder_or_chroma(self):
        source = Path("core/dispatcher/external_sources.py").read_text(encoding="utf-8")

        forbidden = [
            "skills.reddit_skill",
            "urllib.request",
            "requests",
            "httpx",
            "socket",
            "memory.embedder",
            "core.dispatcher.layer0",
            "chromadb",
            "ONNXMiniLM",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, source)


class FetchUrlAdapterTests(unittest.TestCase):
    def _fetched(self, *, text, content_type, ok=True):
        from core.egress.external_fetch import ExternalFetchResult

        return ExternalFetchResult(
            ok=ok,
            text=text,
            fetch_type="fetch_url",
            decision="allow",
            request_id="diag-page-1",
            content_type=content_type,
        )

    def _request(self, utterance):
        from core.dispatcher.external_sources import ExternalAdapterRequest
        from core.dispatcher.spec import ExternalSource

        return ExternalAdapterRequest(
            source=ExternalSource.FETCH_URL,
            utterance=utterance,
            conversation_state={},
            retrieval_timestamp="2026-06-12T00:00:00Z",
        )

    def test_html_is_extracted_not_raw(self):
        from core.dispatcher import external_sources as es

        html = (
            "<html><head><title>T</title><script>x</script></head>"
            "<body><p>real body text</p></body></html>"
        )
        with mock.patch.object(
            es.external_fetch,
            "fetch_text",
            return_value=self._fetched(text=html, content_type="text/html; charset=utf-8"),
        ):
            payload = es._fetch_url_adapter(
                es.ExternalSource.FETCH_URL,
                self._request("check https://a.example/page"),
            )

        self.assertIn("real body text", payload.text)
        self.assertIn("T", payload.text.splitlines()[0])
        self.assertNotIn("<script>", payload.text)
        self.assertNotIn("<html>", payload.text)
        self.assertEqual(payload.egress_diagnostic_id, "diag-page-1")

    def test_non_text_content_type_refused_empty(self):
        from core.dispatcher import external_sources as es

        with mock.patch.object(
            es.external_fetch,
            "fetch_text",
            return_value=self._fetched(text="%PDF-1.7 ...", content_type="application/pdf"),
        ):
            with self.assertRaises(es._MappedExternalFailure) as ctx:
                es._fetch_url_adapter(
                    es.ExternalSource.FETCH_URL,
                    self._request("check https://a.example/file.pdf"),
                )

        self.assertEqual(ctx.exception.status, es.ExternalBranchStatus.EMPTY)

    def test_empty_extraction_refused_empty(self):
        from core.dispatcher import external_sources as es

        with mock.patch.object(
            es.external_fetch,
            "fetch_text",
            return_value=self._fetched(
                text="<html><script>only noise</script></html>",
                content_type="text/html",
            ),
        ):
            with self.assertRaises(es._MappedExternalFailure):
                es._fetch_url_adapter(
                    es.ExternalSource.FETCH_URL,
                    self._request("check https://a.example/empty"),
                )


if __name__ == "__main__":
    unittest.main()
