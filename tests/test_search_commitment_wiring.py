import os
import inspect
import asyncio
import unittest
from unittest import mock

from core.brain.conversation_controller import ConversationController
from core.search.searxng_client import FakeSearchBackend
from skills.telegram_voice import TelegramVoice


def _make_controller() -> ConversationController:
    return ConversationController(memory=None, pipeline=None, daemon=None)


class SearchCommitmentWiringTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))
        self.ctrl = _make_controller()

    def test_default_off_no_offer_no_search(self):
        backend = FakeSearchBackend()

        self.assertFalse(
            self.ctrl.store_search_offer(
                "telegram_text",
                "owner",
                "llama.cpp",
                health="healthy",
            )
        )
        self.assertIsNone(
            self.ctrl.resolve_search_affirmation(
                "telegram_text",
                "owner",
                "yeah sure",
                backend,
                now_ts=1.0,
                turns_since=1,
            )
        )
        self.assertEqual(backend.searched, [])

    def test_offer_then_yes_executes_exact_query(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        backend = FakeSearchBackend(results=[{"title": "T", "url": "U", "content": "C"}])

        self.assertTrue(
            self.ctrl.store_search_offer(
                "telegram_text",
                "owner",
                "llama.cpp news",
                health="healthy",
                now_ts=1.0,
            )
        )
        out = self.ctrl.resolve_search_affirmation(
            "telegram_text",
            "owner",
            "yeah sure",
            backend,
            now_ts=2.0,
            turns_since=1,
        )

        self.assertEqual(out[0]["title"], "T")
        self.assertEqual(backend.searched, ["llama.cpp news"])
        self.assertIsNone(self.ctrl.get_search_offer("telegram_text", "owner"))

    def test_degraded_creates_no_offer(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"

        self.assertFalse(
            self.ctrl.store_search_offer(
                "telegram_text",
                "owner",
                "q",
                health="degraded",
            )
        )
        self.assertIsNone(self.ctrl.get_search_offer("telegram_text", "owner"))

    def test_no_pending_receipt_does_not_health_check_backend(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"

        class ExplodingHealthBackend(FakeSearchBackend):
            def health(self):
                raise AssertionError("health should not be checked without a receipt")

        self.assertIsNone(
            self.ctrl.resolve_search_affirmation(
                "telegram_text",
                "owner",
                "yeah sure",
                ExplodingHealthBackend(),
                now_ts=2.0,
                turns_since=1,
            )
        )

    def test_awaiting_card_blocks_resolution(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        backend = FakeSearchBackend()
        self.ctrl.store_search_offer(
            "telegram_text",
            "owner",
            "q",
            health="healthy",
            now_ts=1.0,
        )

        with mock.patch.object(self.ctrl, "has_awaiting_card", return_value=True):
            out = self.ctrl.resolve_search_affirmation(
                "telegram_text",
                "owner",
                "yeah sure",
                backend,
                now_ts=2.0,
                turns_since=1,
            )

        self.assertIsNone(out)
        self.assertEqual(backend.searched, [])


class TelegramSearchCommitmentSeamTests(unittest.TestCase):
    def test_typed_resolver_runs_before_legacy_offer_consumer(self):
        src = inspect.getsource(TelegramVoice._try_offer_binding_intent)

        self.assertIn("resolve_search_affirmation", src)
        self.assertLess(
            src.index("resolve_search_affirmation"),
            src.index("consume_offer_approval"),
        )

    def test_offer_creation_runs_before_general_reply_path(self):
        src = inspect.getsource(TelegramVoice._handle_message)

        self.assertIn("_try_search_commitment_offer_intent", src)
        self.assertLess(
            src.index("_try_search_commitment_offer_intent"),
            src.index("await self._process_message"),
        )

    def test_offer_creation_uses_typed_store_not_legacy_slot(self):
        method = getattr(TelegramVoice, "_try_search_commitment_offer_intent")
        src = inspect.getsource(method)

        self.assertIn("store_search_offer", src)
        self.assertNotIn("maybe_store_offer", src)

    def test_health_loss_after_offer_sends_honest_unavailable(self):
        async def run():
            os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
            tv = TelegramVoice.__new__(TelegramVoice)
            tv.authorized_user = 123
            tv._controller = _make_controller()
            tv._controller.store_search_offer(
                "telegram_text",
                "123",
                "llama.cpp news",
                health="healthy",
                now_ts=1.0,
            )
            tv._search_commitment_backend = lambda: FakeSearchBackend(health="down")

            with mock.patch("skills.telegram_voice._reply_text", new_callable=mock.AsyncMock) as reply:
                handled = await tv._try_offer_binding_intent(object(), "yeah sure")

            self.assertTrue(handled)
            sent_text = reply.await_args.args[1]
            self.assertIn("unavailable", sent_text.lower())

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
