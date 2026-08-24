# U5 design council — the witness was pointed at the wrong thing

Convened 2026-08-23 BEFORE writing the U5 harness, per the standing directive
to use the council when unsure. One seat has reported; two are still out. Its
central findings are **verified in the code**, not accepted on assertion.

## The claim T5/U5 exist to support is FALSE TODAY, and U5 could not have caught it

`core/ledger/writer.py:612-620` — the only production write path:

    try:
        return w.write_turn(turn_kind, raw_text, **kwargs)
    except Exception as e:
        _LOGGER.warning("shadow ledger write failed (kind=%r): %s", turn_kind, e)
        return None

**Every** production write silently drops on **any** error, including
`SQLITE_BUSY`. The Theme-2 claim is "the ledger cannot omit or misdate a life".
Omission is currently a caught exception and a warning line. No fencing
witness, green or red, can make that claim true while this stands.

`core/ledger/model_reply_persistence.py:86` — `sqlite3.connect(db_path)` then
`commit()`, with **no `busy_timeout` and no `BEGIN IMMEDIATE`**. It fails at
0 ms under any contention, and U5's two-fenced-writers design would never have
exercised it.

## The topology U5 would certify is not the one production runs

`core/ledger/writer.py:603` constructs `LedgerWriter(db_path)` and closes it
per call, so the per-instance `threading.Lock` at :209 serializes nothing
across calls — the class docstring's "a single threading.Lock serializes the
entire critical section" is false for the only path production uses.
Production is >=3 processes (daemon, maez-web, `cli/maez_chat.py:804`) with
unbounded connections, not U5's two long-lived writers.

Worse: the SQLite defect at issue is a WAL-**reset** defect, and closing the
last connection resets the WAL. Per-write connection churn MAXIMISES the
hazard; U5's two long-lived processes are the shape that MINIMISES it. A green
U5 would have understated production's exposure while appearing to certify it.

## Integrity currently depends on an environment variable that silently vanishes

Verified live: bare `.venv/bin/python3` links **3.46.1** (inside the WAL-reset
window); with `LD_LIBRARY_PATH=vendor/sqlite/lib` it links **3.53.4**. The
systemd drop-ins set it for `maez.service` and `maez-web.service`.
`cli/maez_chat.py` is **not a unit** — it writes the ledger at :804 under
3.46.1. An integrity property a missing env var disables is not an integrity
property.

## Recommended direction (pending the other two seats)

Make the daemon the single serialized ledger owner holding ONE long-lived
writer; have the web surface, the CLI and `model_reply_persistence` enqueue
through the `/message` rail that already exists
(`daemon/maez_daemon.py:12971`, already used by the cockpit proxy). Keep WAL —
the readers are `mode=ro` and want reader/writer concurrency. Then
`require_fixed()` becomes defence-in-depth rather than the load-bearing
guarantee, because the reset defect does not apply to a single writer even on
3.46.1.

This is nearly free right now: the ledger is 0 bytes and `MAEZ_LEDGER_WRITES`
is unset everywhere. There is no live ledger to migrate and no running writer
to disturb. It also deletes U5, O-6's latch blocker, and the standing WAL
rule's tension in one move.

**Fix the two bugs above first and independently of any topology decision.**
