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

    def test_update_model_changes_session_default(self):
        sid = self.ws.create_session(title="model test", model="sonnet")
        self.assertEqual(self.ws.get_session(sid).model, "sonnet")
        ok = self.ws.update_session_model(sid, "opus")
        self.assertTrue(ok)
        self.assertEqual(self.ws.get_session(sid).model, "opus")

    def test_update_model_rejects_empty(self):
        sid = self.ws.create_session(title="x", model="sonnet")
        self.assertFalse(self.ws.update_session_model(sid, ""))
        self.assertFalse(self.ws.update_session_model(sid, "   "))
        # Model unchanged
        self.assertEqual(self.ws.get_session(sid).model, "sonnet")

    def test_update_model_nonexistent_session_returns_false(self):
        self.assertFalse(
            self.ws.update_session_model("does-not-exist", "opus"),
        )

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


class MentionExpansion(_Base):
    """@path mentions in user_message get resolved to file contents."""

    def _mock_repo(self, files: dict[str, str]):
        """Create a temp 'repo' with the given files. Patch the
        workshop module's _REPO_ROOT to point at it."""
        import tempfile
        self._repo_tmp = tempfile.TemporaryDirectory()
        root = Path(self._repo_tmp.name)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        self._root_patch = mock.patch.object(
            self.ws, "_REPO_ROOT", root,
        )
        self._root_patch.start()
        return root

    def tearDown(self):
        if hasattr(self, "_root_patch"):
            self._root_patch.stop()
        if hasattr(self, "_repo_tmp"):
            self._repo_tmp.cleanup()
        super().tearDown()

    def test_simple_mention_resolves_and_appends(self):
        self._mock_repo({"core/foo.py": "def hello():\n    return 1\n"})
        expanded, notes = self.ws.expand_mentions(
            "review @core/foo.py for leaks",
        )
        self.assertIn("[ATTACHED FILES]", expanded)
        self.assertIn("def hello()", expanded)
        self.assertIn("```python", expanded)
        # Original @mention preserved in the prose part
        self.assertIn("@core/foo.py", expanded)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["status"], "attached")

    def test_no_mentions_passes_through_unchanged(self):
        self._mock_repo({})
        expanded, notes = self.ws.expand_mentions(
            "what's the weather like today?",
        )
        self.assertEqual(expanded, "what's the weather like today?")
        self.assertEqual(notes, [])

    def test_unresolved_path_reported_but_prose_intact(self):
        self._mock_repo({"core/exists.py": "x"})
        expanded, notes = self.ws.expand_mentions(
            "look at @core/doesnt_exist.py",
        )
        # Prose preserved, no attachment block since nothing resolved
        self.assertEqual(
            expanded, "look at @core/doesnt_exist.py",
        )
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["status"], "unresolved")

    def test_absolute_paths_not_recognized_as_mentions(self):
        """@/etc/shadow does not match the mention regex at all —
        the regex requires a leading path-segment token. Prose passes
        through unchanged and no notes are produced. This is the
        first line of defense against filesystem escape."""
        self._mock_repo({"x.py": "ok"})
        expanded, notes = self.ws.expand_mentions(
            "show me @/etc/passwd contents",
        )
        self.assertNotIn("[ATTACHED FILES]", expanded)
        self.assertEqual(notes, [])

    def test_relative_escape_attempt_is_refused_at_resolution(self):
        """@../../something DOES parse as a mention (regex allows dots)
        but _resolve_path_safely refuses it because the resolved path
        falls outside _REPO_ROOT. This is the second line of defense."""
        self._mock_repo({"x.py": "ok"})
        expanded, notes = self.ws.expand_mentions(
            "please look at @../../../etc/hosts now",
        )
        # No attachment block because resolution failed
        self.assertNotIn("[ATTACHED FILES]", expanded)
        # And notes record the unresolved status
        self.assertTrue(
            any(n["status"] == "unresolved" for n in notes),
            f"expected unresolved status, got notes={notes}",
        )

    def test_duplicate_mention_deduped(self):
        self._mock_repo({"core/foo.py": "x = 1\n"})
        expanded, notes = self.ws.expand_mentions(
            "first look at @core/foo.py then look at @core/foo.py again",
        )
        # Only one attachment block, not two
        self.assertEqual(expanded.count("--- core/foo.py ---"), 1)
        self.assertEqual(len(notes), 1)

    def test_large_file_truncated_with_note(self):
        big = "line\n" * 20000  # ~100k chars
        self._mock_repo({"big.py": big})
        # Override the cap to a tiny value so we don't need a real big file
        with mock.patch.object(self.ws, "_MENTION_MAX_BYTES", 500):
            expanded, notes = self.ws.expand_mentions("look at @big.py")
        # The fenced content must be ≤ cap (roughly)
        self.assertIn("[ATTACHED FILES]", expanded)
        self.assertEqual(notes[0]["status"], "attached_truncated")

    def test_mention_regex_doesnt_catch_email(self):
        self._mock_repo({"core/foo.py": "x"})
        # @user in an email or handle shouldn't trigger resolution
        expanded, notes = self.ws.expand_mentions(
            "ping me at rohit@example.com or ask @user later",
        )
        # No attachments, no notes
        self.assertEqual(notes, [])
        self.assertNotIn("[ATTACHED FILES]", expanded)


