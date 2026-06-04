from __future__ import annotations

import unittest


class EgressProvenancePrimitiveTests(unittest.TestCase):
    def test_concat_preserves_span_order_classes_refs_and_flags(self):
        from core.egress.provenance import ProvenancedText

        left = ProvenancedText.public_fact(
            "public weather", source_ref="weather:test"
        )
        right = ProvenancedText.memory(
            " remembered detail", source_ref="memory:ep-1"
        )

        combined = left + right

        self.assertEqual(combined.text, "public weather remembered detail")
        self.assertEqual(
            [span.origin_class for span in combined.spans],
            ["public_fact", "memory"],
        )
        self.assertEqual(
            [span.source_ref for span in combined.spans],
            ["weather:test", "memory:ep-1"],
        )
        self.assertEqual(
            [span.redaction_allowed for span in combined.spans],
            [False, True],
        )

    def test_raw_string_conversion_is_explicit_and_conservative(self):
        from core.egress.provenance import ProvenancedText

        text = ProvenancedText.from_raw_conservative(
            "legacy blended prompt", source_ref="legacy:test"
        )

        self.assertEqual(text.text, "legacy blended prompt")
        self.assertEqual(len(text.spans), 1)
        self.assertEqual(text.spans[0].origin_class, "unclassified")
        self.assertFalse(text.spans[0].redaction_allowed)

    def test_blended_summary_takes_most_restrictive_source_class(self):
        from core.egress.provenance import ProvenancedText

        public = ProvenancedText.public_fact("rain data", source_ref="public:1")
        memory = ProvenancedText.memory("Rohit note", source_ref="memory:1")

        summary = ProvenancedText.blended_summary(
            "A summary fusing rain data and Rohit's note.",
            sources=[public, memory],
            source_ref="summary:1",
        )

        self.assertEqual(summary.spans[0].origin_class, "memory")
        self.assertTrue(summary.spans[0].redaction_allowed)

    def test_model_or_tool_output_is_not_upgraded_to_public(self):
        from core.egress.provenance import ProvenancedText

        memory_source = ProvenancedText.memory(
            "private source", source_ref="memory:private"
        )

        derived = ProvenancedText.derived_output(
            "model phrasing of the private source",
            source=memory_source,
            source_ref="model:derived",
        )

        self.assertEqual(derived.spans[0].origin_class, "memory")
        self.assertTrue(derived.spans[0].redaction_allowed)


class OwnerAccountRestrictivenessTests(unittest.TestCase):
    def test_owner_account_context_has_explicit_restrictiveness_score(self):
        import core.egress.provenance as provenance

        self.assertIn("owner_account_context", provenance._RESTRICTIVENESS)
        self.assertEqual(provenance._RESTRICTIVENESS["owner_account_context"], 3)

    def test_owner_account_context_dominates_memory_in_blended_summary(self):
        from core.egress.provenance import ProvenancedText

        owner = ProvenancedText.owner_account_context(
            "private account fact",
            source_ref="test:owner_account",
        )
        memory = ProvenancedText.memory(
            "ordinary recalled memory",
            source_ref="test:memory",
        )

        summary = ProvenancedText.blended_summary(
            "summary of both",
            sources=[memory, owner],
            source_ref="test:blend",
        )

        self.assertEqual(summary.spans[0].origin_class, "owner_account_context")
        self.assertFalse(summary.spans[0].redaction_allowed)

    def test_owner_account_context_dominates_memory_in_derived_output(self):
        from core.egress.provenance import ProvenancedText

        source = ProvenancedText.owner_account_context(
            "private account fact",
            source_ref="test:owner_account",
        )

        derived = ProvenancedText.derived_output(
            "derived private account observation",
            source=source,
            source_ref="test:derived",
        )

        self.assertEqual(derived.spans[0].origin_class, "owner_account_context")
        self.assertFalse(derived.spans[0].redaction_allowed)


if __name__ == "__main__":
    unittest.main()
