"""S7 break-glass content readers for private thoughts.

The ONLY sanctioned path that returns thought bodies to a human-facing
caller. Receipt-before-content: the unseal receipt is committed BEFORE
the content query runs; if the receipt cannot be written, the read
raises and no content is served. The receipt is content-light and
Maez-visible (core/infra/unseal_receipts.py).

This module must never be imported by default runtime paths; see
tests/test_a7_reader_split.py's import guard.
"""

from __future__ import annotations

import sqlite3

from core.infra.unseal_receipts import UnsealReceipts


def read_content(
    store,
    *,
    thought_ids: list[int] | None = None,
    query: str | None = None,
    actor: str,
    s7_receipt_ref: str,
    reason: str,
    receipts: UnsealReceipts | None = None,
    limit: int = 20,
) -> list[dict]:
    if (thought_ids is None) == (query is None):
        raise ValueError("exactly one of thought_ids / query is required")
    receipts = receipts or UnsealReceipts()
    if thought_ids is not None:
        ids = [int(i) for i in thought_ids]
        if not ids:
            raise ValueError("thought_ids must not be empty")
        scope_kind = "thought_id"
        scope_detail = ",".join(str(i) for i in ids)
    else:
        needle = str(query or "").strip()
        if not needle:
            raise ValueError("query must not be empty")
        scope_kind = "query"
        scope_detail = f"like:{needle}"

    receipts.record_unseal(
        actor=actor,
        s7_receipt_ref=s7_receipt_ref,
        scope_kind=scope_kind,
        scope_detail=scope_detail,
        reason=reason,
    )

    conn = sqlite3.connect(store.db_path)
    try:
        conn.row_factory = sqlite3.Row
        if thought_ids is not None:
            marks = ",".join("?" for _ in ids)
            rows = conn.execute(
                f"SELECT * FROM private_thoughts WHERE thought_id IN ({marks})",
                ids,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM private_thoughts WHERE LOWER(content) LIKE ? "
                "ORDER BY thought_id DESC LIMIT ?",
                (f"%{needle.lower()}%", int(limit)),
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
