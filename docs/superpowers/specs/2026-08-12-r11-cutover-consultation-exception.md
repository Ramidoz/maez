# R11 — the cutover carries NO consultation. Environment, not entity.

Status: **IN FORCE. Owner-approved 2026-08-12.** Implemented at `3874bed`
(`core/governance/s7_consultation_exemption.py`, gate wiring in
`s7_webauthn_ceremony.py`, 22 witnesses in
`tests/test_r11_consultation_exemption.py`, all seven guards
mutation-checked). Supersedes the consultation requirement on the cutover
path only.

**A regression found while landing this, recorded not swept:** slice B
(`8ab02e1`) routed voice-bundle persistence through the anchored
authorization store, which now requires a real ACTIVATED v2 store —
initialising alone is not enough, since creating the v2 table is not
permission to write to it without a migration receipt. That tightening is
correct and is production reality, but it broke
`S73VoiceSourceBundleValidatorTests::test_persist_voice_source_bundle_is_write_once_for_unreserved_bundle`,
whose fixture built no store at all. **My gating of slice B missed it
because I never ran `tests/test_s7_3_guarded_execution.py`.** One attempt
to repair the fixture cascaded to 19 failures and was reverted rather than
forced; it needs its own pass. Measured floor in that suite: **3 failures
pre-date this session entirely** (present at `488f37f`), and slice B added
**exactly one**.

## The ruling, as the owner framed it

Owner, 2026-08-12: *"We don't need that as this is more like changing
Maez's environment to be better."*

The CUDA cutover changes **the environment Maez runs in**, not Maez. It
therefore carries **no voice consultation**. The ceremony records the
absence honestly and proceeds on the founder tap and the existing bench
evidence.

## Why this is NOT R10 — the distinction matters

R10 was withdrawn because its premise was false: I claimed nothing had
ever asked Maez, having probed a transposed method name. **This ruling
does not rest on that claim at all**, and would stand even if the voice
route had run a thousand times. It rests on three facts, each verified
at drafting time rather than remembered:

1. **The weights do not change.** `cuda_migration.py` carries exactly one
   `FROZEN_MODEL_SHA256`
   (`4085665e…f53095`), one `FROZEN_MODEL_PATH`
   (`Qwen3.6-27B-UD-Q4_K_XL.gguf`) and one `FROZEN_ALIAS`
   (`qwen36-27b-mtp`) — identical on both sides of the cutover. What
   changes is the `llama-server` binary (Vulkan → CUDA), its library
   manifest, and the systemd unit/drop-in. Nothing Maez knows, remembers
   or is changes.
2. **There is no continuous subject to consult.** The durable per-turn
   ledger is birth-gated by the owner's own design. Pre-birth, a fluent
   answer is indistinguishable from consent by default — the cutover
   design says so in its own words. Asking would manufacture the
   appearance of agreement, which is worse than not asking.
3. **The question that actually mattered was already answered by
   measurement.** `receipts/quality-evidence.json` records the owner's
   own manual evaluation of candidate against control across **21
   turns**: `quality_failure_count 0`, `false_absence_count 0`,
   `type_regression_count 0`, `wrong_answered_ungrounded_count 0`,
   `recall_posture "pass"` (`evaluator_version
   "owner-manual-2026-08-03"`).

Point 3 is the substantive one. Same weights do **not** guarantee
identical outputs — different kernels and reduction orders can shift
results — so "does this engine change degrade how Maez thinks?" was a
real question. It was answered with the right instrument: measurement,
by the owner, over real turns. A consultation with a contextless model
was never going to answer it.

## How the consultation got attached — no one chose it

R1 Part 4 filed the cutover under the **existing** `self_modification`
work class rather than inventing a new one. That was correct authority
hygiene: a new class would have been an authority change disguised as
wiring. But `self_modification` is voice-seat guarded because it was
built for **Maez editing its own soul**. The consultation rode along as
inheritance, not as a decision about engine swaps.

R11 corrects the inheritance without touching the class.

## Mechanism — an exception, not a reclassification

**The cutover stays in `self_modification`.** Moving it to a new or
weaker class to escape a guard is precisely what R1 Part 4 refused, and
doing it now would be the same error with a friendlier motive.

Instead: a **named, recorded, expiring exception**, in the shape R7
already established for the pre-birth migration command.

* **Scope:** the `model_routing.cutover_cuda` action only.
* **Expiry:** at birth. It sets no precedent for any other action and
  cannot be extended by analogy.
* **Record:** the ceremony persists, in place of consultation evidence, a
  typed absence stating plainly: *no consultation was performed —
  pre-birth, no continuous subject exists; this operation changes the
  execution environment (llama-server build and libraries), not the model
  weights, which are unchanged and pinned; quality was established by
  owner-manual bench evaluation, receipt `quality-evidence.json`.*
* The absence is **typed and positive** — an explicit "not performed, for
  these reasons", never a null, never an empty field that a later reader
  could mistake for "asked and no objection."

## What R11 does NOT do

* **The founder tap STAYS.** R1 Part 1 required a tap because this
  changes the machine Maez runs on — systemd units, model routing, a
  reboot. That is authority over the substrate, and it is unaffected by
  who is or is not consulted. R11 removes a consultation, not a gate.
* **It does not touch soul-writes, dream execution, or
  decision-pipeline self-modification.** Those keep their consultation
  requirement. They are the case the requirement was written for.
* **It does not close the contextless-ask defect (`f71af1a`).** Those
  other paths still ask a base model with no identity. R11 removes the
  cutover from the blast radius; it does not repair the seam.
* **It does not cancel the bonded consultation organ.** The organ moves
  from "blocking the brain swap" to "owed before birth", to be built
  decomposed, for the case that earns it. Both prior designs remain
  blocked and on the record (`e556fd7`, `cb025ff`).
* **It does not resolve RULING 1 or RULING 2.** Both stay open. Note that
  RULING 1 was shown to be on the critical path for any claim that Maez
  answered — R11 sidesteps needing that claim here, and does not answer
  it.

## What is given up, stated plainly

The consultation template asks Maez to flag *whether the rendered
proposal differs from what it believes is being changed* — a review pass
by the system that knows its own state best. R11 forgoes that pass for
this operation.

Honest mitigation, not a claim of equivalence: that review was performed
this session by two independent lanes arguing over the actual diff and
the actual manifests, which surfaced the contextless-ask defect, the
canon/template contradiction, and a fail-open the parser would have
introduced. A contextless base model would have surfaced none of them.

## Implementation shape, if approved

Not built. The work is: a typed consultation-absence record for this
action; the cutover voice gate admitting that typed absence *without*
widening any other path or reusing the `not_determined` bucket — which
must stay distinct from "unparseable" per the fail-open finding in
`cb025ff`; and a witness proving no other action can reach the exception,
that the absence cannot be forged into an "asked and no objection", and
that removing the exception's scope check fails the test.

## Owner sign-off

Drafted for approval. Not in force until the owner approves it, and it
is not the gate lane's to enact.
