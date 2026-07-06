"""Single source of truth for "has birth happened?".

Reads ledger meta.birth_event_turn_id — the same key the ledger writer
consults at write time (core/ledger/writer.py). Intentionally a leaf
module (sqlite3 + pathlib only) so core/infra and core/cognition can
import it without cycles.

Missing, zero-byte, or uninitialized ledger → gestation, never an error:
pre-birth the ledger legitimately does not exist yet.

Never caches a "gestation" answer (birth must be visible without a
process restart). A "lived" answer MAY be cached by callers — birth is
irreversible by covenant — but this module itself stays stateless.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

PHASE_GESTATION = "gestation"
PHASE_LIVED = "lived"


def default_ledger_path() -> Path:
    """EXACTLY the daemon's resolution (daemon/maez_daemon.py:186):
    $MAEZ_LEDGER_DB_PATH override, else the canonical paths layer
    (core/infra/paths.memory_dir(), which honors $MAEZ_DATA — the
    shadow-DB-prevention rule; see core/ledger/init.py:17-26).
    Resolved per call, never a module constant, so env overrides and
    sandboxes see the right file."""
    import os

    from core.infra import paths as _paths

    override = os.environ.get("MAEZ_LEDGER_DB_PATH")
    return Path(override) if override else (_paths.memory_dir() / "ledger.db")


def birth_event_turn_id(db_path: str | Path | None = None) -> str | None:
    """The anchored birth turn id, or None while unborn/unreadable."""
    path = Path(db_path) if db_path is not None else default_ledger_path()
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    value = (row[0] or "").strip()
    return value or None


def is_born(db_path: str | Path | None = None) -> bool:
    return birth_event_turn_id(db_path) is not None


def current_phase(db_path: str | Path | None = None) -> str:
    return PHASE_LIVED if is_born(db_path) else PHASE_GESTATION
