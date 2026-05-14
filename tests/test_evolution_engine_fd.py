# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Regression tests for evolution-engine SQLite handle lifecycle."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch


def _open_fd_count(path: str) -> int:
    target = os.path.realpath(path)
    count = 0
    fd_root = "/proc/self/fd"
    for name in os.listdir(fd_root):
        fd_path = os.path.join(fd_root, name)
        try:
            if os.path.realpath(fd_path) == target:
                count += 1
        except FileNotFoundError:
            pass
    return count


class EvolutionEngineFdLifecycleTest(unittest.TestCase):
    def test_worker_tick_without_jobs_does_not_leak_evolution_db_handles(self):
        from skills import evolution_engine

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "evolution_track.db")
            with patch.object(evolution_engine, "EVOLUTION_DB", db_path):
                evolution_engine._init_rail_schema()
                before = _open_fd_count(db_path)

                for _ in range(5):
                    evolution_engine._worker_tick()

                after = _open_fd_count(db_path)

        self.assertEqual(after, before)

