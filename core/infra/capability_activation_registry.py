# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability activation registry + completion handler (Step 5d).

When a capability implementation has landed and tests pass, the
completion path records the activation here and transitions the
acquisition-queue row to 'completed'. This is the only sanctioned
path from queued → completed; ``AcquisitionQueue.transition`` keeps
working for cancellation / failure but completion goes through
``complete()`` exclusively.

Hard contract — atomicity is load-bearing:

  • Registry write FIRST, queue transition SECOND.
  • Registry write is idempotent on ``queue_id`` so a retry after
    a partial failure (registry succeeded, queue transition crashed)
    inserts no duplicate and finishes the transition.
  • Default behaviour rejects a second 'active' row for the same
    ``capability_id``. Pass ``supersedes=<prior_registry_id>`` to
    flip the prior row to 'superseded' and link the new row.
  • completed_at is the time the registry row was filed.
    activated_at is reserved for the daemon to set when the code
    actually starts running; never set by this handler.

The registry never deletes rows. Status transitions are the only
mutation; the audit trail is permanent.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from core.infra.capability_acquisition_queue import AcquisitionQueue

logger = logging.getLogger(__name__)


_VALID_STATUS: frozenset[str] = frozenset({
    "active", "disabled", "superseded",
})


# ── exceptions ────────────────────────────────────────────────────


class RegistryError(ValueError):
    """Raised on registry-level invariant violations: unknown
    supersedes target, capability_id mismatch on supersession,
    bad status. Subclasses ValueError so existing handlers keep
    working."""


class DuplicateActiveCapabilityError(RegistryError):
    """A second 'active' row for the same capability_id was
    attempted without ``supersedes=``. Lift this by either marking
    the prior row superseded or disabling it first."""


class CompletionError(ValueError):
    """Public completion path failed input validation: unknown
    queue id, status drift, capability_id mismatch, missing commit
    SHA, missing files. Distinct from RegistryError so callers can
    tell apart "your inputs were wrong" from "registry invariant
    broken"."""


# ── registry store ────────────────────────────────────────────────


def _default_registry_path() -> Path:
    """Resolve the canonical registry path under
    ``memory/capability_activation_registry.db``. Falls back to a
    relative path if ``core.paths`` is unavailable (matches the
    queue module's posture)."""
    try:
        from core import paths as _paths
        return (
            _paths.memory_dir() / "capability_activation_registry.db"
        )
    except Exception:
        return Path("memory/capability_activation_registry.db")


