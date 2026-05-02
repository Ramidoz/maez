#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""One-shot backfill: approve-and-failed audit rows → consequence_memory.

Why this exists
---------------

Commit 8694b14 wired `_on_approve`'s failure branch to write
`CLASS_TOOL_FAILURE` rows when an approved action fails downstream.
That fixes new failures going forward but leaves the historical
floor — 80+ existing `outcome='approved_and_failed'` rows in
audit_log.db (mostly an `apt install openrgb` fixation episode)
that the planner has no learning signal for.

This script copies those historical rows into consequence_memory's
events table so `consequence_memory.relevant()` surfaces them on
future planner cycles. It does NOT delete or modify audit_log.db.

Why direct SQLite insert (not record_event)
-------------------------------------------

`consequence_memory.record_event()` stamps `time.time()` on every
write — fine for the live producer path but wrong for backfill
(would re-anchor every historical failure to "today"). We open
the consequence_memory DB directly and insert with the original
`outcome_ts` from audit_log.

Idempotency
-----------

Each backfilled row carries `extra={"backfill": True,
"request_id": <audit.request_id>}`. Re-runs scan existing
events.extra_json for those request_ids and skip them. This
mirrors the migration pattern in
`scripts/memory_curation/curate_2026_04_24.py`.

Usage
-----

    .venv/bin/python scripts/backfill_consequence_from_audit.py
    .venv/bin/python scripts/backfill_consequence_from_audit.py --commit

Dry-run is default. `--commit` executes inserts. Log lands in
`logs/backfill_approved_and_failed_consequence_<YYYY-MM-DD>.txt`
regardless of mode.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.backfill_consequence")

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _default_audit_db() -> Path:
    return REPO / "memory" / "audit_log.db"


def _default_cm_db() -> Path:
    return Path(os.environ.get(
        "MAEZ_CONSEQUENCE_MEMORY_DB",
        str(REPO / "memory" / "consequence_memory.db"),
    ))


def _default_log_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return REPO / "logs" / f"backfill_approved_and_failed_consequence_{today}.txt"


# ── shape ─────────────────────────────────────────────────────────────


def _extract_cmd(params_json: str) -> str:
    if not params_json:
        return ""
    try:
        params = json.loads(params_json)
    except Exception:
        return ""
    if isinstance(params, dict):
        cmd = params.get("cmd")
        if isinstance(cmd, str):
            return cmd
    return ""


def _build_event_fields(audit_row: dict) -> dict:
    """Map an audit_log row to consequence_memory event columns.

    Mirrors the producer block in core/decision/decision_pipeline.py
    `_on_approve` (commit 8694b14) so backfilled rows surface the
    same way as fresh ones.
    """
    action = audit_row.get("action") or "unknown"
    cmd = _extract_cmd(audit_row.get("params_json") or "")
    if cmd:
        context = f"action={action} cmd={cmd!r}"
    else:
        context = f"action={action}"
    outcome = audit_row.get("outcome_notes") or ""
    tags = [action]
    if cmd:
        first_tok = cmd.strip().split()
        if first_tok:
            tags.append(first_tok[0])
    ts = audit_row.get("outcome_ts")
    if ts is None:
        ts = audit_row.get("ts") or 0.0
    extra = {
        "backfill": True,
        "request_id": audit_row.get("request_id") or "",
        "audit_id": audit_row.get("id"),
    }
    return {
        "ts": float(ts),
        "context": context[:400],
        "outcome": outcome[:400],
        "tags": tags,
        "extra": extra,
    }


# ── reads ─────────────────────────────────────────────────────────────


def _read_failed_rows(audit_db: Path) -> list[dict]:
    if not audit_db.exists():
        return []
    with contextlib.closing(sqlite3.connect(audit_db)) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT id, request_id, ts, action, params_json, "
            "outcome_ts, outcome_notes "
            "FROM audit_log WHERE outcome = 'approved_and_failed' "
            "ORDER BY id ASC"
        )
        return [dict(r) for r in cur.fetchall()]


