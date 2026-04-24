# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Cleaned-exchange parsing across all three surfaces — 2026-04-24 F4.

The `skills.surface.maez_adapter._clean_exchange` cleaner turns raw
`store_telegram` entries into the `"<name>: <user>\\nMaez: <reply>"`
shape the downstream `core.brain.conversation_history` parser
expects. Before F4 it only handled the daemon-surface form
(`"the owner (<surface>):"`). Web and telegram_voice surfaces
stored their exchanges in a different shape
(`"the owner asked: X\\nMaez replied: Y"`) — and the cleaner passed
those through unchanged. The downstream parser's prefix-agnostic
split *nearly* worked on them, but pulled in the "replied:" marker
as part of the reply body.

Net effect: web + voice follow-ups silently lost continuity
threading. The failure mode is identical to the Telegram 04:53
meta-harness incident that commit cc462c5 closed — but for the
surfaces cc462c5 didn't cover.

These tests lock the fix in:
  1. Daemon form still cleans (regression guard on the existing path).
  2. Web/voice `"the owner asked: X\\nMaez replied: Y"` form now
     cleans to the same shape as the daemon form.
  3. Operational-notes formats (card state summaries, recovery
     markers, random test fixtures) still pass through unchanged.
  4. The end-to-end path: stored → cleaned → history_to_messages
     returns user/assistant pairs for both forms."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class DaemonFormStillCleans(unittest.TestCase):
    """Regression guard: the original daemon-surface path stays green."""

    def _clean(self, doc):
        from skills.surface.maez_adapter import _clean_exchange
        return _clean_exchange(doc)

    def test_simple_daemon_form(self):
        out = self._clean(
            "the owner (telegram_surface): hi there\nMaez: hello back"
        )
        self.assertIn(": hi there\nMaez: hello back", out)

    def test_daemon_form_with_envelope_body(self):
        # The real stored shape — envelope text between user and reply.
        # Cleaner must strip the envelope.
        stored = (
            "the owner (telegram_surface): Check the build\n"
            "\n[JARVIS TRANSCRIPT — AUTHORITATIVE record...]\n"
            "  ✓ run_shell({\"cmd\": \"pytest\"})\n"
            "    → all passing\n"
            "\nMaez: Build's green."
        )
        out = self._clean(stored)
        # User message and reply both present, envelope gone.
        self.assertIn("Check the build", out)
        self.assertIn("Build's green.", out)
        self.assertNotIn("JARVIS TRANSCRIPT", out)
        # Output is exactly one user-line + "Maez: reply".
        lines = out.split("\n")
        self.assertEqual(len(lines), 2)


class WebVoiceFormCleans(unittest.TestCase):
    """F4 — web and telegram_voice `"the owner asked: X\\nMaez replied: Y"`
    form now cleans to the same shape as the daemon form."""

    def _clean(self, doc):
        from skills.surface.maez_adapter import _clean_exchange
        return _clean_exchange(doc)

    def test_simple_asked_form(self):
        out = self._clean(
            "the owner asked: what is meta-harness?\n"
            "Maez replied: a framework from Stanford IRIS Lab."
        )
        # Expected cleaned shape (owner prefix is display_name —
        # "Rohit" on this install via identity.yaml).
        self.assertIn(": what is meta-harness?", out)
        self.assertIn("Maez: a framework from Stanford IRIS Lab.", out)
        # Critical: "replied:" must NOT leak into the reply body.
        self.assertNotIn("Maez replied:", out)
        self.assertFalse(
            out.endswith("replied: a framework from Stanford IRIS Lab."),
            "cleaner left 'replied:' prefix on the assistant message",
        )

    def test_asked_form_with_multiline_reply(self):
        out = self._clean(
            "the owner asked: tell me about X\n"
            "Maez replied: First paragraph.\n\nSecond paragraph."
        )
        self.assertIn("tell me about X", out)
        self.assertIn("First paragraph.", out)
        self.assertIn("Second paragraph.", out)

    def test_empty_asked_user_passes_through(self):
        # Degenerate input — the cleaner returns the raw doc so the
        # downstream parser gets a chance to reject.
        doc = "the owner asked: \nMaez replied: "
        out = self._clean(doc)
        self.assertEqual(out, doc)


class OperationalFormsPassThrough(unittest.TestCase):
    """Card-state summaries, recovery notes, and other non-Q/A
    storage formats must pass through unchanged. The downstream
    parser rejects them — correct behavior, they aren't
    conversational turns."""

    def _clean(self, doc):
        from skills.surface.maez_adapter import _clean_exchange
        return _clean_exchange(doc)

    def test_card_state_summary_unchanged(self):
        # telegram_voice.py:822-828 shape
        doc = (
            "the owner said: 'approve'\n"
            "Card abc123 (run_shell): apt install htop\n"
            "New status: approved. (...)"
        )
        self.assertEqual(self._clean(doc), doc)

    def test_recovery_marker_unchanged(self):
        # telegram_voice.py:1078 shape
        doc = "Maez recovery pass 2: retried the install with sudo..."
        self.assertEqual(self._clean(doc), doc)

    def test_random_text_unchanged(self):
        doc = "some completely unstructured note"
        self.assertEqual(self._clean(doc), doc)


class EndToEndThreading(unittest.TestCase):
    """stored → cleaned → history_to_messages pipeline works for both
    daemon and web/voice forms."""

    def _thread(self, stored_entries):
        from skills.surface.maez_adapter import _clean_exchange
        from core.brain.conversation_history import history_to_messages
        cleaned = []
        for entry in stored_entries:
            c = _clean_exchange(entry.get("content", ""))
            if c:
                cleaned.append({"content": c})
        return history_to_messages(cleaned)

    def test_daemon_entries_thread(self):
        entries = [
            {"content": "the owner (telegram_surface): hi\nMaez: hey"},
        ]
        msgs = self._thread(entries)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["content"], "hi")
        self.assertEqual(msgs[1]["content"], "hey")

    def test_web_entries_thread(self):
        entries = [
            {"content": "the owner asked: q from web\nMaez replied: a from web"},
        ]
        msgs = self._thread(entries)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["content"], "q from web")
        self.assertEqual(msgs[1]["content"], "a from web")

    def test_mixed_surfaces_thread_in_order(self):
        entries = [
            {"content": "the owner (telegram_surface): tg q\nMaez: tg a"},
            {"content": "the owner asked: web q\nMaez replied: web a"},
            {"content": "the owner (voice): voice q\nMaez: voice a"},
        ]
        msgs = self._thread(entries)
        self.assertEqual(len(msgs), 6)
        self.assertEqual(msgs[0]["content"], "tg q")
        self.assertEqual(msgs[1]["content"], "tg a")
        self.assertEqual(msgs[2]["content"], "web q")
        self.assertEqual(msgs[3]["content"], "web a")
        self.assertEqual(msgs[4]["content"], "voice q")
        self.assertEqual(msgs[5]["content"], "voice a")

    def test_operational_entries_dropped_from_thread(self):
        # Card-state and recovery entries are stored in the same
        # memory collection but MUST NOT appear in messages[] —
        # they're not conversational turns.
        entries = [
            {"content": "the owner (telegram_surface): real q\nMaez: real a"},
            {"content": "Maez recovery pass 2: operational note"},
            {"content": "the owner said: 'approve'\nCard abc: ..."},
        ]
        msgs = self._thread(entries)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["content"], "real q")
        self.assertEqual(msgs[1]["content"], "real a")


if __name__ == "__main__":
    unittest.main()
