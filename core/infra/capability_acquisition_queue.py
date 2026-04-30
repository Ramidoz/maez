# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability acquisition queue (Step 4b of the Decision-19/20 arc).

Records *intent* — owner approved acquiring capability X on date Y.
Does NOT fetch code, install dependencies, modify files, or run
network calls. Step 5 (later, separate slice) consumes this queue
to actually integrate.

Hard contract:

  • Append-only-ish. Status transitions are allowed
    (queued → cancelled / completed / failed) but rows are NEVER
    deleted. The queue is the audit trail of approved intent.
  • Action handler validates source/path/acquisition match the
    manual entry, refusing stale or tampered cards.
  • Owner-visible output is honest about non-installation:
    "Acquisition intent queued. No code was fetched or installed."

The queue is intentionally a separate store from
``skills/evolution_engine.py`` self-edit candidates. Different
lifecycle: capability acquisition intent vs code-patch proposal.
Conflating them was a deliberate avoid.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


_VALID_STATUS: frozenset[str] = frozenset({
    "queued", "cancelled", "completed", "failed",
})

# An "open" status blocks duplicate enqueues for the same
# capability. Terminal statuses (cancelled / completed / failed)
# don't suppress new attempts — the previous attempt is over.
_OPEN_STATUSES: frozenset[str] = frozenset({"queued"})


_DEFAULT_QUEUE_PATH: Path | None = None


def _default_queue_path() -> Path:
    """Resolve the canonical queue path under
    ``memory/capability_acquisition_queue.db``."""
    global _DEFAULT_QUEUE_PATH
    if _DEFAULT_QUEUE_PATH is None:
        try:
            from core import paths as _paths
            _DEFAULT_QUEUE_PATH = (
                _paths.memory_dir() / "capability_acquisition_queue.db"
            )
        except Exception:
            _DEFAULT_QUEUE_PATH = Path(
                "memory/capability_acquisition_queue.db",
            )
    return _DEFAULT_QUEUE_PATH


# ── store ──────────────────────────────────────────────────────────


