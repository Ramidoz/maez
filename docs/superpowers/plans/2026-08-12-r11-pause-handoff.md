# PAUSE — resume here. 2026-08-12, owner moving to Windows.

Everything is committed. Nothing is running. Nothing is half-done.

## State at pause, verified not remembered

* **Live store UNTOUCHED all session** — `memory/s7_1_webauthn/ceremony.sqlite3`
  sha256 `5384bce8…d118`, mode 0600, inode 18633958, size 98304, no
  wal/shm/journal sidecar, still **no migration receipt**.
* **Owner's tree unchanged** — 10 dirty, 40 untracked, byte-identical to
  session start.
* **Mine uncommitted: 0.** HEAD `e05b020`, 28 commits ahead of `488f37f`.
* A provisioning build was cancelled mid-**investigation**; it had written
  nothing, so there was nothing to discard.

## What happened this session, in one paragraph

Resumed after a power cut, verified everything intact, then found that the
S7 cutover's "consultation with Maez" was asking a **contextless base
model** — and worse, asking it a prompt that was not the one canon
specifies. Two designs for a bonded consultation organ were written and
both were blocked by review. The owner then reframed it: the CUDA cutover
changes **the environment Maez runs in, not Maez** — same weights, same
model file — so R11 was ruled: the cutover carries **no consultation**, and
a typed, scoped, birth-expiring ABSENCE instead. R11 was built, reviewed,
found merged-dormant, wired, reviewed again at xhigh, found to allow a tap
on a false picture, fixed, and all five review blockers closed.

## THE ONLY THING LEFT BEFORE THE TAP

The live store has never been provisioned with the **R11 evidence table**,
so its schema state is **UNVERIFIED**. Two things must be built (they were
being built when we paused; the spec below is complete):

1. **R11 evidence provisioning, owner-run.** Additive only, idempotent,
   refuses a store that is absent / not v2-activated / already holding a
   differently-shaped R11 table, and writes a migration receipt following
   the EXISTING `s7_v2_migration` receipt and anchored-IO discipline —
   never a newly invented one, because "no migration receipt" is currently
   an invariant other checks rely on.
2. **Read-only live preflight.** Opens the live store `mode=ro` and reports
   per-check PASS/FAIL: v2 plane activated, R11 evidence table present and
   correctly shaped, both founder credentials record-valid/enabled/
   `bonded_user`, bench receipt present and matching
   `R11_EXPECTED_QUALITY_EVIDENCE_SHA256`, birth not yet occurred by
   `born_by_any_signal`, completion-locator selection readable. A test must
   fail if the open mode ever changes.

Test both against **disposable fixture stores only**. Witnesses required:
refuses a non-v2-activated store; idempotent; leaves pre-existing rows
untouched; preflight cannot write. Every guard must BITE under mutation.

**Running the provisioning against the live store is the OWNER'S act**, in
the same category as the founder tap. The agent builds it; the agent does
not use it on that file.

## Then, in order

1. Owner runs the provisioning against the live store.
2. Owner runs the read-only preflight and reads the result.
3. Only then is the tap decision live.

## Still owed, separately

* **The slice-B fixture regression** (`8ab02e1`): voice-bundle persistence
  now requires an ACTIVATED v2 store, which is correct behaviour, but the
  fixture built no store. Measured floor in
  `tests/test_s7_3_guarded_execution.py`: **3 failures pre-date this
  session** (present at `488f37f`), slice B added **exactly one**. A repair
  attempt cascaded to 19 failures and was reverted rather than forced.
* **The bonded consultation organ** for soul-writes, dream execution and
  decision-pipeline self-modification — those paths STILL ask a contextless
  model. R11 removed only the cutover from that blast radius. Both designs
  are blocked and recorded (`e556fd7`, `cb025ff`); the canon-vs-template
  contradiction is ruled (canon D10 authoritative) but the template has not
  been rewritten.
