# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Bounded read-only ledger span reader.

S2 of the consolidation spine needs a citation substrate that reads by
``chain_position`` only, freezes a committed high-water mark, verifies the
ledger chain, materializes rows, and releases SQLite before caller work.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from core.ledger import chain

__all__ = [
    "SpanReadError",
    "SpanChainVerificationError",
    "SpanReadResult",
    "read_span",
]


class SpanReadError(RuntimeError):
    """Typed refusal for span-reader failures."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class SpanChainVerificationError(SpanReadError):
    """Typed refusal when the frozen ledger prefix fails chain verification."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        after_chain_position: int,
        high_water: int,
        violations: list[dict],
    ) -> None:
        super().__init__(message, reason=reason)
        self.after_chain_position = after_chain_position
        self.high_water = high_water
        self.violations = violations


@dataclass(frozen=True)
class SpanReadResult:
    """Materialized rows for ``(after_chain_position, high_water]``."""

    after_chain_position: int
    high_water: int
    rows: list[dict]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def _open_readonly(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise SpanReadError(
            f"ledger database does not exist: {path}",
            reason="ledger_missing",
        )
    uri_path = quote(str(path.resolve()), safe="/")
    try:
        conn = sqlite3.connect(
            f"file:{uri_path}?mode=ro",
            uri=True,
            isolation_level=None,
        )
    except sqlite3.Error as exc:
        raise SpanReadError(
            f"cannot open ledger read-only: {exc}",
            reason="ledger_open_failed",
        ) from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _fetch_high_water(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT MAX(chain_position) AS high_water FROM turns"
    ).fetchone()
    if row is None or row["high_water"] is None:
        return -1
    return int(row["high_water"])


def _load_turns_through_high_water(
    conn: sqlite3.Connection,
    high_water: int,
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM turns WHERE chain_position <= ?",
        (high_water,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _fetch_head_hash(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT value FROM meta WHERE key='last_chain_hash'"
    ).fetchone()
    if row is None:
        return None
    return str(row["value"])


def _violation(
    *,
    reason: str,
    expected: str = "",
    actual: str = "",
    turn_id: str = "",
    row_index: int = -1,
) -> dict:
    return {
        "row_index": row_index,
        "turn_id": turn_id,
        "reason": reason,
        "expected": expected,
        "actual": actual,
    }


def _walk_chain(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return rows in chain order plus structural violations."""
    if not rows:
        return [], []

    by_prev: dict[object, list[dict]] = {}
    for row in rows:
        by_prev.setdefault(row["prev_chain_hash"], []).append(row)

    genesis_candidates = by_prev.get(None, [])
    if len(genesis_candidates) == 0:
        return [], [
            _violation(
                reason="chain_no_genesis",
                expected="one genesis row",
            )
        ]
    if len(genesis_candidates) > 1:
        return [], [
            _violation(
                reason="chain_multiple_genesis",
                expected="one genesis row",
                actual=str(len(genesis_candidates)),
            )
        ]

    ordered: list[dict] = []
    seen_turn_ids: set[object] = set()
    current = genesis_candidates[0]

    while True:
        turn_id = current.get("turn_id")
        if turn_id in seen_turn_ids:
            return ordered, [
                _violation(
                    reason="chain_cycle",
                    turn_id=str(turn_id),
                    actual=str(turn_id),
                )
            ]
        seen_turn_ids.add(turn_id)
        ordered.append(current)

        successors = by_prev.get(current["chain_hash"], [])
        if len(successors) == 0:
            break
        if len(successors) > 1:
            return ordered, [
                _violation(
                    reason="chain_fork",
                    turn_id=str(turn_id),
                    expected="one successor",
                    actual=str(len(successors)),
                )
            ]
        current = successors[0]

    if len(ordered) != len(rows):
        return ordered, [
            _violation(
                reason="chain_unreached_rows",
                expected=str(len(rows)),
                actual=str(len(ordered)),
            )
        ]

    return ordered, []


def _head_pointer_violation(
    head_hash: str | None,
    ordered_rows: list[dict],
) -> dict | None:
    if head_hash is None:
        return {
            "reason": "missing-head-pointer",
            "expected": "<meta.last_chain_hash row>",
            "actual": "(absent)",
        }
    if not ordered_rows:
        return None
    actual_head = ordered_rows[-1].get("chain_hash", "")
    if head_hash != actual_head:
        return {
            "reason": "head-pointer-mismatch",
            "expected": head_hash,
            "actual": actual_head if isinstance(actual_head, str) else "",
        }
    return None


def _validate_cursor(after_chain_position: int) -> int:
    if (
        isinstance(after_chain_position, bool)
        or not isinstance(after_chain_position, int)
    ):
        raise SpanReadError(
            "after_chain_position must be an integer chain_position cursor",
            reason="invalid_cursor",
        )
    if after_chain_position < -1:
        raise SpanReadError(
            "after_chain_position must be -1 or greater",
            reason="invalid_cursor",
        )
    return after_chain_position


def read_span(
    db_path: str | Path,
    *,
    after_chain_position: int,
) -> SpanReadResult:
    """Read ``(after_chain_position, high_water]`` in chain order.

    The connection is opened read-only, the read snapshot is explicitly frozen
    before ``high_water`` is observed, rows are materialized as plain dicts,
    and the connection is closed before the result is returned.
    """
    after = _validate_cursor(after_chain_position)
    conn = _open_readonly(db_path)
    try:
        try:
            conn.execute("BEGIN")
            high_water = _fetch_high_water(conn)
            prefix_rows = _load_turns_through_high_water(conn, high_water)
            head_hash = _fetch_head_hash(conn)
            conn.execute("COMMIT")
        except SpanReadError:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise SpanReadError(
                f"sqlite error while reading ledger span: {exc}",
                reason="sqlite_read_error",
            ) from exc
    finally:
        conn.close()

    ordered_rows, violations = _walk_chain(prefix_rows)
    if not violations:
        violations = chain.verify_chain(ordered_rows)
        head_violation = _head_pointer_violation(head_hash, ordered_rows)
        if head_violation is not None:
            violations = [*violations, head_violation]
    if violations:
        raise SpanChainVerificationError(
            "ledger span chain verification failed",
            reason="chain_verification_failed",
            after_chain_position=after,
            high_water=high_water,
            violations=violations,
        )
    span_rows = [
        dict(row)
        for row in ordered_rows
        if after < row.get("chain_position", -1) <= high_water
    ]

    return SpanReadResult(
        after_chain_position=after,
        high_water=high_water,
        rows=span_rows,
    )
