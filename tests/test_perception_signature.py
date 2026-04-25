# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Perception-signature delta gate — 2026-04-25 fixation fix.

Locks in the axes that drive the gate (disk%, git dirty count,
presence, top-3 process names) and the skip-decision truth table.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.cognition.perception_signature import (
    compute_signature,
    extract_axes,
    redact_stale_perception_block,
    should_skip_reasoning,
    signature_from_axes,
    stale_fields,
    DEFAULT_MIN_THOUGHT_FLOOR,
    DEFAULT_STALE_THRESHOLD,
)


_SAMPLE_PERCEPTION_BLOCK = """=== System State: 2026-04-25 15:30:00 ===

CPU: 5.0% overall across 32 cores @ 1635 MHz, 64.0°C
RAM: 30.8/62.5 GB (49.3%)
GPU: 6.0% util, 19155/24564 MB VRAM, 47.0°C

Disk /: 33.2/46.6 GB (75.0%)
Disk /home: 167.0/306.0 GB (58.0%)
Network: ↑ 0.1 Mbps, ↓ 0.5 Mbps

Top processes (CPU):
  firefox                   CPU:  10.0%  MEM:   5.0%
  python3                   CPU:   2.0%  MEM:   1.5%
  chrome                    CPU:   1.0%  MEM:   3.0%
  systemd                   CPU:   0.0%  MEM:   0.0%
  kworker                   CPU:   0.0%  MEM:   0.0%
Top processes (MEM):
  firefox                   CPU:  10.0%  MEM:   5.0%
  chrome                    CPU:   1.0%  MEM:   3.0%
  python3                   CPU:   2.0%  MEM:   1.5%
  systemd                   CPU:   0.0%  MEM:   0.0%
  kworker                   CPU:   0.0%  MEM:   0.0%"""


def _snap(**overrides):
    snap = {
        "disk": {"/": {"percent": 75.0}},
        "top_processes_cpu": [
            {"name": "firefox"},
            {"name": "python3"},
            {"name": "chrome"},
        ],
    }
    snap.update(overrides)
    return snap


