# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Presence-return greeting composer — 2026-04-24 voice fix,
simplified 2026-04-25.

Tests cover the deterministic shape: name + optional absence
duration, no suffix. The "Last we talked you asked: '...'" suffix
was removed after two follow-on incidents (closing remark
re-quoted as pending question; casual "What is good maez?"
re-quoted as a real question on welcome-back). The suffix
duplicated chat_history threading and was net-noise — see
module docstring."""
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
            compose_return_greeting(display_name="Rohit", absence_secs=300),
            "",
        )
        self.assertEqual(
            compose_return_greeting(display_name="Rohit", absence_secs=1199),
            "",
        )


class NameIsNotHardcoded(unittest.TestCase):
    def _compose(self, name: str, secs: int):
        from core.brain.return_greeting import compose_return_greeting
        return compose_return_greeting(display_name=name, absence_secs=secs)

    def test_simple_path_uses_configured_name(self):
        self.assertEqual(self._compose("Rohit", 3600), "Welcome back, Rohit.")
        self.assertEqual(self._compose("Alex", 3600), "Welcome back, Alex.")
        self.assertEqual(self._compose("Friend", 3600), "Welcome back, Friend.")

    def test_empty_name_falls_back_to_friend(self):
        self.assertEqual(self._compose("", 3600), "Welcome back, Friend.")
        self.assertEqual(self._compose("   ", 3600), "Welcome back, Friend.")

    def test_literal_role_label_never_appears(self):
        # "the owner" must never leak into any output.
        for name in ("Rohit", "Friend", "Alex", ""):
            for secs in (1800, 3600, 7200, 36000):
                msg = self._compose(name, secs)
                self.assertNotIn("the owner", msg.lower())


class AbsenceDurationFormatting(unittest.TestCase):
    def _compose(self, secs: int):
        from core.brain.return_greeting import compose_return_greeting
        return compose_return_greeting(display_name="Rohit", absence_secs=secs)

    def test_under_2_hours_no_duration(self):
        msg = self._compose(3600)
        self.assertEqual(msg, "Welcome back, Rohit.")

    def test_just_under_2hr_boundary(self):
        msg = self._compose(7199)
        self.assertEqual(msg, "Welcome back, Rohit.")

    def test_over_2_hours_includes_duration(self):
        msg = self._compose(3 * 3600)
        self.assertIn("3h 0m", msg)
        self.assertTrue(msg.startswith("Welcome back, Rohit"))

    def test_long_absence_with_minutes(self):
        msg = self._compose(9 * 3600 + 58 * 60)
        self.assertIn("9h 58m", msg)


class NoSuffixForAnyShape(unittest.TestCase):
    """The whole class of suffix-related bugs (closed-statement
    re-open, casual-greeting re-quote) is gone. The greeting is
    deterministic: name + duration only. No quote-back can happen
    because the function takes no exchange-history parameter."""

    def test_signature_takes_only_name_and_absence(self):
        import inspect
        from core.brain.return_greeting import compose_return_greeting
        sig = inspect.signature(compose_return_greeting)
        self.assertEqual(
            set(sig.parameters.keys()),
            {"display_name", "absence_secs"},
            "compose_return_greeting must not accept exchange-history "
            "params — that path was the source of repeated voice bugs.",
        )

    def test_output_never_contains_quote_marks(self):
        # No re-quoted message text means no apostrophes around
        # quoted content. Apostrophes inside the prose ("you've")
        # are fine; the assertion is on the quote-pair pattern
        # ": '...'" which only the deleted suffix produced.
        from core.brain.return_greeting import compose_return_greeting
        for secs in (1800, 3600, 7200, 36000, 9 * 3600):
            msg = compose_return_greeting(
                display_name="Rohit", absence_secs=secs,
            )
            self.assertNotIn(": '", msg)
            self.assertNotIn("you asked", msg.lower())


if __name__ == "__main__":
    unittest.main()
