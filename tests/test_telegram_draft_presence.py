# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Telegram draft-presence slice tests.

These tests pin the contract from docs/SLICE_TELEGRAM_DRAFT_PRESENCE.md:
empty Maez-authored draft text only, default-disabled owner-local config,
wrapper-isolated Bot API call, fail-neutral behavior, and no gating of the
final reply path.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path

from skills.surface.platform_base import MessageEvent, Platform, SessionSource
from skills.surface.platform_config import PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


def _event(
    *,
    chat_id: str = "42",
    message_id: str = "100",
    update_id: int = 9001,
) -> MessageEvent:
    return MessageEvent(
        text="hello",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            user_id="rohit",
            user_name="Rohit",
        ),
        message_id=message_id,
        platform_update_id=update_id,
    )


class _DraftBot:
    def __init__(self, *, delay: float = 0.0, fail: Exception | None = None):
        self.delay = delay
        self.fail = fail
        self.calls: list[dict] = []

    async def send_message_draft(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise self.fail
        return object()


class TelegramDraftPresenceConfigTests(unittest.TestCase):
    def test_missing_config_disables_draft_presence(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            adapter._telegram_draft_presence_config_path = Path(td) / "missing.json"
            cfg = adapter._load_telegram_draft_presence_config()

        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.timeout_ms, 750)

    def test_enabled_config_loads_schema_version_one(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "enabled": True,
                        "attempt_timeout_ms": 500,
                        "max_attempts_per_inbound_message": 1,
                    }
                )
            )
            adapter._telegram_draft_presence_config_path = path
            cfg = adapter._load_telegram_draft_presence_config()

        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.timeout_ms, 500)

    def test_bad_config_warning_is_bounded(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            path.write_text("{not-json")
            adapter._telegram_draft_presence_config_path = path
            with self.assertLogs("skills.surface.telegram_adapter", level="WARNING") as cap:
                first = adapter._load_telegram_draft_presence_config()
                second = adapter._load_telegram_draft_presence_config()

        self.assertFalse(first.enabled)
        self.assertFalse(second.enabled)
        self.assertEqual(len(cap.records), 1)


class TelegramDraftPresenceBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_draft_call_is_exactly_empty_text(self):
        adapter = TelegramAdapter(PlatformConfig())
        bot = _DraftBot()
        adapter._bot = bot
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        result = await adapter.send_empty_draft_presence(_event())

        self.assertTrue(result)
        self.assertEqual(len(bot.calls), 1)
        call = bot.calls[0]
        self.assertEqual(call["text"], "")
        self.assertEqual(call["text"].encode("utf-8"), b"")
        self.assertNotIn("parse_mode", call)
        self.assertNotIn("entities", call)

    async def test_unsupported_bot_method_fails_neutral_and_opens_circuit(self):
        class NoDraftBot:
            pass

        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = NoDraftBot()
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        result = await adapter.send_empty_draft_presence(_event())

        self.assertFalse(result)
        self.assertTrue(adapter._telegram_draft_presence_circuit_open)

    async def test_one_attempt_per_inbound_logical_message(self):
        adapter = TelegramAdapter(PlatformConfig())
        bot = _DraftBot()
        adapter._bot = bot
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )
        event = _event()

        first = await adapter.send_empty_draft_presence(event)
        second = await adapter.send_empty_draft_presence(event)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(bot.calls), 1)

    async def test_failure_does_not_block_final_send(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(fail=RuntimeError("token=SECRET chat_id=42 boom"))
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        result = await adapter.send_empty_draft_presence(_event())

        self.assertFalse(result)

    async def test_slow_draft_hook_does_not_gate_message_handler(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(delay=0.2)
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )
        observed: dict[str, float] = {}

        async def handler(event):
            observed["handler_at"] = time.perf_counter()
            return "final"

        async def fake_send(*args, **kwargs):
            observed["send_at"] = time.perf_counter()
            return type("Result", (), {"success": True})()

        adapter.set_message_handler(handler)
        adapter._send_with_retry = fake_send  # type: ignore[method-assign]
        event = _event()
        session_key = "telegram:dm:42"
        adapter._active_sessions[session_key] = asyncio.Event()

        started = time.perf_counter()
        await adapter._process_message_background(event, session_key)

        self.assertIn("handler_at", observed)
        self.assertIn("send_at", observed)
        self.assertLess(observed["handler_at"] - started, 0.1)
        self.assertLess(observed["send_at"] - started, 0.1)


class TelegramDraftPresenceStaticTests(unittest.TestCase):
    def test_config_path_is_gitignored(self):
        from pathlib import Path

        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("config/telegram_draft_presence.local.json", gitignore)


if __name__ == "__main__":
    unittest.main()
