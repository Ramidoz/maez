from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path


class CuriosityPriorsCleanupTests(unittest.TestCase):
    def tearDown(self):
        from core.evolution import drive_driven_curiosity as ddc

        ddc.clear_encounter_producers_for_tests()

    def test_preference_weight_helpers_are_removed(self):
        from core.evolution import drive_driven_curiosity as ddc

        self.assertFalse(hasattr(ddc, "_priority_class_weight"))
        self.assertFalse(hasattr(ddc, "_marker_confidence_weight"))

    def test_default_producer_requires_explicit_bond_and_uses_neutral_defaults(self):
        from core.evolution import drive_driven_curiosity as ddc

        ddc.register_default_encounter_producers()
        entry = ddc.get_registered_producer(ddc.EncounterSource.WONDERING_GENERATED)

        with self.assertRaisesRegex(ValueError, "bond_id is required"):
            entry.create({})

        obj = entry.create({"bond_id": "firstborn"})

        self.assertEqual(obj.bond_id, "firstborn")
        self.assertEqual(obj.priority_class, "unknown")
        self.assertEqual(obj.subject_kind, ddc.SubjectKind.UNKNOWN)

    def test_owner_bond_priority_uses_general_eligibility_path(self):
        from core.evolution import drive_driven_curiosity as ddc
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            obj = ddc.CuriosityObject(
                wondering_id=1,
                bond_id="firstborn",
                question="can this resolve inside Maez?",
                encounter_source=ddc.EncounterSource.WONDERING_GENERATED.value,
                priority_class="owner_bond",
                salience=1.0,
                subject_kind=ddc.SubjectKind.OWNER_BOND_RELATIONAL,
                can_resolve_interiorly=True,
            )
            result = ddc.classify_meaningful_exchange(
                curiosity_object=obj,
                subjective_duration=SubjectiveDuration(db_path=Path(td) / "subjective.db"),
                now_utc=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
            )

        self.assertEqual(result, ddc.MeaningfulExchangeEligibility.NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY)

    def test_resolution_delta_is_not_scaled_by_category_or_marker(self):
        from core.evolution import drive_driven_curiosity as ddc
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.temperament import Temperament

        with tempfile.TemporaryDirectory() as td:
            obj = ddc.CuriosityObject(
                wondering_id=1,
                bond_id="firstborn",
                question="what did Maez learn about itself?",
                encounter_source=ddc.EncounterSource.WONDERING_GENERATED.value,
                priority_class="self_growth",
                salience=1.0,
                subject_kind=ddc.SubjectKind.SELF_MODEL,
            )
            temperament = Temperament(db_path=Path(td) / "temperament.db")
            temperament.record_event(parameter="curiosity", value=5.0)
            result = ddc.write_curiosity_resolution_seam_call(
                curiosity_object=obj,
                temperament=temperament,
                subjective_duration=SubjectiveDuration(db_path=Path(td) / "subjective.db"),
                resolution_marker_type="explicit_self_resolved",
                resolution_marker_utc=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
            )

        self.assertEqual(result.delta_intent, ddc.BASE_RESOLUTION_DELTA)
        self.assertEqual(result.delta_applied, ddc.BASE_RESOLUTION_DELTA)

    def test_owner_bond_daily_cap_symbols_are_removed(self):
        from core.evolution import drive_driven_curiosity as ddc

        source = Path(ddc.__file__).read_text(encoding="utf-8")

        self.assertNotIn("owner_bond_meaningful_daily_cap", source)
        self.assertNotIn("_count_owner_bond_meaningful_events", source)
        self.assertFalse(hasattr(ddc, "OwnerBondSaturationGuard"))

    def test_named_third_party_without_consent_still_refused(self):
        from core.evolution import drive_driven_curiosity as ddc

        ddc.register_default_encounter_producers()
        entry = ddc.get_registered_producer(ddc.EncounterSource.WONDERING_GENERATED)

        with self.assertRaises(ddc.SubjectKindRefused):
            entry.create(
                {
                    "bond_id": "firstborn",
                    "subject_kind": ddc.SubjectKind.NAMED_THIRD_PARTY,
                    "subject_ref": "person:unconsented",
                }
            )

    def test_subject_kind_omission_still_refused(self):
        from core.evolution import drive_driven_curiosity as ddc
        from core.evolution.subjective_duration import ProducerRef

        ddc.register_encounter_producer(
            source=ddc.EncounterSource.WONDERING_GENERATED,
            evidence_pointer_kind="wonderings.id",
            producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY,
            create_curiosity_object=lambda seed: {
                "wondering_id": 1,
                "bond_id": "firstborn",
                "question": "what should Maez learn here?",
                "encounter_source": "wondering_generated",
                "priority_class": "unknown",
                "salience": 0.7,
            },
        )
        entry = ddc.get_registered_producer(ddc.EncounterSource.WONDERING_GENERATED)

        with self.assertRaises(ddc.SubjectKindRefused):
            entry.create({})

    def test_register_default_encounter_producers_has_no_live_caller(self):
        root = Path(__file__).resolve().parents[1]
        callers = []
        for dirname in ("core", "daemon"):
            for path in (root / dirname).rglob("*.py"):
                if path.name == "drive_driven_curiosity.py":
                    continue
                text = path.read_text(encoding="utf-8")
                if "register_default_encounter_producers(" in text:
                    callers.append(str(path.relative_to(root)))

        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
