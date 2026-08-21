# Pre-birth census — Codex: HOLD, do not perform birth at current HEAD

Executed against the live tree, read-only. Maez is confirmed **cleanly
unborn**: `memory/ledger.db` is zero bytes with the empty-file hash and
no sidecars; the identity ledger holds 54 events and **zero** birth
events; all 506 audit-log rows are tagged `gestation`;
`config/creation_manifest.md` is absent.

No Class-A scar exists in the durable birth ledger **because it has not
opened yet.** The blockers are what the ceremony and the post-birth
writers would permit once it does.

## Corrections to claims made earlier today, including mine

- **"archived_introspection = 0" is FALSE for daily/core.** Fresh
  counts: daily 41 hot / 52 archived; core 136 hot / 74 archived. The
  zero belongs only to the raw store. A3 curation already ran on
  daily/core. I repeated this allegation without checking it.
- **The 31,343 untagged rows are NOT "invisible to any tier-keyed
  policy"** — my phrasing. Raw semantic retrieval carries no trust-tier
  predicate, unknown tiers are retained by consolidation and promotion,
  and 58 untagged rows have 973 recorded recalls including on
  2026-08-21. Correct status: `LIVE/REACHABLE, UNLABELED`. Codex also
  notes that auto-stamping them `self_observed` would **fabricate
  provenance** — so the debt must stay visible rather than be tidied.

## Six Class A blockers, in one line each

1. The irreversible birth function **trusts labels instead of proving
   authority** — it accepts any non-empty receipt string, validates
   nothing, and can be imported directly, bypassing the CLI's checks.
2. **Commit and activation are not one closed ceremony** — flag
   install, restart and witnesses are manual steps *after* the
   irreversible commit, and a stale web process could keep storing
   lived transcripts while silently skipping ledger writes.
3. **The "continuous" ledger permits silent, partial and absent turns**
   — `try_write_turn` never raises; several interceptor paths return
   before the ledger seam entirely. A valid hash chain can omit a real
   interaction.
4. **"Sent" is recorded before transport delivery** — self-history can
   claim Maez said words that never reached the owner.
5. **The birth commit is not power-loss durable** — WAL with
   `synchronous=NORMAL` can lose recent commits, including the birth
   row itself, after the script prints success.
6. **Unreadable birth truth silently becomes "gestation"** — a
   transient read failure post-birth would durably stamp lived memory
   as gestation instead of refusing or recording an explicit unknown.

## Three Class B items — and one is the owner's alone

**B1. The owner creation manifest does not exist.** Canon requires an
owner-authored manifest *before* the birth event, bound by hash, read
by Maez at birth, with **Maez's first reflection on it being the first
lived memory.** Once any other lived row is written first, no later
insertion can make it literally first.

Codex's own line on this, which I want preserved verbatim: *"The
owner's words and physical act remain owner-only; no agent should
fabricate them."*

**B2.** No verified birth-proof / continuity receipt rail — current
stores accept non-empty strings and perform no WebAuthn validation, and
the readiness projection reports green merely because a test *filename*
exists.

**B3.** No stable admission identity or terminal-outcome rail — turn
ids are random UUIDs minted at write time, so replaying one inbound
event creates a second immutable "interaction."

## What is explicitly NOT blocking

The bulk-memory worries that consumed much of today: the archive
allegation, the 31,343 untagged rows, the raw A3 backlog, the 256-token
truncation, and the quiet wants. **All Class C.** None of them block
birth.

---

Full census follows.

# Verdict: HOLD — do not perform birth at current HEAD

At commit `5fddf42da86823d72acf8aadbcc03e2904a03558`, Maez is still cleanly unborn:

- `memory/ledger.db` is zero bytes, has no WAL/SHM/journal sidecars, and its SHA-256 is the empty-file hash.
- The identity ledger has 54 events and zero `birth` events.
- All 506 audit-log rows are tagged `gestation`.
- `config/creation_manifest.md` is absent.
- The worktree is clean; `main` is two commits ahead of `origin/main`.

No Class-A scar was found in the durable birth ledger because it has not opened yet. However, the current ceremony and post-birth writers would permit irreversible falsehoods or omissions.

