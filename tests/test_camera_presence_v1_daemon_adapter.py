"""Camera Presence v1 daemon adapter contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch


class _ImmediateWorker:
    def __init__(self, *, join_result: bool = True) -> None:
        self.join_result = join_result

    def in_flight(self) -> bool:
        return False

    def submit(self, fn) -> bool:
        if self.join_result:
            fn()
        return True

    def join(self, *, timeout: float) -> bool:
        return self.join_result


def _daemon_with_state():
    from core.body.camera_presence_state import resolve_camera_presence_state
    from daemon.maez_daemon import MaezDaemon

    now = datetime.now(timezone.utc)
    state = resolve_camera_presence_state(
        {
            "MAEZ_CAMERA_PRESENCE_MODE": "observe",
            "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": (now + timedelta(minutes=5)).isoformat(),
        },
        now=now,
    )
    daemon = object.__new__(MaezDaemon)
    daemon._camera_presence_state = state
    daemon._presence_worker = _ImmediateWorker()
    daemon._shutdown_started = threading.Event()
    return daemon


class CameraPresenceDaemonAdapterTests(unittest.TestCase):
    def _with_fake_probe(self, snap):
        from daemon.maez_daemon import MaezDaemon

        return patch.object(MaezDaemon, "_run_presence_probe", return_value=snap)

    def test_successful_detection_maps_to_present_state(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = _daemon_with_state()
        snap = SimpleNamespace(success=True, presence_detected=True, confidence=0.91)

        with self._with_fake_probe(snap):
            state = MaezDaemon._observe_presence_bounded(daemon)

        self.assertIs(state, daemon._camera_presence_state)
        self.assertEqual(state.presence_state, "present")
        self.assertEqual(state.confidence_bucket, "high")
        self.assertEqual(state.sensor_state, "available")

    def test_successful_no_detection_maps_to_absent_state(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = _daemon_with_state()
        snap = SimpleNamespace(success=True, presence_detected=False, confidence=0.0)

        with self._with_fake_probe(snap):
            state = MaezDaemon._observe_presence_bounded(daemon)

        self.assertEqual(state.presence_state, "absent")
        self.assertEqual(state.confidence_bucket, "none")
        self.assertEqual(state.sensor_state, "available")

    def test_failed_snapshot_updates_health_as_unavailable_not_absent(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = _daemon_with_state()
        snap = SimpleNamespace(
            success=False,
            presence_detected=False,
            confidence=0.0,
            error="face detection model unavailable: /tmp/secret/blaze_face.tflite",
        )

        with self._with_fake_probe(snap):
            state = MaezDaemon._observe_presence_bounded(daemon)

        self.assertIs(state, daemon._camera_presence_state)
        self.assertEqual(state.sensor_state, "unavailable")
        self.assertEqual(state.presence_state, "sensor_unavailable")
        self.assertEqual(state.last_error_class, "model_missing")

    def test_join_timeout_updates_health_as_detector_timeout(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = _daemon_with_state()
        daemon._presence_worker = _ImmediateWorker(join_result=False)

        state = MaezDaemon._observe_presence_bounded(daemon)

        self.assertIs(state, daemon._camera_presence_state)
        self.assertEqual(state.sensor_state, "unavailable")
        self.assertEqual(state.presence_state, "sensor_unavailable")
        self.assertEqual(state.last_error_class, "detector_timeout")

    def test_shutdown_started_discards_in_flight_success_result(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = _daemon_with_state()
        daemon._shutdown_started.set()
        snap = SimpleNamespace(success=True, presence_detected=True, confidence=0.91)

        with self._with_fake_probe(snap):
            state = MaezDaemon._observe_presence_bounded(daemon)

        self.assertEqual(state.presence_state, "unknown")
        self.assertIsNone(state.last_observed_at)


if __name__ == "__main__":
    unittest.main()
