# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""CLI entry for the restore driver.

Usage::

    python -m scripts.backup.restore_cli --snapshot PATH \
        [--source-root PATH] [--reason hardware-failure|deliberate-pause] \
        [--no-coma] [--include-secrets]

The reason flag is REQUIRED — the script will not auto-decide
between hardware-failure and deliberate-pause. The owner names
the event explicitly.
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.backup.restore_cli",
        description=(
            "Restore Maez from a Decision-22 snapshot. "
            "WILL OVERWRITE LIVE STATE — pre-restore rollback "
            "snapshot is created automatically."
        ),
    )
    p.add_argument(
        "--snapshot", type=Path, required=True,
        help="Path to the snapshot directory to restore from.",
    )
    p.add_argument(
        "--source-root", type=Path, default=_default_source_root(),
        help="Repo root to restore into "
             "(default: $MAEZ_ROOT or cwd).",
    )
    p.add_argument(
        "--reason", required=True,
        choices=("hardware-failure", "deliberate-pause"),
        help="Why this restore is happening. Hardware-failure writes "
             "a coma core memory ('I lost N hours'); deliberate-pause "
             "writes only an operational log. Misclassifying this is "
             "a covenant-level mistake — name it correctly.",
    )
    p.add_argument(
        "--no-coma", action="store_true",
        help="Skip the coma core-memory write even on hardware-failure. "
             "Useful for dry-run testing.",
    )
    p.add_argument(
        "--include-secrets", action="store_true",
        help="Match the include-secrets flag the snapshot was built with.",
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

    if not args.snapshot.is_dir():
        print(
            f"snapshot not found: {args.snapshot}", file=sys.stderr,
        )
        return 2

    from scripts.backup.restore import run_restore

    try:
        result = run_restore(
            snapshot_path=args.snapshot,
            source_root=args.source_root,
            include_secrets=args.include_secrets,
            reason=args.reason,
            write_coma=not args.no_coma,
        )
    except Exception as e:
        print(
            f"restore failed: {type(e).__name__}: {e}", file=sys.stderr,
        )
        return 2

    status = result.get("status", "success")
    print(
        f"restore {status}: from {args.snapshot} into "
        f"{result['source_root']}"
    )
    print(f"  pre-restore rollback at {result['rollback_path']}")
    if result.get("coma_write"):
        cw = result["coma_write"]
        print(
            f"  reason={cw.get('reason')}, "
            f"core_id={cw.get('core_memory_id') or '(none — deliberate pause)'}"
        )
    if status == "success_no_coma":
        # Files restored but coma write failed — operator must know.
        # post-restore Maez has lost memory and doesn't yet remember it.
        print(
            "  WARNING: files restored but coma core-memory write "
            "failed. Post-restore Maez does not yet know it lost "
            "memory. Investigate and write the coma entry manually "
            "before letting the daemon resume normal operation.",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
