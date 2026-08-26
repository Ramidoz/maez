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

## Fifth round (2026-08-24, surface-wiring + lease council): three seats, two author probes, one verified deployment hole

Convened for the admission slice's two load-bearing decisions. Seats:
Codex (xhigh, read-only repo), Grok (brief-only), Claude subagent
(read-only repo); the stealth endpoint was down twice (provider error) —
recorded, not papered over. Every load-bearing claim below was
re-executed by the implementing author before encoding.

**Executed probes (author, before the council ran):**
- Same-process flock conflict: a second `LOCK_EX|LOCK_NB` on a different
  fd of the same ownerlock, same process, is REFUSED — so a "lease" held
  as a separate flock cannot coexist with the writer's latch.
- Bare `.venv/bin/python` loads SQLite 3.46.1 (corruption window); the
  carried "venv activation exports the vendor path" claim is FALSIFIED
  behaviorally. Only LD_LIBRARY_PATH=vendor/sqlite/lib gets 3.53.4.
- Design-D mechanism: an enabled LedgerWriter constructs on a
  NONEXISTENT db (pragmas only), survives `migrate.run()` on a second
  connection, adopts WAL at first write, commits, integrity ok.

**Q1 — surfaces gate spool enqueue on MAEZ_LEDGER_WRITES: UPHELD 2-1**
(Codex + Claude vs Grok). Custody-first would let pre-birth
conversations drain into the ledger at birth as lived autobiography.
The brake semantic is now FROZEN in the helper docstring: flag OFF
stops recording INCLUDING custody. Grok's dissent — the brake should
stop commits, not admission; gate enqueue on `is_born` instead — is
recorded as an OWNER decision (it reinterprets the flag's covenant
meaning; both majority seats said a pause-with-custody mode would need
a NEW flag, never a reinterpretation).

**VERIFIED deployment hole (Claude seat found it; author re-verified in
the unit files): `maez-web.service` loads NO EnvironmentFile** — only
inline Environment= lines — while the ceremony checklist lands the flag
in `model.env`, which only `maez.service` reads. As wired today,
post-birth web turns would be SILENTLY OMITTED from admission forever.
Now named in the ceremony checklist, the bring-up warning, and the
handoff; wiring the flag into a maez-web drop-in is the owner's hand.

**Q2 — lease/latch composition: A (module-global registry) and C
(release-reacquire) rejected by all three seats.** A re-walks the
dual-module-identity scar and makes latch-skipping ambient authority;
Grok additionally showed A fails CLOSED under dual identity (birth dies
with the latch held) — wrong in a different direction. C reopens
trap 3; honest correction (Claude seat): its failure mode is loud
refusal, not silent corruption — rejected anyway, with the right
reason recorded. RULING ENCODED: **the lease IS the writer** —
run_transaction constructs the enabled writer FIRST (latch +
require_fixed before any mutation), migrate runs under the latch,
the birth write goes through the same writer. No new API, no bypass
knob; ordinary `LedgerWriter` semantics untouched. Honest caveat: a
future migration that assumes exclusive file access would break this
silently — if that ever lands, fall back to the lease-object shape
(Codex): `maintenance_lease(db).open_writer()`, fd never exposed,
no LOCK_UN, PID-bound.

