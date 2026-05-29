from __future__ import annotations

from types import SimpleNamespace
import unittest


def _substrate_spec(*, framing=None):
    from core.dispatcher.spec import (
        CompositionHint,
        CompositionSpec,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
        SubstrateSource,
    )

    if framing is None:
        framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
    return CompositionSpec(
        substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
        external_sources=[],
        composition_hint=CompositionHint.SUBSTRATE_ONLY,
        provenance_framing=framing,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability={
            SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
        },
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )


def _block(*, role_hint=None, text="x"):
    from core.dispatcher.layer1 import RecallBlock
    from core.dispatcher.spec import SubstrateSource

    return RecallBlock(
        source=SubstrateSource.TELEGRAM_SEMANTIC,
        text=text,
        timestamp=None,
        freshness="f",
        rationale="r",
        prompt_cost=len(text),
        role_hint=role_hint,
    )


class SourceRoleHome(unittest.TestCase):
    def test_sourcerole_lives_in_spec(self):
        from core.dispatcher.spec import SourceRole

        self.assertEqual(SourceRole.SUBSTRATE_EVIDENCE.value, "SUBSTRATE_EVIDENCE")
        self.assertEqual(SourceRole.SUBSTRATE_CONTEXT.value, "SUBSTRATE_CONTEXT")

    def test_renderer_reexports_same_object(self):
        from core.dispatcher.provenance_renderer import SourceRole as S2
        from core.dispatcher.spec import SourceRole as S1

        self.assertIs(S1, S2)


class RecallBlockRoleHint(unittest.TestCase):
    def test_defaults_none(self):
        self.assertIsNone(_block().role_hint)

    def test_carries_role(self):
        from core.dispatcher.spec import SourceRole

        b = _block(role_hint=SourceRole.SUBSTRATE_EVIDENCE)
        self.assertEqual(b.role_hint, SourceRole.SUBSTRATE_EVIDENCE)

    def test_to_dict_omits_role_hint_when_none(self):
        self.assertNotIn("role_hint", _block().to_dict())

    def test_to_dict_includes_role_hint_when_set(self):
        from core.dispatcher.spec import SourceRole

        d = _block(role_hint=SourceRole.SUBSTRATE_CONTEXT).to_dict()
        self.assertEqual(d["role_hint"], "SUBSTRATE_CONTEXT")


