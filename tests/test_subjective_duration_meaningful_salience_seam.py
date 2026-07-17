from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "slices" / "track-b-subjective-duration-meaningful-salience-seam" / "spec.md"
SUBJECTIVE = ROOT / "core" / "evolution" / "subjective_duration.py"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke_meaningful_salience_seam_migration.sh"
SCRATCH_CANARY_SCRIPT = ROOT / "scripts" / "scratch_e2e_canary.py"


def _temp_paths(td: str) -> tuple[Path, Path]:
    root = Path(td)
    return root / "subjective_duration.db", root / "subjective_duration.jsonl"


def _all_modulation_values(value: float | None) -> dict[str, float | None]:
    from core.evolution.subjective_duration import MODULATION_TEMPERAMENT_INPUTS

    return {name: value for name in MODULATION_TEMPERAMENT_INPUTS}


def _row_dict(db_path: Path, query: str, params: tuple[object, ...] = ()) -> dict[str, object] | None:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, params).fetchone()
    return None if row is None else dict(row)


def _all_event_columns(db_path: Path) -> dict[str, sqlite3.Row]:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return {
            str(row["name"]): row
            for row in conn.execute("PRAGMA table_info(subjective_duration_salience_events)").fetchall()
        }


def _create_legacy_salience_db(db_path: Path) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE subjective_duration_samples (
                sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                value REAL NOT NULL,
                felt_time_rate REAL NOT NULL,
                drag_multiplier REAL NOT NULL,
                engagement_multiplier REAL NOT NULL,
                residual_resonance REAL NOT NULL,
                retrospective_density REAL NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE subjective_duration_salience_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                salience_event_kind TEXT NOT NULL,
                producer_ref TEXT NOT NULL DEFAULT '',
                owner_auth_class TEXT NOT NULL DEFAULT '',
                source_ref_digest TEXT NOT NULL DEFAULT '',
                meaningfulness_score REAL NOT NULL DEFAULT 0.0,
                meaningfulness_input_count INTEGER NOT NULL DEFAULT 0,
                temperament_delta_mean REAL,
                temperament_delta_max REAL,
                temperament_before_digest TEXT NOT NULL DEFAULT '',
                temperament_after_digest TEXT NOT NULL DEFAULT '',
                explicit_salience_marker_present INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX idx_sd_events_ts
                ON subjective_duration_salience_events(ts_utc);
            INSERT INTO subjective_duration_salience_events (
                ts_utc, salience_event_kind, producer_ref, metadata_json
            ) VALUES (
                '2026-05-25T12:00:00+00:00',
                'manual_test_event',
                'legacy.fixture',
                '{}'
            );
            """
        )


def _record_producer_event(
    sd,
    *,
    bond_id: str = "firstborn",
    producer_event_id: str = "producer-event-1",
    before: dict[str, float | None] | None = None,
    after: dict[str, float | None] | None = None,
    salience_event_kind: str = "meaningful_exchange",
    is_canary: bool = False,
    meaningfulness_score: float | None = None,
    explicit_salience_marker_present: bool = False,
    now_utc: datetime | None = None,
) -> int:
    from core.evolution.subjective_duration import ProducerRef

    return sd.record_salience_event(
        salience_event_kind=salience_event_kind,
        producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
        bond_id=bond_id,
        producer_event_id=producer_event_id,
        producer_temperament_before=before if before is not None else _all_modulation_values(5.0),
        producer_temperament_after=after if after is not None else {**_all_modulation_values(5.0), "curiosity": 6.0},
        is_canary=is_canary,
        meaningfulness_score=meaningfulness_score,
        explicit_salience_marker_present=explicit_salience_marker_present,
        now_utc=now_utc or datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
    )


class SubjectiveDurationMeaningfulSalienceSeamTests(unittest.TestCase):
    def test_schema_migration_adds_five_columns(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)

            columns = _all_event_columns(db_path)

        self.assertEqual(columns["bond_id"]["type"], "TEXT")
        self.assertEqual(columns["bond_id"]["notnull"], 1)
        self.assertEqual(columns["bond_id"]["dflt_value"], "'_LEGACY'")
        for column in [
            "producer_event_id",
            "producer_temperament_before_json",
            "producer_temperament_after_json",
        ]:
            self.assertEqual(columns[column]["type"], "TEXT")
            self.assertEqual(columns[column]["notnull"], 1)
            self.assertEqual(columns[column]["dflt_value"], "''")
        self.assertEqual(columns["is_canary"]["type"], "INTEGER")
        self.assertEqual(columns["is_canary"]["notnull"], 1)
        self.assertEqual(columns["is_canary"]["dflt_value"], "0")

    def test_schema_migration_is_idempotent(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            before = list(_all_event_columns(db_path))
            SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            after = list(_all_event_columns(db_path))

        self.assertEqual(before, after)
        self.assertEqual(len(after), 19)

    def test_schema_migration_preserves_existing_rows(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            row = _row_dict(
                db_path,
                "SELECT bond_id, producer_event_id, producer_temperament_before_json, "
                "producer_temperament_after_json, is_canary FROM subjective_duration_salience_events "
                "WHERE event_id = ?",
                (event_id,),
            )

        self.assertEqual(row["bond_id"], "_LEGACY")
        self.assertEqual(row["producer_event_id"], "")
        self.assertEqual(row["producer_temperament_before_json"], "")
        self.assertEqual(row["producer_temperament_after_json"], "")
        self.assertEqual(row["is_canary"], 0)

    def test_producer_ref_enum_exists_with_manual_test_producer(self):
        from core.evolution.subjective_duration import ProducerRef

        self.assertEqual(ProducerRef.MANUAL_TEST_PRODUCER.value, "manual_test_producer")

    def test_unknown_producer_ref_rejected_on_producer_path(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "unknown producer_ref"):
                sd.record_salience_event(
                    salience_event_kind="meaningful_exchange",
                    producer_ref="unreviewed_free_text",
                    bond_id="firstborn",
                    producer_event_id="event-1",
                    producer_temperament_before=_all_modulation_values(5.0),
                    producer_temperament_after={**_all_modulation_values(5.0), "curiosity": 6.0},
                )

    def test_producer_ref_enum_value_accepted(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = _record_producer_event(sd)

        self.assertGreater(event_id, 0)

    def test_producer_snapshot_path_requires_all_snapshot_kwargs(self):
        from core.evolution.subjective_duration import ProducerRef, SubjectiveDuration

        kwargs = {
            "bond_id": "firstborn",
            "producer_event_id": "event-1",
            "producer_temperament_before": _all_modulation_values(5.0),
            "producer_temperament_after": {**_all_modulation_values(5.0), "curiosity": 6.0},
        }
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            for omitted in kwargs:
                supplied = dict(kwargs)
                supplied.pop(omitted)
                with self.subTest(omitted=omitted):
                    with self.assertRaisesRegex(ValueError, "requires ALL"):
                        sd.record_salience_event(
                            salience_event_kind="meaningful_exchange",
                            producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                            **supplied,
                        )

    def test_producer_snapshot_path_requires_non_empty_bond_id(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "bond_id"):
                _record_producer_event(sd, bond_id="")

    def test_producer_snapshot_path_requires_non_empty_producer_event_id(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "producer_event_id"):
                _record_producer_event(sd, producer_event_id="")

    def test_producer_snapshots_drive_meaningfulness_score(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = _record_producer_event(sd)
            row = _row_dict(
                db_path,
                "SELECT meaningfulness_score, meaningfulness_input_count, temperament_delta_mean, temperament_delta_max "
                "FROM subjective_duration_salience_events WHERE event_id = ?",
                (event_id,),
            )

        self.assertGreater(row["meaningfulness_score"], 0.0)
        self.assertEqual(row["meaningfulness_input_count"], 6)
        self.assertAlmostEqual(row["temperament_delta_mean"], 1.0 / 6.0)
        self.assertAlmostEqual(row["temperament_delta_max"], 1.0)

    def test_producer_snapshot_zero_delta_yields_zero_score(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = _record_producer_event(
                sd,
                before=_all_modulation_values(5.0),
                after=_all_modulation_values(5.0),
            )
            row = _row_dict(db_path, "SELECT meaningfulness_score FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["meaningfulness_score"], 0.0)

    def test_legacy_back_to_back_path_still_structurally_zero(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(
                db_path=db_path,
                diagnostic_log_path=log_path,
                temperament_reader=lambda: {**_all_modulation_values(5.0), "curiosity": 9.0},
            )
            event_id = sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            row = _row_dict(db_path, "SELECT meaningfulness_score, bond_id FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["meaningfulness_score"], 0.0)
        self.assertEqual(row["bond_id"], "_LEGACY")

    def test_legacy_free_text_producer_ref_still_allowed_without_snapshots(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )

        self.assertGreater(event_id, 0)

    def test_lookup_returns_producer_driven_record(self):
        from core.evolution.subjective_duration import MeaningfulSalienceEventRecord, SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = _record_producer_event(sd, bond_id="bond-a", producer_event_id="event-a")
            record = sd.lookup_meaningful_salience_event_record(bond_id="bond-a", producer_event_id="event-a")

        self.assertIsInstance(record, MeaningfulSalienceEventRecord)
        self.assertEqual(record.event_id, event_id)
        self.assertEqual(record.bond_id, "bond-a")
        self.assertEqual(record.producer_event_id, "event-a")
        self.assertGreater(record.meaningfulness_score, 0.0)
        self.assertTrue(record.producer_temperament_before)
        self.assertTrue(record.producer_temperament_after)

    def test_lookup_refuses_empty_bond_id(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "bond_id"):
                sd.lookup_meaningful_salience_event_record(bond_id="", producer_event_id="event-a")

    def test_lookup_refuses_empty_producer_event_id(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "producer_event_id"):
                sd.lookup_meaningful_salience_event_record(bond_id="bond-a", producer_event_id="")

    def test_lookup_preserves_bond_scope(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            _record_producer_event(sd, bond_id="bond-a", producer_event_id="same-id")
            _record_producer_event(sd, bond_id="bond-b", producer_event_id="same-id", after={**_all_modulation_values(5.0), "curiosity": 7.0})
            record = sd.lookup_meaningful_salience_event_record(bond_id="bond-b", producer_event_id="same-id")

        self.assertEqual(record.bond_id, "bond-b")
        self.assertAlmostEqual(record.temperament_delta_max, 2.0)

    def test_lookup_returns_none_for_unknown_pair(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            self.assertIsNone(sd.lookup_meaningful_salience_event_record(bond_id="bond-a", producer_event_id="missing"))

    def test_diagnostic_v2_has_new_fields_for_producer_and_legacy_rows(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            _record_producer_event(sd, bond_id="bond-a", producer_event_id="event-a")
            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        for row in rows:
            self.assertEqual(row["schema_version"], "subjective-duration-diagnostic-v2")
            for key in [
                "bond_id",
                "producer_event_id",
                "producer_temperament_before_json",
                "producer_temperament_after_json",
                "is_canary",
            ]:
                self.assertIn(key, row)
        legacy, producer = rows[0], rows[1]
        self.assertEqual(legacy["bond_id"], "_LEGACY")
        self.assertIsNone(legacy["producer_event_id"])
        self.assertFalse(legacy["is_canary"])
        self.assertEqual(producer["bond_id"], "bond-a")
        self.assertEqual(producer["producer_event_id"], "event-a")

    def test_legacy_explicit_nonzero_meaningfulness_guard_still_requires_marker(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaises(PermissionError):
                sd.record_salience_event(
                    salience_event_kind="meaningful_exchange",
                    producer_ref="legacy.freeform",
                    meaningfulness_score=0.5,
                    now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                )

    def test_producer_auto_compute_does_not_trigger_explicit_score_guard(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = _record_producer_event(sd)

        self.assertGreater(event_id, 0)

    def test_producer_path_rejects_explicit_meaningfulness_score(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "producer-snapshot path auto-computes"):
                _record_producer_event(
                    sd,
                    meaningfulness_score=0.75,
                    explicit_salience_marker_present=True,
                )

    def test_producer_path_rejects_explicit_score_even_for_kind_gated_events(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "producer-snapshot path auto-computes"):
                _record_producer_event(
                    sd,
                    salience_event_kind="manual_test_event",
                    meaningfulness_score=0.75,
                    explicit_salience_marker_present=True,
                )

    def test_migration_smoke_against_production_db_copy(self):
        with tempfile.TemporaryDirectory() as td:
            source_db = Path(td) / "legacy.db"
            scratch_db = Path(td) / "scratch.db"
            _create_legacy_salience_db(source_db)
            result = subprocess.run(
                [os.fspath(SMOKE_SCRIPT), os.fspath(source_db), os.fspath(scratch_db)],
                check=False,
                env={**os.environ, "PYTHON": sys.executable},
                text=True,
                capture_output=True,
            )
            row = _row_dict(
                scratch_db,
                "SELECT bond_id, producer_event_id, producer_temperament_before_json, "
                "producer_temperament_after_json, is_canary FROM subjective_duration_salience_events "
                "WHERE producer_ref = 'legacy.fixture'",
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("meaningful-salience seam migration smoke passed", result.stdout)
        self.assertEqual(row["bond_id"], "_LEGACY")
        self.assertEqual(row["producer_event_id"], "")
        self.assertEqual(row["producer_temperament_before_json"], "")
        self.assertEqual(row["producer_temperament_after_json"], "")
        self.assertEqual(row["is_canary"], 0)

    def test_snapshot_serialization_is_deterministic(self):
        from core.evolution.subjective_duration import _serialize_temperament_snapshot

        left = {"warmth": 6.0, "curiosity": 5.0}
        right = {"curiosity": 5.0, "warmth": 6.0}

        self.assertEqual(_serialize_temperament_snapshot(left), _serialize_temperament_snapshot(right))
        self.assertEqual(_serialize_temperament_snapshot(None), "")

    def test_producer_canary_event_end_to_end(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = _record_producer_event(sd, bond_id="firstborn", producer_event_id="manual-canary")
            record = sd.lookup_meaningful_salience_event_record(bond_id="firstborn", producer_event_id="manual-canary")

        self.assertEqual(record.event_id, event_id)
        self.assertGreater(record.meaningfulness_score, 0.0)

    def test_index_created_on_bond_producer(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            with closing(sqlite3.connect(db_path)) as conn:
                indexes = {
                    row[1]
                    for row in conn.execute("PRAGMA index_list(subjective_duration_salience_events)").fetchall()
                }

        self.assertIn("idx_sd_events_bond_producer", indexes)

    def test_partial_producer_kwargs_refuse_all_one_two_three_of_four_permutations(self):
        from itertools import combinations

        from core.evolution.subjective_duration import ProducerRef, SubjectiveDuration

        producer_kwargs = {
            "bond_id": "firstborn",
            "producer_event_id": "event-a",
            "producer_temperament_before": _all_modulation_values(5.0),
            "producer_temperament_after": {**_all_modulation_values(5.0), "curiosity": 6.0},
        }
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            for size in (1, 2, 3):
                for names in combinations(producer_kwargs, size):
                    supplied = {name: producer_kwargs[name] for name in names}
                    with self.subTest(names=names):
                        with self.assertRaisesRegex(ValueError, "requires ALL"):
                            sd.record_salience_event(
                                salience_event_kind="meaningful_exchange",
                                producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                                **supplied,
                            )

    def test_sovereignty_first_validation_reports_bond_before_bad_producer_ref(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "bond_id"):
                sd.record_salience_event(
                    salience_event_kind="meaningful_exchange",
                    producer_ref="not_reviewed",
                    bond_id="",
                    producer_event_id="event-a",
                    producer_temperament_before=_all_modulation_values(5.0),
                    producer_temperament_after={**_all_modulation_values(5.0), "curiosity": 6.0},
                )

    def test_validation_order_empty_bond_before_empty_producer_ref(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "bond_id"):
                sd.record_salience_event(
                    salience_event_kind="meaningful_exchange",
                    producer_ref="",
                    bond_id="",
                    producer_event_id="event-a",
                    producer_temperament_before=_all_modulation_values(5.0),
                    producer_temperament_after={**_all_modulation_values(5.0), "curiosity": 6.0},
                )

    def test_legacy_sentinel_replaces_empty_string(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            row = _row_dict(db_path, "SELECT bond_id FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["bond_id"], "_LEGACY")

    def test_producer_path_refuses_legacy_sentinel(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "_LEGACY"):
                _record_producer_event(sd, bond_id="_LEGACY")

    def test_legacy_sentinel_refused_at_lookup(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "_LEGACY"):
                sd.lookup_meaningful_salience_event_record(bond_id="_LEGACY", producer_event_id="event-a")

    def test_wildcard_bond_id_refused(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            for bad in {"*", "%", "all", "any"}:
                with self.subTest(path="producer", bad=bad):
                    with self.assertRaisesRegex(ValueError, "wildcard"):
                        _record_producer_event(sd, bond_id=bad)
                with self.subTest(path="lookup", bad=bad):
                    with self.assertRaisesRegex(ValueError, "wildcard"):
                        sd.lookup_meaningful_salience_event_record(bond_id=bad, producer_event_id="event-a")

    def test_kind_gated_zero_score_explicit(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = _record_producer_event(sd, salience_event_kind="engaged_work")
            row = _row_dict(db_path, "SELECT meaningfulness_score, metadata_json FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["meaningfulness_score"], 0.0)
        self.assertEqual(json.loads(row["metadata_json"]), {"kind_gated_zero_score": True})

    def test_is_canary_column_set_explicitly(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = _record_producer_event(sd, is_canary=True)
            row = _row_dict(db_path, "SELECT is_canary, metadata_json FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["is_canary"], 1)
        self.assertNotIn("canary_row", row["metadata_json"])

    def test_manual_test_producer_sunset_signal_present(self):
        text = SPEC.read_text(encoding="utf-8")

        self.assertIn("MANUAL_TEST_PRODUCER", text)
        self.assertIn("Sunset trigger", text)
        self.assertIn("DRIVE_DRIVEN_CURIOSITY", text)

    def test_diagnostic_v2_no_cross_bond_separation_documented(self):
        text = SPEC.read_text(encoding="utf-8")

        self.assertIn("diagnostic stream is a single", text)
        self.assertIn("Track C", text)

    def test_hmac_per_instance_not_per_bond_documented(self):
        text = SPEC.read_text(encoding="utf-8")

        self.assertIn("per-instance", text)
        self.assertIn("not per-bond", text)

    def test_producer_snapshots_match_temperament_log(self):
        from core.evolution.temperament import Temperament
        from core.evolution.subjective_duration import SubjectiveDuration

        def assert_snapshot_matches_temperament_log(
            db_path: Path,
            *,
            before: dict[str, float | None],
            after: dict[str, float | None],
            parameter: str,
        ) -> None:
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT value, prior_value FROM temperament_events "
                    "WHERE parameter = ? ORDER BY event_id DESC LIMIT 1",
                    (parameter,),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], after[parameter])
            self.assertEqual(row[1], before[parameter])

        with tempfile.TemporaryDirectory() as td:
            temperament_db = Path(td) / "temperament.db"
            temp = Temperament(db_path=temperament_db)
            temp.record_event(parameter="curiosity", value=5.0)
            before = temp.current()
            temp.record_event(parameter="curiosity", value=6.0)
            after = temp.current()

            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=Path(td) / "sd.jsonl")
            event_id = _record_producer_event(sd, before=before, after=after)
            assert_snapshot_matches_temperament_log(
                temperament_db,
                before=before,
                after=after,
                parameter="curiosity",
            )

            fake_after = {**after, "curiosity": 8.0}

            with self.assertRaises(AssertionError):
                assert_snapshot_matches_temperament_log(
                    temperament_db,
                    before=before,
                    after=fake_after,
                    parameter="curiosity",
                )
        self.assertGreater(event_id, 0)

    def test_aggregate_reader_residual_resonance_excludes_legacy_and_canary(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            baseline = sd._residual_resonance(now)
            sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref="legacy.freeform",
                meaningfulness_score=1.0,
                explicit_salience_marker_present=True,
                now_utc=now,
            )
            _record_producer_event(sd, is_canary=True, now_utc=now + timedelta(seconds=1))
            after = sd._residual_resonance(now + timedelta(seconds=2))

        self.assertEqual(after, baseline)

    def test_aggregate_reader_recent_meaningful_event_count_excludes_legacy_and_canary(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            baseline = sd._recent_meaningful_event_count_capped(now)
            sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref="legacy.freeform",
                meaningfulness_score=1.0,
                explicit_salience_marker_present=True,
                now_utc=now,
            )
            _record_producer_event(sd, is_canary=True, now_utc=now + timedelta(seconds=1))
            after = sd._recent_meaningful_event_count_capped(now + timedelta(seconds=2))

        self.assertEqual(after, baseline)

    def test_live_path_canary_does_not_pollute_aggregate_readers(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            pre_residual = sd._residual_resonance(now)
            pre_count = sd._recent_meaningful_event_count_capped(now)
            _record_producer_event(
                sd,
                bond_id="firstborn",
                producer_event_id="live-canary",
                salience_event_kind="manual_test_event",
                is_canary=True,
                now_utc=now,
            )
            post_residual = sd._residual_resonance(now + timedelta(seconds=1))
            post_count = sd._recent_meaningful_event_count_capped(now + timedelta(seconds=1))

        self.assertEqual(post_residual, pre_residual)
        self.assertEqual(post_count, pre_count)

    def test_is_canary_column_default_zero(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            row = _row_dict(db_path, "SELECT is_canary FROM subjective_duration_salience_events WHERE event_id = ?", (event_id,))

        self.assertEqual(row["is_canary"], 0)

    def test_diagnostic_v2_schema_version_on_legacy_row(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            _, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=log_path)
            sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="legacy.freeform",
                now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
            )
            row = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(row["schema_version"], "subjective-duration-diagnostic-v2")
        self.assertEqual(row["bond_id"], "_LEGACY")
        self.assertIsNone(row["producer_event_id"])
        self.assertFalse(row["is_canary"])

    def test_is_canary_requires_producer_path(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            with self.assertRaisesRegex(ValueError, "is_canary"):
                sd.record_salience_event(
                    salience_event_kind="manual_test_event",
                    producer_ref="legacy.freeform",
                    is_canary=True,
                    now_utc=datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
                )

    def test_first_observation_none_temperament(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        before = _all_modulation_values(None)
        after = {**_all_modulation_values(None), "curiosity": 6.0}
        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            event_id = _record_producer_event(sd, before=before, after=after)
            row = _row_dict(
                db_path,
                "SELECT meaningfulness_score, meaningfulness_input_count, temperament_delta_mean FROM subjective_duration_salience_events WHERE event_id = ?",
                (event_id,),
            )

        self.assertEqual(row["meaningfulness_score"], 0.0)
        self.assertEqual(row["meaningfulness_input_count"], 0)
        self.assertIsNone(row["temperament_delta_mean"])

    def test_lookup_handles_duplicate_producer_event_id(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            first = _record_producer_event(sd, bond_id="bond-a", producer_event_id="same")
            second = _record_producer_event(sd, bond_id="bond-a", producer_event_id="same", after={**_all_modulation_values(5.0), "curiosity": 7.0})
            record = sd.lookup_meaningful_salience_event_record(bond_id="bond-a", producer_event_id="same")

        self.assertGreater(second, first)
        self.assertEqual(record.event_id, second)

    def test_record_salience_event_is_the_extended_method(self):
        import inspect

        from core.evolution.subjective_duration import SubjectiveDuration

        signature = inspect.signature(SubjectiveDuration.record_salience_event)

        self.assertIn("producer_event_id", signature.parameters)
        self.assertIn("bond_id", signature.parameters)
        self.assertFalse(hasattr(SubjectiveDuration, "record_meaningful_salience_event"))

    def test_default_rollback_preserves_db(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path, log_path = _temp_paths(td)
            sd = SubjectiveDuration(db_path=db_path, diagnostic_log_path=log_path)
            _record_producer_event(sd)
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT ts_utc, salience_event_kind, producer_ref, owner_auth_class, source_ref_digest, "
                    "meaningfulness_score, meaningfulness_input_count, temperament_delta_mean, temperament_delta_max, "
                    "temperament_before_digest, temperament_after_digest, explicit_salience_marker_present, metadata_json "
                    "FROM subjective_duration_salience_events"
                ).fetchone()

        self.assertIsNotNone(row)

    def test_scratch_fixture_sentinel_accepted_at_producer_path(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            event_id = _record_producer_event(sd, bond_id="_SCRATCH_FIXTURE", is_canary=True)

        self.assertGreater(event_id, 0)

    def test_scratch_fixture_sentinel_refused_at_lookup_and_aggregates(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=_temp_paths(td)[0], diagnostic_log_path=_temp_paths(td)[1])
            _record_producer_event(sd, bond_id="_SCRATCH_FIXTURE", is_canary=False, now_utc=now)
            with self.assertRaisesRegex(ValueError, "_SCRATCH_FIXTURE"):
                sd.lookup_meaningful_salience_event_record(
                    bond_id="_SCRATCH_FIXTURE",
                    producer_event_id="producer-event-1",
                )
            residual = sd._residual_resonance(now + timedelta(seconds=1))
            count = sd._recent_meaningful_event_count_capped(now + timedelta(seconds=1))

        self.assertEqual(residual, 0.0)
        self.assertEqual(count, 0.0)

    def test_scratch_canary_runs_end_to_end(self):
        self.assertTrue(SCRATCH_CANARY_SCRIPT.exists(), "scratch E2E canary script must exist")
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sd_scratch.db"
            result = subprocess.run(
                [os.fspath(SCRATCH_CANARY_SCRIPT), os.fspath(db_path)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("scratch E2E canary passed", result.stdout)

    def test_scratch_canary_refuses_existing_db_path(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "existing.db"
            db_path.write_bytes(b"not a scratch db")
            result = subprocess.run(
                [os.fspath(SCRATCH_CANARY_SCRIPT), os.fspath(db_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses to write to an existing DB", result.stderr)

    def test_red_test_table_has_51_entries(self):
        text = SPEC.read_text(encoding="utf-8")
        numbers = {
            int(match.group(1))
            for match in __import__("re").finditer(r"^\| (\d+) \| `test_", text, flags=__import__("re").MULTILINE)
        }

        self.assertEqual(numbers, set(range(1, 52)))

if __name__ == "__main__":
    unittest.main()
