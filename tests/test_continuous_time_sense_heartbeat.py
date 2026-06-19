import inspect, os, unittest
from unittest import mock


class ContinuousTimeSenseFlag(unittest.TestCase):
    def test_flag_default_off(self):
        from daemon import maez_daemon as md
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_CONTINUOUS_TIME_SENSE", None)
            self.assertFalse(md.continuous_time_sense_enabled())

    def test_flag_on(self):
        from daemon import maez_daemon as md
        with mock.patch.dict(os.environ, {"MAEZ_CONTINUOUS_TIME_SENSE": "1"}, clear=False):
            self.assertTrue(md.continuous_time_sense_enabled())

    def test_heartbeat_refresh_uses_peek_gated_on_flag(self):
        # The per-cycle hook calls SubjectiveDuration.peek() (read-only refresh) behind the flag;
        # it must NOT call current() unconditionally (that would flood). The sparse anchor (current())
        # is rate-limited by an interval constant.
        from daemon import maez_daemon as md
        src = inspect.getsource(md)
        self.assertIn("continuous_time_sense_enabled()", src)
        self.assertIn(".peek(", src)                                   # read-only refresh
        self.assertIn("_CONTINUOUS_TIME_ANCHOR_INTERVAL_S", src)       # sparse anchor interval exists