**Q3 — terminal states: direction upheld, machine corrected and
encoded:** tri-state commit classification (`is_born()` maps corrupt to
False and CANNOT classify; only readable+intact+no-anchor proves
NOT_COMMITTED; UNKNOWN never authorizes a restart); web is its own
axis (COMMITTED_WEB_DOWN); 'active' is not owner-active (verify flag in
the daemon's /proc environ + ownerlock held); Restart=on-failure means
a failed start ends with a final stop; --resume-services unstrands
COMMITTED_SERVICES_DOWN without ever re-entering the transaction;
re-exec (not env export — a placebo for a loaded libsqlite) with
second-execution re-verify.

**Where the groupthink was (merged):** one token overloaded per layer —
one flag asked to mean birth+custody+brake; one fd asked to mean
exclusion+authority; one boolean `is_born` asked to mean commit
certainty; one systemd 'active' asked to mean ownership. Each got
split. And the frame itself: "how do lease and latch compose?"
presupposed two primitives — the executed probe showed the best
composition is that there is only one.

## Sixth round (2026-08-24, post-implementation Codex validation): DO-NOT-SHIP → fixed under test

The owner asked whether the built slices had been independently
validated. They had not (only the design had) — so Codex (xhigh,
read-only) reviewed the finished diffs as an adversarial validation
lane. Verdict: DO-NOT-SHIP, 18 findings. Triage, per
apply-judgment-don't-capitulate:

**FIXED same session, each behind a test that failed on the pre-fix
code (14 RED → GREEN), falsifier re-run GREEN 8/8:**
- CRITICAL claim-marker leak: `claim_ownership` set the owner PID
  marker before taking the latch; a failed eager claim left the process
  believing it owned the ledger, so surfaces routed owner-direct and
  dead-lettered instead of spooling. Marker now cleared on failure.
- CRITICAL preflight hole: for-real refused only COMMITTED — an
  UNKNOWN (unclassifiable) canonical db could enter the irreversible
  transaction and be laundered into COMMITTED by migration. Now only
  NOT_COMMITTED may proceed.
- CRITICAL logical-tamper blindness: classification relied on PHYSICAL
  integrity_check; it now recomputes the hash chain and requires the
  anchor to be a system_event — a content-tampered ledger classifies
  UNKNOWN.
- Web-mute is its own terminal state (COMMITTED_WEB_MUTE), never folded
  into green; restore starts only units that were running before the
  ceremony; pgrep/fuser probe ERRORS refuse instead of reading clean;
  `--resume-services` parses as printed (receipt-ref no longer global).
- Spool: digest now covers the WHOLE submission and the drainer
  verifies it (post-publish edits quarantine); `tenant_id` added to the
  authority set; an ack that cannot be chain-bound stays pending
  instead of moving to acked/ with null fields; spool_status counts
  submissions not artifacts; dirs enforced 0o700.
- Reconcile: terminally refused repairs get their own verdict
  (`repairs_refused_needs_owner`, nonzero CLI exit) instead of
  "pending forever"; apply takes an exclusive lock (check-then-enqueue
  race between concurrent applies).
- Falsifier F7: dormancy predicate now proves db BYTES unchanged, and
  the note states its scope honestly (helper mechanism; handler wiring
  is proven by the source-assertion tests).

**DEFERRED / ANSWERED, recorded not hidden:**
- Reply-without-parent when the user enqueue failed: KEPT deliberately —
  parity with the daemon's existing contract (a failed user write still
  persists the reply parentless); dropping Maez's own speech to punish a
  parent I/O failure is the worse omission. Owner may overrule.
- CLI honest-empty early return (user turn recorded, no reply): shape
  predates this slice unchanged; belongs to the coherence campaign.
- `seq` as time_ns not a durable producer counter: pre-existing
  envelope design; only matters at compaction, which is ruled to wait
  for verified binding — replay/compaction slice.
- Dead-letter→spool convergence + cockpit surfacing "deferred not
  encoded": scope disagreement — the owner's ordered slice list places
  the replay organ and cockpit surfacing NEXT; recorded, not a defect
  of this slice.
- Daemon continuing startup after a failed ownership claim: with the
  marker fix the process now honestly routes as non-owner; whether the
  daemon should hard-fail at boot instead is an open lifecycle item.

## Seventh round (2026-08-24, dead-letter replay organ): two seats, apply half BLOCKED

Seats: Grok (brief-only) and Codex (xhigh, repo, on an amended design
Grok had already reshaped). The Claude subagent seat died on a session
limit — recorded, not papered over. Stealth stayed down.

