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
import logging
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
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
                        "enabled_until": (
                            datetime.now(timezone.utc) + timedelta(hours=1)
                        ).isoformat().replace("+00:00", "Z"),
                        "max_attempts_per_inbound_message": 1,
                    }
                )
            )
            adapter._telegram_draft_presence_config_path = path
            cfg = adapter._load_telegram_draft_presence_config()

        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.timeout_ms, 500)

    def test_enabled_config_requires_unexpired_timebox(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "enabled": True,
                        "enabled_until": (
                            datetime.now(timezone.utc) - timedelta(minutes=1)
                        ).isoformat().replace("+00:00", "Z"),
                    }
                )
            )
            adapter._telegram_draft_presence_config_path = path
            cfg = adapter._load_telegram_draft_presence_config()

        self.assertFalse(cfg.enabled)

    def test_unsupported_schema_disables_draft_presence(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            path.write_text(json.dumps({"schema_version": 2, "enabled": True}))
            adapter._telegram_draft_presence_config_path = path
            cfg = adapter._load_telegram_draft_presence_config()

        self.assertFalse(cfg.enabled)

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

    def test_bad_config_does_not_reset_circuit_breaker(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            path.write_text("{not-json")
            adapter._telegram_draft_presence_config_path = path
            adapter._telegram_draft_presence_circuit_open = True
            adapter._telegram_draft_presence_failures["api_error"] = [time.time()]

            cfg = adapter._load_telegram_draft_presence_config()

        self.assertFalse(cfg.enabled)
        self.assertTrue(adapter._telegram_draft_presence_circuit_open)
        self.assertIn("api_error", adapter._telegram_draft_presence_failures)


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

    async def test_attempted_idempotency_set_eviction_is_bounded(self):
        adapter = TelegramAdapter(PlatformConfig())
        max_entries = adapter._TELEGRAM_DRAFT_PRESENCE_ATTEMPTED_MAX

        for idx in range(max_entries + 5):
            adapter._telegram_draft_presence_mark_attempted(("42", str(idx)))

        self.assertEqual(len(adapter._telegram_draft_presence_attempted), max_entries)
        self.assertNotIn(("42", "0"), adapter._telegram_draft_presence_attempted)
        self.assertNotIn(("42", "4"), adapter._telegram_draft_presence_attempted)
        self.assertIn(("42", str(max_entries + 4)), adapter._telegram_draft_presence_attempted)

    async def test_duplicate_message_with_different_update_id_is_suppressed(self):
        adapter = TelegramAdapter(PlatformConfig())
        bot = _DraftBot()
        adapter._bot = bot
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        first = await adapter.send_empty_draft_presence(_event(update_id=1))
        second = await adapter.send_empty_draft_presence(_event(update_id=2))

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(bot.calls), 1)

    async def test_timeout_opens_failure_path_without_final_exception(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(delay=0.05)
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=1,
        )

        result = await adapter.send_empty_draft_presence(_event())

        self.assertFalse(result)

    async def test_three_same_reason_failures_open_circuit_breaker(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(fail=OSError("network down token=SECRET"))
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        for idx in range(3):
            await adapter.send_empty_draft_presence(_event(message_id=str(idx)))

        self.assertTrue(adapter._telegram_draft_presence_circuit_open)

    async def test_failure_window_discards_stale_timestamps(self):
        adapter = TelegramAdapter(PlatformConfig())
        reason = "network_error"
        stale = time.time() - adapter._TELEGRAM_DRAFT_PRESENCE_FAILURE_WINDOW_SECONDS - 1
        adapter._telegram_draft_presence_failures[reason] = [stale]

        adapter._telegram_draft_presence_record_failure(reason)

        self.assertEqual(len(adapter._telegram_draft_presence_failures[reason]), 1)
        self.assertGreater(
            adapter._telegram_draft_presence_failures[reason][0],
            stale,
        )

    async def test_config_change_resets_circuit_breaker(self):
        adapter = TelegramAdapter(PlatformConfig())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "telegram_draft_presence.local.json"
            adapter._telegram_draft_presence_config_path = path
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "enabled": True,
                        "enabled_until": (
                            datetime.now(timezone.utc) + timedelta(hours=1)
                        ).isoformat().replace("+00:00", "Z"),
                    }
                )
            )
            adapter._telegram_draft_presence_circuit_open = True
            adapter._telegram_draft_presence_failures["network_error"] = [time.time()]
            adapter._load_telegram_draft_presence_config()

            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "enabled": True,
                        "enabled_until": (
                            datetime.now(timezone.utc) + timedelta(hours=2)
                        ).isoformat().replace("+00:00", "Z"),
                    }
                )
            )
            adapter._load_telegram_draft_presence_config()

        self.assertFalse(adapter._telegram_draft_presence_circuit_open)
        self.assertEqual(adapter._telegram_draft_presence_failures, {})

    async def test_failure_does_not_block_final_send(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(fail=RuntimeError("token=SECRET chat_id=42 boom"))
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        result = await adapter.send_empty_draft_presence(_event())

        self.assertFalse(result)

    async def test_exception_telemetry_is_sanitized(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(fail=RuntimeError("token=SECRET chat_id=42 boom"))
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        with self.assertLogs("skills.surface.telegram_adapter", level="INFO") as cap:
            result = await adapter.send_empty_draft_presence(_event())

        logs = "\n".join(cap.output)
        self.assertFalse(result)
        self.assertIn("telegram_draft_presence.failed", logs)
        self.assertIn("reason=api_error", logs)
        self.assertNotIn("SECRET", logs)
        self.assertNotIn("chat_id=42", logs)
        self.assertNotIn("boom", logs)

    async def test_telemetry_failure_is_fail_neutral(self):
        class RaisingHandler(logging.Handler):
            def emit(self, record):
                raise RuntimeError("telemetry sink down token=SECRET")

        adapter = TelegramAdapter(PlatformConfig())
        bot = _DraftBot()
        adapter._bot = bot
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )
        handler = RaisingHandler()
        logger = logging.getLogger("skills.surface.telegram_adapter")
        logger.addHandler(handler)
        try:
            result = await adapter.send_empty_draft_presence(_event())
        finally:
            logger.removeHandler(handler)

        self.assertTrue(result)
        self.assertEqual(len(bot.calls), 1)

    async def test_bad_chat_id_fails_neutral(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot()
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        result = await adapter.send_empty_draft_presence(_event(chat_id="not-int"))

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
            observed["send_content"] = kwargs.get("content")
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
        self.assertEqual(observed["send_content"], "final")
        self.assertLess(observed["handler_at"] - started, 0.1)
        self.assertLess(observed["send_at"] - started, 0.1)

    async def test_disabled_draft_presence_preserves_final_reply(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot()
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=False,
            timeout_ms=750,
        )
        observed: dict[str, str] = {}

        async def handler(event):
            return "final"

        async def fake_send(*args, **kwargs):
            observed["send_content"] = kwargs.get("content")
            return type("Result", (), {"success": True})()

        adapter.set_message_handler(handler)
        adapter._send_with_retry = fake_send  # type: ignore[method-assign]
        event = _event()
        session_key = "telegram:dm:42"
        adapter._active_sessions[session_key] = asyncio.Event()

        await adapter._process_message_background(event, session_key)

        self.assertEqual(observed["send_content"], "final")
        self.assertEqual(adapter._telegram_draft_presence_tasks, set())

    async def test_disabled_config_does_not_schedule_draft_task(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=False,
            timeout_ms=750,
        )

        adapter._schedule_empty_draft_presence(_event())

        self.assertEqual(adapter._telegram_draft_presence_tasks, set())

    async def test_disconnect_drains_draft_task_scheduled_during_app_shutdown(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._bot = _DraftBot(delay=10.0)
        adapter._telegram_draft_presence_config = lambda: adapter._TelegramDraftPresenceConfig(
            enabled=True,
            timeout_ms=750,
        )

        class FakeUpdater:
            running = False

        class FakeApp:
            updater = FakeUpdater()
            running = False

            async def shutdown(self):
                adapter._schedule_empty_draft_presence(_event())
                await asyncio.sleep(0)

        adapter._app = FakeApp()

        await adapter.disconnect()

        self.assertEqual(adapter._telegram_draft_presence_tasks, set())


class TelegramDraftPresenceStaticTests(unittest.TestCase):
    def test_config_path_is_gitignored(self):
        from pathlib import Path

        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("config/telegram_draft_presence.local.json", gitignore)


if __name__ == "__main__":
    unittest.main()
