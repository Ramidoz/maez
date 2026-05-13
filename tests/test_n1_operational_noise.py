import logging
import sys
import types
import unittest
from unittest.mock import patch

from daemon import maez_daemon
from skills import calendar_perception, presence_perception


class InvalidGrantCredentials:
    valid = False
    expired = True
    refresh_token = "refresh-token"

    def refresh(self, _request):
        raise Exception(("invalid_grant: Bad Request", {"error": "invalid_grant"}))


class N1OperationalNoiseTests(unittest.TestCase):
    def setUp(self):
        calendar_perception._cache = None
        calendar_perception._cache_time = 0
        setattr(calendar_perception, "_credential_error", None)
        setattr(calendar_perception, "_invalid_grant_blocked_until", 0.0)
        setattr(calendar_perception, "_invalid_grant_logged", False)

        setattr(presence_perception, "_detection_error", None)
        setattr(presence_perception, "_missing_dependency_logged", set())

    def test_calendar_invalid_grant_is_classified_and_log_throttled(self):
        with (
            patch("skills.calendar_perception.os.path.exists", return_value=True),
            patch(
                "google.oauth2.credentials.Credentials.from_authorized_user_file",
                return_value=InvalidGrantCredentials(),
            ),
            patch("google.auth.transport.requests.Request", object),
            self.assertLogs("maez", level="WARNING") as captured,
        ):
            self.assertIsNone(calendar_perception._get_credentials())
            self.assertIsNone(calendar_perception._get_credentials())

        invalid_grant_logs = [line for line in captured.output if "invalid_grant" in line.lower()]
        self.assertEqual(1, len(invalid_grant_logs))
        self.assertEqual(
            "Google Calendar OAuth invalid_grant; reauthorization required",
            calendar_perception._credential_error,
        )

    def test_presence_missing_mediapipe_is_unavailable_not_absent(self):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "mediapipe" or name.startswith("mediapipe"):
                raise ImportError("No module named 'mediapipe'")
            return real_import(name, *args, **kwargs)

        with (
            patch.dict(sys.modules, {"cv2": types.SimpleNamespace()}, clear=False),
            patch("builtins.__import__", side_effect=fake_import),
            self.assertLogs("maez", level="WARNING") as captured,
        ):
            first = presence_perception.observe()
            second = presence_perception.observe()

        self.assertFalse(first.success)
        self.assertFalse(second.success)
        self.assertIn("mediapipe", first.error)
        missing_dependency_logs = [line for line in captured.output if "mediapipe" in line.lower()]
        self.assertEqual(1, len(missing_dependency_logs))

    def test_websocket_invalid_http_handshake_noise_is_classified(self):
        record = logging.LogRecord(
            "websockets.server",
            logging.ERROR,
            "server.py",
            1,
            "opening handshake failed",
            (),
            None,
        )
        record.exc_info = (
            EOFError,
            EOFError("connection closed while reading HTTP request line"),
            None,
        )

        normal_record = logging.LogRecord(
            "websockets.server",
            logging.ERROR,
            "server.py",
            1,
            "real websocket server failure",
            (),
            None,
        )

        self.assertTrue(maez_daemon._is_ws_invalid_handshake_noise(record))
        self.assertFalse(maez_daemon._is_ws_invalid_handshake_noise(normal_record))


if __name__ == "__main__":
    unittest.main()
