# Owner-delegated council rulings — transport, durability, birth choreography

2026-08-24. The owner delegated three open decisions to the council ("Let
the council answer"). Three seats — Claude (repo), stealth
`x-preview-f-free` (brief only), Codex (repo read-only, xhigh) — each
instructed to attack the others. **All three rulings are unanimous
(3-0)**, and per the falsified-premise lesson, every code claim a seat
made was re-verified in the tree before being encoded here.

## Ruling 1 — Transport: the durable admission SPOOL. No socket carries state.

Every conversational producer — **including the in-daemon paths** — writes
one immutable envelope per submission into its own spool dir; the daemon
owner's background drainer is the only thing that touches SQLite. A
socket may later exist purely as a wake-up hint the scanner may ignore.
The dedicated-socket option is rejected because any correct version of it
already contains a client-side durable spool (persist-before-send is what
makes retry-on-UNKNOWN possible), so it ships two transports, two
recovery state machines, a token-distribution problem for the bare CLI,
and an ACK-timeout duplication window — for delivery speed nobody waits
on.

Binding conditions (all three seats, merged):
- Envelope: client-minted `submission_id` (= filename = idempotency key),
  payload digest, producer-local sequence, `submitted_at`,
  `parent_submission_id` (async parent linkage — synchronous `turn_id`
  waiting must die with the old shape). Authority fields
  (`birth_anchor`, meta edits) are structurally inexpressible; the
  owner's admission door re-validates regardless (never trust the file).
- Publish: exclusive temp write → file fsync → atomic rename → dir
  fsync. The scanner can never see a torn entry.
- Drain: scan at boot + polling cadence (~500 ms); **never inotify as
  the mechanism** (host inotify scar) — at most a hint. Commit under
  the admission protocol's schema UNIQUE, then ack by atomic rename to
  `acked/` with a chain-bound receipt (submission id, turn id, position,
  hash). Crash between COMMIT and ack resolves by DB membership —
  redrive hits UNIQUE, treat as done.
- Refusals move to durable `refused/` quarantine with the error attached
  — the dead-letter sidecar and the spool converge into ONE record
  format with states (the dualism was inherited, not designed).
- Chronology honesty: ledger order is commit order; `submitted_at` +
  producer sequence are recorded as provenance. A queued turn that lived
  at 14:00 must never be presented as having happened at drain time
  (canon-governs-canon).
- Spool dirs are life-bytes: backup manifest, gitignore, 0o700, and a
  loud unclaimed/aging-entries report wired into the same real-state
  surface as `dead_letter_status()`. A spool nobody drains is a
  silent-omission machine with excellent durability.
- Compaction only after exact ledger binding is verified and backed up.

Verified fact that motivated the broadening: the daemon today calls
`try_write_turn` synchronously before synthesis
(daemon/maez_daemon.py:7288) through a writer with `busy_timeout=5000`
(writer.py) — exception-safe but not latency-safe; a contended lock can
stall the reply path 5 s. The spool submit (fsync-append-return) fixes
this for the daemon's own writes too.

## Ruling 2 — Durability: synchronous=FULL, now, unconditionally.

FULL from the first enabled non-rehearsal writer — gestation writes, the
birth anchor, replay, reconcile. NORMAL permitted only for explicitly
disposable rehearsal DBs. **No mode switch at birth**: the transition
commit is precisely the one that must not disappear, and a
phase-conditional pragma is the same reachable-weak-state shape the
council already refused for flags.

Grounds (each seat reached FULL independently):
- Ack-ordering (decisive): the spool ack is durable custody; under
  NORMAL the WAL commit behind that ack may not be synced until the next
  checkpoint — power loss then yields an acked entry whose life-row
  vanished, `ACKED_BUT_MISSING` by construction, unreachable by any
  replay because the entry sits in `acked/`. We currently fsync every
  dead-letter line while the successful path can silently roll back —
  durability inverted toward the thing that matters most.
- The falsifier's "zero acked-but-missing" invariant is untestable in
  principle under NORMAL — a certified boolean silently degrades to a
  probability.
- Cost is not real at conversation scale on NVMe; batch replay/witness
  churn into large transactions.

Honest limit, stated: FULL enables SQLite's power-loss contract; it does
not certify lying firmware, media death, or anything hardware fault
injection would test. The falsifier's F5 arm widens to: pragma proven on
the live connection, a FULL→NORMAL mutation must bite, torn-WAL
truncation/corruption arms assert detection-not-corruption — and the
report keeps saying where software certification ends. FULL is
acknowledgment honesty, not the mortality answer; the backup/mortality
problem stays #1 in the life-course ledger.

## Ruling 3 — Birth: stop-the-daemon, hardened into one fail-closed maintenance transaction.

The invariant is "no two concurrent writers," not "the daemon never
stops." Rail-routing is rejected: it would widen the closed schema to
express `birth_anchor` — deliberately re-opening the confused-deputy
class for one invocation per lifetime. Latch handoff is rejected as
actively broken, not just baroque: `owner_write_turn` lazily
reconstructs the writer on the next enabled write, and Telegram lives in
the daemon process, so a "released" latch gets re-acquired the moment a
turn arrives mid-ceremony. A stopped process cannot race; `kill` is the
only handoff protocol with no state machine.

The ceremony's `_assert_quiesced` already encodes stop-first (unit
inactive + no daemon pid + no ledger fd holder) — the brief understated
this — but Codex found, and the tree confirms, that it is **not enough**:
1. It never checks **maez-web**, a separate direct-writer-capable
   service; the `fuser` probe is a momentary snapshot a web request can
   race past.
