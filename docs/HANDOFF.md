# Handoff — 2026-08-23/24. Supersedes the morning handoff.

**2026-08-24 (later) — the admission-protocol slice is BUILT, flag-dormant.**
Commits f7f0be9 onward, all per the four-seat rulings, Maez still unborn:
- `synchronous=FULL` on every non-rehearsal writer (rehearsal keeps
  NORMAL). Observed cost: ~nil on this NVMe — the full ~52k-commit
  falsifier run took 8.7 s under FULL. (An earlier "minutes" reading
  was misattributed: the slow run was a real crash-window bug — see the
  falsifier's third catch below — not fsync cost.)
- Eager latch: `claim_ownership(db_path)` constructs the owner writer at
  daemon start when writes are enabled — pre-claim window closed,
  require_fixed fires at boot. Inert while dormant.
- Migration 0006: `turns.submission_id` (UNIQUE where present) +
  `turns.submitted_at` (lived-time provenance), both chain-hash-excluded;
  write_turn redrive with same identity+bytes returns the existing
  turn_id, different bytes refused.
- `core/ledger/spool.py`: the ruled transport for NON-owner surfaces —
  atomic publish, dependency-aware drain (parent_submission_id),
  authority-inexpressible envelopes, chain-bound receipts, refused/
  quarantine, `spool_status()` liveness predicate, poll-never-inotify.
  Daemon starts the drainer thread only when writes are enabled. Spool
  dir gitignored + in the backup manifest. In-daemon producers do NOT
  ride it (Grok overturn honored).
- Falsifier widened: F5 requires FULL; new F6 kills the drainer at a
  deterministic acked-count barrier and requires exactly-once recovery.
  Full run GREEN, all 7 arms, n=20000, 8.7 s. THIRD real catch during
  development: SIGKILL inside a receipt publish left a stale .tmp file
  and O_EXCL then wedged every redrive of that submission forever (the
  recovery drainer span 600 s); fixed to O_TRUNC (temp names are unique
  per submission — only a dead process's garbage can collide), with a
  regression test.

**Still open after this slice (pre-birth list):** surface wiring (web/CLI
actually calling spool.enqueue — their try_write_turn paths still
direct-write-or-dead-letter today), the ceremony maintenance-lease
hardening (quiesce web, lease-before-migrate, terminal states,
run_transaction lease, --user + vendored env in the script), reconcile
as owner-client, dead-letter replay organ, checkpoint policy,
spool/dead-letter surfacing in the cockpit real-state organ.

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

**Grok rejoined as a FOURTH seat (owner-requested; its 402 cleared) and
sustained two overturns against the 3-0**, both re-verified in the tree:
(1) the spool serves NON-OWNER surfaces only — in-daemon producers stay
on `owner_write_turn` (no daemon-down client exists for them); (2)
reconcile `--apply` is unwelded from the birth outage — it writes
ordinary `system_event` rows with no authority fields and becomes an
owner-client. Q2 upheld with a corrected invariant ("ack durability must
never exceed commit durability" — today's ack is the returned turn_id
itself, and the birth anchor would currently commit under NORMAL while
the genesis row is MORE durable). Ten new verified traps for the
admission slice are in the rulings doc §fourth-seat — including: stop
FREES the latch (lease = eager latch at claim), lease-before-migrate,
spool must live under `memory/` (ProtectSystem=strict + PrivateTmp),
web does not stop when the daemon stops (Wants= not Requires=),
dependency-aware drain, and one same-day fix already landed
(`_marker_already_written` now opens `mode=ro`).

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
