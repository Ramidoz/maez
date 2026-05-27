import json
import unittest


def _hybrid_spec():
    from core.dispatcher.spec import (
        CompositionHint,
        ExternalSource,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
        SubstrateSource,
    )

    return __import__(
        "core.dispatcher.spec",
        fromlist=["CompositionSpec"],
    ).CompositionSpec(
        substrate_sources=[SubstrateSource.REDDIT_SOURCE],
        external_sources=[ExternalSource.WEB_SEARCH],
        composition_hint=CompositionHint.PARALLEL,
        provenance_framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability={
            SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
            ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
        },
        availability_limitations=[],
        freshness_window={"max_age_s": 900},
        trust_scope_union={"bond_id": "owner"},
    )


class DispatcherProvenanceRendererTests(unittest.TestCase):
    def test_hybrid_conversational_render_uses_inline_role_markers_and_closed_audit_envelope(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceRole,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import (
            ExternalSource,
            ProvenanceAuditMismatchReason,
            SubstrateSource,
        )

        spec = _hybrid_spec()
        rendered = render_provenance(
            spec,
            utterance="how's Qwen looking online?",
            surface="telegram",
            ask_shape=AskShape.CONVERSATIONAL,
            timestamp="2026-05-27T08:30:00Z",
            source_summaries=[
                SourceSummary(
                    source=SubstrateSource.REDDIT_SOURCE,
                    role=SourceRole.SUBSTRATE_CONTEXT,
                    text="Your saved LocalLLaMA notes say Qwen interest has been rising.",
                    content_digest="sha256:memory",
                ),
                SourceSummary(
                    source=ExternalSource.WEB_SEARCH,
                    role=SourceRole.FRESH_EVIDENCE,
                    text="Fresh search says Qwen3 discussion is active today.",
                    content_digest="sha256:fresh",
                ),
            ],
        )

        self.assertIn("[memory context]", rendered.prompt_block)
        self.assertIn("[fresh evidence]", rendered.prompt_block)
        self.assertNotIn("## Memory context", rendered.prompt_block)
        self.assertEqual(
            rendered.audit_envelope["mismatch_reason"],
            ProvenanceAuditMismatchReason.NONE.value,
        )
        self.assertEqual(rendered.audit_envelope["surface"], "telegram")
        self.assertEqual(
            rendered.audit_envelope["source_role_map"],
            {
                SubstrateSource.REDDIT_SOURCE.value: SourceRole.SUBSTRATE_CONTEXT.value,
                ExternalSource.WEB_SEARCH.value: SourceRole.FRESH_EVIDENCE.value,
            },
        )
        self.assertEqual(
            sorted(rendered.audit_assistant_text_metadata),
            [
                "mismatch_reason",
                "provenance_framing",
                "refusal_reason",
                "rendered_block_roles",
                "schema_version",
                "source_role_map",
                "spec_digest",
                "surface",
                "template_id",
                "template_version_hash",
                "timestamp",
                "utterance_digest",
            ],
        )

    def test_audit_envelope_omits_raw_private_content(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceRole,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import ExternalSource, SubstrateSource

        spec = _hybrid_spec()
        private_phrase = "raw private diary sentence"
        rendered = render_provenance(
            spec,
            utterance="how's Qwen looking online?",
            surface="telegram",
            ask_shape=AskShape.CONVERSATIONAL,
            timestamp="2026-05-27T08:31:00Z",
            source_summaries=[
                SourceSummary(
                    source=SubstrateSource.REDDIT_SOURCE,
                    role=SourceRole.SUBSTRATE_CONTEXT,
                    text=private_phrase,
                    content_digest="sha256:private",
                ),
                SourceSummary(
                    source=ExternalSource.WEB_SEARCH,
                    role=SourceRole.FRESH_EVIDENCE,
                    text="Fresh public summary.",
                    content_digest="sha256:fresh-public",
                ),
            ],
        )

        envelope_json = json.dumps(rendered.audit_envelope, sort_keys=True)
        self.assertIn(private_phrase, rendered.prompt_block)
        self.assertNotIn(private_phrase, envelope_json)
        self.assertIn("sha256:private", envelope_json)

    def test_report_shape_uses_structured_sections_not_inline_only(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceRole,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import ExternalSource, SubstrateSource

        rendered = render_provenance(
            _hybrid_spec(),
            utterance="give me a summary of Qwen online",
            surface="web",
            ask_shape=AskShape.REPORT,
            timestamp="2026-05-27T08:32:00Z",
            source_summaries=[
                SourceSummary(
                    source=SubstrateSource.REDDIT_SOURCE,
                    role=SourceRole.SUBSTRATE_CONTEXT,
                    text="Saved Reddit memory.",
                    content_digest="sha256:memory",
                ),
                SourceSummary(
                    source=ExternalSource.WEB_SEARCH,
                    role=SourceRole.FRESH_EVIDENCE,
                    text="Fresh web search.",
                    content_digest="sha256:fresh",
                ),
            ],
        )

        self.assertIn("## Memory context", rendered.prompt_block)
        self.assertIn("## Fresh evidence", rendered.prompt_block)
        self.assertEqual(rendered.audit_envelope["template_id"], "report.hybrid.v1")

    def test_mismatched_block_role_refuses_before_prompt_render(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceRole,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import (
            CompositionHint,
            DispatcherSpecRefused,
            DispatcherRefusalReason,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        substrate_only = __import__(
            "core.dispatcher.spec",
            fromlist=["CompositionSpec"],
        ).CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[],
            composition_hint=CompositionHint.SUBSTRATE_ONLY,
            provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            inventory_witness=InventoryWitness.PRESENT,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )

        with self.assertRaises(DispatcherSpecRefused) as ctx:
            render_provenance(
                substrate_only,
                utterance="what do you remember about Qwen?",
                surface="telegram",
                ask_shape=AskShape.CONVERSATIONAL,
                timestamp="2026-05-27T08:33:00Z",
                source_summaries=[
                    SourceSummary(
                        source=SubstrateSource.TELEGRAM_SEMANTIC,
                        role=SourceRole.FRESH_EVIDENCE,
                        text="Wrong role.",
                        content_digest="sha256:wrong",
                    )
                ],
            )

        self.assertEqual(ctx.exception.reason, DispatcherRefusalReason.PROVENANCE_TEMPLATE_MISMATCH)


if __name__ == "__main__":
    unittest.main()
