#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Summarize Maez continuity probe JSONL ledgers."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
LEDGER_DIR = _REPO / "logs" / "continuity"


@dataclass(frozen=True)
class DaySummary:
    day: str
    totals: Counter[str]
    by_category: dict[str, Counter[str]]
    by_probe: dict[str, Counter[str]]


def load_rows(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        if not path.exists():
            continue
        ledger_day = _day_from_path(path)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
            if "timestamp" not in row or "probe_id" not in row or "verdict" not in row:
                raise ValueError(f"{path}:{line_no}: missing required continuity ledger fields")
            if ledger_day:
                row["_ledger_day"] = ledger_day
            rows.append(row)
    return rows


def _day_from_path(path: Path) -> str:
    stem = path.stem
    prefix = "continuity_"
    if not stem.startswith(prefix):
        return ""
    return stem.removeprefix(prefix)


def ledger_paths(ledger_dir: Path = LEDGER_DIR, *, days: int = 7) -> list[Path]:
    paths = sorted(ledger_dir.glob("continuity_*.jsonl"))
    if days < 1:
        raise ValueError("days must be >= 1")
    return paths[-days:]


def summarize_rows(rows: list[dict[str, object]]) -> list[DaySummary]:
    days: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        day = str(row.get("_ledger_day") or row["timestamp"])[:10]
        days[day].append(row)

    summaries: list[DaySummary] = []
    for day in sorted(days):
        totals: Counter[str] = Counter()
        by_category: dict[str, Counter[str]] = defaultdict(Counter)
        by_probe: dict[str, Counter[str]] = defaultdict(Counter)
        for row in days[day]:
            verdict = str(row["verdict"])
            category = str(row.get("category", "unknown"))
            probe_id = str(row["probe_id"])
            totals[verdict] += 1
            by_category[category][verdict] += 1
            by_probe[probe_id][verdict] += 1
        summaries.append(
            DaySummary(
                day=day,
                totals=totals,
                by_category=dict(by_category),
                by_probe=dict(by_probe),
            ),
        )
    return summaries


def new_regressions(previous: DaySummary | None, current: DaySummary | None) -> list[str]:
    if previous is None or current is None:
        return []
    regressions: list[str] = []
    for probe_id, counts in sorted(current.by_probe.items()):
        if counts.get("FAIL", 0) <= 0:
            continue
        previous_failed = previous.by_probe.get(probe_id, Counter()).get("FAIL", 0) > 0
        if not previous_failed:
            regressions.append(probe_id)
    return regressions


def render_summary(summaries: list[DaySummary]) -> str:
    if not summaries:
        return "No continuity ledger rows found."

    lines = ["Continuity Ledger Summary", "=" * 28]
    for summary in summaries:
        total = sum(summary.totals.values())
        lines.append(
            f"{summary.day}: PASS={summary.totals.get('PASS', 0)} "
            f"FAIL={summary.totals.get('FAIL', 0)} "
            f"FLAG={summary.totals.get('FLAG', 0)} of {total}"
        )
        for category in sorted(summary.by_category):
            counts = summary.by_category[category]
            category_total = sum(counts.values())
            lines.append(
                f"  {category}: PASS={counts.get('PASS', 0)} "
                f"FAIL={counts.get('FAIL', 0)} "
                f"FLAG={counts.get('FLAG', 0)} of {category_total}"
            )
    regressions = new_regressions(summaries[-2] if len(summaries) >= 2 else None, summaries[-1])
    if regressions:
        lines.append(f"New FAIL regressions since previous day: {', '.join(regressions)}")
    else:
        lines.append("New FAIL regressions since previous day: none")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", type=Path, default=LEDGER_DIR)
    parser.add_argument("--days", type=int, default=7)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = ledger_paths(args.ledger_dir, days=args.days)
    summaries = summarize_rows(load_rows(paths))
    print(render_summary(summaries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
