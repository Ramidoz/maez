from types import SimpleNamespace
import unittest

from skills.surface.platform_base import PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


def _message(*, user_id: int, chat_type: str = "private"):
    return SimpleNamespace(
        chat=SimpleNamespace(type=chat_type, id=123),
        from_user=SimpleNamespace(id=user_id),
        message_thread_id=None,
        reply_to_message=None,
        text="hello",
        caption=None,
    )


class TelegramAllowedUsersBoundaryTest(unittest.TestCase):
    def test_non_allowed_sender_is_rejected_before_owner_event(self):
        adapter = TelegramAdapter(
            PlatformConfig(extra={"allowed_users": ["111"], "require_mention": False})
        )

        self.assertFalse(adapter._should_process_message(_message(user_id=222)))

    def test_allowed_sender_is_accepted(self):
        adapter = TelegramAdapter(
            PlatformConfig(extra={"allowed_users": ["111"], "require_mention": False})
        )

        self.assertTrue(adapter._should_process_message(_message(user_id=111)))

    def test_star_explicitly_allows_all_senders(self):
        adapter = TelegramAdapter(
            PlatformConfig(extra={"allowed_users": ["*"], "require_mention": False})
        )

        self.assertTrue(adapter._should_process_message(_message(user_id=222)))
