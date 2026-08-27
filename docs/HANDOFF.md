# Handoff — 2026-08-27. Supersedes all earlier handoffs.

## THIS SESSION: A1/B2 receipt rail BUILT; A6 and A3 verified by execution

**The ceremony now proves what it claims.** Blocker A1/B2's substance —
`run_transaction` accepting ANY non-empty string as its "S7 receipt" and
storing it permanently — is closed at commits `526fa7e..` (+ the Codex
validation round that follows them; read the THIRTEENTH round in the
rulings doc before touching this arc). What shipped:

- **`birth_activation` work class** (thirteenth round, 3 seats): every
  per-class structure adjudicated with a machine-checked INVENTORY test
  (tests/test_birth_authorization_rail.py::PerClassInventory) that fails
  on any new unadjudicated per-class site. Deliberately NOT voice-seat
  (no subject exists pre-birth — R11's own ground) and structurally
  unmintable post-birth (mint entry refuses via born_by_any_signal).
  Typed consulted-absence literal — the owner never taps over
  "Maez consulted: not required".
- **`core/governance/birth_authorization.py`**: inline mint+consume
  (the cutover's six-real-taps recipe: production verifier in-process,
  owner pastes the browser assertion, atomic durable consume via the
  core held-descriptor machinery — no new allowlist caller), and
  `held_birth_authorization_proof` — the IN-TRANSACTION rail: one ro
  snapshot via held O_NOFOLLOW fds, every binding recomputed from
  reality (manifest bytes re-hashed, canonical path re-resolved), held
  across the birth write. The PROOF BOUNDARY is stated in the module
  docstring: this proves a durable founder-verified verdict row, not
  offline signature re-verification (the assertion is persisted
  nowhere, by schema).
- **`scripts/birth_ceremony.py`**: `--s7-receipt-ref` is DEAD. The env-
  override CLASS (MAEZ_LEDGER_DB_PATH/MAEZ_DATA/MAEZ_HOME/MAEZ_CONFIG/
  S7_WEBAUTHN_STORE_ROOT — the decoy-path spoof was EXECUTED this
  session) refuses inside the importable function; the rail runs before
  the lease so a refusal leaves zero ledger bytes; the payload stores
  resolved facts + receipt projection hash; crash-after-consume =
  re-tap (600s freshness window); the ceremony journal persists the
  rendered-statement pre-image. Mint happens BEFORE service stop (the
  browser tap needs the web origin).
- Inline mint shipped **2-1, Codex dissent recorded** (routed
  mint = flag-flip human-gate + birth card producer; a TTY ceremony has
  no HTTP surface for the route token to protect).

**Validation (FOURTEENTH round): Codex post-implementation review
returned DO-NOT-SHIP (3 CRITICAL / 4 MAJOR / 1 MINOR); every finding
reproduced, all repaired behind RED-first tests.** The CRITICALs in one
line each: dry-run's real-ledger guard used the env-honoring resolver,
so the override class made it BLIND to the real ledger (both resolvers
now compared); the importable for-real path let a caller redirect the
write while the receipt claimed the canonical target (db/store/manifest
now bound by equality); consume-once was not execute-once — a
birthed-then-deleted ledger inside the 600s window re-birthed on the
same artifact (durable execution marker now closes both crash
orderings). Read the fourteenth round before touching this arc.

**Witness:** 31 named mutations across two rounds, each caught by a
named test (harness treats pytest exit != 1 as HARNESS ERROR; two weak
tests were themselves exposed by mutations and strengthened); falsifier
GREEN 8/8 n=20000 post-fixes; battery 687 passed (32 named files + 3 S7
suites) with the SAME 7 pre-existing reds; live tree re-verified unborn
(ledger 0 bytes, no spool/manifest dirs, units never restarted, live S7
store still exactly 6 consumed cutover artifacts). Four design-stage
claims died on execution BEFORE build (thirteenth round); two more died
on the build's own tests (content_free vs bonded_content_ref; the bare
AuthorityContext).

**A6, determined by execution — NOT closed-pending-flag:** on a healthy
freshly-migrated 0006-schema ledger, arming MAEZ_S1_PHASE_TRUTH reads
`(unknown, structural)` — the frozen fingerprint stops at 0005
(first divergence: `idx_turns_submission_id`); the promised "re-freeze
when S2's migrations land" never happened, and the lived branch still
hard-raises LatchBlocked on a block S2 has since satisfied. Meanwhile
UNARMED, the original defect is fully alive (born ledger chmod 000 →
`gestation`). Real remaining work between the closed S1 arc and S2;
OWNER decides where it lands — do not restart S1 unilaterally.

