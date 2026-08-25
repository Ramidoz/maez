# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Single serialized ledger owner — process side.

The U5 design council ruled (three seats, unanimous): production must not
run two concurrent WAL writers on the ledger. This module is the shape
that replaces per-call open-write-close churn in the process that owns
the ledger (the daemon): ONE long-lived :class:`LedgerWriter` behind one
process-wide lock, holding the on-disk owner latch for its lifetime.

Ownership is claimed explicitly (`claim_ownership()`, called by the
daemon at startup) and recorded as this process's pid in ``os.environ``
— environment state is process-wide, so the check survives the
``python -m`` dual-module-identity hazard where two copies of a module
hold two copies of a module-global. A forked child inherits the env var
but has a different pid, so it is correctly NOT the owner.

Dormancy: nothing here activates unless MAEZ_LEDGER_WRITES is enabled.
The flag is re-read on EVERY write, so unsetting it remains an emergency
brake even though the writer is long-lived.
"""
from __future__ import annotations

import logging
import os
import threading

from core.ledger.writer import (
    LedgerWriter,
    _REFUSAL_ERRORS,
    _report_dropped_write,
)

__all__ = ["claim_ownership", "this_process_is_owner", "owner_write_turn",
           "live_writer_connection"]

_LOGGER = logging.getLogger("core.ledger.owner")

_OWNER_PID_ENV = "MAEZ_LEDGER_OWNER_PID"

_lock = threading.Lock()
_writer: LedgerWriter | None = None
_writer_db_path: str | None = None
_constructions = 0


def claim_ownership(db_path: str | None = None) -> None:
    """Mark THIS process as the single serialized ledger owner.

    With ``db_path`` and writes ENABLED, the owner writer is constructed
    EAGERLY — taking the on-disk latch now, not at the first write.
    Council trap #3 (2026-08-24): a lazily-taken latch leaves a
    pre-claim window in which any enabled process can become the writer;
    "stop the daemon" is an invitation, not a lease, unless the restarted
    owner closes that window immediately. Eager construction also fires
    require_fixed() at startup — a daemon on the wrong SQLite fails at
    boot, not at the first life-event. Raises on eager failure; inert
    (no latch, no files) while writes are disabled.
    """
    os.environ[_OWNER_PID_ENV] = str(os.getpid())
    if db_path is None:
        return
    from core.ledger.writes_flag import ledger_writes_enabled

    if not ledger_writes_enabled():
        return
    with _lock:
        try:
            _ensure_writer_locked(db_path)
        except BaseException:
            # Codex validation round (2026-08-24): the marker must not
            # outlive a failed claim. A process that could not take the
            # latch is NOT the owner — leaving the marker set would make
            # this_process_is_owner() true, so surfaces would route
            # owner-direct and dead-letter instead of spooling, while
            # the real owner lives elsewhere.
            os.environ.pop(_OWNER_PID_ENV, None)
            raise


def _ensure_writer_locked(db_path: str) -> LedgerWriter:
    """Construct/reuse the long-lived writer. Caller holds ``_lock``."""
    global _writer, _writer_db_path, _constructions
    if _writer is None or _writer_db_path != db_path:
        if _writer is not None:
            try:
                _writer.close()
            except Exception:
                pass
            _writer = None
            _writer_db_path = None
        _writer = LedgerWriter(db_path)
        _writer_db_path = db_path
        _constructions += 1
    return _writer


def this_process_is_owner() -> bool:
    return os.environ.get(_OWNER_PID_ENV, "") == str(os.getpid())


def live_writer_connection(db_path: str):
    """The owner's live connection for this db, or None.

    READ-ONLY use by health surfaces: per-connection PRAGMA state (e.g.
    ``wal_autocheckpoint``) can only be read truthfully from the
    connection that actually holds it. Never write through this.
    """
    if _writer is None or _writer_db_path != db_path:
        return None
    return getattr(_writer, "_conn", None)


def owner_write_turn(
    db_path: str,
    turn_kind: str,
    raw_text: str | None = None,
    **kwargs,
):
    """Append one turn through the owner's long-lived writer. Never raises.

    Same caller contract as ``try_write_turn`` (turn_id or None; failures
    dead-letter and log at ERROR/CRITICAL; the reply path ships
    regardless), but without per-write connection churn — churn is the
    shape that maximises the WAL-reset hazard, and it makes the writer's
    serializing lock meaningless.

    Self-healing: an environmental write failure drops the cached writer
    so the next write reconstructs it (a broken connection must not
    poison every subsequent write). Deterministic payload refusals keep
    the writer — nothing is wrong with the connection.
    """
    global _writer, _writer_db_path, _constructions

    import uuid

    from core.ledger.writes_flag import ledger_writes_enabled

    # Attempt identity minted before any attempt — see try_write_turn.
    attempt_id = uuid.uuid4().hex
    # ...and PERSISTED on the committed row (2026-08-24 replay council):
    # without it, "did this dead-letter record actually commit?" is
    # answerable only by byte archaeology, and a timeout-after-commit
    # would look identical to a genuine loss. With it, the dead-letter
    # event_id and the row's submission_id are the same key — an exact
    # lookup — and an owner redrive is idempotent by identity.
    # An explicit submission_id (the spool drainer's) always wins.
    kwargs.setdefault("submission_id", attempt_id)

    with _lock:
        if not ledger_writes_enabled():
            return None
        try:
            _ensure_writer_locked(db_path)
        except Exception as e:
            _report_dropped_write(
                db_path, turn_kind, raw_text, kwargs, e, "init", attempt_id
            )
            return None
        try:
            return _writer.write_turn(turn_kind, raw_text, **kwargs)
        except Exception as e:
            _report_dropped_write(
                db_path, turn_kind, raw_text, kwargs, e, "write", attempt_id
            )
            if not isinstance(e, _REFUSAL_ERRORS):
                try:
                    _writer.close()
                except Exception:
                    pass
                _writer = None
                _writer_db_path = None
            return None


def owner_commit(
    db_path: str,
    turn_kind: str,
    raw_text: str | None,
    **kwargs,
) -> tuple[str, object]:
    """Serialized commit with a CLASSIFIED outcome, for the spool drainer.

    Returns ('acked', turn_id) | ('refused', error) | ('failed', error).
    The distinction owner_write_turn cannot express (it returns None for
    both) is load-bearing here: a refusal is quarantined terminally,
    a failure stays pending for redrive. Never raises.
    """
    global _writer, _writer_db_path

    from core.ledger.writes_flag import ledger_writes_enabled

    with _lock:
        if not ledger_writes_enabled():
            return ("failed", RuntimeError("ledger writes disabled"))
        try:
            w = _ensure_writer_locked(db_path)
        except Exception as e:
            return ("failed", e)
        try:
            tid = w.write_turn(turn_kind, raw_text, **kwargs)
        except _REFUSAL_ERRORS as e:
            return ("refused", e)
        except Exception as e:
            try:
                w.close()
            except Exception:
                pass
            _writer = None
            _writer_db_path = None
            return ("failed", e)
        if tid is None:
            return ("failed", RuntimeError("writer returned no turn_id"))
        return ("acked", tid)


def _reset_for_tests() -> None:
    """Close and forget the singleton and unclaim ownership. Tests only."""
    global _writer, _writer_db_path, _constructions
    with _lock:
        if _writer is not None:
            try:
                _writer.close()
            except Exception:
                pass
        _writer = None
        _writer_db_path = None
        _constructions = 0
    os.environ.pop(_OWNER_PID_ENV, None)


def _writer_constructions_for_tests() -> int:
    return _constructions
