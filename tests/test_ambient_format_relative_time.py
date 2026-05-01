# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5s — relative-time rendering for ambient signals.

The ambient block previously emitted truncated ISO timestamps for
signal events ("(2026-05-01T03:0Z)"). The model would have to do
datetime math on every chat turn to translate those into "about 4
hours ago". This slice wires Step 5c's relative_time_phrase into
the ambient formatter so signals render as humanized phrases
against the block's own ``now`` reference.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class TestHumanizeSignalTime(unittest.TestCase):
    def test_signal_recent_renders_as_hours_before_now(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T03:00:00+00:00",
            "2026-05-01T07:00:00+00:00",
        )
        self.assertIn("hour", out)
        self.assertIn("before now", out)

    def test_signal_days_old(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-04-25T08:00:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertIn("days", out)
        self.assertIn("before now", out)

    def test_thirty_minutes_renders_as_minutes_before_now(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T07:30:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "30 minutes before now")

    def test_one_minute_renders_singular(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T07:59:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "1 minute before now")

    def test_under_one_minute_just_now(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T07:59:50+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "just now")

    def test_about_four_hours(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T03:00:00+00:00",
            "2026-05-01T07:00:00+00:00",
        )
        self.assertEqual(out, "about 4 hours before now")

    def test_future_dated_signal_uses_in_phrasing(self):
        """Clock-skew edge case: signal arrived a few seconds in
        the future relative to the ambient block's ``now``. Should
        render as 'in seconds' / 'in N minutes' / 'in about N
        hours' rather than crash."""
        from core.memory.ambient_format import _humanize_signal_time
        # 30s skew
        out = _humanize_signal_time(
            "2026-05-01T08:00:30+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "in seconds")
        # 5 min ahead
        out = _humanize_signal_time(
            "2026-05-01T08:05:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "in 5 minutes")
        # 4 hours ahead
        out = _humanize_signal_time(
            "2026-05-01T12:00:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertEqual(out, "in about 4 hours")

    def test_future_signal_uses_from_now(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-08T08:00:00+00:00",
            "2026-05-01T08:00:00+00:00",
        )
        self.assertIn("from now", out)
        self.assertNotIn("before now", out)

    def test_unparseable_falls_back_to_truncated_iso(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "not a timestamp",
            "2026-05-01T08:00:00+00:00",
        )
        # Falls back to the original 16-char trim convention.
        self.assertEqual(out, "not a timestampZ"[:17])

    def test_missing_reference_falls_back_to_iso(self):
        from core.memory.ambient_format import _humanize_signal_time
        out = _humanize_signal_time(
            "2026-05-01T07:30:00+00:00", None,
        )
        # Truncated ISO with Z suffix.
        self.assertTrue(out.endswith("Z"))
        self.assertIn("2026-05-01", out)

    def test_empty_signal_returns_empty(self):
        from core.memory.ambient_format import _humanize_signal_time
        self.assertEqual(
            _humanize_signal_time("", "2026-05-01T08:00:00+00:00"),
            "",
        )


class TestFormatRendersRelativeTime(unittest.TestCase):
    def test_format_uses_relative_phrase_for_signal_block(self):
        """The full _format() output should contain relative phrases
        on the signals block, not raw truncated ISO."""
        from core.memory.ambient_format import _format

        ctx = {
            "now": "2026-05-01T07:00:00+00:00",
            "signals_latest": {
                "arrive_home": {
                    "timestamp": "2026-05-01T03:00:00+00:00",
                    "kind": "arrive_home",
                    "data": {},
                    "source": "ios_shortcuts",
                },
            },
        }
        out = _format(ctx)
        self.assertIn("arrive_home", out)
        self.assertIn("before now", out)
        # The truncated-ISO marker should not appear for this signal.
        self.assertNotIn("(2026-05-01T03:0Z)", out)


class TestNoRegressionOnExistingTests(unittest.TestCase):
    def test_ambient_prompt_block_renders_without_raising(self):
        """The pre-existing chat-injection sanity test (Step 5r).
        Re-checked here so a regression in this slice surfaces
        immediately rather than at the next test_chat_ambient
        run."""
        from core.memory.ambient_format import ambient_prompt_block
        out = ambient_prompt_block()
        self.assertIsInstance(out, str)


if __name__ == "__main__":
    unittest.main()
