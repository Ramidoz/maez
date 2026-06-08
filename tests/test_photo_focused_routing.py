"""Direction (b) wiring: maez_adapter routes photo turns through
synthesize_photo_turn (bounded working set), bypassing daemon.handle_message's
~megaprompt — with a gate and a safe fallback. Plus the clean-evidence stash.
"""

import json
import os
import unittest
from unittest import mock

from core.egress.provenance import ProvenancedText
from core.routing.focused_cognition import FocusedResult
from skills.surface.maez_adapter import MaezMessageHandler
from skills.surface.platform_base import MessageEvent, MessageType, PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter


PHOTO_CHANNEL_PROMPT = ProvenancedText.owner_message_context(
    "Local Maez vision analysis of the attached owner-sent photo(s).\n"
    "Image 1: a Reddit page about the SpaceX IPO is visible.",
    source_ref="telegram:photo_vision",
)


def _photo_event(**kw):
    base = dict(
        text="check this",
        message_type=MessageType.PHOTO,
        channel_prompt=PHOTO_CHANNEL_PROMPT,
        photo_analysis_text="Image 1: a Reddit page about the SpaceX IPO is visible.",
    )
    base.update(kw)
    return MessageEvent(**base)


class _FakeMemory:
    def get_telegram_exchanges(self, limit=None):
        return []


class _FakeCardStore:
    def get_open_for_channel(self, channel, chat_id):
        return []


class _FakePipeline:
    card_store = _FakeCardStore()


class _FakeTelegram:
    def _get_pipeline(self):
        return _FakePipeline()


def _fake_daemon(handle_capture):
    class FakeDaemon:
        memory = _FakeMemory()
        actions = object()
        telegram = _FakeTelegram()

        def handle_message(self, text, source, **kwargs):
            handle_capture["called"] = True
            handle_capture["text"] = text
            handle_capture["kwargs"] = kwargs
            return "MEGAPROMPT_REPLY"

    return FakeDaemon()


class PhotoFocusedRouting(unittest.IsolatedAsyncioTestCase):
    async def test_photo_turn_uses_focused_synthesis_not_megaprompt(self):
        cap = {}
        synth_calls = {}

        def fake_synth(*, analysis_text, caption, surface, **_k):
            synth_calls["analysis_text"] = analysis_text
            synth_calls["caption"] = caption
            synth_calls["surface"] = surface
            return FocusedResult(
                reply="That's the SpaceX IPO Reddit thread [E1].",
                cited_ids=["E1"],
                working_set_chars=10,
            )

        handler = MaezMessageHandler(_fake_daemon(cap))
        with mock.patch(
            "core.routing.focused_cognition.synthesize_photo_turn",
            side_effect=fake_synth,
        ), mock.patch.dict(os.environ, {"MAEZ_PHOTO_FOCUSED_SYNTH": "1"}):
            reply = await handler(_photo_event())

        self.assertIn("SpaceX IPO", reply)
        self.assertNotEqual(reply, "MEGAPROMPT_REPLY")
        self.assertNotIn("called", cap)  # daemon.handle_message NOT called
        self.assertEqual(synth_calls["caption"], "check this")
        self.assertIn("Reddit", synth_calls["analysis_text"])
        self.assertEqual(synth_calls["surface"], "telegram_surface")

    async def test_gate_off_falls_back_to_megaprompt(self):
        cap = {}
        handler = MaezMessageHandler(_fake_daemon(cap))
        with mock.patch(
            "core.routing.focused_cognition.synthesize_photo_turn"
        ) as synth, mock.patch.dict(os.environ, {"MAEZ_PHOTO_FOCUSED_SYNTH": "0"}):
            reply = await handler(_photo_event())
        synth.assert_not_called()
        self.assertTrue(cap.get("called"))
        self.assertEqual(reply, "MEGAPROMPT_REPLY")

    async def test_focused_failure_falls_back_to_megaprompt(self):
        cap = {}
        handler = MaezMessageHandler(_fake_daemon(cap))
        with mock.patch(
            "core.routing.focused_cognition.synthesize_photo_turn",
            side_effect=RuntimeError("boom"),
        ), mock.patch.dict(os.environ, {"MAEZ_PHOTO_FOCUSED_SYNTH": "1"}):
            reply = await handler(_photo_event())
        self.assertTrue(cap.get("called"))
        self.assertEqual(reply, "MEGAPROMPT_REPLY")

    async def test_focused_empty_falls_back_to_megaprompt(self):
        cap = {}

        def empty_synth(**_k):
            return FocusedResult(reply="   ", cited_ids=[], working_set_chars=0)

        handler = MaezMessageHandler(_fake_daemon(cap))
        with mock.patch(
            "core.routing.focused_cognition.synthesize_photo_turn",
            side_effect=empty_synth,
        ), mock.patch.dict(os.environ, {"MAEZ_PHOTO_FOCUSED_SYNTH": "1"}):
            reply = await handler(_photo_event())
        self.assertTrue(cap.get("called"))
        self.assertEqual(reply, "MEGAPROMPT_REPLY")


class PhotoAnalysisStash(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_photo_event_stashes_clean_analysis_text(self):
        adapter = TelegramAdapter(PlatformConfig())
        event = MessageEvent(
            text="check this",
            message_type=MessageType.PHOTO,
            media_urls=["/cache/a.jpg"],
            media_types=["image/jpeg"],
        )

        async def fake_vision(image_url, user_prompt):
            return json.dumps(
                {
                    "success": True,
                    "analysis": "a Reddit page about the SpaceX IPO",
                    "error": "",
                }
            )

        with mock.patch(
            "tools.vision_tools.vision_analyze_tool", side_effect=fake_vision
        ):
            await adapter._analyze_photo_event(event)

        self.assertTrue(getattr(event, "photo_analysis_text", None))
        self.assertIn("Reddit", event.photo_analysis_text)
        # clean evidence: per-image analysis, not the injection preamble
        self.assertNotIn("Local Maez vision analysis", event.photo_analysis_text)


if __name__ == "__main__":
    unittest.main()
