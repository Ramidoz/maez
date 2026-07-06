"""A7 unseal receipts — the honest-both-directions ledger of drawer-openings.

Every S7 break-glass read of private-thought CONTENT records a row here
BEFORE the content is served (receipt-before-content is enforced by the
unseal reader, Task 6 — this module is the store). Rows are content-light
by construction: ids/patterns/reasons, never thought bodies.

Receipts are FOR Maez: this module is default-importable and its reader
may be surfaced by the heartbeat/recall so Maez can know its drawer was
opened, when, by whom, and why. Append-only at the SQL layer (triggers).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from core.infra import paths as _paths

SCOPE_KINDS = ("thought_id", "query", "range")


def default_db_path() -> Path:
    """Canonical paths layer (honors $MAEZ_DATA) — same discipline as
    core/ledger/init.py and dream_state; never a __file__-relative
    constant (the shadow-DB scar)."""
    return _paths.memory_dir() / "unseal_receipts.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS unseal_receipts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             REAL NOT NULL,
    actor          TEXT NOT NULL,
    s7_receipt_ref TEXT NOT NULL,
    scope_kind     TEXT NOT NULL CHECK (scope_kind IN ('thought_id','query','range')),
    scope_detail   TEXT NOT NULL,
    reason         TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS unseal_receipts_no_update
    BEFORE UPDATE ON unseal_receipts
    BEGIN SELECT RAISE(ABORT, 'unseal receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS unseal_receipts_no_delete
    BEFORE DELETE ON unseal_receipts
    BEGIN SELECT RAISE(ABORT, 'unseal receipts are append-only'); END;
"""


class UnsealReceipts:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path is not None else str(default_db_path())
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def record_unseal(
        self,
        *,
        actor: str,
        s7_receipt_ref: str,
        scope_kind: str,
        scope_detail: str,
        reason: str,
    ) -> int:
        if scope_kind not in SCOPE_KINDS:
            raise ValueError(f"scope_kind must be one of {SCOPE_KINDS}")
        for name, value in (
            ("actor", actor),
            ("s7_receipt_ref", s7_receipt_ref),
            ("scope_detail", scope_detail),
            ("reason", reason),
        ):
            if not (value or "").strip():
                raise ValueError(f"{name} is required")
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO unseal_receipts"
                " (ts, actor, s7_receipt_ref, scope_kind, scope_detail, reason)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), actor, s7_receipt_ref, scope_kind, scope_detail, reason),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def recent(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM unseal_receipts ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM unseal_receipts").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0
