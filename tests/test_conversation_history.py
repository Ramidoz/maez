# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Conversation-history threading — 2026-04-24 gap closure.

Regression test for the named incident: on 2026-04-24 04:42 Maez
answered an owner question about `stanford-iris-lab/meta-harness`
(grounded via web_search). At 04:53 the owner's follow-up "You think
it'll be useful for you?" lost the "it" referent — Maez replied "I
don't know what 'it' refers to" because synthesis only saw
`[system, user]` messages without prior-turn context.

`core.brain.conversation_history.history_to_messages` parses the
adapter's cleaned exchange format and emits user/assistant message
pairs. `daemon.handle_message` threads those pairs between the
system prompt and the current user turn so anaphoric references can
bind. These tests lock the contract in."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class HistoryToMessages(unittest.TestCase):
    def _convert(self, history):
        from core.brain.conversation_history import history_to_messages
        return history_to_messages(history)

    def test_empty_history_returns_empty(self):
        self.assertEqual(self._convert(None), [])
        self.assertEqual(self._convert([]), [])

    def test_single_cleaned_exchange_splits_into_pair(self):
        entry = {
            "content": "Rohit: what is meta-harness?\n"
                       "Maez: a framework from Stanford IRIS Lab.",
        }
        out = self._convert([entry])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], {
            "role": "user",
            "content": "what is meta-harness?",
        })
        self.assertEqual(out[1], {
            "role": "assistant",
            "content": "a framework from Stanford IRIS Lab.",
        })

    def test_multiple_exchanges_in_order(self):
        entries = [
            {"content": "Rohit: hi\nMaez: hello"},
            {"content": "Rohit: ok?\nMaez: yes"},
        ]
        out = self._convert(entries)
        self.assertEqual(len(out), 4)
        self.assertEqual(out[0]["content"], "hi")
        self.assertEqual(out[1]["content"], "hello")
        self.assertEqual(out[2]["content"], "ok?")
        self.assertEqual(out[3]["content"], "yes")

    def test_legacy_envelope_entries_rejected(self):
        # Pre-2026-04-23 storage form — has envelope text, no
        # "Rohit:" prefix after cleaning. Must not leak into messages.
        entries = [
            {"content": "the owner (telegram_surface): stuff\n[TURN STATE...]\nMaez: whatever"},
            {"content": "some other opaque stored blob"},
        ]
        self.assertEqual(self._convert(entries), [])

    def test_empty_user_or_assistant_rejected(self):
        entries = [
            {"content": "Rohit: \nMaez: hello"},        # empty user
            {"content": "Rohit: question\nMaez: "},     # empty assistant
            {"content": "Rohit: \nMaez: "},             # both empty
        ]
        self.assertEqual(self._convert(entries), [])

    def test_missing_maez_marker_rejected(self):
        entries = [
            {"content": "Rohit: something without the reply marker"},
        ]
        self.assertEqual(self._convert(entries), [])

    def test_non_dict_entries_skipped(self):
        entries = [
            None,
            "a string, not a dict",
            42,
            {"content": "Rohit: q\nMaez: a"},
        ]
        out = self._convert(entries)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["content"], "q")

    def test_multiline_assistant_reply_preserved(self):
        # Maez often replies across multiple lines. The split must
        # only fire on the "Rohit:" prefix and first "\nMaez:" marker;
        # everything after is the full reply.
        entry = {
            "content": (
                "Rohit: what is meta-harness?\n"
                "Maez: It's a framework from Stanford IRIS Lab.\n\n"
                "It's relevant because it formalizes harness tuning."
            ),
        }
        out = self._convert([entry])
        self.assertEqual(len(out), 2)
        self.assertIn("formalizes harness tuning", out[1]["content"])

    def test_anaphora_incident_shape(self):
        # The actual 2026-04-24 incident shape — this is the pair that
        # SHOULD thread through so "you think it'll be useful?" can
        # resolve "it" back to meta-harness.
        history = [{
            "content": (
                "Rohit: Check about meta harness on GitHub\n"
                "Maez: It's a framework from Stanford IRIS Lab "
                "(stanford-iris-lab/meta-harness) for automatically "
                "optimizing the 'harness' around a fixed model."
            ),
        }]
        out = self._convert(history)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["role"], "user")
        self.assertIn("meta harness", out[0]["content"].lower())
        self.assertEqual(out[1]["role"], "assistant")
        self.assertIn("stanford-iris-lab/meta-harness", out[1]["content"])


if __name__ == "__main__":
    unittest.main()
