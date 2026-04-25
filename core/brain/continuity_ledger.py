# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Compact continuity probe ledger summaries for Maez's self-continuity."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from core.infra.paths import logs_dir

LEDGER_DIR = logs_dir() / "continuity"


def ledger_path_for_date(date_str: str, *, ledger_dir: Path = LEDGER_DIR) -> Path:
    return ledger_dir / f"continuity_{date_str}.jsonl"


def load_day_rows(date_str: str, *, ledger_dir: Path = LEDGER_DIR) -> list[dict[str, object]]:
    path = ledger_path_for_date(date_str, ledger_dir=ledger_dir)
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid continuity ledger row: {exc}") from exc
        rows.append(row)
    return rows


def summarize_day_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No continuity probes were recorded today."
    totals: Counter[str] = Counter(str(row.get("verdict", "UNKNOWN")) for row in rows)
    categories = sorted({str(row.get("category", "unknown")) for row in rows})
    failed = sorted({
        str(row.get("probe_id"))
        for row in rows
        if str(row.get("verdict")) == "FAIL" and row.get("probe_id")
    })
    flagged = sorted({
        str(row.get("probe_id"))
        for row in rows
        if str(row.get("verdict")) == "FLAG" and row.get("probe_id")
    })
    base = (
        f"Continuity probes today: PASS={totals.get('PASS', 0)}, "
        f"FAIL={totals.get('FAIL', 0)}, FLAG={totals.get('FLAG', 0)} "
        f"of {len(rows)} across {', '.join(categories)}."
    )
    if failed:
        return f"{base} Failed probes: {', '.join(failed[:8])}."
    if flagged:
        return f"{base} Human-review flags: {', '.join(flagged[:8])}."
    return f"{base} No objective regressions recorded."


def summarize_day(date_str: str, *, ledger_dir: Path = LEDGER_DIR) -> str:
    return summarize_day_rows(load_day_rows(date_str, ledger_dir=ledger_dir))
