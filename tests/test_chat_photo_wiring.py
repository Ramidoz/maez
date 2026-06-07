import json
import unittest
from unittest import mock

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
        self.assertIn("Image 1: analysis for a", event.text)
        self.assertIn("Image 2: analysis for b", event.text)
        self.assertIn("Image 3: analysis for c", event.text)
        self.assertIn("+1 more image not analyzed", event.text)
        self.assertIn("caption", event.text)

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
        self.assertIn("Image 1: [Maez could not see this image.]", event.text)
        self.assertIn("caption", event.text)
        self.assertNotIn("analysis", event.text)


if __name__ == "__main__":
    unittest.main()
