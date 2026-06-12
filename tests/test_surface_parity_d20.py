from __future__ import annotations

import asyncio
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from skills.surface import MaezMessageHandler, MessageEvent, Platform, SessionSource
from tests.test_surface_adapter import _FakeDaemon, _Pipe, _TelegramWithController

_SRC = Path("skills/surface/maez_adapter.py").read_text()


class D20PlacementTests(unittest.TestCase):
    def test_d20_call_is_after_auth_before_card_handling(self):
        auth = _SRC.index("guard_owner_text")
        d20 = _SRC.index("maybe_fire_capability_proposal")
        cards = _SRC.index("get_open_for_channel")
        self.assertLess(auth, d20)
        self.assertLess(d20, cards)


class D20BehaviorTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def _event(self, text: str = "I wish you could do something new") -> MessageEvent:
        return MessageEvent(
            text=text,
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )

    def test_fires_with_pending_card_store_fire_and_forget(self):
        pipe = _Pipe()
        daemon = _FakeDaemon(reply="normal reply")
        daemon.telegram = _TelegramWithController(pipe=pipe)
        handler = MaezMessageHandler(daemon)
        seen = threading.Event()
        calls: list[dict] = []

        def fake_fire(user_text, **kwargs):
            calls.append({"user_text": user_text, **kwargs})
            seen.set()
            return {"fired": False}

        with patch("core.infra.capability_gap_detector.maybe_fire_capability_proposal", fake_fire):
            result = asyncio.run(handler(self._event()))

        self.assertEqual(result, "normal reply")
        self.assertTrue(seen.wait(1.0), calls)
        self.assertEqual(calls[0]["user_text"], "I wish you could do something new")
        self.assertIs(calls[0]["pending_card_store"], pipe.card_store)
        self.assertEqual(calls[0]["chat_id"], "c")
        self.assertEqual(calls[0]["user_id"], "rohit")

    def test_detector_exception_does_not_change_reply(self):
        daemon = _FakeDaemon(reply="still replies")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)

        def boom(*args, **kwargs):
            raise RuntimeError("detector failed")

        with patch("core.infra.capability_gap_detector.maybe_fire_capability_proposal", boom):
            result = asyncio.run(handler(self._event()))

        self.assertEqual(result, "still replies")

    def test_flag_off_no_d20_call(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        daemon = _FakeDaemon(reply="normal reply")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)

        with patch("core.infra.capability_gap_detector.maybe_fire_capability_proposal") as fire:
            result = asyncio.run(handler(self._event()))

        self.assertEqual(result, "normal reply")
        fire.assert_not_called()
