# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for the vendored surface package + Maez glue.

Locks in the integration shape — MessageEvent in, Maez daemon reply
out, audit rail applied, surface label threaded through. Does NOT
exercise the real TelegramAdapter network path (that requires a live
bot token); the shape tests here confirm the glue is wired correctly
so a future bootstrap call produces a working bot.
"""
from __future__ import annotations

import asyncio
import unittest
from typing import Optional

from skills.surface import (
    MessageEvent, MessageType,
    Platform, PlatformConfig, HomeChannel,
    SessionSource, build_session_key,
    MaezMessageHandler, build_telegram_adapter, SURFACE_NAME,
)


class SurfaceImports(unittest.TestCase):
    def test_package_exports_present(self):
        # Sanity — the public re-exports resolve
        self.assertIs(Platform.TELEGRAM.value, "telegram")
        self.assertEqual(SURFACE_NAME, "telegram_surface")

    def test_platform_config_shape(self):
        cfg = PlatformConfig(enabled=True, token="dummy",
                             extra={"allowed_users": [123]})
        d = cfg.to_dict()
        self.assertTrue(d["enabled"])
        self.assertEqual(d["token"], "dummy")
        self.assertEqual(d["extra"]["allowed_users"], [123])

    def test_session_key_builds(self):
        src = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="42",
            user_id="rohit",
            user_name="Rohit",
            chat_type="dm",
        )
        key = build_session_key(src)
        self.assertIsInstance(key, str)
        self.assertIn("telegram", key)


class _FakeDaemon:
    """Minimal daemon stand-in for handler tests."""

    def __init__(self, reply: str = "hello back"):
        self._reply = reply
        self.last_source: Optional[str] = None
        self.last_text: Optional[str] = None

    def handle_message(self, text: str, source: str = "unknown") -> str:
        self.last_text = text
        self.last_source = source
        return self._reply


class HandlerRouting(unittest.TestCase):
    def test_handler_routes_text_through_daemon(self):
        daemon = _FakeDaemon(reply="I heard you")
        handler = MaezMessageHandler(daemon)

        event = MessageEvent(
            text="ping",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )
        result = asyncio.run(handler(event))
        self.assertEqual(result, "I heard you")
        # Handler wraps the user text with the brain_loop's synthesis
        # instructions (HARD INSTRUCTION when tools ran, NO-TOOL block
        # when nothing ran). The original text must still be present.
        self.assertIn("ping", daemon.last_text or "")
        self.assertEqual(daemon.last_source, SURFACE_NAME)

    def test_empty_text_returns_none(self):
        handler = MaezMessageHandler(_FakeDaemon())
        event = MessageEvent(text="", source=None)
        result = asyncio.run(handler(event))
        self.assertIsNone(result)

    def test_daemon_raising_returns_error_string(self):
        class Raiser:
            def handle_message(self, text, source="unknown"):
                raise RuntimeError("brain offline")

        handler = MaezMessageHandler(Raiser())
        event = MessageEvent(text="anyone home?",
                             source=SessionSource(platform=Platform.TELEGRAM,
                                                  chat_id="c"))
        result = asyncio.run(handler(event))
        self.assertIsNotNone(result)
        self.assertIn("internal error", result)

    def test_audit_runs_on_reply(self):
        """If the daemon returns a fabrication-shape reply, the
        self-claim audit rewrites it before return.

        Integration test — hits the real grounding judge endpoint
        configured via /etc/maez/model.env. Stubs the judge return at
        the HTTP layer so the test doesn't need the live llama-judge
        service up; asserts that audit pipeline correctly rewrites when
        the judge flags."""
        from unittest.mock import patch
        fab = "I've been testing the Maelstrom framework (2.0.0)."
        handler = MaezMessageHandler(_FakeDaemon(reply=fab))
        event = MessageEvent(text="anything new?",
                             source=SessionSource(platform=Platform.TELEGRAM,
                                                  chat_id="c",
                                                  user_id="rohit"))
        # Force the judge to flag the Maelstrom span — isolates the
        # audit pipeline shape from judge-model capability / env setup.
        fake_out = (
            '{"ungrounded": [{"text": "Maelstrom framework (2.0.0)", '
            '"reason": "fabricated internal framework name"}]}'
        )
        with patch("core.grounding_judge._call_dedicated_judge",
                   return_value=fake_out):
            result = asyncio.run(handler(event))
        self.assertIsNotNone(result)
        self.assertNotIn("Maelstrom", result,
            f"audit did not rewrite fabrication: {result!r}")


class BuildTelegramAdapter(unittest.TestCase):
    def test_builder_returns_adapter_with_handler_set(self):
        daemon = _FakeDaemon()
        adapter = build_telegram_adapter(
            token="fake_token", authorized_users=[42], daemon=daemon,
        )
        # Extension point must be populated
        self.assertIsNotNone(adapter._message_handler)
        self.assertIsInstance(adapter._message_handler, MaezMessageHandler)
        self.assertIs(adapter._message_handler.daemon, daemon)
        # Platform auto-detected by the subclass
        self.assertEqual(adapter.platform, Platform.TELEGRAM)


if __name__ == "__main__":
    unittest.main()