class AcquisitionQueue:
    """SQLite-backed queue of acquisition intents. Append-only-ish:
    rows are inserted on enqueue; status is updated via transition;
    no public delete."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS acquisition_queue (
        id              TEXT    PRIMARY KEY,
        created_at      REAL    NOT NULL,
        updated_at      REAL    NOT NULL,
        status          TEXT    NOT NULL,
        capability_id   TEXT    NOT NULL,
        source          TEXT    NOT NULL,
        manual_source_path TEXT NOT NULL,
        acquisition     TEXT    NOT NULL,
        proposal_id     TEXT,
        card_request_id TEXT,
        reason          TEXT,
        plain_english   TEXT,
        payload_json    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_queue_status
        ON acquisition_queue(status);
    CREATE INDEX IF NOT EXISTS idx_queue_cap
        ON acquisition_queue(capability_id);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_queue_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(self._SCHEMA)
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def enqueue(
        self,
        *,
        capability_id: str,
        source: str,
        manual_source_path: str,
        acquisition: str,
        proposal_id: str | None = None,
        card_request_id: str | None = None,
        reason: str | None = None,
        plain_english: str | None = None,
        payload_json: str | None = None,
    ) -> str:
        """Insert one acquisition-intent row. If a row for the same
        ``capability_id`` is already in an open status, returns
        that existing row's id without inserting a duplicate.
        """
        if not capability_id:
            raise ValueError("capability_id is required")
        existing = self._find_open_for(capability_id)
        if existing is not None:
            return existing["id"]
        now = time.time()
        row_id = "acq-" + uuid4().hex[:12]
        with self._connect() as con:
            con.execute(
                "INSERT INTO acquisition_queue "
                "(id, created_at, updated_at, status, capability_id, "
                "source, manual_source_path, acquisition, "
                "proposal_id, card_request_id, reason, plain_english, "
                "payload_json) "
                "VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id, now, now, capability_id, source,
                    manual_source_path, acquisition,
                    proposal_id, card_request_id,
                    reason, plain_english, payload_json,
                ),
            )
            con.commit()
        return row_id

    def get(self, row_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM acquisition_queue WHERE id = ?",
                (row_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM acquisition_queue "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_open(self) -> list[dict]:
        placeholders = ",".join("?" for _ in _OPEN_STATUSES)
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM acquisition_queue "
                f"WHERE status IN ({placeholders}) "
                "ORDER BY created_at DESC",
                tuple(_OPEN_STATUSES),
            ).fetchall()
        return [dict(r) for r in rows]

    def transition(self, row_id: str, status: str) -> None:
        """Move the row to a new status. Rejects unknown statuses
        (audit-trail discipline). Does not delete or unwind history."""
        if status not in _VALID_STATUS:
            raise ValueError(
                f"unknown status {status!r}; "
                f"expected one of {sorted(_VALID_STATUS)}"
            )
        with self._connect() as con:
            con.execute(
                "UPDATE acquisition_queue "
                "SET status = ?, updated_at = ? WHERE id = ?",
                (status, time.time(), row_id),
            )
            con.commit()

    def _find_open_for(self, capability_id: str) -> dict | None:
        placeholders = ",".join("?" for _ in _OPEN_STATUSES)
        with self._connect() as con:
            row = con.execute(
                f"SELECT * FROM acquisition_queue "
                f"WHERE capability_id = ? AND status IN ({placeholders}) "
                "ORDER BY created_at DESC LIMIT 1",
                (capability_id, *_OPEN_STATUSES),
            ).fetchone()
        return dict(row) if row else None


# ── module-level convenience wrapper ──────────────────────────────


def enqueue(queue: AcquisitionQueue, **kwargs: Any) -> str:
    """Module-level wrapper for ``AcquisitionQueue.enqueue``. Used
    by the action handler and tests so the call surface is uniform."""
    return queue.enqueue(**kwargs)


# ── action handler ─────────────────────────────────────────────────


_MANUAL_DIR_NAME = "maez_manual"


def _is_path_inside_manual(path_str: str) -> bool:
    """True iff ``path_str`` resolves to a file under
    ``docs/maez_manual/``. Path-traversal-safe: uses
    ``Path.resolve()`` so ``..`` segments are normalized before
    the containment check."""
    if not path_str:
        return False
    try:
        candidate = Path(path_str).resolve()
    except (OSError, ValueError):
        return False
    # Walk up the candidate's parents looking for a docs/maez_manual
    # ancestor.
    for ancestor in candidate.parents:
        if ancestor.name == _MANUAL_DIR_NAME and ancestor.parent.name == "docs":
            return candidate.is_file()
    return False


def _read_manual_acquisition(manual_source_path: str) -> str | None:
    """Read the ``acquisition`` field from the manual entry's
    front-matter. Returns None if the file isn't a valid manual
    entry."""
    try:
        from core.capability_manual import load_capability
        entry = load_capability(manual_source_path)
        return entry.acquisition
    except Exception as e:
        logger.debug(
            "capability_acquisition_queue: load_capability failed: %s", e,
        )
        return None


def handle_capability_acquire(
    params: dict,
    *,
    queue_path: Path | str | None = None,
) -> str:
    """Action handler for ``capability.acquire``.

    Validates params, writes one queued row, returns the
    owner-visible message. Does NOT fetch, install, or modify
    anything. The output text declares non-installation explicitly
    so the cockpit / approval surface can't accidentally mislead
    the operator.
    """
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")

    capability_id = params.get("capability_id")
    if not capability_id or not isinstance(capability_id, str):
        raise ValueError("capability_id is required")

    source = params.get("source")
    if source != "manual":
        # v1 only knows about the manual. Field-search support is
        # Step 5+ — gating here prevents stale or tampered cards
        # from declaring an unsupported source.
        raise ValueError(
            f"source must be 'manual' in v1; got {source!r}"
        )

    manual_source_path = params.get("manual_source_path")
    if not manual_source_path or not isinstance(manual_source_path, str):
        raise ValueError("manual_source_path is required")
    if not _is_path_inside_manual(manual_source_path):
        raise ValueError(
            f"manual_source_path {manual_source_path!r} is not "
            "under docs/maez_manual/ or doesn't exist"
        )

    acquisition = params.get("acquisition")
    actual = _read_manual_acquisition(manual_source_path)
    if actual is None:
        raise ValueError(
            f"could not read manual entry at {manual_source_path}"
        )
    if acquisition != actual:
        raise ValueError(
            f"acquisition param {acquisition!r} does not match "
            f"manual entry's {actual!r} — possible stale/tampered card"
        )

    queue = AcquisitionQueue(queue_path)
    row_id = queue.enqueue(
        capability_id=capability_id,
        source=source,
        manual_source_path=manual_source_path,
        acquisition=acquisition,
        proposal_id=params.get("proposal_id"),
        card_request_id=params.get("card_request_id"),
        reason=params.get("reason"),
        plain_english=params.get("plain_english"),
        payload_json=json.dumps(
            {k: v for k, v in params.items()
             if k not in {"plain_english"}},  # plain_english stored separately
            sort_keys=True,
        ),
    )
    return (
        f"Acquisition intent queued for {capability_id} "
        f"(row id {row_id}). No code was fetched or installed; "
        "this is a recorded intent only. Step 5 (later) will "
        "consume the queue for actual integration, gated by "
        "additional consent at that time."
    )


__all__ = [
    "AcquisitionQueue",
    "enqueue",
    "handle_capability_acquire",
]
