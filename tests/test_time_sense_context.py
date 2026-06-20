import os, sqlite3, tempfile, unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from core.evolution import subjective_duration as sd

UTC = timezone.utc


def _insert_owner_contact(db_path, *, ts, is_canary=0, owner_auth_class="cockpit"):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO subjective_duration_salience_events "
            "(ts_utc, salience_event_kind, owner_auth_class, is_canary) VALUES (?,?,?,?)",
            (ts.isoformat(), "owner_contact", owner_auth_class, is_canary),
        )
        conn.commit()


class TimeSenseContext(unittest.TestCase):
    def _inst(self):
        return sd.SubjectiveDuration(db_path=os.path.join(tempfile.mkdtemp(), "sd.db"))

    def test_valid_context_has_value_phrase_version_and_seconds_since_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                       # an anchor so felt-time computes
        _insert_owner_contact(inst.db_path, ts=t0)     # a real last-contact reference
        ctx = inst.time_sense_context(now=t0 + timedelta(hours=2))
        self.assertIsNotNone(ctx)
        self.assertIn("felt_value", ctx)
        self.assertIn("felt_phrase", ctx)
        self.assertEqual(ctx["felt_compute_version"], sd.CURRENT_COMPUTE_VERSION)
        self.assertAlmostEqual(ctx["seconds_since_last_owner_contact"], 7200.0, places=1)  # since CONTACT, not anchor

    def test_none_when_no_owner_contact_reference(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)                        # felt-time exists, but no owner_contact row
        self.assertIsNone(inst.time_sense_context(now=t0 + timedelta(hours=1)))

    def test_none_when_only_canary_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        _insert_owner_contact(inst.db_path, ts=t0, is_canary=1)   # canary must NOT count as last contact
        self.assertIsNone(inst.time_sense_context(now=t0 + timedelta(hours=1)))

    def test_none_on_clock_degraded_and_writes_nothing(self):
        inst = self._inst()
        t1 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t1)                         # latest anchor at t1
        _insert_owner_contact(inst.db_path, ts=t1)
        with closing(sqlite3.connect(inst.db_path)) as conn:
            samples_before = conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0]
            events_before = conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0]
        ctx = inst.time_sense_context(now=t1 - timedelta(hours=1))   # clock went BACKWARD -> degraded
        self.assertIsNone(ctx)
        with closing(sqlite3.connect(inst.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM subjective_duration_samples").fetchone()[0], samples_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM subjective_duration_salience_events").fetchone()[0], events_before)

    def test_excludes_canary_uses_real_contact(self):
        inst = self._inst()
        t0 = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
        inst.current(now_utc=t0)
        _insert_owner_contact(inst.db_path, ts=t0 + timedelta(hours=3), is_canary=1)   # newer but canary
        _insert_owner_contact(inst.db_path, ts=t0, is_canary=0)                         # older but real
        ctx = inst.time_sense_context(now=t0 + timedelta(hours=4))
        self.assertIsNotNone(ctx)
        self.assertAlmostEqual(ctx["seconds_since_last_owner_contact"], 4 * 3600.0, places=1)  # used the REAL row


class HumanizeElapsed(unittest.TestCase):
    def test_humanizes_hours_and_minutes(self):
        self.assertEqual(sd.humanize_elapsed(3 * 3600 + 12 * 60), "3h 12m")
        self.assertEqual(sd.humanize_elapsed(90), "1m")          # <1h -> minutes
        self.assertEqual(sd.humanize_elapsed(45), "under a minute")
        self.assertEqual(sd.humanize_elapsed(26 * 3600), "1d 2h")
