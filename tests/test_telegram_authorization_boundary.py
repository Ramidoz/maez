import asyncio
import os
from types import SimpleNamespace
import unittest
from unittest import mock

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

    def test_model_picker_callback_uses_configured_allowed_users(self):
        adapter = TelegramAdapter(
            PlatformConfig(extra={"allowed_users": ["111"], "require_mention": False})
        )
        adapter._model_picker_state["123"] = {"providers": [], "on_model_selected": None}
        query = SimpleNamespace(
            data="mx",
            from_user=SimpleNamespace(id=222, first_name="Mallory"),
            message=SimpleNamespace(chat_id=123),
        )
        update = SimpleNamespace(callback_query=query)
        answers = []

        async def fake_query_call(_query, method, **kwargs):
            answers.append((method, kwargs))

        async def fail_model_picker(*_args, **_kwargs):
            raise AssertionError("unauthorized model picker callback was handled")

        with (
            mock.patch.object(adapter, "_egress_query_call", side_effect=fake_query_call),
            mock.patch.object(
                adapter,
                "_handle_model_picker_callback",
                side_effect=fail_model_picker,
            ),
        ):
            asyncio.run(adapter._handle_callback_query(update, None))

        self.assertEqual(answers[0][0], "answer")
        self.assertIn("not authorized", answers[0][1]["text"])

    def test_callback_configured_allowed_users_wins_over_env_fallback(self):
        adapter = TelegramAdapter(
            PlatformConfig(extra={"allowed_users": ["111"], "require_mention": False})
        )
        adapter._model_picker_state["123"] = {"providers": [], "on_model_selected": None}
        query = SimpleNamespace(
            data="mx",
            from_user=SimpleNamespace(id=222, first_name="Mallory"),
            message=SimpleNamespace(chat_id=123),
        )
        update = SimpleNamespace(callback_query=query)
        answers = []

        async def fake_query_call(_query, method, **kwargs):
            answers.append((method, kwargs))

        with (
            mock.patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": "222"}),
            mock.patch.object(adapter, "_egress_query_call", side_effect=fake_query_call),
        ):
            asyncio.run(adapter._handle_callback_query(update, None))

        self.assertEqual(answers[0][0], "answer")
        self.assertIn("not authorized", answers[0][1]["text"])
