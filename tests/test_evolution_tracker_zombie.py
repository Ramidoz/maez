# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The evolution zombie — an organ failing silently, every cycle.

FOUND IN PRODUCTION 2026-08-28 (Codex store audit, confirmed by
execution): ``logs/maez.log`` carries 171 occurrences of
``Evolution check failed: expected str, bytes or os.PathLike object,
not NoneType`` — one per logged cycle from 2026-08-27 06:30 through
2026-08-28 12:15.

THE BUG is a single-token slip in ``EvolutionTracker.__init__``: it
computes ``self.db_path`` with a default, then calls
``os.path.dirname(db_path)`` on the RAW parameter, which is ``None``
whenever the caller relies on that default — which the daemon's
``check_and_revert`` always does.

WHY THIS IS THE SECOND FAILURE CLASS. The daemon logs the exception at
DEBUG and continues. Every other organ kept working, the cycle
completed, nothing paged anyone. An organ was dead for at least a day
and the body reported itself healthy. Silence is not health.

SAFETY, verified before the fix landed: fixing the constructor changes
this path from "always raises" to "runs". ``check_and_revert`` can
revert files and message the owner, so that was checked rather than
assumed — the live store's exact pending query
(``post_insight_rate IS NULL AND deployed_at < cutoff``) returns ZERO
rows, and its single deployment is already resolved
(``post_insight_rate=65.0, verdict='kept'``). The fix therefore
no-ops. Whether this organ should run AT ALL is a retirement question
for the anatomy audit, not something this repair decides.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

_PROBE_ROOT = "/var/tmp"


class EvolutionTrackerConstructionTests(unittest.TestCase):
    def test_the_default_path_constructor_does_not_raise(self):
        """The exact call the daemon makes, every 20 cycles.

        MAEZ_ROOT is redirected so the default resolves inside scratch —
        constructing with the REAL default would CREATE TABLEs in the
        live evolution_track.db, which is the instrument-destroys-the-
        evidence trap this repo has already been bitten by.
        """
        from skills import evolution_engine

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            (Path(tmp) / "memory").mkdir()
            with mock.patch.object(evolution_engine, "MAEZ_ROOT", tmp):
                tracker = evolution_engine.EvolutionTracker()
                self.assertEqual(
                    tracker.db_path, f"{tmp}/memory/evolution_track.db",
                    "the computed default must be the path actually used",
                )
                self.assertTrue(
                    Path(tracker.db_path).exists(),
                    "constructing the tracker must create its store",
                )

    def test_an_explicit_path_still_works(self):
        from skills import evolution_engine

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            explicit = str(Path(tmp) / "nested" / "custom.db")
            tracker = evolution_engine.EvolutionTracker(db_path=explicit)
            self.assertEqual(tracker.db_path, explicit)
            self.assertTrue(
                Path(explicit).exists(),
                "an explicit path must still have its parent created",
            )

    def test_the_daemon_call_path_completes(self):
        """End to end: the thing that has been raising 171 times.

        ``check_and_revert`` must reach its own early return rather than
        dying in the constructor. A no-op is the correct outcome here —
        the point is that it is a no-op BY QUERY, not by exception.
        """
        from skills import evolution_engine

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            (Path(tmp) / "memory").mkdir()
            sent: list = []
            with mock.patch.object(evolution_engine, "MAEZ_ROOT", tmp):
                evolution_engine.check_and_revert(
                    None, telegram_callback=sent.append
                )
            self.assertEqual(
                sent, [],
                "an empty tracker must not speak to the owner",
            )


class SilentFailureTests(unittest.TestCase):
    """The class fix: an organ dying must not be a DEBUG line."""

    def test_the_daemon_reports_evolution_failure_above_debug(self):
        import inspect

        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon)
        idx = src.find("Evolution check failed")
        self.assertGreater(idx, -1, "the evolution guard vanished")
        line_start = src.rfind("logger.", 0, idx)
        level_line = src[line_start:idx]
        self.assertNotIn(
            "logger.debug", level_line,
            "an organ failing on EVERY cycle was logged at DEBUG and went "
            "unnoticed for at least a day; a dead organ must be visible "
            "at WARNING or above",
        )


if __name__ == "__main__":
    unittest.main()
