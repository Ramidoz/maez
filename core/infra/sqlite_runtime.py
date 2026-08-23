# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Which SQLite is this process actually running on?

2026-08-23. Ubuntu 26.04 ships SQLite 3.46.1 in every pocket — inside the
documented WAL-reset corruption window (multiple connections writing and
checkpointing concurrently; fixed in 3.51.3). The owner ruled: upgrade.
No apt path and no wheel reaches the fix, so 3.53.4 is built repo-local at
``vendor/sqlite`` and loaded via ``LD_LIBRARY_PATH`` in the maez systemd
units and the venv activation — deliberately NOT system-wide.

That scoping has a failure mode: a process launched without the env var
silently gets 3.46.1 and *looks identical*. Version drift you cannot see is
how the WAL rule gets violated by accident three months from now. So every
long-lived Maez process calls ``report()`` at startup: one log line always,
a WARNING when the fix is absent.

Two rules this module states so nobody re-derives them wrongly:

- The upgrade does NOT lift the no-concurrent-WAL-writers rule. The rule
  stands until S2's U5 witnesses the chosen writer topology under the fixed
  library. A newer library makes the witness *possible*, not unnecessary.
- ``require_fixed()`` exists for the code that will eventually depend on
  the fix (the ledger's multi-writer path, if U5 ever authorizes one).
  Nothing calls it today. It hard-fails, because a concurrent WAL writer
  running on 3.46.1 is precisely the corruption we spent the upgrade
  avoiding.
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger("maez.sqlite_runtime")

#: First release with the WAL-reset fix (backports 3.44.6 / 3.50.7 also
#: carry it, but nothing on this host can reach those).
FIXED = (3, 51, 3)


def version_tuple() -> tuple[int, int, int]:
    parts = [int(x) for x in sqlite3.sqlite_version.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)  # type: ignore[return-value]


def has_wal_reset_fix() -> bool:
    return version_tuple() >= FIXED


def report(where: str = "") -> str:
    """One line, every startup. Visible version = auditable version.

    The daemon calls this before logging is configured, and Python's
    last-resort handler only surfaces WARNING and above — so the first
    version of this function announced the BAD state loudly and the good
    state not at all. A check whose success is invisible cannot be told
    apart from a check that never ran; when no handler exists yet, the good
    line goes to stderr directly (the unit appends stderr to maez.log).
    """
    import sys as _sys

    v = sqlite3.sqlite_version
    if has_wal_reset_fix():
        line = (f"sqlite {v} (WAL-reset fix present)"
                f"{f' [{where}]' if where else ''}")
        logger.info("%s", line)
        if not logging.getLogger().hasHandlers():
            _sys.stderr.write(line + "\n")
    else:
        logger.warning(
            "sqlite %s is INSIDE the WAL-reset corruption window (< 3.51.3)."
            " This process was launched without the vendor library — check"
            " LD_LIBRARY_PATH / the systemd drop-ins. Single-writer discipline"
            " is MANDATORY on this version.%s",
            v, f" [{where}]" if where else "")
    return v


def require_fixed(what: str) -> None:
    """Hard gate for code that depends on the fix. Unused until U5 lands."""
    if not has_wal_reset_fix():
        raise RuntimeError(
            f"{what} requires SQLite >= 3.51.3 (WAL-reset fix); this process "
            f"is linked against {sqlite3.sqlite_version}. Refusing — a "
            f"concurrent WAL writer on this version risks the exact "
            f"corruption the vendor build exists to prevent.")
