# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maez ledger production writer.

Implements the append-only writer for the ledger ``turns`` table. Every
write computes a ``chain_hash`` per docs/ledger/envelope-schema.md §6.1 and
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
        the ``core.ledger.writes_flag`` logger naming ``MAEZ_LEDGER_WRITES``.
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

import functools
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from core.cognition import audit_policy as _audit_policy
from core.ledger import chain
from core.ledger import envelope_schema as _envelope_schema
from core.ledger import taint_stamping

__all__ = ["LedgerWriter"]


_LOGGER = logging.getLogger("core.ledger.writer")

_REHEARSAL_ROOT = Path(__file__).resolve().parents[2] / "logs" / "rehearsal"

# Per-kind contract from docs/ledger/envelope-schema.md §4.2.
# Field names below are the kwarg base names used by write_turn — they
# are substrings of the underlying column names (e.g. "evidence_envelope"
# is a substring of "evidence_envelope_json"), so error messages remain
# unambiguous regardless of which form callers grep for.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "user_message": ("raw_text",),
    "model_reply": (
        "raw_text",
        "model_id",
        "prompt_hash",
        "soul_hash",
        "evidence_envelope",
        "audit_verdict",
    ),
    "tool_call": ("raw_text", "action_proposal"),
    "tool_result": ("raw_text", "parent_turn_id"),
    "daemon_cycle": (
        "raw_text",
        "model_id",
        "prompt_hash",
        "soul_hash",
        "evidence_envelope",
        "audit_verdict",
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
    "taint_labels_json",
    "privacy_access",
)


def _owner_latch_path(db_path: str) -> str:
    return f"{os.path.abspath(db_path)}.ownerlock"