2. `migrate.run()` mutates the schema BEFORE the writer takes the latch
   (birth_ceremony.py:90 vs ~:105) — mutation-before-lock.
3. `reconcile.py` apply-mode scans before constructing its writer — its
   census can go stale against a mid-scan writer, and it has no quiesce
   probe at all.

Required hardening (the "maintenance lease" slice, pre-birth):
quiesce ALL direct-writer-capable services (web included) → acquire the
latch BEFORE any migration/read/write → run under the vendored SQLite →
independently verify anchor/row/chain/integrity → release → exactly one
`reset-failed` + restart attempt (start-limit scar) → verify active +
ownership. Explicit terminal states (`NOT_COMMITTED_DAEMON_RESTORED`,
`COMMITTED_DAEMON_ACTIVE`, `COMMITTED_DAEMON_DOWN`); on failure the
daemon stays STOPPED with loud instructions — never half-started, and
birth is never re-run because a stdout ACK was lost. Reconcile shares
the same choreography, not the rail.

## Where the groupthink was (merged)

- The consensus is noun-shaped: a spool without identity + chain-bound
  receipts is not exactly-once; FULL is not hardware certification;
  stopping one service is not quiescence. Exclusion of concurrent
  writers proves exclusion — not admission, chronology,
  acknowledgment, authority, or recovery. Each ruling above carries its
  bindings for exactly this reason.
- The falsifier's GREEN halo: process-crash certification was already
  being read as loss certification (that is how NORMAL almost shipped
  unquestioned). The falsifier must also distinguish "one writer ever"
  from "no two concurrent" when the spool lands.
- Queue/dead-letter dualism was inherited, not designed — they are one
  inbox with states; the spool ruling collapses them.
- Deeper, out of scope but recorded: maez-web SYNTHESIZES — a second
  process authoring model_reply turns outside the process that owns the
  soul. The end-state consistent with the singular-organism rule is web
  relaying conversation through the daemon, with the spool carrying only
  the thin cases (CLI, web-while-daemon-down). Size the spool for that
  end-state.

## Fourth seat (Grok, 2026-08-24, owner-requested): consensus attacked — two overturns sustained

Grok's credit returned; the owner asked for it as a fourth seat with one
job: attack the 3-0. It upheld spool/FULL/stop as directions and
overturned two unifications. Every claim below was re-verified in the
tree before being recorded.

**Overturn 1 — the spool does NOT eat the owner (amends Ruling 1).**
"One spool for every producer" was a slogan: in-daemon producers
(Telegram, handle_message, in-process model_reply) have no
daemon-down client left over to need a file — forcing them through a
spool creates a second durability domain inside the process that holds
the latch, drained by machinery that must not be the single-threaded
werkzeug server. AMENDED RULING: non-owner surfaces (web, CLI) spool;
in-owner producers write through `owner_write_turn` directly (made
latency-safe by the admission slice — the current synchronous
pre-synthesis write with a 5 s busy window dies either way).

