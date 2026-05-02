# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the 5x.F.B operational watch CLI parser.

The CLI's load-bearing part is the regex that extracts F.B's
structured log line + the three-region classification logic. The
journalctl / file I/O is shell-dependent and not worth mocking;
these tests cover the pure-function parser + Stats."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# Realistic journalctl-style output mixing F.B lines with surrounding
# noise (other log entries, timestamps, level tags). Every parser
# assertion must work against this shape, not a synthetic clean
# stream.
_REAL_LOG_SAMPLE = """\
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] Cycle 1100
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] baseline_update provenance downgraded=True untrusted_count=1 recall_count=3
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] Some other action
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] baseline_update provenance downgraded=False untrusted_count=0 recall_count=5
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] baseline_update provenance downgraded=False untrusted_count=0 recall_count=0
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] baseline_update provenance downgraded=True untrusted_count=2 recall_count=4
May 01 22:56:36 maez python3[420893]: 2026-05-01 22:56:36 [INFO] baseline_update provenance downgraded=False untrusted_count=0 recall_count=2
"""


class ParseLinesTests(unittest.TestCase):
    def test_parse_realistic_journalctl_output(self):
        from scripts.probe.baseline_downgrade_rate import parse_lines
        stats = parse_lines(_REAL_LOG_SAMPLE)
        self.assertEqual(stats.total, 5)
        self.assertEqual(stats.downgraded, 2)
        self.assertEqual(stats.untrusted_count_sum, 3)  # 1 + 0 + 0 + 2 + 0
        self.assertEqual(stats.recall_count_sum, 14)    # 3 + 5 + 0 + 4 + 2
        self.assertAlmostEqual(stats.downgrade_rate, 0.4)

    def test_parse_empty_input_returns_zeroed_stats(self):
        from scripts.probe.baseline_downgrade_rate import parse_lines
        stats = parse_lines("")
        self.assertEqual(stats.total, 0)
        self.assertEqual(stats.downgrade_rate, 0.0)

    def test_parse_ignores_unrelated_log_lines(self):
        """The parser must not match other 'provenance' or
        'downgraded' log lines from other subsystems."""
        from scripts.probe.baseline_downgrade_rate import parse_lines
        # Note the leading subsystem differs — must not match.
        text = (
            "[INFO] cycle_recall_context capture failed\n"
            "[INFO] some_other_action provenance downgraded=True\n"
            "[INFO] baseline_update other_field=42\n"
        )
        stats = parse_lines(text)
        self.assertEqual(stats.total, 0)

    def test_parse_skips_malformed_marker_lines_without_crashing(self):
        """A log line carrying the F.B marker substring but with
        a malformed payload (lowercase bool, negative count,
        missing field) must NOT crash the parser. Locks the
        contract against well-meaning future regex relaxation
        that could turn a malformed line into a parse error."""
        from scripts.probe.baseline_downgrade_rate import parse_lines
        text = (
            # lowercase 'true' — should NOT parse (regex anchored)
            "baseline_update provenance downgraded=true "
            "untrusted_count=1 recall_count=3\n"
            # missing untrusted_count — should NOT parse
            "baseline_update provenance downgraded=False "
            "recall_count=2\n"
            # one valid line so we can confirm parser isn't broken
            "baseline_update provenance downgraded=True "
            "untrusted_count=2 recall_count=4\n"
        )
        stats = parse_lines(text)
        self.assertEqual(stats.total, 1)
        self.assertEqual(stats.downgraded, 1)
        # All three lines carry the marker substring → 3 candidates.
        # Only one parsed → drift warning would fire (see other test).
        self.assertEqual(stats.candidate_line_count, 3)


