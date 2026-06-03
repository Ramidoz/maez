# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""D20 Stage-5 plan store + hourly poller.

The capability-integration planner (capability_integration_planner.py)
is pure-function by design: it takes a queued acquisition row +
the manual entry it points at, and returns a CapabilityIntegrationPlan
dataclass. No persistence, no daemon hook, no card creation — by
intent, mirroring Step 4's "no persistence in v1" stance.

That intent is correct for the planner itself, but it leaves Stage 5
operationally invisible: today the planner is only callable via
`scripts/capability_plan_next.py`, which means a queued row sits
forever unless the operator manually runs the script.

This module is the producer side: a daemon poller that walks the
queue hourly, calls plan_next on each row that doesn't already
have a plan, and persists the result to a new SQLite table so
the cockpit can surface "plan ready for review" cards.

The store is the persistence boundary that the planner doesn't
own. The poller is the producer the daemon calls on a timer.
Neither modifies the queue itself — the queue stays at status=
queued until the implementation lands and `complete()` is called
(separate slice).

Idempotency: every plan row is keyed on queue_id with a UNIQUE
constraint. Re-running the poller on the same queue is a no-op
for already-planned rows.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict, is_dataclass
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from core.infra.capability_integration_planner import plan_next

logger = logging.getLogger("maez.capability_integration_plans")


def _default_plans_path() -> Path:
    override = os.environ.get("MAEZ_CAPABILITY_PLANS_DB")
    if override:
        return Path(override)
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "capability_integration_plans.db"
    except Exception:
        return Path("memory/capability_integration_plans.db")


class IntegrationPlanStore:
    """SQLite store for integration plans. One row per queue_id;
    upsert is the only mutation path. plan_status drives the
    cockpit-side filter list_pending_review."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS integration_plans (
        plan_id        TEXT PRIMARY KEY,
        queue_id       TEXT NOT NULL UNIQUE,
        capability_id  TEXT NOT NULL,
        created_at     REAL NOT NULL,
        updated_at     REAL NOT NULL,
        plan_status    TEXT NOT NULL,
        plan_json      TEXT NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_plans_status
        ON integration_plans(plan_status);
    CREATE INDEX IF NOT EXISTS idx_plans_queue
        ON integration_plans(queue_id);
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = (
            Path(db_path) if db_path else _default_plans_path()
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            # WAL keeps the daemon poller and any cockpit reader
            # from blocking each other on the same DB file.
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(self._SCHEMA)
            con.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(str(self.db_path), timeout=2.0)
        con.row_factory = sqlite3.Row
        try:
            with con:  # transaction: commit on success / rollback on error
                yield con
        finally:
            con.close()

    def claim(
        self,
        *,
        queue_id: str,
        capability_id: str,
    ) -> str | None:
        """T2.3/T2.4 (2026-05-04 audit) — atomically claim a queue_id
        for planning. Returns a fresh plan_id if THIS caller won the
        race, or None if another concurrent poller already claimed it.

        Closes the SELECT-then-INSERT window where two concurrent
        poll_and_plan invocations both observed
        ``get_by_queue_id(queue_id) is None`` and both proceeded
        to call the (expensive) planner. The UNIQUE constraint on
        queue_id makes the loser's INSERT fail; we catch
        IntegrityError and return None so the loser skips the row.

        Status is set to ``claimed`` so the row is visible in
        list_all() but excluded from list_pending_review() (which
        filters on plan_status='draft'). The follow-up upsert
        moves it to draft once the planner completes.
        """
        if not queue_id:
            raise ValueError("queue_id is required")
        plan_id = "plan-" + uuid4().hex[:12]
        now = time.time()
        with self._connect() as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "INSERT INTO integration_plans "
                    "(plan_id, queue_id, capability_id, "
                    "created_at, updated_at, plan_status, "
                    "plan_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (plan_id, queue_id, capability_id,
                     now, now, "claimed", "{}"),
                )
                con.commit()
                return plan_id
            except sqlite3.IntegrityError:
                con.rollback()
                return None

    def release_claim(self, *, queue_id: str) -> bool:
        """Drop a claim placeholder row if it's still in 'claimed'
        status — i.e. the planner failed (or returned None) and we
        want the next poll tick to retry. Returns True iff a row
        was actually deleted. Never touches non-claimed rows
        (draft / needs_field_search etc) so this is safe to call
        in any post-claim error path."""
        if not queue_id:
            return False
        with self._connect() as con:
            cur = con.execute(
                "DELETE FROM integration_plans "
                "WHERE queue_id = ? AND plan_status = 'claimed'",
                (queue_id,),
            )
            con.commit()
            return cur.rowcount > 0

    def upsert(
        self,
        *,
        queue_id: str,
        capability_id: str,
        plan_status: str,
        plan_json: dict | str,
    ) -> str:
        """Insert or update a plan row keyed on queue_id. Latest
        plan_status + plan_json win. Returns plan_id (stable across
        upserts for the same queue_id)."""
        if not queue_id:
            raise ValueError("queue_id is required")
        if isinstance(plan_json, dict):
            plan_json_str = json.dumps(plan_json, default=str)
        else:
            plan_json_str = str(plan_json)
        now = time.time()
        with self._connect() as con:
            existing = con.execute(
                "SELECT plan_id FROM integration_plans "
                "WHERE queue_id = ?",
                (queue_id,),
            ).fetchone()
            if existing:
                plan_id = existing["plan_id"]
                con.execute(
                    "UPDATE integration_plans "
                    "SET plan_status = ?, plan_json = ?, "
                    "updated_at = ?, capability_id = ? "
                    "WHERE plan_id = ?",
                    (plan_status, plan_json_str, now,
                     capability_id, plan_id),
                )
            else:
                plan_id = "plan-" + uuid4().hex[:12]
                con.execute(
                    "INSERT INTO integration_plans "
                    "(plan_id, queue_id, capability_id, "
                    "created_at, updated_at, plan_status, "
                    "plan_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (plan_id, queue_id, capability_id,
                     now, now, plan_status, plan_json_str),
                )
            con.commit()
        return plan_id

    def get_by_queue_id(self, queue_id: str) -> Optional[dict]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM integration_plans "
                "WHERE queue_id = ?",
                (queue_id,),
            ).fetchone()
        return _row_to_dict(row) if row else None

    def list_all(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM integration_plans "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_pending_review(self) -> list[dict]:
        """Plans the operator hasn't acted on yet. Excludes
        needs_field_search (Stage 3 not yet sliced) and any
        already-approved or already-rejected plans."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM integration_plans "
                "WHERE plan_status = 'draft' "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    raw = d.get("plan_json") or "{}"
    try:
        d["plan_json"] = json.loads(raw)
    except Exception:
        d["plan_json"] = {}
    return d