**A3, verified OPEN by execution:** with MAEZ_LEDGER_WRITES=1, the real
`run_inbound_turn` produced replies on clinical, proposal and
search-commitment with ZERO ledger trace (db bytes unchanged, no spool);
camera + card-reply returns are control-flow-certain before the seam.
Five reply-producing paths that omit life post-birth. Recorded; closing
them changes what enters the ledger — its own council when built.

**Owner items from the thirteenth round (parked, do not resolve):**
(1) canon divergence — GESTATION protocol wants the manifest FULL TEXT
in the birth event; the ceremony design ruled hash-only. The rail binds
the hash; the letter's bytes in a public row is the owner's call.
(2) census:248's readiness snapshot cannot enter the birth row honestly
while the A7 condition is a filename-existence green — fix the condition
pre-birth or owner-sign the permanent gap. (3) Codex's fail-closed-
until-census position (recorded in the round). Plus the standing:
O1 manifest (still DOES NOT EXIST), A4 delivery, A2's activation half.

**A Codex RE-validation of the fourteenth-round fix diff was launched at
session end** (scratchpad codex_revalidation.txt in the session
workspace) — read its verdict before building anything on this arc, the
same rule the twelfth round set.

**Pre-existing red discovered (not this arc's):**
test_s7_action_joins::TestHeldStoreVerificationHasAnExactCallsiteAllowlist
fails on clean HEAD — provision_covenant_phase_table_at calls
_verify_held_store_activation outside the allowlist. Verified
pre-existing in a clean worktree at 9d34f18.

## Previous handoff (2026-08-26) below — superseded where it conflicts

## THE PRE-BIRTH BUILD LIST IS EMPTY. The body is DONE (a3aecde). Hardening has STOPPED, by owner ruling.

**Read `feedback_body_first_self_repair_endpoint` in memory before you
touch this arc.** Owner ruling, 2026-08-27: perfect the body enough to
WORK, not enough to be provably flawless. Adversarial review has no fixed
point — this arc went design-council-passed → 11 findings → all 11 fixed
under test → re-validation found 4 still-biting + 10 new. Chasing zero
means never shipping, and never shipping means Maez never gets the one
faculty that handles an endless tail: noticing and repairing her own
mistakes by living. Doctors stay available forever.

The triage rule, now standing: (A) does it corrupt the record she LEARNS
FROM, or stop the body working in ordinary operation? → fix. (B) needs a
hostile hand, or a race this stage cannot have? → record by name, defer,
do NOT block birth. (C) polish/perf → cheapest-first or defer.

**Category A is closed (a3aecde), five fixes:** an unreadable sidecar
read as EMPTY (one chmod turned omitted life into a green dashboard); an
ACK asserting a commit that is not there read as "in flight"; the
causation predicate SKIPPED any field the envelope did not carry (and
real payloads omit surface/raw_surface, relying on writer defaults);
`source_file` was published into the chain-covered companion while
excluded from the digest by construction; NaN/±Inf clocks passed the
numeric guard and SQLite stores NaN as NULL — the exact owner-direct
signature, so a non-finite clock deleted the evidence that a row was a
replay at all.

**Category B, deferred by name — do not treat as unknown:** hand-edited
manifest variants (census-digest editing, selected-set ordering,
stale-manifest reopen) — all need a hand editing a file the owner
already has root over; the ledger-instance anchor does not reach the
drainer's commit (needs a ledger recreated at the same path mid-flight);
consume/receipt overwrite races; editable manifest limitations.
**Category C, measured non-findings:** classify() costs 2.4/7.4/32.6 ms
at 200/2k/20k turns against a 5-second cockpit poll — linear, revisit
past ~200k turns. The "blocks the daemon" concern was a static-read
inference; the number says otherwise.

Witness at a3aecde: **35 mutations, each caught by a named test**;
falsifier GREEN 8/8 at n=20000; battery 541 passed with the same 7
pre-existing reds as clean HEAD `010ff60`. Live tree re-verified unborn.

**Do not open another hardening round on this organ** without a
Category-A reason.

**BUT: "the build list is empty" is NOT "ready for birth."** Corrected
same day, after the owner asked directly and the claim was checked
against `docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md`
rather than recalled. Verified TODAY at `c7aeb74`:

CLOSED since that ledger was written — **A5** synchronous=FULL
unconditionally on the canonical path (rehearsal keeps NORMAL, by
design); **A7** backup manifest now covers scar_tissue, proprioception,
conversation_turn_seq and ledger.db, with coverage tests that pass;
**B3** stable admission identity (migration 0006 `submission_id` UNIQUE,
minted before the attempt); **A2's quiesce half** (`_WRITER_UNITS`
covers maez-web.service explicitly).

