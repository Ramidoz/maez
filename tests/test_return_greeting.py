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
        long_q = "a" * 500
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
