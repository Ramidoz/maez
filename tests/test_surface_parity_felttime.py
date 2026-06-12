from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth
from skills.surface import MaezMessageHandler, MessageEvent, Platform, SessionSource
from tests.test_surface_adapter import _FakeDaemon, _TelegramWithController


class FeltTimeAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def _run(self, *, flag: str | None):
        if flag is None:
            os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        else:
            os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = flag
        daemon = _FakeDaemon(reply="normal reply")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="are you able to feel time?",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )
        with patch(
            "core.safety.audited_output.audit_assistant_text",
            side_effect=lambda reply, **kwargs: reply,
        ):
            result = asyncio.run(handler(event))
        self.assertEqual(result, "normal reply")
        return daemon.last_kwargs

    def test_flag_on_passes_subjective_duration_auth(self):
        kwargs = self._run(flag="1")

        auth = kwargs.get("subjective_duration_owner_auth")
        self.assertIsInstance(auth, SubjectiveDurationOwnerAuth)
        self.assertEqual(auth.surface, "telegram_owner")
        self.assertEqual(auth.proof, "telegram_authorized_user")

    def test_flag_zero_and_off_auth_absent(self):
        for flag in (None, "0"):
            kwargs = self._run(flag=flag)
            self.assertIsNone(kwargs.get("subjective_duration_owner_auth"))
