"""Direction (b) wiring (post-review architecture): the adapter passes the
success-only photo analysis into daemon.handle_message, which synthesizes photo
turns over a BOUNDED working set INSIDE its reply pipeline — so the photo reply
still flows through strip / self-claim-audit / store_telegram / trace. The
adapter does NOT bypass handle_message and does NOT import the low-level audit.
"""

import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

from core.egress.provenance import ProvenancedText
from skills.surface.maez_adapter import MaezMessageHandler
from skills.surface.platform_base import MessageEvent, MessageType, PlatformConfig
from skills.surface.telegram_adapter import TelegramAdapter

_REPO = Path(__file__).resolve().parents[1]


def _handle_message_body() -> str:
    src = (_REPO / "daemon" / "maez_daemon.py").read_text()
    start = src.find("def handle_message")
    assert start != -1, "handle_message not found"
    m = re.search(r"\n    def ", src[start + 20:])
    end = start + 20 + m.start() if m else len(src)
    return src[start:end]


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
            return "PIPELINE_REPLY"

    return FakeDaemon()


class AdapterPassesPhotoAnalysisToHandleMessage(unittest.IsolatedAsyncioTestCase):
    async def test_passes_success_analysis_through_handle_message(self):
        cap = {}
        handler = MaezMessageHandler(_fake_daemon(cap))
        reply = await handler(
            _photo_event(photo_analysis_text="Image 1: a Reddit page.")
        )
        # The adapter does NOT bypass handle_message — it routes through it.
        self.assertTrue(cap.get("called"))
        self.assertEqual(reply, "PIPELINE_REPLY")
        self.assertEqual(cap["kwargs"].get("photo_analysis"), "Image 1: a Reddit page.")

    async def test_passes_none_when_no_successful_analysis(self):
        cap = {}
        handler = MaezMessageHandler(_fake_daemon(cap))
        await handler(_photo_event(photo_analysis_text=None))
        self.assertTrue(cap.get("called"))
        self.assertIsNone(cap["kwargs"].get("photo_analysis"))


class PhotoSynthesisLivesInsideThePipeline(unittest.TestCase):
    """Structural guarantees (mirrors test_model_reply_persistence): the photo
    synthesis runs INSIDE handle_message, before strip + store, so the reply is
    stripped, audited, stored, traced — never bypassed."""

    def test_photo_synth_runs_before_strip_and_store(self):
        body = _handle_message_body()
        i_synth = body.find("synthesize_photo_turn")
        i_strip = body.find("strip_tool_call_leaks")
        i_store = body.find("store_telegram")
        self.assertGreater(i_synth, -1, "photo synthesis not wired into handle_message")
        self.assertGreater(i_strip, -1)
        self.assertGreater(i_store, -1)
        self.assertLess(i_synth, i_strip, "photo synth must precede strip")
        self.assertLess(i_synth, i_store, "photo synth must precede store_telegram")

    def test_photo_branch_is_gated_and_evidence_driven(self):
        body = _handle_message_body()
        self.assertIn("photo_analysis", body)
        self.assertIn("photo_focused_synth_enabled", body)


class AdapterDoesNotImportLowLevelAudit(unittest.TestCase):
    def test_adapter_has_no_single_line_self_claim_audit_import(self):
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()
        self.assertNotIn("from core.self_claim_audit import audit", src)
        self.assertNotIn("core.self_claim_audit import audit as", src)


class PhotoAnalysisStash(unittest.IsolatedAsyncioTestCase):
    async def test_successful_vision_stashes_clean_analysis_text(self):
        adapter = TelegramAdapter(PlatformConfig())
        event = MessageEvent(
            text="check this",
            message_type=MessageType.PHOTO,
            media_urls=["/cache/a.jpg"],
            media_types=["image/jpeg"],
        )

        async def ok_vision(image_url, user_prompt):
            return json.dumps(
                {"success": True, "analysis": "a Reddit page about the SpaceX IPO", "error": ""}
            )

        with mock.patch("tools.vision_tools.vision_analyze_tool", side_effect=ok_vision):
            await adapter._analyze_photo_event(event)

        self.assertTrue(getattr(event, "photo_analysis_text", None))
        self.assertIn("Reddit", event.photo_analysis_text)
        self.assertNotIn("Local Maez vision analysis", event.photo_analysis_text)

    async def test_failed_vision_leaves_photo_analysis_text_none(self):
        # Finding 2: a "could not see" failure is NOT evidence — must not route
        # to focused synthesis. photo_analysis_text stays None → legacy fallback.
        adapter = TelegramAdapter(PlatformConfig())
        event = MessageEvent(
            text="check this",
            message_type=MessageType.PHOTO,
            media_urls=["/cache/a.jpg"],
            media_types=["image/jpeg"],
        )

        async def fail_vision(image_url, user_prompt):
            return json.dumps({"success": False, "analysis": "", "error": "vision_call_failed"})

        with mock.patch("tools.vision_tools.vision_analyze_tool", side_effect=fail_vision):
            await adapter._analyze_photo_event(event)

        self.assertIsNone(event.photo_analysis_text)
        # the legacy injection still carries the honest "could not see" line
        self.assertIn("could not see", str(event.channel_prompt).lower())


if __name__ == "__main__":
    unittest.main()
