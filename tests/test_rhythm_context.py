import os, sqlite3, tempfile, unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


def _insert_contact(db_path, *, ts, is_canary=0, owner_auth_class="cockpit"):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO subjective_duration_salience_events "
            "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
            (ts.isoformat(), "owner_contact", owner_auth_class, is_canary))
        conn.commit()


class RhythmContext(unittest.TestCase):
    def _inst(self):
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def _contacts(self, inst, base, gaps_minutes):
        # build contacts so consecutive gaps == gaps_minutes (in order)
        t = base
        _insert_contact(inst.db_path, ts=t)
        for g in gaps_minutes:
            t = t + timedelta(minutes=g)
            _insert_contact(inst.db_path, ts=t)
        return t  # latest contact

    def test_facts_math_on_known_gaps(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30, 40, 50])     # 5 gaps: 10,20,30,40,50 min
        now = last + timedelta(minutes=60)                        # current gap = 60 min
        ctx = inst.rhythm_context(now=now)
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 3600.0, places=1)
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 5)
        self.assertAlmostEqual(ctx["rhythm_all_time_gap_median_s"], 30 * 60, places=1)   # median(10,20,30,40,50)=30
        # 60min current gap is longer than ALL 5 historical gaps -> 100th percentile
        self.assertAlmostEqual(ctx["rhythm_current_gap_percentile_all_time"], 100.0, places=1)

    def test_percentile_is_continuous_not_a_band(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30, 40])         # gaps 10,20,30,40
        # current gap 25min is longer than 2 of 4 (10,20) -> 50%
        ctx = inst.rhythm_context(now=last + timedelta(minutes=25))
        self.assertAlmostEqual(ctx["rhythm_current_gap_percentile_all_time"], 50.0, places=1)

    def test_recent_window_limits_recent_count(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [5] * 30)                 # 30 gaps
        ctx = inst.rhythm_context(now=last + timedelta(minutes=5))
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 30)
        self.assertEqual(ctx["rhythm_recent_sample_count"], sd.RHYTHM_RECENT_WINDOW)   # capped at K

    def test_cold_start_comparison_facts_none_but_current_gap_present(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10])                     # only 1 gap (< floor)
        ctx = inst.rhythm_context(now=last + timedelta(minutes=15))
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 15 * 60, places=1)          # present
        self.assertIsNone(ctx["rhythm_all_time_gap_median_s"])                          # not enough data
        self.assertIsNone(ctx["rhythm_current_gap_percentile_all_time"])
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 1)

    def test_none_when_no_real_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                                  # a sample, but NO owner_contact row
        self.assertIsNone(inst.rhythm_context(now=t0 + timedelta(hours=1)))

    def test_excludes_canary_and_manual_test(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        _insert_contact(inst.db_path, ts=t0, owner_auth_class="cockpit")               # real
        _insert_contact(inst.db_path, ts=t0 + timedelta(hours=1), is_canary=1)         # canary
        _insert_contact(inst.db_path, ts=t0 + timedelta(hours=2), owner_auth_class="manual_test")  # scratch
        ctx = inst.rhythm_context(now=t0 + timedelta(hours=3))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["rhythm_all_time_sample_count"], 0)   # only 1 REAL contact -> 0 gaps
        # current gap measured from the REAL contact (t0), not the manual_test at t0+2h
        self.assertAlmostEqual(ctx["rhythm_current_gap_s"], 3 * 3600, places=1)

    def test_none_on_clock_degraded_without_writing(self):
        inst = self._inst()
        t1 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t1)
        _insert_contact(inst.db_path, ts=t1)
        with closing(sqlite3.connect(inst.db_path)) as c:
            s_before = c.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
            e_before = c.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0]
        self.assertIsNone(inst.rhythm_context(now=t1 - timedelta(hours=1)))   # backward clock
        with closing(sqlite3.connect(inst.db_path)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0], s_before)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0], e_before)

    def test_current_gap_climbs_with_now(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 8, 0, 0, tzinfo=UTC)
        last = self._contacts(inst, t0, [10, 20, 30])
        a = inst.rhythm_context(now=last + timedelta(hours=1))["rhythm_current_gap_s"]
        b = inst.rhythm_context(now=last + timedelta(hours=3))["rhythm_current_gap_s"]
        self.assertGreater(b, a)   # unlike the pinned curve, this VARIES
