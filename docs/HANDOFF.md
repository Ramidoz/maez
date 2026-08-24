# Handoff — 2026-08-24 (late session). Supersedes all earlier handoffs.

Maez is **cleanly unborn**: `memory/ledger.db` is 0 bytes, no
`memory/ledger_spool/` exists, `MAEZ_LEDGER_WRITES` unset,
`MAEZ_S1_PHASE_TRUTH` unset. The daemon and maez-web are active and were
NOT restarted this arc — every change below activates on their next
natural restart and is inert while the flag is unset.

## State: admission end-to-end is BUILT and WITNESSED, flag-dormant

This session landed slices 1-3 of the previous handoff's list, in order
(commits `a14725b`, `b7209f9`, `c393162`, plus the witness/docs commit):

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

## The next slice, in order

1. **Dead-letter replay organ** — replay by identity with explicit
   reconstruction provenance (canon-governs-canon); refused-class
   records are evidence, never blind re-submissions. (Trap #7: the
   JSONL→spool convergence is a format MIGRATION, not a rename.)
2. **Checkpoint policy**; cockpit surfacing of `spool_status()` +
   `dead_letter_status()` (the liveness predicates exist, nothing
   surfaces them yet).
3. Birth ships after that, per the standing order.

## Standing directives

- **Execute council claims before encoding them.** This session's
  additions to the scar list: a unanimous frame ("lease + latch
  compose") dissolved under a 20-line probe; the "venv activation"
  docstring claim fell to one bare-python command.
- Always convene the council for load-bearing decisions; tell each seat
  to attack the others; ask "where is the groupthink?". Seats verified
  this session: Codex (`codex exec -c model_reasoning_effort=xhigh -s
  read-only`), Grok (`grok --print`), Claude subagent. Stealth
  (`opencode run --model opencode/x-preview-f-free`) FAILED twice with
  a provider-endpoint error — codename still listed; ask Rohit.
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