class ApplyDiff(_Base):
    """apply_diff() parses a unified diff, backs up the target, and
    applies via `patch`. These tests exercise the path-safety guard
    and error handling paths without requiring a real `patch` install
    for every code path — the happy-path test is gated on patch
    being available on PATH (most Linux systems)."""

    def _mock_repo(self, files: dict[str, str]):
        import tempfile
        self._repo_tmp = tempfile.TemporaryDirectory()
        root = Path(self._repo_tmp.name)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        # Backups go next to repo so cleanup is trivial
        backup_dir = root / "workshop_backups"
        self._root_patch = mock.patch.object(self.ws, "_REPO_ROOT", root)
        self._backup_patch = mock.patch.object(
            self.ws, "_APPLY_BACKUP_DIR", backup_dir,
        )
        self._root_patch.start()
        self._backup_patch.start()
        return root

    def tearDown(self):
        if hasattr(self, "_root_patch"):
            self._root_patch.stop()
        if hasattr(self, "_backup_patch"):
            self._backup_patch.stop()
        if hasattr(self, "_repo_tmp"):
            self._repo_tmp.cleanup()
        super().tearDown()

    def test_target_extraction_from_plus_header(self):
        d = (
            "--- foo/bar.py\n"
            "+++ foo/bar.py\n"
            "@@ -1 +1 @@\n"
            "-x\n+y\n"
        )
        path, had_prefix = self.ws._extract_target_path(d)
        self.assertEqual(path, "foo/bar.py")
        self.assertFalse(had_prefix)

    def test_target_extraction_strips_git_prefix(self):
        d = (
            "--- a/foo/bar.py\n"
            "+++ b/foo/bar.py\n"
            "@@ -1 +1 @@\n"
            "-x\n+y\n"
        )
        path, had_prefix = self.ws._extract_target_path(d)
        self.assertEqual(path, "foo/bar.py")
        self.assertTrue(had_prefix)

    def test_target_extraction_refuses_dev_null(self):
        d = "--- foo/bar.py\n+++ /dev/null\n"
        path, _ = self.ws._extract_target_path(d)
        self.assertIsNone(path)

    def test_missing_session_fails(self):
        self._mock_repo({"x.py": "a\n"})
        result = self.ws.apply_diff(
            session_id="bogus", diff_text="+++ x.py\n",
        )
        self.assertFalse(result["applied"])
        self.assertIn("no session", result["error"])

    def test_no_target_fails_cleanly(self):
        self._mock_repo({})
        sid = self.ws.create_session(title="t")
        result = self.ws.apply_diff(
            session_id=sid, diff_text="not a real diff",
        )
        self.assertFalse(result["applied"])
        self.assertIn("target path", result["error"].lower())

    def test_escape_target_is_refused(self):
        self._mock_repo({"x.py": "a\n"})
        sid = self.ws.create_session(title="t")
        result = self.ws.apply_diff(
            session_id=sid,
            diff_text="--- a/../../../etc/hosts\n+++ b/../../../etc/hosts\n",
        )
        self.assertFalse(result["applied"])
        self.assertIn("not a file under the repo", result["error"])

    def test_git_prefix_diff_uses_p1_strip(self):
        """self-dev review on 07ab21b (concern #1): git-format diffs
        with 'a/' 'b/' prefixes must be applied with patch -p1, not
        -p0. This test verifies a git-style diff applies cleanly."""
        import shutil
        if not shutil.which("patch"):
            self.skipTest("patch binary not available")
        root = self._mock_repo({"foo.py": "a\nb\nc\n"})
        sid = self.ws.create_session(title="git-prefix test")
        diff = (
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,3 @@\n"
            " a\n"
            "-b\n"
            "+B\n"
            " c\n"
        )
        result = self.ws.apply_diff(session_id=sid, diff_text=diff)
        self.assertTrue(result["applied"],
                         f"git-style diff should apply with -p1; got {result}")
        self.assertEqual((root / "foo.py").read_text(), "a\nB\nc\n")

    def test_apply_logs_as_assistant_not_system(self):
        """self-dev review on 07ab21b (concern #4): the apply event
        must be persisted as role='assistant' (with a bracketed
        marker) so future turn() calls see it — system-role turns
        are filtered out of the history rebuild."""
        import shutil
        if not shutil.which("patch"):
            self.skipTest("patch binary not available")
        self._mock_repo({"foo.py": "a\nb\nc\n"})
        sid = self.ws.create_session(title="visibility test")
        diff = (
            "--- foo.py\n"
            "+++ foo.py\n"
            "@@ -1,3 +1,3 @@\n"
            " a\n"
            "-b\n"
            "+B\n"
            " c\n"
        )
        self.ws.apply_diff(session_id=sid, diff_text=diff)
        turns = self.ws.get_turns(sid)
        apply_turns = [t for t in turns if "Workshop applied" in t.content]
        self.assertEqual(len(apply_turns), 1)
        self.assertEqual(apply_turns[0].role, "assistant")

    def test_happy_path_applies_when_patch_available(self):
        import shutil
        if not shutil.which("patch"):
            self.skipTest("patch binary not available")
        root = self._mock_repo({"foo.py": "a\nb\nc\n"})
        sid = self.ws.create_session(title="t")
        # diff that changes line 2 from 'b' → 'B'
        diff = (
            "--- foo.py\n"
            "+++ foo.py\n"
            "@@ -1,3 +1,3 @@\n"
            " a\n"
            "-b\n"
            "+B\n"
            " c\n"
        )
        result = self.ws.apply_diff(session_id=sid, diff_text=diff)
        self.assertTrue(result["applied"],
                         f"expected applied=True; got {result}")
        self.assertEqual(result["target"], "foo.py")
        self.assertTrue(result["backup"])
        # File should now have the change
        self.assertEqual((root / "foo.py").read_text(), "a\nB\nc\n")
        # Backup should have the original
        self.assertEqual(Path(result["backup"]).read_text(),
                          "a\nb\nc\n")
        # A system-role turn should have been recorded
        turns = self.ws.get_turns(sid)
        self.assertTrue(
            any("applied diff" in t.content for t in turns),
            "expected the apply to log a system turn",
        )