class MergeGrouping(unittest.TestCase):
    def test_none_hint_single_summary(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SubstrateSource

        out = _source_summaries(
            _substrate_spec(),
            (_block(text="a"), _block(text="b")),
            (),
        )
        tel = [s for s in out if s.source == SubstrateSource.TELEGRAM_SEMANTIC]
        self.assertEqual(len(tel), 1)
        self.assertEqual(tel[0].text, "a\nb")

    def test_two_roles_two_summaries_evidence_first(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SourceRole

        out = _source_summaries(
            _substrate_spec(),
            (
                _block(role_hint=SourceRole.SUBSTRATE_CONTEXT, text="old"),
                _block(role_hint=SourceRole.SUBSTRATE_EVIDENCE, text="new"),
            ),
            (),
        )
        roles = [s.role for s in out]
        self.assertIn(SourceRole.SUBSTRATE_EVIDENCE, roles)
        self.assertIn(SourceRole.SUBSTRATE_CONTEXT, roles)
        self.assertLess(
            roles.index(SourceRole.SUBSTRATE_EVIDENCE),
            roles.index(SourceRole.SUBSTRATE_CONTEXT),
        )

    def test_illegal_role_refused(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SourceRole

        with self.assertRaises(Exception):
            _source_summaries(
                _substrate_spec(),
                (_block(role_hint=SourceRole.FRESH_EVIDENCE),),
                (),
            )


class DirectRenderGrouping(unittest.TestCase):
    def test_direct_render_emits_both_labels(self):
        from core import brain_loop
        from core.dispatcher.spec import SourceRole

        result = SimpleNamespace(
            recall_blocks=(
                _block(role_hint=SourceRole.SUBSTRATE_CONTEXT, text="old"),
                _block(role_hint=SourceRole.SUBSTRATE_EVIDENCE, text="new"),
            ),
            branch_results=(),
        )
        rendered = brain_loop._render_dispatcher_transcript(
            _substrate_spec(),
            result,
            user_text="what do you remember?",
            surface="telegram",
        )

        self.assertIn("[memory evidence]", rendered)
        self.assertIn("[memory context]", rendered)
        self.assertLess(
            rendered.index("[memory evidence]"),
            rendered.index("[memory context]"),
        )

    def test_direct_and_merge_grouping_agree(self):
        from core.brain.brain_loop import _recall_source_summaries
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SourceRole

        blocks = (
            _block(role_hint=SourceRole.SUBSTRATE_CONTEXT, text="old"),
            _block(role_hint=SourceRole.SUBSTRATE_EVIDENCE, text="new"),
        )
        spec = _substrate_spec()
        direct = _recall_source_summaries(spec, blocks)
        merged = _source_summaries(spec, blocks, ())

        self.assertEqual(
            [(s.source, s.role, s.text) for s in direct],
            [(s.source, s.role, s.text) for s in merged],
        )


class AuditHonesty(unittest.TestCase):
    def test_source_role_entries_carries_both_roles(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import SourceRole, SubstrateSource

        rendered = render_provenance(
            _substrate_spec(),
            utterance="u",
            surface="telegram",
            ask_shape=AskShape.CONVERSATIONAL,
            timestamp="t",
            source_summaries=[
                SourceSummary(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    role=SourceRole.SUBSTRATE_EVIDENCE,
                    text="new",
                    content_digest="d1",
                ),
                SourceSummary(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    role=SourceRole.SUBSTRATE_CONTEXT,
                    text="old",
                    content_digest="d2",
                ),
            ],
        )

        entries = rendered.audit_envelope["source_role_entries"]
        pairs = {(entry["source"], entry["role"]) for entry in entries}
        self.assertIn(("TELEGRAM_SEMANTIC", "SUBSTRATE_EVIDENCE"), pairs)
        self.assertIn(("TELEGRAM_SEMANTIC", "SUBSTRATE_CONTEXT"), pairs)
        self.assertEqual({entry["digest"] for entry in entries}, {"d1", "d2"})
        self.assertEqual(
            rendered.audit_envelope["source_role_map"]["TELEGRAM_SEMANTIC"],
            "SUBSTRATE_EVIDENCE",
        )

    def test_assistant_text_metadata_forwards_entries(self):
        from core.dispatcher.provenance_renderer import (
            AskShape,
            SourceSummary,
            render_provenance,
        )
        from core.dispatcher.spec import SourceRole, SubstrateSource

        rendered = render_provenance(
            _substrate_spec(),
            utterance="u",
            surface="telegram",
            ask_shape=AskShape.CONVERSATIONAL,
            timestamp="t",
            source_summaries=[
                SourceSummary(
                    source=SubstrateSource.TELEGRAM_SEMANTIC,
                    role=SourceRole.SUBSTRATE_EVIDENCE,
                    text="new",
                    content_digest="d1",
                )
            ],
        )

        self.assertIn("source_role_entries", rendered.audit_assistant_text_metadata)


class SchemaStability(unittest.TestCase):
    def test_base_envelope_has_entries(self):
        from core.dispatcher.merge import _base_audit_envelope
        from core.dispatcher.spec import FreshAttemptOutcome

        env = _base_audit_envelope(
            _substrate_spec(),
            utterance="u",
            surface="telegram",
            timestamp="t",
            fresh_attempt_outcome=FreshAttemptOutcome.NOT_ATTEMPTED,
            refusal_reason=None,
        )

        self.assertEqual(env["source_role_entries"], [])

    def test_assistant_metadata_forwards_entries(self):
        from core.dispatcher.merge import _assistant_metadata, _base_audit_envelope
        from core.dispatcher.spec import FreshAttemptOutcome

        env = _base_audit_envelope(
            _substrate_spec(),
            utterance="u",
            surface="telegram",
            timestamp="t",
            fresh_attempt_outcome=FreshAttemptOutcome.NOT_ATTEMPTED,
            refusal_reason=None,
        )
        env["source_role_entries"] = [
            {"source": "TELEGRAM_SEMANTIC", "role": "SUBSTRATE_CONTEXT", "digest": "d"}
        ]

        self.assertEqual(_assistant_metadata(env)["source_role_entries"], env["source_role_entries"])


class Parity(unittest.TestCase):
    def test_none_hints_render_and_audit_unchanged(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import (
            ProvenanceFraming,
            SourceRole,
            SubstrateSource,
        )

        spec = _substrate_spec(framing=ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT)
        summaries = _source_summaries(
            spec,
            (_block(text="a"), _block(text="b")),
            (),
        )

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].source, SubstrateSource.TELEGRAM_SEMANTIC)
        self.assertEqual(summaries[0].role, SourceRole.SUBSTRATE_EVIDENCE)
        self.assertEqual(summaries[0].text, "a\nb")

    def test_none_hint_direct_render_matches_existing_label(self):
        from core import brain_loop
        from core.dispatcher.spec import ProvenanceFraming

        result = SimpleNamespace(
            recall_blocks=(_block(text="a"), _block(text="b")),
            branch_results=(),
        )
        rendered = brain_loop._render_dispatcher_transcript(
            _substrate_spec(framing=ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT),
            result,
            user_text="what do you remember?",
            surface="telegram",
        )

        self.assertIn("[memory evidence] a\nb", rendered)
        self.assertNotIn("[memory context]", rendered)


if __name__ == "__main__":
    unittest.main()