class SignatureAxes(unittest.TestCase):
    """Each axis that drives fixation must change the signature."""

    def test_identical_inputs_match(self):
        a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        self.assertEqual(a, b)

    def test_disk_one_percent_change_crosses(self):
        # Soul note threshold is at 75%; ~1% moves matter.
        a = compute_signature(_snap(disk={"/": {"percent": 74.4}}),
                              presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(_snap(disk={"/": {"percent": 75.0}}),
                              presence_state="at_desk", git_dirty_count=3)
        self.assertNotEqual(a, b)

    def test_disk_subpercent_noise_does_not_cross(self):
        a = compute_signature(_snap(disk={"/": {"percent": 75.0}}),
                              presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(_snap(disk={"/": {"percent": 75.2}}),
                              presence_state="at_desk", git_dirty_count=3)
        self.assertEqual(a, b)

    def test_presence_change_crosses(self):
        a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(_snap(), presence_state="away", git_dirty_count=3)
        self.assertNotEqual(a, b)

    def test_git_dirty_count_change_crosses(self):
        a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=4)
        self.assertNotEqual(a, b)

    def test_top_process_replacement_crosses(self):
        a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(
            _snap(top_processes_cpu=[
                {"name": "firefox"},
                {"name": "python3"},
                {"name": "code"},  # was chrome
            ]),
            presence_state="at_desk", git_dirty_count=3,
        )
        self.assertNotEqual(a, b)

    def test_top_process_reorder_does_not_cross(self):
        # Names sorted, so order noise doesn't churn the gate.
        a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        b = compute_signature(
            _snap(top_processes_cpu=[
                {"name": "chrome"},
                {"name": "firefox"},
                {"name": "python3"},
            ]),
            presence_state="at_desk", git_dirty_count=3,
        )
        self.assertEqual(a, b)

    def test_cpu_jitter_does_not_cross(self):
        # CPU/RAM/GPU intentionally excluded from signature — they
        # jitter cycle-to-cycle on idle and would prevent the gate
        # from ever firing on the very cycles that need it.
        a = compute_signature(
            {"disk": {"/": {"percent": 75.0}}, "cpu": {"percent": 0.4}},
            presence_state="at_desk", git_dirty_count=3,
        )
        b = compute_signature(
            {"disk": {"/": {"percent": 75.0}}, "cpu": {"percent": 9.9}},
            presence_state="at_desk", git_dirty_count=3,
        )
        self.assertEqual(a, b)


class SkipDecision(unittest.TestCase):
    """Truth table for should_skip_reasoning."""

    def test_first_cycle_does_not_skip(self):
        self.assertFalse(should_skip_reasoning(
            current_signature="any",
            last_thought_signature=None,
            cycles_since_last_thought=0,
        ))

    def test_signature_change_does_not_skip(self):
        self.assertFalse(should_skip_reasoning(
            current_signature="A",
            last_thought_signature="B",
            cycles_since_last_thought=3,
        ))

    def test_match_under_floor_skips(self):
        self.assertTrue(should_skip_reasoning(
            current_signature="A",
            last_thought_signature="A",
            cycles_since_last_thought=5,
            min_thought_floor=10,
        ))

    def test_match_at_floor_does_not_skip(self):
        # At floor: must run a thought to feed cognition_quality.
        self.assertFalse(should_skip_reasoning(
            current_signature="A",
            last_thought_signature="A",
            cycles_since_last_thought=10,
            min_thought_floor=10,
        ))

    def test_default_floor_is_5_minutes(self):
        # 10 cycles × 30s = 5 minutes. Long enough that fixation
        # can't accumulate inside the cognition_quality analyzer's
        # 20-cycle window; short enough that the analyzer always
        # has fresh data.
        self.assertEqual(DEFAULT_MIN_THOUGHT_FLOOR, 10)


class ExtractAxes(unittest.TestCase):
    """Patch A's foundation: per-cycle axis dict, used both for the
    gate signature AND for stale-fields detection."""

    def test_axes_have_expected_keys(self):
        axes = extract_axes(_snap(), presence_state="at_desk", git_dirty_count=3)
        self.assertEqual(
            set(axes.keys()), {"disk", "presence", "git", "procs"},
        )

    def test_disk_rounded_to_int(self):
        a = extract_axes(_snap(disk={"/": {"percent": 75.0}}))
        b = extract_axes(_snap(disk={"/": {"percent": 75.4}}))
        self.assertEqual(a["disk"], 75)
        self.assertEqual(b["disk"], 75)

    def test_signature_round_trips_through_axes(self):
        sig_a = compute_signature(_snap(), presence_state="at_desk", git_dirty_count=3)
        sig_b = signature_from_axes(extract_axes(
            _snap(), presence_state="at_desk", git_dirty_count=3,
        ))
        self.assertEqual(sig_a, sig_b)


class StaleFields(unittest.TestCase):
    """Patch A: the redactor input. A field is stale when it's been
    constant across the last `threshold` thoughts AND the current
    cycle. Stale fields get stripped from the prompt."""

    def test_empty_history_returns_no_stale(self):
        current = extract_axes(
            _snap(), presence_state="at_desk", git_dirty_count=3,
        )
        self.assertEqual(stale_fields([], current), set())

    def test_below_threshold_returns_no_stale(self):
        current = extract_axes(
            _snap(), presence_state="at_desk", git_dirty_count=3,
        )
        # Threshold defaults to 3; 2 entries shouldn't trigger.
        self.assertEqual(stale_fields([current, current], current), set())

    def test_all_axes_stable_returns_full_set(self):
        current = extract_axes(
            _snap(), presence_state="at_desk", git_dirty_count=3,
        )
        history = [current, current, current]
        self.assertEqual(
            stale_fields(history, current),
            {"disk", "presence", "git", "procs"},
        )

    def test_one_axis_changed_excludes_only_that_axis(self):
        # Disk varies in current; everything else stable.
        history = [
            extract_axes(_snap(disk={"/": {"percent": 75.0}}),
                         presence_state="at_desk", git_dirty_count=3),
            extract_axes(_snap(disk={"/": {"percent": 75.0}}),
                         presence_state="at_desk", git_dirty_count=3),
            extract_axes(_snap(disk={"/": {"percent": 75.0}}),
                         presence_state="at_desk", git_dirty_count=3),
        ]
        current = extract_axes(_snap(disk={"/": {"percent": 78.0}}),
                               presence_state="at_desk", git_dirty_count=3)
        self.assertEqual(
            stale_fields(history, current),
            {"presence", "git", "procs"},  # disk excluded — moved
        )

    def test_incident_shape_disk_stable_processes_vary(self):
        # The 2026-04-25 cycle 48-vs-51 case: disk + presence + git
        # stable across thoughts, top processes shuffle one slot.
        # Stale fields must include disk/presence/git but NOT procs.
        history = [
            extract_axes(_snap(top_processes_cpu=[
                {"name": "firefox"}, {"name": "python3"}, {"name": "chrome"},
            ]), presence_state="at_desk", git_dirty_count=3),
            extract_axes(_snap(top_processes_cpu=[
                {"name": "firefox"}, {"name": "python3"}, {"name": "code"},
            ]), presence_state="at_desk", git_dirty_count=3),
            extract_axes(_snap(top_processes_cpu=[
                {"name": "firefox"}, {"name": "python3"}, {"name": "node"},
            ]), presence_state="at_desk", git_dirty_count=3),
        ]
        current = extract_axes(_snap(top_processes_cpu=[
            {"name": "firefox"}, {"name": "python3"}, {"name": "chrome"},
        ]), presence_state="at_desk", git_dirty_count=3)
        result = stale_fields(history, current)
        self.assertIn("disk", result)
        self.assertIn("presence", result)
        self.assertIn("git", result)
        self.assertNotIn("procs", result)

    def test_threshold_default_is_3(self):
        self.assertEqual(DEFAULT_STALE_THRESHOLD, 3)


class RedactStalePerceptionBlock(unittest.TestCase):
    """Patch A: strip stale fields from format_snapshot() output."""

    def test_empty_stale_returns_unchanged(self):
        self.assertEqual(
            redact_stale_perception_block(_SAMPLE_PERCEPTION_BLOCK, set()),
            _SAMPLE_PERCEPTION_BLOCK,
        )

    def test_disk_stale_strips_disk_lines(self):
        out = redact_stale_perception_block(_SAMPLE_PERCEPTION_BLOCK, {"disk"})
        self.assertNotIn("Disk /", out)
        self.assertNotIn("33.2/46.6 GB", out)
        self.assertNotIn("167.0/306.0 GB", out)
        # Other content preserved.
        self.assertIn("CPU: 5.0%", out)
        self.assertIn("Top processes (CPU):", out)

    def test_procs_stale_strips_both_top_processes_sections(self):
        out = redact_stale_perception_block(_SAMPLE_PERCEPTION_BLOCK, {"procs"})
        self.assertNotIn("Top processes (CPU):", out)
        self.assertNotIn("Top processes (MEM):", out)
        self.assertNotIn("firefox", out)
        self.assertNotIn("kworker", out)
        # Disk + CPU + RAM lines preserved.
        self.assertIn("Disk /: 33.2", out)
        self.assertIn("CPU: 5.0%", out)
        self.assertIn("RAM: 30.8/62.5 GB", out)

    def test_both_stale_strips_both(self):
        out = redact_stale_perception_block(
            _SAMPLE_PERCEPTION_BLOCK, {"disk", "procs"})
        self.assertNotIn("Disk", out)
        self.assertNotIn("Top processes", out)
        self.assertNotIn("firefox", out)
        # CPU/RAM/network/header still there.
        self.assertIn("CPU: 5.0%", out)
        self.assertIn("RAM:", out)
        self.assertIn("Network:", out)
        self.assertIn("System State", out)

    def test_irrelevant_stale_axes_ignored(self):
        # 'presence' and 'git' axes don't live in format_snapshot's
        # output — caller handles them by gating their separate
        # append in _reason(). Asking the redactor about them is a
        # no-op.
        out = redact_stale_perception_block(
            _SAMPLE_PERCEPTION_BLOCK, {"presence", "git"})
        self.assertEqual(out, _SAMPLE_PERCEPTION_BLOCK)


if __name__ == "__main__":
    unittest.main()
