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

    def test_external_source_closed_vocabulary_enums_are_strict(self):
        from core.dispatcher.spec import (
            DeadlineKind,
            ExternalBranchStatus,
            ExternalEmptyReason,
            ExternalErrorClass,
            FreshAttemptOutcome,
            FreshnessClass,
        )

        self.assertEqual(ExternalBranchStatus.PREFLIGHT_BLOCKED.value, "PREFLIGHT_BLOCKED")
        self.assertEqual(ExternalErrorClass.AUTH_DENIED.value, "AUTH_DENIED")
        self.assertEqual(
            ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED.value,
            "SUBJECT_BOUNDARY_REFUSED",
        )
        self.assertEqual(ExternalEmptyReason.NO_RESULTS.value, "NO_RESULTS")
        self.assertEqual(DeadlineKind.GLOBAL.value, "GLOBAL")
        self.assertEqual(FreshnessClass.LIVE_FETCH.value, "LIVE_FETCH")
        self.assertEqual(FreshAttemptOutcome.PARTIAL.value, "PARTIAL")

        with self.assertRaises(ValueError):
            ExternalErrorClass("MODEL_DECIDED_REASON")

    def test_external_source_subject_boundary_limitation_is_closed_vocab(self):
        from core.dispatcher.spec import (
            AvailabilityLimitation,
            CompositionHint,
            CompositionSpec,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
        )

        spec = CompositionSpec(
            substrate_sources=[],
            external_sources=[ExternalSource.WEB_SEARCH],
            composition_hint=CompositionHint.FRESH_ONLY,
            provenance_framing=ProvenanceFraming.FRESH_ONLY,
            inventory_witness=InventoryWitness.PRESENT,
            source_availability={
                ExternalSource.WEB_SEARCH: SourceAvailability.TRUST_SCOPE_RESTRICTED,
            },
            availability_limitations=[
                AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY
            ],
            freshness_window={"requested": "live"},
            trust_scope_union={"subject_boundary": "third_party"},
        )

        payload = spec.to_dict()

        self.assertEqual(
            payload["availability_limitations"],
            ["THIRD_PARTY_SUBJECT_BOUNDARY"],
        )
        self.assertEqual(
            CompositionSpec.from_dict(payload).availability_limitations,
            [AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY],
        )

    def test_model_invented_url_refusal_reason_is_closed_vocab(self):
        from core.dispatcher.spec import DispatcherRefusalReason

        self.assertEqual(
            DispatcherRefusalReason.MODEL_INVENTED_URL.value,
            "MODEL_INVENTED_URL",
        )

    def test_fresh_failure_hybrid_fallback_illegal_reason_is_closed_vocab(self):
        from core.dispatcher.spec import DispatcherRefusalReason

        self.assertEqual(
            DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL.value,
            "FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL",
        )


if __name__ == "__main__":
    unittest.main()