def _acquire_owner_latch(db_path: str) -> int:
    """Take the single-owner flock for this ledger, or refuse immediately.

    No retry loop on purpose: a live owner holds the latch for its whole
    lifetime, so waiting is not contention — it is a second writer trying
    to exist. Refusal feeds the dead-letter path, which is recoverable;
    a second concurrent writer is the corruption class the standing rule
    forbids. O_CLOEXEC so exec'd children cannot inherit ownership.
    """
    import fcntl

    path = _owner_latch_path(db_path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            holder = os.pread(fd, 64, 0).decode("ascii", "replace").strip()
        except OSError:
            holder = ""
        os.close(fd)
        raise RuntimeError(
            f"ledger {db_path} already has a live owner"
            f"{f' (pid {holder})' if holder else ''}; refusing a second "
            f"concurrent writer — enqueue through the owner instead"
        ) from None
    os.ftruncate(fd, 0)
    os.pwrite(fd, str(os.getpid()).encode("ascii"), 0)
    return fd


def _is_rehearsal_sidecar_ledger_path(db_path: str, *, rehearsal_root: Path) -> bool:
    try:
        path = Path(db_path).resolve()
        root = rehearsal_root.resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return False
    return path.name == "ledger.db" and path.parent.name.startswith("x6_")


def _canonical_json(obj) -> str:
    """Canonical JSON encoding matching chain.canonical_row_bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _require_stamp_kwargs(fn):
    """Refuse omitted S1 stamp kwargs without adding semantic defaults."""

    @functools.wraps(fn)
    def wrapper(self, turn_kind: str, raw_text: str | None, *args, **kwargs):
        if not args:
            for field in ("taint_labels", "privacy_access"):
                if field not in kwargs:
                    raise taint_stamping.TaintStampingRefusal(
                        f"{turn_kind}: {field} is required; no default is allowed",
                        turn_kind=turn_kind,
                        reason=f"{field}_missing",
                    )
        return fn(self, turn_kind, raw_text, *args, **kwargs)

    return wrapper


class LedgerWriter:
    """Append-only writer for the Maez ledger turns table."""

    def __init__(
        self,
        db_path: str,
        *,
        rehearsal_mode: bool = False,
        rehearsal_root: str | Path | None = None,
    ) -> None:
        root = Path(rehearsal_root) if rehearsal_root is not None else _REHEARSAL_ROOT
        if rehearsal_mode and not _is_rehearsal_sidecar_ledger_path(
            db_path,
            rehearsal_root=root,
        ):
            raise ImportError(
                "rehearsal ledger writers must use logs/rehearsal/x6_<run_id>/ledger.db"
            )
        self._db_path = db_path
        self._rehearsal_mode = rehearsal_mode
        self._lock = threading.Lock()
        self._enabled = self._parse_flag()
        self._owner_latch_fd: int | None = None
        if self._enabled:
            # An ENABLED writer refuses to construct on a SQLite inside the
            # WAL-reset corruption window (< 3.51.3) instead of merely
            # reporting it at boot — a process launched without the vendored
            # library (a bare shell, unlike the systemd units) must not be
            # able to write the life record on a vulnerable engine. Disabled
            # writers are untouched so the flag-dormant state is unchanged.
            from core.infra.sqlite_runtime import require_fixed

            require_fixed("ledger writer (MAEZ_LEDGER_WRITES enabled)")
            # Single-owner latch: at most one live ENABLED writer per DB,
            # in or across processes. flock dies with the process (SIGKILL
            # included), so a crashed owner never wedges the ledger. This
            # makes the forbidden concurrent-WAL-writers topology
            # structurally unreachable rather than discouraged by rule.
            self._owner_latch_fd = _acquire_owner_latch(db_path)
        # check_same_thread=False so the threading.Lock is the
        # serialization point, not Python's per-connection thread guard.
        # isolation_level=None gives manual transaction control so we can
        # use BEGIN IMMEDIATE — required to close the cross-process fork
        # window where two writers SELECT the same head pointer under
        # SHARED locks and both succeed at INSERT.
        try:
            self._conn: sqlite3.Connection | None = sqlite3.connect(
                db_path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.execute("PRAGMA foreign_keys = ON")
            # Wait up to 5 seconds for cross-process write lock contention
            # rather than failing immediately with "database is locked".
            self._conn.execute("PRAGMA busy_timeout = 5000")
            # Council ruling Q2 (2026-08-24, four seats): synchronous=FULL
            # on the canonical path, unconditionally. The acknowledgment
            # (the returned turn_id, used immediately as parent/felt-state)
            # must never be more durable than the commit it names; under
            # NORMAL a power cut can erase an acked commit until the next
            # checkpoint, and no checkpoint policy ships. Rehearsal
            # sidecars are explicitly disposable and keep NORMAL.
            if self._rehearsal_mode:
                self._conn.execute("PRAGMA synchronous = NORMAL")
            else:
                self._conn.execute("PRAGMA synchronous = FULL")
        except BaseException:
            self._release_owner_latch()
            raise

    # ------------------------------------------------------------------ flag

    def _parse_flag(self) -> bool:
        from core.ledger.writes_flag import ledger_writes_enabled

        return ledger_writes_enabled()

    def is_enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------ write

    @_require_stamp_kwargs
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
        audit_trace_label: str | None = None,
        audit_trace_value_schema: int | None = None,
        audit_trace_metadata_shape: int | None = None,
        audit_trace_lineage: dict | None = None,
        lifecycle_stage: str | None = None,
        birth_anchor: bool = False,
        meta_marker_keys: list[str] | tuple[str, ...] | None = None,
        submission_id: str | None = None,
        submitted_at: float | None = None,
        taint_labels: list[str] | tuple[str, ...] | set[str],
        privacy_access: str,
    ) -> str | None:
        # Admission identity (migration 0006): optional, UNIQUE where
        # present. A redrive with the same identity AND the same payload
        # bytes returns the existing turn_id (idempotent commit); the
        # same identity with different bytes is refused — an identity
        # collision is never silently resolved.
        if submission_id is not None and (
            not isinstance(submission_id, str) or not submission_id.strip()
        ):
            raise ValueError("submission_id must be a non-empty string")
        # One-time markers: each named meta key is set to the new turn_id
        # INSIDE the write transaction, and refused (rolling back the turn
        # row) if already set. This is what makes "the marker turn and the
        # meta row that names it" atomic — the crash window between a turn
        # commit and a separate meta commit produced duplicate one-time
        # markers (model_reply_persistence, 2026-08-23 council follow-up).
        _RESERVED_META_KEYS = (
            "last_chain_hash",
            "birth_event_turn_id",
            "ledger_era_starts_at",
        )
        for _mk in meta_marker_keys or ():
            if not isinstance(_mk, str) or not _mk.strip():
                raise ValueError("meta_marker_keys entries must be non-empty strings")
            if _mk in _RESERVED_META_KEYS:
                raise ValueError(
                    f"meta_marker_keys may not name reserved meta key {_mk!r}"
                )
        if self._rehearsal_mode and lifecycle_stage != "rehearsal":
            raise ValueError("rehearsal ledger writer requires lifecycle_stage='rehearsal'")
        if lifecycle_stage == "rehearsal" and not self._rehearsal_mode:
            raise ValueError("production ledger writer refuses rehearsal lifecycle_stage rows")
        if lifecycle_stage is not None and lifecycle_stage != "rehearsal":
            raise ValueError(f"unknown explicit lifecycle_stage {lifecycle_stage!r}")
        if birth_anchor:
            if turn_kind != "system_event":
                raise ValueError("birth_anchor requires turn_kind='system_event'")
            if self._rehearsal_mode:
                raise ValueError("rehearsal writer refuses birth_anchor")
            if not self._enabled:
                raise ValueError(
                    "birth_anchor requires an enabled writer (MAEZ_LEDGER_WRITES)"
                )

        stamp = taint_stamping.validate_turn_stamp(
            turn_kind=turn_kind,
            taint_labels=taint_labels,
            privacy_access=privacy_access,
            caller=raw_surface or surface,
        )

        # Disabled writer is a silent SQL no-op, but S1 stamp validation still
        # runs so bad caller provenance is refused at the writer door.
        if not self._enabled:
            return None

        # S1 §4: "write refused (post-birth mode); pre-birth shadow path
        # unchanged". Gate round 21 executed the ordering bug in the first
        # placement: sitting BEFORE the disabled no-op, a disabled writer
        # raised PhaseUnknownRefusal where legacy returned None -- the shadow
        # path was no longer unchanged. The check belongs exactly here: after
        # the disabled no-op (a writer that will not write cannot misstamp),
        # before any chain interaction (the resolver's read stays outside the
        # write transaction). §4's TYPED refusal replaces the untyped
        # RuntimeError the chain-head read produced. try_write_turn converts
        # the raise into its shadow no-op on the reply path; DIRECT callers
        # (birth ceremony, reconcile, replay harness) see the new exception
        # by design -- a direct writer asking to write against an unvouchable
        # ledger should hear "no" loudly, and that propagation is ratified in
        # the T3 map rather than silently narrowed here.
        from core.memory import birth_phase as _bp
        if _bp.s1_enabled() and lifecycle_stage != "rehearsal":
            _pr = _bp.resolve(self._db_path)
            if _pr.phase == "unknown":
                raise _bp.PhaseUnknownRefusal(
                    f"ledger_writer.write_turn: refusing the write — the "
                    f"resolver reads unknown ({_pr.reason}); lifecycle_stage "
                    f"cannot be stamped truthfully")

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
            raise ValueError(f"unknown turn_kind {turn_kind!r} (per §4.2)")
        for field in required:
            if provided.get(field) is None:
                raise ValueError(f"{turn_kind} requires {field} (NOT NULL contract per §4.2)")

        for field in _FORBIDDEN_FIELDS.get(turn_kind, ()):
            if provided.get(field) is not None:
                raise ValueError(f"{turn_kind} forbids {field} (per §4.2)")

        # §3 envelope-shape validation (slice 3.0b: self_history slot
        # added). Permissive on unknown keys; strict on the well-known
        # slot shapes. None envelopes (allowed where the per-kind
        # contract permits absence) skip cleanly.
        if evidence_envelope is not None:
            try:
                _envelope_schema.validate_envelope(evidence_envelope)
            except ValueError as e:
                raise ValueError(f"{turn_kind} evidence_envelope invalid: {e}") from e

        _audit_policy.validate_trace_metadata(
            audit_trace_label=audit_trace_label,
            audit_trace_value_schema=audit_trace_value_schema,
            audit_trace_metadata_shape=audit_trace_metadata_shape,
            audit_trace_lineage=audit_trace_lineage,
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
            "taint_labels_json": stamp.taint_labels_json,
            "privacy_access": stamp.privacy_access,
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
                    raise RuntimeError("ledger meta.last_chain_hash missing — DB not migrated?")
                prev_chain_hash = head[0]
                position_row = conn.execute(
                    "SELECT COALESCE(MAX(chain_position), -1) + 1 FROM turns"
                ).fetchone()
                chain_position = int(position_row[0])

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
                era_unset = era_row is None or not (era_row[0] or "").strip()
                if era_unset:
                    conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) "
                        "VALUES ('ledger_era_starts_at', ?)",
                        (repr(ts),),
                    )

                new_chain_hash = chain.compute_chain_hash(row, prev_chain_hash)

                # Gestation Boundary slice (2026-05-08): post-birth
                # writes carry lifecycle_stage='lived'; pre-birth rows
                # fall through to SQL DEFAULT 'gestation'. The column
                # is intentionally not in the chain-hash row dict
                # (per chain._CHAIN_HASH_EXCLUDE) so birth state never
                # affects chain integrity.
                birth_row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
                ).fetchone()
                post_birth = birth_row is not None and (birth_row[0] or "").strip() != ""

                cols = list(_TURN_COLUMNS) + [
                    "chain_position",
                    "prev_chain_hash",
                    "chain_hash",
                ]
                values = [row[c] for c in _TURN_COLUMNS] + [
                    chain_position,
                    prev_chain_hash,
                    new_chain_hash,
                ]
                if lifecycle_stage == "rehearsal":
                    cols.append("lifecycle_stage")
                    values.append("rehearsal")
                elif post_birth:
                    cols.append("lifecycle_stage")
                    values.append("lived")
                if audit_trace_label is not None:
                    cols.extend(
                        [
                            "audit_trace_label",
                            "audit_trace_value_schema",
                            "audit_trace_metadata_shape",
                        ]
                    )
                    values.extend(
                        [
                            audit_trace_label,
                            audit_trace_value_schema,
                            audit_trace_metadata_shape,
                        ]
                    )
                if submission_id is not None:
                    cols.append("submission_id")
                    values.append(submission_id)
                if submitted_at is not None:
                    cols.append("submitted_at")
                    values.append(float(submitted_at))
                placeholders = ",".join("?" for _ in cols)

                conn.execute(
                    f"INSERT INTO turns ({','.join(cols)}) VALUES ({placeholders})",
                    values,
                )
                if audit_trace_label is not None:
                    assert audit_trace_lineage is not None
                    conn.execute(
                        "INSERT INTO audit_trace_lineage ("
                        "turn_id, rule_id, source_ids_json, "
                        "policy_doc_sha256, trace_value_schema, "
                        "trace_metadata_shape, applied_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            turn_id,
                            audit_trace_lineage["rule_id"],
                            _canonical_json(audit_trace_lineage["source_ids"]),
                            audit_trace_lineage["policy_doc_sha256"],
                            audit_trace_value_schema,
                            audit_trace_metadata_shape,
                            float(audit_trace_lineage["applied_at"]),
                        ),
                    )
                conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'last_chain_hash'",
                    (new_chain_hash,),
                )
                if birth_anchor:
                    already = conn.execute(
                        "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
                    ).fetchone()
                    if already is not None and (already[0] or "").strip():
                        raise ValueError(
                            "birth_event_turn_id already set — we do not re-birth"
                        )
                    conn.execute(
                        "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', ?)",
                        (turn_id,),
                    )
                for _mk in meta_marker_keys or ():
                    _already = conn.execute(
                        "SELECT value FROM meta WHERE key = ?", (_mk,)
                    ).fetchone()
                    if _already is not None and (_already[0] or "").strip():
                        raise ValueError(
                            f"meta marker {_mk!r} already set — one-time "
                            "markers are write-once"
                        )
                    conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                        (_mk, turn_id),
                    )
                # Explicit COMMIT — with isolation_level=None,
                # conn.commit() is a no-op; transaction control is
                # via SQL statements.
                conn.execute("COMMIT")
            except sqlite3.IntegrityError as e:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                if submission_id is not None and "submission_id" in str(e):
                    existing = conn.execute(
                        "SELECT turn_id, raw_text FROM turns"
                        " WHERE submission_id = ?",
                        (submission_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing[1] == raw_text:
                            _LOGGER.info(
                                "idempotent redrive: submission_id=%r already"
                                " committed as %s; writing nothing",
                                submission_id, existing[0],
                            )
                            return existing[0]
                        raise ValueError(
                            f"submission_id {submission_id!r} already"
                            " committed with DIFFERENT payload bytes —"
                            " identity collision refused"
                        ) from e
                raise
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
            self._release_owner_latch()

    def _release_owner_latch(self) -> None:
        if self._owner_latch_fd is not None:
            try:
                os.close(self._owner_latch_fd)  # closing the fd drops flock
            finally:
                self._owner_latch_fd = None


# ---------------------------------------------------------------------------
# Shadow-write helper for daemon callers
# ---------------------------------------------------------------------------


def dead_letter_path(db_path: str) -> str:
    """Sidecar file where this process's failed ENABLED writes are durably
    preserved. Per-process (pid suffix) so concurrent failing processes
    never interleave partial lines — a shared append file would quietly
    rebuild the multi-writer problem in JSONL. Discovery uses
    :func:`dead_letter_glob`."""
    return f"{db_path}.deadletter.{os.getpid()}.jsonl"


def dead_letter_glob(db_path: str) -> str:
    """Glob matching every process's dead-letter sidecar for this DB."""
    return f"{db_path}.deadletter.*.jsonl"


def dead_letter_status(db_path: str) -> dict:
    """Machine-readable dead-letter state: {files, rows, oldest_ts, bytes}.

    Logs are not operator state — a nonzero row count here is the honest
    'the ledger has omitted life-events pending replay' health predicate
    for status endpoints and the cockpit real-state surface. Never raises.
    """
    import glob as _glob

    files = sorted(_glob.glob(dead_letter_glob(db_path)))
    rows = 0
    oldest_ts: float | None = None
    total_bytes = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    rows += 1
                    try:
                        ts = json.loads(line).get("ts")
                    except (ValueError, AttributeError):
                        continue
                    if isinstance(ts, (int, float)):
                        oldest_ts = ts if oldest_ts is None else min(oldest_ts, ts)
            total_bytes += os.path.getsize(f)
        except OSError:
            continue
    return {
        "files": len(files),
        "rows": rows,
        "oldest_ts": oldest_ts,
        "bytes": total_bytes,
    }


#: Deterministic writer refusals (bad payload / provenance). These are
#: preserved as evidence but must never be blindly re-submitted by a
#: replayer — resubmitting bytes the writer refused at the door would
#: invert the refusal semantics. Environmental failures are "failed" and
#: are the replay candidates.
_REFUSAL_ERRORS: tuple[type[BaseException], ...] = (
    ValueError,
    taint_stamping.TaintStampingRefusal,
)


def _json_safe(obj):
    """Lossless-enough JSON coercion for dead-letter kwargs: sets become
    sorted lists (write_turn accepts set-typed taint_labels; str() of a
    set would be unreplayable), unknown objects become repr strings."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        vals = [_json_safe(v) for v in obj]
        try:
            return sorted(vals)
        except TypeError:
            return sorted(vals, key=repr)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def _dead_letter(
    db_path: str,
    turn_kind: str,
    raw_text: str | None,
    kwargs: dict,
    error: BaseException,
    stage: str,
    attempt_id: str | None = None,
) -> str:
    """Append the full failed payload to the dead-letter sidecar, fsynced.

    The Theme-2 claim is that the ledger cannot omit a life. A write that
    fails while writes are enabled must therefore leave the payload bytes
    somewhere durable — never only a log line. Raises on failure; the
    caller decides how loud losing the payload has to be.

    Mechanics chosen against known failure modes: one os.write() of the
    whole line (a buffered writer may split a line across syscalls),
    fsync of the file, fsync of the parent directory on first creation
    (else the file's existence itself is not crash-durable), 0o600 like
    the DB. ``event_id`` is minted here so replay/reconcile has an
    idempotency identity; ``category`` separates deterministic refusals
    (never blindly replayable) from environmental failures (replay
    candidates) so a replayer cannot poison itself.

    Honest limits, stated: this file shares the DB's filesystem, so the
    failures most likely to break the DB (ENOSPC, read-only remount)
    likely break it too — that is the CRITICAL branch; and its rows are
    outside the chain until a replayer re-appends them with explicit
    reconstruction provenance.
    """
    record = {
        # Identity minted BEFORE the first attempt when the caller passes
        # attempt_id (try_write_turn / owner_write_turn do) — a post-hoc
        # id cannot identify a transaction that committed before the
        # response was lost. The fallback mint keeps old callers safe.
        "event_id": attempt_id or uuid.uuid4().hex,
        "ts": time.time(),
        "pid": os.getpid(),
        "stage": stage,
        "category": (
            "refused" if isinstance(error, _REFUSAL_ERRORS) else "failed"
        ),
        "turn_kind": turn_kind,
        "raw_text": raw_text,
        "kwargs": _json_safe(kwargs),
        "error": repr(error),
    }
    line = (
        json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        + "\n"
    ).encode("utf-8")
    path = dead_letter_path(db_path)
    existed = os.path.exists(path)
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        # os.write may write fewer bytes than asked; a short write here
        # would be a torn JSON record despite the fsync. Loop to complete.
        view = memoryview(line)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if not existed:
        dfd = os.open(os.path.dirname(os.path.abspath(path)) or ".", os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    return path


def _report_dropped_write(
    db_path: str,
    turn_kind: str,
    raw_text: str | None,
    kwargs: dict,
    error: BaseException,
    stage: str,
    attempt_id: str | None = None,
) -> None:
    """Failed enabled write: dead-letter the payload, log ERROR; if even the
    dead-letter append fails, say the payload is LOST at CRITICAL. Never
    raises — the reply path ships regardless."""
    prefix = (
        "shadow ledger writer init failed"
        if stage == "init"
        else "shadow ledger write failed"
    )
    try:
        path = _dead_letter(
            db_path, turn_kind, raw_text, kwargs, error, stage, attempt_id
        )
        _LOGGER.error(
            "%s (kind=%r): %s — payload dead-lettered to %s",
            prefix, turn_kind, error, path,
        )
    except Exception as dl_error:
        _LOGGER.critical(
            "%s (kind=%r): %s — AND the dead-letter append failed (%s); "
            "the payload is LOST",
            prefix, turn_kind, error, dl_error,
        )


def try_write_turn(
    db_path: str,
    turn_kind: str,
    raw_text: str | None,
    **kwargs,
) -> str | None:
    """Open a LedgerWriter, write one turn, close. Never raises.

    Daemon callers use this so a ledger failure (writer disabled, DB
    missing, validation error, SQL error, anything) does NOT break the
    user-facing reply path.

    A failure while writes are ENABLED is never silent: the full payload
    is dead-lettered to ``<db_path>.deadletter.jsonl`` (fsynced, for later
    reconcile/replay) and the failure logs at ERROR; if even the
    dead-letter append fails, the loss is named at CRITICAL. The disabled
    path is a silent no-op exactly as before.

    Returns the new turn_id on success, or None on disabled-writer /
    failure. The single-call shape keeps the daemon plumbing to one
    line per write.

    Per the architectural invariant: shadow writes only. The user
    reply ships regardless of what happens here.
    """
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        return None

    # Owner routing: a process that claimed ledger ownership holds ONE
    # long-lived writer (and the owner latch with it) — a per-call writer
    # here would collide with our own latch. Everything below this line
    # is the non-owner / unclaimed-process path.
    from core.ledger import owner as _owner

    if _owner.this_process_is_owner():
        return _owner.owner_write_turn(db_path, turn_kind, raw_text, **kwargs)

    # Attempt identity, minted BEFORE any attempt: the same id names this
    # submission whether it commits, dead-letters, or vanishes mid-flight.
    # (The schema cannot yet enforce uniqueness on it — recorded as the
    # admission-protocol gap in the council synthesis; this is the seam.)
    attempt_id = uuid.uuid4().hex

    try:
        w = LedgerWriter(db_path)
    except Exception as e:
        _report_dropped_write(
            db_path, turn_kind, raw_text, kwargs, e, "init", attempt_id
        )
        return None
    try:
        return w.write_turn(turn_kind, raw_text, **kwargs)
    except Exception as e:
        _report_dropped_write(
            db_path, turn_kind, raw_text, kwargs, e, "write", attempt_id
        )
        return None
    finally:
        try:
            w.close()
        except Exception:
            pass