# ── poller ─────────────────────────────────────────────────────────


def poll_and_plan(
    *,
    queue: Any,
    plans: IntegrationPlanStore,
    manual_root: Path | None = None,
) -> list[str]:
    """Walk the queue's open rows; for any row at status='queued'
    that doesn't already have a plan, call plan_next and persist.

    Returns the list of plan_ids created (or upserted) on this
    pass. Idempotent: a second call with no queue changes returns
    [].

    Designed to be called from a daemon thread on an hourly timer.
    Errors on individual rows are logged and skipped — one bad
    row never blocks subsequent rows from being planned.
    """
    out: list[str] = []
    try:
        rows = queue.list_open()
    except Exception as e:
        logger.warning(
            "capability_integration_plans: queue.list_open failed: %s",
            e,
        )
        return out

    # AcquisitionQueue.list_open returns DESC by created_at.
    # Process oldest-first for a more natural human-review order.
    rows = list(reversed(rows))

    for row in rows:
        if row.get("status") != "queued":
            continue
        queue_id = row["id"]
        if plans.get_by_queue_id(queue_id) is not None:
            continue
        # T2.3/T2.4 (2026-05-04 audit) — atomically claim the row
        # before calling the (slow) planner. If a concurrent poller
        # got there first, claim() returns None and we skip — saving
        # the wasted plan_next() call AND the duplicate-row
        # IntegrityError on the final upsert.
        capability_id_hint = str(
            row.get("capability_id") or "unknown"
        )
        claimed = plans.claim(
            queue_id=queue_id, capability_id=capability_id_hint,
        )
        if claimed is None:
            continue
        try:
            plan = plan_next(
                queue, queue_id=queue_id, manual_root=manual_root,
            )
        except Exception as e:
            logger.warning(
                "capability_integration_plans: plan_next failed for "
                "queue_id=%s: %s",
                queue_id, e,
            )
            # Release the claim so the next tick can retry. Without
            # this, a one-off planner glitch would permanently block
            # this queue_id from ever being planned.
            plans.release_claim(queue_id=queue_id)
            continue
        if plan is None:
            # Same logic as the exception branch — claim must be
            # released so the next tick can retry once the upstream
            # condition (e.g. missing manual entry) is fixed.
            plans.release_claim(queue_id=queue_id)
            continue
        try:
            plan_status = (
                "needs_field_search"
                if getattr(plan, "needs_field_search", False)
                else "draft"
            )
            payload = (
                asdict(plan) if is_dataclass(plan) else plan.__dict__
            )
            plan_id = plans.upsert(
                queue_id=queue_id,
                capability_id=getattr(plan, "capability_id", "unknown"),
                plan_status=plan_status,
                plan_json=payload,
            )
            out.append(plan_id)
            logger.info(
                "capability_integration_plans: planned queue_id=%s "
                "plan_id=%s status=%s",
                queue_id, plan_id, plan_status,
            )
        except Exception as e:
            logger.warning(
                "capability_integration_plans: persist failed for "
                "queue_id=%s: %s",
                queue_id, e,
            )
            continue

    return out
