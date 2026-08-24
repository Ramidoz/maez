# Handoff — 2026-08-23. Read this before the older handoff.

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes,
`MAEZ_LEDGER_WRITES` unset, `MAEZ_S1_PHASE_TRUTH` unset. The daemon is
active. Nothing here changes that, and nothing should until the owner says so.

## Do these three first. They are independent of every open design question.

Theme 2's claim is "the ledger cannot omit or misdate a life". **It is false
today**, and no witness — green or red — can make it true while these stand:

1. **`core/ledger/writer.py:612-620`** — the only production write path wraps
   `w.write_turn(...)` in `except Exception` → log a warning → `return None`.
   Every write silently drops on any error, including `SQLITE_BUSY`. Omission
   is currently a caught exception.
2. **`core/ledger/model_reply_persistence.py:86`** — bare
   `sqlite3.connect(db_path)` then `commit()`: no `busy_timeout`, no
   `BEGIN IMMEDIATE`. Fails at 0 ms under contention.
3. **`core/infra/sqlite_runtime.py:84`** — `require_fixed()` exists and is
   **never called**. Reporting the linked SQLite version at boot is not the
   same as refusing to run on a vulnerable one. Call it at writer construction.

All three were found by the U5 design council and verified in the code, not
accepted on assertion.

## The U5 ruling: unanimous, three independent seats — DO NOT BUILD U5 AS FROZEN

Full rulings retained: `docs/superpowers/witness/theme2-s2-u5-council-finding.md`
(seat 1, with the verified code citations), `…-seat2.txt` (Codex), `…-seat3.txt`.

**Why not.** U5 would certify two concurrent WAL writers — a topology
production does not run and the project's own standing rule forbids.
`writer.py:603` builds and closes a connection PER WRITE, so the
`threading.Lock` at :209 serializes nothing and the class docstring is false
for the only live path. Production is ≥3 processes (daemon, maez-web,
`cli/maez_chat.py:804`) with unbounded connections. The SQLite defect is a WAL
**reset** defect and closing the last connection resets the WAL — so per-write
churn MAXIMISES the hazard while U5's two long-lived writers MINIMISE it. A
green U5 would understate exposure while appearing to certify it.

Also: SQLite's own team reports that ordinary stress could not reproduce the
defect; special instrumentation was required. 1000 ordinary exchanges prove
nothing about it. And the deepest objection, from seat 3: *even perfectly
executed, green certifies latency under benign conditions, not
non-corruption. Green is fully compatible with unsafe.*

**Ship instead:** one serialized ledger owner — the daemon holding ONE
long-lived `LedgerWriter` behind one process-wide lock. Web
(`skills/web_interface.py:6824`), CLI (`cli/maez_chat.py:804`) and
`model_reply_persistence.py` enqueue through the `/message` rail that already
exists at `daemon/maez_daemon.py:12971` (the cockpit proxy already uses it).
**Keep WAL** — readers are `mode=ro` and want reader/writer concurrency;
reject WAL2 (not mainline, not in 3.53.4). Under one writer the reset defect
does not apply even on 3.46.1, so the vendored build becomes defence-in-depth
rather than the load-bearing guarantee.

Nearly free right now: 0-byte ledger, writes flag unset everywhere. Nothing to
migrate, no writer to disturb. It deletes U5, O-6's latch blocker, and the
standing WAL-rule tension in one move.

**Replace U5 with a falsifier, not a statistic.** Tens of thousands of
deterministic appends (payload = f(index)) through the REAL topology; verify
every row present exactly once and byte-exact; `PRAGMA integrity_check`;
forced `wal_checkpoint(TRUNCATE)` under concurrent write load; then repeatedly
SIGKILL a writer mid-batch and verify recovery — crash recovery is where WAL
defects live. Never p99: safety claims are booleans and booleans have no
percentiles. If a timing component survives, kill on MAX over a hard budget
with CLOCK_MONOTONIC, and assert the positive control tripped for the RIGHT
REASON (refusal at ≈5000 ms), not merely that it tripped.

## The T5 arc is CLOSED. Do not restart it.

Protocol **v7.12**. Rounds 25-33 found ~50 defects; that proved the method
worked AND that it is finished. The closure ritual is replaced by a dated risk
register of disclaimed classes, reopened only on a producer-interface change
or on the flag being un-dormanted. §0.4's licensed claim is adopted
unconditionally and states plainly that PASS does not establish authenticity
against a malicious evidence author and does not certify any clause no test
exercises. Two known open items are recorded, not hidden, in
`theme2-s1-clause-coverage.md`.

Current evidence: `witness/evidence/discriminator-2026-08-23-r32/`, all clauses
PASS. Four superseded evidence sets are retained and fail on purpose.

## Standing directives

- **Always convene the council; two agreeing seats are not a quorum.** Tell
  each seat what the others concluded and instruct it to ATTACK them. Ask
  "where is the groupthink?" — it produced the best finding of the day. See
  memory `use-the-council-when-unsure` for how to reach each seat.
- Codex blocks on adversarial phrasing ("forgery", "attack"); describe work
  accurately as negative-testing. Two blocks = lane closed for that framing;
  do not keep rewording to slip a refusal.
- Ox Alpha via `opencode run --model <codename>`; codenames ROTATE, ask which.
  Run from a small scratch dir, never the repo. Grok: HTTP 402, out of credit.
- `pkill -f` MATCHES MY OWN COMMAND LINE — it killed my shell twice today and
  the aborted commands' side effects looked like three unrelated bugs. Resolve
  PIDs and kill by number.
- `inotify_add_watch ... No space left on device` is NOT a full disk. The
  watch limit was raised to 524288 today (`sysctl`, may not persist).
