from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


class DreamIdleGateTest(unittest.TestCase):
    def test_idle_proven_camera_unavailable_fires(self):
        from core.evolution.dream_state import dream_may_run

        self.assertTrue(
            dream_may_run(
                no_interaction_secs=2400,
                camera="unavailable",
                active_until_future=False,
                activity_known=True,
            )
        )

    def test_fresh_camera_present_blocks(self):
        from core.evolution.dream_state import dream_may_run

        self.assertFalse(
            dream_may_run(
                no_interaction_secs=2400,
                camera="present_fresh",
                active_until_future=False,
                activity_known=True,
            )
        )

    def test_fresh_activity_hint_blocks(self):
        from core.evolution.dream_state import dream_may_run

        self.assertFalse(
            dream_may_run(
                no_interaction_secs=2400,
                camera="absent",
                active_until_future=True,
                activity_known=True,
            )
        )

    def test_activity_uncertainty_blocks(self):
        from core.evolution.dream_state import dream_may_run

        self.assertFalse(
            dream_may_run(
                no_interaction_secs=2400,
                camera="absent",
                active_until_future=False,
                activity_known=False,
            )
        )

    def test_below_threshold_does_not_fire(self):
        from core.evolution.dream_state import dream_may_run

        self.assertFalse(
            dream_may_run(
                no_interaction_secs=600,
                camera="absent",
                active_until_future=False,
                activity_known=True,
            )
        )

    def test_camera_absent_with_proven_idle_fires(self):
        from core.evolution.dream_state import dream_may_run

        self.assertTrue(
            dream_may_run(
                no_interaction_secs=2400,
                camera="absent",
                active_until_future=False,
                activity_known=True,
            )
        )


class DreamDaemonInputTest(unittest.TestCase):
    def test_owner_interaction_tracker_makes_activity_known(self):
        from daemon.maez_daemon import (
            _dream_idle_inputs,
            _record_owner_interaction,
        )

        daemon = SimpleNamespace(
            _last_owner_interaction_ts=None,
            _rohit_active_until=0.0,
            _last_presence_snap=None,
            _camera_presence_state=None,
        )

        unknown = _dream_idle_inputs(daemon, now=5000.0)
        self.assertFalse(unknown["activity_known"])

        _record_owner_interaction(daemon, now=1000.0)
        known = _dream_idle_inputs(daemon, now=5000.0)
        self.assertTrue(known["activity_known"])
        self.assertEqual(known["no_interaction_secs"], 4000.0)

    def test_daemon_inputs_classify_fresh_camera_present_as_blocking(self):
        from core.body.camera_presence_state import CameraPresenceState
        from daemon.maez_daemon import _dream_idle_inputs

        now_dt = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
        daemon = SimpleNamespace(
            _last_owner_interaction_ts=now_dt.timestamp() - 2400,
            _rohit_active_until=0.0,
            _last_presence_snap=CameraPresenceState(
                mode="observe",
                enabled_until="2026-06-03T00:00:00+00:00",
                enabled_until_at=now_dt + timedelta(hours=12),
                sensor_state="available",
                presence_state="present",
                confidence_bucket="high",
                last_observed_at=now_dt - timedelta(seconds=10),
                received_at=now_dt - timedelta(seconds=10),
            ),
            _camera_presence_state=None,
        )

        inputs = _dream_idle_inputs(daemon, now=now_dt.timestamp())

        self.assertEqual(inputs["camera"], "present_fresh")

    def test_daemon_inputs_treat_stale_or_unavailable_camera_as_uncertain_not_blocking(self):
        from core.body.camera_presence_state import CameraPresenceState
        from daemon.maez_daemon import _dream_idle_inputs

        now_dt = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
        for state in [
            CameraPresenceState(
                mode="observe",
                enabled_until="2026-06-03T00:00:00+00:00",
                enabled_until_at=now_dt + timedelta(hours=12),
                sensor_state="available",
                presence_state="present",
                confidence_bucket="high",
                last_observed_at=now_dt - timedelta(seconds=600),
                received_at=now_dt - timedelta(seconds=600),
            ),
            CameraPresenceState(),
        ]:
            with self.subTest(state=state):
                daemon = SimpleNamespace(
                    _last_owner_interaction_ts=now_dt.timestamp() - 2400,
                    _rohit_active_until=0.0,
                    _last_presence_snap=state,
                    _camera_presence_state=None,
                )

                inputs = _dream_idle_inputs(daemon, now=now_dt.timestamp())

                self.assertNotEqual(inputs["camera"], "present_fresh")

    def test_telegram_authorized_command_marks_owner_interaction(self):
        from skills.telegram_voice import TelegramVoice

        daemon = SimpleNamespace(_last_owner_interaction_ts=None)
        voice = TelegramVoice.__new__(TelegramVoice)
        voice.authorized_user = 42
        voice.daemon = daemon

        self.assertTrue(voice._is_authorized(42))

        self.assertIsNotNone(daemon._last_owner_interaction_ts)

    def test_owner_control_routes_record_activity(self):
        from daemon.maez_daemon import MaezDaemon

        source = inspect.getsource(MaezDaemon._run_health_server)

        def route_body(route: str) -> str:
            marker = f'@app.route("{route}"'
            start = source.index(marker)
            next_route = source.find("@app.route(", start + len(marker))
            if next_route == -1:
                return source[start:]
            return source[start:next_route]

        for route in [
            "/internal/s7/webauthn/register/begin",
            "/internal/s7/webauthn/register/finish",
            "/internal/s7/webauthn/register/backup-card",
            "/internal/s7/webauthn/proof/disable-card",
            "/internal/s7/webauthn/proof/disable-credential",
            "/internal/s7/cards/<request_id>/webauthn/begin",
            "/internal/s7/cards/<request_id>/webauthn/finish",
            "/internal/s7/cards/<request_id>/execute",
            "/internal/approve_card/<request_id>",
        ]:
            with self.subTest(route=route):
                self.assertIn("_record_owner_interaction(self)", route_body(route))
