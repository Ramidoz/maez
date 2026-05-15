# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Regression contract for bounded camera-presence observation.

The daemon must never run native camera / MediaPipe presence detection
directly in the reasoning loop. If that native path hangs, the daemon
heartbeat must keep advancing and /health must report the timeout.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class PresenceObserveBoundedTests(unittest.TestCase):
    def setUp(self):
        self.src = (_REPO / "daemon" / "maez_daemon.py").read_text()

    def test_daemon_uses_bounded_presence_observer(self):
        self.assertIn('BoundedSingletonWorker(name="presence-observe"', self.src)
        self.assertIn("def _observe_presence_bounded(self)", self.src)
        self.assertIn("self._presence_worker.submit(", self.src)
        self.assertIn("self._presence_worker.join(timeout=", self.src)
        self.assertIn("presence observation timed out", self.src)

    def test_reasoning_loop_does_not_call_presence_observe_directly(self):
        loop = self.src.split("def _loop(self):", 1)[1].split("def start(self):", 1)[0]

        self.assertIn("self._observe_presence_bounded()", loop)
        self.assertNotIn("presence_observe()", loop)

    def test_daemon_uses_killable_subprocess_for_native_camera_probe(self):
        self.assertIn("def _run_presence_probe(self", self.src)
        self.assertIn('"-m", "skills.presence_perception"', self.src)
        self.assertIn("--json-once", self.src)
        self.assertIn("subprocess.run(", self.src)
        self.assertIn("def _presence_probe_env()", self.src)
        self.assertIn("env=self._presence_probe_env()", self.src)
        self.assertIn('"DISPLAY"', self.src)
        self.assertIn('"XAUTHORITY"', self.src)
        self.assertIn('"WAYLAND_DISPLAY"', self.src)

    def test_shutdown_closes_presence_worker(self):
        stop_body = self.src.split("def stop(self, signum=None, frame=None):", 1)[1]

        self.assertIn("self._presence_worker.shutdown(timeout=", stop_body)
        self.assertIn("Presence worker did not finish within shutdown timeout", stop_body)
        self.assertIn("native_shutdown_timeout", stop_body)

    def test_disabled_mode_shutdown_does_not_import_native_presence_cleanup(self):
        stop_body = self.src.split("def stop(self, signum=None, frame=None):", 1)[1]

        self.assertIn("self._presence_native_initialized", self.src)
        self.assertIn("if self._presence_native_initialized:", stop_body)


if __name__ == "__main__":
    unittest.main()
