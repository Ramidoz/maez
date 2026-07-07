#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Run unittest discover and write the repo-green receipt for birth readiness."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RECEIPT_PATH = ROOT / "memory" / "repo_green_receipt.json"
FLOOR_NOTE = (
    "floor=3 known pre-existing tests.test_memory_integrity_invariant drifts: "
    "web-search prose inventory drift; adapter self-claim audit import drift; "
    "stale retry-marker cognition-quality-grader cleanup drift"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def _worktree_clean() -> bool:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
    )
    return status == ""


def main() -> int:
    started_at = _utc_now()
    try:
        commit = _head()
        worktree_clean = _worktree_clean()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        receipt = {
            "commit": commit,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "ran": int(result.testsRun),
            "failures": len(result.failures),
            "errors": len(result.errors),
            "floor_note": FLOOR_NOTE,
            "worktree_clean": worktree_clean,
        }
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except BaseException as exc:
        receipt = {
            "commit": "",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "ran": 0,
            "failures": 0,
            "errors": 1,
            "floor_note": f"repo_green_receipt crashed: {exc.__class__.__name__}",
        }
        try:
            RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT_PATH.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"repo_green_receipt crashed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
