# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Manual runner for the B2 consolidation shadow witness ceremony."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.consolidation.span_planner import ConsolidationPaths, default_paths
from core.consolidation.span_planner import run_consolidation_pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one dormant consolidation shadow pass.",
    )
    parser.add_argument(
        "--ledger-db",
        type=Path,
        default=None,
        help="Ledger DB path. Defaults to memory/ledger.db via core.infra.paths.",
    )
    parser.add_argument(
        "--min-idle-seconds",
        type=float,
        default=30 * 60,
        help="Minimum manual idle window age to report to the runtime.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Root for shadow output DBs and receipts when using a custom "
            "ledger DB. Required with --ledger-db."
        ),
    )
    return parser


def _paths_for_args(*, ledger_db: Path | None, output_root: Path | None) -> ConsolidationPaths:
    paths = default_paths()
    if output_root is None:
        return ConsolidationPaths(
            ledger_db_path=ledger_db or paths.ledger_db_path,
            spine_db_path=paths.spine_db_path,
            episode_digests_db_path=paths.episode_digests_db_path,
            receipts_path=paths.receipts_path,
            live_wonderings_db_path=paths.live_wonderings_db_path,
        )
    root = output_root
    return ConsolidationPaths(
        ledger_db_path=ledger_db or paths.ledger_db_path,
        spine_db_path=root / "memory" / "consolidation" / "spine.sqlite3",
        episode_digests_db_path=(
            root / "memory" / "consolidation" / "episode_digests.sqlite3"
        ),
        receipts_path=root / "logs" / "consolidation_receipts.jsonl",
        live_wonderings_db_path=root / "memory" / "wonderings.db",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.ledger_db is not None and args.output_root is None:
        print(
            "error: --ledger-db requires --output-root so a rehearsal ledger "
            "cannot write real consolidation outputs",
            file=sys.stderr,
        )
        return 2
    paths = _paths_for_args(ledger_db=args.ledger_db, output_root=args.output_root)
    result = run_consolidation_pass(
        paths=paths,
        idle_inputs={
            "no_interaction_secs": float(args.min_idle_seconds),
            "camera": "absent",
            "active_until_future": False,
            "activity_known": True,
        },
        min_idle_seconds=float(args.min_idle_seconds),
    )
    print(json.dumps(result.__dict__, sort_keys=True, separators=(",", ":")))
    return 0 if result.status in {"completed", "empty", "disabled", "not_idle"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
