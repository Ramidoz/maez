# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Bounded ledger lookback by turn_kind.

Slice 3 proper foundation. The evidence-envelope builder uses
:func:`recent_turns_by_kind` to populate the ``self_history`` slot
declared by :mod:`core.ledger.envelope_schema` (slice 3.0b). This
module is intentionally minimal: a thin SQL wrapper over the
``idx_turns_kind_ts`` index, returning raw turn rows. Mapping rows
into ``SelfHistoryRef`` shape (truncating ``raw_text`` to
``utterance_summary`` ≤ 200 chars) is the envelope builder's
responsibility, not this module's.

Read-only by construction: opens the DB with ``mode=ro`` so a live
writer is not contended.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

__all__ = ["recent_turns_by_kind"]


def recent_turns_by_kind(
    db_path: str,
    *,
    kinds: Iterable[str],
    limit: int,
    tenant_id: str = "owner",
    recall_gestation: str = "user",
) -> list[dict]:
    """Return up to ``limit`` most-recent turn rows whose ``turn_kind``
    is in ``kinds``, newest-first, scoped to ``tenant_id``.

    Each returned dict carries ``turn_id``, ``timestamp``,
    ``turn_kind``, ``raw_text``, ``lifecycle_stage`` — the columns
    required to build a ``SelfHistoryRef`` plus the gestation-aware
    label hook.

    ``recall_gestation`` (Gestation Boundary slice, 2026-05-08, per
    docs/SLICE_GESTATION_BOUNDARY_MEMO.md §4):

      * ``"user"`` (default) — user-facing recall: rows are sorted
        with ``lifecycle_stage='lived'`` first, then ``'gestation'``,
        and recency within each tier. Implements the memo's
        "0.15x downweight" as a two-tier ranking — gestation rows
        only surface when not enough lived rows fill the limit.
      * ``"full"`` — dev/operator path: pure recency-only ordering,
        gestation and lived interleave by timestamp. Used when an
        explicit caller (debug query, build-history question) wants
        the full diary.

    Edge cases:
      - ``kinds`` empty → returns ``[]`` (no SQL run).
      - ``limit == 0`` → returns ``[]`` (no SQL run).
      - ``limit < 0`` → raises ``ValueError``.
      - ``recall_gestation`` not in ``("user", "full")`` → raises
        ``ValueError``.
    """
    if limit < 0:
        raise ValueError(f"limit must be >= 0, got {limit}")
    if recall_gestation not in ("user", "full"):
        raise ValueError(
            f"recall_gestation must be 'user' or 'full', "
            f"got {recall_gestation!r}"
        )
    kinds_list = list(kinds)
    if not kinds_list or limit == 0:
        return []

    placeholders = ",".join("?" * len(kinds_list))
    if recall_gestation == "full":
        # Pure recency. Gestation and lived interleave by timestamp.
        order_clause = "ORDER BY timestamp DESC"
    else:
        # Two-tier: lived first, gestation second, recency within tier.
        # Implements the memo §4 "0.15x downweight" as priority sort:
        # gestation rows only surface when lived rows don't fill limit.
        order_clause = (
            "ORDER BY "
            "CASE WHEN lifecycle_stage = 'lived' THEN 1 ELSE 2 END ASC, "
            "timestamp DESC"
        )

    sql = (
        "SELECT turn_id, timestamp, turn_kind, raw_text, lifecycle_stage "
        "FROM turns "
        f"WHERE tenant_id = ? AND turn_kind IN ({placeholders}) "
        f"{order_clause} "
        "LIMIT ?"
    )
    params = (tenant_id, *kinds_list, limit)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