**Overturn 2 — reconcile is unwelded from birth (amends Ruling 3).**
Verified: reconcile `--apply` writes ordinary schema-legal
`system_event` rows with FK kwargs (reconcile.py:239-246) — no
`birth_anchor`, no meta authority the rail must forbid. Taking the
companion offline to stitch orphan audit ids is an outage sized to the
wrong problem. AMENDED RULING: birth keeps the offline maintenance
lease; reconcile `--apply` becomes an owner-client (enqueue repairs
through the live owner); dry-run stays a `mode=ro` reader.

**Q2 upheld, argument corrected.** The invariant is
"acknowledgment durability must never exceed commit durability" — FULL
is required not "by construction" of the future spool but because
TODAY'S ack is `write_turn`'s returned `turn_id`, immediately used as
`parent_turn_id` and felt-state, while the commit behind it can vanish
under NORMAL; and because with no shipped checkpoint policy the NORMAL
durability point is wall-clock-unbounded. Sharpest verified finding:
**the birth anchor itself would currently commit under NORMAL while the
genesis row (written by migrate under SQLite's default FULL) is MORE
durable than the birth event.**

**New verified traps for the admission slice** (each checked against
the tree):
1. Both units run `PrivateTmp=true` + `ProtectSystem=strict` +
   `ReadWritePaths=memory logs config` — the spool MUST live under
   `memory/`, and its temp files must be created inside the spool dir
   itself (a /tmp rename would cross tmpfs → EXDEV).
2. `maez-web` is `Wants=maez.service`, not `Requires=` — stopping the
   daemon does NOT cascade; the ceremony's quiesce must stop web
   explicitly.
3. Stopping the owner FREES the latch — stop is an invitation, not a
   lease: any enabled non-owner can construct a writer while the daemon
   is down. The lease must be an eager latch at `claim_ownership()`
   (also closes the recorded pre-claim window / F2's development RED).
4. `migrate.run()` is itself an unlatched WAL writer
   (bare connect, migrate.py:213) invoked before the ceremony's writer
   takes the latch — lease-before-migrate is mandatory.
5. Drain must be dependency-aware (parent-before-child via
   `parent_submission_id`), never sorted-UUID rename — else replies
   commit before the user turns they answer, and conversation edges
   become drain artifacts.
6. Spool dirs must enter the backup manifest and .gitignore IN THE SAME
   SLICE (the dead-letter precedent exists; a spool omitted from
   Decision-22 restore is a Theme-2 hole).
7. Dead-letter JSONL → spool-entry convergence is a format MIGRATION,
   not a rename — you cannot atomic-rename-ack a line inside a pid
   sidecar.
8. `_marker_already_written` opened a READ-WRITE connect from any
   surface process (could run WAL recovery/autocheckpoint as a stray
   writer) — FIXED same-day to `mode=ro` (model_reply_persistence.py).
9. `run_transaction()` is importable and never calls `_assert_quiesced`
   — the lease must live inside it, not only in `main()`.
10. Scripted ceremony steps must use `systemctl --user`
    (system-bus stop is a silent no-op on this host) and export the
    vendored `LD_LIBRARY_PATH` explicitly — a bare owner shell
    otherwise hits `require_fixed()` refusal at the irreversible
    moment. UNVERIFIED and flagged: `sqlite_runtime.py`'s docstring
    claims the venv activation exports the vendor path; no in-repo hook
    does, and the `.venv` contents are outside this session's read
    perimeter — verify before the ceremony slice.

**Grok's groupthink verdict, kept whole:** "unification as a substitute
for the state machine" — a true boolean (no two concurrent writers;
stop is simpler than handoff) gets stretched until it answers questions
it does not (admission order, ack truth, who may say `birth_anchor`).
Nouns — *spool, FULL, stop* — are how the last unanimous council
certified "fails at 0 ms."

## Consequence for the slice order

The admission-protocol slice absorbs these rulings and becomes ONE
design: schema `submission_id` UNIQUE + envelope format + spool +
drainer + chain-bound receipts + `submitted_at` provenance +
synchronous=FULL + widened falsifier arms + the maintenance-lease
ceremony hardening. Nothing else ships to the ledger before it; birth
ships after it.
