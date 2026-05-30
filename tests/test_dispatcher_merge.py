from __future__ import annotations

import unittest
from unittest import mock


def _spec(*, hint, framing, substrate_sources=(), external_sources=()):
    from core.dispatcher.spec import (
        CompositionSpec,
        InventoryWitness,
        SourceAvailability,
    )

    return CompositionSpec(
        substrate_sources=list(substrate_sources),
        external_sources=list(external_sources),
        composition_hint=hint,
        provenance_framing=framing,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability={
            source: SourceAvailability.EXECUTABLE_PRESENT
            for source in (*substrate_sources, *external_sources)
        },
        availability_limitations=[],
        freshness_window={"requested": "live"} if external_sources else None,
        trust_scope_union=None,
    )


def _layer1_result(*blocks):
    from core.dispatcher.layer1 import Layer1FanoutResult

    return Layer1FanoutResult(
        fanout_generation_id="seal-merge",
        sealed_at=10.0,
        accepted_branch_ids=tuple(f"seal-merge:{block.source.value}" for block in blocks),
        branch_results=(),
        recall_blocks=tuple(blocks),
    )


def _recall_block(source, text="saved memory", *, items=()):
    from core.dispatcher.layer1 import RecallBlock

    return RecallBlock(
        source=source,
        text=text,
        timestamp=1.0,
        freshness="substrate",
        rationale="selected by test",
        prompt_cost=len(text),
        items=tuple(items),
    )


def _external_result(*branches, blocks=(), availability_limitations=()):
    from core.dispatcher.external_sources import ExternalFanoutResult

    return ExternalFanoutResult(
        fanout_generation_id="seal-merge",
        sealed_at=11.0,
        branch_results=tuple(branches),
        fresh_blocks=tuple(blocks),
        availability_limitations=tuple(availability_limitations),
    )


def _fresh_block(source, text="fresh evidence"):
    from core.dispatcher.external_sources import FreshBlock
    from core.dispatcher.spec import FreshnessClass

    return FreshBlock(
        source=source,
        text=text,
        retrieval_timestamp="2026-05-27T12:00:00Z",
        freshness=FreshnessClass.LIVE_FETCH,
        prompt_cost=len(text),
        egress_diagnostic_id="diag-fresh",
    )


def _external_branch(source, status, *, blocks=(), error_class=None, completed_at=10.5):
    from core.dispatcher.external_sources import ExternalBranchResult

    return ExternalBranchResult(
        branch_id=f"seal-merge:{source.value}",
        fanout_generation_id="seal-merge",
        source=source,
        status=status,
        blocks=tuple(blocks),
        error_class=error_class,
        completed_at=completed_at,
    )


