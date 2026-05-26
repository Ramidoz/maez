from __future__ import annotations

import ast
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVE = ROOT / "core" / "evolution" / "drive_driven_curiosity.py"


class CuriosityProducerCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.wonderings_path = root / "wonderings.db"
        self.temperament_path = root / "temperament.db"
        self.subjective_path = root / "subjective_duration.db"
        self.diagnostic_path = root / "subjective_duration.jsonl"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _stores(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.evolution.temperament import Temperament
        from core.evolution.wonderings import Wonderings

        return (
            Wonderings(db_path=self.wonderings_path),
            Temperament(db_path=self.temperament_path),
            SubjectiveDuration(
                db_path=self.subjective_path,
                diagnostic_log_path=self.diagnostic_path,
            ),
        )

    def _curiosity_object(
        self,
        *,
        priority_class: str = "owner_bond",
        salience: float = 0.8,
        subject_kind=None,
    ):
        from core.evolution.drive_driven_curiosity import (
            SubjectKind,
            project_curiosity_object,
            record_wondering_drive_metadata,
        )

        wonderings, _, _ = self._stores()
        wondering_id = wonderings.add(
            "what did that unresolved owner-bond question mean?",
            source="test",
            bond_id="firstborn",
        )
        record_wondering_drive_metadata(
            wonderings,
            wondering_id=wondering_id,
            bond_id="firstborn",
            encounter_source="wondering_generated",
            encounter_ref_digest="hmac-sha256:" + "a" * 64,
            priority_class=priority_class,
            salience=salience,
            subject_kind=subject_kind or SubjectKind.OWNER_BOND_RELATIONAL,
        )
        return project_curiosity_object(wonderings, wondering_id)

    def _row(self, query: str, params: tuple[object, ...] = ()) -> dict[str, object] | None:
        with closing(sqlite3.connect(self.subjective_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(query, params).fetchone()
        return None if row is None else dict(row)

    def test_resolution_temperament_write_caps_daily_budget(self):
        from core.evolution.drive_driven_curiosity import (
            OwnerBondSaturationGuard,
            write_curiosity_resolution_seam_call,
        )
        from core.evolution.temperament import Temperament

        obj = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        temperament.record_event(parameter="curiosity", value=5.0)
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)

        for offset in range(6):
            write_curiosity_resolution_seam_call(
                curiosity_object=obj,
                temperament=temperament,
                subjective_duration=subjective,
                resolution_marker_type="explicit_owner_resolved",
                resolution_marker_utc=now + timedelta(minutes=offset),
                guard=OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=99),
            )

        self.assertLessEqual(Temperament(db_path=self.temperament_path).current_value("curiosity"), 7.0)

    def test_null_first_write_suppressed_when_daily_budget_exhausted(self):
        from core.evolution.drive_driven_curiosity import (
            OwnerBondSaturationGuard,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        events = []

        result = write_curiosity_resolution_seam_call(
            curiosity_object=obj,
            temperament=temperament,
            subjective_duration=subjective,
            resolution_marker_type="explicit_owner_resolved",
            resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            daily_delta_budget=0.0,
            guard=OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=99),
            diagnostic_sink=events.append,
        )

        self.assertIsNone(temperament.current_value("curiosity"))
        self.assertIsNone(result.temperament_event_id)
        self.assertIsNone(result.salience_event_id)
        self.assertEqual(events[0]["event_type"], "TEMPERAMENT_WRITE_CLAMPED")
        self.assertTrue(events[0]["first_observation_suppressed"])

    def test_cross_organ_seam_records_nonzero_meaningfulness_score(self):
        from core.evolution.drive_driven_curiosity import (
            DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF,
            OwnerBondSaturationGuard,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        temperament.record_event(parameter="curiosity", value=5.0)

        result = write_curiosity_resolution_seam_call(
            curiosity_object=obj,
            temperament=temperament,
            subjective_duration=subjective,
            resolution_marker_type="explicit_owner_resolved",
            resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            guard=OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=99),
        )

        record = subjective.lookup_meaningful_salience_event_record(
            bond_id="firstborn",
            producer_event_id=result.producer_event_id,
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.producer_ref, DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF)
        self.assertEqual(record.salience_event_kind, "meaningful_exchange")
        self.assertGreater(record.meaningfulness_score, 0.0)
        self.assertGreater(record.temperament_delta_max, 0.0)

    def test_live_path_canary_seam_row_does_not_pollute_aggregate_readers(self):
        from core.evolution.drive_driven_curiosity import (
            OwnerBondSaturationGuard,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        temperament.record_event(parameter="curiosity", value=5.0)
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        pre_residual = subjective._residual_resonance(now)
        pre_count = subjective._recent_meaningful_event_count_capped(now)

        result = write_curiosity_resolution_seam_call(
            curiosity_object=obj,
            temperament=temperament,
            subjective_duration=subjective,
            resolution_marker_type="explicit_owner_resolved",
            resolution_marker_utc=now,
            guard=OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=99),
            is_canary=True,
        )
        record = subjective.lookup_meaningful_salience_event_record(
            bond_id="firstborn",
            producer_event_id=result.producer_event_id,
        )
        post_residual = subjective._residual_resonance(now + timedelta(seconds=1))
        post_count = subjective._recent_meaningful_event_count_capped(
            now + timedelta(seconds=1)
        )

        self.assertIsNotNone(record)
        self.assertIsNone(result.temperament_event_id)
        self.assertTrue(record.is_canary)
        self.assertGreater(record.meaningfulness_score, 0.0)
        self.assertEqual(temperament.current_value("curiosity"), 5.0)
        self.assertEqual(post_residual, pre_residual)
        self.assertEqual(post_count, pre_count)

    def test_curiosity_producer_refuses_other_salience_event_kinds(self):
        from core.evolution.drive_driven_curiosity import (
            CuriosityAuthorityRefused,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object()
        _, temperament, subjective = self._stores()

        with self.assertRaises(CuriosityAuthorityRefused):
            write_curiosity_resolution_seam_call(
                curiosity_object=obj,
                temperament=temperament,
                subjective_duration=subjective,
                resolution_marker_type="explicit_owner_resolved",
                resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                salience_event_kind="engaged_work",
            )

    def test_curiosity_producer_refuses_other_temperament_parameters(self):
        from core.evolution.drive_driven_curiosity import (
            CuriosityAuthorityRefused,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object()
        _, temperament, subjective = self._stores()

        with self.assertRaises(CuriosityAuthorityRefused):
            write_curiosity_resolution_seam_call(
                curiosity_object=obj,
                temperament=temperament,
                subjective_duration=subjective,
                resolution_marker_type="explicit_owner_resolved",
                resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                temperament_parameter="awareness",
            )

    def test_eligibility_classifier_owner_bond_saturation_floor_caps_meaningful_writes(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            OwnerBondSaturationGuard,
            classify_meaningful_exchange,
            write_curiosity_resolution_seam_call,
        )

        obj = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        temperament.record_event(parameter="curiosity", value=5.0)
        guard = OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=1)
        events = []

        first = classify_meaningful_exchange(
            curiosity_object=obj,
            subjective_duration=subjective,
            guard=guard,
            now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        )
        write_curiosity_resolution_seam_call(
            curiosity_object=obj,
            temperament=temperament,
            subjective_duration=subjective,
            resolution_marker_type="explicit_owner_resolved",
            resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            guard=guard,
        )
        second = classify_meaningful_exchange(
            curiosity_object=obj,
            subjective_duration=subjective,
            guard=guard,
            now_utc=datetime(2026, 5, 25, 13, 0, tzinfo=UTC),
            diagnostic_sink=events.append,
        )

        self.assertEqual(first, MeaningfulExchangeEligibility.ELIGIBLE_OWNER_BOND)
        self.assertEqual(
            second,
            MeaningfulExchangeEligibility.NOT_ELIGIBLE_OWNER_BOND_ROUTINE,
        )
        self.assertEqual(events[0]["reason"], "owner_bond_saturation")

    def test_saturation_guard_counts_owner_bond_events_only(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            OwnerBondSaturationGuard,
            SubjectKind,
            classify_meaningful_exchange,
            write_curiosity_resolution_seam_call,
        )

        self_model = self._curiosity_object(
            priority_class="self_growth",
            salience=1.0,
            subject_kind=SubjectKind.SELF_MODEL,
        )
        owner_bond = self._curiosity_object(salience=1.0)
        _, temperament, subjective = self._stores()
        temperament.record_event(parameter="curiosity", value=5.0)
        guard = OwnerBondSaturationGuard(owner_bond_meaningful_daily_cap=1)

        write_curiosity_resolution_seam_call(
            curiosity_object=self_model,
            temperament=temperament,
            subjective_duration=subjective,
            resolution_marker_type="explicit_self_resolved",
            resolution_marker_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            guard=guard,
        )
        owner_result = classify_meaningful_exchange(
            curiosity_object=owner_bond,
            subjective_duration=subjective,
            guard=guard,
            now_utc=datetime(2026, 5, 25, 13, 0, tzinfo=UTC),
        )

        self.assertEqual(owner_result, MeaningfulExchangeEligibility.ELIGIBLE_OWNER_BOND)

    def test_allowed_sources_extended_for_curiosity(self):
        from core.evolution.temperament import ALLOWED_SOURCES

        self.assertIn("drive_driven_curiosity_resolution", ALLOWED_SOURCES)

    def test_eligibility_classifier_blocks_routine_fact(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            classify_meaningful_exchange,
        )

        obj = self._curiosity_object(priority_class="world_knowledge", salience=0.5)
        _, _, subjective = self._stores()

        self.assertEqual(
            classify_meaningful_exchange(
                curiosity_object=obj,
                subjective_duration=subjective,
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            ),
            MeaningfulExchangeEligibility.NOT_ELIGIBLE_ROUTINE_FACT,
        )

    def test_eligibility_classifier_reads_owner_bond_boundary_blocks(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            classify_meaningful_exchange,
        )

        obj = self._curiosity_object()
        _, _, subjective = self._stores()

        for blocked in (
            {"extraction_shape_blocked": True},
            {"third_party_blocked": True},
        ):
            with self.subTest(blocked=blocked):
                self.assertEqual(
                    classify_meaningful_exchange(
                        curiosity_object=replace(obj, **blocked),
                        subjective_duration=subjective,
                        now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                    ),
                    MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE,
                )

    def test_eligibility_classifier_reads_routine_fact_age_and_advance_count(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            classify_meaningful_exchange,
        )

        obj = self._curiosity_object(priority_class="world_knowledge", salience=0.5)
        _, _, subjective = self._stores()
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)

        self.assertEqual(
            classify_meaningful_exchange(
                curiosity_object=replace(
                    obj,
                    created_at=(now - timedelta(hours=48)).timestamp(),
                    advance_count=2,
                ),
                subjective_duration=subjective,
                now_utc=now,
            ),
            MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE,
        )

    def test_eligibility_classifier_detects_long_carried_resolution(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            classify_meaningful_exchange,
        )

        obj = self._curiosity_object(priority_class="owner_bond", salience=0.8)
        _, _, subjective = self._stores()
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)

        result = classify_meaningful_exchange(
            curiosity_object=replace(
                obj,
                priority_class="world_knowledge",
                created_at=(now - timedelta(days=8)).timestamp(),
                fixation_released=False,
            ),
            subjective_duration=subjective,
            now_utc=now,
        )

        self.assertEqual(
            result,
            MeaningfulExchangeEligibility.ELIGIBLE_LONG_CARRIED_RESOLUTION,
        )

    def test_eligibility_classifier_reads_can_resolve_interiorly_except_owner_bond(self):
        from core.evolution.drive_driven_curiosity import (
            MeaningfulExchangeEligibility,
            classify_meaningful_exchange,
        )

        owner = self._curiosity_object(priority_class="owner_bond")
        world = self._curiosity_object(priority_class="world_knowledge")
        _, _, subjective = self._stores()

        self.assertEqual(
            classify_meaningful_exchange(
                curiosity_object=replace(owner, can_resolve_interiorly=True),
                subjective_duration=subjective,
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            ),
            MeaningfulExchangeEligibility.ELIGIBLE_OWNER_BOND,
        )
        self.assertEqual(
            classify_meaningful_exchange(
                curiosity_object=replace(world, can_resolve_interiorly=True),
                subjective_duration=subjective,
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            ),
            MeaningfulExchangeEligibility.NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY,
        )

    def test_authority_bearing_calls_use_literal_kwargs_and_no_raw_unpacking(self):
        tree = ast.parse(DRIVE.read_text(), filename=str(DRIVE))
        violations = []
        found_temperament_call = False
        found_salience_call = False

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name.endswith(".record_event"):
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                if any(kw.arg is None for kw in node.keywords):
                    violations.append(f"{node.lineno}:record_event uses **kwargs")
                source = kwargs.get("source")
                if isinstance(source, ast.Constant) and source.value == "drive_driven_curiosity_resolution":
                    found_temperament_call = True
                    parameter = kwargs.get("parameter")
                    if not (
                        isinstance(parameter, ast.Constant)
                        and parameter.value == "curiosity"
                    ):
                        violations.append(f"{node.lineno}:record_event parameter not literal curiosity")
            if name.endswith(".record_salience_event"):
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                if any(kw.arg is None for kw in node.keywords):
                    violations.append(f"{node.lineno}:record_salience_event uses **kwargs")
                producer_ref = kwargs.get("producer_ref")
                if (
                    isinstance(producer_ref, ast.Name)
                    and producer_ref.id == "DRIVE_DRIVEN_CURIOSITY_PRODUCER_REF"
                ):
                    found_salience_call = True
                    kind = kwargs.get("salience_event_kind")
                    if not (
                        isinstance(kind, ast.Constant)
                        and kind.value == "meaningful_exchange"
                    ):
                        violations.append(
                            f"{node.lineno}:record_salience_event kind not literal meaningful_exchange"
                        )

        self.assertTrue(found_temperament_call)
        self.assertTrue(found_salience_call)
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
