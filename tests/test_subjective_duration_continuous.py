import os, sqlite3, tempfile, unittest
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


class ReplayFeltValue(unittest.TestCase):
    def test_replay_uses_frozen_anchor_state_not_live(self):
        anchor_ts = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        anchor_row = {"ts": anchor_ts, "value": 2.0, "drag_multiplier": 1.0,
                      "engagement_multiplier": 0.5, "residual_resonance": 0.0, "compute_version": 1}
        at = anchor_ts + timedelta(hours=2)
        replayed = sd.replay_felt_value(anchor_row, at_ts=at)
        expected = sd.compute_subjective_duration_update(
            prior_value=2.0, delta_hours=2.0, drag_multiplier=1.0, engagement_multiplier=0.5,
            residual_multiplier=1.0 + 0.35 * 0.0, config=sd.config_for_version(1))
        self.assertAlmostEqual(replayed, expected, places=9)
        # Different frozen residual in the anchor => different result (proves it reads the ANCHOR, not globals)
        anchor2 = dict(anchor_row, residual_resonance=5.0)
        self.assertNotAlmostEqual(sd.replay_felt_value(anchor2, at_ts=at), replayed, places=6)

    def test_replay_reads_no_live_state(self):
        # Replaying the SAME anchor twice gives the SAME value regardless of any global/live mood.
        anchor_ts = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        anchor_row = {"ts": anchor_ts, "value": 3.0, "drag_multiplier": 0.8,
                      "engagement_multiplier": 0.6, "residual_resonance": 1.0, "compute_version": 1}
        at = anchor_ts + timedelta(hours=5)
        first = sd.replay_felt_value(anchor_row, at_ts=at)
        second = sd.replay_felt_value(anchor_row, at_ts=at)
        self.assertEqual(first, second)

    def test_compute_version_maps_to_config(self):
        self.assertEqual(sd.config_for_version(1).base_rate_per_hour,
                         sd.SubjectiveDurationConfig().base_rate_per_hour)


class SchemaMigration(unittest.TestCase):
    def test_old_db_without_compute_version_migrates_to_v1(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "sd.db")
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE subjective_duration_samples ("
                "sample_id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT NOT NULL, value REAL NOT NULL,"
                "felt_time_rate REAL NOT NULL, drag_multiplier REAL NOT NULL, engagement_multiplier REAL NOT NULL,"
                "residual_resonance REAL NOT NULL, retrospective_density REAL NOT NULL,"
                "metadata_json TEXT NOT NULL DEFAULT '{}')")
            conn.execute("INSERT INTO subjective_duration_samples "
                         "(ts_utc, value, felt_time_rate, drag_multiplier, engagement_multiplier, residual_resonance, retrospective_density) "
                         "VALUES ('2026-06-19T12:00:00+00:00', 1.0, 0.5, 1.0, 0.5, 0.0, 0.0)")
            conn.commit()
        sd.SubjectiveDuration(db_path=path)   # __init__ -> _initialize -> migration
        with sqlite3.connect(path) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(subjective_duration_samples)")}
            self.assertIn("compute_version", cols)
            self.assertEqual(conn.execute("SELECT compute_version FROM subjective_duration_samples").fetchone()[0], 1)
