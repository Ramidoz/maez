# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The pruner deletes only what it should, and never the newest.

This code deletes backups. It is tested on synthetic archives before it is
ever pointed at the real one.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.backup.prune import finalized_snapshots, plan, SNAPSHOT_FORMAT

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def build(root: Path, stamps, *, finalized=True):
    for s in stamps:
        d = root / s.strftime(SNAPSHOT_FORMAT)
        d.mkdir(parents=True)
        if finalized:
            (d / "manifest.json").write_text("{}")


class Pruning(unittest.TestCase):

    def _archive(self, stamps, **kw):
        tmp = Path(tempfile.mkdtemp())
        build(tmp, stamps, **kw)
        return tmp, finalized_snapshots(tmp)

    def test_recent_window_is_kept_entirely(self):
        stamps = [NOW - timedelta(hours=6 * i) for i in range(20)]  # 5 days
        _root, snaps = self._archive(stamps)
        kept, doomed = plan(snaps, now=NOW)
        self.assertEqual(len(doomed), 0)
        self.assertEqual(len(kept), 20)

    def test_newest_is_never_deleted_even_if_ancient(self):
        stamps = [NOW - timedelta(days=900)]
        _root, snaps = self._archive(stamps)
        kept, doomed = plan(snaps, now=NOW)
        self.assertEqual(doomed, [])
        self.assertIn("never pruned", kept[0][2])

    def test_dense_old_days_collapse_to_one_per_day(self):
        # 8 snapshots/day for 20 days, all older than the 7-day window.
        #
        # Note on what GFS does and does not promise: a date may legitimately
        # appear twice overall, once via the daily rule and once via the
        # weekly rule at the window boundary. The guarantee is per-rule, so
        # that is what is asserted. (My first version of this test asserted
        # global date-uniqueness and failed against correct behaviour.)
        stamps = [NOW - timedelta(days=d, hours=3 * h)
                  for d in range(10, 30) for h in range(8)]
        _root, snaps = self._archive(stamps)
        kept, _doomed = plan(snaps, now=NOW)
        daily_days = [k[0].date() for k in kept if k[2].startswith("daily")]
        self.assertEqual(len(daily_days), len(set(daily_days)),
                         "the daily rule kept more than one snapshot in a day")
        self.assertLess(len(kept), len(snaps) / 4,
                        "dense old snapshots did not collapse")

    def test_a_year_of_hourly_snapshots_collapses_hard(self):
        stamps = [NOW - timedelta(hours=6 * i) for i in range(4 * 365)]
        _root, snaps = self._archive(stamps)
        kept, doomed = plan(snaps, now=NOW)
        # 4/day for a year = 1460. Correct retention is ~28 (the 7-day window
        # at 4/day) + ~23 daily + ~22 weekly + ~12 monthly. My first threshold
        # of 80 was simply wrong arithmetic, not a code defect.
        self.assertLess(len(kept), 100, f"kept too many: {len(kept)}")
        self.assertGreater(len(kept), 50, f"kept too few: {len(kept)}")
        self.assertGreater(len(doomed), 1300)
        # and every retained bucket is represented
        self.assertTrue(any("monthly" in k[2] for k in kept))
        self.assertTrue(any("weekly" in k[2] for k in kept))
        self.assertTrue(any("daily" in k[2] for k in kept))

    def test_unfinalized_directories_are_invisible(self):
        tmp = Path(tempfile.mkdtemp())
        build(tmp, [NOW - timedelta(days=100)], finalized=False)
        (tmp / "2026-01-01T00-00-00.in-progress").mkdir()
        (tmp / "not-a-snapshot").mkdir()
        self.assertEqual(finalized_snapshots(tmp), [],
                         "a directory without manifest.json must be ignored, "
                         "not pruned")

    def test_oldest_is_never_deleted(self):
        stamps = [NOW - timedelta(days=d) for d in range(0, 400, 2)]
        _root, snaps = self._archive(stamps)
        kept, doomed = plan(snaps, now=NOW)
        oldest = min(snaps, key=lambda p: p[0])[1]
        self.assertNotIn(oldest, [d[1] for d in doomed],
                         "the first snapshot ever taken was pruned")
        self.assertIn("oldest snapshot",
                      next(k[2] for k in kept if k[1] == oldest))

    def test_every_kept_snapshot_has_a_stated_reason(self):
        stamps = [NOW - timedelta(days=d) for d in range(0, 400, 3)]
        _root, snaps = self._archive(stamps)
        kept, _ = plan(snaps, now=NOW)
        for _s, _p, reason in kept:
            self.assertTrue(reason.strip())

    def test_keep_and_delete_partition_the_archive(self):
        stamps = [NOW - timedelta(days=d) for d in range(0, 200, 2)]
        _root, snaps = self._archive(stamps)
        kept, doomed = plan(snaps, now=NOW)
        self.assertEqual(len(kept) + len(doomed), len(snaps))
        self.assertEqual(set(k[1] for k in kept) & set(d[1] for d in doomed),
                         set())


if __name__ == "__main__":
    unittest.main()