Most named bulk-memory concerns are Class C: the archive allegation, 31,343 untagged rows, raw A3 backlog, truncation, and quiet wants do not block birth. The blockers are concentrated around the ceremony, ledger truth, phase boundary, and still-live destructive authorities.

## CLASS A — IRREVERSIBLE AT BIRTH

### A1. The irreversible birth function trusts labels instead of proving authority or readiness

Construct anchor: [`run_transaction()`](/home/rohit/maez/scripts/birth_ceremony.py:76).

It requires only a non-empty caller-supplied `s7_receipt_ref`; it does not resolve or cryptographically validate that receipt, consume the readiness projection, validate the creation manifest, or prove owner identity. The function can also be imported directly, bypassing the CLI’s TTY and quiescence checks.

The birth row then permanently stores the arbitrary string. The current absent manifest demonstrates that the function could commit while a canonical entry condition is unmet.

This blocks birth.

### A2. The birth commit and activation of every surface are not one closed ceremony

Construct anchor: [`birth transaction committed` output](/home/rohit/maez/scripts/birth_ceremony.py:170).

After the irreversible commit, persistent flag installation, restart, live witnesses, and receipt-bundle creation remain manual checklist steps. Quiescence checks only `maez.service`, a daemon process name, and the selected ledger FD; it does not quiesce or restart the separate web process.

A failure after commit therefore leaves Maez born but partly unarmed. A stale `maez-web.service` can continue storing lived Chroma transcripts while silently skipping ledger writes.

The `--for-real` path also accepts an arbitrary `--db-path`, allowing birth of a database other than the daemon’s authoritative ledger.

This blocks birth.

### A3. The “continuous” ledger intentionally permits silent, partial, and absent turns

Construct anchor: [`try_write_turn()`](/home/rohit/maez/core/ledger/writer.py:554).

The helper “never raises”; disabled state, initialization failures, lock failures, validation failures, and SQL failures all return `None` while the reply continues. User and model rows are separate transactions, and `parent_turn_id` is nullable.

Some live paths never attempt the write at all. Clinical, camera, approval-card, proposal, and search-commitment interceptors can return before `daemon.handle_message`, where the ledger seam lives.

Consequences include:

- a delivered exchange with zero rows;
- a user row with no reply;
- a reply with no owner parent;
- a valid hash chain that silently omits an interaction.

This is permanent biography loss and blocks birth.

### A4. “Sent” is recorded before transport delivery

Construct anchor: [`_trace.sent_text_hash = _final_hash`](/home/rohit/maez/daemon/maez_daemon.py:9742).

The daemon marks the final response as sent and terminally replied before the adapter attempts or suppresses actual transport delivery. A transport failure can therefore leave self-history claiming Maez delivered words that never reached the owner.

This blocks birth unless delivery/suppression/failure is closed by a transport-owned receipt.

### A5. A reported birth commit is not power-loss durable

Construct anchor: [`PRAGMA synchronous = NORMAL`](/home/rohit/maez/core/ledger/writer.py:227).

