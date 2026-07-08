# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger cross-DB reconciliation.

Implements the §6.2 reconciliation contract: walk the four external
dependent DBs (audit_log, fabrication_events, pending_cards,
self_mod_dialogs), find post-era rows that have no matching FK
reference in the ledger ``turns`` table, and (optionally) repair the
gap by appending synthetic ``system_event`` turns through the writer.

State C (was_rewritten=1 with no claims) is detected and reported but
never auto-repaired in this slice — claim extraction is slice 4.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.ledger import writer

__all__ = ["reconcile"]

# Pre-2001 timestamps are treated as "low-era" — the operator likely
# fat-fingered the era setup. With --apply on a populated DB this
# would write a synthetic system_event for every existing dependent
# row across decades of history. We refuse unless force_low_era=True.
_MIN_REASONABLE_ERA = 1.0e9  # ~2001-09-09 UTC
_LOW_ERA_ORPHAN_THRESHOLD = 50


# (table_name, ts_col, fk_col, result_key)
_FK_MAP: tuple[tuple[str, str, str, str], ...] = (
    ("audit_log", "ts", "audit_log_id", "audit_log"),
    ("fabrication_events", "ts", "fabrication_event_id", "fabrication_events"),
    ("pending_cards", "created_at", "pending_card_id", "pending_cards"),
    ("self_mod_dialogs", "created_at", "self_mod_dialog_id", "self_mod_dialogs"),
)

def _writes_enabled() -> bool:
    from core.ledger.writes_flag import ledger_writes_enabled

    return ledger_writes_enabled()


def _read_era(ledger_db_path: str) -> float:
    conn = sqlite3.connect(
        f"file:{ledger_db_path}?mode=ro", uri=True
    )
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='ledger_era_starts_at'"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise RuntimeError(
            "ledger era is missing: meta.ledger_era_starts_at row absent"
        )
    raw_value = row[0]
    if raw_value is None or raw_value == "":
        raise RuntimeError(
            "ledger era is empty: meta.ledger_era_starts_at has no value"
        )
    try:
        return float(raw_value)
    except (TypeError, ValueError) as e:
        raise RuntimeError(
            f"ledger era value {raw_value!r} is not a parseable float: {e}"
        )


def _post_era_rows(
    db_path: str, table: str, ts_col: str, era_ts: float,
) -> list[dict]:
    """Read post-era ids from an external DB.

    Tolerant by design:
      - missing DB file → return [] (treat as State A: nothing yet exists)
      - missing table → return [] (subsystem hasn't initialized yet)
    Any other SQL error propagates.
    """
    if not Path(db_path).is_file():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        # Probe for the table — a brand-new install where the dependent
        # subsystem hasn't created its table yet is morally State A.
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if present is None:
            return []
        rows = conn.execute(
            f"SELECT id, {ts_col} FROM {table} WHERE {ts_col} > ? "
            "ORDER BY id ASC",
            (era_ts,),
        ).fetchall()
    finally:
        conn.close()
    return [{"id": int(r[0]), "ts": float(r[1])} for r in rows]