class CandidateLineDriftWarningTests(unittest.TestCase):
    """M1+M2: when the F.B marker substring appears but the strict
    regex parsed zero, the CLI must surface a log-format-drift
    warning rather than emitting a confident 'no_data' verdict."""

    def test_candidate_count_exceeds_parsed_when_format_drifts(self):
        from scripts.probe.baseline_downgrade_rate import parse_lines
        # Future hypothetical log-format change: bool serialized
        # lowercase. All three lines carry the marker substring
        # but none match the strict regex.
        text = (
            "baseline_update provenance downgraded=true "
            "untrusted_count=1 recall_count=3\n"
            "baseline_update provenance downgraded=false "
            "untrusted_count=0 recall_count=2\n"
            "baseline_update provenance downgraded=false "
            "untrusted_count=0 recall_count=5\n"
        )
        stats = parse_lines(text)
        self.assertEqual(stats.total, 0)
        self.assertEqual(stats.candidate_line_count, 3)
        # The CLI's _format_human should emit "WARNING: log-format
        # drift detected" on this shape — exercised below.

    def test_human_output_warns_on_drift(self):
        from scripts.probe.baseline_downgrade_rate import (
            _format_human, parse_lines, parse_recall_count_distribution,
        )
        text = (
            "baseline_update provenance downgraded=true "
            "untrusted_count=1 recall_count=3\n"
        )
        out = _format_human(
            parse_lines(text),
            parse_recall_count_distribution(text),
            "test",
        )
        self.assertIn("WARNING", out)
        self.assertIn("log-format drift", out)
        # Must NOT confidently claim "dormant" when drift detected.
        self.assertNotIn("DORMANT", out)


class FloatingPointBoundaryTests(unittest.TestCase):
    """m2: thresholds use float comparison. Test non-power-of-two
    totals where IEEE 754 rounding can surprise."""

    def _stats(self, total, downgraded):
        from scripts.probe.baseline_downgrade_rate import Stats
        return Stats(total, downgraded, 0, 0, total)

    def test_dormant_at_exactly_5_percent_with_total_20(self):
        # 1/20 = exactly 0.05 in IEEE 754.
        self.assertEqual(self._stats(20, 1).region(), "dormant")

    def test_working_at_just_above_5_percent_with_total_37(self):
        # 2/37 ≈ 0.05405 → working
        self.assertEqual(self._stats(37, 2).region(), "working")

    def test_aggressive_at_exactly_40_percent_with_total_5(self):
        # 2/5 = 0.4 (exact in IEEE 754).
        self.assertEqual(self._stats(5, 2).region(), "aggressive")

    def test_working_at_just_below_40_percent_with_total_25(self):
        # 9/25 = 0.36 → working
        self.assertEqual(self._stats(25, 9).region(), "working")


class RegionClassificationTests(unittest.TestCase):
    def _stats(self, total, downgraded):
        from scripts.probe.baseline_downgrade_rate import Stats
        return Stats(total, downgraded, 0, 0)

    def test_no_data_region(self):
        self.assertEqual(self._stats(0, 0).region(), "no_data")

    def test_dormant_at_zero_percent(self):
        self.assertEqual(self._stats(100, 0).region(), "dormant")

    def test_dormant_at_exactly_5_percent(self):
        # Inclusive lower-bound: 5% is still dormant.
        self.assertEqual(self._stats(100, 5).region(), "dormant")

    def test_working_just_above_5_percent(self):
        self.assertEqual(self._stats(100, 6).region(), "working")

    def test_working_at_25_percent(self):
        self.assertEqual(self._stats(100, 25).region(), "working")

    def test_working_just_below_40_percent(self):
        self.assertEqual(self._stats(100, 39).region(), "working")

    def test_aggressive_at_exactly_40_percent(self):
        # Inclusive lower-bound: 40% is already aggressive.
        self.assertEqual(self._stats(100, 40).region(), "aggressive")

    def test_aggressive_at_100_percent(self):
        self.assertEqual(self._stats(50, 50).region(), "aggressive")


class RecallDistributionTests(unittest.TestCase):
    def test_distribution_counts_each_recall_count_value(self):
        from scripts.probe.baseline_downgrade_rate import (
            parse_recall_count_distribution,
        )
        dist = parse_recall_count_distribution(_REAL_LOG_SAMPLE)
        # recall_count values seen: 3, 5, 0, 4, 2 → all distinct, n=1 each
        self.assertEqual(dist, {0: 1, 2: 1, 3: 1, 4: 1, 5: 1})

    def test_distribution_groups_repeats(self):
        from scripts.probe.baseline_downgrade_rate import (
            parse_recall_count_distribution,
        )
        text = (
            "baseline_update provenance downgraded=False "
            "untrusted_count=0 recall_count=0\n"
            "baseline_update provenance downgraded=False "
            "untrusted_count=0 recall_count=0\n"
            "baseline_update provenance downgraded=False "
            "untrusted_count=0 recall_count=3\n"
        )
        dist = parse_recall_count_distribution(text)
        self.assertEqual(dist, {0: 2, 3: 1})


if __name__ == "__main__":
    unittest.main()