class GetTurnsTail(_Base):
    """self-dev review on 07ab21b (concern #3): get_turns's old
    `limit` kwarg returned the OLDEST N, not newest. Renamed to
    `tail` with correct semantics."""

    def test_tail_returns_most_recent_still_oldest_first(self):
        sid = self.ws.create_session(title="tail test")
        for i in range(10):
            self.ws._persist_turn(sid, "user", f"msg-{i}")
        tail_3 = self.ws.get_turns(sid, tail=3)
        self.assertEqual(len(tail_3), 3)
        # Tail = most recent 3; internal order = oldest-first
        self.assertEqual(tail_3[0].content, "msg-7")
        self.assertEqual(tail_3[1].content, "msg-8")
        self.assertEqual(tail_3[2].content, "msg-9")

    def test_no_tail_returns_everything_oldest_first(self):
        sid = self.ws.create_session(title="full test")
        for i in range(5):
            self.ws._persist_turn(sid, "user", f"msg-{i}")
        all_turns = self.ws.get_turns(sid)
        self.assertEqual(len(all_turns), 5)
        self.assertEqual(all_turns[0].content, "msg-0")
        self.assertEqual(all_turns[-1].content, "msg-4")


class Rollup(_Base):
    def test_rollup_includes_turn_count(self):

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
