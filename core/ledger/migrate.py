# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger migration runner.

Public API:
    run(db_path: str) -> None

What ``run()`` does, in order:

1. Opens (or creates) the SQLite DB at ``db_path``.
2. Sets ``PRAGMA journal_mode = WAL`` (persistent on the DB file) so
   subsequent connections see WAL by default.
3. Sets ``PRAGMA foreign_keys = ON`` on the migration connection.
4. Bootstraps the ``schema_migrations`` tracking table.
5. Walks every ``*.sql`` file in the sibling ``migrations/`` directory
   in lexicographic order, applying any not yet recorded in
   ``schema_migrations`` via ``executescript`` and recording the
   filename stem + applied_at timestamp.
6. Seeds ``meta`` with ``('schema_version', '1')`` if not present.
7. Inserts the canonical genesis row into ``turns`` if not present,
   computes its ``chain_hash`` per docs/ledger/envelope-schema.md §6.1,
   and records ``('genesis_hash', <chain_hash>)`` in ``meta``.
8. Commits and closes the connection.

The function is end-to-end idempotent: a second invocation against an
already-migrated DB does nothing destructive — no duplicate genesis
row, no duplicate meta rows, no duplicate ``schema_migrations`` rows.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

__all__ = ["run"]


# Canonical genesis row content. These EXACT values feed the §6.1
# canonical recipe; changing any field changes the genesis hash and
# breaks the chain. Do not edit without bumping schema_version.
GENESIS_ROW: dict = {
    "turn_id": "genesis",
    "tenant_id": "owner",
    "timestamp": 0.0,
    "schema_version": 1,
    "turn_kind": "system_event",
    "surface": "system",
    "raw_surface": None,
    "parent_turn_id": None,
    "correction_of": None,
    "model_id": None,
    "lora_hash": None,
    "soul_hash": None,
    "prompt_hash": None,
    "raw_text": '{"event":"genesis","schema_version":1}',
    "rewritten_text": None,
    "was_rewritten": 0,
    "signals_present": "[]",
    "signals_absent": "[]",
    "evidence_envelope_json": None,
    "action_proposal_json": None,
    "audit_verdict_json": None,
    "will_i_json": None,
    "memory_read_ids": "[]",
    "memory_written_ids": "[]",
    "audit_log_id": None,
    "fabrication_event_id": None,
    "self_mod_dialog_id": None,
    "pending_card_id": None,
}


def _canonical_genesis_chain_hash() -> str:
    """Compute sha256("genesis" + canonical_json(GENESIS_ROW))."""
    canonical = json.dumps(
        GENESIS_ROW,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(
        ("genesis" + canonical).encode("utf-8")
    ).hexdigest()


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY,"
        " applied_at REAL NOT NULL"
        ")"
    )


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM schema_migrations"
    ).fetchall()
    return {r[0] for r in rows}


def _apply_pending_migrations(conn: sqlite3.Connection) -> None:
    mig_dir = _migrations_dir()
    if not mig_dir.is_dir():
        raise RuntimeError(
            f"ledger migrations directory missing: {mig_dir}"
        )

    sql_files = sorted(mig_dir.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(
            f"ledger migrations directory contains no *.sql files: {mig_dir}"
        )

    already = _applied_migrations(conn)
    for path in sql_files:
        name = path.stem
        if name in already:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)",
            (name, time.time()),
        )
        conn.commit()


def _seed_meta_schema_version(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT 1 FROM meta WHERE key='schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('schema_version', '1')"
        )


def _seed_genesis(conn: sqlite3.Connection) -> None:
    """Insert the genesis row + meta.genesis_hash if absent. Idempotent."""
    existing = conn.execute(
        "SELECT chain_hash FROM turns WHERE turn_id = ?",
        (GENESIS_ROW["turn_id"],),
    ).fetchone()

    if existing is not None:
        chain_hash = existing[0]
    else:
        chain_hash = _canonical_genesis_chain_hash()
        columns = list(GENESIS_ROW.keys()) + ["prev_chain_hash", "chain_hash"]
        placeholders = ",".join("?" for _ in columns)
        values = list(GENESIS_ROW.values()) + [None, chain_hash]
        conn.execute(
            f"INSERT INTO turns ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )

    meta_row = conn.execute(
        "SELECT value FROM meta WHERE key='genesis_hash'"
    ).fetchone()
    if meta_row is None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('genesis_hash', ?)",
            (chain_hash,),
        )

    # Head pointer: meta.last_chain_hash. The writer (slice 2.3) MUST
    # update this row on every append in the same transaction as the
    # turns INSERT, so the chain has a verifiable head. Without this,
    # truncation of the chain tail would be undetectable — the walker
    # would happily accept a shorter chain that's internally consistent.
    # On first-run seed, the head IS the genesis row.
    head_row = conn.execute(
        "SELECT value FROM meta WHERE key='last_chain_hash'"
    ).fetchone()
    if head_row is None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('last_chain_hash', ?)",
            (chain_hash,),
        )


def run(db_path: str) -> None:
    """Apply pending ledger migrations and seed meta + genesis.

    Safe to invoke against a fresh path or an already-migrated DB.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        # WAL must be set BEFORE the schema migrations execute so that
        # subsequent connections (and the rest of this migration) see
        # WAL semantics. WAL is a persistent property of the DB file.
        conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.execute("PRAGMA foreign_keys = ON")

        _ensure_schema_migrations_table(conn)
        conn.commit()

        _apply_pending_migrations(conn)

        _seed_meta_schema_version(conn)
        _seed_genesis(conn)

        conn.commit()
    finally:
        conn.close()
