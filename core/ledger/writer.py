# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger production writer.

Implements the append-only writer for the ledger ``turns`` table. Every
write computes a ``chain_hash`` per LEDGER_ENVELOPE_SCHEMA.md §6.1 and
updates the ``meta.last_chain_hash`` head pointer in the same SQLite
transaction so the chain has a verifiable head at all times.

Public API:
    LedgerWriter(db_path)           — open a writer against a migrated DB.
    LedgerWriter.is_enabled()       — gate on MAEZ_LEDGER_WRITES.
    LedgerWriter.write_turn(...)    — append one turn, return turn_id or None.
    LedgerWriter.close()            — release the SQLite connection.

Enablement:
    Reads ``MAEZ_LEDGER_WRITES`` once at construction time.
      - ``"1"`` / ``"true"`` (case-insensitive, whitespace stripped) → enabled.
      - ``"0"`` / ``"false"`` / ``"no"`` / ``"off"`` / empty → disabled, silent.
      - Any other non-empty value → disabled, ONE warning per instance via
        the ``core.ledger.writer`` logger naming ``MAEZ_LEDGER_WRITES``.
    A disabled writer is a silent no-op: ``write_turn`` returns ``None``
    without validating the payload and without touching the DB.

Per-kind contract:
    The §4.2 NOT-NULL and forbidden-field contracts are enforced BEFORE
    any SQL runs. Validation failure raises ``ValueError`` whose message
    names both the kind and the offending field. No row is inserted on
    validation failure and ``meta.last_chain_hash`` is not modified.

Atomicity:
    The ``INSERT INTO turns`` and ``UPDATE meta SET value = ? WHERE
    key='last_chain_hash'`` always run inside one explicit transaction.
    On any error the transaction is rolled back, leaving zero observable
    state change.

Concurrency:
    A single ``threading.Lock`` serializes the entire critical section
    (head read → hash compute → INSERT → meta UPDATE → COMMIT). Without
    it, racing threads would read the same prev_chain_hash and produce a
    fork that ``chain.verify_chain`` would flag.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid

from core.ledger import chain

__all__ = ["LedgerWriter"]


_LOGGER = logging.getLogger("core.ledger.writer")

_TRUE_VALUES = {"1", "true"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}

# Per-kind contract from LEDGER_ENVELOPE_SCHEMA.md §4.2.
# Field names below are the kwarg base names used by write_turn — they
# are substrings of the underlying column names (e.g. "evidence_envelope"
# is a substring of "evidence_envelope_json"), so error messages remain
# unambiguous regardless of which form callers grep for.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "user_message": ("raw_text",),
    "model_reply": (
        "raw_text", "model_id", "prompt_hash", "soul_hash",
        "evidence_envelope", "audit_verdict",
    ),
    "tool_call": ("raw_text", "action_proposal"),
    "tool_result": ("raw_text", "parent_turn_id"),
    "daemon_cycle": (
        "raw_text", "model_id", "prompt_hash", "soul_hash",
        "evidence_envelope", "audit_verdict",
    ),
    "approval_decision": ("raw_text", "audit_verdict", "pending_card_id"),
    "self_mod_dialog_step": ("raw_text", "audit_verdict", "self_mod_dialog_id"),
    # peer_message_in: only raw_text required per §12 sign-off ratification
    # 2026-05-06 (parent_turn_id was originally required but removed because
    # the parent lives in the OTHER Maez's ledger, not ours).
    "peer_message_in": ("raw_text",),
    "peer_message_out": ("raw_text", "evidence_envelope", "audit_verdict"),
    "system_event": ("raw_text",),
}

_FORBIDDEN_FIELDS: dict[str, tuple[str, ...]] = {
    "user_message": ("model_id", "prompt_hash", "audit_verdict"),
    "model_reply": (),
    "tool_call": ("model_id",),
    "tool_result": ("model_id", "evidence_envelope"),
    "daemon_cycle": (),
    "approval_decision": ("model_id",),
    "self_mod_dialog_step": (),
    "peer_message_in": (),
    "peer_message_out": (),
    "system_event": ("model_id", "prompt_hash"),
}

# Column order for the INSERT — all 28 columns from GENESIS_ROW plus
# the two chain columns. Kept in lockstep with migrate.GENESIS_ROW.
_TURN_COLUMNS: tuple[str, ...] = (
    "turn_id",
    "tenant_id",
    "timestamp",
    "schema_version",
    "turn_kind",
    "surface",
    "raw_surface",
    "parent_turn_id",
    "correction_of",
    "model_id",
    "lora_hash",
    "soul_hash",
    "prompt_hash",
    "raw_text",
    "rewritten_text",
    "was_rewritten",
    "signals_present",
    "signals_absent",
    "evidence_envelope_json",
    "action_proposal_json",
    "audit_verdict_json",
    "will_i_json",
    "memory_read_ids",
    "memory_written_ids",
    "audit_log_id",
    "fabrication_event_id",
    "self_mod_dialog_id",
    "pending_card_id",
)


