# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Presence-return greeting composer — 2026-04-24 voice fix.

The daemon's presence-detection loop used to send two hardcoded
strings verbatim:

    "Welcome back the owner."
    "Welcome back the owner — you've been away for ... Here's what
     I've been thinking about: <random raw memory entry>"

Both carried the role label "the owner" into surface text (the owner
has a name in identity config; it wasn't being used), and the >2hr
path pulled an arbitrary raw-memory entry as a "thought" hook — which
at best was a cycle's internal monologue, never the pending
conversation thread.

`compose_return_greeting` is the testable pure-function replacement
that resolves the name from `display_name()` (no hardcoding) and, if
the last telegram exchange is present and fresh enough, surfaces the
owner's literal last question as a continuity pointer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class ShortAbsenceSuppressed(unittest.TestCase):
    def test_under_20_minutes_returns_empty(self):
        from core.brain.return_greeting import compose_return_greeting
        self.assertEqual(
            compose_return_greeting(
                display_name="Rohit",
                absence_secs=300,
            ),
            "",
        )
        self.assertEqual(
            compose_return_greeting(
                display_name="Rohit",
                absence_secs=1199,
            ),
            "",
        )


class NameIsNotHardcoded(unittest.TestCase):
    def _compose(self, name: str, secs: int):
        from core.brain.return_greeting import compose_return_greeting
        return compose_return_greeting(
            display_name=name,
            absence_secs=secs,
        )

    def test_simple_path_uses_configured_name(self):
        # Name from identity.display_name() flows through verbatim.
        self.assertEqual(
            self._compose("Rohit", 3600),
            "Welcome back, Rohit.",
        )
        self.assertEqual(
            self._compose("Alex", 3600),
            "Welcome back, Alex.",
        )
        self.assertEqual(
            self._compose("Friend", 3600),
            "Welcome back, Friend.",
        )

    def test_empty_name_falls_back_to_friend(self):
        self.assertEqual(
            self._compose("", 3600),
            "Welcome back, Friend.",
        )
        self.assertEqual(
            self._compose("   ", 3600),
            "Welcome back, Friend.",
        )

    def test_literal_role_label_never_appears(self):
        # "the owner" must never leak into any output.
        for name in ("Rohit", "Friend", "Alex", ""):
            for secs in (1800, 3600, 7200, 36000):
                msg = self._compose(name, secs)
                self.assertNotIn("the owner", msg.lower())

    def test_detailed_path_uses_configured_name(self):
        out = self._compose("Rohit", 10800)
        self.assertTrue(out.startswith("Welcome back, Rohit"))
        self.assertIn("3h 0m", out)


class ThreadContinuitySuffix(unittest.TestCase):
    def _compose(self, **kw):
        from core.brain.return_greeting import compose_return_greeting
        kw.setdefault("display_name", "Rohit")
        return compose_return_greeting(**kw)

    def test_incident_shape_simple_path(self):
        # Reproduces the 2026-04-24 incident: owner came back after
        # 67 minutes on an open meta-harness thread. Old greeting was
        # "Welcome back the owner." — zero continuity. New greeting
        # must reference the pending question.
        msg = self._compose(
            absence_secs=67 * 60,
            last_exchange={
                "content": (
                    "Rohit: You think it'll be useful for you? "
                    "How will it make you better in layman's terms\n"
                    "Maez: I don't know what 'it' refers to..."
                ),
            },
            last_exchange_age_secs=67 * 60,
        )
        self.assertIn("Rohit", msg)
        self.assertIn("You think it'll be useful", msg)

    def test_stale_exchange_suppresses_suffix(self):
        # >24h old: do not reopen a cold thread as if it were warm.
        msg = self._compose(
            absence_secs=3600,
            last_exchange={"content": "Rohit: something\nMaez: reply"},
            last_exchange_age_secs=86400 + 600,
        )
        self.assertEqual(msg, "Welcome back, Rohit.")

    def test_no_exchange_means_plain_greeting(self):
        msg = self._compose(absence_secs=3600, last_exchange=None)
        self.assertEqual(msg, "Welcome back, Rohit.")

    def test_long_question_truncated(self):
        # Long question (must read as a question after the 2026-04-25
        # gating fix — bare "aaaa..." would now suppress the suffix
        # entirely instead of being treated as text to truncate).
        long_q = "What about " + ("a" * 500) + "?"
        msg = self._compose(
            absence_secs=3600,
            last_exchange={"content": f"Rohit: {long_q}\nMaez: ok"},
            last_exchange_age_secs=100,
        )
        self.assertIn("…", msg)
        self.assertLess(len(msg), 300)

    def test_detailed_path_with_thread_ref(self):
        msg = self._compose(
            absence_secs=5 * 3600,
            last_exchange={
                "content": "Rohit: when will you finish?\nMaez: soon",
            },
            last_exchange_age_secs=5 * 3600,
        )
        self.assertIn("5h 0m", msg)
        self.assertIn("when will you finish", msg)


class ClosingStatementSuppressesSuffix(unittest.TestCase):
    """2026-04-25 incident regression: owner closed an overnight
    thread with 'You still don't get it but I guess that's how it's
    supposed to be. You'll understand what I'm talking about later.'
    Maez acknowledged ('Fair enough. I'll keep running.'). The
    welcome-back greeting at 11:16 the next morning pulled the
    closing remark back as 'Last we talked you asked: ...' — which
    misframed a settled thread as a pending question. Fix: only
    surface the suffix when the owner's last message looks like an
    actual open question or request."""

    def _compose(self, **kw):
        from core.brain.return_greeting import compose_return_greeting
        kw.setdefault("display_name", "Rohit")
        return compose_return_greeting(**kw)

    def test_incident_shape_no_suffix_for_closing_remark(self):
        msg = self._compose(
            absence_secs=10 * 3600,
            last_exchange={
                "content": (
                    "Rohit: You still don't get it but I guess that's how "
                    "it's supposed to be. You'll understand what I'm "
                    "talking about later.\n"
                    "Maez: Fair enough. I'm listening. I'll keep running."
                ),
            },
            last_exchange_age_secs=10 * 3600,
        )
        # Detailed-path absence still works.
        self.assertIn("Welcome back, Rohit", msg)
        self.assertIn("away for", msg)
        # But the suffix is suppressed.
        self.assertNotIn("you asked", msg.lower())
        self.assertNotIn("you still don't get it", msg.lower())
        # No quoted-message segment — base greeting has apostrophes
        # in "you've" but no `'…'` quoted-message segment.
        self.assertNotIn(": '", msg)

    def test_question_with_question_mark_keeps_suffix(self):
        msg = self._compose(
            absence_secs=2 * 3600,
            last_exchange={
                "content": "Rohit: What did you think of the proposal?\n"
                           "Maez: It looks reasonable.",
            },
            last_exchange_age_secs=2 * 3600,
        )
        self.assertIn("you asked", msg.lower())
        self.assertIn("What did you think of the proposal?", msg)

    def test_question_starting_with_how_keeps_suffix(self):
        msg = self._compose(
            absence_secs=2 * 3600,
            last_exchange={
                "content": "Rohit: How do you handle a stale memory entry\n"
                           "Maez: I tag it integrity=stale.",
            },
            last_exchange_age_secs=2 * 3600,
        )
        self.assertIn("you asked", msg.lower())
        self.assertIn("How do you handle", msg)

    def test_imperative_request_keeps_suffix(self):
        # "Tell me X" is a request, not a closing statement.
        msg = self._compose(
            absence_secs=2 * 3600,
            last_exchange={
                "content": "Rohit: Tell me what you noticed yesterday\n"
                           "Maez: I noticed the disk fixation pattern.",
            },
            last_exchange_age_secs=2 * 3600,
        )
        self.assertIn("you asked", msg.lower())

    def test_short_closing_statement_suppressed(self):
        for closing in (
            "good night",
            "talk to you later",
            "later",
            "we'll see",
            "I'll be back",
            "okay",
        ):
            msg = self._compose(
                absence_secs=2 * 3600,
                last_exchange={
                    "content": f"Rohit: {closing}\nMaez: noted.",
                },
                last_exchange_age_secs=2 * 3600,
            )
            self.assertNotIn(
                "you asked", msg.lower(),
                f"closing remark {closing!r} unexpectedly surfaced as a question",
            )

    def test_bare_period_statement_suppressed(self):
        # Statement, no question mark, no question opener — must suppress.
        msg = self._compose(
            absence_secs=2 * 3600,
            last_exchange={
                "content": "Rohit: I'll figure it out myself.\n"
                           "Maez: noted.",
            },
            last_exchange_age_secs=2 * 3600,
        )
        self.assertNotIn("you asked", msg.lower())


class QuestionDetector(unittest.TestCase):
    def _looks(self, msg: str) -> bool:
        from core.brain.return_greeting import _looks_like_open_question
        return _looks_like_open_question(msg)

    def test_question_mark_detects(self):
        self.assertTrue(self._looks("Are you there?"))
        self.assertTrue(self._looks("really?"))
        self.assertTrue(self._looks("Wait, what?"))

    def test_question_words_detect(self):
        for q in ("How are you", "What do you think", "Why does it",
                  "Can you check", "Should we keep going",
                  "Tell me about it", "Show me the log"):
            self.assertTrue(self._looks(q), q)

    def test_statements_do_not_detect(self):
        for s in (
            "You'll understand later.",
            "I'm going to bed.",
            "Good night.",
            "I'll figure it out myself.",
            "Maez is doing fine.",
            "later",
            "talk soon",
            "see you",
            "okay",
            "thanks",
        ):
            self.assertFalse(self._looks(s), s)

    def test_empty_does_not_detect(self):
        self.assertFalse(self._looks(""))
        self.assertFalse(self._looks("   "))


class ExchangeContentParsing(unittest.TestCase):
    """The content parser must be name-agnostic (Phase 2 de-Rohit-ify
    holds — no hardcoded owner prefix)."""

    def _extract(self, content: str):
        from core.brain.return_greeting import _extract_owner_question
        return _extract_owner_question(content)

    def test_cleaned_form_rohit(self):
        self.assertEqual(
            self._extract("Rohit: what time is it?\nMaez: noon"),
            "what time is it?",
        )

    def test_cleaned_form_alt_name(self):
        self.assertEqual(
            self._extract("Alex: hey\nMaez: hi"),
            "hey",
        )

    def test_cleaned_form_friend_default(self):
        self.assertEqual(
            self._extract("Friend: anything going on?\nMaez: quiet"),
            "anything going on?",
        )

    def test_legacy_envelope_form(self):
        self.assertEqual(
            self._extract(
                "the owner (telegram_surface): check it\n[TURN STATE]\nMaez: ok"
            ),
            "check it",
        )

    def test_empty_content_returns_none(self):
        self.assertIsNone(self._extract(""))
        self.assertIsNone(self._extract("   "))

    def test_malformed_first_line_returns_none(self):
        self.assertIsNone(self._extract("no colon here at all"))


if __name__ == "__main__":
    unittest.main()
