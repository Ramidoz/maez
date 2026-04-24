# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Regression tests for non-terminating shell command guards."""

from __future__ import annotations

import unittest

from core.action_engine import ActionEngine, ForbiddenActionError


class ContinuousCommandGuard(unittest.TestCase):
    def setUp(self):
        self.engine = ActionEngine.__new__(ActionEngine)

    def assert_forbidden(self, cmd: str):
        with self.assertRaisesRegex(ForbiddenActionError, "non-terminating"):
            self.engine._check_forbidden("run_shell", {"cmd": cmd})

    def test_blocks_incident_nvidia_smi_loop(self):
        self.assert_forbidden(
            "echo '=== SYSTEM VITALS ===' && "
            "nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total "
            "--format=csv -l 1 && tail -n 5 logs/maez.log"
        )

    def test_blocks_common_streaming_commands(self):
        for cmd in (
            "tail -f logs/maez.log",
            "tail -F logs/maez.log",
            "journalctl -f -u maez",
            "journalctl -fu maez",
            "watch nvidia-smi",
            "strace -p 1234",
        ):
            with self.subTest(cmd=cmd):
                self.assert_forbidden(cmd)

    def test_allows_finite_diagnostic_commands(self):
        allowed = [
            "nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader",
            "tail -n 20 logs/maez.log",
            "journalctl -n 50 -u maez --no-pager",
            "strace -c -p 1234",
        ]
        for cmd in allowed:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.engine._check_forbidden("run_shell", {"cmd": cmd}))


if __name__ == "__main__":
    unittest.main()
