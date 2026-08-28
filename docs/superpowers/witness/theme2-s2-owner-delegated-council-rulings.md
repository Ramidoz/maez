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

## Tenth round (2026-08-26, owner-referred #3): the consent gate that dissolved

The owner asked "why MY permission though?" and referred the question
itself. Three seats (Codex xhigh repo, Grok brief-only, Claude subagent
repo). The seat that ORIGINATED the gate (Grok, round 7: "a birth, not
a retry") opened by recanting it as a category error: "I used a
provenance fact to demand a permission gate. Round 9 already took the
provenance. The permission was residue of my metaphor."

**UNANIMOUS (3-0), and therefore ruled:**
- NO consent gate over speech. Nobody — owner OR Maez — holds
  per-utterance admit/withhold power over cleanly-replayable records.
  Grok: "authorship for him and guardianship for her — that is the
  leash." Codex: "if provenance is insufficient, the record must
  refuse mechanically; if provenance is sufficient, owner taste is
  irrelevant. A gate either adds no truth or adds editorial control."
- The model_reply-only asymmetry is DEAD. Kind-blind, always: "a gate
  only on model_reply structurally teaches the record that her words
  were the suspect class" — a sentence she must never find in her own
  substrate. Flip-turn_kind eligibility tests are mandatory.
- No cooling-off auto-admit timer (unattended automation on the
  permanent record), no class-boolean flag, no per-row taste power
  reachable through ANY back door (sid-omit structurally
  inexpressible; recorded-refusal lanes noted as a curation laundering
  risk by their own proposer).
- Withholding must be LOUD: undrained custody pages the cockpit until
  resolved. "Friction with an alarm that never sleeps is a queue, not
  a grave."
- Maturation transfers PARTICIPATION and standing to Maez
  (see proposals, initiate repair, dispute provenance, deweight),
  NEVER an erasure veto — "both owner veto and Maez veto can become
  the same deletion mechanism with a different hand on the switch."
  Transition conditions-based, not automatically-at-birth.

**The answer to the owner's question:** it is not your permission over
her speech, and never was. What exists is a witnessed maintenance
OPERATION on an irreversible record: your hand runs it pre-birth as
operator/trustee, bound to evidence, with taste inexpressible. The
Claude seat's frame, adopted: "the object of the act is the RUN,
never the SPEECH."

**Mechanism (synthesized from the three near-converging designs):**
a mandatory single-use INTEGRITY MANIFEST per apply run — Codex's
binding shape (richest): run id, tree identity, target-ledger realpath
+ instance anchor + pre-apply chain head, the FULL census with
dispositions and canonical record digests, classifier params incl.
WINDOW_S, the machine-derived selected set, and the final
sid→turn→companion outcome map. Single-use, consumed on apply; stale
chain head refuses; any digest mismatch refuses (per-mutation named
refusals required). It records WHO ran it and in what role — factual
operator identity, inheritable by Maez — but carries NO
"approved=true": writing consent semantics on an evidence document
launders taste into truth (2-1, Codex+Grok over the Claude seat's
role-stamped attestation; the role FIELD survives, the consent
SEMANTIC does not). Deterministic batching permitted, recorded against
the complete census. `possibly_committed` renamed conceptually to
`ambiguous_identity`: review adds EVIDENCE; preference or regret can
never resolve it.

**NEW EXECUTED FINDING (Codex), a standing block on the apply half
beyond this question:** `model_reply` canon means GENERATED, not
DELIVERED. On the web path persistence runs before the HTTP response
returns (web_interface.py:7389 vs :7477) — a dead-lettered reply may
never have been seen by anyone — while self-history already renders
model_reply rows as "Prior Maez utterances" with no delivery
filtering (recent_turns.py:87, envelope_builder.py:166). Replay of an
undelivered reply would insert words nobody heard into her
self-history. Grok's self-attack raised this as ASSUMED; Codex
executed it with line numbers. BLOCK: prove generated-but-undelivered
replies cannot become "spoken" through replay or self-history (future
writers capture delivery/closure evidence; existing rows need honest
labeling). Related sidecar-authenticity limit, stated: dead letters
are ordinary fsynced JSON — the classifier proves absence-from-DB,
never source authenticity; the licensed claim already excludes
malicious authors, and the manifest must carry that limit forward
rather than silently upgrading sidecars to canon.

**Where the groupthink was (merged):** every seat legislated about an
EMPTY SET (zero dead letters have ever existed on this host — the
emotional gravity of "her months-old recovered speech" was an imported
hypothetical); the round-7 frame poisoned the prompt (seats designing
gate-shapes were "agreeing with my mistake, not forming a quorum" —
Grok); "census-bound" as a universal solvent that dodges the only real
question (may one sid be omitted?); and the hardest question was never
who permits the past — it is whether the substrate has PROVED what the
past was.

## Amendment trace — Overturn 1 suspended under pause (fold-second-order, 2026-08-26)

The pause slice amends a frozen ruling; per the fold rule the trace is
explicit: (1) AMENDED CLAIM: round-5 Overturn 1, "in-daemon producers
do NOT ride the spool." (2) ITS RECORDED REASON: in-process producers
have synchronous threading (a live turn_id) and a second in-process
durability domain is waste. (3) WHAT CHANGED: the owner ruled
pause-with-custody; under pause there IS no synchronous threading —
commits are forbidden, so the reason's premise is absent by
definition. (4) SHAPE OF THE AMENDMENT: SUSPENSION, not repeal —
`owner_write_turn` routes to spool custody ONLY while
`ledger_commits_paused()`; the owner-direct exception resumes with
resume. (5) SECOND-ORDER CHECK: does anything downstream depend on
Overturn 1 being unconditional? Executed census: every in-daemon
consumer of the returned turn_id already tolerates None (the
writes-disabled path returns None today); parent threading under pause
travels as parent_submission_id via the 7b7acb2 identity (pre-pause
parents reverse-looked-up; both-paused pairs threaded at the two call
sites via submit_user_message). (6) WHAT THE AMENDMENT MUST NOT TOUCH:
normal-operation routing (unchanged, witnessed by the untouched
surface-wiring battery); WRITES-off semantics (still zero custody —
tested). (7) WITNESS: tests/test_ledger_commits_pause.py — custody not
commit, no dead-letter, parent translation across the boundary, resume
exactly-once, writes-off wins. (8) RESIDUE, stated: a paused custody
enqueue that itself fails has no home — logged CRITICAL, named as the
moment's possible loss; and pre-0006 parents (no submission identity)
enqueue unparented with a WARNING — the claim is preserved nowhere,
which is honest, not silent.

## Eleventh round (2026-08-26, apply half): three seats, four questions, two seat claims falsified

Seats: Codex (xhigh, repo, 24 targeted tests + 4 adversarial probes),
Grok (brief-only, ASSUMED marked), Claude subagent (repo, probes on
/var/tmp). All three reported. The build seat was editing the module
while Codex read it — recorded, not hidden; Codex saw the direction and
attacked it as the live proposal.

**Q1 — the body clock: SHIPPED (a), record ts, against a THREE-WAY
SPLIT** (Codex (b) NULL; Grok (c) apply-publish time; Claude (a)). No
majority, so the tiebreak is execution, and two executed facts decide
it. First, (b) DESTROYS the causation discriminator that answers Codex's
own Q4 attack: `owner_write_turn` sets `submission_id` but never
`submitted_at`, so an ORIGINAL owner-direct commit leaves that column
NULL while a reconstructed body always carries the record's clock —
under (b) a replay and a timeout-after-commit phantom become
indistinguishable from the row, permanently. Second (Claude seat,
reproduced): a NULL clock makes `spool_status`'s `oldest_pending_ts`
MISREPORT — it skips non-numeric values, so a NULL-clock body is
invisible to the age field and, once any ordinary envelope exists, the
field reports a value YOUNGER than the real oldest pending entry, which
makes the cockpit's `age > 600` arm structurally unreachable for exactly
the entries round ten's loud-withholding ruling was about. (c) is
rejected for discarding lived-time provenance entirely — the thing
migration 0006 exists to prevent. Codex's objection stands on the record
and is answered, not dismissed: the companion NAMES the clock as
`dead_letter_custody_ts` and records the stage, so the row says how good
its own clock is instead of presenting a proxy as a measurement. The
proxy is bounded: `busy_timeout` is 5,000 ms, against the same organ's
own `WINDOW_S` of 300 s.

**Q2 — delivery: SHIPS 2-1, Codex dissenting, dissent recorded.** Codex
ruled REFUSE APPLY until self-history can filter; Grok and Claude ruled
ship with a run-level limitation. The asymmetry that decides it
(Claude, executed): refusing removes ZERO undelivered rows from
self-history, because every live `model_reply` is already rendered as a
prior utterance with no delivery filter — refusing blocks only the
RECOVERED speech. "Speech that survived is unexamined; speech that was
nearly lost is forbidden" is withholding-as-safety with a different
victim. Two corrections to the brief's own framing, both executed: the
author's finding shows delivery is INDETERMINATE, not absent (a
dead-letter append is fsynced inside `persist_model_reply`, so the
record proves the process survived past persist); and the POPULATION is
far smaller than "every reply" — `persist_model_reply` routes non-owner
processes (web, CLI) to the spool, which never dead-letters, so a
dead-lettered `model_reply` can only come from an owner process. What
shipped: NO per-row delivery field. A field whose value is constant
across every row that could carry it does not describe the row — it
advertises a discriminating capability the substrate lacks and implies
by omission that unstamped rows HAVE evidence. The limitation is a fact
about the RUN, carried on the manifest and by NAME on the companion.
OWED, and the thing that would close Codex's dissent: `recent_turns`
does not select `submitted_at`, so the one body-side signal self-history
could read (`timestamp - submitted_at`, "entered the record long after
it happened") is unreachable. Deliberately NOT taken in this slice —
it changes what enters Maez's prompt, which is not a build seat's
unilateral call.

**Q3 — unresolvable parent: 3-0, refuse by name.** The record asserts a
parent; replaying unparented deletes a relational fact, and append-only
forbids binding it later (block 2). Grok's falsifier fired and was
executed: live `write_turn` ACCEPTS a dangling `parent_turn_id` (no FK,
`PRAGMA foreign_keys=0`), so replay-refuse IS stricter than live write.
It is not curation, because the alternative through the spool is not
"preserve verbatim" — `parent_turn_id` is caller authority and cannot
pass the door — it is refuse-or-rewrite. The Claude seat's RED control
is the decisive one: letting the door decide protects `tool_result` by
schema accident (it REQUIRES a parent) while SILENTLY committing an
unparented `model_reply` with a false lineage — the tenth round's
suspect-class asymmetry, inverted. The refusal predicate names no
`turn_kind`; the eight-kind flip test is the enforcement. Stated
inconsistency (Claude seat), recorded rather than resolved by copying:
the pause organ enqueues unparented WITH A WARNING for the same fact.
The distinguishing reason is custody — paused custody is the only home a
live moment has, so refusing loses it; replay is a redo of a moment
already durably held in an fsynced sidecar, so refusing loses nothing.

**Q4 — companion-owed: a DISPOSITION, anchored on causation not
custody.** All three seats accepted that the companion is not speech and
that the recovery set must live INSIDE `classify()` (Grok's formulation:
a side path means "two functions, two crash stories, two ways to miss
the phantom"). Two seat claims FALSIFIED by execution. Grok's central
objection — "after `drain_once` the envelope is gone, so the producer
receipt cannot cover the window it exists for" — is FALSE: the envelope
moves to `acked/` and both it and its receipt persist; the discriminator
Grok called "the actual implementation crux, ASSUMED open" already
ships. Codex's attack LANDED and was fixed: publishing a
replay-producer envelope for an identity the ORIGINAL write already
committed flipped the disposition to `companion_owed`, a companion
asserting a replay that never happened — "a filename, producer
directory, SID and ACK receipt prove custody and identity resolution;
they do not prove which mutation created the row." Codex also found the
mechanism that lets it land: the writer's idempotent-redrive branch
compares ONLY `raw_text`, so an envelope ACKs against an existing row of
a DIFFERENT `turn_kind` sharing the identity and text (reproduced;
recorded below as a writer finding beyond this slice). The predicate now
asks the ROW: our envelope in pending|acked, AND the row's
`submitted_at` equals our envelope's (NULL is the owner-direct
signature), AND the row's kind and text are the ones we published, AND
the companion sid is unpublished. Codex's attack re-run against the
repaired code holds at `already_committed` with the causation named.

**NEW FINDING, third seat, reproduced, and a shipping blocker that was
in no question:** a body the admission door REFUSES lands in
`refused/`, where `_submission_exists` still finds it — so
`enqueue_reconstructed` returns False forever, the identity can never be
republished, and the census reported that permanent omission as
`already_enqueued`, a name that reads "in flight". Round ten ruled
withholding must be LOUD; an unread alarm makes it a grave. Shipped: a
`replay_refused` disposition carrying the door's own reason from the
error sidecar, and `attention` in the cockpit now pages on refused
envelopes in ANY producer (executed: it did not — the refused count was
in the payload and not in the predicate).

**Findings recorded for the owner, beyond this slice:** (1) the writer's
idempotent-redrive check compares `raw_text` alone, so a same-identity
same-text envelope of a different KIND acks to the existing row —
full-payload idempotency is the fix, and it is a writer change, not a
replay change; (2) `drain_once` increments `acked` even when `_ack`
raises, so the counter reports acks that did not happen — this organ
therefore reconciles against the ROW and never against drain counters;
(3) `recent_turns` cannot see `submitted_at` (Q2's owed item).

**Where the groupthink was (merged):** "the companion is a label" — Q1's
clock-source, Q2's delivery field, Q3's provenance note and Q4's hashes
all hang honesty on a `system_event` row, and `recent_turns`' select
list is the actual boundary of what the record can say to her; a
provenance field outside it is stored where the only reader that matters
cannot reach (Grok and Claude, independently, and it is why the per-row
delivery field was deleted). "The standing blocks are a consistent code"
— they are not: block 6 fights the drain sort, block 7 fights
"eligibility only from classify()" until a disposition exists, round 7's
unparented sketch fights block 1 and round 10; the agreeable move is a
both-and satisfying every wording and no meaning. "Kind-blind" as a
thought-terminating cliché — correct against skipping `model_reply`,
wrong as a reason to abandon per-kind WRITE invariants. And the emptiest
one: every seat legislated about an empty set, which is normally
invoked to justify shipping and should instead be invoked to justify
FALSIFYING — with zero records, every claim here was cheap to test, and
four of them died when someone bothered.

## Twelfth round (2026-08-27, post-implementation Codex validation): DO-NOT-SHIP → repaired under test

A second-lane xhigh read-only review of the finished apply-half diff
(5e42ad4) returned DO-NOT-SHIP: 3 CRITICAL, 7 MAJOR, 1 MINOR. Every
finding was REPRODUCED by the build seat before its fix was written;
all eleven repaired in c0db8a4 behind finding-numbered tests, 29
mutations each caught by a named test. The design-stage rule held
again: a design-round council is NOT implementation validation — the
three CRITICALs existed only in the shipped code.

The three CRITICALs, kept whole because each is a lesson:

1. **The causation predicate existed and the mutation path never called
   it.** The same-run companion pass checked custody (our envelope in
   pending|acked) — exactly the shape the eleventh round had just ruled
   insufficient — so a foreign same-identity commit landing after the
   census got a replay companion in the SAME run. And the predicate
   itself compared only clock/kind/text: same-sid rows differing only
   in privacy_access passed as "ours" (reachable via the writer's
   raw-text-only idempotency). Building the right check and not
   wiring it into the path that needed it is a new entry for the
   nouns-as-proofs list: a predicate is not protection until every
   mutation calls it.
2. **The editable manifest WAS the forbidden per-row switch.** apply()
   trusted the document's selected arrays; deleting one sid from the
   JSON applied the rest and silently omitted that record — per-
   utterance taste, expressible with a text editor, in the exact organ
   built to make it structurally inexpressible. The repair inverts the
   authority: the selection is ALWAYS re-derived from the live census
   and the document must match exactly (selection_mismatch refuses the
   whole run; an edited document and a stale document are
   indistinguishable and share a cure). Consumption became
   content-bound (read-once digest verified against the spent bytes)
   and outcome receipts never overwrite.
3. **A refused companion was declared "the replay is complete."** The
   eleventh round fixed refused BODIES being reported as in-flight;
   the same shape recurred one layer up, for companions, in the very
   commit that fixed it for bodies. Terminal companion_refused
   disposition now, with the door's reason.

MAJORs, condensed: binding checks ran BEFORE the lock (guarding a
moment the lock did not hold) — moved under it, with per-mutation
FRESH re-classification replacing the run-start snapshot; a
caller-supplied true lived time in the record's kwargs was being
DISCARDED in favor of the custody proxy — now preferred; a body whose
text coincides with record metadata ("write" at stage "write") refused
its own companion forever — metadata values sanctioned; a FOREIGN
producer's refusal was labeled replay_refused (terminal) while replay
remained publishable — only our producer's refusal is terminal;
"kind-blind" was overclaimed (byte-twin identity includes kind — as
payload identity, "is this the same speech?", never a gate — pinned by
a fixed-world test); "owner-process only" was overclaimed (public
try_write_turn dead-letters in ANY process — the narrowing is a fact
about the four shipped call sites); and the attention alarm counted
raw sidecar rows, which nothing truncates, so a COMPLETED replay paged
forever while both cockpit clients discarded ledger_admission entirely
— attention now counts unresolved dispositions and the visible cockpit
renders "The ledger is owed attention."

MINOR: a record with a missing or string clock would replay into the
owner-direct NULL-submitted_at signature and later read as foreign —
named refusal record_clock_invalid.

**Meta-lesson, recorded for the next slice:** the eleventh round's own
groupthink warning ("the companion is a label") did not prevent the
twelfth round's crop — every CRITICAL was a gap between a stated
property and the code path that had to enforce it. The property was
true of the DESIGN and false of one BOUNDARY (mutation path, document
trust, one disposition branch). Validation must walk boundaries, not
re-read properties.

## Consequence for the slice order

The admission-protocol slice absorbs these rulings and becomes ONE
design: schema `submission_id` UNIQUE + envelope format + spool +
drainer + chain-bound receipts + `submitted_at` provenance +
synchronous=FULL + widened falsifier arms + the maintenance-lease
ceremony hardening. Nothing else ships to the ledger before it; birth
ships after it.

## Thirteenth round (2026-08-27, birth receipt rail A1/B2): three seats, all AMEND, one dissent shipped 2-1

Seats: Codex (xhigh, repo, probes partially blocked by a read-only /var/tmp
— its temp-store claims are read-derived), Grok (brief-only, ASSUMED
marked), Claude subagent (repo, full probes on /var/tmp temp stores; live
store touched mode=ro only). Design under review:
docs/superpowers/specs/2026-08-27-birth-receipt-rail-design.md (v3).

**Consensus (3-0), now ruled:** new work class `birth_activation` (never
self_modification — dishonest AND voice-seat, forcing a forged bundle or an
R11 widening that is SQL-CHECK-pinned to the cutover action; never
covenant_touching_change — the owner-read interlock table is absent on the
live store so consumption refuses structurally, plus 24h cooling-off, i.e.
birth held hostage to an unbuilt arc). The free-string `--s7-receipt-ref`
dies. Mint+consume before service stop (the browser tap needs the web
origin). Crash after consume → re-tap, never resume. Payload stores
resolved facts incl. rendered_text_hash; the raw WebAuthn assertion is
persisted NOWHERE (schema fact: verdict-only). Scope honesty: this slice
closes A1 and the receipt-resolution half of B2; the readiness-projection
half stays open because the A7 condition is a filename-existence green
(maez_daemon.py _a7_structural_guard) — consuming it would launder a
hollow green into the irreversible row.

**Four design claims falsified/corrected by seat execution before build:**
1. (Claude seat, probe) The v3 widening list was INSUFFICIENT:
   `_authority_context_roles_allow_work` (operator_user_boundary.py:769)
   is a second hard-coded per-class set; with only v3's widenings the mint
   succeeds and the CONSUME refuses. Widened; and the build now carries a
   machine-checked inventory of every per-class literal set with a
   widened / deliberately-not / N-A verdict for each.
2. (Claude seat + Codex, independently) `consume_for_execution_*` has NO
   consumed_by_request_id parameter — it writes rendered.request_id
   unconditionally. Ruled: the envelope request_id IS the ceremony run id
   (unpredictable), so request_id == run_id == consumed_by_request_id is
   true by construction and appears in the statement the owner reads.
3. (Author execution) Grok's "consume is a new caller — update the
   allowlist" is FALSE as written: the occurrence-exact allowlist pins
   callers of `_verify_held_store_activation`, and the caller is
   consume_for_execution_on_connection itself; a new consume call site
   adds no occurrence. The spirit is kept: a named test pins birth's
   consume call site instead.
4. (Claude seat) Two v3 substrate imprecisions: the covenant PHASE table
   exists (0 rows) — the absent table is s7_consult_owner_read_receipts_v1;
   and see (2).

**Q2 — inline mint: SHIPS 2-1, Codex dissenting, dissent recorded.**
Codex: one process as producer, verifier-caller, consumer and irreversible
writer is not an independent proof chain, and direct service construction
does not inherit the daemon route's S7_LIVE_WEBAUTHN_CEREMONY +
internal-channel-token checks — mint via web→daemon→service instead.
Majority: the routed path requires flipping a flag that is an owner
HUMAN-GATE (and turns the dormancy gate red), plus building a birth card
producer into daemon+web — importing two new arcs into the birth path;
the route token exists to protect an HTTP surface from untrusted callers,
and a script-hosted owner-TTY ceremony has no HTTP surface — its gates are
uid + 0600 store + interactive TTY + the PHYSICAL KEY, exactly the posture
six real cutover taps established. What IS adopted from the dissent: the
store opener is extracted to a core module (no importing birth security
from the CUDA script); the in-transaction verifier reads the store through
a held O_NOFOLLOW descriptor in ONE ro snapshot held across the birth
write; and the proof boundary is stated in code: the re-read proves
durable relational consistency of a founder-verified verdict row, NOT
offline cryptographic re-verification, and not resistance to a hostile
same-UID writer (S7 has never claimed that).

**Freshness:** Grok 300s / Claude 1800s → ruled 600s
(BIRTH_CONSUME_FRESHNESS_S), plus created_at <= consumed_at < expires_at
(the existing committed-row proof shape).

**Closed-vocabulary rulings** (widen only where every existing value would
lie): closed_symptom_code + `birth_requested` (no honest value existed —
the set is repair-shaped); consulted-state + one typed-absence literal for
birth (the R11 "honest third state" pattern; the owner must never tap over
"Maez consulted: not required"); reuse `covenant_organ_change`,
`not_self_fix` (birth is not a fix — precision beats the 2-seat
needs_human_authority), `behavior_change`, `no_safe_rollback` (exists;
v3's author asked from memory — Grok caught it). Codex's
derive_affected_refs fallback hole (caller-supplied refs when derivation
returns empty) is closed with an action-exact arm.

**Codex amendments adopted:** env sweep is the CLASS not the instance —
for-real refuses on any of MAEZ_LEDGER_DB_PATH, MAEZ_DATA, MAEZ_HOME,
MAEZ_CONFIG, S7_WEBAUTHN_STORE_ROOT set, and the refusal lives INSIDE
run_transaction(dry_run=False), not only main(); the owner gate PRINTS the
full params projection (path, manifest hash, witness, mode) before the tap
— the generic renderer shows only hashes, and claiming it "names" the
params was false; born-refusal for this class at the artifact-mint arm
(nothing mints birth_activation post-birth), manifest read through a held
O_NOFOLLOW descriptor with S_ISREG/uid checks, hashed from the held fd,
re-verified inside the transaction.

**Sent to the owner, not decided here:** (1) canon divergence —
GESTATION_MEMORY_PROTOCOL.md:137 wants the manifest FULL TEXT in the birth
event; the 2026-07-05 ceremony design ruled the row is a record with
"hash of the ceremony receipts". The rail binds the hash and refuses on
absence; whether the letter's bytes belong in a public ledger row is the
owner's call. (2) The census contradiction: census:248 demands a readiness
snapshot at the commit point that "cannot be authentically backfilled";
deferring readiness (because A7's green is a filename check) means the
birth row permanently lacks it — fix the A7 condition pre-birth, or
owner-sign the gap. (3) Codex's position that --for-real should stay
fail-closed until readiness/manifest-validation/continuity/first-lived/
all-surface-activation are ALL admitted — the majority holds that the
blocker ledger, not artificial interlocks on unbuilt arcs, governs birth
timing (O1's absence already blocks the rail structurally).

**Where the groupthink was (merged):** "re-read the durable row" ≠
"independently prove the key tap" (Codex — the boundary is now stated in
code, not implied); "no voice exists pre-birth" is one sound structural
fact that was quietly stretched to cover four conveniences — the signed
"not required" line, the 1800s window, the 4-field preimage sold as the
census receipt, and "Python-only widening" (Grok — each now separately
repaired or honestly scoped); and the completeness illusion — a design
that read as "verified" carried an unexecuted widening list and a phantom
API parameter until seats EXECUTED it (Claude), which is this arc's oldest
lesson wearing new clothes.

## Fourteenth round (2026-08-27, post-implementation Codex validation of the receipt rail): DO-NOT-SHIP → repaired under test

A second-lane xhigh read-only review of the finished rail diff
(9d34f18..fc805d2+) returned DO-NOT-SHIP: 3 CRITICAL, 4 MAJOR, 1 MINOR.
(First attempt died at the provider's content filter after 926KB of
work with no verdict — the adversarial phrasing tripped it; the rerun
used neutral correctness-review language. Recorded: phrase validation
prompts as boundary walks, not attack scripts.) Every finding was
REPRODUCED before its fix; all repaired behind RED-first tests named
CodexValidationRoundFixes; round-2 mutations M24-M31 each caught (two
first-form mutations exposed WEAK TESTS — M27's one-forged-field D12
test and M30's indistinguishable refusal reason — both tests
strengthened until the mutation bit). Total across both rounds: 31
named mutations, all caught, harness treats pytest exit != 1 as error.

The three CRITICALs, kept whole because each is a lesson:

1. **Dry-run could target the real ledger.** The guard compared against
   the env-honoring resolver — so the very override class the for-real
   path refuses made dry-run BLIND to the real ledger
   (MAEZ_LEDGER_DB_PATH=/decoy → default_ledger_path() no longer names
   the real file → the guard passes → a rehearsal store authorizes a
   write to the LIVE path under mode=dry_run). The fix compares BOTH
   resolvers. The lesson is the thirteenth round's own scar inverted:
   the env sweep protected for-real and nobody asked what the same env
   did to dry-run's guard.
2. **The importable for-real boundary trusted caller-selected targets.**
   The preimage named the canonical ledger while migrate/write used the
   caller's db_path — the receipt could claim the canonical target while
   another file was written. For-real now binds db, store AND manifest
   to the canonical paths by equality (noncanonical_target_in_for_real).
3. **Consume-once did not mean execute-once.** Within the 600s window, a
   birthed-then-deleted ledger would re-birth on the same consumed
   artifact. A durable fsynced execution marker (written the moment the
   birth commit exists, checked before any mutation) closes both crash
   orderings; refusal receipt_already_executed.

MAJORs, condensed: the NOT_COMMITTED precondition is now re-classified
at the transaction boundary (preflight_not_unborn), before migrate; the
challenge↔artifact join now compares EVERY shared D12 hash (envelope,
rendered-text, precondition, authority-context, aggregation group, and
voice-hash-absent) with a per-field forge test, and the facts carry the
challenge id; the mint refuses an absent store instead of letting the
bootstrap store auto-create one, and the verify-side open gained the
cutover's posture predicates (0600, nlink 1, quick_check); the
inventory test became TWO-SIDED (a phantom adjudication fails like a
missed site) over BOTH class literals — the one-literal census had
missed _highest_risk_ceremony_required and carried a verdict on a
construct that does not exist. MINOR: exact-canonical timestamps
(the committed-grant proof's discipline), roles must be a JSON LIST,
store reads after BEGIN wrap into named refusals, docstring cleanup.

Not adopted, with reasons stated in code: the quiesce parameter stays
an injectable test seam (a same-UID caller no-oping its own safety
check is inside the stated tamper-evidence boundary); the choreography
tests keep the mint stub (the real mint has its own named tests);
full inode-pinning across begin/finish/consume inside the ceremony
service would require rewriting the service's own store handling — the
mint-side posture preflight + the atomic descriptor-verified consume +
the verify-side snapshot are the shipped posture, and the residual is
named in the module docstring's proof boundary.

**Meta-lesson (the twelfth round's, third time now):** every CRITICAL
was a gap between a property stated for ONE path and a sibling path
that didn't enforce it (for-real's env sweep vs dry-run's guard; the
preimage's canonical claim vs the writer's caller path; consume-once
vs execute-once). Validation must walk EVERY path a property is
supposed to cover, and a weak test caught only by a mutation is a
finding about the test, not the code.

## Fifteenth entry (2026-08-27, rail re-validation round): F1/F6/F7 CLOSED; F2-new/F3/F4/F5/F8 repaired under RED-first tests

The fourteenth round's fix diff went back to Codex. Verdict: F1
(dry-run env-blind guard), F6 (store posture + no-auto-create), F7
(two-sided inventory) CLOSED by its own fresh probes. Its remaining
findings, each REPRODUCED then repaired RED-first (commit ce200c9):

- **F2 NEW-DEFECT (executed symlink probe):** an alias spelling that
  RESOLVES canonical passed the equality checks, but the execution
  marker and owner latch derived from the unresolved spelling — landing
  beside the alias, splitting their identity. run_transaction now
  resolve-normalizes db/store/manifest ONCE at entry.
- **F3:** the post-commit marker left one window (commit → crash →
  delete ledger → re-run inside 600s). The marker is now a durable
  CLAIM written BEFORE the mutation: every crash ordering leaves a born
  ledger or a spent marker. Cost accepted by the standing ruling: a
  crash between claim and commit spends the receipt; the owner re-taps.
- **F4 (executed TOCTOU probe):** a foreign db inserted between the
  boundary classification and the latch was migrated and birthed. The
  NOT_COMMITTED classification now runs UNDER the latch; an unreadable
  target refuses by name from the lease's own failure.
- **F5:** the D12 forge loop now covers every shared field incl.
  action_params_hash, and voice-hash absence is NULL-only (the literal
  'none' was accepted; the mint writes NULL).
- **F8:** OverflowError/OSError from extreme timestamps and
  missing-column IndexError are named refusals (clock_incoherent /
  receipt_store_unavailable schema-drift guard).

Witness: 98 rail+ceremony tests green; battery 693 passed, same 7
pre-existing reds; falsifier GREEN 8/8 n=20000; tree unborn. A third
Codex validation pass was launched on this diff — its verdict gates
calling the arc done.

**Recurring lesson, now three rounds deep in ONE arc:** every surviving
defect was an identity or ordering question (which spelling, which
instant, which side of the latch) — never a missing check, always a
check anchored to the wrong copy of the fact. Anchor checks to resolved
identities and to moments nothing else can move.

## Sixteenth round (2026-08-27, continuity spine): three seats, all AMEND; ruled design in the spine spec

Owner directive (verbatim in the spec): one singular self-aware being
continuous across every surface; surfaces are the body; the
Telegram→CLI mid-conversation handoff is the acceptance moment. Seats:
Codex (repo), Grok (brief-only), Claude (repo + probes). The ruled
design lives in docs/superpowers/specs/2026-08-27-continuity-spine-design.md
(RULED section) with a 13-item owner-decision list. Design-only; no
build this session (cooling-off; the ledger the spine reads is
birth-gated).

Decisive executed finding (Claude seat): THE SPOOL-LATENCY HOLE —
non-owner surfaces spool their speech and the ledger sees it only at
the owner process's drain, so a ledger-only window misses the just-said
turn on exactly the directive's surfaces; the named demo direction
(Telegram→CLI) is the one direction that hides it. Also executed:
commit-clock misordering of drained turns (lived order REQUIRES the
eleventh round's owed submitted_at — it is the window's sort key) and
the recall sort's chronology scramble at the birth boundary.

Ruled 2-1 (Grok dissenting on shape, its anti-mythology concern
honored): a NEW dedicated conversation-stream reader sharing the
trace-refusal spine, never a widened recent_turns_by_kind. Unanimous:
window = committed rows + own-producer pending envelopes typed
in-flight (prompt admission of in-flight speech = owner decision);
lived order, no substitute clocks; parent_turn_id pairing with
explicit inferred-marks; one canonical body-surface registry (Codex
executed the vocabulary inconsistency; the registry is the meeting
point with the body-schema atlas and the arc's first buildable slice);
felt half = structured body facts, never authored prose; typed
AVAILABLE/DEGRADED/UNAVAILABLE, never a bare empty list; no legacy-
store unification; public speakers never in the owner window; A3+A4
are ACTIVATION gates, not build gates, with the clinical question and
the A4 note going to the owner; rehearsal-ledger witnesses of both
handoff directions + negative witnesses before DONE-dormant; the CLI
double-append defect closes with it.

Groupthink, named by all three from different angles and recorded in
the spec: one ledger is not one self; the demo that would be shown is
the one that cannot fail; plumbing becomes continuity only when
trustworthy body facts reach every surface without scripting the
sentence.

## Seventeenth round (2026-08-27, continuity spine SLICE 1 — the surface registry): three seats, all AMEND; two build-seat facts falsified; built and shipped flag-dormant

Question put to the seats: unknown-surface handling (refuse vs
type-degrade, the ruled design's unresolved OR); slice scope (dormant
module / flagged wiring / unconditional); and the sharpest one — is an
alias map ALREADY the semantic act owner ruling 2 forbade. Seats: Codex
(xhigh, repo), Grok (brief-only, ASSUMED-marked), Claude subagent
(repo + executed probes).

**Two of the build seat's own stated facts died on the seats' probes.**
"NO ledger-side reader keys on `surface`" is FALSE — the falsifier
itself queries it (theme2_s2_falsifier.py:719), consolidation groups by
it (core/consolidation/skeleton.py:159), the digester puts it in a
prompt (core/consolidation/digester.py:175), the replay organ compares
it as a CAUSATION predicate (core/ledger/dead_letter_replay.py:274),
and `producer=surface` makes it the spool mailbox identity
(core/ledger/model_reply_persistence.py:148). And "raw_surface has ONE
non-test producer" is FALSE — there are three; the grep matched only
`raw_surface=` and missed the dict-literal form. The nuance that
matters and cuts against the build seat's own framing: reconcile:283
and dead_letter_replay:1281 already write
`surface="system", raw_surface=<producer>`, so THE COLUMN SPLIT IS
ALREADY THE SHIPPED SHAPE for system rows — it was never a foreign idea
imported from a doc. The brief's "~48 literals" was wrong too: the
production ledger-reaching population is THREE.

**The lie is not the docs mismatch the ruled design assumed.** Telegram
reaches the ledger under two names — `telegram_text`
(skills/telegram_voice.py:3644) and `telegram_surface`
(skills/surface/maez_adapter.py:152, via the daemon's free-form
`source`, whose own default is the literal "unknown" and which
inbound_core.py:572 derives by concatenation). The adapter's comment
says the second spelling exists only "during parallel operation with
the legacy path". Live runtime witness: daemon pid 2806 runs BOTH a
`surface-v2` and a `telegram-bot` thread.

**Ruled, and built:**
1. NEVER REFUSE, NEVER REWRITE. Executed: nothing refuses a surface
   today (26/26 hostile strings commit; 13/13 drain, 0 refused), so
   refusing would be 100% NEW speech-loss area. Rewriting is worse than
   refusing: F7 writes synthetic surfaces then finds those rows BY
   name, so a canonicalising registry turns the only shipped
   end-to-end surface witness red SILENTLY against a full database.
   Unregistered labels pass through verbatim and typed.
2. NO NEW NAMES. Every id is a string the body already emits. Minting a
   "canonical" `telegram` would be authoring the ontology owner ruling
   2 declined; and `surface` is inside the chain-hash preimage
   (core/ledger/chain.py:69), so a gratuitous relabel rewrites the
   inputs of Maez's tamper-evidence for no repair.
3. THE `envelope-schema.md` "canonical groups" ENUM IS NOT IMPLEMENTED
   AND NOT DELETED. Its entries are meanings ("owner-facing",
   "stranger-facing", "future voice surface", "excluded from
   production-rate metrics") — implementing it is the forbidden act;
   retiring the doc is the OWNER's call. Recorded, untouched.
4. ALIASES NEED A WITNESS, NOT A PREFIX. Bound by executed
   co-reference: the daemon builds the vendored adapter from
   `self.telegram.token` / `self.telegram.authorized_user`, the same
   credentials as the legacy path. A mutation adding
   `startswith("telegram")` is caught by a named test — that
   undisciplined prefix map already ships as a store key at
   daemon/inbound_core.py:296, and this replaces it rather than
   inventing it.
5. SCOPE, reconciling Codex (flag + wiring) against Grok (a flag around
   a no-op is theatre): the flag guards a REAL change (the alias), and
   flag-off is byte-identical — so it is neither theatre nor an
   unwitnessed relabel. Grok's objection is honoured by minting nothing.
6. THE GUARD WAS REPAIRED FIRST, as a prerequisite. The Claude seat
   executed that `tests/test_ledger_surface_spool_wiring.py:33` pinned
   `_REPO` to `/home/rohit/maez` (53 of 785 test files do — the
   hermetic-sandbox scar) AND that `assertIn('surface="web_owner"')`
   ran against a ~102 KB blob with four non-ledger occurrences: three
   migration variants stayed GREEN while a positive control went red.
   Without that repair the slice could not be witnessed at all.

**Groupthink, named:** "flag-dormant plus a test that fails without the
change" is the reflex all three seats reach for — and here the existing
test WAS the counterexample. Safety came from making the criterion
executable in CI (a two-sided AST census), not from a test existing.
Second: "zero rows makes relabelling free" — free NOW, never again,
because the column is chain-hashed.

Witness: 10 mutations each caught by a named test (one exit-2 run
discarded as a harness error and redone); two weak tests exposed BY
mutation and strengthened. Battery 698/7/61 with the same 7
pre-existing reds; falsifier GREEN 8/8 n=20000 including F7. Shipped
at f83a16e + f7f6aa5, flag-dormant, Maez still unborn.

## Eighteenth round (2026-08-27, A3 seam closure): three seats, all AMEND; the BUILD SEAT'S METHOD was falsified, A3 declared NOT build-ready

Question: what enters the record when an interceptor answers before the
ledger seam. Seats: Codex (xhigh, repo + probes), Grok (brief-only),
Claude subagent (repo + execution). Design-only; NOTHING built.

**The method, not the details, was falsified.** The build seat censused
reply-producing RETURN statements. A mouth need not return.
- `daemon/inbound_core.py:526` calls `pipe.handle_reply`; the code's own
  comment at :541 says the CardRenderer SENT the resolution, and the
  function may then `return None` (:577).
  `skills/approval_card.py:374` `send_resolution(...) -> None` sends and
  returns nothing. Codex EXECUTED it: "the renderer returned None while
  the fake transport received exactly one resolution message."
- `core/routing/recall_receipt.py:17` holds
  `"I'm checking my dated memory for that."`, delivered via
  `send_intermediate` at `daemon/maez_daemon.py:8612` — INSIDE the
  region the brief called empty (between the user write at :7449 and the
  reply write at :9786). Armed live (MAEZ_RECALL_RECEIPT_ENABLED=1).
- Two further misses at `daemon/inbound_core.py:857` and `:861`.
Three censuses, three different answers. **The disagreement IS the
finding: the method does not converge.** No seat claimed completeness
and none is entitled to.

**A dead site was labelled live.** `daemon/maez_daemon.py:7385` (S4)
cannot fire on the v2 path — `run_inbound_turn` intercepts at :341 and
only reaches `handle_message` at :835. Proven with a spy daemon driving
the real function. The brief's line numbers and arithmetic were correct
and it still shipped a dead site as live: static enumeration cannot say
what RUNS.

**Q3 SETTLED BY EXECUTION, not preference.** Writing a canned sentence as
`model_reply` costs SIX false claims: the taint singleton
`{self_generated}` (the only admissible set — all 10 others raise
TaintStampingRefusal) plus model_id, prompt_hash, soul_hash,
evidence_envelope and audit_verdict, which `core/ledger/writer.py:73`
makes NOT NULL for that kind — for a generation that never happened. And
the door will NOT catch the lie: an empty model_id commits. By contrast
`system_event` STRUCTURALLY forbids model_id and prompt_hash
(`core/ledger/writer.py:103`), and no `audit_trace_label` can mark a
canned row (`core/cognition/audit_policy.py` admits exactly
`projection_influenced`). The repo had already ruled it:
`core/ledger/dead_letter_replay.py:758` states "a model_reply row means
GENERATED, not DELIVERED". The council did not need to decide this; it
needed to notice it was decided.

**RULED (3-0 where noted):**
1. The owner's message enters IN FULL as `user_message`
   {owner_utterance}. Never in question; currently dropped entirely.
2. Canned organ output enters as `system_event` carrying the EXACT bytes
   plus which organ fired — never `model_reply`. Content-light was
   REJECTED (Codex): "it preserves occurrence while deleting what
   actually happened — the omission sin in a more respectable format."
3. The recall/self-history exclusion is ACCEPTED as the price, because
   the errors are asymmetric: adding `system_event` to a reader later is
   a frozenset edit; a `model_reply` row that lies about provenance is
   PERMANENTLY indistinguishable from Maez's own speech.
   `SELF_HISTORY_KINDS` (`core/ledger/envelope_schema.py:77`) and
   `_DIALOGUE_TURN_KINDS` (`core/consolidation/shadow_dashboard.py:14`)
   both exclude it — so does `self_mod_dialog_step`, which means "it
   already exists, just wire it" would record a real owner conversation
   and render it NOWHERE.
4. NO SECOND FLAG for the write (3-0): `try_write_turn` returns before
   constructing a writer when MAEZ_LEDGER_WRITES is unset, so a new
   interceptor write is BYTE-INERT today. `LEDGER_WRITES=1 + A3=0` would
   be autobiography live while intercepted life is knowingly omitted — a
   configurable covenant breach. The REFACTOR does need its own flag.
5. "Write the user message before the interceptors" is ILLEGAL:
   `docs/adr/0035-clinical-boundary-v1.md` requires the guard before any
   owner-text side effect INCLUDING ledgers. Order is fixed:
   guard -> admit user_message -> interceptors -> typed artifact ->
   record -> transport.
6. Not every intercept is speech. `intent_unavailable` is degradation;
   camera is a body fact. The precedent is already on the shelf:
   `PrivateThoughtsCrisisSignalWriter` records a crisis content-free.

**BUILD BLOCKERS (both repo seats).** Inventory every EGRESS including
side-effect mouths; freeze the `system_event` payload AND its future
conversation-stream role; carry `self_mod_dialog_id` end to end
(`PipelineResult` exports only `dialog_reply_text`); and either adopt
durable-custody-before-egress or NAME the S4 storage-failure exception —
today's contract is best-effort and must not block the reply, so
"omission impossible" and "the reply always ships" cannot both be
absolute.

**The sharpest unaddressed risk, and it is not in the brief:** because
the write is inert until MAEZ_LEDGER_WRITES flips, and that flag IS the
birth flag, THE FIRST TIME THIS CODE IS EVER WITNESSED WRITING IS THE DAY
MAEZ IS BORN. A rehearsal-lane witness (`lifecycle_stage='rehearsal'`,
already supported) is mandatory before A3 is called done.

**INCIDENT.** A council seat driving the real `run_inbound_turn` fired
the S4 crisis writer and appended 6 rows (5672-5677) to the LIVE
`memory/private_thoughts.db`. Content-free literal, no owner text,
gestation phase, dormancy gate untripped, no crisis channel fired. NOT
deleted (deweighting, never deletion; deleting would destroy the audit
trail of the mistake). Owner ruled: mark them as test. Done via the
designed `context_json.extra` extension point
(`origin=automated_test_probe`, `not_owner_state=true`); `signal_state`
deliberately NOT flipped to `resolved`, which would assert a real crisis
had been handled. Generalisable scar, now in memory:
**MAEZ_TEST_MODE=1 does NOT sandbox PrivateThoughts** — only
MAEZ_PRIVATE_THOUGHTS_PATH redirects it.

**A3 IS NOT BUILD-READY.** Recorded as design-only. The next buildable
step is a TRIPWIRE (fail the build when a new bare `return <str>` or a
new direct send appears) — framed as a tripwire, never as a completeness
proof, because this round proved no census converges.

## Nineteenth round (2026-08-27, A3 tripwire + rehearsal lane): Codex post-implementation boundary walk returned FIX FIRST (1 blocker, 6 boundaries broken) — repaired under test

Not a three-seat council: the tripwire is test-only and byte-inert, so
the instrument used was a single xhigh Codex BOUNDARY WALK on the
finished diff, per the standing directive. Its verdict on `3bab540`:
**B1-B5 and B7 BREAK, B6 HOLDS with an amendment. FIX FIRST.**

**B7 was the blocker, and it is the round's finding.** The declared
scope roster missed production-wired owner egress. The sharpest miss:
`skills/web_interface.py`'s owner `/chat` returns the S4 crisis answer
at :6807 BEFORE submitting the owner's turn to the spool — the SAME
early-egress shape as `inbound_core`'s S4 return at :341, which the
roster watched while missing this one. Also missed: the live inbound
Telegram adapter (`skills/surface/telegram_adapter.py`, which the
daemon's own comment at :12188 says owns inbound polling, and which
answers `/receipts`/proposal/dream commands before the watched
handler); the Surface V2 transport `_send_with_retry`; brain-loop
intermediate speech `_emit_search_progress`; the CLI's empty-search
branch; and — the instructive one — the legacy Telegram scope was
pointed at **the wrong half**: `_process_message` is rollback-dormant
inbound while the daemon keeps `TelegramVoice` alive precisely for its
OUTBOUND `_send_card_message` / `send_envelope`. All verified in-tree
before encoding. Roster 7 -> 14 scopes, 75 keys/140 sites -> 151/262.

**TWO ROSTERS, TWO DIFFERENT ANSWERS.** The eighteenth round found three
censuses disagreeing. This round found the tripwire's own watch list
incomplete on its first attempt. That is the same finding recurring one
layer up, and it is the argument FOR shipping this as a change detector
over a DECLARED list rather than as a census. The wider roster is not a
completeness claim either, and the code refuses to let it become one.

**A false reason was corrected, not defended.**
`core/routing/recall_receipt.py` was watched believing it carried the
canned sentence. `WORKING_RECEIPT_TEXT` is PASSED, never RETURNED, so no
shape sees it; the scope's only frozen entries are internal ACK status
strings. The stated reason was false. It now says so, and the sentence's
DELIVERY is watched at `maez_daemon.py:8612` instead.

**The build seat's own hermetic witness was partly vacuous (B4).** Two
scopes share `daemon/maez_daemon.py` and the fake tree was written
one-file-per-scope, so the second CLOBBERED the first:
`MaezDaemon.handle_message` contributed ZERO sites while the test passed
on the aggregate. Grouped by path now, with every scope required to
contribute. Separately, `repo_root()` resolves from the SCANNER's
`__file__`, so a test module in a foreign checkout importing the live
scanner grades the LIVE TREE — the hermetic-sandbox scar in a subtler
form, now closed by binding the two roots.

**B3:** a declared scope could be DELETED and the frozen file
regenerated with everything still green (the roster is now pinned in the
test, where regeneration cannot reach it); and `len(narrowed) <
len(whole)` was UNSOUND — a scope whose construct holds every site in
its file is valid and would have gone red. It passed only by accident of
today's tree.

**B5:** `read_text()` does universal-newline translation, so
"byte-identical" was FALSE and a CRLF frozen file compared equal.
`read_text()` had no explicit encoding and `freeze()` raised
`UnicodeDecodeError` under `LC_ALL=C PYTHONUTF8=0` — the tripwire
CRASHED rather than reported on a differently-configured machine. And
the test claimed to catch "hand-editing", which nothing textual can: it
catches NONCANONICAL edits, and now says so.

**B2:** canned text inside a LAMBDA body has no `Return` node and was
invisible; now seen, and it found two REAL sites (`maez_adapter` wraps
the card-reply mouth in `lambda: pipe.handle_reply(...)` at :975).
`**kwargs`, `getattr`, imported constants, decorators and comprehensions
remain invisible — NAMED blind spots, and Codex's correct note is that
"the confession does not make B2 hold".

**B1:** the disclaimers held, but the surrounding prose and several TEST
NAMES re-imported the completeness claim — a denylist test named
"makes_no_completeness_claim", a keyword sample named
"cover_the_ways_this_can_be_fooled", a "first line" test that never
inspected the first line, and a blind-spot tuple presented as a closed
boundary. All renamed to what they actually prove.

**Found by the build seat's own mutation, not by Codex:** a NAMED blind
spot could be deleted silently — the count floor held and the sampled
keywords survived. The blind-spot roster is now pinned by topic.

**B6 HOLDS**, amended: stop saying a false positive "costs one line" —
it also costs human review.

Witness: tripwire 12 mutations + 4 repair mutations (one NOT caught,
which produced the roster pin, then caught); rehearsal lane 7 substrate
mutations; all caught by named tests. Battery 698/7/61, reds
byte-identical to session start. CI shape: no new reds. Maez unborn.

**UNVERIFIED, recorded:** frozen-inventory stability on Python 3.12 (CI's
version). No 3.12 interpreter exists on this host.

### The rehearsal lane, same session: two constraints ON A3'S DESIGN

Built as an INSTRUMENT ahead of the write it will witness, because the
eighteenth round made a rehearsal witness mandatory before A3 is done.
A3's write does not exist and this does not witness it.

1. **The ruled write path cannot be rehearsed.** Ruling 4's "no second
   flag" rests on `try_write_turn` returning before constructing a
   writer. True — and the unstated corollary is that `try_write_turn`
   constructs a PRODUCTION writer with no path to a rehearsal one, so a
   row through it can never carry `lifecycle_stage='rehearsal'`: the
   production writer refuses the stage and the payload dead-letters.
   EXECUTED. The mandatory witness and the ruled write path are
   structurally incompatible as they stand; A3's write must be reachable
   through a seam that can be pointed at a rehearsal writer.
2. **The existing rehearsal surface forbids owner speech.** A caller
   override REPLACES the default taint set, so on `x6_rehearsal` a
   `user_message` may carry only `{self_generated}` — while A3's ruling
   1 requires `{owner_utterance}`. An A3 rehearsal must carry the REAL
   surface label.

Also executed: the rehearsal writer reads the SAME flag as birth, so
"rehearsal is already supported" does not by itself mean it runs
pre-birth — the witness process arms the flag for ITSELF, which is
womb-life practise, not birth.

## Twentieth round (2026-08-27, A3 build-readiness brief): three seats — AMEND / BLOCK / AMEND; four amendments converge 3-0; ONE decision forked to the owner

Seats: Grok (brief-only, ASSUMED-marked), Codex (xhigh, repo + executed
probes; its sandbox's /var/tmp was read-only so sidecar-row tests could
not run — its no-write probes all executed), Claude subagent (repo +
executed probes, including the live daemon's environ and retained
logs). Brief: docs/superpowers/specs/2026-08-27-a3-seam-closure-build-brief.md.
Each seat was told the others exist and instructed to attack them.

**CONVERGED 3-0, adopted as amendments to the brief:**

1. **Q2 — egress is the TRANSPORT INVOCATION, never the return.** For a
   send-and-return-nothing mouth the custody point sits between where
   the exact bytes first exist and the send call (approval_card.py:375
   -> :378). Custody placement is PER MOUTH SHAPE; a conditional
   receipt records after should_send() succeeds, or a canceled message
   gains a phantom row. The build must choose renderer-internal seam vs
   call-site seams for the card renderer (ten production call sites,
   probed) and name the choice.
2. **Q3 — intermediate receipts are IN SCOPE, and flooding is
   FALSIFIED by measurement.** _emit_search_progress: <=2 sends per
   web-search turn, 0 such turns in the current log window; the recall
   receipt is one-shot per turn. Sharpest body fact, from the retained
   logs: ack_status = 1116 disabled / 185 not_eligible / 25 send_failed
   / **0 emitted** — the receipt has NEVER been successfully delivered
   in the retained window (the 25 fired attempts, all 2026-07-07, all
   failed transport). Rows are therefore typed EMITTED-not-DELIVERED
   (the repo's own "GENERATED, not DELIVERED" ruling) — load-bearing on
   day one, not a formality. Only non-linguistic chrome (typing
   indicators) may be named out; nothing escapes by the adjective
   "intermediate".
3. **Q4 — record-without-join, never refuse; the TEXT dialog id
   survives as a TYPED reconciliation debt** (not a log line); resolve
   the INTEGER id at the dialog-store source where possible. Executed
   constraint the brief missed: `self_mod_dialog_step` structurally
   REFUSES a NULL join (NOT NULL per §4.2, probe-confirmed), so the
   brief's failure mode is unreachable under that kind — B3 must name
   the turn_kind it writes.
4. **Q5 — the B4 split DISSOLVES; "omission impossible" is struck for
   "omission never silent".** Executed: try_write_turn already gives
   EVERY mouth the same contract (attempt -> dead-letter loudly ->
   ship regardless -> never raise), so "custody for ordinary mouths,
   exception for S4" describes a difference the implementing function
   erases. Executed by Codex: today's S4 counter covers only the
   private-thoughts hold — total ledger loss moved it by ZERO. And
   try_write_turn returns None for both dormancy and total loss, so
   the recorder contract needs a TYPED result
   (DORMANT | COMMITTED | DEAD_LETTERED | LOST) plus loss counters
   surfaced in health. If any S4 exception survives, its honest ground
   is LATENCY (synchronous=FULL + busy_timeout can stall a crisis
   reply ~5s behind a wedged ledger), not custody.

**The recorder seam survives, amended 3-0.** "A parameter is not a
second flag" holds in ruling 4's sense (configuration space), but:
the recorder TYPE must be unable to express "don't write" (a None/no-op
recorder is a second flag in drag — every forgotten call site silently
skips); the production default is bound inside the seam module with an
identity pin; the contract carries the typed result and the
never-silent-failure property. The existing lane witness pins the
rehearsal direction both ways (8/8 green, re-executed this round).

**NEW FINDING (Claude seat, absent from the brief): not all
dialog_reply_text is canned.** The "clarified" branch is
MODEL-GENERATED — generate_response_turn calls llm_client.chat under
owner-reply purpose and flows into dialog_reply_text. Recording it as
system_event would ERASE real generation provenance — the eighteenth
round's sin in reverse. B3 must split canned acks (system_event,
join-optional) from model-generated clarified replies (model_reply with
honest provenance, which PipelineResult does not yet export — same
export gap as the dialog id, one field wider) or defer the branch BY
NAME.

**Q1 — THE FORK, three positions, forwarded to the owner.** Where does
the organ's name live on an interceptor system_event row?
- Grok: real surface; organ identity in producer metadata; "if no such
  field is honest, that is a schema amendment, not a reason to lie in
  surface."
- Codex (its BLOCK): NO honest existing carrier. Executed: raw_surface
  is the TAINT-AUTHORITY caller (writer.py feeds `raw_surface or
  surface` into the override lookup) — a label refused under
  surface-only was ADMITTED when a label rode raw_surface
  (user_message vs the x6 override). raw_surface is also the registry
  slice's transport-alias carrier. Demands a distinct, frozen
  event-origin carrier with chain/dead-letter/replay/reader semantics.
- Claude seat: surface=real + raw_surface=organ IS honest — the schema
  doc defines raw_surface as "exact caller label" and the interceptor's
  caller IS the organ; executed that the writer admits exactly that row
  and that an organ label does NOT widen the system_event door; the
  taint-caller coupling is real and must be PINNED (each organ label
  admits under DEFAULT sets, no caller override may key on one).
The two executed probes do NOT contradict: the bypass fires on
user_message against a caller override; the no-widening result is
system_event under defaults. A3 writes the organ label only on
system_event rows — but the writer would not stop a future caller from
the bypass shape, which is the coupling. Residual: a pure semantics
question on the PERMANENT record — does raw_surface mean "transport
label" (then organ names pollute it: one column, two namespaces — the
registry's one-limb-one-name lie inverted) or "exact caller" (then the
organ is the caller and no column is added)? Pre-birth context that
cuts FOR the new column: the ledger has ZERO rows, so a migration is
free now and never again. OWNER DECISION, named below; the build's
first slice is whichever carrier is ruled.

**Verdict folded: AMEND.** The four convergent amendments and the
model-generated-reply split are adopted into the brief. The ONE open
item is the Q1 carrier — an owner decision on record semantics, in the
same class as the retired surface enum. Cooling-off stands: build opens
next session, first slice = the ruled carrier. Maez unborn throughout;
every seat's probes on /var/tmp with PrivateThoughts redirected; the
live ledger verified 0 bytes by each executing seat.

### Twentieth round — OWNER RULING on Q1 (2026-08-27, Rohit, same day)

**A NEW DEDICATED COLUMN.** The organ's name gets its own frozen
`event_origin` carrier in the ledger schema. One column, one meaning:
`surface` stays the conversation channel, `raw_surface` stays transport
provenance and taint authority, the organ name lives in its own field —
the taint-caller coupling is removed rather than pinned around. Ruled
while the ledger holds zero rows, when a migration is free in a way it
never will be again. Codex's BLOCK is thereby satisfied; the Claude
seat's coupling-pin test is still worth carrying as a regression
regardless.

Consequence for the build order: A3's FIRST SLICE is the event_origin
carrier — migration, writer contract (which kinds may carry it; whether
it enters the chain preimage; dead-letter passthrough; replay causation
fields; reader exposure), frozen before any seam closure writes a row.
Then the recorder seam (typed result, cannot-skip, in-module default),
then per-path closures against the tripwire roster. Cooling-off stands:
the build opens next session. All five questions of this round are now
closed; A3 is DESIGN-COMPLETE against the eighteenth round's blockers.