def _referenced_ids(ledger_db_path: str, fk_col: str) -> set:
    conn = sqlite3.connect(
        f"file:{ledger_db_path}?mode=ro", uri=True
    )
    try:
        rows = conn.execute(
            f"SELECT {fk_col} FROM turns WHERE {fk_col} IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    return {int(r[0]) for r in rows}


def _state_c_turns(ledger_db_path: str) -> list[str]:
    conn = sqlite3.connect(
        f"file:{ledger_db_path}?mode=ro", uri=True
    )
    try:
        rows = conn.execute(
            "SELECT turn_id FROM turns WHERE was_rewritten = 1 "
            "AND turn_id NOT IN (SELECT turn_id FROM claims) "
            "ORDER BY rowid ASC"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def reconcile(
    ledger_db_path: str,
    *,
    audit_log_db_path: str,
    fabrication_log_db_path: str,
    pending_cards_db_path: str,
    self_mod_dialogs_db_path: str,
    dry_run: bool = True,
    force_low_era: bool = False,
) -> dict:
    """Walk the four external DBs and reconcile FK orphans against ledger.

    See module docstring for the contract.

    `force_low_era`: required to apply repairs when the era timestamp
    is implausibly old (pre-2001-09) AND many orphans exist. This is
    the operator-confirmation guard against writing a synthetic row for
    every pre-existing audit/fabrication/card row in production.
    """
    # Era gate first — fails before any other work.
    era_ts = _read_era(ledger_db_path)

    # If the caller asked to apply, the writer flag must be on. We check
    # this before doing any expensive work so the failure mode is fast.
    if not dry_run and not _writes_enabled():
        raise RuntimeError(
            "MAEZ_LEDGER_WRITES is not enabled; refusing to apply writes. "
            "Set MAEZ_LEDGER_WRITES=1 to permit reconciliation writes."
        )

    ext_paths = {
        "audit_log": audit_log_db_path,
        "fabrication_events": fabrication_log_db_path,
        "pending_cards": pending_cards_db_path,
        "self_mod_dialogs": self_mod_dialogs_db_path,
    }

    orphans: dict[str, list[int]] = {
        "audit_log": [],
        "fabrication_events": [],
        "pending_cards": [],
        "self_mod_dialogs": [],
    }

    for table, ts_col, fk_col, key in _FK_MAP:
        ext_db = ext_paths[key]
        post_era = _post_era_rows(ext_db, table, ts_col, era_ts)
        if not post_era:
            continue
        referenced = _referenced_ids(ledger_db_path, fk_col)
        orphan_ids = sorted(
            int(row["id"]) for row in post_era
            if int(row["id"]) not in referenced
        )
        orphans[key] = orphan_ids

    state_c = _state_c_turns(ledger_db_path)
    total_orphans = sum(len(v) for v in orphans.values())

    # Low-era guard: era < 2001 + many orphans + apply-mode is the
    # operator-fat-finger scenario. Refuse unless explicitly forced.
    if (
        not dry_run
        and not force_low_era
        and era_ts < _MIN_REASONABLE_ERA
        and total_orphans > _LOW_ERA_ORPHAN_THRESHOLD
    ):
        raise RuntimeError(
            f"refusing to apply: ledger_era_starts_at={era_ts!r} is "
            f"implausibly old (pre-{_MIN_REASONABLE_ERA:g}) and would "
            f"flag {total_orphans} pre-existing rows as orphans. "
            f"Either set the era to a real timestamp, or pass "
            f"force_low_era=True to override (CLI: --force-low-era)."
        )

    writes_applied = 0
    if not dry_run and total_orphans > 0:
        w = writer.LedgerWriter(ledger_db_path)
        try:
            if not w.is_enabled():
                # Defensive; we already checked the env above, but the
                # writer's view of the flag is the authoritative one.
                raise RuntimeError(
                    "MAEZ_LEDGER_WRITES is not enabled per LedgerWriter."
                )
            for table, ts_col, fk_col, key in _FK_MAP:
                ext_db = ext_paths[key]
                post_era = _post_era_rows(ext_db, table, ts_col, era_ts)
                row_by_id = {int(row["id"]): row for row in post_era}
                for orphan_id in orphans[key]:
                    source_ts = row_by_id.get(orphan_id, {}).get("ts")
                    raw_text = json.dumps(
                        {
                            "event": "orphan_dependent_row",
                            "reason": (
                                "ledger_write_missing_after_crash_or_legacy_write"
                            ),
                            "source_db": key,
                            "source_id": orphan_id,
                            "source_table": table,
                            "source_ts": source_ts,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    kwargs = {fk_col: orphan_id}
                    tid = w.write_turn(
                        "system_event",
                        raw_text,
                        surface="system",
                        raw_surface="ledger_reconciliation",
                        taint_labels=["self_generated"],
                        privacy_access="public",
                        **kwargs,
                    )
                    if tid is not None:
                        writes_applied += 1
        finally:
            w.close()

    if dry_run:
        verdict = "orphans_found" if total_orphans > 0 else "clean"
    else:
        verdict = "repaired" if writes_applied > 0 else "clean"

    return {
        "ledger_era_starts_at": era_ts,
        "orphans_found": orphans,
        "state_c_turns": state_c,
        "writes_applied": writes_applied,
        "verdict": verdict,
    }
