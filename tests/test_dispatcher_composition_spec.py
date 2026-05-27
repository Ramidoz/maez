import unittest


class DispatcherCompositionSpecTests(unittest.TestCase):
    def test_composition_spec_serializes_availability_fields(self):
        from core.dispatcher.spec import (
            AvailabilityLimitation,
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
            external_sources=[ExternalSource.WEB_SEARCH],
            composition_hint=CompositionHint.PARALLEL,
            provenance_framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            inventory_witness=InventoryWitness.MIXED,
            source_availability={
                SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_UNKNOWN,
            },
            availability_limitations=[AvailabilityLimitation.INVENTORY_UNKNOWN],
            freshness_window={"requested": "recent", "scoring": "deferred"},
            trust_scope_union={"eligible": ["owner"], "excluded": ["guest"]},
        )

        payload = spec.to_dict()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["inventory_witness"], "MIXED")
        self.assertEqual(
            payload["source_availability"],
            {
                "REDDIT_SOURCE": "EXECUTABLE_PRESENT",
                "WEB_SEARCH": "EXECUTABLE_UNKNOWN",
            },
        )
        self.assertEqual(payload["availability_limitations"], ["INVENTORY_UNKNOWN"])
        self.assertEqual(
            CompositionSpec.from_dict(payload).to_dict(),
            payload,
        )

    def test_unknown_closed_vocabulary_value_refused(self):
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            DispatcherRefusalReason,
            DispatcherSpecRefused,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
        )

        with self.assertRaises(DispatcherSpecRefused) as raised:
            CompositionSpec.from_dict(
                {
                    "schema_version": 1,
                    "substrate_sources": ["NEW_NOTEBOOK"],
                    "external_sources": [ExternalSource.WEB_SEARCH.value],
                    "composition_hint": CompositionHint.PARALLEL.value,
                    "provenance_framing": (
                        ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES.value
                    ),
                    "inventory_witness": InventoryWitness.UNKNOWN.value,
                    "source_availability": {
                        "NEW_NOTEBOOK": SourceAvailability.EXECUTABLE_PRESENT.value,
                        ExternalSource.WEB_SEARCH.value: SourceAvailability.EXECUTABLE_UNKNOWN.value,
                    },
                    "availability_limitations": [],
                    "freshness_window": None,
                    "trust_scope_union": None,
                }
            )

        self.assertEqual(
            raised.exception.reason,
            DispatcherRefusalReason.UNKNOWN_CLOSED_VOCABULARY_VALUE,
        )

    def test_incoherent_hint_framing_pair_refused(self):
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            DispatcherRefusalReason,
            DispatcherSpecRefused,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with self.assertRaises(DispatcherSpecRefused) as raised:
            CompositionSpec(
                substrate_sources=[SubstrateSource.REDDIT_SOURCE],
                external_sources=[],
                composition_hint=CompositionHint.SUBSTRATE_ONLY,
                provenance_framing=ProvenanceFraming.FRESH_ONLY,
                inventory_witness=InventoryWitness.PRESENT,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                freshness_window=None,
                trust_scope_union=None,
            )

        self.assertEqual(
            raised.exception.reason,
            DispatcherRefusalReason.INCOHERENT_HINT_FRAMING_PAIR,
        )

    def test_named_sources_require_availability_entries(self):
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            DispatcherRefusalReason,
            DispatcherSpecRefused,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )

        with self.assertRaises(DispatcherSpecRefused) as raised:
            CompositionSpec(
                substrate_sources=[SubstrateSource.REDDIT_SOURCE],
                external_sources=[ExternalSource.WEB_SEARCH],
                composition_hint=CompositionHint.PARALLEL,
                provenance_framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                inventory_witness=InventoryWitness.MIXED,
                source_availability={
                    SubstrateSource.REDDIT_SOURCE: SourceAvailability.EXECUTABLE_PRESENT,
                },
                availability_limitations=[],
                freshness_window=None,
                trust_scope_union=None,
            )

        self.assertEqual(
            raised.exception.reason,
            DispatcherRefusalReason.CALLER_SUPPLIED_SOURCE_SELECTION,
        )


if __name__ == "__main__":
    unittest.main()
