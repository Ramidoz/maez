"""Fresh-moment receipts v0.

Content-light sidecar receipts for factual Maez-internal moments. This module
is a leaf: it does not import wonderings, wants, salience, dream state,
action engine, soul writers, or private-thought raw readers.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


FRESH_MOMENT_RECEIPTS_VERSION = "fresh_moment_receipts.v0"
FRESH_MOMENT_RECEIPTS_PATH_ENV = "MAEZ_FRESH_MOMENT_RECEIPTS_PATH"
MOMENT_PRIVATE_THOUGHT_LANDED = "private_thought_landed"
FRESH_MOMENT_BOND_ID = "private_owner"


def _default_fresh_moment_receipts_path() -> Path:
    override = os.environ.get(FRESH_MOMENT_RECEIPTS_PATH_ENV)
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir

        return memory_dir() / "fresh_moment_receipts.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "fresh_moment_receipts.db"


def fresh_moment_receipts_db_path() -> Path:
    """Return the configured fresh-moment receipt path without initializing it."""
    return _default_fresh_moment_receipts_path()


class FreshMomentReceipts:
    """Content-light sidecar store for factual fresh-moment receipts."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fresh_moment_receipts (
                    receipt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at      REAL NOT NULL,
                    moment_kind     TEXT NOT NULL,
                    thought_id      INTEGER NOT NULL,
                    source          TEXT NOT NULL,
                    bond_id         TEXT NOT NULL,
                    content_sha256  TEXT NOT NULL,
                    content_len     INTEGER NOT NULL,
                    schema_version  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fmr_kind_created "
                "ON fresh_moment_receipts(moment_kind, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fmr_thought "
                "ON fresh_moment_receipts(thought_id)"
            )
            conn.commit()
        finally:
            conn.close()

    def record_private_thought_landed(
        self,
        *,
        thought_id: int,
        source: str,
        bond_id: str,
        content_sha256: str,
        content_len: int,
        created_at: float | None = None,
    ) -> int:
        if int(thought_id) <= 0:
            raise ValueError("thought_id must be positive")
        source = str(source or "").strip()
        if not source:
            raise ValueError("source must be non-empty")
        bond_id = str(bond_id or "").strip()
        if not bond_id:
            raise ValueError("bond_id must be non-empty")
        content_sha256 = str(content_sha256 or "").strip()
        if not content_sha256:
            raise ValueError("content_sha256 must be non-empty")
        content_len = int(content_len)
        if content_len < 0:
            raise ValueError("content_len must be non-negative")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """INSERT INTO fresh_moment_receipts
                   (created_at, moment_kind, thought_id, source, bond_id,
                    content_sha256, content_len, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    float(time.time() if created_at is None else created_at),
                    MOMENT_PRIVATE_THOUGHT_LANDED,
                    int(thought_id),
                    source,
                    bond_id,
                    content_sha256,
                    content_len,
                    FRESH_MOMENT_RECEIPTS_VERSION,
                ),
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
                "SELECT * FROM fresh_moment_receipts ORDER BY receipt_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def column_names(self) -> list[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM fresh_moment_receipts LIMIT 0")
            return [desc[0] for desc in cursor.description]
        finally:
            conn.close()
