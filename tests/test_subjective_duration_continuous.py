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


class PeekReadOnly(unittest.TestCase):
    def _inst(self):
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def _count(self, inst):
        with sqlite3.connect(inst.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]

    def test_peek_does_not_write_but_current_does(self):
        inst = self._inst()
        before = self._count(inst)
        inst.peek(now_utc=datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC))
        self.assertEqual(self._count(inst), before)              # peek wrote nothing
        inst.current(now_utc=datetime(2026, 6, 19, 12, 0, 30, tzinfo=UTC))
        self.assertEqual(self._count(inst), before + 1)          # current still writes

    def test_elapsed_is_exact_felt_is_derived(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                                 # anchor row
        snap = inst.peek(now_utc=t0 + timedelta(hours=2))
        self.assertAlmostEqual(snap.elapsed_seconds, 7200.0, places=3)   # exact wall-clock
        self.assertNotAlmostEqual(snap.felt_value, 7200.0, places=3)     # felt != elapsed
        self.assertLessEqual(snap.felt_value, 10.0)                      # 0-10 curve, not seconds
        self.assertEqual(snap.felt_value, snap.value)                    # felt_value aliases value

    def test_monotonic_climb_no_band(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        a = inst.peek(now_utc=t0 + timedelta(hours=1)).felt_value
        b = inst.peek(now_utc=t0 + timedelta(hours=3)).felt_value
        self.assertGreater(b, a)                                 # raw continuous value climbs

    def test_current_stores_computed_modulators_and_replays(self):
        # The stored anchor's modulators must be EXACTLY what _compute produced, AND replaying the
        # persisted row forward through Task 1's replay_felt_value must reproduce a faithful felt value.
        inst = self._inst()
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        snap = inst.current(now_utc=t0)             # writes the anchor; snap == what _compute produced
        inst.peek(now_utc=t0 + timedelta(hours=4))  # read-only; must not perturb the stored anchor
        with sqlite3.connect(inst.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM subjective_duration_samples ORDER BY sample_id DESC LIMIT 1").fetchone()
        # (1) the stored modulators ARE the computed ones (not asserted in prose anymore)
        self.assertAlmostEqual(row["drag_multiplier"], snap.drag_multiplier, places=9)
        self.assertAlmostEqual(row["engagement_multiplier"], snap.engagement_multiplier, places=9)
        self.assertAlmostEqual(row["residual_resonance"], snap.residual_resonance, places=9)
        self.assertAlmostEqual(row["value"], snap.value, places=9)
        self.assertEqual(row["compute_version"], sd.CURRENT_COMPUTE_VERSION)
        # (2) replay from the STORED row reproduces a forward-replayed felt value, deterministically
        anchor = {"ts": t0, "value": row["value"], "drag_multiplier": row["drag_multiplier"],
                  "engagement_multiplier": row["engagement_multiplier"],
                  "residual_resonance": row["residual_resonance"],
                  "compute_version": row["compute_version"]}
        at = t0 + timedelta(hours=2)
        replayed = sd.replay_felt_value(anchor, at_ts=at)
        self.assertEqual(replayed, sd.replay_felt_value(anchor, at_ts=at))   # deterministic
        self.assertGreaterEqual(replayed, row["value"])                       # climbs forward from the anchor


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


class PerceptionLineRecomputes(unittest.TestCase):
    def test_perception_line_advances_with_clock_not_stale_row(self):
        inst = sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                       # one stored row (the stale one it used to echo)
        # 8h later, perception_line must reflect the RECOMPUTED felt time, not the stored row's phrase
        line_later = inst.perception_line(now_utc=t0 + timedelta(hours=8))
        stale = f"Felt time: {inst._snapshot_from_row(inst._latest_sample(), source_ref_digest=None).surface_phrase}."
        self.assertNotEqual(line_later, stale)         # recomputed, didn't echo the old row
        self.assertTrue(line_later.startswith("Felt time:"))

    def test_perception_line_is_read_only(self):
        inst = sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))
        t0 = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        with sqlite3.connect(inst.db_path) as conn:
            before = conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
        inst.perception_line(now_utc=t0 + timedelta(hours=4))
        with sqlite3.connect(inst.db_path) as conn:
            after = conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
        self.assertEqual(before, after)                # peek-based: no write
