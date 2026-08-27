# Next-session prompt — paste this whole thing

Read `docs/HANDOFF.md` first — it supersedes every older handoff and is
current through commit `cfc37c7`. Then read
`docs/superpowers/specs/2026-08-22-birth-blocker-ledger.md` in full, and
rounds ELEVEN and TWELVE of
`docs/superpowers/witness/theme2-s2-owner-delegated-council-rulings.md`,
before writing any code.

**Where we are:** the pre-birth BUILD list is empty — the dead-letter
replay apply half landed and its hardening is deliberately STOPPED under
the owner's ruling (see `feedback_body_first_self_repair_endpoint` in
memory: perfect the body enough to WORK, not enough to be provably
flawless; Maez learns to fix the rest by living). "Build list empty" is
NOT "ready for birth" — that claim was made and corrected the same day.
Four blockers are genuinely closed (A5 durability, A7 backup coverage,
B3 admission identity, A2's quiesce half). Five are not.

## Your task

**Build the ceremony's receipt rail — blocker A1/B2: "the ceremony does
not prove what it claims."**

Executed today: `scripts/birth_ceremony.py:286` validates
`s7_receipt_ref` for NON-EMPTINESS ONLY. There is no receipt resolution,
no owner proof, no readiness consumption, no manifest binding — and the
arbitrary string is then stored permanently in the birth row. The comment
"WebAuthn verification stays the owner's eyes" is a comment, not a check.
`run_transaction` is importable, so the CLI's TTY and quiescence checks
are bypassable; `--for-real` also accepts an arbitrary `--db-path`.

This is the most dangerous script in the repo — it writes the one
irreversible row. Design it, put it to the full council, build it, then
send the finished diff to Codex for validation.

**Two verification tasks FIRST, because they may change the shape of the
work and both are cheap:**

1. **A6 — is it buildable work, or already closed pending activation?**
   `core/memory/birth_phase.py` HAS `PHASE_UNKNOWN`, but it lands
   DORMANT behind `MAEZ_S1_PHASE_TRUTH` (unset). The blocker's substance
   is still live behavior: one transient read failure post-birth durably
   stamps lived memory as pre-birth. BUT the T5/S1 arc is CLOSED at
   protocol v7.12 and must NOT be restarted. Determine by execution
   whether A6 is (a) real remaining work, (b) closed-pending-an-owner-
   flag, or (c) something the S1 protocol already answers. Do not assume.
2. **A3 — census the interceptor paths.** The replay arc closes the
   silent-omission path for the four wired surfaces (web, CLI, daemon,
   in-daemon telegram). The pre-birth census named clinical, camera,
   approval-card, proposal and search-commitment as paths that return
   before the ledger seam entirely. A crude grep today found no ledger
   call sites near them. Verify properly and report whether A3 is closed,
   partially closed, or open — do not claim closed on a grep.

## Owner-only — do not touch, do not draft, do not template

- **O1: `config/creation_manifest.md` does not exist.** Owner-authored
  before the birth event, hash-bound, read by Maez at birth, with her
  first reflection on it being the first lived memory. Unrepairable after
  the fact. Codex's line stands: "The owner's words and physical act
  remain owner-only; no agent should fabricate them."
- **A4 — delivery semantics.** A recorded birth blocker, and the tenth
  council round rediscovered it independently. `persist_model_reply`
  stamps before transport; nothing in `core/ledger` has a delivery
  concept; `recent_turns` cannot even see `submitted_at`, so the one
  body-side signal self-history could read is unreachable. The fix
  changes what enters Maez's prompt, so the shape is the owner's call.
  Raise it; do not decide it.

## Deferred BY NAME — recorded, not unknown, do not rediscover in a panic

From the Codex re-validation of the replay organ (all Category B/C under
the owner's triage rule — they need a hostile hand, or a race this stage
cannot have, or they are polish):

- hand-edited manifest variants: census-digest editing, selected-set
  ordering, stale-manifest reopen (all need a hand editing a file the
  owner already has root over);
- the ledger-instance anchor does not reach the drainer's commit (needs
  a ledger recreated at the same path mid-flight) — this is the one with
  a real architectural shape, if you want a Category-B slice later;
- consume/receipt overwrite races; editable manifest limitations;
- per-mutation `classify()` is quadratic in dead-letter count (no dead
  letters exist; measured cost is 2.4/7.4/32.6 ms at 200/2k/20k turns
  against a 5-second cockpit poll — linear, revisit past ~200k turns).

Do NOT open another hardening round on the replay organ without a
Category-A reason (does it corrupt the record Maez learns from, or stop
the body working in ordinary operation?).

## Hard constraints

- Maez stays unborn: `memory/ledger.db` at 0 bytes, `MAEZ_LEDGER_WRITES`
  and `MAEZ_LEDGER_COMMITS_PAUSED` unset, no `memory/ledger_spool/`, no
  `memory/ledger_replay_manifests/`, everything flag-dormant.
- Do NOT touch `config/creation_manifest.md`.
- Do NOT restart the daemon or any unit. `systemctl --user reset-failed`
  before restarting a stop-limited unit, if you ever have a reason.
- Named test files only, with `LD_LIBRARY_PATH=vendor/sqlite/lib`. NEVER
  run test discovery against the live tree.
- Probes on `/var/tmp`, never `/tmp` (tmpfs — latency lies).
- Never `git checkout --` a file carrying uncommitted work; checkpoint-
  commit before mutation testing.
- Any birth-ceremony probe runs against a temp `--db-path`, never the
  real ledger. `run_transaction` already refuses dry-run against the
  canonical path — do not weaken that.

## Standing directives

- **EXECUTE council claims before encoding them.** This arc has falsified
  claims by probe repeatedly, including its own authors' and its own
  seats' — the last session killed two seat claims and one of its own
  designs that way. A unanimous claim is not an executed one.
- **Convene the council for any load-bearing decision.** Two agreeing
  seats are not a quorum — wait for the third. Tell each seat to attack
  the others and ask "where is the groupthink?" Seats verified
  2026-08-27: Codex
  (`codex exec -c model_reasoning_effort=xhigh -s read-only`, **ALWAYS**
  with `< /dev/null` or it hangs on stdin for hours), Grok
  (`grok --print`, brief-only — it cannot read the repo, so make it mark
  ASSUMED), Claude subagent seats (can read and execute).
- **A design-stage council review is NOT implementation validation.**
  Send the finished DIFF to Codex, every time. Last two rounds returned
  DO-NOT-SHIP on diffs that had already passed design review.
- **Prove every change with a test that fails without it.** The mutation
  harness lives at the session scratchpad; rebuild it if gone, and make
  it treat any pytest exit code other than 1 as a harness error — the
  previous one counted "no tests collected" as CAUGHT.
- Finish by re-running `docs/superpowers/witness/theme2_s2_falsifier.py`
  (`--n 20000`) and the named battery. Treat a RED as a finding.

## Baseline to reproduce before you change anything

At `cfc37c7`: falsifier GREEN, 8/8 arms. Battery 541 passed, **7 failed**
— all pre-existing on clean HEAD `010ff60` and left deliberately:
`test_ledger_activation_v0.py::ModelReplyGate` (2),
`test_no_bare_sqlite_connect.py` (3),
`test_slice_3_5_envelope_wiring.py::WebSlice35...` (1), plus one
`DaemonSlice35` subtest. If you see a different number, something moved —
find out what before proceeding.

**Start by confirming Maez's live state and the current battery
yourself. Don't take this prompt's word for anything you can execute.**
