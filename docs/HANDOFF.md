# Handoff — 2026-08-24 (late session). Supersedes all earlier handoffs.

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
3. **Consent gate for replayed SPEECH.** Grok's replay seat: auto
   re-admitting a dead-lettered `model_reply` months later "is a birth,
   not a retry" — `MAEZ_LEDGER_WRITES` is a write lock, not consent.
   Proposal (unbuilt, awaiting the owner): replayed `model_reply` rows
   require an explicit second owner flag; replayed `user_message` rows
   do not (they are the owner's own words, already spoken).

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

1. **Dead-letter replay — APPLY half** (classifier landed in c5e35bc).
   Remaining and CONTESTED, do not build on one seat's word: the
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
2. **Checkpoint policy** — the last pre-birth item.
3. Birth ships after that, per the standing order.

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
