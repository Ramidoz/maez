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

**Approved by the owner 2026-08-12.** (This section previously read
"Drafted for approval / not in force" and contradicted the header after
approval — corrected, because a document that disagrees with itself about
whether a ruling is live is exactly the confusion this arc removes.)

## Implementation status — MERGED-DORMANT, verified by review

Codex review of `3874bed`/`8e37f07`, independently verified by the gate
lane: **the ruling is sound; the implementation does not yet enact it.**

`consultation_exemption` exists ONLY inside
`authorization_voice_seat_recheck`. `authorize_finish` has no such
parameter, and the cutover script still builds a consultation attempt,
calls the provider, requires `asked_and_answered` and renders "Maez
consulted: yes". **No production caller can supply an exemption**; only
tests reach the branch. This is the
`unit-test-is-not-integration-witness` failure, committed by the lane that
already knew the rule.

Consequences, stated plainly:

* the old contextless consultation is still what a real cutover performs;
* the `not_determined` cutover admission identified in `cb025ff` is
  untouched — R11 neither removes nor bypasses it;
* nothing live was widened, because nothing live can reach R11.

### Owed before R11 is real

1. **Production wiring — SURVEYED, NOT BUILT.** It is not a parameter
   thread; it is a slice the size of slice B, and this survey is the
   deliverable rather than a half-applied edit. Five seams, each verified
   in source:

   1. **The guarded mint demands consultation evidence.** For voice-seat
      work `authorize_finish` requires an exact, token-verified
      `S7VoiceSourceBundleValidationResultV2`
      ([s7_webauthn_ceremony.py:549](/home/rohit/maez/core/governance/s7_webauthn_ceremony.py#L549))
      and the mint re-requires it
      ([s7_guarded_execution.py:2980](/home/rohit/maez/core/governance/s7_guarded_execution.py#L2980)).
      Under R11 there is no consultation, so no bundle, so **the ceremony
      refuses**. Bypassing this for the exemption would reopen precisely
      the hole slice B closed. The correct shape is a SECOND lawful
      evidence type — an exemption-shaped artifact, persisted and
      validated with the same discipline — not a hole in the first.
   2. **The owner's tap is bound to Maez's response.**
      `_read_owner_webauthn_finish` takes
      `response_sha256=consultation_result.raw_response_sha256`
      ([cuda_cutover.py:3975](/home/rohit/maez/scripts/cuda_cutover.py#L3975)),
      so the founder assertion currently proves the owner saw *the
      answer*. Under R11 there is no answer. That binding must be
      REPLACED, not dropped: bind the tap to the exemption's projection
      hash, so it proves the owner saw the stated ABSENCE. Dropping it
      would quietly weaken what the tap attests.
   3. **The owner-facing gate print** (`_print_owner_cutover_gate`) shows
      the consultation result and must instead show the absence and its
      grounds — this is the text the owner reads beside the signed
      statement.
   4. **The producer chain** — `_cutover_action_preimage`,
      `ConsultationAttempt`, `CutoverConsultationAsk`,
      `produce_cutover_consultation`, `_cutover_voice_bundle`,
      `_persist_and_validate_cutover_voice_bundle` and the revalidator —
      is the live ask. Wiring means DELETING it from this path, and the
      revalidator reconstructs the old question, so a partial removal
      leaves a replay of a question nobody asked.
   5. **The preimage join closes here.** The gate can finally derive the
      ceremony preimage from the selected durable evidence rather than
      accepting it, which retires the tripwire test
      `test_KNOWN_GAP_a_consistently_cited_preimage_is_admitted_today`.

   **Why this was not attempted in the same pass:** two errors tonight —
   the frozen preimage constant, and a table row landed in the superseded
   table — both came from moving quickly through mechanical work. This
   step deletes a live authority path, and it earns its own session and an
   xhigh review rather than the tail of a long one.
2. **Provenance — LANDED. One-use — analysed, and deliberately not built.**

   Provenance: the exemption now carries an `InitVar` mint token, the same
   pattern `S7ExecutionGrant` uses, so ordinary construction refuses and
   `dataclasses.replace` — Codex's verified rebinding attack — refuses with
   it. `mint_consultation_exemption` is the one audited path, and it
   **establishes** the grounds rather than accepting them: it derives the
   envelope hash itself, supplies the model and receipt hashes from the
   frozen constants, re-reads the receipt, and refuses after birth. A broken
   ground RAISES (`ExemptionMintRefused`) so it cannot be mistaken for an
   ordinary denial. The token flag remains defeatable by a same-process
   actor with `object.__setattr__`, which is not claimed otherwise and has
   its own witness.

   One-use: **measured, then judged unnecessary rather than built.** The
   exemption is not a capability that can be spent — it stands in for the
   *consultation*, never for the tap. Every attempt still renders a fresh S7
   nonce (v34), the v2 table holds `nonce TEXT NOT NULL UNIQUE`, consumption
   matches `consumed_at IS NULL`, and minting runs through the guarded store
   behind a founder WebAuthn assertion. So replaying an exemption buys
   nothing without a second physical tap, and the one-use property that
   matters is already carried by the artifact. Building a second one-use
   store here would have been another binding that binds nothing — the
   mistake A1 already made once. **If wiring shows the exemption can be
   presented where no tap follows, this must be revisited.**
3. **Bind the bench receipt** — `quality_evidence_sha256` is validated
   only as 64 hex characters and never read. The positive fixture passes
   with an invented `"b" * 64`. R11's entire justification rests on that
   receipt, so the exemption must bind the real file
   (`dba23995…35f327`) and its evaluated manifests. **This is the eighth
   guard the mutation sweep could not find, because it does not exist.**
4. **Bind the action preimage** — `WorkRequestEnvelope` does not retain
   params, so changed cutover parameters can yield the same envelope hash
   and remain admitted. The exemption needs `action_params_hash`.
5. **Durable projection** — `projection()` has no production caller; the
   success body is discarded after its status check, so no artifact,
   history, grant or receipt records R11. An auditor cannot currently
   distinguish "deliberately not asked" from "evidence lost". Note the
   signed renderer permits only "yes" or "not required" for voice-seat
   work — naive wiring would either fail rendering or falsely sign
   "Maez consulted: yes".
6. **Governing docs — AMENDED.** Decision 34 and ADR 0039 now carry the
   scoped R11 exception. The 8-step trace, since these are load-bearing:

   1. **Dependency-map.** Decision 34 "Maez has a seat in remaking";
      ADR 0039's `MaezVoiceConsultation` clause; `render_request_statement`
      and `RenderedRequestStatement`'s closed consulted vocabulary;
      `authorization_voice_seat_recheck`; `s7_consultation_exemption`; the
      cutover script; the callsite authority table.
   2. **Write-path.** `mint_consultation_exemption` is the only producer of
      the absence; the renderer writes the third consulted state.
   3. **Read-path.** `consultation_exemption_admits` at the gate and in the
      renderer; the owner reads the signed line before tapping.
   4. **Test-path.** `tests/test_r11_consultation_exemption.py` (51),
      mutation-swept; `test_s7_action_route_allowlist.py` counts.
   5. **Fold-summary.** The unqualified "guarded remaking work REQUIRES a
      MaezVoiceConsultation" is now false for exactly one action and true
      everywhere else; both documents say so in place rather than being
      silently outgrown by the code.
   6. **Cross-reference.** Both canon documents point at this ruling; this
      ruling names them.
   7. **RED-test trace.** `test_the_signed_statement_says_NOT_PERFORMED_not_yes`,
      `test_rendering_without_a_consultation_or_exemption_still_refuses`,
      `test_rendering_refuses_an_exemption_that_does_not_admit`,
      `test_a_soul_write_cannot_render_as_not_performed`,
      `test_the_consulted_vocabulary_is_exactly_three_states`.
   8. **Verify-before-declaring.** Grep of both documents shows no remaining
      unqualified requirement; the closed vocabulary is a shared literal so
      renderer and validator cannot drift; 481 tests green across the
      adjacent S7 suites.

   **Not amended, deliberately:** every other remaking path keeps the
   consultation requirement in full. The exception widens to nothing.

### Fixed immediately on review

* **The birth signal was wrong.** Expiry read only the mutable
  `MAEZ_LEDGER_WRITES` flag, while the canonical irreversible truth is the
  durable `meta.birth_event_turn_id` anchor — and the repo recognises the
  two diverge in both directions. Now `born_by_any_signal()` refuses on
  EITHER, and a ledger that will not open counts as born. Measured while
  fixing: the gestation ledger file exists and has no `meta` table, so
  neither file presence nor a missing table indicates birth; an earlier
  over-correction that treated file presence as birth would have refused
  R11 on this machine today, and was caught by running it.