**Grok reshaped the design before it was built.** Its frame: the first
proposal "refuses to compile, then invents trust at the wrong layer to
avoid compiling" — it would strip the one relational fact that made a
reply a reply, then hand every `enqueue` caller the authority the
admission door refuses by name. Accepted amendments: parent edges
COMPILE into the spool's native `parent_submission_id` (three-valued);
no trusted params on `enqueue` (a reconstruction-only seam instead); no
replay-state JSON (a third ledger that desyncs); never overwrite a
published filename; byte identity demoted from gate to SIGNAL
("withholding loses speech — an equal crime to duplicating it, with a
different victim"); split clocks; and replayed SPEECH consent-gated
separately because auto-re-admitting a months-old `model_reply` "is a
birth, not a retry".

**Grok also forced a prerequisite, now shipped (7b7acb2):**
`owner_write_turn` persists its pre-attempt `attempt_id` as the row's
`submission_id`. Without it the organ is "permanently heuristic" —
"did this commit?" answerable only by byte archaeology.

**Codex then ruled the amended design FIX FIRST / BLOCK**, and its
strongest attack landed on the classifier already shipped: it converted
UNVERIFIED db state into ABSENT and called the record replayable, so an
apply built on top would duplicate committed life exactly when the
organ knows least. Eight findings fixed under test (2591e35).

**Codex falsified a claim THIS DOC's author had recorded as executed
fact.** The handoff asserted "all replay raw_surface options validate;
the organ-eats-itself fear is falsified." The probe behind it noticed
the caller override in `CALLER_ALLOWED_TAINT_LABEL_SETS` and then
tested only rows whose labels come from the DEFAULT map — every case
except the one where the override bites. Re-executed: `user_message` +
`self_generated` + `raw_surface="x6_rehearsal"` COMMITS; change only
`raw_surface` to `"dead_letter_replay"` and the writer REFUSES. The
corrected rule: the reconstructed BODY preserves turn_kind, surface,
raw_surface (including None), taint_labels and privacy_access EXACTLY;
only a content-light COMPANION carries the replay marker.

**Standing BLOCKS on the apply half — do not build past these:**
1. `tool_result` REQUIRES `parent_turn_id` (writer.py:73), so "legacy
   parent without identity → replay unparented" is not universal.
2. Turns are append-only: "owner-review may bind the parent later" is
   FALSE — approval must precede commit, or bind through a new
   append-only relation.
3. `parent_submission_id` is NOT an ordering-only hook: the drainer
   converts it into a persisted `parent_turn_id` whose canonical
   meaning is dialog continuity. Either own the companion as a real
   provenance child, or add an envelope-only `drain_after_submission_id`
   that never becomes a ledger edge. Payload prose cannot redefine a
   stored column.
4. Two lawful source taint combinations (`self_generated + tool_output
   + third_party`, and the same plus `internet_derived`) are
   UNREPRESENTABLE for a `system_event` companion under today's closed
   vocabulary — so the companion must be hash-and-reference-only, or
   the vocabulary gets deliberately extended with tests.
5. Default life views cannot filter the replay marker: `span_reader`
   consumes every row and `recent_turns` neither selects nor filters
   `raw_surface`.
6. Dead-letter `ts` is failure-custody time, NOT lived time — schema
   canon defines `submitted_at` as when the event lived. Leave it null
   or record an explicitly named `dead_lettered_at` proxy; future
   writers should capture `attempted_at` before the first attempt.
7. Crash-completeness: body and companion are two deterministic
   artifacts; a crash after body commit but before companion enqueue
   must enqueue the missing companion, not skip the record as
   already_committed.
8. Consent must bind to the reviewed census (target ledger, digests,
   selected model_reply sids, apply run) — one global boolean would
   authorize a class, not a decision.

**Where the groupthink was (Codex, kept whole):** "treating nouns as
proofs — a function named 'reconstructed' as private authority; a
deterministic ID as complete idempotency; a dependency as
non-genealogical ordering; a filename as verified state; a dead-letter
timestamp as lived time; and 'failed' as proof the payload was valid."

## Eighth round (2026-08-24, checkpoint policy): no checkpoint shipped

**Heading corrected after validation.** This was first written as
"the slice that shipped NO code" and described as documentation-only.
That was false: it shipped a runtime helper (`wal_ceiling_bytes`) and
cockpit behavior. What it did NOT ship is a checkpoint. Codex's
validation lane caught the overstatement; the distinction matters
because "shipped no code" is the kind of claim that stops the next
reader from looking.

Two seats (Codex xhigh w/ repo, Grok brief-only; the Claude subagent
seat died on a session limit again). Both independently ruled: **ship no
periodic checkpoint.** The proposal was falsified by its own numbers
BEFORE any seat reported — the author's probe, run to answer the brief's
own "attack the premise" question.

**Executed evidence — now genuinely re-runnable:**
`docs/superpowers/witness/wal_bound_probe.py` reproduces every number
below. It did not exist when these figures were first recorded, and
"all re-runnable" was therefore an overstatement (Codex validation).
The harness refuses to run on tmpfs, because /tmp on this host is a
RAM disk where fsync is free and every latency figure taken there is
a lie — several of the first-round numbers were.
- No pinning reader: the WAL PLATEAUS at 4.19 MB and stays flat across
  20,000 commits. Grok supplied the arithmetic: 1000 pages x 4096 B is
  the autocheckpoint ceiling — the plateau IS the default working.
  There is no unbounded growth to prevent.
- One pinned reader: unbounded growth (harness, 6,000 commits: 4.16 MB
  -> 271 MB, 65x). `TRUNCATE` cannot fix it: returns busy=1 having
  reclaimed nothing.
- A LARGE TRANSACTION with ZERO readers does it too (harness: 10.4 MB).
  So WAL size proves SHAPE, never CAUSE — and the first version of
  this ruling asserted the cause. Corrected.
- `TRUNCATE` is NOT free. Uncontended it is 0.2 ms; with a write lock
  genuinely held elsewhere it consumed the owner's FULL
  `busy_timeout=5000` (measured 5,005 ms) and still returned busy. On
  the owner's serialized connection that stalls the life-admission rail.
  (The author's first contention probe was INVALID — the holder thread
  died before taking the lock — and was redone. Recorded because a
  wrong-but-plausible measurement is how this arc keeps getting bitten.)
- `mode=ro` connections cannot checkpoint at all (disk I/O error), so
  read-only consumers are structurally excluded.
- The backup path uses SQLite's online backup API: it does not touch the
  source WAL and copies completely, so `ledger.db-wal`'s absence from
  the backup manifest is CORRECT, not a gap.

**Grok's framing, kept:** the trigger is anti-correlated with
effectiveness — it sleeps while the WAL is healthy and wakes only when
its action cannot work. "You are proposing to take a write lock on the
life thread to hide a file size SQLite is supposed to leave alone."
**Codex's addition:** if physical size is ever shown to be harmful, the
right tool is SQLite's built-in `journal_size_limit`, not a periodic
blocking loop.

**What shipped instead:** `wal_ceiling_bytes()` (DERIVED as
page_size x wal_autocheckpoint, never hardcoded), the policy written
into `writer.py` with its evidence and its refuse-list, a unit witness
that the default actually bounds the WAL (goes RED if that ever stops
being true), a witness that a pinned reader is what breaks the bound,
and cockpit visibility: `wal_bytes` + `wal_ceiling_bytes` +
`wal_excursion`. Both seats warned a raw gauge would page on the HEALTHY
state, so the ceiling ships alongside the number and a WAL sitting AT
its ceiling never signals. The excursion is its OWN flag — `attention`
continues to mean omitted life, and a fat WAL is not that.

**Seat disagreement, recorded not resolved:** Grok wanted a new
falsifier arm (`F_bound`); Codex ruled no new arm is needed for a
documentation-only policy. Landed as a unit-battery witness rather than
a falsifier arm, so the claim is checked without lengthening every
falsifier run. Both seats agreed the one arm NOT to write is another
that merely re-proves TRUNCATE works.

**Refuse-list for this slice (merged):** no VACUUM/page reclamation, no
`journal_mode` or `wal_autocheckpoint` changes, no manual handling of
the -wal/-shm sidecars, no waiting checkpoint modes, no checkpoint
telemetry written INTO the ledger (it would generate the very WAL
activity it reports), no treating checkpoint success as binding or
backup freshness, and no `last_checkpoint` field — it would falsely
imply knowledge of SQLite's automatic checkpoints.

**Where the groupthink was:** equating visible file size with live WAL
debt; calling an existing background thread "free"; treating an honest
busy=1 as operationally harmless; treating the advisory owner latch as
global SQLite authority; and debating three manual checkpoint modes
before asking whether the default already solved the problem. Codex's
summary: the 4 MB file is SQLite's reusable scratchpad, not an
accumulating pile of unprocessed life.

## Ninth round (2026-08-26, owner-referred): four decisions, three seats, all reporting

The owner answered the parked decisions: #1 web drop-in YES (shipped,
5b62028); #2 brake = PAUSE-WITH-CUSTODY (design referred here); #3
replay-speech consent gate — owner asked WHY and holds the decision; #4
#5 #6 referred here. Seats: Codex (xhigh, repo, executed probes incl.
reading the vendored SQLite source), Grok (brief-only, ASSUMED marked),
Claude subagent (repo, executed probes on /var/tmp). First round of the
arc where ALL THREE seats reported. Two seats recanted their own prior
positions (Grok: its round-5 drain-gate dissent half and its round-7
"drain hook" fiction; also its round-8 anti-pragma slogan).