def _existing_request_ids(cm_db: Path) -> set[str]:
    """Scan extra_json for backfill markers so re-runs skip them."""
    if not cm_db.exists():
        return set()
    out: set[str] = set()
    with contextlib.closing(sqlite3.connect(cm_db)) as con:
        cur = con.execute(
            "SELECT extra_json FROM events WHERE class = 'tool_failure'"
        )
        for (raw,) in cur.fetchall():
            if not raw:
                continue
            try:
                ex = json.loads(raw)
            except Exception:
                continue
            if isinstance(ex, dict) and ex.get("backfill"):
                rid = ex.get("request_id")
                if isinstance(rid, str) and rid:
                    out.add(rid)
    return out


# ── writes ────────────────────────────────────────────────────────────


def _insert_event(con: sqlite3.Connection, fields: dict) -> int:
    cur = con.execute(
        "INSERT INTO events (ts, class, surface, context, outcome, "
        "feedback, tags, extra_json) "
        "VALUES (?, 'tool_failure', 'decision_pipeline.backfill', "
        "?, ?, '', ?, ?)",
        (
            fields["ts"], fields["context"], fields["outcome"],
            ",".join(fields["tags"]), json.dumps(fields["extra"]),
        ),
    )
    return cur.lastrowid


def _ensure_schema(cm_db: Path) -> None:
    """Materialise the events table by going through the canonical
    schema in core/learning/consequence_memory.py:_connect (the only
    source of truth). Avoids drift if that schema gains a column —
    the alternative of duplicating the CREATE here would silently
    skew under fresh-DB tests."""
    cm_db.parent.mkdir(parents=True, exist_ok=True)
    from core import consequence_memory as _cm
    with contextlib.closing(_cm._connect()):
        pass


# ── driver ────────────────────────────────────────────────────────────


def run(
    *,
    audit_db: Optional[Path] = None,
    cm_db: Optional[Path] = None,
    log_path: Optional[Path] = None,
    commit: bool = False,
) -> int:
    """Returns the number of NEW rows that were (or would be) written."""
    audit_db = audit_db or _default_audit_db()
    cm_db = cm_db or _default_cm_db()
    log_path = log_path or _default_log_path()

    log_lines: list[str] = []

    def log(msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        prefix = "[COMMIT] " if commit else "[DRYRUN] "
        line = f"{stamp} {prefix}{msg}"
        log_lines.append(line)
        print(line)

    log(f"audit_db = {audit_db}")
    log(f"cm_db    = {cm_db}")

    rows = _read_failed_rows(audit_db)
    log(f"approved_and_failed rows in audit_log: {len(rows)}")

    _ensure_schema(cm_db)
    already = _existing_request_ids(cm_db)
    log(f"already-backfilled request_ids: {len(already)}")

    todo = [r for r in rows if (r.get("request_id") or "") not in already]
    log(f"new rows to backfill: {len(todo)}")

    written = 0
    if commit and todo:
        with contextlib.closing(sqlite3.connect(cm_db)) as con:
            for r in todo:
                fields = _build_event_fields(r)
                _insert_event(con, fields)
                written += 1
            con.commit()
        log(f"wrote {written} rows to consequence_memory.events")
    elif todo:
        # Dry-run: still surface a sample so a human can sanity-check
        for r in todo[:3]:
            fields = _build_event_fields(r)
            head_outcome = (fields["outcome"] or "")[:80].replace("\n", " ")
            log(f"  WOULD WRITE: rid={r.get('request_id')} "
                f"ts={fields['ts']:.0f} "
                f"ctx={fields['context'][:80]!r} "
                f"out={head_outcome!r}")
        if len(todo) > 3:
            log(f"  ... and {len(todo) - 3} more")

    # Persist the log regardless of mode.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = log_path.read_text() if log_path.exists() else ""
    header = (
        "\n" + "=" * 70 + "\n"
        f"Run at {datetime.now(timezone.utc).isoformat()} "
        f"({'COMMIT' if commit else 'DRY RUN'})\n"
        + "=" * 70 + "\n"
    )
    log_path.write_text(existing + header + "\n".join(log_lines) + "\n")

    return len(todo) if not commit else written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true",
                    help="Execute inserts. Default is a dry run.")
    ap.add_argument("--audit-db", type=Path, default=None)
    ap.add_argument("--cm-db", type=Path, default=None)
    ap.add_argument("--log-path", type=Path, default=None)
    args = ap.parse_args()
    run(
        audit_db=args.audit_db,
        cm_db=args.cm_db,
        log_path=args.log_path,
        commit=args.commit,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