def _canonical_json(obj) -> str:
    """Canonical JSON encoding matching chain.canonical_row_bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


class LedgerWriter:
    """Append-only writer for the Maez ledger turns table."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._enabled = self._parse_flag()
        # check_same_thread=False so the threading.Lock is the
        # serialization point, not Python's per-connection thread guard.
        # isolation_level=None gives manual transaction control so we can
        # use BEGIN IMMEDIATE — required to close the cross-process fork
        # window where two writers SELECT the same head pointer under
        # SHARED locks and both succeed at INSERT.
        self._conn: sqlite3.Connection | None = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None,
        )
        self._conn.execute("PRAGMA foreign_keys = ON")
        # Wait up to 5 seconds for cross-process write lock contention
        # rather than failing immediately with "database is locked".
        self._conn.execute("PRAGMA busy_timeout = 5000")
        # Explicit synchronous=NORMAL — fine under WAL, makes intent clear.
        self._conn.execute("PRAGMA synchronous = NORMAL")

    # ------------------------------------------------------------------ flag

    def _parse_flag(self) -> bool:
        raw = os.environ.get("MAEZ_LEDGER_WRITES", "")
        stripped = raw.strip().lower()
        if stripped in _TRUE_VALUES:
            return True
        if stripped in _FALSE_VALUES:
            return False
        # Unrecognized non-empty, non-falsy value: disabled + warn once.
        _LOGGER.warning(
            "MAEZ_LEDGER_WRITES has unrecognized value %r; "
            "treating as disabled. Use '1' or 'true' to enable.",
            raw,
        )
        return False

    def is_enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------ write

    def write_turn(
        self,
        turn_kind: str,
        raw_text: str | None,
        *,
        tenant_id: str = "owner",
        surface: str = "system",
        raw_surface: str | None = None,
        parent_turn_id: str | None = None,
        correction_of: str | None = None,
        model_id: str | None = None,
        lora_hash: str | None = None,
        soul_hash: str | None = None,
        prompt_hash: str | None = None,
        rewritten_text: str | None = None,
        was_rewritten: bool = False,
        signals_present: list | None = None,
        signals_absent: list | None = None,
        evidence_envelope: dict | None = None,
        action_proposal: dict | None = None,
        audit_verdict: dict | None = None,
        will_i: dict | None = None,
        memory_read_ids: list | None = None,
        memory_written_ids: list | None = None,
        audit_log_id: int | None = None,
        fabrication_event_id: int | None = None,
        self_mod_dialog_id: int | None = None,
        pending_card_id: int | None = None,
    ) -> str | None:
        # Disabled writer is a silent no-op — no validation, no SQL.
        if not self._enabled:
            return None

        # Build a name → value map for validation purposes. Uses the
        # kwarg base names (without _json suffix) so error messages
        # match the schema doc's §4.2 vocabulary.
        provided = {
            "raw_text": raw_text,
            "parent_turn_id": parent_turn_id,
            "model_id": model_id,
            "prompt_hash": prompt_hash,
            "soul_hash": soul_hash,
            "evidence_envelope": evidence_envelope,
            "action_proposal": action_proposal,
            "audit_verdict": audit_verdict,
            "will_i": will_i,
            "pending_card_id": pending_card_id,
            "self_mod_dialog_id": self_mod_dialog_id,
        }

        required = _REQUIRED_FIELDS.get(turn_kind)
        if required is None:
            raise ValueError(
                f"unknown turn_kind {turn_kind!r} (per §4.2)"
            )
        for field in required:
            if provided.get(field) is None:
                raise ValueError(
                    f"{turn_kind} requires {field} "
                    f"(NOT NULL contract per §4.2)"
                )

        for field in _FORBIDDEN_FIELDS.get(turn_kind, ()):
            if provided.get(field) is not None:
                raise ValueError(
                    f"{turn_kind} forbids {field} (per §4.2)"
                )

        # Build the canonical row. Column shape matches GENESIS_ROW.
        turn_id = str(uuid.uuid4())
        ts = time.time()

        def _list_col(v: list | None) -> str:
            return _canonical_json(v) if v is not None else "[]"

        def _dict_col(v: dict | None) -> str | None:
            return _canonical_json(v) if v is not None else None

        row: dict = {
            "turn_id": turn_id,
            "tenant_id": tenant_id,
            "timestamp": ts,
            "schema_version": 1,
            "turn_kind": turn_kind,
            "surface": surface,
            "raw_surface": raw_surface,
            "parent_turn_id": parent_turn_id,
            "correction_of": correction_of,
            "model_id": model_id,
            "lora_hash": lora_hash,
            "soul_hash": soul_hash,
            "prompt_hash": prompt_hash,
            "raw_text": raw_text,
            "rewritten_text": rewritten_text,
            "was_rewritten": 1 if was_rewritten else 0,
            "signals_present": _list_col(signals_present),
            "signals_absent": _list_col(signals_absent),
            "evidence_envelope_json": _dict_col(evidence_envelope),
            "action_proposal_json": _dict_col(action_proposal),
            "audit_verdict_json": _dict_col(audit_verdict),
            "will_i_json": _dict_col(will_i),
            "memory_read_ids": _list_col(memory_read_ids),
            "memory_written_ids": _list_col(memory_written_ids),
            "audit_log_id": audit_log_id,
            "fabrication_event_id": fabrication_event_id,
            "self_mod_dialog_id": self_mod_dialog_id,
            "pending_card_id": pending_card_id,
        }

        with self._lock:
            conn = self._conn
            if conn is None:
                raise RuntimeError("LedgerWriter is closed")

            try:
                # BEGIN IMMEDIATE acquires a RESERVED lock at transaction
                # start, so a concurrent writer in another process is
                # blocked at this point rather than reading the same head
                # pointer and producing a fork. busy_timeout (set in
                # __init__) makes this wait up to 5s rather than failing
                # immediately. With isolation_level=None on the connection,
                # we drive transactions explicitly.
                conn.execute("BEGIN IMMEDIATE")
                # Read head pointer for prev_chain_hash.
                head = conn.execute(
                    "SELECT value FROM meta WHERE key = 'last_chain_hash'"
                ).fetchone()
                if head is None:
                    raise RuntimeError(
                        "ledger meta.last_chain_hash missing — DB not migrated?"
                    )
                prev_chain_hash = head[0]

                # Era init: on the first non-genesis write, set
                # meta.ledger_era_starts_at to the current timestamp
                # in the SAME transaction as the INSERT. After that,
                # never overwrite. Reconciliation reads this row to
                # determine which external rows are post-ledger and
                # therefore eligible to be flagged as orphans. Without
                # this, slice 2.4 reconciliation refuses to run; with
                # it, the era is anchored at the moment the daemon
                # first started writing through the ledger.
                era_row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'ledger_era_starts_at'"
                ).fetchone()
                era_unset = (
                    era_row is None
                    or not (era_row[0] or "").strip()
                )
                if era_unset:
                    conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) "
                        "VALUES ('ledger_era_starts_at', ?)",
                        (repr(ts),),
                    )

                new_chain_hash = chain.compute_chain_hash(row, prev_chain_hash)

                cols = list(_TURN_COLUMNS) + ["prev_chain_hash", "chain_hash"]
                placeholders = ",".join("?" for _ in cols)
                values = [row[c] for c in _TURN_COLUMNS] + [
                    prev_chain_hash, new_chain_hash,
                ]

                conn.execute(
                    f"INSERT INTO turns ({','.join(cols)}) "
                    f"VALUES ({placeholders})",
                    values,
                )
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'last_chain_hash'",
                    (new_chain_hash,),
                )
                # Explicit COMMIT — with isolation_level=None,
                # conn.commit() is a no-op; transaction control is
                # via SQL statements.
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        return turn_id

    # ----------------------------------------------------------------- close

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None


