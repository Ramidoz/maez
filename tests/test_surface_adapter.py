# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for the vendored surface package + Maez glue.

Locks in the integration shape — MessageEvent in, Maez daemon reply
out, audit rail applied, surface label threaded through. Does NOT
exercise the real TelegramAdapter network path (that requires a live
bot token); the shape tests here confirm the glue is wired correctly
so a future bootstrap call produces a working bot.
"""
from __future__ import annotations

import asyncio
import os
import time
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[1]

from core.brain.conversation_controller import ConversationController
from core.search.searxng_client import FakeSearchBackend
from skills.surface import (
    MessageEvent, Platform, PlatformConfig, SessionSource, build_session_key,
    MaezMessageHandler, build_telegram_adapter, SURFACE_NAME,
)


class SurfaceImports(unittest.TestCase):
    def test_package_exports_present(self):
        # Sanity — the public re-exports resolve
        self.assertIs(Platform.TELEGRAM.value, "telegram")
        self.assertEqual(SURFACE_NAME, "telegram_surface")

    def test_platform_config_shape(self):
        cfg = PlatformConfig(enabled=True, token="dummy",
                             extra={"allowed_users": [123]})
        d = cfg.to_dict()
        self.assertTrue(d["enabled"])
        self.assertEqual(d["token"], "dummy")
        self.assertEqual(d["extra"]["allowed_users"], [123])

    def test_session_key_builds(self):
        src = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="42",
            user_id="rohit",
            user_name="Rohit",
            chat_type="dm",
        )
        key = build_session_key(src)
        self.assertIsInstance(key, str)
        self.assertIn("telegram", key)


class _FakeDaemon:
    """Minimal daemon stand-in for handler tests."""

    def __init__(self, reply: str = "hello back"):
        self._reply = reply
        self.last_source: Optional[str] = None
        self.last_text: Optional[str] = None

    def handle_message(self, text: str, source: str = "unknown",
                       **kwargs) -> str:
        # 2026-04-23 Commit 1: the daemon now owns the final-reply
        # audit. A faithful stand-in applies the same helper so tests
        # that check "did the fabrication get rewritten end-to-end"
        # still pass without needing a real daemon.
        self.last_text = text
        self.last_source = source
        self.last_kwargs = kwargs
        reply = self._reply
        try:
            from core.safety.audited_output import audit_assistant_text
            reply = audit_assistant_text(
                reply,
                surface=source,
                transcript=kwargs.get("transcript", "") or "",
                signals_present=kwargs.get("signals_present"),
                signals_absent=kwargs.get("signals_absent"),
            )
        except Exception:
            pass
        return reply


class _EmptyCards:
    def get_open_for_channel(self, *args, **kwargs):
        return []


class _Pipe:
    def __init__(self, *, open_cards=None, dialog_reply="card handled"):
        self.card_store = self
        self._open_cards = [] if open_cards is None else open_cards
        self._dialog_reply = dialog_reply
        self.replies = []

    def get_open_for_channel(self, *args, **kwargs):
        return list(self._open_cards)

    def handle_reply(self, **kwargs):
        self.replies.append(kwargs)

        class _Result:
            dialog_reply_text = self._dialog_reply

        return _Result()


class _TelegramWithController:
    def __init__(self, controller=None, pipe=None):
        self._controller = controller or ConversationController(
            memory=None,
            pipeline=None,
            daemon=None,
        )
        self._pipe = pipe or _Pipe()

    def _get_pipeline(self):
        return self._pipe


class HandlerRouting(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))

    def test_handler_routes_text_through_daemon(self):
        daemon = _FakeDaemon(reply="I heard you")
        handler = MaezMessageHandler(daemon)

        event = MessageEvent(
            text="ping",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )
        result = asyncio.run(handler(event))
        self.assertEqual(result, "I heard you")
        # Handler must keep owner text clean. Tool/no-tool scaffolding
        # belongs in transcript/system context, not in the text that
        # memory/search/trace treat as the owner's message.
        self.assertEqual(daemon.last_text, "ping")
        self.assertNotIn("TURN STATE", daemon.last_text or "")
        self.assertNotIn("JARVIS TRANSCRIPT", daemon.last_text or "")
        self.assertEqual(daemon.last_source, SURFACE_NAME)

    def test_empty_text_returns_none(self):
        handler = MaezMessageHandler(_FakeDaemon())
        event = MessageEvent(text="", source=None)
        result = asyncio.run(handler(event))
        self.assertIsNone(result)

    def test_daemon_raising_returns_error_string(self):
        class Raiser:
            def handle_message(self, text, source="unknown", **kwargs):
                raise RuntimeError("brain offline")

        handler = MaezMessageHandler(Raiser())
        event = MessageEvent(text="anyone home?",
                             source=SessionSource(platform=Platform.TELEGRAM,
                                                  chat_id="c"))
        result = asyncio.run(handler(event))
        self.assertIsNotNone(result)
        self.assertIn("internal error", result)

    def test_audit_runs_on_reply(self):
        """If the daemon returns a fabrication-shape reply, the
        self-claim audit rewrites it before return.

        Integration test — hits the real grounding judge endpoint
        configured via /etc/maez/model.env. Stubs the judge return at
        the HTTP layer so the test doesn't need the live llama-judge
        service up; asserts that audit pipeline correctly rewrites when
        the judge flags."""
        from unittest.mock import patch
        fab = "I've been testing the Maelstrom framework (2.0.0)."
        handler = MaezMessageHandler(_FakeDaemon(reply=fab))
        event = MessageEvent(text="anything new?",
                             source=SessionSource(platform=Platform.TELEGRAM,
                                                  chat_id="c",
                                                  user_id="rohit"))
        # Force the judge to flag the Maelstrom span — isolates the
        # audit pipeline shape from judge-model capability / env setup.
        fake_out = (
            '{"ungrounded": [{"text": "Maelstrom framework (2.0.0)", '
            '"reason": "fabricated internal framework name"}]}'
        )
        with patch("core.grounding_judge._call_dedicated_judge",
                   return_value=fake_out):
            result = asyncio.run(handler(event))
        self.assertIsNotNone(result)
        self.assertNotIn("Maelstrom", result,
            f"audit did not rewrite fabrication: {result!r}")

    def test_adapter_does_not_fold_tool_scaffolding_into_owner_text(self):
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()
        self.assertNotIn("build_synthesis_user_text", src)
        self.assertNotIn("synthesis_text", src)
        self.assertIn("text,", src)
        self.assertIn("transcript=jarvis_transcript", src)

    def test_brain_loop_receives_telegram_surface_label(self):
        """Dispatcher recall must see the real Telegram surface.

        Living recall is intentionally telegram-scoped. Passing the
        generic "adapter" label here makes a live Telegram turn fall
        back to legacy recall even when MAEZ_RECALL_TRIAD_ENABLED=1.
        """

        class _Cards:
            def get_open_for_channel(self, *args, **kwargs):
                return []

        class _Pipe:
            card_store = _Cards()

        class _Telegram:
            def _get_pipeline(self):
                return _Pipe()

        class _Result:
            transcript = ""
            tool_calls = []

        daemon = _FakeDaemon(reply="I heard you")
        daemon.actions = object()
        daemon.telegram = _Telegram()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="living recall probe",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        with patch("core.brain_loop.run_brain_loop", return_value=_Result()) as run:
            result = asyncio.run(handler(event))

        self.assertEqual(result, "I heard you")
        self.assertEqual(run.call_args.kwargs["surface"], SURFACE_NAME)

    def test_surface_v2_search_commitment_offers_before_daemon_synthesis(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        handler._search_commitment_backend = lambda: FakeSearchBackend(health="healthy")
        event = MessageEvent(
            text="what's the latest llama.cpp release?",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        result = asyncio.run(handler(event))

        self.assertIn("Want me to?", result)
        self.assertIsNotNone(
            daemon.telegram._controller.get_search_offer("telegram_text", "c")
        )
        self.assertIsNone(daemon.last_text)

    def test_surface_v2_search_commitment_resolves_yes_to_results(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        backend = FakeSearchBackend(
            health="healthy",
            results=[{"title": "Release", "url": "https://example.test", "content": "notes"}],
        )
        ctrl = ConversationController(memory=None, pipeline=None, daemon=None)
        self.assertTrue(
            ctrl.store_search_offer(
                "telegram_text",
                "c",
                "llama.cpp release",
                health="healthy",
                now_ts=time.time(),
            )
        )
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController(controller=ctrl)
        handler = MaezMessageHandler(daemon)
        handler._search_commitment_backend = lambda: backend
        event = MessageEvent(
            text="yeah sure",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        result = asyncio.run(handler(event))

        self.assertIn("Here's what I found", result)
        self.assertIn("Release", result)
        self.assertEqual(backend.searched, ["llama.cpp release"])
        self.assertIsNone(daemon.last_text)

    def test_surface_v2_open_card_precedes_search_commitment_yes(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        backend = FakeSearchBackend(health="healthy")
        ctrl = ConversationController(memory=None, pipeline=None, daemon=None)
        ctrl.store_search_offer(
            "telegram_text",
            "c",
            "llama.cpp release",
            health="healthy",
            now_ts=time.time(),
        )
        pipe = _Pipe(open_cards=[{"id": "card-1"}], dialog_reply="card handled")
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController(controller=ctrl, pipe=pipe)
        handler = MaezMessageHandler(daemon)
        handler._search_commitment_backend = lambda: backend
        event = MessageEvent(
            text="yeah sure",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        result = asyncio.run(handler(event))

        self.assertEqual(result, "card handled")
        self.assertEqual(backend.searched, [])
        self.assertIsNotNone(ctrl.get_search_offer("telegram_text", "c"))

    def test_surface_v2_health_loss_after_offer_is_honest_unavailable(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        ctrl = ConversationController(memory=None, pipeline=None, daemon=None)
        ctrl.store_search_offer(
            "telegram_text",
            "c",
            "llama.cpp release",
            health="healthy",
            now_ts=time.time(),
        )
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController(controller=ctrl)
        handler = MaezMessageHandler(daemon)
        handler._search_commitment_backend = lambda: FakeSearchBackend(health="down")
        event = MessageEvent(
            text="yeah sure",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        result = asyncio.run(handler(event))

        self.assertIn("unavailable", result.lower())
        self.assertIsNone(daemon.last_text)

    def test_surface_v2_degraded_search_creates_no_executable_offer(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        daemon = _FakeDaemon(reply="general reply")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        handler._search_commitment_backend = lambda: FakeSearchBackend(health="degraded")
        event = MessageEvent(
            text="what's the latest llama.cpp release?",
            source=SessionSource(
                platform=Platform.TELEGRAM,
                chat_id="c",
                user_id="rohit",
                user_name="Rohit",
            ),
        )

        result = asyncio.run(handler(event))

        self.assertIn("degraded", result.lower())
        self.assertIsNone(daemon.telegram._controller.get_search_offer("telegram_text", "c"))
        self.assertIsNone(daemon.last_text)


class BuildTelegramAdapter(unittest.TestCase):
    def test_builder_returns_adapter_with_handler_set(self):
        daemon = _FakeDaemon()
        adapter = build_telegram_adapter(
            token="fake_token", authorized_users=[42], daemon=daemon,
        )
        # Extension point must be populated
        self.assertIsNotNone(adapter._message_handler)
        self.assertIsInstance(adapter._message_handler, MaezMessageHandler)
        self.assertIs(adapter._message_handler.daemon, daemon)
        # Platform auto-detected by the subclass
        self.assertEqual(adapter.platform, Platform.TELEGRAM)

    def test_link_previews_disabled_by_default(self):
        adapter = build_telegram_adapter(
            token="fake_token", authorized_users=[42], daemon=_FakeDaemon(),
        )

        self.assertTrue(adapter._disable_link_previews)
        self.assertTrue(adapter._link_preview_kwargs())

    def test_link_previews_can_be_reenabled_by_config(self):
        cfg = PlatformConfig(
            enabled=True,
            token="fake_token",
            extra={"authorized_users": [42], "disable_link_previews": False},
        )
        from skills.surface.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(cfg)

        self.assertFalse(adapter._disable_link_previews)
        self.assertEqual(adapter._link_preview_kwargs(), {})


if __name__ == "__main__":
    unittest.main()