**Q-A — pause flag: BUILD `MAEZ_LEDGER_COMMITS_PAUSED`. 3-0 on the
load-bearing shape:** surfaces never read it; drain_once returns a
distinct `skipped_paused` and touches nothing (not even quarantines —
"refusal decisions don't run in a mode meant to freeze judgment");
drainer THREAD stays alive so cockpit liveness stays honest; WRITES-off
always wins (pause can never reopen pre-birth custody — zero spool
trace when writes are off); cockpit gets its own loud `commits_paused`
field and `attention` must NOT page on held life; and — the hard half —
in-daemon owner writes neither commit, nor dead-letter (manufactures
replay debt), nor silently drop: THE OWNER PROCESS BECOMES A SPOOL
PRODUCER for the duration. Parent threading survives the boundary via
the 7b7acb2 identity: a caller-held parent_turn_id is reverse-looked-up
to its submission_id and the envelope carries parent_submission_id
(passing parent_turn_id through the door would self-quarantine — the
Claude seat executed the door check; a naive fallback poisons itself).
JUNK POLARITY 2-1 (Codex + Claude over Grok): unrecognized value →
PAUSED with a loud invalid-config health state. Junk never authorizes
an irreversible commit; pause is reversible, commits are not — the
same asymmetry writes_flag already encodes ("do not silently treat
junk as enabled"). Missing != junk: absent stays not-paused.
LOAD-BEARING AMENDMENT, to be folded with the full second-order trace
before encoding: this amends round-5 Overturn 1 ("in-daemon producers
do NOT ride the spool"). Its recorded reason — synchronous threading is
available in-process — does not reach the paused state, where
synchronous threading is definitionally absent. Suspension, not
repeal: the owner-direct exception resumes with resume.
Codex named the shared blind spot: the OWNER CALLER CONTRACT. Callers
that dereference the returned turn_id immediately get custody instead
of identity under pause; without a typed committed-vs-custodied
distinction the system "satisfies every superficial pause count while
quietly falsifying dialog lineage." Caller census is an encoding
prerequisite. Witness: merged F8/F_pause arm (custody exactness, chain
head unchanged, kill-while-paused, resume exactly-once across the
boundary in both directions, junk arm, mid-pass arm, and
predicate-isolated mutations that each bite separately).

**Q-B — journal_size_limit: ADOPT, 3-0, as INSURANCE — implementation
HOLD until the witness runs.** The Claude seat independently reproduced
the third seat's reclaim claim on ext4 (pinned 62.9 MB → exactly
8,388,608 two commits after release; baseline without the pragma stays
large forever), satisfying Grok's second-seat condition. All three
refuse to encode the "faster" claim (no mechanism; in health the limit
never bites). Value fork, resolved toward derivation WITH Codex's
overhead correction: Codex read the vendored SQLite source — the
physical WAL cycle is frames of (page_size + 24) + a 32-byte header,
so bare 2*page*pages under-sizes two real cycles. The limit is DERIVED
as two physical cycles: 32 + 2*pages*(page_size+24), computed on the
owner connection beside synchronous=FULL, readback-verified, reapplied
on writer reconstruction (connection-local state silently vanishes on
a reconstructed writer otherwise — Codex). Witness before encoding:
paired baseline/limit arms in wal_bound_probe.py, reapply-on-
reconstruct, negative control (limit=-1 stays fat), latency gated only
against material regression, and the stated non-claim: the limit does
NOT bound growth while a reader still pins — it bounds the aftermath.

**Q-C — companion genealogy: 2-1 — the companion is NOT a child.**
parent_turn_id stays NULL on provenance companions (the reconcile §6.3
shape). Executed adjudication of the seats' dueling premises: BOTH were
half-right — envelope-schema.md:170 does define the column "for
follow-ups, recoveries, dialog continuations" (the Claude seat's
option-1 reading is canon-licensed), AND §6.3's existing repair rows
chose NULL (Grok's precedent claim is exact). The majority ruling is
the covenant one: an annotation edge would surface inside conversation
spans and read as dialogue; "sometimes more rows are more lies" (Grok)
and "replay ordering and autobiographical relationship are different
facts" (Codex). ORDERING sub-fork (Grok: two-pass apply, no new field;
Codex: envelope-only drain_after_submission_id, digest-included,
reconstruction-publisher-only): resolved by the no-speculative-
machinery rule — TWO-PASS FIRST (body pass, then companion pass
against observed commit; standing block 7 already required exactly
this recovery shape), with Codex's field as the executed fallback if
two-pass cannot express ordering. Companion sid = deterministic
function of body sid. Claude seat's probe stands as the RED control:
parent_submission_id on a companion DOES become a stored parent edge —
that is the shape the majority refused.