# ---------------------------------------------------------------------------
# Shadow-write helper for daemon callers
# ---------------------------------------------------------------------------


def try_write_turn(
    db_path: str,
    turn_kind: str,
    raw_text: str | None,
    **kwargs,
) -> str | None:
    """Open a LedgerWriter, write one turn, close. Never raises.

    Daemon callers use this so a ledger failure (writer disabled, DB
    missing, validation error, SQL error, anything) does NOT break the
    user-facing reply path. On any exception, logs a warning at
    core.ledger.writer level and returns None.

    Returns the new turn_id on success, or None on disabled-writer /
    failure. The single-call shape keeps the daemon plumbing to one
    line per write.

    Per the architectural invariant: shadow writes only. The user
    reply ships regardless of what happens here.
    """
    raw_flag = os.environ.get("MAEZ_LEDGER_WRITES", "")
    stripped_flag = raw_flag.strip().lower()
    if stripped_flag in _FALSE_VALUES:
        return None
    if stripped_flag not in _TRUE_VALUES:
        _LOGGER.warning(
            "MAEZ_LEDGER_WRITES has unrecognized value %r; "
            "treating shadow write as disabled. Use '1' or 'true' to enable.",
            raw_flag,
        )
        return None

    try:
        w = LedgerWriter(db_path)
    except Exception as e:
        _LOGGER.warning(
            "shadow ledger writer init failed (kind=%r, path=%r): %s",
            turn_kind, db_path, e,
        )
        return None
    try:
        return w.write_turn(turn_kind, raw_text, **kwargs)
    except Exception as e:
        _LOGGER.warning(
            "shadow ledger write failed (kind=%r): %s",
            turn_kind, e,
        )
        return None
    finally:
        try:
            w.close()
        except Exception:
            pass

