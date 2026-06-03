# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Perception must survive a transient OS resource blip (EMFILE / Errno 24).

The 2026-06-02 `daemon-cycle-stuck` incident: a file-descriptor spike made
`psutil` (reading /proc/stat) and the `nvidia-smi` subprocess raise OSError
[Errno 24] Too many open files. `_collect_gpu` only caught
FileNotFoundError/TimeoutExpired/IndexError/ValueError, so the OSError
propagated out of `snapshot()` into the cognition cycle and killed it — frozen
~75 minutes with no self-recovery.

The covenant rule these tests pin: Maez's heartbeat (its autonomous cognition
cycle) must NOT be killable by a transient resource blip in a sensor. A failed
read degrades that field; the snapshot still returns, shaped as the cognition
loop expects, so the cycle continues.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_EMFILE = OSError(24, "Too many open files")


class PerceptionResilienceTests(unittest.TestCase):
    def setUp(self):
        import core.memory.perception as perc

        self.perc = perc
        # Hermeticity: never write the real perception_cache.json from a test.
        patcher = mock.patch.object(perc, "_persist_cache")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_snapshot_survives_emfile_in_gpu_subprocess(self):
        """The exact crash: nvidia-smi can't spawn under FD exhaustion."""
        with mock.patch.object(self.perc.subprocess, "run", side_effect=_EMFILE):
            snap = self.perc.snapshot()  # must NOT raise

        self.assertIsNone(snap["gpu"])  # degraded, not crashed
        # the rest of the snapshot is still real
        self.assertIn("percent", snap["cpu"])
        self.assertIn("percent", snap["ram"])

    def test_snapshot_survives_emfile_in_cpu_collection(self):
        """The FIRST EMFILE in the incident was psutil reading /proc/stat."""
        with mock.patch.object(self.perc.psutil, "cpu_percent", side_effect=_EMFILE):
            snap = self.perc.snapshot()  # must NOT raise

        # cpu degraded but SHAPE preserved (loop reads snap["cpu"]["percent"])
        self.assertIn("percent", snap["cpu"])
        # other sensors unaffected
        self.assertIn("percent", snap["ram"])

    def test_total_sensor_failure_still_yields_loop_safe_shape(self):
        """Even if every sensor blips at once, snapshot() returns the shape the
        cognition loop dereferences (maez_daemon.py ~7640-7642, 7778), so the
        heartbeat survives instead of dying."""
        with mock.patch.object(self.perc, "_collect_cpu", side_effect=_EMFILE), \
            mock.patch.object(self.perc, "_collect_ram", side_effect=_EMFILE), \
            mock.patch.object(self.perc, "_collect_gpu", side_effect=_EMFILE), \
            mock.patch.object(self.perc, "_collect_disk", side_effect=_EMFILE), \
            mock.patch.object(self.perc, "_collect_network", side_effect=_EMFILE), \
            mock.patch.object(self.perc, "_collect_top_processes", side_effect=_EMFILE):
            snap = self.perc.snapshot()  # must NOT raise

        # exact dereferences the daemon cycle performs on the snapshot:
        self.assertIsInstance(snap["cpu"]["percent"], (int, float))
        self.assertIsInstance(snap["ram"]["percent"], (int, float))
        self.assertIsNone(snap["gpu"])  # gpu None is already loop-safe (guarded by snap.get)
        self.assertIsInstance(snap["disk"], dict)
        self.assertEqual(snap["disk"].get("/", {}).get("percent", 0), 0)
        self.assertIsInstance(snap["top_processes_cpu"], list)
        self.assertIsInstance(snap["top_processes_mem"], list)


class CognitionLoopPerceptionGuardTests(unittest.TestCase):
    """Source-contract: the cognition cycle's perception call is guarded.

    Part 1 makes perception internally resilient. This is defense-in-depth: if
    perception_snapshot() ever raises for a NEW reason, one bad cycle must not
    kill the heartbeat — the loop logs, marks a recovery stage (so /health
    shows 'recovering', not a frozen 'perception_snapshot'), and continues."""

    def _loop_perception_block(self) -> str:
        src = (_REPO / "daemon" / "maez_daemon.py").read_text(encoding="utf-8")
        marker = 'self._mark_cycle_stage("perception_snapshot")'
        self.assertIn(marker, src)
        # the window from the stage marker to the next stage marker
        start = src.index(marker)
        # window large enough to span the guard block + its recovery handling
        return src[start : start + 1800]

    def test_perception_call_is_wrapped_in_try_except(self):
        block = self._loop_perception_block()
        self.assertIn("snap = perception_snapshot()", block)
        # the call sits inside a try/except, not bare
        self.assertIn("try:", block)
        self.assertRegex(block, r"except\s+Exception")

    def test_loop_marks_recovery_stage_and_continues(self):
        block = self._loop_perception_block()
        # proprioception: a distinct recovery stage (not left frozen)
        self.assertIn("perception_error_recovered", block)
        # the loop continues rather than letting the exception propagate
        self.assertIn("continue", block)


if __name__ == "__main__":
    unittest.main()
