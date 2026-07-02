import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ProprioceptionTests(unittest.TestCase):
    def test_record_and_hourly_aggregate(self):
        from core.body.proprioception import ProprioceptionStore

        with tempfile.TemporaryDirectory() as td:
            store = ProprioceptionStore(Path(td) / "prop.db")
            for i, cpu in enumerate((10.0, 30.0, 20.0)):
                store.record(
                    ts=1000.0 + i,
                    cpu_pct=cpu,
                    ram_pct=40.0,
                    gpu_pct=5.0,
                    gpu_temp_c=48.0,
                )
            agg = store.aggregate(since_ts=0.0)
            self.assertEqual(agg["samples"], 3)
            self.assertAlmostEqual(agg["cpu_pct"]["max"], 30.0)
            self.assertAlmostEqual(agg["cpu_pct"]["median"], 20.0)

    def test_query_answers_trend_question(self):
        from core.body.proprioception import ProprioceptionStore

        with tempfile.TemporaryDirectory() as td:
            store = ProprioceptionStore(Path(td) / "prop.db")
            store.record(
                ts=1.0,
                cpu_pct=1.0,
                ram_pct=1.0,
                gpu_pct=1.0,
                gpu_temp_c=40.0,
            )
            self.assertIn("gpu_temp_c", store.aggregate(since_ts=0.0))


class DaemonProprioceptionWireTests(unittest.TestCase):
    def test_record_proprioception_sample_uses_cycle_snapshot(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = mock.Mock()
        daemon._proprioception_store_get.return_value = mock.Mock()
        snap = {
            "cpu": {"percent": 12.5},
            "ram": {"percent": 45.0},
            "gpu": {"utilization_pct": 6.0, "temperature_c": 50.0},
        }
        MaezDaemon._record_proprioception_sample(daemon, snap, ts=123.0)
        daemon._proprioception_store_get.return_value.record.assert_called_once_with(
            ts=123.0,
            cpu_pct=12.5,
            ram_pct=45.0,
            gpu_pct=6.0,
            gpu_temp_c=50.0,
        )

    def test_record_proprioception_sample_degrades_missing_gpu_to_minus_one(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = mock.Mock()
        daemon._proprioception_store_get.return_value = mock.Mock()
        snap = {"cpu": {"percent": 1.0}, "ram": {"percent": 2.0}, "gpu": None}
        MaezDaemon._record_proprioception_sample(daemon, snap, ts=123.0)
        kwargs = daemon._proprioception_store_get.return_value.record.call_args.kwargs
        self.assertEqual(kwargs["gpu_pct"], -1.0)
        self.assertEqual(kwargs["gpu_temp_c"], -1.0)
