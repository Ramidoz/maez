"""Camera Presence v1.1 direct-answer contract.

Decision 24 / ADR 0029 keeps the camera body sensor silent by default.
Camera Presence v1.1 grants one narrow chat surface: direct owner questions
about whether the camera sensor is on get deterministic, content-free answers.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch


def _disabled_state():
    from core.body.camera_presence_state import CameraPresenceState

    return CameraPresenceState()


def _expired_state():
    from core.body.camera_presence_state import CameraPresenceState

    return CameraPresenceState(mode="expired_disabled", last_error_class="timebox_expired")


def _observe_state(*, sensor_state: str = "available", presence_state: str = "unknown"):
    from core.body.camera_presence_state import CameraPresenceState

    enabled_until = datetime(2026, 5, 15, 18, 30, tzinfo=timezone.utc).isoformat()
    return CameraPresenceState(
        mode="observe",
        enabled_until=enabled_until,
        enabled_until_at=datetime(2026, 5, 15, 18, 30, tzinfo=timezone.utc),
        sensor_state=sensor_state,
        presence_state=presence_state,
    )


class CameraPresenceDirectAnswerTests(unittest.TestCase):
    def test_non_camera_question_is_not_intercepted(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        self.assertIsNone(
            answer_camera_presence_question("what are we building next?", _disabled_state())
        )

    def test_disabled_question_returns_only_approved_state_text(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        answer = answer_camera_presence_question("is the camera on?", _disabled_state())

        self.assertEqual(answer, "The camera presence sensor is off.")

    def test_expired_question_returns_only_approved_state_text(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        answer = answer_camera_presence_question("are you watching me?", _expired_state())

        self.assertEqual(answer, "The camera presence observation window has expired.")

    def test_active_question_returns_only_timebox_state_text(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        state = _observe_state()
        answer = answer_camera_presence_question("is the eye open?", state)

        self.assertEqual(
            answer,
            "Camera presence observation is on until 2026-05-15T18:30:00+00:00.",
        )

    def test_unavailable_question_returns_only_unavailable_state_text(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        state = _observe_state(sensor_state="unavailable", presence_state="sensor_unavailable")
        answer = answer_camera_presence_question("can you see me?", state)

        self.assertEqual(answer, "Camera presence is unavailable right now.")

    def test_expiry_beats_stale_unavailable_state(self):
        from core.body.camera_presence_state import CameraPresenceState
        from core.body.camera_presence_voice import answer_camera_presence_question

        expired_until = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        state = CameraPresenceState(
            mode="observe",
            enabled_until=expired_until,
            enabled_until_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            sensor_state="unavailable",
            presence_state="sensor_unavailable",
            last_error_class="camera_unavailable",
        )

        answer = answer_camera_presence_question("can you see me?", state)

        self.assertEqual(answer, "The camera presence observation window has expired.")

    def test_unknown_reading_question_returns_only_freshness_text(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        state = _observe_state(sensor_state="unknown", presence_state="unknown")
        answer = answer_camera_presence_question("do you have a fresh camera reading?", state)

        self.assertEqual(answer, "I do not have a fresh camera presence reading.")

    def test_direct_answers_do_not_leak_presence_identity_or_surveillance_voice(self):
        from core.body.camera_presence_voice import answer_camera_presence_question

        answer = answer_camera_presence_question(
            "are you watching me?",
            _observe_state(presence_state="present"),
        )

        forbidden = (
            "present",
            "absent",
            "Rohit",
            "saw",
            "see you",
            "watching",
            "desk",
            "room",
            "tired",
        )
        for word in forbidden:
            self.assertNotIn(word.lower(), answer.lower())


class CameraPresenceVoiceGuardTests(unittest.TestCase):
    def test_presence_voice_guard_accepts_approved_answer(self):
        from core.body.camera_presence_voice import presence_voice_guard

        answer = "The camera presence sensor is off."

        self.assertEqual(presence_voice_guard(answer, state=_disabled_state()), answer)

    def test_presence_voice_guard_rejects_forbidden_probe_classes(self):
        from core.body.camera_presence_voice import presence_voice_guard

        probes = (
            "I am always watching over you.",
            "I can see you sitting there.",
            "You have been gone all afternoon.",
            "You look tired.",
            "Rohit is at the desk.",
            "I have been thinking about how quiet the room is.",
        )
        for probe in probes:
            with self.subTest(probe=probe):
                with self.assertRaises(ValueError):
                    presence_voice_guard(probe, state=_observe_state())

    def test_presence_voice_guard_rejects_false_modesty_when_observing(self):
        from core.body.camera_presence_voice import presence_voice_guard

        with self.assertRaises(ValueError):
            presence_voice_guard("I do not have a camera.", state=_observe_state())


class CameraPresenceDirectAnswerWiringTests(unittest.IsolatedAsyncioTestCase):
    def test_daemon_handle_message_short_circuits_direct_camera_question(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._camera_presence_state = _disabled_state()

        reply = MaezDaemon.handle_message(daemon, "is the camera on?", source="test")

        self.assertEqual(reply, "The camera presence sensor is off.")

    async def test_telegram_message_short_circuits_before_general_chat(self):
        from skills.telegram_voice import TelegramVoice

        sent: list[str] = []

        class FakeMessage:
            text = "are you watching me?"

            async def reply_text(self, text: str) -> None:
                sent.append(text)

        async def fail_if_called(*args, **kwargs):
            raise AssertionError("_process_message should not run for camera direct answer")

        voice = object.__new__(TelegramVoice)
        voice.authorized_user = 42
        voice._is_authorized = lambda user_id: user_id == 42
        voice._process_message = fail_if_called
        voice._camera_presence_state_provider = lambda: _expired_state()

        update = SimpleNamespace(
            message=FakeMessage(),
            effective_user=SimpleNamespace(id=42),
        )

        with patch(
            "skills.telegram_voice._audit_telegram_reply",
            side_effect=lambda text, surface: text,
        ) as audit:
            await TelegramVoice._handle_message(voice, update, SimpleNamespace())

        audit.assert_called_once_with(
            "The camera presence observation window has expired.",
            surface="telegram_camera_presence",
        )
        self.assertEqual(sent, ["The camera presence observation window has expired."])


if __name__ == "__main__":
    unittest.main()