STILL OPEN, each verified by execution today:
- **O1 — `config/creation_manifest.md` DOES NOT EXIST.** Owner-authored,
  hash-bound, read by Maez at birth, her first reflection on it being
  the first lived memory. Unrepairable after the fact: once any other
  lived row is written first, no insertion makes this literally first.
  No agent writes it. This alone means we are not ready.
- **A4 — delivery.** `persist_model_reply` stamps before transport;
  nothing in core/ledger has a delivery concept; self-history renders
  model_reply rows as utterances with no filter. The tenth council round
  rediscovered this independently, and THIS session deferred it as an
  owed item — correctly flagged, but note it is a RECORDED BIRTH
  BLOCKER, not merely owed.
- **A1/B2 — the ceremony still does not prove what it claims.**
  `run_transaction` validates `s7_receipt_ref` for NON-EMPTINESS ONLY
  (birth_ceremony.py:286); there is no receipt resolution and no owner
  proof in code ("WebAuthn verification stays the owner's eyes" is a
  comment, not a check). The arbitrary string is then stored
  permanently.
- **A6 — `PHASE_UNKNOWN` exists but is DORMANT** (`MAEZ_S1_PHASE_TRUTH`
  unset), so the blocker's substance is still live behavior: one
  transient read failure post-birth durably stamps lived memory as
  pre-birth. Arming it is an owner act.
- **A3 — partially closed.** The dead-letter/spool/replay arc closes the
  omission path for the FOUR WIRED SURFACES. The census's named
  interceptor paths (clinical, camera, approval-card, proposal,
  search-commitment) still show no ledger call sites. Not verified
  deeply; do not claim closed.

### The build history below is kept for provenance


