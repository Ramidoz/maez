# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.workshop — session storage + turn orchestrator."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "ws.db"
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_WORKSHOP_DB": str(self._db_path)},
        )
        self._env.start()
        from core import workshop
        importlib.reload(workshop)
        self.ws = workshop

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class SessionCRUD(_Base):
    def test_create_and_fetch(self):
        sid = self.ws.create_session(title="refactor audit", model="sonnet")
        self.assertIsInstance(sid, str)
        s = self.ws.get_session(sid)
        self.assertIsNotNone(s)
        self.assertEqual(s.title, "refactor audit")
        self.assertEqual(s.model, "sonnet")
        # Default system prompt is populated
        self.assertIn("Workshop", s.system_prompt)

    def test_list_sessions_newest_first(self):
        s1 = self.ws.create_session(title="A")
        s2 = self.ws.create_session(title="B")
        s3 = self.ws.create_session(title="C")
        rows = self.ws.list_sessions()
        self.assertEqual([r.id for r in rows[:3]], [s3, s2, s1])

    def test_update_title(self):
        sid = self.ws.create_session(title="first")
        self.assertTrue(self.ws.update_session_title(sid, "renamed"))
        s = self.ws.get_session(sid)
        self.assertEqual(s.title, "renamed")
        # Non-existent session returns False cleanly
        self.assertFalse(self.ws.update_session_title("bogus", "x"))

    def test_delete_session_cascades_turns(self):
        sid = self.ws.create_session(title="temp")
        self.ws._persist_turn(sid, "user", "hello")
        self.ws._persist_turn(sid, "assistant", "hi")
        self.assertEqual(len(self.ws.get_turns(sid)), 2)
        self.assertTrue(self.ws.delete_session(sid))
        # Turns should be gone too via cascade
        self.assertEqual(self.ws.get_turns(sid), [])
        self.assertIsNone(self.ws.get_session(sid))

    def test_custom_system_prompt(self):
        sid = self.ws.create_session(
            title="x", system_prompt="Be extremely brief.",
        )
        s = self.ws.get_session(sid)
        self.assertEqual(s.system_prompt, "Be extremely brief.")


class TurnOrchestration(_Base):
    def test_turn_persists_both_user_and_assistant(self):
        from core.claude_tier import TierReply

        sid = self.ws.create_session(title="t1")
        fake = TierReply(
            reply="hi from assistant",
            model_used="claude-sonnet-4-6",
            input_tokens=30, output_tokens=15, raw={},
        )
        with mock.patch("core.claude_tier.call", return_value=fake):
            result = self.ws.turn(
                session_id=sid, user_message="hello assistant",
            )
        self.assertEqual(result["assistant"], "hi from assistant")
        self.assertEqual(result["output_tokens"], 15)
        turns = self.ws.get_turns(sid)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].role, "user")
        self.assertEqual(turns[0].content, "hello assistant")
        self.assertEqual(turns[1].role, "assistant")
        self.assertEqual(turns[1].content, "hi from assistant")
        self.assertEqual(turns[1].input_tokens, 30)
        self.assertEqual(turns[1].output_tokens, 15)

    def test_turn_with_history_sends_context(self):
        """Subsequent turns should include prior messages in the
        composed prompt passed to claude_tier."""
        from core.claude_tier import TierReply

        sid = self.ws.create_session(title="t2")
        self.ws._persist_turn(sid, "user", "first question")
        self.ws._persist_turn(sid, "assistant", "first answer")

        fake = TierReply(
            reply="second answer",
            model_used="sonnet", input_tokens=50, output_tokens=10, raw={},
        )
        with mock.patch("core.claude_tier.call",
                         return_value=fake) as m_call:
            self.ws.turn(session_id=sid, user_message="second question")

        sent_prompt = m_call.call_args.kwargs["prompt"]
        # History should be embedded
        self.assertIn("first question", sent_prompt)
        self.assertIn("first answer", sent_prompt)
        # Current message should be marked as current
        self.assertIn("second question", sent_prompt)
        # Caller label propagated
        self.assertTrue(
            m_call.call_args.kwargs["caller"].startswith("workshop/"),
        )

    def test_turn_without_session_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            self.ws.turn(session_id="nonexistent", user_message="x")
        self.assertIn("no session", str(cm.exception))

    def test_empty_message_raises(self):
        sid = self.ws.create_session(title="x")
        with self.assertRaises(RuntimeError):
            self.ws.turn(session_id=sid, user_message="")
        with self.assertRaises(RuntimeError):
            self.ws.turn(session_id=sid, user_message="   ")

    def test_tier_error_propagates_after_user_persisted(self):
        """If the tier call fails, the user turn must already be
        persisted (so the UI can show it and retry) but no
        assistant turn should be recorded."""
        from core.claude_tier import ClaudeTierUnavailable

        sid = self.ws.create_session(title="t3")
        with mock.patch("core.claude_tier.call",
                         side_effect=ClaudeTierUnavailable("down")):
            with self.assertRaises(RuntimeError):
                self.ws.turn(session_id=sid, user_message="hi")
        turns = self.ws.get_turns(sid)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].role, "user")

    def test_override_model_per_turn(self):
        from core.claude_tier import TierReply

        sid = self.ws.create_session(title="t4", model="sonnet")
        fake = TierReply(
            reply="ok", model_used="gpt-4o-mini",
            input_tokens=1, output_tokens=1, raw={},
        )
        with mock.patch("core.claude_tier.call",
                         return_value=fake) as m_call:
            self.ws.turn(
                session_id=sid, user_message="hi",
                override_model="openai/gpt-4o-mini",
            )
        self.assertEqual(
            m_call.call_args.kwargs["model"], "openai/gpt-4o-mini",
        )
        # Session's default model unchanged
        s = self.ws.get_session(sid)
        self.assertEqual(s.model, "sonnet")


class Rollup(_Base):
    def test_rollup_includes_turn_count(self):
        from core.claude_tier import TierReply

        sid = self.ws.create_session(title="only one")
        self.ws._persist_turn(sid, "user", "q")
        self.ws._persist_turn(sid, "assistant", "a")

        data = self.ws.rollup()
        self.assertEqual(len(data["sessions"]), 1)
        self.assertEqual(data["sessions"][0]["turn_count"], 2)

    def test_rollup_empty(self):
        data = self.ws.rollup()
        self.assertEqual(data["sessions"], [])


if __name__ == "__main__":
    unittest.main()
