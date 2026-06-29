from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
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
                "what did that unresolved self-growth question mean?",
                source="manual",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=wid,
                bond_id="firstborn",
                encounter_source="wondering_generated",
                encounter_ref_digest="hmac-sha256:" + "8" * 64,
                priority_class="self_growth",
                salience=1.0,
                subject_kind=self.curiosity.SubjectKind.SELF_MODEL,
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
            )
            record = subjective.lookup_meaningful_salience_event_record(
                bond_id="firstborn",
                producer_event_id=result.producer_event_id,
            )

        self.assertIsNotNone(record)
        self.assertGreater(record.meaningfulness_score, 0.0)

    def test_subjective_duration_producer_materializes_from_real_salience_event(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            parent_id = store.add("parent SD object", source="manual", bond_id="firstborn")
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=parent_id,
                bond_id="firstborn",
                encounter_source="subjective_duration_meaningful_event",
                encounter_ref_digest="hmac-sha256:" + "c" * 64,
                priority_class="self_growth",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.SELF_MODEL,
                produced_via_subjective_duration_depth=0,
            )
            event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )
            obj = entry.create({"event_id": event_id, "bond_id": "firstborn"})

            with closing(sqlite3.connect(store.db_path)) as con:
                con.row_factory = sqlite3.Row
                metadata = con.execute(
                    """
                    SELECT encounter_source, encounter_ref_digest,
                           produced_via_subjective_duration_depth
                    FROM wondering_drive_metadata
                    WHERE wondering_id = ?
                    """,
                    (obj.wondering_id,),
                ).fetchone()

        self.assertEqual(entry.evidence_pointer_kind, "subjective_duration_salience_events.event_id")
        self.assertEqual(obj.bond_id, "firstborn")
        self.assertEqual(
            obj.encounter_source,
            self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT.value,
        )
        self.assertEqual(obj.subject_kind, self.curiosity.SubjectKind.SELF_MODEL)
        self.assertEqual(obj.produced_via_subjective_duration_depth, 1)
        self.assertEqual(metadata["encounter_source"], "subjective_duration_meaningful_event")
        self.assertEqual(metadata["produced_via_subjective_duration_depth"], 1)
        self.assertTrue(str(metadata["encounter_ref_digest"]).startswith("hmac-sha256:"))

    def test_subjective_duration_producer_refuses_zero_canary_manual_and_cross_bond(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            zero_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id="zero",
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 5.0},
                now_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            )
            canary_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id="canary",
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 1, tzinfo=UTC),
                is_canary=True,
            )
            manual_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                bond_id="firstborn",
                producer_event_id="manual",
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 2, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )

            with self.assertRaisesRegex(ValueError, "meaningfulness_score"):
                entry.create({"event_id": zero_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "canary"):
                entry.create({"event_id": canary_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "manual-test"):
                entry.create({"event_id": manual_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "bond_id mismatch"):
                entry.create({"event_id": zero_id, "bond_id": "other-bond"})

            self.assertEqual(self.curiosity.list_drive_curiosity_objects(store, bond_id="firstborn"), [])

    def test_subjective_duration_producer_refuses_missing_or_cross_bond_parent(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            other_parent_id = store.add(
                "other bond parent",
                source="manual",
                bond_id="other-bond",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=other_parent_id,
                bond_id="other-bond",
                encounter_source="subjective_duration_meaningful_event",
                encounter_ref_digest="hmac-sha256:" + "d" * 64,
                priority_class="self_growth",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.SELF_MODEL,
            )
            missing_parent_event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id="wondering:999999:priority:self_growth:resolution:explicit_self_resolved:1",
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 6, tzinfo=UTC),
            )
            unparseable_parent_event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id="subjective-duration:without-parent-wondering",
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 6, 30, tzinfo=UTC),
            )
            sidecarless_parent_id = store.add(
                "sidecarless parent",
                source="manual",
                bond_id="firstborn",
            )
            sidecarless_parent_event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{sidecarless_parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 6, 45, tzinfo=UTC),
            )
            cross_bond_event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{other_parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 7, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )

            with self.assertRaisesRegex(ValueError, "parent wondering"):
                entry.create({"event_id": missing_parent_event_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "parent wondering id required"):
                entry.create({"event_id": unparseable_parent_event_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "missing drive metadata"):
                entry.create({"event_id": sidecarless_parent_event_id, "bond_id": "firstborn"})
            with self.assertRaisesRegex(ValueError, "parent bond_id mismatch"):
                entry.create({"event_id": cross_bond_event_id, "bond_id": "firstborn"})

            self.assertEqual(len(self.curiosity.list_drive_curiosity_objects(store, bond_id="firstborn")), 0)

    def test_subjective_duration_recursion_depth_limit(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            parent_id = store.add("parent recursion object", source="manual", bond_id="firstborn")
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=parent_id,
                bond_id="firstborn",
                encounter_source="subjective_duration_meaningful_event",
                encounter_ref_digest="hmac-sha256:" + "b" * 64,
                priority_class="self_growth",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.SELF_MODEL,
                produced_via_subjective_duration_depth=2,
            )
            event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 3, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
                max_recursion_depth=2,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )

            with self.assertRaisesRegex(ValueError, "recursion depth"):
                entry.create({"event_id": event_id, "bond_id": "firstborn"})

            self.assertEqual(len(self.curiosity.list_drive_curiosity_objects(store, bond_id="firstborn")), 1)

    def test_subjective_duration_recursion_dedupe(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            parent_id = store.add("parent dedupe object", source="manual", bond_id="firstborn")
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=parent_id,
                bond_id="firstborn",
                encounter_source="subjective_duration_meaningful_event",
                encounter_ref_digest="hmac-sha256:" + "e" * 64,
                priority_class="self_growth",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.SELF_MODEL,
            )
            event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 4, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
                recursion_dedupe_window_hours=4,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )
            first = entry.create({"event_id": event_id, "bond_id": "firstborn"})

            with self.assertRaisesRegex(ValueError, "dedupe"):
                entry.create({"event_id": event_id, "bond_id": "firstborn"})

            self.assertEqual(
                len(self.curiosity.list_drive_curiosity_objects(store, bond_id="firstborn")),
                2,
            )
            self.assertEqual(first.produced_via_subjective_duration_depth, 1)

    def test_subjective_duration_subject_kind_refusal_leaves_no_orphan_wondering(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.wonderings import Wonderings

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = Wonderings(db_path=root / "wonderings.db")
            subjective = SubjectiveDuration(
                db_path=root / "subjective_duration.db",
                diagnostic_log_path=root / "subjective_duration.jsonl",
            )
            parent_id = store.add(
                "parent subject-kind object",
                source="manual",
                bond_id="firstborn",
            )
            self.curiosity.record_wondering_drive_metadata(
                store,
                wondering_id=parent_id,
                bond_id="firstborn",
                encounter_source="subjective_duration_meaningful_event",
                encounter_ref_digest="hmac-sha256:" + "f" * 64,
                priority_class="self_growth",
                salience=0.8,
                subject_kind=self.curiosity.SubjectKind.NAMED_THIRD_PARTY,
            )
            event_id = subjective.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,
                bond_id="firstborn",
                producer_event_id=(
                    f"wondering:{parent_id}:priority:self_growth:"
                    "resolution:explicit_self_resolved:1"
                ),
                producer_temperament_before={"curiosity": 5.0},
                producer_temperament_after={"curiosity": 6.0},
                now_utc=datetime(2026, 5, 26, 12, 5, tzinfo=UTC),
            )

            self.curiosity.register_subjective_duration_meaningful_event_producer(
                store,
                subjective,
            )
            entry = self.curiosity.get_registered_producer(
                self.curiosity.EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT
            )

            with self.assertRaises(self.curiosity.SubjectKindRefused):
                entry.create(
                    {
                        "event_id": event_id,
                        "bond_id": "firstborn",
                    }
                )
            with closing(sqlite3.connect(store.db_path)) as con:
                count = con.execute("SELECT COUNT(*) FROM wonderings").fetchone()[0]

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
