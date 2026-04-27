# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""UI /message history threading test (2026-04-27 incident).

Sunday 21:36-21:42 UI session: owner sent "Hi" mid-conversation
(after 4 active turns) and got a fresh greeting back. Root cause:
the cockpit POSTs to ``http://127.0.0.1:11435/message`` with only
``{text, source}``; the daemon's ``/message`` route called
``handle_message(text, source="UI")`` without a chat_history kwarg.
Every UI turn synthesised from scratch.

The 2026-04-24 anaphora fix added ``chat_history`` threading to
``handle_message``, but the UI path was never wired through. This
test locks the helper that bridges the two formats:
``[{role, content}, ...]`` (cockpit shape) →
``[{content: "<display>: <msg>\\nMaez: <reply>"}, ...]``
(``handle_message`` shape).

Tests:
- Empty / non-list inputs return [] without raising.
- Adjacent (user, assistant) pairs convert correctly.
- Unpaired trailing user (the current live turn) is dropped.
- Malformed entries are skipped, not propagated.
- Owner display name is sourced from identity, not hardcoded.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class PairsAdjacentUserAssistantTurns(unittest.TestCase):
    def test_basic_pair(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "user", "content": "Hey maez"},
                {
                    "role": "assistant",
                    "content": "Hey Rohit. What's on your mind?",
                },
            ]
        )
        self.assertEqual(len(out), 1)
        # The cleaned-exchange shape that conversation_history parses.
        content = out[0]["content"]
        self.assertIn(": Hey maez", content)
        self.assertIn("\nMaez: Hey Rohit. What's on your mind?", content)

    def test_multiple_pairs(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
            ]
        )
        self.assertEqual(len(out), 2)
        self.assertIn(": u1\nMaez: a1", out[0]["content"])
        self.assertIn(": u2\nMaez: a2", out[1]["content"])


class TrailingUnpairedUserDropped(unittest.TestCase):
    """The current live turn is at the tail of the cockpit's history
    when the request fires; it must NOT be threaded as history (would
    duplicate the live message in the prompt)."""

    def test_trailing_user_without_assistant_dropped(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "the live turn"},
            ]
        )
        self.assertEqual(len(out), 1)
        self.assertNotIn("the live turn", out[0]["content"])


class MalformedInputsHandledGracefully(unittest.TestCase):
    """The /message endpoint must not 500 on a malformed history."""

    def test_empty_list_returns_empty(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        self.assertEqual(_pair_history_for_chat_threading([]), [])

    def test_none_returns_empty(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        self.assertEqual(_pair_history_for_chat_threading(None), [])

    def test_non_list_returns_empty(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        self.assertEqual(_pair_history_for_chat_threading("not a list"), [])
        self.assertEqual(_pair_history_for_chat_threading({"a": 1}), [])

    def test_missing_role_or_content_skipped(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "user"},  # missing content
                {"role": "assistant", "content": "a1"},
                {"content": "u2"},  # missing role
                {"role": "assistant", "content": "a2"},
                # Survivors: a single valid pair below.
                {"role": "user", "content": "real-u"},
                {"role": "assistant", "content": "real-a"},
            ]
        )
        # Only the survivor pair should make it through.
        self.assertEqual(len(out), 1)
        self.assertIn("real-u", out[0]["content"])
        self.assertIn("real-a", out[0]["content"])

    def test_empty_strings_skipped(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": ""},
                {"role": "user", "content": "real-u"},
                {"role": "assistant", "content": "real-a"},
            ]
        )
        # Both empty-content pairs filtered (dict items pass the
        # outer truthy check but the inner pair-build skips empties).
        self.assertEqual(len(out), 1)
        self.assertIn("real-u", out[0]["content"])

    def test_assistant_first_skipped_until_user(self):
        from daemon.maez_daemon import _pair_history_for_chat_threading

        out = _pair_history_for_chat_threading(
            [
                {"role": "assistant", "content": "stray a"},
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
            ]
        )
        # The leading assistant is consumed by the loop's i+=1
        # branch; only the (u1, a1) pair survives.
        self.assertEqual(len(out), 1)
        self.assertIn("u1", out[0]["content"])


class DisplayNameNotHardcoded(unittest.TestCase):
    """Owner prefix in the cleaned-exchange shape must come from
    identity.display_name(), not a literal 'Rohit'. Fallback to
    'Rohit' is acceptable when identity is unavailable, but a
    successful identity lookup must take precedence."""

    def test_uses_display_name_from_identity(self):
        from unittest import mock

        from daemon.maez_daemon import _pair_history_for_chat_threading

        with mock.patch("core.identity.display_name", return_value="Alex"):
            out = _pair_history_for_chat_threading(
                [
                    {"role": "user", "content": "u1"},
                    {"role": "assistant", "content": "a1"},
                ]
            )
        self.assertEqual(len(out), 1)
        self.assertIn("Alex: u1", out[0]["content"])
        self.assertNotIn("Rohit:", out[0]["content"])


if __name__ == "__main__":
    unittest.main()
