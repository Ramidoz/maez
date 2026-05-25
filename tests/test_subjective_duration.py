from __future__ import annotations

import json
import math
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


DIAGNOSTIC_KEYS = {
    "schema_version",
    "timestamp_utc",
    "event_type",
    "value",
    "felt_time_rate",
    "render_band",
    "residual_resonance",
    "retrospective_density",
    "salience_event_kind",
    "producer_ref",
    "owner_auth_class",
    "source_ref_digest",
    "source_ref_present",
    "meaningfulness_score",
    "meaningfulness_input_count",
    "temperament_delta_mean",
    "temperament_delta_max",
    "temperament_before_digest",
    "temperament_after_digest",
    "explicit_salience_marker_present",
    "bond_id",
    "producer_event_id",
    "producer_temperament_before_json",
    "producer_temperament_after_json",
    "is_canary",
    "content_recorded",
}

HMAC_SHA256_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")


class SubjectiveDurationSubstrateTests(unittest.TestCase):
    def test_public_exports_include_scalar_constants_snapshot_and_typed_owner_auth(self):
        from core.evolution.subjective_duration import (
            SUBJECTIVE_DURATION_MAX,
            SUBJECTIVE_DURATION_MIN,
            SubjectiveDurationOwnerAuth,
            SubjectiveDurationSnapshot,
        )

        self.assertEqual(SUBJECTIVE_DURATION_MIN, 0.0)
        self.assertEqual(SUBJECTIVE_DURATION_MAX, 10.0)
        self.assertTrue(is_dataclass(SubjectiveDurationSnapshot))
        self.assertEqual(
            [field.name for field in fields(SubjectiveDurationSnapshot)],
            [
                "value",
                "felt_time_rate",
                "residual_resonance",
                "retrospective_density",
                "render_band",
                "surface_phrase",
                "source_ref_digest",
            ],
        )
        self.assertTrue(is_dataclass(SubjectiveDurationOwnerAuth))
        self.assertEqual([field.name for field in fields(SubjectiveDurationOwnerAuth)], ["surface", "proof"])
        with self.assertRaises(ValueError):
            SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="manual_test")

    def test_fresh_store_exposes_prompt_safe_snapshot_and_sample_row(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / "subjective_duration.db"
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(db_path=store, diagnostic_log_path=log_path)

            snap = sd.current(now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))

            self.assertEqual(snap.value, 0.0)
            self.assertEqual(snap.render_band, "light")
            self.assertEqual(snap.surface_phrase, "time feels light right now")
            self.assertIn("time feels light right now", sd.perception_line())
            self.assertNotIn("2026-", sd.perception_line())
            self.assertNotIn("seconds", sd.perception_line().lower())

            row = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(set(row), DIAGNOSTIC_KEYS)
            self.assertEqual(row["schema_version"], "subjective-duration-diagnostic-v2")
            self.assertEqual(row["event_type"], "sample")
            self.assertIsNone(row["salience_event_kind"])
            self.assertIsNone(row["producer_ref"])
            self.assertIsNone(row["owner_auth_class"])
            self.assertIsNone(row["source_ref_digest"])
            self.assertFalse(row["source_ref_present"])
            self.assertIsNone(row["meaningfulness_score"])
            self.assertIsNone(row["meaningfulness_input_count"])
            self.assertIsNone(row["temperament_delta_mean"])
            self.assertIsNone(row["temperament_delta_max"])
            self.assertIsNone(row["temperament_before_digest"])
            self.assertIsNone(row["temperament_after_digest"])
            self.assertIsNone(row["bond_id"])
            self.assertIsNone(row["producer_event_id"])
            self.assertIsNone(row["producer_temperament_before_json"])
            self.assertIsNone(row["producer_temperament_after_json"])
            self.assertFalse(row["is_canary"])
            self.assertFalse(row["explicit_salience_marker_present"])
            self.assertFalse(row["content_recorded"])

    def test_phrase_mapping_is_read_time_only_and_uses_spec_thresholds(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "subjective_duration.db"
            sd = SubjectiveDuration(
                db_path=db_path,
                diagnostic_log_path=Path(td) / "subjective_duration.jsonl",
            )
            sd.current(now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))

            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    "UPDATE subjective_duration_samples "
                    "SET value = ?, metadata_json = ? "
                    "WHERE sample_id = (SELECT MAX(sample_id) FROM subjective_duration_samples)",
                    (
                        1.5,
                        json.dumps(
                            {
                                "render_band": "light",
                                "surface_phrase": "stale stored phrase must not win",
                            }
                        ),
                    ),
                )
                conn.commit()

            line = sd.perception_line()

            self.assertIn("time has a little stretch to it", line)
            self.assertNotIn("stale stored phrase", line)

    def test_compute_update_is_continuous_bounded_and_rejects_bad_multipliers(self):
        from core.evolution.subjective_duration import (
            SubjectiveDurationConfig,
            compute_subjective_duration_update,
        )

        config = SubjectiveDurationConfig()

        value = compute_subjective_duration_update(
            prior_value=0.0,
            delta_hours=6.0,
            drag_multiplier=1.0,
            engagement_multiplier=0.4,
            residual_multiplier=1.0,
            config=config,
        )
        self.assertGreater(value, 0.0)
        self.assertLessEqual(value, 10.0)

        saturated = compute_subjective_duration_update(
            prior_value=9.99,
            delta_hours=100.0,
            drag_multiplier=1.75,
            engagement_multiplier=0.4,
            residual_multiplier=1.35,
            config=config,
        )
        self.assertGreaterEqual(saturated, 0.0)
        self.assertLessEqual(saturated, 10.0)

        for bad in (-1.0, math.nan, math.inf):
            with self.assertRaises(ValueError):
                compute_subjective_duration_update(
                    prior_value=1.0,
                    delta_hours=1.0,
                    drag_multiplier=bad,
                    engagement_multiplier=1.0,
                    residual_multiplier=1.0,
                    config=config,
                )

        for bad_prior in (math.nan, math.inf):
            with self.assertRaises(ValueError):
                compute_subjective_duration_update(
                    prior_value=bad_prior,
                    delta_hours=1.0,
                    drag_multiplier=1.0,
                    engagement_multiplier=1.0,
                    residual_multiplier=1.0,
                    config=config,
                )

    def test_temporal_spine_normalizes_event_at_and_rejects_naive_datetimes(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=log_path)

            with self.assertRaises(ValueError):
                sd.current(now_utc=datetime(2026, 5, 24, 12, 0))

            event_id = sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="test:temporal-spine",
                source_ref="event source must only be digested",
                now_utc="2026-05-24T07:30:00-05:00",
            )

            self.assertGreater(event_id, 0)
            row = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(row["timestamp_utc"], "2026-05-24T12:30:00+00:00")

            with closing(sqlite3.connect(Path(td) / "sd.db")) as conn:
                ts_utc = conn.execute(
                    "SELECT ts_utc FROM subjective_duration_salience_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()[0]
            self.assertEqual(ts_utc, "2026-05-24T12:30:00+00:00")

    def test_sqlite_tables_are_append_only_and_reinstantiate_from_same_db(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "subjective_duration.db"
            first = SubjectiveDuration(db_path=db_path, diagnostic_log_path=Path(td) / "first.jsonl")
            base = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
            first.current(now_utc=base)
            first.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="test:append-only",
                meaningfulness_score=0.5,
                explicit_salience_marker_present=True,
                now_utc=base + timedelta(minutes=5),
            )
            first_value = first.current(now_utc=base + timedelta(hours=2)).value

            with closing(sqlite3.connect(db_path)) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                sample_count_before = conn.execute(
                    "SELECT COUNT(*) FROM subjective_duration_samples"
                ).fetchone()[0]
                event_count_before = conn.execute(
                    "SELECT COUNT(*) FROM subjective_duration_salience_events"
                ).fetchone()[0]
                sample_columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(subjective_duration_samples)").fetchall()
                }
                event_columns = {
                    row[1]: row
                    for row in conn.execute(
                        "PRAGMA table_info(subjective_duration_salience_events)"
                    ).fetchall()
                }

            self.assertIn("subjective_duration_samples", tables)
            self.assertIn("subjective_duration_salience_events", tables)
            self.assertIn("drag_multiplier", sample_columns)
            self.assertIn("engagement_multiplier", sample_columns)
            self.assertIn("metadata_json", sample_columns)
            for column in [
                "owner_auth_class",
                "source_ref_digest",
                "temperament_before_digest",
                "temperament_after_digest",
            ]:
                self.assertEqual(event_columns[column][3], 1, column)
                self.assertIsNotNone(event_columns[column][4], column)
            self.assertGreaterEqual(sample_count_before, 2)
            self.assertEqual(event_count_before, 1)

            second = SubjectiveDuration(db_path=db_path, diagnostic_log_path=Path(td) / "second.jsonl")
            second_value = second.current(now_utc=base + timedelta(hours=3)).value
            self.assertGreaterEqual(second_value, first_value)

            with closing(sqlite3.connect(db_path)) as conn:
                sample_count_after = conn.execute(
                    "SELECT COUNT(*) FROM subjective_duration_samples"
                ).fetchone()[0]
                event_count_after = conn.execute(
                    "SELECT COUNT(*) FROM subjective_duration_salience_events"
                ).fetchone()[0]

            self.assertGreater(sample_count_after, sample_count_before)
            self.assertEqual(event_count_after, event_count_before)

    def test_temperament_modulation_makes_engaged_flow_lighter_than_idle(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        later = now + timedelta(hours=6)
        idle = {
            "curiosity": 1.0,
            "awareness": 1.0,
            "persistence": 1.0,
            "joy": 1.0,
            "warmth": 1.0,
            "caution": 8.0,
        }
        engaged = {
            "curiosity": 9.0,
            "awareness": 9.0,
            "persistence": 9.0,
            "joy": 8.0,
            "warmth": 8.0,
            "caution": 2.0,
        }

        with tempfile.TemporaryDirectory() as td:
            idle_sd = SubjectiveDuration(
                db_path=Path(td) / "idle.db",
                diagnostic_log_path=Path(td) / "idle.jsonl",
                temperament_reader=lambda: idle,
            )
            engaged_sd = SubjectiveDuration(
                db_path=Path(td) / "engaged.db",
                diagnostic_log_path=Path(td) / "engaged.jsonl",
                temperament_reader=lambda: engaged,
            )
            idle_sd.current(now_utc=now)
            engaged_sd.current(now_utc=now)

            idle_value = idle_sd.current(now_utc=later).value
            engaged_value = engaged_sd.current(now_utc=later).value

            self.assertGreater(idle_value, engaged_value)

    def test_caution_drag_increases_felt_time_without_crossing_scalar_bounds(self):
        from core.evolution.subjective_duration import (
            SUBJECTIVE_DURATION_MAX,
            SUBJECTIVE_DURATION_MIN,
            SubjectiveDuration,
        )

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        later = now + timedelta(hours=6)
        low_caution = {
            "curiosity": 5.0,
            "awareness": 5.0,
            "persistence": 5.0,
            "joy": 5.0,
            "warmth": 5.0,
            "caution": 0.0,
        }
        high_caution = {**low_caution, "caution": 10.0}

        with tempfile.TemporaryDirectory() as td:
            low_sd = SubjectiveDuration(
                db_path=Path(td) / "low.db",
                diagnostic_log_path=Path(td) / "low.jsonl",
                temperament_reader=lambda: low_caution,
            )
            high_sd = SubjectiveDuration(
                db_path=Path(td) / "high.db",
                diagnostic_log_path=Path(td) / "high.jsonl",
                temperament_reader=lambda: high_caution,
            )
            low_sd.current(now_utc=now)
            high_sd.current(now_utc=now)

            low = low_sd.current(now_utc=later)
            high = high_sd.current(now_utc=later)

            self.assertGreater(high.value, low.value)
            self.assertGreaterEqual(high.value, SUBJECTIVE_DURATION_MIN)
            self.assertLessEqual(high.value, SUBJECTIVE_DURATION_MAX)
            high_row = json.loads((Path(td) / "high.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            low_row = json.loads((Path(td) / "low.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertGreater(high_row["felt_time_rate"], low_row["felt_time_rate"])

    def test_owner_contact_requires_typed_auth_and_event_row_is_non_reconstructive(self):
        from core.evolution.subjective_duration import SubjectiveDuration, SubjectiveDurationOwnerAuth

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=log_path)
            sd.current(now_utc=now)
            before = sd.current(now_utc=now + timedelta(hours=8)).value
            with self.assertRaises(PermissionError):
                sd.record_salience_event(
                    salience_event_kind="owner_contact",
                    producer_ref="test:public-web",
                    source_ref="unauthenticated public text",
                    now_utc=now + timedelta(hours=8, minutes=1),
                )
            with self.assertRaises((PermissionError, TypeError, ValueError)):
                sd.record_salience_event(
                    salience_event_kind="owner_contact",
                    producer_ref="test:forged",
                    source_ref="string labels are not typed auth",
                    owner_auth="telegram_owner",
                    now_utc=now + timedelta(hours=8, minutes=1),
                )
            self.assertEqual("", sd.perception_line(owner_auth="telegram_owner"))
            event_id = sd.record_salience_event(
                salience_event_kind="owner_contact",
                producer_ref="test:owner",
                source_ref="raw owner text must not appear",
                owner_auth=SubjectiveDurationOwnerAuth(
                    surface="telegram_owner",
                    proof="telegram_authorized_user",
                ),
                now_utc=now + timedelta(hours=8, minutes=1),
            )
            after = sd.current(now_utc=now + timedelta(hours=8, minutes=2)).value

            self.assertGreater(event_id, 0)
            self.assertGreater(before, 0.0)
            self.assertGreater(after, 0.0)

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            event_rows = [row for row in rows if row["event_type"] == "salience_event"]
            self.assertEqual(len(event_rows), 1)
            event = event_rows[0]
            self.assertEqual(set(event), DIAGNOSTIC_KEYS)
            self.assertEqual(event["salience_event_kind"], "owner_contact")
            self.assertEqual(event["owner_auth_class"], "telegram_owner")
            self.assertEqual(event["bond_id"], "_LEGACY")
            self.assertIsNone(event["producer_event_id"])
            self.assertFalse(event["is_canary"])
            self.assertRegex(event["source_ref_digest"], HMAC_SHA256_RE)
            self.assertTrue(event["source_ref_present"])
            self.assertNotIn("raw owner text", json.dumps(event))
            self.assertEqual(event["content_recorded"], False)

    def test_meaningfulness_defaults_zero_and_trace_fields_are_bounded(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(
                db_path=Path(td) / "sd.db",
                diagnostic_log_path=log_path,
                temperament_reader=lambda: {
                    "curiosity": None,
                    "awareness": None,
                    "persistence": None,
                    "joy": None,
                    "warmth": None,
                    "caution": None,
                },
            )

            sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref="test:exchange",
                source_ref="dramatic words do not matter by themselves",
                now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
            )

            row = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(row["meaningfulness_score"], 0.0)
            self.assertEqual(row["meaningfulness_input_count"], 0)
            self.assertIsNone(row["temperament_delta_mean"])
            self.assertIsNone(row["temperament_delta_max"])
            self.assertRegex(row["temperament_before_digest"], HMAC_SHA256_RE)
            self.assertRegex(row["temperament_after_digest"], HMAC_SHA256_RE)
            self.assertFalse(row["explicit_salience_marker_present"])
            self.assertRegex(row["source_ref_digest"], HMAC_SHA256_RE)
            self.assertNotIn("dramatic words", json.dumps(row))

            with self.assertRaises(ValueError):
                sd.record_salience_event(
                    salience_event_kind="manual_test_event",
                    producer_ref="test:bad-meaningfulness",
                    meaningfulness_score=math.nan,
                    explicit_salience_marker_present=True,
                    now_utc=datetime(2026, 5, 24, 12, 1, tzinfo=UTC),
                )

    def test_residual_echo_half_life_and_bounded_lookback(self):
        from core.evolution.subjective_duration import ProducerRef, SubjectiveDuration

        base = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        before = {
            "curiosity": 0.0,
            "awareness": 0.0,
            "persistence": 0.0,
            "joy": 0.0,
            "warmth": 0.0,
            "caution": 0.0,
        }
        after = {name: 10.0 for name in before}
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(
                db_path=Path(td) / "sd.db",
                diagnostic_log_path=Path(td) / "sd.jsonl",
            )
            sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                bond_id="firstborn",
                producer_event_id="half-life",
                producer_temperament_before=before,
                producer_temperament_after=after,
                now_utc=base,
            )

            at_four = sd.current(now_utc=base + timedelta(hours=4))
            at_eight = sd.current(now_utc=base + timedelta(hours=8))
            outside = sd.current(now_utc=base + timedelta(hours=25))

            self.assertAlmostEqual(at_four.residual_resonance, 0.5, delta=0.08)
            self.assertAlmostEqual(at_eight.residual_resonance, 0.25, delta=0.08)
            self.assertEqual(outside.residual_resonance, 0.0)

    def test_retrospective_density_meaningful_event_count_caps_after_three(self):
        from core.evolution.subjective_duration import ProducerRef, SubjectiveDuration

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        before = {
            "curiosity": 0.0,
            "awareness": 0.0,
            "persistence": 0.0,
            "joy": 0.0,
            "warmth": 0.0,
            "caution": 0.0,
        }
        after = {name: 10.0 for name in before}
        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(
                db_path=Path(td) / "sd.db",
                diagnostic_log_path=Path(td) / "sd.jsonl",
                temperament_reader=lambda: {
                    "curiosity": 0.0,
                    "awareness": 0.0,
                    "persistence": 0.0,
                    "joy": 0.0,
                    "warmth": 0.0,
                    "caution": 0.0,
                },
            )
            sd.current(now_utc=now)
            baseline = sd.current(now_utc=now + timedelta(minutes=1)).retrospective_density
            for index in range(3):
                sd.record_salience_event(
                    salience_event_kind="meaningful_exchange",
                    producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                    bond_id="firstborn",
                    producer_event_id=f"meaningful:{index}",
                    producer_temperament_before=before,
                    producer_temperament_after=after,
                    now_utc=now + timedelta(minutes=index + 2),
                )

            density_after_three = sd._recent_meaningful_event_count_capped(
                now + timedelta(minutes=10)
            )
            sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref=ProducerRef.MANUAL_TEST_PRODUCER.value,
                bond_id="firstborn",
                producer_event_id="meaningful:extra",
                producer_temperament_before=before,
                producer_temperament_after=after,
                now_utc=now + timedelta(minutes=6),
            )
            density_after_four = sd._recent_meaningful_event_count_capped(
                now + timedelta(minutes=10)
            )

            self.assertEqual(baseline, 0.0)
            self.assertEqual(density_after_three, 1.0)
            self.assertEqual(density_after_four, 1.0)

    def test_clock_moving_backward_records_degraded_event_and_returns_safe_value(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        base = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=log_path)
            sd.current(now_utc=base)
            safe = sd.current(now_utc=base + timedelta(hours=3))
            degraded = sd.current(now_utc=base + timedelta(hours=2, minutes=30))

            self.assertEqual(degraded.value, safe.value)
            self.assertGreaterEqual(degraded.value, 0.0)
            self.assertLessEqual(degraded.value, 10.0)

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            degraded_rows = [
                row
                for row in rows
                if row["event_type"] == "salience_event"
                and row["salience_event_kind"] == "clock_degraded_event"
            ]
            self.assertEqual(len(degraded_rows), 1)
            self.assertFalse(degraded_rows[0]["content_recorded"])
            self.assertEqual(degraded_rows[0]["source_ref_digest"], "")
            self.assertFalse(degraded_rows[0]["source_ref_present"])

    def test_diagnostics_have_full_row_shape_and_exclude_raw_private_fields(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subjective_duration.jsonl"
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db", diagnostic_log_path=log_path)
            sd.current(now_utc=now)
            sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="test:diagnostics",
                source_ref="raw prompt and memory payload must not be logged",
                now_utc=now + timedelta(minutes=1),
            )

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertGreaterEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(set(row), DIAGNOSTIC_KEYS)
                serialized = json.dumps(row).lower()
                for forbidden_fragment in [
                    "raw prompt",
                    "memory payload",
                    "watchdog",
                    "halt",
                    "telegram_text",
                    "prompt_text",
                    "raw_source_ref",
                    "memory_content",
                ]:
                    self.assertNotIn(forbidden_fragment, serialized)

            sample = next(row for row in rows if row["event_type"] == "sample")
            event = next(row for row in rows if row["event_type"] == "salience_event")
            for key in [
                "salience_event_kind",
                "producer_ref",
                "owner_auth_class",
                "source_ref_digest",
                "meaningfulness_score",
                "meaningfulness_input_count",
                "temperament_delta_mean",
                "temperament_delta_max",
                "temperament_before_digest",
                "temperament_after_digest",
                "bond_id",
                "producer_event_id",
                "producer_temperament_before_json",
                "producer_temperament_after_json",
            ]:
                self.assertIsNone(sample[key], key)
            self.assertIs(sample["source_ref_present"], False)
            self.assertIs(sample["explicit_salience_marker_present"], False)
            self.assertIs(sample["is_canary"], False)
            self.assertIs(sample["content_recorded"], False)
            self.assertRegex(event["source_ref_digest"], HMAC_SHA256_RE)
            self.assertIs(event["source_ref_present"], True)
            self.assertIs(event["content_recorded"], False)

            sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="test:no-source",
                source_ref=None,
                now_utc=now + timedelta(minutes=2),
            )
            no_source = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(no_source["source_ref_digest"], "")
            self.assertIs(no_source["source_ref_present"], False)
            sd.record_salience_event(
                salience_event_kind="manual_test_event",
                producer_ref="test:empty-source",
                source_ref="",
                now_utc=now + timedelta(minutes=3),
            )
            empty_source = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(empty_source["source_ref_digest"], "")
            self.assertIs(empty_source["source_ref_present"], False)

    def test_retrospective_density_tracks_engagement_and_meaningful_events(self):
        from core.evolution.subjective_duration import SubjectiveDuration

        now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
        idle = {
            "curiosity": 1.0,
            "awareness": 1.0,
            "persistence": 1.0,
            "joy": 1.0,
            "warmth": 1.0,
            "caution": 5.0,
        }
        engaged = {
            "curiosity": 9.0,
            "awareness": 9.0,
            "persistence": 9.0,
            "joy": 9.0,
            "warmth": 9.0,
            "caution": 5.0,
        }

        with tempfile.TemporaryDirectory() as td:
            idle_sd = SubjectiveDuration(
                db_path=Path(td) / "idle.db",
                diagnostic_log_path=Path(td) / "idle.jsonl",
                temperament_reader=lambda: idle,
            )
            engaged_sd = SubjectiveDuration(
                db_path=Path(td) / "engaged.db",
                diagnostic_log_path=Path(td) / "engaged.jsonl",
                temperament_reader=lambda: engaged,
            )
            idle_sd.current(now_utc=now)
            engaged_sd.current(now_utc=now)
            engaged_sd.record_salience_event(
                salience_event_kind="meaningful_exchange",
                producer_ref="test:meaningful",
                meaningfulness_score=1.0,
                explicit_salience_marker_present=True,
                now_utc=now + timedelta(minutes=5),
            )

            idle_density = idle_sd.current(now_utc=now + timedelta(hours=6)).retrospective_density
            engaged_density = engaged_sd.current(now_utc=now + timedelta(hours=6)).retrospective_density

            self.assertGreater(engaged_density, idle_density)
            self.assertGreaterEqual(engaged_density, 0.0)
            self.assertLessEqual(engaged_density, 1.0)

    def test_registry_contract_and_unknown_kind_refusal(self):
        from core.evolution.subjective_duration import (
            SalienceEventDefinition,
            SubjectiveDuration,
            build_salience_event_registry,
        )

        registry = build_salience_event_registry()
        self.assertEqual(
            set(registry),
            {
                "owner_contact",
                "meaningful_exchange",
                "engaged_work",
                "idle_cycle",
                "public_stranger_contact",
                "manual_test_event",
                "clock_degraded_event",
            },
        )
        self.assertIsInstance(registry["owner_contact"], SalienceEventDefinition)
        self.assertTrue(registry["owner_contact"].owner_auth_required)
        self.assertIn("residual_resonance", registry["meaningful_exchange"].affects)

        with tempfile.TemporaryDirectory() as td:
            sd = SubjectiveDuration(db_path=Path(td) / "sd.db")
            with self.assertRaises(ValueError):
                sd.record_salience_event(
                    salience_event_kind="unreviewed_new_feeling",
                    producer_ref="test",
                )


if __name__ == "__main__":
    unittest.main()
