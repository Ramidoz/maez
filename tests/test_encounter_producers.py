from __future__ import annotations

import unittest

from core.evolution.subjective_duration import ProducerRef
from core.policies.exceptions import BondIsolationViolation


class EncounterProducerRegistrationTests(unittest.TestCase):
    def setUp(self):
        from core.evolution import drive_driven_curiosity as curiosity

        curiosity.clear_encounter_producers_for_tests()
        self.curiosity = curiosity

    def tearDown(self):
        self.curiosity.clear_encounter_producers_for_tests()

    def _valid_fields(self, **overrides):
        fields = {
            "wondering_id": 1,
            "bond_id": "private_owner",
            "question": "what should Maez learn here?",
            "encounter_source": "wondering_generated",
            "priority_class": "owner_bond",
            "salience": 0.7,
            "subject_kind": self.curiosity.SubjectKind.OWNER_BOND_RELATIONAL,
        }
        fields.update(overrides)
        return fields

    def _register_v1_wired(self):
        for source in self.curiosity.v1_wired_encounter_sources():
            self.curiosity.register_encounter_producer(
                source=source,
                evidence_pointer_kind=(
                    "subjective_duration_salience_events.event_id"
                    if source
                    == self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
                    else "wonderings.id"
                ),
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
                create_curiosity_object=lambda seed, source=source: self._valid_fields(
                    encounter_source=source.value,
                    **seed,
                ),
            )

    def test_timer_only_producer_refused_at_registration(self):
        with self.assertRaises(self.curiosity.ProducerRegistrationRefused):
            self.curiosity.register_encounter_producer(
                source=self.curiosity.EncounterSource.WONDERING_GENERATED,
                evidence_pointer_kind="timer",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
                create_curiosity_object=lambda seed: self._valid_fields(**seed),
            )

    def test_manual_test_producer_refused_for_production_registration(self):
        with self.assertRaises(self.curiosity.ProducerRegistrationRefused):
            self.curiosity.register_encounter_producer(
                source=self.curiosity.EncounterSource.WONDERING_GENERATED,
                evidence_pointer_kind="wonderings.id",
                producer_ref=ProducerRef.MANUAL_TEST_PRODUCER,
                canary=False,
                create_curiosity_object=lambda seed: self._valid_fields(**seed),
            )

        self.curiosity.register_encounter_producer(
            source=self.curiosity.EncounterSource.WONDERING_GENERATED,
            evidence_pointer_kind="wonderings.id",
            producer_ref=ProducerRef.MANUAL_TEST_PRODUCER,
            canary=True,
            create_curiosity_object=lambda seed: self._valid_fields(**seed),
        )
        entry = self.curiosity.get_registered_producer(
            self.curiosity.EncounterSource.WONDERING_GENERATED
        )
        self.assertTrue(entry.canary)

    def test_subject_kind_omission_refused_at_creation(self):
        self._register_v1_wired()

        for source in self.curiosity.v1_wired_encounter_sources():
            with self.subTest(source=source.value):
                entry = self.curiosity.get_registered_producer(source)
                events = []
                with self.assertRaises(self.curiosity.SubjectKindRefused):
                    entry.create(
                        {
                            "subject_kind": None,
                            "diagnostic_sink": events.append,
                        }
                    )
                self.assertEqual(
                    [event["event_type"] for event in events],
                    ["SUBJECT_KIND_REFUSED"],
                )

    def test_subject_kind_vocabulary_is_canonical_and_policy_exception_family(self):
        self.assertEqual(
            {kind.value for kind in self.curiosity.SubjectKind},
            {
                "public_topic",
                "owner_self",
                "owner_bond_relational",
                "self_model",
                "named_third_party",
                "unknown",
            },
        )
        self.assertTrue(issubclass(self.curiosity.SubjectKindRefused, BondIsolationViolation))

    def test_explicit_unknown_subject_kind_materializes_for_downstream_refusal(self):
        self.curiosity.register_encounter_producer(
            source=self.curiosity.EncounterSource.WONDERING_GENERATED,
            evidence_pointer_kind="wonderings.id",
            producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
            create_curiosity_object=lambda seed: self._valid_fields(**seed),
        )
        entry = self.curiosity.get_registered_producer(
            self.curiosity.EncounterSource.WONDERING_GENERATED
        )

        obj = entry.create({"subject_kind": self.curiosity.SubjectKind.UNKNOWN})

        self.assertEqual(obj.subject_kind, self.curiosity.SubjectKind.UNKNOWN)

    def test_named_third_party_without_matching_owner_explicit_consent_refused_at_creation(self):
        self._register_v1_wired()

        for source in self.curiosity.v1_wired_encounter_sources():
            with self.subTest(source=source.value):
                entry = self.curiosity.get_registered_producer(source)
                events = []
                with self.assertRaises(self.curiosity.SubjectKindRefused):
                    entry.create(
                        {
                            "subject_kind": self.curiosity.SubjectKind.NAMED_THIRD_PARTY,
                            "subject_ref": "person:unconsented",
                            "diagnostic_sink": events.append,
                        }
                    )
                self.assertEqual(
                    [event["event_type"] for event in events],
                    ["SUBJECT_KIND_REFUSED"],
                )

    def test_v1_three_sources_wired_and_four_deferred_with_reasons(self):
        self.curiosity.register_default_encounter_producers()

        self.assertEqual(len(self.curiosity.v1_wired_encounter_sources()), 3)
        for source in self.curiosity.v1_wired_encounter_sources():
            with self.subTest(wired=source.value):
                self.assertFalse(
                    isinstance(
                        self.curiosity.get_registered_producer(source),
                        self.curiosity.ProducerSourceDeferred,
                    )
                )

        deferred = self.curiosity.deferred_encounter_sources()
        self.assertEqual(len(deferred), 4)
        for source in deferred:
            with self.subTest(deferred=source.value):
                entry = self.curiosity.get_registered_producer(source)
                self.assertIsInstance(entry, self.curiosity.ProducerSourceDeferred)
                self.assertTrue(entry.reason)


if __name__ == "__main__":
    unittest.main()
