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
    should_skip_reasoning,
    DEFAULT_MIN_THOUGHT_FLOOR,
)


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


if __name__ == "__main__":
    unittest.main()
