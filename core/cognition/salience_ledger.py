"""Slice C / C2 - private-loop-only salience ledger.

A notebook of correlation, not a judge. Outcomes are derived only from the idle
loop's own per-pulse signals; `unmoved` is neutral, never failure.
`evolved_earlier_wondering` is deferred to C2.1 after real thoughts accrue.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

LEDGER_VERSION = "salience_ledger.v0"
SALIENCE_LEDGER_PATH_ENV = "MAEZ_SALIENCE_LEDGER_PATH"


def _default_salience_ledger_path() -> Path:
    override = os.environ.get(SALIENCE_LEDGER_PATH_ENV)
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir

        return memory_dir() / "salience_ledger.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "salience_ledger.db"


def salience_ledger_db_path() -> Path:
    """Return the configured C2 salience ledger path without initializing the store."""
    return _default_salience_ledger_path()

_OUTCOME_INPUT_KEYS = ("note_chars", "stored", "skip_reason")


def _pulse_signal(result: dict | None) -> dict:
    r = result or {}
    return {
        "note_chars": int(r.get("note_chars") or 0),
        "stored": bool(r.get("stored")),
        "skip_reason": str(r.get("skip_reason") or ""),
    }


def derive_outcome(window_results: list[dict] | None) -> dict:
    """Resolve the idle loop's outcome over [N, N+1]. Neutral by default."""
    signals = [_pulse_signal(r) for r in (window_results or [])]
    thought_formed = any(s["note_chars"] > 0 for s in signals)
    non_duplicate_stored = any(s["stored"] for s in signals)
    duplicate = any(s["skip_reason"] == "duplicate_recent_output" for s in signals)
    return {
        "thought_formed": thought_formed,
        "non_duplicate_stored": non_duplicate_stored,
        "repetition_signal": "duplicate" if duplicate else "not_applicable",
        "unmoved": not thought_formed and not non_duplicate_stored,
    }


class SalienceLedger:
    """Content-light store for proposal-bound idle-loop outcomes."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS salience_ledger (
                    row_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    pulse_id             TEXT NOT NULL,
                    strategy             TEXT NOT NULL,
                    arm                  TEXT NOT NULL DEFAULT 'proposed',
                    fact_key             TEXT NOT NULL,
                    change_kind          TEXT NOT NULL,
                    proposal_hash        TEXT NOT NULL,
                    thought_formed       INTEGER NOT NULL,
                    non_duplicate_stored INTEGER NOT NULL,
                    repetition_signal    TEXT NOT NULL,
                    unmoved              INTEGER NOT NULL,
                    schema_version       TEXT NOT NULL
                )
                """
            )
            cols = [
                row[1]
                for row in conn.execute("PRAGMA table_info(salience_ledger)").fetchall()
            ]
            if "arm" not in cols:
                conn.execute(
                    "ALTER TABLE salience_ledger "
                    "ADD COLUMN arm TEXT NOT NULL DEFAULT 'proposed'"
                )
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        *,
        pulse_id: str,
        strategy: str,
        arm: str,
        fact_key: str,
        change_kind: str,
        proposal_hash: str,
        outcome: dict,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO salience_ledger
                   (pulse_id, strategy, arm, fact_key, change_kind, proposal_hash,
                    thought_formed, non_duplicate_stored, repetition_signal,
                    unmoved, schema_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(pulse_id),
                    str(strategy),
                    str(arm),
                    str(fact_key),
                    str(change_kind),
                    str(proposal_hash),
                    int(bool(outcome["thought_formed"])),
                    int(bool(outcome["non_duplicate_stored"])),
                    str(outcome["repetition_signal"]),
                    int(bool(outcome["unmoved"])),
                    LEDGER_VERSION,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, limit: int = 20) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM salience_ledger ORDER BY row_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def column_names(self) -> list[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM salience_ledger LIMIT 0")
            return [desc[0] for desc in cursor.description]
        finally:
            conn.close()
