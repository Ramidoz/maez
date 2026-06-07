import unittest
import inspect
import json
import tempfile
from pathlib import Path
from unittest import mock

from skills.surface.platform_base import MessageEvent, MessageType, PlatformConfig
from skills.surface.platform_config import Platform
from skills.surface.session import SessionSource
from skills.surface.telegram_adapter import TelegramAdapter


def _event(text: str) -> MessageEvent:
    return _event_with_chat(text, "owner-chat")


def _event_with_chat(text: str, chat_id: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.COMMAND,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            user_id="owner",
            user_name="Rohit",
        ),
    )


class _FakeDream:
    def __init__(self):
        self.applied = []
        self.rejected = []

    def list_pending(self):
        return [
            (55, "2026-06-04 01:53:46", "I notice a semantic drift."),
            (56, "2026-06-04 04:54:34", "This suggests monitoring repetition."),
        ]

    def apply_proposal(self, prop_id):
        self.applied.append(prop_id)
        return False, "S7 execution authorization required before /apply_dream soul write"

    def reject_proposal(self, prop_id):
        self.rejected.append(prop_id)
        return True, f"dream #{prop_id} rejected"


class _FakeDaemon:
    def __init__(self):
        self.dream = _FakeDream()


class _FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return mock.Mock(message_id=101)


class TelegramDreamCommandSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_handle_command_checks_dream_commands_before_generic_dispatch(self):
        source = inspect.getsource(TelegramAdapter._handle_command)
        dream_idx = source.find("_try_handle_dream_command_event")
        generic_idx = source.find("await self.handle_message(event)")

        self.assertGreaterEqual(dream_idx, 0)
        self.assertGreaterEqual(generic_idx, 0)
        self.assertLess(dream_idx, generic_idx)

    async def test_dreams_command_lists_pending_without_llm(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._maez_daemon = _FakeDaemon()
        sent = []

        async def fake_send(chat_id, content, **kwargs):
            sent.append((chat_id, str(content)))
            return mock.Mock(success=True)

        adapter.send = mock.AsyncMock(side_effect=fake_send)
        handled = await adapter._try_handle_dream_command_event(_event("/dreams"))

        self.assertTrue(handled)
        self.assertEqual(len(sent), 1)
        self.assertIn("#55", sent[0][1])
        self.assertIn("/apply_dream 55", sent[0][1])
        self.assertIn("/reject_dream 56", sent[0][1])

    async def test_dream_command_reply_is_classified_at_telegram_egress(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._maez_daemon = _FakeDaemon()
        bot = _FakeBot()
        adapter._bot = bot

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "telegram_egress.jsonl"
            with mock.patch.dict(
                "os.environ",
                {
                    "MAEZ_TELEGRAM_EGRESS_LOG": str(log_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "dream-command-test",
                },
                clear=False,
            ):
                handled = await adapter._try_handle_dream_command_event(
                    _event_with_chat("/dreams", "123")
                )

            rows = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertTrue(handled)
        self.assertEqual(len(bot.calls), 1)
        self.assertIn("#55", bot.calls[0]["text"])
        self.assertEqual(rows[-1]["decision"], "allow")
        self.assertIn(
            "maez_authored_owner_third_party_transport",
            rows[-1]["origin_classes"],
        )
        self.assertNotIn("unclassified", rows[-1]["origin_classes"])

    async def test_apply_dream_uses_dream_state_and_reports_s7_fail_closed(self):
        daemon = _FakeDaemon()
        adapter = TelegramAdapter(PlatformConfig())
        adapter._maez_daemon = daemon
        sent = []

        async def fake_send(chat_id, content, **kwargs):
            sent.append((chat_id, str(content)))
            return mock.Mock(success=True)

        adapter.send = mock.AsyncMock(side_effect=fake_send)
        adapter.handle_message = mock.AsyncMock()

        handled = await adapter._try_handle_dream_command_event(_event("/apply_dream 55"))

        self.assertTrue(handled)
        self.assertEqual(daemon.dream.applied, [55])
        self.assertIn("S7 execution authorization", sent[0][1])
        adapter.handle_message.assert_not_called()

    async def test_reject_dream_uses_dream_state_without_llm(self):
        daemon = _FakeDaemon()
        adapter = TelegramAdapter(PlatformConfig())
        adapter._maez_daemon = daemon
        sent = []

        async def fake_send(chat_id, content, **kwargs):
            sent.append((chat_id, str(content)))
            return mock.Mock(success=True)

        adapter.send = mock.AsyncMock(side_effect=fake_send)
        handled = await adapter._try_handle_dream_command_event(_event("/reject dream 56"))

        self.assertTrue(handled)
        self.assertEqual(daemon.dream.rejected, [56])
        self.assertIn("dream #56 rejected", sent[0][1])

    async def test_unrelated_command_falls_through(self):
        adapter = TelegramAdapter(PlatformConfig())
        adapter._maez_daemon = _FakeDaemon()

        handled = await adapter._try_handle_dream_command_event(_event("/status"))

        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
