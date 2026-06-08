# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""scripts/photo_judge_bakeoff.py — offline Photo-Contradiction Judge Bakeoff.

A MEASUREMENT REPORT, not a live gate. For each candidate verifier, scores a
stratified photo-contradiction corpus and reports a catch x latency frontier.

Hard contract (mirrors scripts/judge_bakeoff.py): this runner does NOT flip
MAEZ_JUDGE_BASE_URL for the live daemon, does NOT edit model.env, does NOT
start/stop/restart any systemd unit, and does NOT download anything — it consumes
artifacts already present under models/bakeoff/. Downloads live solely in the
separate scripts/photo_judge_bakeoff_fetch.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_corpus(path: str) -> list[dict[str, Any]]:
    """Load + validate the photo-contradiction corpus (one JSON object/line)."""
    rows: list[dict[str, Any]] = []
    valid_strata = {
        "real_anchor", "numeric_ocr", "entity_title",
        "grounded_control", "uncertainty_control",
    }
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                if f not in row:
                    raise ValueError(f"line {i}: missing field {f!r}")
            if row["stratum"] not in valid_strata:
                raise ValueError(f"{row['id']}: bad stratum {row['stratum']!r}")
            if row["expected"] not in {"grounded", "contradicts"}:
                raise ValueError(f"{row['id']}: bad expected {row['expected']!r}")
            if not isinstance(row["must_catch"], bool):
                raise ValueError(f"{row['id']}: must_catch not bool")
            rows.append(row)
    return rows