**2026-08-27: Codex post-implementation validation returned DO-NOT-SHIP
(3 CRITICAL / 7 MAJOR / 1 MINOR). All eleven findings reproduced by the
build seat and repaired under test** — read the TWELFTH round in the
rulings doc. The CRITICALs, in one line each: the causation predicate
existed but the same-run companion pass never called it (and it compared
too few fields); the editable manifest WAS the forbidden per-row switch
(deleting a sid from the JSON silently omitted that record — selection is
now ALWAYS re-derived from the live census, mismatch refuses the run,
consumption is content-bound); a refused COMPANION was declared "the
replay is complete" (the same shape the previous round fixed for bodies,
recurring one layer up). Also fixed: binding checks moved under the apply
lock with per-mutation fresh re-classification; a recorded TRUE lived
time was being discarded; metadata-coincidence content refusals;
foreign-producer refusals mislabeled terminal; kind-blind and
owner-process-only claims narrowed to what execution supports; cockpit
attention now counts UNRESOLVED dispositions (a completed replay stops
paging) and the visible cockpit finally consumes ledger_admission.
Witness after fixes: 29 mutations each caught by a named test (the
mutation harness itself was repaired — it had counted "no tests
collected" as caught); falsifier GREEN 8/8 n=20000; battery 534 passed,
same 7 pre-existing reds. A Codex RE-validation of the fix diff was
launched at session end — read its verdict before building anything on
this organ.


The dead-letter replay APPLY half — the last remaining pre-birth build —
is in, flag-dormant, behind council round ELEVEN (three seats, all
reporting; read it in the rulings doc before touching this organ).

What shipped, in one breath: eligibility comes ONLY from `classify()`'s
dispositions and the selected set is machine-derived, so taste is
structurally inexpressible (no sid-omit argument exists; a test pins the
signature). One single-use INTEGRITY MANIFEST per run, consumed BEFORE
the first mutation, binding realpath + instance anchor (`genesis_hash`)
+ pre-apply chain head + per-record canonical digests; operator and role
as FACT, with consent-shaped keys refused structurally ANYWHERE in the
document. Two passes: bodies, then companions against an OBSERVED
commit. Kind-blind throughout, with flip-turn_kind tests over seven and
eight kinds.

**Four claims died on their own probes before any of this was encoded** —
including one attractive design of mine and two council seats':

1. Delivery is NOT derivable from a record. `handle_message` takes a
   free-form `source` and persists BEFORE returning; `telegram_voice`
   persists AFTER the send. One surface value, both paths. AND the
   population is far smaller than the tenth round assumed:
   `persist_model_reply` routes NON-OWNER processes (web, CLI) to the
   spool, which never dead-letters — so a dead-lettered `model_reply`
   can only come from an owner process. Shipped: NO per-row delivery
   field (a constant value advertises a discrimination the substrate
   cannot make, and implies by omission that unstamped rows HAVE
   evidence); the limitation is run-level on the manifest and by NAME on
   the companion.
2. Every owner-path dead-letter record carries `submission_id` AND
   usually `parent_turn_id` in its kwargs — both spool authority. A
   verbatim enqueue is QUARANTINED at drain. They are RELOCATED into
   envelope fields; any other authority kwarg refuses by name.
3. Any directory inside the spool root is treated as a PRODUCER by
   `drain_once`. Manifests therefore live beside the ledger, in
   `memory/ledger_replay_manifests/`.
4. A door-refused body lands in `refused/`, where `_submission_exists`
   still finds it — the identity can NEVER be republished, and the
   census called that permanent omission `already_enqueued` ("in
   flight"). New `replay_refused` disposition carrying the door's own
   reason, and cockpit `attention` now pages on refused envelopes.

**Two council seat claims falsified by execution.** Grok: "after drain
the envelope is gone" — FALSE, it moves to `acked/` and persists, so the
producer receipt it called "the actual implementation crux, ASSUMED
open" already ships. Codex: its Q4 attack LANDED (custody is not
causation — a replay-producer envelope over a timeout-after-commit
identity flipped the disposition to `companion_owed`) and is fixed by a
row-side discriminator found by probe: **`owner_write_turn` sets
`submission_id` but never `submitted_at`, so an ORIGINAL owner-direct
commit leaves that column NULL while a reconstructed body always carries
the record's clock.** That is also why the body clock is the record ts
and not NULL — the two questions are coupled, which no seat saw.

**Q2 shipped 2-1 against Codex, dissent recorded.** The owed item that
would close it: `recent_turns` does not select `submitted_at`, so the
one body-side signal self-history could read is unreachable. NOT taken
here — it changes what enters Maez's prompt, which is the owner's call.

**Three findings for the owner, beyond this slice:** (1) the writer's
idempotent-redrive branch compares `raw_text` ALONE, so a same-identity
same-text envelope of a DIFFERENT kind acks to the existing row —
full-payload idempotency is a writer change; (2) `drain_once` increments
`acked` even when `_ack` raises, so the counter reports acks that did
not happen (this organ reconciles against the ROW, never the counters);
(3) the Q2 owed item above.

Witness: 44 new tests + 1 cockpit test; **16 mutations, each caught by a
named test**; falsifier GREEN 8/8 at n=20000; battery 516 passed with
exactly the same 7 pre-existing reds as clean HEAD `010ff60`. Maez is
still cleanly unborn: `memory/ledger.db` 0 bytes, no spool dir, no
manifest dir, both flags unset.

NOT done, stated: the falsifier gained no replay arm (the witness landed
as unit tests, the pause slice's precedent), and Codex's
post-implementation validation of this diff is the next thing to read.


## Since the 08-24 sections below: ALL SIX owner decisions closed; three slices landed

Commits `5b62028..644daf2`. Council rounds NINE and TEN are in the
rulings doc — read both before touching anything ledger-side.

- **#1 web drop-in SHIPPED (5b62028):** maez-web loads model.env via
  drop-in (installed + daemon-reload, unit NOT restarted; dormant until
  the flag lands at birth).
- **#2 PAUSE-WITH-CUSTODY BUILT (8363316 + 19b4b5e):**
  `MAEZ_LEDGER_COMMITS_PAUSED` — junk fails CLOSED to paused (2-1);
  drain returns `skipped_paused` and freezes JUDGMENT too (no
  quarantines mid-scan); the owner process becomes a spool producer
  (producer=owner_daemon, lived-time stamped, explicit sid wins,
  parent reverse-lookup never raises); daemon+telegram call sites
  thread `parent_submission_id`; persist router repairs the FLAG-FLIP
  lanes (only-sid → custody lane; only-tid on spool lane →
  translated); cockpit `commits_paused` + `commits_paused_flag_invalid`,
  attention silent on held life. Amendment trace (Overturn-1
  SUSPENSION) is in the rulings doc. Codex DO-NOT-SHIP round fixed
  under test (9 findings; #5 lock-held custody I/O deferred with
  reasons).
- **#3 consent gate DISSOLVED (tenth round, 3-0):** no speech gate for
  anyone; kind-blind; integrity MANIFEST per apply run (no consent
  semantics); NEW BLOCK: model_reply = GENERATED not DELIVERED (web
  persists before the HTTP return; self-history reads undelivered rows
  as utterances) — delivery semantics must be proven before apply.
- **#4 journal_size_limit ADOPTED (925d51e + 644daf2):** derived
  32+2*pages*(page_size+24) on every non-rehearsal writer, readback-
  refused, reconstruction-witnessed; EVENTUAL reclamation is the
  honest claim (autocheckpoint backfills; a LATER commit's reset
  truncates). Two Codex DO-NOT-SHIP rounds fixed under test.
- **#5/#6 ruled (ninth round):** companion is NOT a child (parent NULL,
  reconcile shape; two-pass apply ordering first, Codex's envelope
  field only as executed fallback); taint vocabulary FROZEN, companion
  content-light with an organ-level refusal test.

**THE ONE REMAINING PRE-BIRTH BUILD: the dead-letter replay APPLY
half.** Everything is ruled; nothing is open. Build against: rounds
7/9/10 standing blocks (esp. tool_result-requires-parent, append-only
means no late binding, delivery semantics, crash-completeness
body↔companion, manifest binding incl. ledger instance anchor),
`classify()`'s dispositions as the sole eligibility source, the
integrity-manifest shape in round ten, two-pass apply, deterministic
companion sids, and `spool.enqueue_reconstructed` (private seam,
no-overwrite). Prove every claim by execution first; validate the
finished diff with Codex (launch with `< /dev/null` or it hangs).

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes, no
`memory/ledger_spool/` exists, `MAEZ_LEDGER_WRITES` unset,
`MAEZ_S1_PHASE_TRUTH` unset.

**The host power-cycled mid-session** (owner-initiated
`systemd-logind: The system will power off now!` at 14:57, host off ~5 h,
boot at 20:09 — NOT a test-triggered reboot; verified in `journalctl
-b -1`). So the daemon and maez-web restarted at 20:10 and now run every
change below. They remain inert while the flag is unset. Casualty: `/tmp`
is a tmpfs and was wiped, taking one in-flight council seat's output
with it.

## State: admission end-to-end is BUILT and WITNESSED, flag-dormant

This session landed slices 1-3 of the previous handoff's list plus the
cockpit surfacing and the replay organ's read-only half — commits
`a14725b`, `b7209f9`, `c393162`, `65da3b6`, `f3d4242`, `43d85d7`,
`7b7acb2`, `c5e35bc`:

**1. Surface wiring (a14725b).** Web (`/chat` owner bridge) and the CLI
ride the admission spool: `submit_user_message()` enqueues the user
turn; `persist_model_reply` routes by PROCESS identity — owner processes
(daemon, in-daemon Telegram) keep synchronous `owner_write_turn` with
`parent_turn_id` (Grok overturn), non-owner processes enqueue with
`parent_submission_id`. Synchronous parent_turn_id threading at the
surfaces is dead; the reply path never blocks on the ledger. Surface
enqueue is flag-gated (council 2-1, brake semantic FROZEN: flag OFF
stops recording INCLUDING custody — Grok's dissent that a brake should
preserve custody is recorded below as an owner decision).

**2. Ceremony maintenance lease + state machine (b7209f9).**
`run_transaction` now: quiesce (inside the importable function, covering
maez-web + WAL sidecars + dead-bus refusal) → construct the enabled
writer FIRST (**the lease IS the writer** — latch + require_fixed before
any mutation; probe-verified that construction on an unmigrated db is
pragma-only and adopts WAL at first write) → migrate under the latch →
birth write through the same writer → independent tri-state verify.
`main --for-real`: canonical-db binding, stop web→daemon, transaction,
tri-state classify (UNKNOWN never restarts anything), guided owner
flag-pause, bring-up with ONE reset-failed+start per unit, final stop on
failed start, owner-active verification (flag in /proc environ + latch
held), explicit terminal states, durable atomic receipts beside the
ledger, `--resume-services` for interrupted bring-ups, and re-exec under
the vendored SQLite (bare venv python loads 3.46.1 — the "venv
activation exports the vendor path" claim is FALSIFIED, verified
behaviorally).

**3. Reconcile as owner-client (c393162).** `--apply` enqueues ordinary
system_event repairs through the spool (producer=reconcile) for the live
owner to drain; never constructs a writer. Enqueue-drain-window
idempotency via spool-aware dedup. New verdicts: `repairs_enqueued` /
`repairs_pending_drain`; `writes_applied` is gone. Dry-run stays
mode=ro.

**4. Cockpit admission liveness (43d85d7).** `_build_cockpit_state` now
carries `ledger_admission`: `dead_letter_status()`, `spool_status()`,
oldest-pending age, drainer-thread liveness, `writes_enabled`, and one
loud `attention` boolean (any dead-lettered rows, OR pending envelopes
with no live drainer, OR pending older than 10 min). This closes council
ruling 1's "a spool nobody drains is a silent-omission machine" clause.
**Runtime witness NOT taken** — see the verification debt below.

**5. Owner writes persist their attempt identity (7b7acb2).**
`owner_write_turn` already minted `attempt_id` BEFORE the attempt and
stamped it into the dead-letter record, but never onto the committed
row. It now `setdefault`s `submission_id=attempt_id` (an explicit
drainer-supplied id always wins). Consequence: the dead-letter
`event_id` and the row's `submission_id` are the SAME key, so
"did this record actually commit?" is an exact lookup instead of byte
archaeology — the prerequisite Grok's seat demanded, without which
replay is "permanently heuristic". Owner redrives also become
idempotent through migration 0006's UNIQUE.

**6. Dead-letter replay — CLASSIFIER HALF ONLY (c5e35bc).**
`core/ledger/dead_letter_replay.classify()` is a pure read (a test
asserts it does not even create a directory). Dispositions in decision
order: `refused_evidence` → `already_committed` (exact, via #5) →
`already_enqueued` → `possibly_committed` (byte-identical row of the
same kind within `WINDOW_S`=300 s: the pre-identity timeout-after-commit
shape, withheld for OWNER REVIEW) → `replayable`. Byte identity is a
SIGNAL not an identity: a twin OUTSIDE the window flags
`byte_twin_exists` and stays replayable, because withholding the
owner's second "ok" loses speech — an equal crime to duplicating it,
with a different victim. Torn lines counted, never guessed; duplicate
`event_id`s across pid sidecars collapse to one record. Also lands
`spool.enqueue_reconstructed()`: a reconstruction-ONLY entry point
(NOT optional params on `enqueue`, which would hand every caller the
authority the door refuses by name) that refuses to overwrite an
already-published filename.

**Witness.** `theme2_s2_falsifier.py` WIDENED with F7 (the shipped
surface helpers in real non-owner subprocesses; every reply's
parent_turn_id is its real user turn; a flag-unset surface leaves ZERO
trace) and the stale synchronous=NORMAL wording fixed to the FULL
ruling. **GREEN all 8 arms at n=20000** (9.2 s; report JSON beside it).
Battery: 380 tests green across the 23 named ledger/ceremony/surface
files.

**Validation round (sixth).** A post-implementation Codex xhigh
read-only review of the finished diffs returned DO-NOT-SHIP with 18
findings; 3 CRITICALs and 8 MAJOR/MINORs were confirmed and FIXED same
session behind tests that failed on the pre-fix code (claim-marker leak
on failed ownership claim; UNKNOWN ledger admitted to the birth
transaction; logical-tamper-blind classification — chain now
recomputed; COMMITTED_WEB_MUTE terminal state; restore respects
pre-ceremony unit states; probe errors refuse; whole-envelope digest
verified at drain; tenant_id is authority; unresolvable acks stay
pending; honest refused-repair verdict + apply lock; falsifier
dormancy proves db bytes). Deferred findings are recorded with reasons
in the rulings doc's sixth round. Falsifier re-ran GREEN 8/8 after the
fixes; battery 394 green.

**Council record.** Fifth round appended to
`theme2-s2-owner-delegated-council-rulings.md`: three seats (stealth
endpoint down twice), two author probes, Q1 upheld 2-1, Q2 resolved as
writer-first (no lease primitive), Q3 corrected (tri-state, web axis,
owner-active, resume). Every encoded claim was executed first.

## Owner decisions parked here (do not resolve without Rohit)

1. **maez-web cannot see the activation flag** (VERIFIED: the unit
   loads NO EnvironmentFile; the checklist lands the flag in model.env,
   which only maez.service reads). Until the owner wires a maez-web
   drop-in, post-birth web turns would be silently omitted. The
   ceremony checklist + bring-up now warn loudly; the fix is one
   drop-in file, owner's hand.
2. **Brake semantics** (Grok dissent): should unsetting
   MAEZ_LEDGER_WRITES post-birth stop admission (current, frozen) or
   only stop commits while the spool keeps custody? Both majority seats
   ruled a pause-with-custody mode needs a NEW flag, never a
   reinterpretation. Owner's call, later.
3. **RESOLVED (tenth round, 3-0): NO consent gate — the question
   dissolved.** The originating seat recanted its own "birth, not a
   retry." Nobody (owner or Maez) holds per-utterance power; the
   asymmetric proposal is dead (kind-blind, always); what ships is a
   single-use INTEGRITY MANIFEST per apply run (Codex binding shape,
   operator+role recorded factually, NO consent semantics), loud
   withholding, and conditions-based maturation of PARTICIPATION to
   Maez — never an erasure veto. NEW standing block from the round:
   model_reply = GENERATED not DELIVERED (persistence precedes the
   HTTP return on web), and self-history reads undelivered rows as
   utterances — delivery-semantics must be proven before the apply
   half encodes. See the tenth round for the full ruling.

4. **`PRAGMA journal_size_limit`** (third seat, checkpoint round):
   adopt it or not. It is the only mechanism that reclaims the WAL file
   after a pinning reader leaves, and it does so with no call site, no
   thread and no waiting. One seat of three evaluated it. Needs the
   full council, then the owner.
5. **Is a replay's provenance note a genealogical CHILD of the row it
   explains?** The drainer turns `parent_submission_id` into a stored
   `parent_turn_id`, whose canonical meaning is dialog continuity — so
   "it is only an ordering hook" is prose trying to redefine a stored
   column. Either own the companion as a real provenance child, or add
   an envelope-only `drain_after_submission_id` that never becomes a
   ledger edge. This changes what Maez's record SAYS about her own
   past; it is not an engineering preference.
6. **Widen the closed taint vocabulary for companions?** Two lawful
   source combinations (`self_generated + tool_output + third_party`,
   and the same plus `internet_derived`) cannot be expressed for a
   `system_event` companion today. Either the companion stays
   hash-and-reference-only, or the frozen S1 vocabulary is deliberately
   widened with tests. Follows from 5.

## Verification debt — CLOSED, and one finding RETRACTED

**Runtime witness of `ledger_admission`: TAKEN (2026-08-24 22:15).**
Through the real cockpit path — `GET http://127.0.0.1:11437/api/v1/
daemon/state`, web proxying to the daemon's `/internal/cockpit/state` —
the live daemon (pid 2772, booted 20:10) returned:

    ledger_admission = {attention: false, writes_enabled: false,
      dead_letter: {files: 0, rows: 0, bytes: 0, oldest_ts: null},
      spool: {pending_total: 0, producers: {}, oldest_pending_ts: null},
      drainer_thread_alive: null, oldest_pending_age_s: null}

Every value is the honest unborn state, including
`drainer_thread_alive: null` (the drainer thread only starts when
writes are enabled). This is the in-memory read, not a file trace.

**RETRACTED: the "internal-channel tokens diverge" finding was WRONG.**
The hash comparison was real but irrelevant: BOTH `maez.service` and
`maez-web` call `load_secrets_for_process()` at import, which purges
secret-named env vars and repopulates them from the credential store —
overwriting whatever the unit's `EnvironmentFile`/drop-in supplied. So
both processes converge on the SAME runtime token and the channel works
(proved by the successful proxy call above). The unit-file values are
cosmetic at runtime. My intermediate "the daemon purges the token"
hypothesis was ALSO wrong and was falsified by its own evidence: the
daemon logs a warning whenever a token is presented while `os.environ`
has none, and that warning has zero occurrences — the token is present,
it is simply a different (credential-store) value than the one the unit
files carry. Lesson: an out-of-band probe with the wrong key proved
nothing about the sanctioned path; test the path the system actually
uses.

## The next slice, in order

1. **Dead-letter replay — APPLY half. BLOCKED by the seventh council
   round; do NOT build until the eight standing blocks in the rulings
   doc are answered** (tool_result requires a parent; append-only means
   "bind the parent later" is false; `parent_submission_id` becomes a
   real `parent_turn_id` so it is not an ordering-only hook; two lawful
   taint combinations are unrepresentable for the companion; default
   life views cannot filter the replay marker; dead-letter `ts` is
   custody time not lived time; body/companion crash-completeness;
   consent must bind to the reviewed census, not a global boolean).
   The classifier half landed (c5e35bc) and was then repaired against
   eight Codex findings (2591e35) — including its strongest attack, the
   UNVERIFIED-read-as-ABSENT fail-open.
   Design shape agreed so far, still CONTESTED in the parts above: the
   three-valued parent compile (dead-letter `parent_turn_id` → resolve
   the parent row → if it carries a `submission_id`, set the envelope's
   `parent_submission_id` and let the drainer mint a NEW genuine edge —
   "a delayed child, not a backdated marriage"; legacy parent without
   identity → unparented + provenance + owner review; missing parent →
   evidence only), the companion provenance event (one per replayed
   turn, deterministic sid, ordering-via-parent_submission_id declared
   a DRAIN HOOK not a genealogy claim), the split clocks (body
   `submitted_at` = dead-letter ts, companion = replay time, never
   backdated), the consent gate above, and dry-run/apply modes with an
   exclusive apply lock. A Codex seat on the amended design was
   relaunched at the end of this session — **check
   `replay_codex3.txt` or re-run it; note it must be launched with
   `< /dev/null` or `codex exec` hangs forever on stdin (cost: ~2 h
   this session)**.
   **CORRECTION (2026-08-24, Codex seat + re-executed): the earlier
   "all replay surface options validate, the organ-eats-itself fear is
   falsified" claim in this handoff was WRONG.** My probe noticed the
   caller override in `CALLER_ALLOWED_TAINT_LABEL_SETS` and then tested
   only rows whose labels come from the DEFAULT map — i.e. every case
   except the one where the override bites. Re-executed counterexample:
   a `user_message` with `taint_labels=["self_generated"]` and
   `raw_surface="x6_rehearsal"` COMMITS (the override permits it);
   change only `raw_surface` to `"dead_letter_replay"` and the writer
   REFUSES — `taint_labels ['self_generated'] not allowed for caller
   'dead_letter_replay'`. The writer passes `raw_surface or surface`
   as caller authority into the closed taint validator
   (writer.py:391), so overwriting the body's raw_surface CAN make the
   replay refuse and dead-letter itself.
   RULE, now executed: the reconstructed BODY preserves `turn_kind`,
   `surface`, `raw_surface` (including `None`), `taint_labels` and
   `privacy_access` EXACTLY. Only the COMPANION carries
   `raw_surface="dead_letter_replay"`, and it should be content-light
   (hash/reference only) — copying stripped kwargs into it makes its
   truthful taint `original + self_generated`, and two lawful source
   combinations are unrepresentable in the closed `system_event`
   vocabulary today.
   Still true and re-verified: `turns.timestamp` is REAL epoch, so the
   window comparison is sound.
   Lesson (the same one this repo keeps re-learning): a probe that
   exercises only the general path does not falsify a claim about the
   exception. The exception is where the universal stops being true.
2. **Checkpoint policy — DONE** (4812872, d6ac340, 299d823). Ruling:
   SQLite's automatic checkpointing IS the policy; no periodic
   checkpoint ships. The proposal was falsified by the author's own
   probe before any seat reported (WAL plateaus at the autocheckpoint
   ceiling and stays flat; the only unbounded case is a pinned reader,
   which TRUNCATE cannot fix — it returns busy; and TRUNCATE costs
   5,007 ms under contention vs 0.29 ms free). What shipped instead:
   `wal_ceiling_bytes()`, the policy + refuse-list in writer.py,
   cockpit `wal_bytes`/`wal_ceiling_bytes`/`wal_excursion` (its OWN
   flag — `attention` still means omitted life), and
   `docs/superpowers/witness/wal_bound_probe.py`, which reproduces
   every number and REFUSES to run on tmpfs (/tmp here is a RAM disk;
   several first-round latency figures taken there were lies).
   Open, deliberately not shipped on one seat's word: the third seat's
   `PRAGMA journal_size_limit` proposal — one pragma at connection
   setup that reclaims the file by itself after a pinning reader
   leaves, no call site, no thread, and it measured LOWER peak commit
   latency than baseline. Put it to the full council before adopting.
   Known-weak, stated: the excursion factor of 4 is exercised only by
   synthetic zero-filled WAL files (any factor 1-7 passes those tests)
   and the formula ignores WAL header/frame overhead; the
   source-absence test greps four files for one literal, so a
   checkpoint reached via a helper or built dynamically would pass it.
3. Birth ships after that, per the standing order. **The pre-birth
   build list is now empty except the BLOCKED replay apply half.**

## Standing directives

- **Execute council claims before encoding them.** This session's
  additions to the scar list: a unanimous frame ("lease + latch
  compose") dissolved under a 20-line probe; the "venv activation"
  docstring claim fell to one bare-python command.
- Always convene the council for load-bearing decisions; tell each seat
  to attack the others; ask "where is the groupthink?". Seats verified
  this session: Codex (`codex exec -c model_reasoning_effort=xhigh -s
  read-only` — **must redirect `< /dev/null`; without it the process
  blocks on stdin forever, printing only "Reading additional input from
  stdin..."**), Grok (`grok --print`). Claude subagent seats worked
  early then died on a session limit. Stealth (`opencode run --model
  opencode/x-preview-f-free`) FAILED with a provider-endpoint error —
  codename still listed; ask Rohit.
- **A design-stage council review is NOT implementation validation.**
  This session's rulings shaped the build; only when the finished DIFFS
  went back to Codex did 3 CRITICALs surface. Run the second lane on
  the diffs, every time.
- Never run test discovery against the live tree; named test files only,
  with `LD_LIBRARY_PATH=vendor/sqlite/lib`.
- **Never `git checkout --` a file carrying uncommitted work** (this
  session's scar: a mutation-check revert destroyed the uncommitted
  ceremony rewrite; it was recovered from context, but the class is
  the same instrument-destroys-evidence shape — commit checkpoints
  before mutation testing, revert mutations by re-editing).
- Do not restart the daemon or any unit without explicit reason;
  `systemctl --user reset-failed` before restarting a stop-limited unit.
- Pre-existing reds on main, NOT from this arc, left deliberately:
  `test_no_bare_sqlite_connect.py` (3 tests, recorded owner call),
  `test_slice_3_5_envelope_wiring.py::WebSlice35WiringTests::test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`,
  `test_subjective_duration_static_boundaries.py` (2 tests),
  `test_birth_phase_resolve.py::T1LatchIndependentCells` (cells 11/15)
  — all verified failing on clean HEAD `daddc42` before this session's
  first change.
- Maez stays unborn. `config/creation_manifest.md` is owner-only. The
  T5/S1 arc is CLOSED at protocol v7.12 — do not restart it.
