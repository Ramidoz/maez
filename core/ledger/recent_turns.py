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

from core.cognition.audit_policy import TraceAuditPolicy

__all__ = ["recent_turns_by_kind"]


def recent_turns_by_kind(
    db_path: str,
    *,
    kinds: Iterable[str],
    limit: int,
    tenant_id: str = "owner",
    recall_gestation: str = "user",
    include_trace_labeled: bool = False,
    audit_path: str = "recent_turns_by_kind",
    would_have_consumed_surface: str = "self_history",
) -> list[dict]:
    """Return up to ``limit`` most-recent turn rows whose ``turn_kind``
    is in ``kinds``, newest-first, scoped to ``tenant_id``.

    Each returned dict carries ``turn_id``, ``timestamp``,
    ``turn_kind``, ``raw_text``, ``lifecycle_stage``, S1 taint/privacy
    labels, and ``chain_position`` — the columns required to build a
    ``SelfHistoryRef`` plus the gestation-aware label hook.

    ``recall_gestation`` (Gestation Boundary slice, 2026-05-08, per
    docs/slices/legacy/gestation-boundary.md §4):

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
        raise ValueError(f"recall_gestation must be 'user' or 'full', got {recall_gestation!r}")
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
            "ORDER BY CASE WHEN lifecycle_stage = 'lived' THEN 1 ELSE 2 END ASC, timestamp DESC"
        )

    select_cols = (
        "turn_id, timestamp, turn_kind, raw_text, lifecycle_stage, "
        "taint_labels_json, privacy_access, chain_position, "
        "audit_trace_label, audit_trace_value_schema, "
        "audit_trace_metadata_shape"
    )
    base_where = f"WHERE tenant_id = ? AND turn_kind IN ({placeholders}) "
    sql = f"SELECT {select_cols} FROM turns {base_where}{order_clause} LIMIT ?"
    params = (tenant_id, *kinds_list, limit)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        if include_trace_labeled:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

        # Log rows that would have been consumed by the unfiltered
        # top-window, then perform the actual read with the refusal
        # predicate at SQL level so untraced older rows can backfill.
        candidate_rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        TraceAuditPolicy.current().apply(
            candidate_rows,
            audit_path=audit_path,
            would_have_consumed_surface=would_have_consumed_surface,
        )

        filtered_sql = (
            f"SELECT {select_cols} "
            "FROM turns "
            f"{base_where}"
            "AND audit_trace_label IS NULL "
            f"{order_clause} "
            "LIMIT ?"
        )
        cur = conn.execute(filtered_sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
