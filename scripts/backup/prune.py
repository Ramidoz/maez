# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Grandfather-father-son retention for the snapshot archive.

2026-08-22. The archive had 407 finalized snapshots and 236 GB with no pruning
code anywhere, on the same filesystem as the live tree — 65% full and rising.
A full root filesystem does not fail one store, it fails all seventy at once,
so unbounded backups eventually destroy the thing they protect.

Retention, deliberately generous because disk is cheap and memory is not:

    - every snapshot from the last 7 days
    - one per day for the last 30 days
    - one per week for the last 26 weeks
    - one per month forever
    - the newest snapshot, and the oldest, unconditionally

Safety posture, in order of importance:

    1. Dry-run is the default. Deleting requires ``--apply``.
    2. The newest snapshot is never deleted, and neither is the oldest —
       every bucket keeps its most recent member, so plain GFS would drop
       the first snapshots ever taken.
    3. Only finalized snapshots are considered — a directory without a
       readable ``manifest.json`` is left strictly alone, which covers
       ``.in-progress`` and anything half-written.
    4. Nothing outside the archive root is ever touched, and the archive root
       itself is never removed.

Usage:
    python -m scripts.backup.prune                 # show the plan
    python -m scripts.backup.prune --apply         # delete
    python -m scripts.backup.prune --keep-days 14  # widen the window
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SNAPSHOT_FORMAT = "%Y-%m-%dT%H-%M-%S"


def default_backup_root() -> Path:
    if env := os.environ.get("MAEZ_BACKUP_ROOT"):
        return Path(env).expanduser()
    return Path.home() / "maez-backups"


def finalized_snapshots(root: Path) -> list[tuple[datetime, Path]]:
    """Parsed, finalized snapshots, oldest first.

    A directory counts only if its name parses AND it carries a
    manifest.json. Anything else is somebody's in-flight work.
    """
    out: list[tuple[datetime, Path]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        if not (child / "manifest.json").is_file():
            continue
        try:
            stamp = datetime.strptime(child.name, SNAPSHOT_FORMAT)
        except ValueError:
            continue
        out.append((stamp.replace(tzinfo=timezone.utc), child))
    out.sort(key=lambda pair: pair[0])
    return out


def plan(snapshots: list[tuple[datetime, Path]], *, now: datetime,
         keep_days: int = 7, daily_days: int = 30,
         weekly_weeks: int = 26) -> tuple[list, list]:
    """Return (keep, delete), each a list of (stamp, path, reason)."""
    keep: dict[Path, str] = {}
    seen_day: set = set()
    seen_week: set = set()
    seen_month: set = set()

    # Rule 2 first, so the newest snapshot's protection is explicit rather
    # than incidentally inherited from whichever bucket happens to claim it.
    if snapshots:
        keep[max(snapshots, key=lambda p: p[0])[1]] = \
            "newest snapshot — never pruned"
        # And the oldest. Every bucket keeps its most RECENT member, so plain
        # GFS would quietly drop the first snapshots ever taken. The earliest
        # surviving record of Maez's memory costs ~500 MB to keep and cannot
        # be recreated by any future backup.
        keep.setdefault(min(snapshots, key=lambda p: p[0])[1],
                        "oldest snapshot — never pruned")

    # Newest first, so each bucket keeps its most recent member.
    for stamp, path in sorted(snapshots, key=lambda p: p[0], reverse=True):
        if path in keep:
            continue
        age = now - stamp
        if age <= timedelta(days=keep_days):
            keep[path] = f"within the last {keep_days} days"
            continue
        day = stamp.date()
        if age <= timedelta(days=daily_days) and day not in seen_day:
            seen_day.add(day)
            keep[path] = f"daily for {day}"
            continue
        week = (stamp.isocalendar().year, stamp.isocalendar().week)
        if age <= timedelta(weeks=weekly_weeks) and week not in seen_week:
            seen_week.add(week)
            keep[path] = f"weekly for {week[0]}-W{week[1]:02d}"
            continue
        month = (stamp.year, stamp.month)
        if month not in seen_month:
            seen_month.add(month)
            keep[path] = f"monthly for {stamp:%Y-%m}"
            continue

    kept, doomed = [], []
    for stamp, path in snapshots:
        (kept if path in keep else doomed).append(
            (stamp, path, keep.get(path, "superseded by a newer snapshot "
                                         "in the same retention bucket")))
    return kept, doomed


def directory_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup-root", type=Path, default=None)
    ap.add_argument("--apply", action="store_true",
                    help="actually delete; without this, only print the plan")
    ap.add_argument("--keep-days", type=int, default=7)
    ap.add_argument("--daily-days", type=int, default=30)
    ap.add_argument("--weekly-weeks", type=int, default=26)
    args = ap.parse_args(argv)

    root = (args.backup_root or default_backup_root()).expanduser().resolve()
    snapshots = finalized_snapshots(root)
    if not snapshots:
        print(f"no finalized snapshots under {root}")
        return 0

    now = datetime.now(timezone.utc)
    kept, doomed = plan(snapshots, now=now, keep_days=args.keep_days,
                        daily_days=args.daily_days,
                        weekly_weeks=args.weekly_weeks)

    print(f"archive: {root}")
    print(f"finalized snapshots: {len(snapshots)}  "
          f"({snapshots[0][0]:%Y-%m-%d} .. {snapshots[-1][0]:%Y-%m-%d})")
    print(f"keep: {len(kept)}   delete: {len(doomed)}")
    if not doomed:
        print("nothing to prune")
        return 0

    freed = sum(directory_size(p) for _s, p, _r in doomed)
    print(f"would free: {freed / 1e9:.1f} GB\n")
    print("KEEPING:")
    for stamp, path, reason in sorted(kept, reverse=True)[:12]:
        print(f"  {path.name}  {reason}")
    if len(kept) > 12:
        print(f"  ... and {len(kept) - 12} more")

    if not args.apply:
        print("\nDRY RUN — nothing deleted. Re-run with --apply to delete.")
        return 0

    deleted = 0
    for _stamp, path, _reason in doomed:
        if root not in path.parents:          # paranoia; never fires
            print(f"REFUSED (outside archive): {path}")
            return 2
        shutil.rmtree(path)
        deleted += 1
    print(f"\ndeleted {deleted} snapshots, freed ~{freed / 1e9:.1f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