class ActivationRegistry:
    """SQLite-backed activation registry. Append-only-ish: rows are
    inserted once; ``status`` is the only mutable field, and only
    via supersession."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS activation_registry (
        id                  TEXT    PRIMARY KEY,
        completed_at        REAL    NOT NULL,
        activated_at        REAL,
        capability_id       TEXT    NOT NULL,
        queue_id            TEXT    NOT NULL UNIQUE,
        proposal_id         TEXT,
        commit_sha          TEXT    NOT NULL,
        implementation_files_json TEXT NOT NULL,
        tests_json          TEXT    NOT NULL,
        status              TEXT    NOT NULL,
        supersedes          TEXT,
        notes               TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_reg_capability
        ON activation_registry(capability_id);
    CREATE INDEX IF NOT EXISTS idx_reg_status
        ON activation_registry(status);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = (
            Path(db_path) if db_path else _default_registry_path()
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(self._SCHEMA)
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    # ── reads ──────────────────────────────────────────────────────

    def get(self, row_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM activation_registry WHERE id = ?",
                (row_id,),
            ).fetchone()
        return _hydrate(row) if row else None

    def get_by_queue_id(self, queue_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM activation_registry WHERE queue_id = ?",
                (queue_id,),
            ).fetchone()
        return _hydrate(row) if row else None

    def list_all(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM activation_registry "
                "ORDER BY completed_at DESC"
            ).fetchall()
        return [_hydrate(r) for r in rows]

    def list_active(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM activation_registry "
                "WHERE status = 'active' ORDER BY completed_at DESC"
            ).fetchall()
        return [_hydrate(r) for r in rows]

    # ── writes ─────────────────────────────────────────────────────

    def record(
        self,
        *,
        capability_id: str,
        queue_id: str,
        proposal_id: str | None,
        commit_sha: str,
        implementation_files: list[str],
        tests: list[str],
        notes: str | None = None,
        supersedes: str | None = None,
    ) -> str:
        """Insert one activation row. Idempotent on ``queue_id`` —
        a second call with the same queue_id returns the existing
        registry row id without inserting a duplicate.

        ``supersedes=None`` (default) rejects a second 'active' row
        for the same capability_id with
        ``DuplicateActiveCapabilityError``. Pass a prior registry id
        to atomically mark it 'superseded' and insert this row as
        the new 'active' record."""
        if not capability_id:
            raise RegistryError("capability_id is required")
        if not queue_id:
            raise RegistryError("queue_id is required")
        if not commit_sha:
            raise RegistryError("commit_sha is required")

        # Idempotency: if a row already exists for this queue_id,
        # return its id. Retry-after-partial-failure path.
        existing = self.get_by_queue_id(queue_id)
        if existing is not None:
            return existing["id"]

        with self._connect() as con:
            if supersedes is not None:
                prior = con.execute(
                    "SELECT * FROM activation_registry WHERE id = ?",
                    (supersedes,),
                ).fetchone()
                if prior is None:
                    raise RegistryError(
                        f"supersedes target {supersedes!r} does not exist"
                    )
                if prior["capability_id"] != capability_id:
                    raise RegistryError(
                        f"supersedes target {supersedes!r} is for "
                        f"capability {prior['capability_id']!r}, not "
                        f"{capability_id!r} — refusing cross-capability "
                        "supersession"
                    )
            else:
                # Default uniqueness gate.
                dup = con.execute(
                    "SELECT id FROM activation_registry "
                    "WHERE capability_id = ? AND status = 'active' "
                    "LIMIT 1",
                    (capability_id,),
                ).fetchone()
                if dup is not None:
                    raise DuplicateActiveCapabilityError(
                        f"capability {capability_id!r} already has an "
                        f"active registry row ({dup['id']}); pass "
                        "supersedes=<prior_id> to replace it"
                    )

            row_id = "act-" + uuid4().hex[:12]
            now = time.time()
            con.execute(
                "INSERT INTO activation_registry ("
                "id, completed_at, activated_at, capability_id, "
                "queue_id, proposal_id, commit_sha, "
                "implementation_files_json, tests_json, status, "
                "supersedes, notes"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row_id, now, None, capability_id,
                    queue_id, proposal_id, commit_sha,
                    json.dumps(list(implementation_files), sort_keys=True),
                    json.dumps(list(tests), sort_keys=True),
                    "active",
                    supersedes,
                    notes,
                ),
            )
            if supersedes is not None:
                con.execute(
                    "UPDATE activation_registry "
                    "SET status = 'superseded' WHERE id = ?",
                    (supersedes,),
                )
            con.commit()
        return row_id


def _hydrate(row: sqlite3.Row) -> dict:
    """Inflate a registry row into a plain dict, parsing the JSON
    blob columns. Hides the storage shape from callers."""
    d = dict(row)
    d["implementation_files"] = json.loads(
        d.pop("implementation_files_json"),
    )
    d["tests"] = json.loads(d.pop("tests_json"))
    return d


# ── completion handler (the public path from queued → completed) ──


def _commit_exists(commit_sha: str, *, repo_root: Path | None = None) -> bool:
    """True iff ``commit_sha`` resolves to a real commit in the repo.
    Uses ``git cat-file -e <sha>`` — the cheapest check git offers.
    Subprocess is allowlist-tested to ensure this remains the only
    shell-out the completion handler performs."""
    if not commit_sha or not isinstance(commit_sha, str):
        return False
    cwd = str(repo_root) if repo_root else None
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", commit_sha],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False
    return proc.returncode == 0


def _maez_repo_root() -> Path:
    """Best-effort resolution of the Maez repo root for ``git
    cat-file`` to run in. Falls back to the current process cwd if
    ``core.paths`` is unavailable (the live-path is always inside
    the repo per spec)."""
    try:
        from core import paths as _paths
        return _paths.home()
    except Exception:
        return Path(os.getcwd())


def complete(
    *,
    queue: "AcquisitionQueue",
    registry: ActivationRegistry,
    queue_id: str,
    capability_id: str,
    commit_sha: str,
    implementation_files: list[str],
    tests: list[str],
    notes: str | None = None,
    supersedes: str | None = None,
    repo_root: Path | None = None,
) -> str:
    """Public completion path. Validates inputs, writes the registry
    row, then transitions the queue row. Idempotent on ``queue_id``
    via the registry's idempotency: retry after a partial failure
    (registry succeeded, queue transition crashed) returns the same
    registry id and finishes the queue transition.

    Validation order is fixed (cheap checks first, subprocess last)
    so a malformed call never reaches ``git cat-file``:

      1. queue row exists
      2. queue row status == 'queued'
      3. capability_id matches the queue row
      4. listed implementation_files exist on disk at HEAD
      5. listed tests exist on disk at HEAD
      6. commit_sha resolves via git cat-file -e

    Then: registry write (FIRST), queue transition (SECOND). Any
    failure between (6) and the queue transition leaves the registry
    row written; a retry is safe.
    """
    row = queue.get(queue_id)
    if row is None:
        raise CompletionError(f"no queue row with id {queue_id!r}")

    # If a registry row already exists for this queue_id (retry
    # path), the cheap revalidation still runs but we tolerate the
    # queue row already being 'completed' — the second transition
    # is a no-op.
    existing_reg = registry.get_by_queue_id(queue_id)

    if (
        row["status"] != "queued"
        and not (existing_reg is not None and row["status"] == "completed")
    ):
        if existing_reg is None:
            raise CompletionError(
                f"queue row {queue_id!r} has status {row['status']!r}; "
                "completion only consumes 'queued' rows"
            )

    if row["capability_id"] != capability_id:
        raise CompletionError(
            f"capability_id param {capability_id!r} does not match "
            f"queue row's {row['capability_id']!r}"
        )

    repo = repo_root if repo_root is not None else _maez_repo_root()

    for rel in implementation_files:
        path = repo / rel
        if not path.is_file():
            raise CompletionError(
                f"implementation file {rel!r} does not exist at HEAD "
                f"under {repo}"
            )
    for rel in tests:
        path = repo / rel
        if not path.is_file():
            raise CompletionError(
                f"test file {rel!r} does not exist at HEAD under {repo}"
            )

    if not _commit_exists(commit_sha, repo_root=repo):
        raise CompletionError(
            f"commit_sha {commit_sha!r} not found via "
            "'git cat-file -e' — refusing to file an activation "
            "anchored on a missing commit"
        )

    # Registry write FIRST. Idempotent on queue_id: retry returns
    # the same row id without inserting a duplicate.
    reg_id = registry.record(
        capability_id=capability_id,
        queue_id=queue_id,
        proposal_id=row.get("proposal_id"),
        commit_sha=commit_sha,
        implementation_files=list(implementation_files),
        tests=list(tests),
        notes=notes,
        supersedes=supersedes,
    )

    # Queue transition SECOND. If this raises, the registry row is
    # safe; a retry will hit the idempotency short-circuit and
    # complete the transition.
    if row["status"] != "completed":
        queue.transition(queue_id, "completed")

    return reg_id


__all__ = [
    "ActivationRegistry",
    "CompletionError",
    "DuplicateActiveCapabilityError",
    "RegistryError",
    "complete",
]
