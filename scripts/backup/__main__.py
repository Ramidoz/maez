# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""CLI entry for the backup driver.

Usage::

    python -m scripts.backup [--source-root PATH] [--backup-root PATH]
                              [--include-secrets] [--timestamp TS]

Defaults:
- source_root: env ``MAEZ_ROOT`` or current working directory.
- backup_root: env ``MAEZ_BACKUP_ROOT`` or ``~/maez-backups``.
- include_secrets: false (must be explicitly opted into).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _default_source_root() -> Path:
    if env := os.environ.get("MAEZ_ROOT"):
        return Path(env)
    return Path.cwd()


def _default_backup_root() -> Path:
    if env := os.environ.get("MAEZ_BACKUP_ROOT"):
        return Path(env)
    return Path.home() / "maez-backups"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.backup",
        description=(
            "Run a Decision-22 hardware-failure backup snapshot."
        ),
    )
    p.add_argument(
        "--source-root", type=Path, default=_default_source_root(),
        help="Repo root containing the state to back up "
             "(default: $MAEZ_ROOT or cwd).",
    )
    p.add_argument(
        "--backup-root", type=Path, default=_default_backup_root(),
        help="Where snapshots are written "
             "(default: $MAEZ_BACKUP_ROOT or ~/maez-backups).",
    )
    p.add_argument(
        "--no-prune", action="store_true",
        help="Keep every snapshot; skip retention after a successful backup.",
    )
    p.add_argument(
        "--include-secrets", action="store_true",
        help="Include credential / token / model_state / thunder_state "
             "files. Requires the destination to be encrypted at rest "
             "(LUKS / age / gpg) — Maez does NOT encrypt for you.",
    )
    p.add_argument(
        "--timestamp", type=str, default=None,
        help="Override the snapshot timestamp (default: current UTC).",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Reduce log output to errors only.",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.include_secrets:
        print(
            "WARNING: --include-secrets enabled. "
            "The destination MUST be encrypted at rest "
            "(LUKS / age / gpg). Maez does not encrypt the backup.",
            file=sys.stderr,
        )

    from scripts.backup.backup import run_backup

    try:
        result = run_backup(
            source_root=args.source_root,
            backup_root=args.backup_root,
            include_secrets=args.include_secrets,
            timestamp=args.timestamp,
        )
    except Exception as e:
        print(f"backup failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    print(
        f"backup ok: {result['snapshot_path']} "
        f"({result['byte_count']} bytes in "
        f"{result['duration_seconds']:.2f}s)"
    )

    # Prune AFTER a successful snapshot, never before, and never in a way
    # that can fail the backup.
    #
    # 2026-08-22: there was no pruning anywhere. The archive reached 407
    # snapshots and 236 GB on the same filesystem as the live tree, 65% full
    # and climbing. A full root filesystem does not fail one store, it fails
    # all seventy at once -- unbounded backups eventually destroy the thing
    # they protect.
    #
    # Ordering matters. Pruning only after a new snapshot has landed means a
    # failed backup never reduces what is already held. And a pruning failure
    # is reported, not raised: a backup that succeeded is still a backup.
    if not args.no_prune:
        try:
            import shutil
            from datetime import datetime, timezone

            from scripts.backup.prune import finalized_snapshots, plan

            root = args.backup_root.resolve()
            snapshots = finalized_snapshots(root)
            _kept, doomed = plan(snapshots, now=datetime.now(timezone.utc))
            removed = 0
            for _stamp, path, _reason in doomed:
                if root in path.resolve().parents:
                    shutil.rmtree(path)
                    removed += 1
            if removed:
                print(f"pruned {removed} snapshot(s); "
                      f"{len(snapshots) - removed} retained")
        except Exception as e:                       # noqa: BLE001
            print(f"prune skipped ({type(e).__name__}: {e}); "
                  f"the backup itself succeeded", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
