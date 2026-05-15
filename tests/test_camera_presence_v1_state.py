"""Camera Presence v1 state contract.

Decision 24 / ADR 0029 makes camera presence a timeboxed body sensor, not
ambient prompt context or biography. These tests pin the state module before
daemon wiring exists.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest


class CameraPresenceModeResolutionTests(unittest.TestCase):
    def test_default_mode_is_disabled_and_content_free(self):
        from core.body.camera_presence_state import resolve_camera_presence_state

        state = resolve_camera_presence_state({}, now=datetime(2026, 5, 15, tzinfo=timezone.utc))
        health = state.to_health()

        self.assertFalse(health["enabled"])
        self.assertEqual(health["mode"], "disabled")
        self.assertEqual(health["sensor_state"], "disabled")
        self.assertEqual(health["presence_state"], "unknown")
        self.assertEqual(health["confidence_bucket"], "none")
        self.assertEqual(health["schema_version"], "camera_presence.v1")
        self.assertEqual(health["source_kind"], "body_sensor.camera_presence")
        self.assertEqual(health["event_kind"], "presence.observed")
        self.assertEqual(health["source_id"], "aurora_camera_presence")
        self.assertEqual(health["source_instance_id"], "aurora_camera_presence.primary")

        encoded = json.dumps(health, sort_keys=True)
        for forbidden in ("Rohit", "face", "frame", "room", "person_identified", "stranger"):
            self.assertNotIn(forbidden, encoded)

    def test_observe_requires_future_timezone_aware_enabled_until(self):
        from core.body.camera_presence_state import resolve_camera_presence_state

        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        future = (now + timedelta(minutes=5)).isoformat()

        state = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": future,
            },
            now=now,
        )

        self.assertTrue(state.enabled)
        self.assertEqual(state.mode, "observe")
        self.assertEqual(state.sensor_state, "unknown")

    def test_missing_malformed_and_expired_timebox_fail_neutral(self):
        from core.body.camera_presence_state import resolve_camera_presence_state

        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)

        missing = resolve_camera_presence_state(
            {"MAEZ_CAMERA_PRESENCE_MODE": "observe"},
            now=now,
        )
        malformed = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": "tomorrow",
            },
            now=now,
        )
        expired = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": (now - timedelta(seconds=1)).isoformat(),
            },
            now=now,
        )

        self.assertEqual(missing.mode, "disabled")
        self.assertEqual(missing.last_error_class, "config_invalid")
        self.assertEqual(malformed.mode, "disabled")
        self.assertEqual(malformed.last_error_class, "config_invalid")
        self.assertEqual(expired.mode, "expired_disabled")
        self.assertEqual(expired.sensor_state, "disabled")
        self.assertEqual(expired.presence_state, "unknown")

    def test_developer_legacy_is_rejected_in_daemon_mode_resolution(self):
        from core.body.camera_presence_state import resolve_camera_presence_state

        state = resolve_camera_presence_state(
            {"MAEZ_CAMERA_PRESENCE_MODE": "developer_legacy"},
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        self.assertEqual(state.mode, "disabled")
        self.assertEqual(state.last_error_class, "config_invalid")

    def test_error_classes_are_closed_and_normalized(self):
        from core.body.camera_presence_state import CameraPresenceState

        state = CameraPresenceState(mode="observe", enabled_until="x")

        timed_out = state.unavailable(error_class="presence observation timed out after 5.0s")
        model_missing = state.unavailable(
            error_class="face detection model unavailable: /home/rohit/maez/models/blaze_face.tflite"
        )
        dependency_missing = state.unavailable(error_class="cv2 unavailable: missing shared object")
        busy = state.unavailable(error_class="presence observation still running")

        self.assertEqual(timed_out.last_error_class, "detector_timeout")
        self.assertEqual(model_missing.last_error_class, "model_missing")
        self.assertEqual(dependency_missing.last_error_class, "dependency_missing")
        self.assertEqual(busy.last_error_class, "camera_busy")
        encoded = json.dumps(model_missing.to_health(), sort_keys=True)
        self.assertNotIn("/home/rohit", encoded)
        self.assertNotIn("blaze_face.tflite", encoded)


class CameraPresenceObservationCommitTests(unittest.TestCase):
    def test_observation_token_discards_result_after_expiry(self):
        from core.body.camera_presence_state import (
            CameraPresenceReading,
            resolve_camera_presence_state,
        )

        start = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        enabled_until = (start + timedelta(seconds=1)).isoformat()
        state = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": enabled_until,
            },
            now=start,
        )
        token = state.make_observation_token(submitted_at=start)

        committed = state.commit_observation(
            CameraPresenceReading(
                presence_state="present",
                confidence_bucket="high",
                observed_at=start,
            ),
            token=token,
            now=start + timedelta(seconds=2),
        )

        self.assertEqual(committed.mode, "expired_disabled")
        self.assertEqual(committed.sensor_state, "disabled")
        self.assertEqual(committed.presence_state, "unknown")
        self.assertEqual(committed.confidence_bucket, "none")

    def test_unavailable_commit_uses_same_token_expiry_oracle(self):
        from core.body.camera_presence_state import resolve_camera_presence_state

        start = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        enabled_until = (start + timedelta(seconds=1)).isoformat()
        state = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": enabled_until,
            },
            now=start,
        )
        token = state.make_observation_token(submitted_at=start)

        committed = state.commit_unavailable(
            "camera 0 not available",
            token=token,
            now=start + timedelta(seconds=2),
        )

        self.assertEqual(committed.mode, "expired_disabled")
        self.assertEqual(committed.sensor_state, "disabled")
        self.assertEqual(committed.presence_state, "unknown")
        self.assertEqual(committed.last_error_class, "timebox_expired")

    def test_stale_reading_clears_present_to_unknown(self):
        from core.body.camera_presence_state import (
            CameraPresenceReading,
            resolve_camera_presence_state,
        )

        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        state = resolve_camera_presence_state(
            {
                "MAEZ_CAMERA_PRESENCE_MODE": "observe",
                "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL": (now + timedelta(hours=1)).isoformat(),
            },
            now=now,
        )
        token = state.make_observation_token(submitted_at=now)
        fresh = state.commit_observation(
            CameraPresenceReading(
                presence_state="present",
                confidence_bucket="high",
                observed_at=now,
            ),
            token=token,
            now=now,
        )

        stale = fresh.with_freshness(now=now + timedelta(seconds=fresh.stale_after_seconds + 1))

        self.assertEqual(stale.sensor_state, "stale")
        self.assertEqual(stale.presence_state, "unknown")
        self.assertEqual(stale.confidence_bucket, "none")


if __name__ == "__main__":
    unittest.main()