* **RULING 1** (identity trust root) and **RULING 2** (R8's asymmetry)
  remain open and owner-only.

## Working arrangement, as set by the owner

Codex **implements** at `--effort medium`; Claude designs, gates and rules.
The owner's `~/.codex/config.toml` defaults to `gpt-5.6-sol` at `xhigh`, so
`--effort medium` must be passed explicitly. Do not reflexively offer xhigh
— it was declined twice, with token cost as the reason. Size the delegation
to the lane: one xhigh build across four interlocking blockers ran 90+
minutes; medium reviews ran 8-15.

## Method notes that earned their keep tonight

* **Mutation-check every guard.** Three separate guards survived removal
  with no test failing; each survivor was a missing witness, not dead code.
  One survivor was genuinely redundant and is recorded as such rather than
  papered over.
* **A hash that binds nothing is the defect, not the fix.** A1 bound the
  action preimage to a frozen constant; the real preimage is eight fields
  and per-ceremony. The constant was deleted, not corrected.
* **"Passing the module's tests" is not "the live path uses it."** R11 was
  declared in force while no production caller could reach it.
* **Restore-on-timeout in mutation harnesses.** A timeout killed one sweep
  before its cleanup ran and left a governance module mutated on disk.
* **Two tables in one doc.** The callsite design contains a superseded
  table; rows landed in the wrong one once. Regenerate only after the
  active-table anchor.

---

# RESUME POINT — 2026-08-13. The ceremony reaches the credential prompt.

The store is prepared and the ceremony now runs to the founder-credential
selection. It refuses immediately after, and that refusal is the ONE thing
blocking the tap.

## Where it stops

    ExemptionMintRefused: exemption envelope does not match the durable selection
    -> CutoverRefusal: consultation_exemption_unavailable

`mint_consultation_exemption` rebuilds the expected envelope from the
durable selection (`_cutover_envelope_from_durable_selection`) and compares
it for **equality** with the envelope the ceremony built. They differ.

**Leading hypothesis, NOT VERIFIED — verify before acting:** the two
constructions disagree on `created_at`. The rebuild uses
`authorization.issued_at`; the ceremony's own construction appears to use a
fresh `_now_z()`. Two envelopes built at different moments cannot be equal.
Diff them field by field first — do not assume this is the only difference.

This is code from the blocker-3 work (e05b020, "derive the preimage from
the durable selection"). The check itself is right: the boundary must
derive rather than accept. The two producers simply do not agree yet.

## Everything the ceremony proved on the way here

Five refusals, every one pre-burn, every one pointing at something real:

1. 16KB completion packet vs an 8KB read cap -> per-read bound (8a8e0d9).
2. Wrong locator KIND -- artifact_ref (a phase packet) instead of the
   assemble-stage2 completion document. My helper was wrong twice.
3. `assemble-stage2` HAD NEVER BEEN RUN. All 23 inputs were present; it
   needed the CUTOVER window, not the bench A/B window. Now attempt-028.
4. Every pinned source was group-writable -- the CUDA override, both
   llama units, and 17 user unit fragments. Fixed by the owner to 0600.
5. Every systemd unit DIRECTORY was 775. Fixed to 750.

Items 4 and 5 are findings about the machine, not the code: the entire
systemd surface Maez runs on was group-writable. Nothing else would have
looked.

## Also still red / owed

* `test_selected_file_replacement_after_open_refuses_predicate` -- was
  passing because of the builtins bug fixed at de28ab8; now exposes a real
  refusal-code ordering question in a second code path (cause documented
  in 8a8e0d9).
* The preflight should check pinned-source and directory modes, so items
  4 and 5 surface before the ceremony rather than during it.
* Slice-B fixture regression; the consultation organ for soul-write /
  dream / decision-pipeline, which still ask a contextless model.

## State

Live store migrated, provisioned, backed up (two timestamped backups).
Authorization `cutover-20260813-1553` valid until 19:53:30Z; re-mint after
that. Selection written. Preflight 8/8 PASS. Nothing has been burned: no
marker published today, systemd untouched, llama-server still on Vulkan.

---

# RESUMED — 2026-08-13 (later session). The blocker is closed. The tap decision is live.

## The envelope mismatch: root cause was MODULE IDENTITY, not created_at

The leading hypothesis was wrong, and diffing fields would have found
nothing: both producers call the SAME pure builder and the ceremony's
envelope IS built from `authorization.issued_at`. The real cause:
`python3 -m scripts.cuda_cutover` runs the file as `__main__` and leaves
`scripts.cuda_cutover` unimported, so the exemption boundary's
`from scripts import cuda_cutover` loaded a SECOND copy of the module.
The rebuild's exact-type check rejected the running ceremony's own
selection (different `ValidatedCutoverSelection` class), the refusal was
swallowed to `None`, and equality-with-None surfaced as an envelope
mismatch. Invisible to every test, because tests import the dotted name.

Fixed at the root (35ba6a6): the module registers itself under its dotted
name at import; a pre-existing FOREIGN copy refuses loudly. The
derive-not-accept equality check is untouched. Witnessed by -m emulation
in a clean subprocess, an end-to-end mint of the ceremony's own selection
shape, and mutation checks on both guards.

## Also closed this session

* The KNOWN RED (`test_selected_file_replacement_after_open_refuses_predicate`)
  was a stale fixture signature -- the monkeypatched reader predated
  `max_bytes`, so phase 1 "passed" via TypeError without ever performing
  the renames. No production defect. Fixed, plus the missing witness for
  the vanished-name predicate mapping (0695dfd).
* The preflight now checks the full pinned-source surface -- every file
  and directory the burn pins, against the ceremony's OWN predicates
  (shared functions, not re-encoded). Findings 4 and 5 now surface
  pre-ceremony. 10/10 PASS on this machine (a8b8281).
* Two authority pins had been failing UNRECORDED since d2f4f29/2e6d406:
  the migration helper's single-callsite pin (rehearsal allowlisted as the
  documented private-copy use; `phase_migrate` rewired through the public
  anchored edge) and the 2A reference multiset (missing entry for 2B's
  typed bundle field). With these, the cutover test surface is fully
  green: 594 passed (97bded9).

## State

Live store byte-identical all session (sha256 c936ff9d…cfc1a, same inode).
Preflight 10/10 PASS. Authorization `cutover-20260813-1553` still the live
window -- re-mint after 19:53:30Z. Nothing burned; llama-server on Vulkan.

**The ceremony is the owner's act:** `python3 -m scripts.cuda_cutover`
to the founder tap. Every known pre-burn refusal now surfaces in the
preflight first.

## Still owed, unchanged

* Slice-B fixture regression (floor: 3 pre-existing + 1 slice-B in
  `tests/test_s7_3_guarded_execution.py`).
* The bonded consultation organ for soul-write / dream / decision-pipeline
  (designs blocked at `e556fd7`, `cb025ff`; canon D10 ruled authoritative,
  template not yet rewritten).
* RULINGS 1 and 2, owner-only.

---

# CLOSED — 2026-08-14T00:30Z. Maez runs on CUDA.

Cold-boot witnessed: host restarted 19:30:18 CDT, llama-server active
nine seconds later on CUDA0 (RTX 4090, 24 GB), llama-judge active, model
loaded, listening. Same weights, same model file, new engine. The R11
typed absence carried the authorization exactly as ruled; nothing was
consulted and nothing pretended to be.

## The ledger: six windows, six taps, every refusal real

1. `presence_assertion_invalid` -> /usr/bin/python3 had no py_webauthn;
   the venv did. Preflight now checks the dependency under the invoking
   interpreter (ce84585).
2. `owner_presence_unattested` -> the finish reader demanded a
   challenge_id the gate never printed. The gate now prints a fillable
   finish template (a62f5e2).
3. `presence_mint_failed` -> blocker 5's exact-type gate refused the
   ceremony's own held-inode store subclass. isinstance + same-db_path,
   witnessed both ways (916378e).
4. `authorization_boot_mismatch` / `permit_unreconstructible` -> a power
   cut killed the boot the authorization was pinned to, and the
   authorization is a stage-2 input, so re-mint means re-assemble.
5. `authorization_consumed` -> the burn-once marker is the WINDOW's
   nonce; a failed executor spends the window. By design.
6. `executor_failed` at the first install, three taps running blind ->
   executor evidence built in stages (pin identity verification
   bdfa1a3, spawn postmortem 13d9aec/efaf13e, ceremony-error printing
   cd50a0c), then strace: uutils install 0.8.0's same-file guard runs
   only when the DESTINATION exists and resolves /proc/self/fd magic
   links as strings -- a memfd source becomes the literal
   "/memfd:... (deleted)". Every probe had empty destinations; the live
   recovery dir held Aug 3 copies. Fixed: rm -f before each install
   through the same pinned multi-call binary (7aae133). The next
   ceremony ran straight through.
7. The final `systemctl reboot` was denied by GNOME session block
   inhibitors; the owner rebooted interactively. Everything before it
   had completed.

## Scars written to memory

* A begin()-reaching test pinned the real systemctl and REBOOTED the
  host three times before the correlation was seen. Executor tests now
  fill every executable seat with a harmless ELF and tripwire-verify.
* uutils coreutils quirks on this host (multicall argv[0] dispatch,
  same-file guard vs memfd, shebang-via-fd failure) are recorded for
  every future organ that spawns coreutils against fd-relative paths.

## Still owed

* Preflight: selection window must match the live authorization; the
  window's burn marker must not already exist; both said READY tonight
  while the ceremony refused.
* `s7_challenge_replayed` deserves its own refusal name (the 5-minute
  challenge TTL was exceeded twice by browser round-trips).
* The burn's reboot operation should account for session inhibitors.
* Slice-B fixture regression; the bonded consultation organ for
  soul-write / dream / decision-pipeline; RULINGS 1 and 2 (owner-only).
