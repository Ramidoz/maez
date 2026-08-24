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

__all__ = ["claim_ownership", "this_process_is_owner", "owner_write_turn"]

_LOGGER = logging.getLogger("core.ledger.owner")

_OWNER_PID_ENV = "MAEZ_LEDGER_OWNER_PID"

_lock = threading.Lock()
_writer: LedgerWriter | None = None
_writer_db_path: str | None = None
_constructions = 0


def claim_ownership() -> None:
    """Mark THIS process as the single serialized ledger owner."""
    os.environ[_OWNER_PID_ENV] = str(os.getpid())


def this_process_is_owner() -> bool:
    return os.environ.get(_OWNER_PID_ENV, "") == str(os.getpid())


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

    with _lock:
        if not ledger_writes_enabled():
            return None
        try:
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
