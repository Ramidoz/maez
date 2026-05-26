from __future__ import annotations

import unittest
import tempfile
from datetime import UTC, datetime
from pathlib import Path

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

    def test_wondering_generated_producer_materializes_from_real_wondering_row(self):
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            wid = store.add(
                "why did that owner-bond thread stay open?",
                source="manual",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=wid,
                bond_id="firstborn",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "7" * 64,
                priority_class="owner_bond",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.OWNER_BOND_RELATIONAL,
            )

            self.curiosity.register_wonderings_backed_producers(store)
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.WONDERING_GENERATED
            )
            obj = entry.create({"wondering_id": wid})

        self.assertEqual(entry.evidence_pointer_kind, "wonderings.id")
        self.assertEqual(obj.wondering_id, wid)
        self.assertEqual(obj.bond_id, "firstborn")
        self.assertEqual(obj.encounter_source, "wondering_generated")
        self.assertEqual(obj.priority_class, "owner_bond")
        self.assertEqual(obj.subject_kind, self.curiosity.SubjectKind.OWNER_BOND_RELATIONAL)
        self.assertIsNotNone(obj.created_at)

    def test_explicit_owner_flag_producer_materializes_from_real_flagged_wondering_row(self):
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            wid = store.add(
                "look this up later",
                source="explicit_owner_flag",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=wid,
                bond_id="firstborn",
                encounter_source="explicit_owner_flag",
                encounter_ref_digest="hmac-sha256:" + "9" * 64,
                priority_class="world_knowledge",
                salience=0.9,
                subject_kind=self.curiosity.SubjectKind.PUBLIC_TOPIC,
            )

            self.curiosity.register_wonderings_backed_producers(store)
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.EXPLICIT_OWNER_FLAG
            )
            obj = entry.create({"wondering_id": wid})

        self.assertEqual(entry.evidence_pointer_kind, "wonderings.id")
        self.assertEqual(obj.encounter_source, "explicit_owner_flag")
        self.assertEqual(obj.priority_class, "world_knowledge")
        self.assertEqual(obj.subject_kind, self.curiosity.SubjectKind.PUBLIC_TOPIC)

    def test_explicit_owner_flag_refuses_non_flagged_wondering_row(self):
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            wid = store.add(
                "ordinary manual row cannot become an explicit owner flag",
                source="manual",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=wid,
                bond_id="firstborn",
                encounter_source="explicit_owner_flag",
                encounter_ref_digest="hmac-sha256:" + "a" * 64,
                priority_class="world_knowledge",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.PUBLIC_TOPIC,
            )

            self.curiosity.register_wonderings_backed_producers(store)
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.EXPLICIT_OWNER_FLAG
            )

            with self.assertRaisesRegex(ValueError, "cannot enter explicit_owner_flag producer"):
                entry.create({"wondering_id": wid})

    def test_wonderings_backed_producer_refuses_legacy_or_missing_sidecar_rows(self):
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            store = Wonderings(db_path=Path(td) / "wonderings.db")
            legacy_id = store.add("legacy question", source="manual")
            bonded_id = store.add("bonded without sidecar", source="manual", bond_id="firstborn")

            self.curiosity.register_wonderings_backed_producers(store)
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.WONDERING_GENERATED
            )
            with self.assertRaises(self.curiosity.LegacyWonderingProjectionRefused):
                entry.create({"wondering_id": legacy_id})
            with self.assertRaises(ValueError):
                entry.create({"wondering_id": bonded_id})

    def test_wonderings_backed_producer_can_drive_scratch_ceremony(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.temperament import Temperament
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            temperament = Temperament(db_path=root / "temperament.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            temperament.record_event(parameter="curiosity", value=5.0)
            wid = store.add(
                "what did that unresolved owner-bond question mean?",
                source="manual",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=wid,
                bond_id="firstborn",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "8" * 64,
                priority_class="owner_bond",
                salience=1.0,
                subject_kind=self.curiosity.SubjectKind.OWNER_BOND_RELATIONAL,
            )
            self.curiosity.register_wonderings_backed_producers(store)
            obj = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.WONDERING_GENERATED
            ).create({"wondering_id": wid})

            result = self.curiosity.write_curiosity_resolution_seam_call(
                curiosity_object=obj,
                temperament=temperament,
                subjective_duration=subjective,
                resolution_marker_type="explicit_owner_resolved",
                resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                guard=self.curiosity.OwnerBondSaturationGuard(
                    owner_bond_meaningful_daily_cap=99
                ),
            )
            record = subjective.lookup_meaningful_salience_event_record(
                bond_id="firstborn",
                producer_event_id=result.producer_event_id,
            )

        self.assertIsNotNone(record)
        self.assertGreater(record.meaningfulness_score, 0.0)


if __name__ == "__main__":
    unittest.main()
