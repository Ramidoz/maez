import json
import unittest
from unittest import mock

from core.egress.provenance import ProvenancedText
from skills.surface.maez_adapter import MaezMessageHandler
from skills.surface.platform_base import MessageEvent, MessageType, PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


class ChatPhotoWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_batch_flush_analyzes_album_with_bound_before_handling(self):
        adapter = TelegramAdapter(PlatformConfig())
        event = MessageEvent(
            text="caption",
            message_type=MessageType.PHOTO,
            media_urls=["/cache/a.jpg", "/cache/b.jpg", "/cache/c.jpg", "/cache/d.jpg"],
            media_types=["image/jpeg"] * 4,
        )
        adapter._pending_photo_batches["batch"] = event

        calls = []

        async def fake_vision(image_url, user_prompt):
            calls.append((image_url, user_prompt))
            return json.dumps(
                {"success": True, "analysis": f"analysis for {image_url[-5]}", "error": ""}
            )

        async def no_sleep(_delay):
            return None

        handled = []

        async def fake_handle(message_event):
            handled.append(message_event)

        with mock.patch(
            "skills.surface.telegram_adapter.asyncio.sleep", side_effect=no_sleep
        ), mock.patch(
            "tools.vision_tools.vision_analyze_tool", side_effect=fake_vision
        ):
            adapter.handle_message = mock.AsyncMock(side_effect=fake_handle)
            await adapter._flush_photo_batch("batch")

        self.assertEqual([call[0] for call in calls], event.media_urls[:3])
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(handled), 1)
        self.assertIs(handled[0], event)
        self.assertEqual("caption", event.text)
        self.assertIsNotNone(event.channel_prompt)
        assert event.channel_prompt is not None
        self.assertIsInstance(event.channel_prompt, ProvenancedText)
        self.assertEqual(
            {span.origin_class for span in event.channel_prompt.spans},
            {"owner_message_context"},
        )
        prompt_text = event.channel_prompt.text
        self.assertIn("Local Maez vision analysis", prompt_text)
        self.assertIn("Image 1: analysis for a", prompt_text)
        self.assertIn("Image 2: analysis for b", prompt_text)
        self.assertIn("Image 3: analysis for c", prompt_text)
        self.assertIn("+1 more image not analyzed", prompt_text)
        self.assertIn("owner-sent photo vision is separate from desktop screen observation", prompt_text)
        self.assertIn("desktop screen observation is disabled", prompt_text)
        self.assertNotIn("analysis for", event.text)
        self.assertNotIn("I don't have vision", prompt_text)
        self.assertNotIn("System is healthy", prompt_text)

    async def test_photo_analysis_failure_injects_honest_no_vision_fallback(self):
        adapter = TelegramAdapter(PlatformConfig())
        event = MessageEvent(
            text="caption",
            message_type=MessageType.PHOTO,
            media_urls=["/cache/a.jpg"],
            media_types=["image/jpeg"],
        )
        adapter._pending_photo_batches["batch"] = event

        async def fake_vision(image_url, user_prompt):
            return json.dumps({"success": False, "analysis": "", "error": "vision_call_failed"})

        async def no_sleep(_delay):
            return None

        handled = []

        async def fake_handle(message_event):
            handled.append(message_event)

        with mock.patch(
            "skills.surface.telegram_adapter.asyncio.sleep", side_effect=no_sleep
        ), mock.patch(
            "tools.vision_tools.vision_analyze_tool", side_effect=fake_vision
        ):
            adapter.handle_message = mock.AsyncMock(side_effect=fake_handle)
            await adapter._flush_photo_batch("batch")

        self.assertEqual(len(handled), 1)
        self.assertEqual("caption", event.text)
        self.assertIsNotNone(event.channel_prompt)
        assert event.channel_prompt is not None
        self.assertIsInstance(event.channel_prompt, ProvenancedText)
        self.assertEqual(
            {span.origin_class for span in event.channel_prompt.spans},
            {"owner_message_context"},
        )
        self.assertIn(
            "Image 1: [Maez could not see this image.]",
            event.channel_prompt.text,
        )
        self.assertNotIn("analysis", event.text)

    async def test_channel_prompt_reaches_daemon_as_system_context_note(self):
        event = MessageEvent(
            text="Fine check this image",
            message_type=MessageType.PHOTO,
            channel_prompt=(
                "Local Maez vision analysis of the attached owner-sent photo:\n"
                "Image 1: a Reddit post is visible."
            ),
        )
        captured = {}

        class FakeMemory:
            def get_telegram_exchanges(self, limit=None):
                return []

        class FakeDaemon:
            memory = FakeMemory()
            actions = None
            telegram = None

            def handle_message(self, text, source, **kwargs):
                captured["text"] = text
                captured["source"] = source
                captured["kwargs"] = kwargs
                return "ok"

        handler = MaezMessageHandler(FakeDaemon())
        reply = await handler(event)

        self.assertEqual(reply, "ok")
        self.assertEqual(captured["text"], "Fine check this image")
        self.assertIn("context_note", captured["kwargs"])
        self.assertIn("Local Maez vision analysis", str(captured["kwargs"]["context_note"]))

    async def test_photo_context_turn_skips_generic_brain_loop(self):
        event = MessageEvent(
            text="Check this",
            message_type=MessageType.PHOTO,
            channel_prompt=ProvenancedText.owner_message_context(
                "Local Maez vision analysis of the attached owner-sent photo(s).\n"
                "Image 1: a Reddit page is visible.",
                source_ref="telegram:photo_vision",
            ),
        )
        captured = {}

        class FakeMemory:
            def get_telegram_exchanges(self, limit=None):
                return []

        class FakeCardStore:
            def get_open_for_channel(self, channel, chat_id):
                return []

        class FakePipeline:
            card_store = FakeCardStore()

        class FakeTelegram:
            def _get_pipeline(self):
                return FakePipeline()

        class FakeDaemon:
            memory = FakeMemory()
            actions = object()
            telegram = FakeTelegram()

            def handle_message(self, text, source, **kwargs):
                captured["text"] = text
                captured["source"] = source
                captured["kwargs"] = kwargs
                return "ok"

        handler = MaezMessageHandler(FakeDaemon())
        with mock.patch("core.brain_loop.run_brain_loop") as run_brain_loop:
            reply = await handler(event)

        self.assertEqual(reply, "ok")
        run_brain_loop.assert_not_called()
        self.assertEqual(captured["text"], "Check this")
        self.assertEqual(captured["kwargs"].get("transcript"), "")
        self.assertIs(captured["kwargs"].get("context_note"), event.channel_prompt)


if __name__ == "__main__":
    unittest.main()