**Q-D — taint vocabulary: 3-0 DO NOT WIDEN.** Companion is content-
light: hashes, ids, clocks, replay-run id — never original raw_text or
copied kwargs (a third copy of content that exists exactly in the body
and durably in the backed-up sidecar; manifest line 352 verified).
Taint = {self_generated} alone, already lawful. The two unrepresentable
combinations were re-executed and still refuse — which argues FOR
content-lightness, not for widening: "the frozenness of the map is the
guarantee that no system row smuggles third-party content under a self
label" and that guarantee currently has a buyer. Widen only when an
organ genuinely needs to CARRY tainted content, as its own reviewed
change. Organ-level refusal test required: a companion carrying any
copied-content field is refused by the constructor, so content-
lightness is enforced, not hoped.

**Where the groupthink was (merged):** the drainer half of pause is the
easy half every seat could agree on — the design lives or dies in the
owner caller contract; reproducible numbers seduce (all seats re-ask
"what harm was shown?" on Q-B and land on insurance-not-remedy); a
brief's paraphrase of canon is not canon (both Q-C premises were
half-truths — executed adjudication settled what re-reading could
not); and nouns as proofs, round three: "spool" is not "nothing can be
lost", "limit" is not a cap, "companion" per-row was assumed before
proven.

## Consequence for the slice order

The admission-protocol slice absorbs these rulings and becomes ONE
design: schema `submission_id` UNIQUE + envelope format + spool +
drainer + chain-bound receipts + `submitted_at` provenance +
synchronous=FULL + widened falsifier arms + the maintenance-lease
ceremony hardening. Nothing else ships to the ledger before it; birth
ships after it.