class DispatcherMergeTests(unittest.TestCase):
    def test_merge_carries_structured_recall_items(self):
        from core.dispatcher.layer1 import RecallItem
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ProvenanceFraming,
            SubstrateSource,
        )

        item = RecallItem(
            text="full recalled body",
            source_type="memory_context",
            durable_id="core-april-27",
            temporal_provenance={"method": "exact_date", "confirmed": True},
        )
        rendered = merge_fanout_results(
            _spec(
                hint=CompositionHint.SUBSTRATE_ONLY,
                framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
                substrate_sources=(SubstrateSource.TELEGRAM_SEMANTIC,),
            ),
            _layer1_result(
                _recall_block(
                    SubstrateSource.TELEGRAM_SEMANTIC,
                    text="[memory context]\ntruncated rendered memory",
                    items=(item,),
                )
            ),
            _external_result(),
            utterance="what did we note around April 27?",
            surface="telegram",
            timestamp="2026-05-30T12:00:00Z",
        )

        self.assertEqual(rendered.recall_items, (item,))

    def test_hybrid_reconstruction_records_prior_framing_in_audit_envelope(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            FreshAttemptOutcome,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE)),
            _external_result(
                ExternalBranchResult(
                    branch_id="seal-merge:WEB_SEARCH",
                    fanout_generation_id="seal-merge",
                    source=ExternalSource.WEB_SEARCH,
                    status=ExternalBranchStatus.ERROR,
                    error_class=ExternalErrorClass.RATE_LIMITED,
                )
            ),
            utterance="what is fresh?",
            surface="telegram",
            timestamp="2026-05-27T12:01:00Z",
        )

        self.assertEqual(
            rendered.effective_spec.provenance_framing,
            ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
        )
        self.assertEqual(
            rendered.audit_envelope["reconstructed_from_framing"],
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES.value,
        )
        self.assertEqual(
            rendered.audit_envelope["reconstructed_from_hint"],
            CompositionHint.PARALLEL.value,
        )
        self.assertEqual(
            rendered.audit_envelope["fresh_attempt_outcome"],
            FreshAttemptOutcome.ALL_FAILED.value,
        )
        self.assertIn("[memory context]", rendered.prompt_block)

    def test_fresh_only_total_failure_cannot_be_rewritten_to_substrate_framing(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            FreshAttemptOutcome,
            ProvenanceFraming,
        )

        spec = _spec(
            hint=CompositionHint.FRESH_ONLY,
            framing=ProvenanceFraming.FRESH_ONLY,
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(),
            _external_result(
                ExternalBranchResult(
                    branch_id="seal-merge:WEB_SEARCH",
                    fanout_generation_id="seal-merge",
                    source=ExternalSource.WEB_SEARCH,
                    status=ExternalBranchStatus.ERROR,
                    error_class=ExternalErrorClass.AUTH_DENIED,
                )
            ),
            utterance="what is fresh?",
            surface="web",
            timestamp="2026-05-27T12:02:00Z",
        )

        self.assertEqual(rendered.effective_spec, spec)
        self.assertEqual(
            rendered.audit_envelope["provenance_framing"],
            ProvenanceFraming.FRESH_ONLY.value,
        )
        self.assertEqual(
            rendered.audit_envelope["fresh_attempt_outcome"],
            FreshAttemptOutcome.ALL_FAILED.value,
        )
        self.assertIn("[no fresh evidence available:", rendered.prompt_block)
        self.assertNotIn("[fresh evidence]", rendered.prompt_block)

    def test_hybrid_fresh_failure_renders_substrate_context_with_attempted_unavailable(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.FRESH_THEN_CONTEXTUALIZE,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            substrate_sources=(SubstrateSource.TELEGRAM_SEMANTIC,),
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(_recall_block(SubstrateSource.TELEGRAM_SEMANTIC, "remembered context")),
            _external_result(
                ExternalBranchResult(
                    branch_id="seal-merge:WEB_SEARCH",
                    fanout_generation_id="seal-merge",
                    source=ExternalSource.WEB_SEARCH,
                    status=ExternalBranchStatus.TIMEOUT,
                    error_class=ExternalErrorClass.TIMEOUT,
                )
            ),
            utterance="fresh then contextualize",
            surface="telegram",
            timestamp="2026-05-27T12:03:00Z",
        )

        self.assertEqual(
            rendered.effective_spec.provenance_framing,
            ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
        )
        self.assertIn("[memory context] remembered context", rendered.prompt_block)
        self.assertNotIn("[fresh evidence]", rendered.prompt_block)

    def test_no_matching_transform_refuses_with_closed_reason(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            DispatcherRefusalReason,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            ProvenanceFraming,
        )

        spec = _spec(
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(),
            _external_result(
                ExternalBranchResult(
                    branch_id="seal-merge:WEB_SEARCH",
                    fanout_generation_id="seal-merge",
                    source=ExternalSource.WEB_SEARCH,
                    status=ExternalBranchStatus.ERROR,
                    error_class=ExternalErrorClass.UNCLASSIFIED,
                )
            ),
            utterance="hybrid but no substrate rows",
            surface="web",
            timestamp="2026-05-27T12:04:00Z",
        )

        self.assertEqual(
            rendered.refusal_reason,
            DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL,
        )
        self.assertEqual(
            rendered.audit_envelope["refusal_reason"],
            DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL.value,
        )

    def test_hybrid_no_substrate_fresh_success_or_partial_reconstructs_to_fresh_only(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            CompositionHint,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            FreshAttemptOutcome,
            ProvenanceFraming,
            SubstrateSource,
        )

        cases = (
            (
                "success",
                (ExternalSource.LIVE_REDDIT,),
                (ExternalSource.LIVE_REDDIT,),
                (),
                FreshAttemptOutcome.ALL_SUCCEEDED,
            ),
            (
                "partial",
                (ExternalSource.LIVE_REDDIT, ExternalSource.WEB_SEARCH),
                (ExternalSource.LIVE_REDDIT,),
                (
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.ERROR,
                        error_class=ExternalErrorClass.RATE_LIMITED,
                    ),
                ),
                FreshAttemptOutcome.PARTIAL,
            ),
        )

        for name, external_sources, successful_sources, extra_branches, expected_outcome in cases:
            with self.subTest(name=name):
                blocks = tuple(
                    _fresh_block(source, f"fresh {source.value} rows")
                    for source in successful_sources
                )
                spec = _spec(
                    hint=CompositionHint.PARALLEL,
                    framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                    substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
                    external_sources=external_sources,
                )

                rendered = merge_fanout_results(
                    spec,
                    _layer1_result(),
                    _external_result(
                        *(
                            _external_branch(
                                block.source,
                                ExternalBranchStatus.SUCCESS,
                                blocks=(block,),
                            )
                            for block in blocks
                        ),
                        *extra_branches,
                        blocks=blocks,
                    ),
                    utterance="check r/Python",
                    surface="web",
                    timestamp="2026-05-27T12:04:15Z",
                )

                self.assertIsNone(rendered.refusal_reason)
                self.assertEqual(rendered.effective_spec.substrate_sources, [])
                self.assertEqual(rendered.effective_spec.external_sources, list(successful_sources))
                self.assertEqual(rendered.effective_spec.composition_hint, CompositionHint.FRESH_ONLY)
                self.assertEqual(rendered.effective_spec.provenance_framing, ProvenanceFraming.FRESH_ONLY)
                self.assertIn(
                    AvailabilityLimitation.NO_RELEVANT_SUBSTRATE,
                    rendered.effective_spec.availability_limitations,
                )
                self.assertEqual(
                    rendered.audit_envelope["reconstructed_from_framing"],
                    ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES.value,
                )
                self.assertEqual(
                    rendered.audit_envelope["reconstructed_from_hint"],
                    CompositionHint.PARALLEL.value,
                )
                self.assertEqual(
                    rendered.audit_envelope["fresh_attempt_outcome"],
                    expected_outcome.value,
                )
                self.assertIn("[fresh evidence]", rendered.prompt_block)
                self.assertNotIn("[memory context]", rendered.prompt_block)

    def test_substrate_only_turn_records_fresh_attempt_not_attempted(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            FreshAttemptOutcome,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.SUBSTRATE_ONLY,
            framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            substrate_sources=(SubstrateSource.TELEGRAM_SEMANTIC,),
        )

        rendered = merge_fanout_results(
            spec,
            _layer1_result(_recall_block(SubstrateSource.TELEGRAM_SEMANTIC)),
            _external_result(),
            utterance="what did I say yesterday?",
            surface="telegram",
            timestamp="2026-05-27T12:05:00Z",
        )

        self.assertEqual(rendered.fresh_attempt_outcome, FreshAttemptOutcome.NOT_ATTEMPTED)
        self.assertEqual(
            rendered.audit_envelope["fresh_attempt_outcome"],
            FreshAttemptOutcome.NOT_ATTEMPTED.value,
        )

    def test_substrate_sources_filtered_to_those_with_rows(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            CompositionHint,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.SUBSTRATE_ONLY,
            framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            substrate_sources=(
                SubstrateSource.TELEGRAM_SEMANTIC,
                SubstrateSource.ENTITY_INDEX,
                SubstrateSource.LIVED_EPISODES,
            ),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(
                _recall_block(SubstrateSource.TELEGRAM_SEMANTIC, "truncated remembered row")
            ),
            _external_result(),
            utterance="what were we talking about last evening?",
            surface="web",
            timestamp="2026-05-27T12:06:00Z",
        )

        self.assertIsNone(rendered.refusal_reason)
        self.assertEqual(
            rendered.effective_spec.substrate_sources,
            [SubstrateSource.TELEGRAM_SEMANTIC],
        )
        self.assertEqual(
            rendered.audit_envelope["reconstructed_from_framing"],
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION.value,
        )
        self.assertEqual(
            rendered.audit_envelope["reconstructed_from_hint"],
            CompositionHint.SUBSTRATE_ONLY.value,
        )
        self.assertIn(
            AvailabilityLimitation.NO_RELEVANT_SUBSTRATE,
            rendered.effective_spec.availability_limitations,
        )
        self.assertIn("[memory evidence] truncated remembered row", rendered.prompt_block)

    def test_substrate_filter_preserves_renderable_state(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ProvenanceAuditMismatchReason,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.SUBSTRATE_ONLY,
            framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            substrate_sources=(
                SubstrateSource.TELEGRAM_SEMANTIC,
                SubstrateSource.ENTITY_INDEX,
                SubstrateSource.LIVED_EPISODES,
            ),
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(
                _recall_block(SubstrateSource.TELEGRAM_SEMANTIC, "renderable row")
            ),
            _external_result(),
            utterance="mixed branches",
            surface="web",
            timestamp="2026-05-27T12:06:30Z",
        )

        self.assertEqual(
            rendered.audit_envelope["mismatch_reason"],
            ProvenanceAuditMismatchReason.NONE.value,
        )
        self.assertEqual(
            {summary.source for summary in rendered.source_summaries},
            {SubstrateSource.TELEGRAM_SEMANTIC},
        )

    def test_substrate_sources_unchanged_when_all_branches_have_rows(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ProvenanceFraming,
            SubstrateSource,
        )

        sources = (
            SubstrateSource.TELEGRAM_SEMANTIC,
            SubstrateSource.ENTITY_INDEX,
        )
        spec = _spec(
            hint=CompositionHint.SUBSTRATE_ONLY,
            framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            substrate_sources=sources,
        )
        rendered = merge_fanout_results(
            spec,
            _layer1_result(
                _recall_block(SubstrateSource.TELEGRAM_SEMANTIC, "memory row"),
                _recall_block(SubstrateSource.ENTITY_INDEX, "entity row"),
            ),
            _external_result(),
            utterance="all rows",
            surface="web",
            timestamp="2026-05-27T12:07:00Z",
        )

        self.assertEqual(rendered.effective_spec.substrate_sources, list(sources))
        self.assertIsNone(rendered.audit_envelope["reconstructed_from_framing"])
        self.assertIsNone(rendered.audit_envelope["reconstructed_from_hint"])

    def test_legal_transform_table_rows_render_without_refusal(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            CompositionHint,
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
            FreshAttemptOutcome,
            ProvenanceFraming,
            SubstrateSource,
        )

        cases = [
            (
                "fresh-only-all-succeeded",
                _spec(
                    hint=CompositionHint.FRESH_ONLY,
                    framing=ProvenanceFraming.FRESH_ONLY,
                    external_sources=(ExternalSource.WEB_SEARCH,),
                ),
                _layer1_result(),
                _external_result(
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.SUCCESS,
                        blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    ),
                    blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                ),
                FreshAttemptOutcome.ALL_SUCCEEDED,
                ProvenanceFraming.FRESH_ONLY,
                None,
            ),
            (
                "fresh-only-partial",
                _spec(
                    hint=CompositionHint.FRESH_ONLY,
                    framing=ProvenanceFraming.FRESH_ONLY,
                    external_sources=(ExternalSource.WEB_SEARCH, ExternalSource.LIVE_REDDIT),
                ),
                _layer1_result(),
                _external_result(
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.SUCCESS,
                        blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    ),
                    ExternalBranchResult(
                        branch_id="seal-merge:LIVE_REDDIT",
                        fanout_generation_id="seal-merge",
                        source=ExternalSource.LIVE_REDDIT,
                        status=ExternalBranchStatus.ERROR,
                        error_class=ExternalErrorClass.RATE_LIMITED,
                    ),
                    blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    availability_limitations=(AvailabilityLimitation.FRESH_ATTEMPT_FAILED,),
                ),
                FreshAttemptOutcome.PARTIAL,
                ProvenanceFraming.FRESH_ONLY,
                AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            ),
            (
                "hybrid-all-succeeded",
                _spec(
                    hint=CompositionHint.PARALLEL,
                    framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                    substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
                    external_sources=(ExternalSource.WEB_SEARCH,),
                ),
                _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE)),
                _external_result(
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.SUCCESS,
                        blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    ),
                    blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                ),
                FreshAttemptOutcome.ALL_SUCCEEDED,
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                None,
            ),
            (
                "hybrid-partial",
                _spec(
                    hint=CompositionHint.PARALLEL,
                    framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                    substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
                    external_sources=(ExternalSource.WEB_SEARCH, ExternalSource.LIVE_REDDIT),
                ),
                _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE)),
                _external_result(
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.SUCCESS,
                        blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    ),
                    ExternalBranchResult(
                        branch_id="seal-merge:LIVE_REDDIT",
                        fanout_generation_id="seal-merge",
                        source=ExternalSource.LIVE_REDDIT,
                        status=ExternalBranchStatus.ERROR,
                        error_class=ExternalErrorClass.RATE_LIMITED,
                    ),
                    blocks=(_fresh_block(ExternalSource.WEB_SEARCH),),
                    availability_limitations=(AvailabilityLimitation.FRESH_ATTEMPT_FAILED,),
                ),
                FreshAttemptOutcome.PARTIAL,
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            ),
            (
                "memory-context-with-fresh-failure",
                _spec(
                    hint=CompositionHint.SUBSTRATE_ONLY,
                    framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
                    substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
                    external_sources=(ExternalSource.WEB_SEARCH,),
                ),
                _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE)),
                _external_result(
                    ExternalBranchResult(
                        branch_id="seal-merge:WEB_SEARCH",
                        fanout_generation_id="seal-merge",
                        source=ExternalSource.WEB_SEARCH,
                        status=ExternalBranchStatus.ERROR,
                        error_class=ExternalErrorClass.AUTH_DENIED,
                    )
                ),
                FreshAttemptOutcome.ALL_FAILED,
                ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
                None,
            ),
        ]

        for name, spec, layer1_result, external_result, outcome, framing, limitation in cases:
            with self.subTest(name=name):
                rendered = merge_fanout_results(
                    spec,
                    layer1_result,
                    external_result,
                    utterance=name,
                    surface="telegram",
                    timestamp="2026-05-27T12:04:30Z",
                )
                self.assertIsNone(rendered.refusal_reason)
                self.assertEqual(rendered.fresh_attempt_outcome, outcome)
                self.assertEqual(rendered.effective_spec.provenance_framing, framing)
                if limitation is not None:
                    self.assertIn(limitation, rendered.effective_spec.availability_limitations)

    def test_late_external_result_cannot_mutate_substrate_only_render(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalBranchStatus,
            ExternalSource,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.SUBSTRATE_ONLY,
            framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        block = _fresh_block(ExternalSource.WEB_SEARCH, "late fresh text")
        rendered = merge_fanout_results(
            spec,
            _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE, "substrate text")),
            _external_result(
                _external_branch(
                    ExternalSource.WEB_SEARCH,
                    ExternalBranchStatus.SUCCESS,
                    blocks=(block,),
                    completed_at=12.0,
                ),
                blocks=(block,),
            ),
            utterance="memory only",
            surface="telegram",
            timestamp="2026-05-27T12:05:00Z",
        )

        self.assertIn("[memory evidence]", rendered.prompt_block)
        self.assertNotIn("late fresh text", rendered.prompt_block)
        self.assertEqual(rendered.audit_envelope["external_sources"], [])

    def test_format_no_fresh_summary_is_deterministic_and_closed_vocab(self):
        from core.dispatcher.external_sources import ExternalBranchResult
        from core.dispatcher.merge import format_no_fresh_summary
        from core.dispatcher.spec import (
            ExternalBranchStatus,
            ExternalErrorClass,
            ExternalSource,
        )

        result = _external_result(
            ExternalBranchResult(
                branch_id="seal-merge:LIVE_REDDIT",
                fanout_generation_id="seal-merge",
                source=ExternalSource.LIVE_REDDIT,
                status=ExternalBranchStatus.ERROR,
                error_class=ExternalErrorClass.AUTH_DENIED,
            ),
            ExternalBranchResult(
                branch_id="seal-merge:WEB_SEARCH",
                fanout_generation_id="seal-merge",
                source=ExternalSource.WEB_SEARCH,
                status=ExternalBranchStatus.TIMEOUT,
                error_class=ExternalErrorClass.TIMEOUT,
            ),
        )

        first = format_no_fresh_summary(result)
        second = format_no_fresh_summary(result)

        self.assertEqual(first, second)
        self.assertIn("LIVE_REDDIT:ERROR:AUTH_DENIED:FRESH_ATTEMPT_FAILED", first)
        self.assertIn("WEB_SEARCH:TIMEOUT:TIMEOUT:SOURCE_TIMEOUT", first)
        self.assertNotIn("fresh evidence text", first)

    def test_merge_does_not_call_layer2_repair_fsm(self):
        from core.dispatcher.merge import merge_fanout_results
        from core.dispatcher.spec import (
            CompositionHint,
            ExternalBranchStatus,
            ExternalSource,
            ProvenanceFraming,
            SubstrateSource,
        )

        spec = _spec(
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            substrate_sources=(SubstrateSource.REDDIT_SOURCE,),
            external_sources=(ExternalSource.WEB_SEARCH,),
        )
        block = _fresh_block(ExternalSource.WEB_SEARCH)
        with mock.patch("core.dispatcher.layer2.Layer2RepairFSM.apply_repair") as repair:
            merge_fanout_results(
                spec,
                _layer1_result(_recall_block(SubstrateSource.REDDIT_SOURCE)),
                _external_result(
                    _external_branch(
                        ExternalSource.WEB_SEARCH,
                        ExternalBranchStatus.SUCCESS,
                        blocks=(block,),
                    ),
                    blocks=(block,),
                ),
                utterance="hybrid",
                surface="telegram",
                timestamp="2026-05-27T12:06:00Z",
            )

        repair.assert_not_called()


if __name__ == "__main__":
    unittest.main()
