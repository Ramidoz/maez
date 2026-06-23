from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


class SelfCardTimeLineTests(unittest.TestCase):
    def test_high_percentile_gap_renders_factual_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 8 * 3600,
            "rhythm_recent_gap_median_s": 24 * 60,
            "rhythm_all_time_gap_median_s": 8 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 226,
            "rhythm_current_gap_percentile_all_time": 91.2,
            "rhythm_recent_gap_iqr_s": None,
            "rhythm_all_time_gap_iqr_s": None,
        }

        line = build_self_card_time_line(lambda: ctx)

        self.assertIsNotNone(line)
        self.assertEqual(line.label, "Time since contact")
        self.assertIn("~8h", line.text)
        self.assertIn("recent usual ~24m", line.text)
        self.assertIn("all-time usual ~8m", line.text)
        self.assertIn("above ~91% of recorded gaps", line.text)
        for forbidden in (
            "miss",
            "lonely",
            "worried",
            "longing",
            "sad",
            "happy",
            "comfort",
            "feel",
        ):
            self.assertNotIn(forbidden, line.text.lower())
        self.assertEqual(line.reason, "percentile_high")

    def test_short_unremarkable_gap_omits_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 4.0,
            "rhythm_recent_gap_median_s": 20 * 60,
            "rhythm_all_time_gap_median_s": 30 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 100,
            "rhythm_current_gap_percentile_all_time": 40.0,
        }

        self.assertIsNone(build_self_card_time_line(lambda: ctx))

    def test_cold_start_under_floor_omits_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 5 * 60,
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_recent_sample_count": 1,
            "rhythm_all_time_sample_count": 1,
            "rhythm_current_gap_percentile_all_time": None,
        }

        self.assertIsNone(build_self_card_time_line(lambda: ctx))

    def test_cold_start_after_floor_renders_learning_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 30 * 60,
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_recent_sample_count": 1,
            "rhythm_all_time_sample_count": 1,
            "rhythm_current_gap_percentile_all_time": None,
        }

        line = build_self_card_time_line(lambda: ctx)

        self.assertIsNotNone(line)
        self.assertIn("~30m since owner contact", line.text)
        self.assertIn("still learning the usual rhythm", line.text)
        self.assertEqual(line.reason, "cold_start_elapsed_floor")

    def test_provider_error_returns_none(self):
        from core.routing.self_card_time import build_self_card_time_line

        def broken():
            raise RuntimeError("boom")

        self.assertIsNone(build_self_card_time_line(broken))

    def test_receipt_is_content_light(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 8 * 3600,
            "rhythm_recent_gap_median_s": 24 * 60,
            "rhythm_all_time_gap_median_s": 8 * 60,
            "rhythm_recent_sample_count": 20,
            "rhythm_all_time_sample_count": 226,
            "rhythm_current_gap_percentile_all_time": 91.2,
        }
        line = build_self_card_time_line(lambda: ctx)
        receipt = line.receipt()

        self.assertEqual(receipt["time_line_reason"], "percentile_high")
        self.assertEqual(receipt["time_line_source"], "subjective_duration.rhythm_context")
        self.assertIn("time_line_sha256", receipt)
        self.assertNotIn("8h", str(receipt))
        self.assertNotIn("owner contact", str(receipt))

    def test_default_provider_reads_existing_store_without_sample_or_event_write(self):
        from core.evolution.subjective_duration import SubjectiveDuration
        from core.routing.self_card_time import build_self_card_time_line, rhythm_time_line_provider

        root = tempfile.mkdtemp()
        inst = SubjectiveDuration(db_path=os.path.join(root, "subjective_duration.db"))
        t0 = datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc)
        inst.current(now_utc=t0)
        with closing(sqlite3.connect(inst.db_path)) as conn:
            conn.execute(
                "INSERT INTO subjective_duration_salience_events "
                "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
                (t0.isoformat(), "owner_contact", "cockpit", 0),
            )
            conn.commit()
            before = (
                conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0],
            )

        line = build_self_card_time_line(
            lambda: rhythm_time_line_provider(db_path=inst.db_path, now=t0 + timedelta(minutes=30))
        )

        with closing(sqlite3.connect(inst.db_path)) as conn:
            after = (
                conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0],
            )
        self.assertIsNotNone(line)
        self.assertEqual(before, after)

    def test_default_provider_returns_none_when_store_missing(self):
        from core.routing.self_card_time import rhythm_time_line_provider

        missing = os.path.join(tempfile.mkdtemp(), "missing-subjective-duration.db")

        self.assertIsNone(rhythm_time_line_provider(db_path=missing))
        self.assertFalse(os.path.exists(missing))

    def test_default_provider_returns_none_for_zero_byte_file_without_writing(self):
        from core.routing.self_card_time import rhythm_time_line_provider

        path = Path(tempfile.mkdtemp()) / "empty-subjective-duration.db"
        path.touch()
        before = path.stat()

        self.assertIsNone(rhythm_time_line_provider(db_path=path))

        after = path.stat()
        self.assertEqual(after.st_size, 0)
        self.assertEqual(before.st_size, after.st_size)

    def test_default_provider_returns_none_for_malformed_nonempty_db_without_writing(self):
        from core.routing.self_card_time import rhythm_time_line_provider

        path = Path(tempfile.mkdtemp()) / "malformed-subjective-duration.db"
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("CREATE TABLE unrelated_table (id INTEGER PRIMARY KEY)")
            conn.commit()
        before_bytes = path.read_bytes()

        self.assertIsNone(rhythm_time_line_provider(db_path=path))

        self.assertEqual(path.read_bytes(), before_bytes)

    def test_invalid_percentile_range_omits_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        for percentile in (-0.1, 100.1):
            with self.subTest(percentile=percentile):
                ctx = {
                    "rhythm_current_gap_s": 8 * 3600,
                    "rhythm_recent_gap_median_s": 24 * 60,
                    "rhythm_all_time_gap_median_s": 8 * 60,
                    "rhythm_recent_sample_count": 20,
                    "rhythm_all_time_sample_count": 226,
                    "rhythm_current_gap_percentile_all_time": percentile,
                }

                self.assertIsNone(build_self_card_time_line(lambda ctx=ctx: ctx))

    def test_cold_start_invalid_present_medians_omit_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        invalid_median_pairs = (
            (-1, 8 * 60),
            ("not-a-number", 8 * 60),
            (24 * 60, float("nan")),
            (24 * 60, float("inf")),
        )
        for recent, all_time in invalid_median_pairs:
            with self.subTest(recent=recent, all_time=all_time):
                ctx = {
                    "rhythm_current_gap_s": 30 * 60,
                    "rhythm_recent_gap_median_s": recent,
                    "rhythm_all_time_gap_median_s": all_time,
                    "rhythm_recent_sample_count": 1,
                    "rhythm_all_time_sample_count": 1,
                    "rhythm_current_gap_percentile_all_time": None,
                }

                self.assertIsNone(build_self_card_time_line(lambda ctx=ctx: ctx))

    def test_cold_start_partial_medians_omit_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        for recent, all_time in ((24 * 60, None), (None, 8 * 60)):
            with self.subTest(recent=recent, all_time=all_time):
                ctx = {
                    "rhythm_current_gap_s": 30 * 60,
                    "rhythm_recent_gap_median_s": recent,
                    "rhythm_all_time_gap_median_s": all_time,
                    "rhythm_recent_sample_count": 1,
                    "rhythm_all_time_sample_count": 1,
                    "rhythm_current_gap_percentile_all_time": None,
                }

                self.assertIsNone(build_self_card_time_line(lambda ctx=ctx: ctx))

    def test_non_finite_percentile_omits_line_instead_of_cold_start(self):
        from core.routing.self_card_time import build_self_card_time_line

        ctx = {
            "rhythm_current_gap_s": 8 * 3600,
            "rhythm_recent_gap_median_s": None,
            "rhythm_all_time_gap_median_s": None,
            "rhythm_recent_sample_count": 1,
            "rhythm_all_time_sample_count": 1,
            "rhythm_current_gap_percentile_all_time": float("nan"),
        }

        self.assertIsNone(build_self_card_time_line(lambda: ctx))

    def test_invalid_comparison_sample_counts_omit_line(self):
        from core.routing.self_card_time import build_self_card_time_line

        for all_time_count in (-1, 10.5):
            with self.subTest(all_time_count=all_time_count):
                ctx = {
                    "rhythm_current_gap_s": 8 * 3600,
                    "rhythm_recent_gap_median_s": 24 * 60,
                    "rhythm_all_time_gap_median_s": 8 * 60,
                    "rhythm_recent_sample_count": 20,
                    "rhythm_all_time_sample_count": all_time_count,
                    "rhythm_current_gap_percentile_all_time": 91.2,
                }

                self.assertIsNone(build_self_card_time_line(lambda ctx=ctx: ctx))

    def test_subjective_duration_db_path_is_public_default_path_helper(self):
        from core.evolution.subjective_duration import subjective_duration_db_path

        expected = Path(tempfile.mkdtemp()) / "owner-time.db"
        with mock.patch.dict(os.environ, {"MAEZ_SUBJECTIVE_DURATION_DB": str(expected)}):
            self.assertEqual(subjective_duration_db_path(), expected)
