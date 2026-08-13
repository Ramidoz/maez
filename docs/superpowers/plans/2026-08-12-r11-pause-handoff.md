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