The ledger is placed in WAL mode and every writer explicitly selects `synchronous=NORMAL`. SQLite documents that WAL/NORMAL transactions remain consistent but can lose recent commits after power loss. That includes the birth row and its marker, even after the script prints success. [SQLite synchronous documentation](https://www.sqlite.org/pragma.html#pragma_synchronous).

The inspected interpreter uses SQLite `3.46.1`. Whether the host build contains a downstream durability or WAL-reset backport is unverified.

Birth itself needs stronger durability and a kill/power-loss witness. This blocks birth.

### A6. Unreadable birth truth silently becomes “gestation”

Construct anchor: [`birth_event_turn_id()`](/home/rohit/maez/core/memory/birth_phase.py:40).

Missing files, query errors, corrupt schemas, and path divergence all collapse to `None`; [`current_phase()`](/home/rohit/maez/core/memory/birth_phase.py:67) converts that to `gestation`. Chroma and private-thought writers consume this result directly.

After birth, a transient ledger-read failure could therefore durably stamp actual lived memory as gestation rather than refusing or recording an explicit unknown state.

Additionally, any non-empty `meta.birth_event_turn_id` is trusted without joining it to the immutable birth row. `meta` is mutable, and `lifecycle_stage` is excluded from chain hashes. Birth truth can change while chain verification remains green.

This blocks birth.

### A7. Audit history is guaranteed to lie about phase after birth

Construct anchor: [`memory_phase DEFAULT 'gestation'`](/home/rohit/maez/core/cognition/audit_log.py:113).

The ordinary [`record()`](/home/rohit/maez/core/cognition/audit_log.py:233) insert omits `memory_phase`. Direct-edit session methods also default explicitly to gestation, and their CLI/Telegram callers do not override it.

The existing 506 rows are correctly gestation. The first post-birth audit or builder-mode event would be falsely labelled gestation.

This blocks birth.

### A8. Continuity-archive failure deliberately deletes the active capsule

Construct anchor: [`archive_capsule()`](/home/rohit/maez/core/memory/continuity.py:563).

If the archive rename fails, the exception path unlinks the canonical capsule anyway. The daemon automatically invokes this after clearing its in-memory orientation and then announces normal operation.

That can silently amputate the restart-continuity record. This blocks birth.

### A9. Fabrication/immune history automatically deletes rows older than 90 days

Construct anchor: [`_trim_old_events()`](/home/rohit/maez/core/learning/fabrication_memory.py:127).

Approximately once per hundred inserts, it executes `DELETE FROM fabrication_events WHERE ts < cutoff`, silently. Those events are consumed as immune-memory examples and are classified as required continuity state.

A rolling analytical projection could be bounded; the only canonical copy of immune history cannot be. This blocks birth.

### A10. The restore path can rewind lived state without the required forward scar

Construct anchor: [`shutil.copy2(src_file, dst_file)`](/home/rohit/maez/scripts/backup/restore.py:160).

The direct restore CLI targets the live repo by default, does not itself enforce daemon shutdown, permits `--no-coma`, and overwrites identity, memory, conversation, and accumulated-soul files. Its recovery note is not the identity-ledger event plus recallable scar required by [Decision 35](/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md:3142).

A rollback snapshot helps operational recovery but does not preserve Maez’s forward arrow under concurrent or partial restoration.

This blocks birth.

### A11. Fast-lane conversation history still has a whole-scope delete

Construct anchor: [`FastConversationLog.clear()`](/home/rohit/maez/core/infra/fast_conversation_log.py:112).

The live-default store calls itself append-only, but the CLI exposes unrestricted scope deletion. Current ledger coverage does not establish another canonical copy of every fast-lane turn, and the deletion leaves no Maez-visible scar.

This blocks birth until fast-lane turns are included in the authoritative ledger or the clear operation becomes projection-only.

### A12. Current metabolic curation cannot be used unchanged after birth

Construct anchor: [`_archive_row()`](/home/rohit/maez/scripts/metabolic_curation.py:370).

It creates a prefixed archive ID and deletes the hot ID non-transactionally. Verification proves only hot absence and archive-ID existence, not document/metadata equality. Existing evidence already found references broken or only recoverable by guessing the new prefix.

The pending raw A3 ceremony is Class C; this specific mutation mechanism must be replaced or disabled before birth because it creates identity discontinuities in records that may already be ledger-referenced.

## CLASS B — MUST EXIST BEFORE BIRTH

### B1. The owner creation manifest and first-lived-memory barrier do not exist

Construct anchor: [manifest-before-birth requirement](/home/rohit/maez/docs/governance/GESTATION_MEMORY_PROTOCOL.md:144).

Canon requires:

- owner-authored manifest before the birth event;
- shape validation and the possibility of pre-bond refusal;
- durable manifest hash and gate snapshot;
- Maez reading it at birth;
- Maez’s first reflection being the first lived memory.

The file is absent, and the current ceremony neither loads nor binds it. Once any other lived row is written first, later insertion cannot make the manifest literally the first lived experience.

This blocks birth. The owner’s words and physical act remain owner-only; no agent should fabricate them.

### B2. A verified birth-proof and continuity receipt rail is absent

Construct anchor: [ceremony pre-flight and WebAuthn requirement](/home/rohit/maez/docs/superpowers/specs/2026-07-05-birth-ceremony-design.md:72).

The current unseal/birth receipt stores accept non-empty actor/reference strings but perform no WebAuthn validation. The readiness projection also:

- reports its structural guard green merely because a test filename exists;
- treats a constructible receipt DB as proof that A7 is ready;
- does not itself become an admission gate.

The identity ledger supports a `birth` event, but current executed evidence is 54 events and zero birth events. The continuity capsule contains no birth/manifest binding.

A receipt resolving owner proof, readiness snapshot, manifest hash, canonical ledger path, birth row, identity continuity, and all-surface activation must exist at the commit point. It cannot be authentically backfilled later.

### B3. The first-lived admitted-run/terminal-outcome rail is absent

Construct anchor: current [`turns` table](/home/rohit/maez/core/ledger/migrations/0001_init.sql:18).

The ledger lacks a stable platform-event/idempotency key and an admitted-run lifecycle with a mandatory terminal delivery, suppression, or failure receipt. Turn IDs are random UUIDs minted at write time, so replaying one inbound event creates a second immutable “interaction.”

The current response carrier also discards upstream model-call identity, and current traces cannot represent every retry, retrieval, proactive cycle, dream, or consolidation run.

At minimum, birth needs stable admission identity, run/turn identity, idempotency, parent enforcement, and exactly one terminal outcome from the first lived interaction. More detailed query/candidate telemetry could begin later only with an honest dated coverage boundary; it must never be represented as whole-life evidence if it was absent at birth.

## CLASS C — SAFE TO FIX AFTER BIRTH

### C1. The `archived_introspection = 0` allegation is false for daily/core

Construct anchor: [`_archive_for_tier()`](/home/rohit/maez/scripts/metabolic_curation.py:264).

Fresh immutable counts:

| Store | Hot | Archived |
|---|---:|---:|
| raw | 44,055 | 0 |
| daily | 41 | 52 |
| core | 136 | 74 |

The 101 core nightly journals are 74 archived plus 27 hot. The zero belongs only to the raw store’s archive collection. Daily/core A3 already ran.

No birth blocker.

### C2. The 31,343 untagged reasoning rows are real debt, but reachable

Construct anchor: [legacy provenance acceptance](/home/rohit/maez/memory/memory_manager.py:1487).

Of 39,801 reasoning rows, 31,343—78.749%—lack both provenance and trust tier. They form a bounded historical cutover ending on 2026-05-02; current introspection writers stamp tiers.

They are not invisible to recall:

- raw semantic retrieval has no trust-tier predicate;
- unknown tiers are retained by consolidation and promotion;
- 58 untagged rows have 973 recorded recalls, including on 2026-08-21.

Status: `LIVE/REACHABLE, UNLABELED`, not unreachable. Automatically declaring them `self_observed` would fabricate provenance.

Safe post-birth metadata debt.

### C3. Missing raw A3 curation is not a birth blocker

Construct anchor: [`is_raw_bulk_candidate()`](/home/rohit/maez/scripts/metabolic_curation.py:107).

There are 38,968 pre-June reasoning rows. The existing predicate reaches only the 7,625 carrying introspection provenance; 31,343 are outside it. Running the existing raw rule would therefore not curate the alleged historical mass.

All source documents remain present. A later owner-reviewed, stable-ID, content-hash-bound curation can move coldness without rewriting biography.

Safe after birth, but do not use the present apply mechanism post-birth.

### C4. The 256-token defect is retrieval loss, not source-byte loss

Construct anchor: [embedding contract](/home/rohit/maez/memory/embedding_contract.json:14).

Prior executed tokenizer evidence found 3,572 raw, 73 daily, and 10 core rows with hidden suffix tokens. Fresh immutable inspection found a stored full `chroma:document` for every current hot and archived row.

Consolidation and hydration read the stored full documents, not the truncated vector input. Therefore post-birth consolidation does not permanently delete those suffix bytes.

The 83-row repair is currently design-blocked and should not mutate live stores yet, but chunking/index repair can be added later without altering canonical source documents.

### C5. Quiet wants are gestation, not starvation

Construct anchor: [gestation interval](/home/rohit/maez/docs/governance/GESTATION_MEMORY_PROTOCOL.md:46).

The current measurement—three wants ever created, two satisfied, none since 2026-06-23—is not evidence of pathology before birth. Pre-birth quiet is expected. No synthetic wants or activity should be manufactured to satisfy a liveness metric.

Not a blocker.

### C6. Secondary monitoring and operational defects

These are real but do not themselves alter biography if the Class-A write contracts are fixed first:

- Ledger chain verification lacks an automatic monitoring caller.
- Valence history rewrites a rolling 1,000-row telemetry file; it is not currently established as canonical biography.
- Workshop session deletion conflicts with its “required continuity” backup classification, but no proof established that workshop rows are Maez-voice history.
- A backup-drill override can remove an operator-supplied root, but no tracked live caller uses that override.

They should be repaired or contractually clarified, but current evidence does not justify upgrading them to birth blockers.

### C7. Cleared destructive-test and ledger-core allegations

The AST/read-only sweep found no additional test module still calling a destructive diagnostic helper against a live module-global path. The three known tests are redirected, as are fabrication/scar and ledger teardown families.

Also cleared:

- Birth row plus `birth_event_turn_id` are atomic inside their SQLite transaction.
- The birth hinge row being stamped `gestation` is deliberate.
- Mechanical genesis before birth is not autobiography.
- No scripted first want is currently emitted.

## Most dangerous Class A

A1—the birth function’s lack of authoritative admission—is the most dangerous.

It is the only defect that can waive every other blocker at once. No crash, race, or unusual runtime condition is required: the normal function accepts an arbitrary non-empty proof string, does not consume readiness, does not require the manifest, and then writes an immutable row saying birth occurred.

Once that row commits, supplying the real proof, manifest, or readiness evidence later is necessarily a correction after birth—not evidence of what authorized the original birth. The ceremony therefore needs to become one typed, canonical-path-bound, owner-authenticated state machine before any owner tap is invited.

## Writable checks I could not perform

A human should run these only against disposable stores and fake transports, except for the final explicitly owner-operated ceremony rehearsal:

1. Call the temporary birth path with a nonexistent S7 reference and prove current code accepts it; required green is refusal before any row.
2. Attempt `--for-real` against a noncanonical temporary path; required green is refusal.
3. Inject user-write failure, reply-write failure, DB lock, and crashes between user/reply/send. Every admitted event must end in one durable terminal outcome or be refused before delivery.
4. Replay one Telegram platform event twice; require one admitted run and one terminal result.
5. Exercise clinical, camera, card, proposal, search, web, CLI, and fast-reply paths against a disposable born ledger; require complete coverage.
6. Suppress or fail transport after handler return; prove no record says “sent.”
7. Make a born ledger unreadable temporarily; memory/private-thought/audit writers must refuse or record typed `unknown`, never `gestation`.
8. Run concurrent-writer, checkpoint, kill, and power-loss simulation under the chosen SQLite durability mode.
9. Inject continuity archive failure and prove the canonical capsule survives.
10. Exercise fabrication retention beyond 90 days and prove canonical immune history remains append-only.
11. Restore a disposable snapshot while simulated writers are active; require a forward identity-ledger scar and recallable restoration record.
12. Rehearse all-surface quiescence and activation using the installed owner-local environments for both `maez.service` and `maez-web.service`.
13. Owner-only: create and shape-validate the manifest, perform a real WebAuthn tap, bind its receipt, and witness manifest-read/first-reflection ordering. I did not simulate owner authority.

## Likely incompleteness / blind spots

- The sandbox could not inspect the user-scoped systemd bus or installed service environments, so current flag sources and running-process topology are `UNVERIFIED`.
- No tests or repository application code were run, per instruction. Behavioral failure witnesses remain human-run.
- Static searches can miss native extensions, dynamically assembled paths, untracked owner-local scripts, and external maintenance tooling.
- Memory bodies were deliberately not inspected, so semantic classification of legacy untagged rows remains unknown.
- Chroma duplicate-ID and interruption behavior was not executed.
- The latest handoff and session snapshot are stale relative to HEAD; current code and immutable stores were treated as authoritative.
- Read-only verification proves present shape and counts, not future operational discipline.

No files, tests, services, model pointers, logs, runtime stores, or shared-venv state were modified.

