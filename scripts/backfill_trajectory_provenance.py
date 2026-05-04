#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""ACTION-Hi-1 — backfill provenance fields on pre-existing
logs/trajectories/*.jsonl entries.

Every line in the trajectory files is missing the provenance
contract added today (provenance_source, trust_tier,
training_eligible, provenance_version). Without this backfill,
historical entries would either:
  - be silently included by a future exporter that doesn't filter
    on provenance-presence (worst case), or
  - require a hand-coded "skip if missing" rule per consumer.

This script appends defaults to every line, derived from the
entry's existing ``source`` field. Idempotent: re-running on a
post-backfill file is a no-op.

Usage:
  .venv/bin/python scripts/backfill_trajectory_provenance.py --dry-run
  .venv/bin/python scripts/backfill_trajectory_provenance.py --commit

Default is dry-run. ``--commit`` writes back atomically (write-
to-tmp + rename). Log goes to
``logs/backfill_trajectory_provenance_<YYYY-MM-DD>.txt``.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_TRAJ_DIR = REPO / "logs" / "trajectories"


def _provenance_for(entry: dict) -> dict:
    """Return the provenance keys to merge in (without overwriting
    any caller-supplied values)."""
    src = (entry.get("source") or "").lower()
    if src == "local":
        prov_source, tier = "local_maez", "own_voice"
    elif src == "external":
        prov_source, tier = "claude_external", "untrusted"
    else:
        prov_source, tier = "unknown", "untrusted"
    return {
        "provenance_source": prov_source,
        "trust_tier": tier,
        "training_eligible": 0,
        "provenance_version": "v1_backfill_2026_05_04",
    }


def _process_file(path: Path, *, commit: bool, log: list[str]) -> tuple[int, int]:
    """Returns (lines_total, lines_modified). Atomic write on
    commit. No-op on entries that already have all four
    provenance keys."""
    lines_total = 0
    lines_modified = 0
    new_lines: list[str] = []
    with path.open() as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if not raw:
                new_lines.append("")
                continue
            lines_total += 1
            try:
                entry = json.loads(raw)
            except Exception as e:
                log.append(f"  [WARN] parse failed in {path.name}: {e}")
                new_lines.append(raw)
                continue
            prov = _provenance_for(entry)
            modified = False
            for k, v in prov.items():
                if k not in entry:
                    entry[k] = v
                    modified = True
            if modified:
                lines_modified += 1
            new_lines.append(json.dumps(entry, ensure_ascii=False))
    if commit and lines_modified > 0:
        # Atomic: write to tmp file in same directory, then rename.
        # try/finally ensures an orphaned .tmp doesn't survive a
        # mid-write crash; rename-failure path also cleans up.
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, prefix=path.name + ".",
            suffix=".tmp",
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            tmp_path.write_text("\n".join(new_lines) + "\n")
            tmp_path.replace(path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    return lines_total, lines_modified


def run(*, traj_dir: Path, commit: bool, log_path: Path) -> int:
    log: list[str] = []

    def add(msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        prefix = "[COMMIT] " if commit else "[DRYRUN] "
        line = f"{stamp} {prefix}{msg}"
        log.append(line)
        print(line)

    add(f"traj_dir: {traj_dir}")
    add(f"mode:     {'COMMIT' if commit else 'DRY RUN'}")

    if not traj_dir.exists():
        add("trajectory dir does not exist; nothing to backfill")
        return 0

    files = sorted(traj_dir.glob("*.jsonl"))
    if not files:
        add("no jsonl files found in trajectory dir")
        return 0

    add(f"jsonl files found: {len(files)}")
    total_lines = 0
    total_modified = 0
    for f in files:
        lines, modified = _process_file(f, commit=commit, log=log)
        add(f"  {f.name}: {lines} lines, {modified} modified")
        total_lines += lines
        total_modified += modified

    add(f"summary: {total_modified}/{total_lines} lines modified across "
        f"{len(files)} files")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = log_path.read_text() if log_path.exists() else ""
    header = (
        "\n" + "=" * 70
        + f"\nRun at {datetime.now(timezone.utc).isoformat()}\n"
        + "=" * 70 + "\n"
    )
    log_path.write_text(existing + header + "\n".join(log) + "\n")
    return total_modified


def _default_log_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return REPO / "logs" / f"backfill_trajectory_provenance_{today}.txt"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--commit", action="store_true",
        help="Execute writes. Default is dry-run.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Explicit dry-run flag (the default).",
    )
    p.add_argument(
        "--traj-dir", type=Path, default=DEFAULT_TRAJ_DIR,
        help=f"Trajectory directory (default: {DEFAULT_TRAJ_DIR})",
    )
    p.add_argument(
        "--log-path", type=Path, default=None,
        help="Path to log file (default: logs/backfill_trajectory_*.txt).",
    )
    args = p.parse_args(argv)
    log_path = args.log_path or _default_log_path()
    run(
        traj_dir=args.traj_dir, commit=bool(args.commit),
        log_path=log_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
