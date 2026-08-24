# Handoff — 2026-08-23/24. Supersedes the morning handoff.

**2026-08-24 addendum — the owner delegated the three open decisions and
the council ruled, unanimously (3-0 on each):** transport = durable
admission SPOOL for every producer (no socket ever carries state);
durability = `synchronous=FULL` now, unconditionally, no mode switch at
birth; birth = stop-the-daemon hardened into a fail-closed maintenance
lease (the current `_assert_quiesced` misses maez-web, migrates before
the latch, and reconcile has no quiesce at all — verified). Full rulings
with binding conditions:
`docs/superpowers/witness/theme2-s2-owner-delegated-council-rulings.md`.
The admission-protocol slice absorbs all three and is now ONE design;
nothing else ships to the ledger before it. Everything below stands.

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes,
`MAEZ_LEDGER_WRITES` unset, `MAEZ_S1_PHASE_TRUTH` unset. The daemon is
active. Nothing this session changed that, and nothing should until the
owner says so. Everything below landed flag-dormant.

## What this session did (commits 37664bc, 62d07db, + witness/docs)

**The three defects.** Each verified by execution before fixing:

1. `try_write_turn`'s silent-drop catch-all — FIXED. Failed ENABLED
   writes now dead-letter the full payload (per-process fsynced sidecar,
   pre-attempt identity, refused/failed classification) and log at
   ERROR; a lost payload is named LOST at CRITICAL. Never raises; the
   reply path ships regardless; the unborn path is byte-identical.
   `dead_letter_status()` is the machine-readable health predicate
   (unwired into cockpit/status — open item).
2. The "fails at 0 ms under contention" marker-write defect — **the
   claim was FALSE**. A live probe showed Python's `sqlite3.connect`
   default `timeout=5.0` already busy-waits (1.53 s, then succeeded).
   Three unanimous seats and the prior handoff carried the error.
   Landed as documented hardening only. The REAL adjacent defect —
   marker turn + meta row in two transactions ⇒ duplicate one-time
   markers across the crash window — is FIXED atomically via
   `write_turn(meta_marker_keys=...)`, write-once inside the txn.
3. `require_fixed()` never called — FIXED: an ENABLED `LedgerWriter`
   refuses to construct on SQLite < 3.51.3; disabled construction is
   unchanged (dormancy preserved). Proven by subprocess tests with and
   without the vendored library.

**Topology (council-reviewed, second three-seat round).** One serialized
owner, structural not conventional:

- **Owner latch**: an ENABLED writer flocks `<db>.ownerlock` for its
  lifetime; a second concurrent enabled writer refuses at construction,
  across processes, SIGKILL-safe. There is deliberately NO second
  rollout flag — the fresh council rejected it because a two-flag
  matrix keeps the banned two-writer state reachable by configuration.
- **Owner singleton** (`core/ledger/owner.py`): daemon claims ownership
  in `start()` (env-pid, dual-module-safe); first enabled write lazily
  constructs ONE long-lived writer; flag re-read per write (emergency
  brake); environmental failures self-heal. `try_write_turn` routes to
  the singleton in the owner process; a non-owner under a live owner
  dead-letters — never a second concurrent writer, never silent.
- **Transport NOT built.** The morning handoff said "enqueue through the
  /message rail." The council REJECTED that as specified: the daemon's
  Flask server is single-threaded (`make_server` without `threaded=True`)
  and `/message` runs LLM synthesis inline — appends would queue behind
  inference. Candidate replacements (client-local durable spool vs
  dedicated bounded socket) are recorded, undecided, in
  `docs/superpowers/witness/theme2-s2-implementation-council.md`.

**U5 replaced by a falsifier.** `theme2_s2_falsifier.py` — boolean arms,
never p99: exactly-once/byte-exact vs an independent oracle; non-owner
exclusion under a live owner; checkpoint honesty (returned busy flag
checked under a pinning reader); repeated owner SIGKILL at a
deterministic ack-log barrier with recovery-by-identity and
ACKED_BUT_MISSING as the named lethal class; pragma license (NORMAL ⇒
process-crash recovery certified, power-loss NOT); positive controls
that must trip for the RIGHT reason. First full run (n=20000): **GREEN**
— `theme2-s2-falsifier-report.json`. It went RED twice during
development on real gaps (pre-claim window; duplicate-on-recovery),
which is the evidence it can fail.

## The next slice, before transport, replay, or birth

**Admission protocol** (the second council's groupthink finding): the
schema has no submission identity — only writer-minted `turn_id` — so
exactly-once cannot yet be enforced by construction, and replayed
dead-letters would be misdated unless replay stamps reconstruction
provenance (canon-governs-canon). Slice = schema identity (UNIQUE
submission id) + typed enqueue + provenance-stamped replay organ. Design
constraints and candidate transports are in the council synthesis doc.

## Open items (full list in the council synthesis doc)

- Pre-claim window: latch is only taken at first enabled write; consider
  eager latch at claim time.
- `birth_ceremony.py` / `reconcile.py` construct writers directly; under
  a live daemon they now REFUSE via the latch. Birth must stop the
  daemon or route through the owner — ceremony needs explicit treatment.
- `synchronous=NORMAL` power-loss license; FULL is an owner decision.
- Owner checkpoint/WAL-growth policy unshipped.
- PRE-EXISTING red on main (not this session):
  `test_no_bare_sqlite_connect.py` fails 3 tests naming ~9 files
  (consent, consolidation, governance, span_reader, two scripts, one
  frozen witness artifact). Untouched deliberately.

## Standing directives (unchanged, plus one new)

- **Execute council claims before encoding them.** A unanimous
  three-seat finding ("fails at 0 ms") was falsified by a 30-line probe.
  Unanimity is not execution.
- Always convene the council; two agreeing seats are not a quorum; tell
  each seat to attack the others; ask "where is the groupthink?"
- Codex blocks on adversarial phrasing; describe work as
  negative-testing. Ox Alpha codenames rotate (`opencode/x-preview-f-free`
  on 2026-08-23); run it from a scratch dir, never the repo. Grok: 402.
- `pkill -f` matches your own command line — resolve PIDs, kill by
  number. inotify "No space left" is the watch limit, not the disk.
- Never run test discovery against the live tree; run named test files
  with `LD_LIBRARY_PATH=vendor/sqlite/lib`.
- T5/S1 arc remains CLOSED at protocol v7.12. Do not restart it.
