from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "memory" / "gestation_claims.db"

CLAIM_KINDS = frozenset({"fact", "interpretation"})
TYPES = frozenset({"milestone", "decision", "scar", "correction", "no_go"})
CONFIDENCES = frozenset({"witnessed", "documented", "inferred"})
OBSERVED_BY = frozenset({"owner", "codex", "claude", "witness"})
SOURCE_KINDS = frozenset({"doc", "commit", "ledger_row", "witness_note"})
STRUCTURAL_SOURCE_KINDS = frozenset({"doc", "commit", "ledger_row"})

MAX_CLAIM_CHARS = 500
MAX_WITNESS_NOTE_CHARS = 500
MAX_EXCERPT_CHARS = 2000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gestation_claims (
    claim_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    REAL    NOT NULL,
    claim_text    TEXT    NOT NULL,
    claim_kind    TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    confidence    TEXT    NOT NULL,
    scar          INTEGER NOT NULL,
    sources_json  TEXT    NOT NULL,
    observed_by   TEXT    NOT NULL,
    metadata_json TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS gestation_claim_supersessions (
    supersession_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    old_claim_id         INTEGER NOT NULL,
    replacement_claim_id INTEGER NOT NULL,
    created_at           REAL    NOT NULL
);
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_update
    BEFORE UPDATE ON gestation_claims
BEGIN
    SELECT RAISE(ABORT, 'gestation_claims is append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_delete
    BEFORE DELETE ON gestation_claims
BEGIN
    SELECT RAISE(ABORT, 'gestation_claims is append-only: DELETE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_update
    BEFORE UPDATE ON gestation_claim_supersessions
BEGIN
    SELECT RAISE(ABORT, 'supersessions is append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_delete
    BEFORE DELETE ON gestation_claim_supersessions
BEGIN
    SELECT RAISE(ABORT, 'supersessions is append-only: DELETE forbidden');
END;
CREATE INDEX IF NOT EXISTS idx_gestation_supersedes
    ON gestation_claim_supersessions(old_claim_id);
"""


@dataclass(frozen=True)
class GestationClaim:
    claim_id: int
    created_at: float
    claim_text: str
    claim_kind: str
    type: str
    confidence: str
    scar: bool
    sources: tuple[dict[str, Any], ...]
    observed_by: str
    metadata: dict[str, Any]


class GestationMemory:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
