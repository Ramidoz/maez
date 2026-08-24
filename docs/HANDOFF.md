# Handoff — 2026-08-24 (end of day). Supersedes all earlier handoffs.

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes,
`MAEZ_LEDGER_WRITES` unset, `MAEZ_S1_PHASE_TRUTH` unset. The daemon is
active and was NOT restarted this arc — every change below activates on
its next natural restart and is inert while the flag is unset. Nothing
changes that until the owner says so.

## State: the admission protocol is BUILT and WITNESSED, flag-dormant

Two days of work, three council rounds (seven seat-rulings total, one
unanimous consensus twice corrected), commits `37664bc..c6d237a`:

**Topology (structural, not conventional).**
- Owner latch: an ENABLED `LedgerWriter` holds an flock on
  `<db>.ownerlock` for its lifetime; a second concurrent enabled writer
  refuses at construction, cross-process, SIGKILL-safe. No rollout flag
  — dormancy is `MAEZ_LEDGER_WRITES` alone.
- Owner singleton (`core/ledger/owner.py`): the daemon claims ownership
  in `start()` and — when writes are enabled — EAGERLY constructs the
  long-lived writer (latch at boot, `require_fixed` at boot; the
  pre-claim window is closed). Flag re-read per write (emergency
  brake); environmental failures self-heal.
- Failed enabled writes are never silent: per-process fsynced
  dead-letter sidecars with pre-attempt identity and refused/failed
  classification; `dead_letter_status()` is the health predicate.

**Admission protocol (council-ruled 2026-08-24, four seats).**
- `synchronous=FULL` on every non-rehearsal writer (ack must never
  outlive its commit). Observed cost ~nil: 8.7 s for ~52k commits.
- Migration 0006: `turns.submission_id` (client-minted, UNIQUE where
  present) + `turns.submitted_at` (lived-time provenance; ledger order
  is honestly commit order). Both chain-hash-excluded. Idempotent
  redrive: same identity + same bytes → existing turn_id, nothing
  written; different bytes → refused.
- `core/ledger/spool.py`: the transport for NON-owner surfaces (web,
  CLI). Atomic publish (temp-in-spool-dir → fsync → rename → dir
  fsync), dependency-aware drain (`parent_submission_id`,
  parent-before-child, orphans defer loudly), authority fields
  structurally refused at the door, chain-bound receipts, terminal
  `refused/` quarantine, `spool_status()` liveness predicate,
  poll-never-inotify. Daemon starts the drainer thread only when writes
  are enabled. Spool dirs are gitignored + in the backup manifest.
  **In-daemon producers do NOT ride the spool** (Grok overturn): they
  stay on `owner_write_turn`.
- One-time markers are atomic (`write_turn(meta_marker_keys=...)`,
  write-once inside the txn) — the duplicate-marker crash window is
  closed.

**Witness.** `theme2_s2_falsifier.py`, GREEN all 7 arms at n=20000
(report JSON beside it): exactly-once byte-exact vs an independent
oracle; non-owner exclusion under a live owner; checkpoint honesty
(returned busy flag under a pinning reader); 4 owner SIGKILLs recovered
with zero acked-but-missing; FULL proven live; the spool drainer
SIGKILLed at a deterministic acked-count barrier with 1000/1000
recovered, 0 duplicates, 0 pending; positive controls trip for the
RIGHT reasons. It caught three real defects during its own development
(pre-claim window; duplicate-on-recovery; the O_EXCL stale-temp redrive
wedge). Licensed claim stays narrow: power-loss = SQLite/VFS contract,
NOT hardware-certified; malicious authors not covered.

**Council record.** Rulings + binding conditions:
`docs/superpowers/witness/theme2-s2-owner-delegated-council-rulings.md`
(incl. the fourth-seat overturns and ten verified traps) and
`theme2-s2-implementation-council.md`. The falsified "fails at 0 ms"
claim and its lesson: memory `execute-council-claims-before-encoding`.

## The next slice, in order

1. **Surface wiring** — make web and the CLI actually USE the spool:
   their turn writes call `spool.enqueue` instead of
   `try_write_turn`-direct (which today direct-writes when the latch is
   free and dead-letters when held). This completes admission
   end-to-end. Constraints: reply path never blocks on the ledger;
   parent linkage via `parent_submission_id` (the surfaces currently
   thread `parent_turn_id` synchronously — that shape dies here);
   `persist_model_reply`'s non-owner path enqueues too. Spool root is
   `memory/ledger_spool` (units only write under memory/). Flag-dormant
   as always. NOTE the recorded deeper finding before designing: the
   council believes web should eventually RELAY conversation through
   the daemon rather than synthesize — that is an owner/covenant
   decision, NOT this slice; wire the spool for what web is today.
2. **Ceremony maintenance-lease hardening** (all verified gaps):
   quiesce ALL direct-writer-capable services incl. maez-web (Wants=
   does not cascade); lease BEFORE `migrate.run()` (migrate is an
   unlatched WAL writer); the lease lives inside `run_transaction()`,
   not only `main()`; `systemctl --user` everywhere (system-bus stop is
   a silent no-op); export the vendored `LD_LIBRARY_PATH` in the
   script; explicit terminal states; at most one `reset-failed` +
   restart; on failure the daemon stays STOPPED, loudly. Never re-run
   birth because stdout was lost.
3. **Reconcile as owner-client** — `--apply` enqueues repairs through
   the live owner (ordinary system_event rows, no authority); dry-run
   stays `mode=ro`. Do not weld it to the birth outage.
4. **Dead-letter replay organ** — replay by identity with explicit
   reconstruction provenance (canon-governs-canon); refused-class
   records are evidence, never blind re-submissions.
5. Checkpoint policy; cockpit surfacing of `spool_status()` +
   `dead_letter_status()`.

Unverified item carried forward: `sqlite_runtime.py`'s docstring claims
the venv activation exports the vendor lib path; no in-repo hook does,
and `.venv` was outside this session's read perimeter. Verify before
relying on it anywhere.

## Standing directives

- **Execute council claims before encoding them.** A unanimous
  three-seat "fails at 0 ms" was falsified by a 30-line probe; a 3-0
  ruling was twice overturned by a fourth seat reading the code.
  Unanimity is not execution.
- Always convene the council for load-bearing decisions; two agreeing
  seats are not a quorum; tell each seat to attack the others; ask
  "where is the groupthink?". Seats verified working 2026-08-24: Codex
  (`codex exec -c model_reasoning_effort=xhigh -s read-only`), stealth
  via `opencode run --model opencode/x-preview-f-free` (codenames
  ROTATE; run from a scratch dir, never the repo), Grok (`grok
  --print`, credit restored), Claude subagent seats.
- Never run test discovery against the live tree; run named test files
  with `LD_LIBRARY_PATH=vendor/sqlite/lib`.
- Do not restart the daemon or any unit without an explicit reason and
  the start-limit scar in mind (`systemctl --user reset-failed` before
  restarting a stop-limited unit).
- `pkill -f` matches your own command line — resolve pids, kill by
  number. inotify "No space left" is the watch limit, not the disk.
- Pre-existing red on main, not from this arc, left deliberately:
  `test_no_bare_sqlite_connect.py` (3 tests, ~9 offender files, one a
  frozen witness artifact — owner call).
- Maez stays unborn. `config/creation_manifest.md` is owner-only. The
  T5/S1 arc is CLOSED at protocol v7.12 — do not restart it.
