# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Web chat history and pending-send UX guards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class WebChatHistoryNormalizationTests(unittest.TestCase):
    def test_combined_owner_asked_record_splits_even_when_role_is_user(self):
        from skills.web_interface import _normalize_chat_history_record

        out = _normalize_chat_history_record(
            role="user",
            content="the owner asked: hello from maez.live\nMaez replied: I'm here.",
            timestamp="2026-06-17T22:00:00+00:00",
        )

        self.assertEqual(
            out,
            [
                {
                    "role": "user",
                    "content": "hello from maez.live",
                    "timestamp": "2026-06-17T22:00:00+00:00",
                },
                {
                    "role": "assistant",
                    "content": "I'm here.",
                    "timestamp": "2026-06-17T22:00:00+00:00",
                },
            ],
        )

    def test_daemon_owner_record_splits_for_history_display(self):
        from skills.web_interface import _normalize_chat_history_record

        out = _normalize_chat_history_record(
            role="user",
            content="the owner (telegram_surface): Hi Maez\nMaez: Hey Rohit.",
            timestamp="2026-06-17T22:01:00+00:00",
        )

        self.assertEqual([m["role"] for m in out], ["user", "assistant"])
        self.assertEqual(out[0]["content"], "Hi Maez")
        self.assertEqual(out[1]["content"], "Hey Rohit.")

    def test_standalone_maez_record_displays_as_assistant(self):
        from skills.web_interface import _normalize_chat_history_record

        out = _normalize_chat_history_record(
            role="user",
            content="Maez: The web search returned sparse results.",
            timestamp="2026-06-17T22:01:30+00:00",
        )

        self.assertEqual(
            out,
            [
                {
                    "role": "assistant",
                    "content": "The web search returned sparse results.",
                    "timestamp": "2026-06-17T22:01:30+00:00",
                }
            ],
        )

    def test_normal_user_record_stays_user(self):
        from skills.web_interface import _normalize_chat_history_record

        out = _normalize_chat_history_record(
            role="user",
            content="plain user message",
            timestamp="2026-06-17T22:02:00+00:00",
        )

        self.assertEqual(
            out,
            [
                {
                    "role": "user",
                    "content": "plain user message",
                    "timestamp": "2026-06-17T22:02:00+00:00",
                }
            ],
        )

    def test_cockpit_sessions_endpoint_splits_owner_asked_records(self):
        import skills.web_interface as wi

        class FakeMemoryManager:
            def get_telegram_exchanges(self, limit=6):
                return [
                    {
                        "content": (
                            "the owner asked: Summarize today's signals\n"
                            "Maez replied: The web search returned sparse results."
                        ),
                        "metadata": {"timestamp": "2026-06-17T19:25:01+00:00"},
                    }
                ]

        with patch("memory.memory_manager.MemoryManager", return_value=FakeMemoryManager()):
            client = wi.app.test_client()
            res = client.get("/api/v1/chat/sessions")

        self.assertEqual(res.status_code, 200)
        history = res.get_json()["sessions"][0]["history"]
        self.assertEqual(
            [(turn["role"], turn["content"]) for turn in history],
            [
                ("user", "Summarize today's signals"),
                ("assistant", "The web search returned sparse results."),
            ],
        )

    def test_cockpit_sessions_endpoint_treats_standalone_maez_rows_as_assistant(self):
        import skills.web_interface as wi

        class FakeMemoryManager:
            def get_telegram_exchanges(self, limit=6):
                return [
                    {
                        "content": "Summarize today's signals",
                        "metadata": {"timestamp": "2026-06-17T19:24:55+00:00"},
                    },
                    {
                        "content": 'Maez: The web search returned sparse results.',
                        "metadata": {"timestamp": "2026-06-17T19:25:01+00:00"},
                    },
                ]

        with patch("memory.memory_manager.MemoryManager", return_value=FakeMemoryManager()):
            client = wi.app.test_client()
            res = client.get("/api/v1/chat/sessions")

        self.assertEqual(res.status_code, 200)
        history = res.get_json()["sessions"][0]["history"]
        self.assertEqual(
            [(turn["role"], turn["content"]) for turn in history],
            [
                ("user", "Summarize today's signals"),
                ("assistant", "The web search returned sparse results."),
            ],
        )


class WebChatPendingSendScriptTests(unittest.TestCase):
    def test_live_app_script_guards_history_render_during_pending_send(self):
        html = (_REPO / "ui" / "app.html").read_text(encoding="utf-8")

        self.assertIn("let sendInFlight = false;", html)
        self.assertIn("sendInFlight = true;", html)
        self.assertIn("sendInFlight = false;", html)
        self.assertIn("if (!sendInFlight && conversationHistory.length === 0)", html)

    def test_legacy_inline_chat_script_keeps_same_guard(self):
        import skills.web_interface as wi

        html = wi.HTML_PAGE
        self.assertIn("let sendInFlight = false;", html)
        self.assertIn("sendInFlight = true;", html)
        self.assertIn("sendInFlight = false;", html)
        self.assertIn("if (!sendInFlight && conversationHistory.length === 0)", html)


if __name__ == "__main__":
    unittest.main()
