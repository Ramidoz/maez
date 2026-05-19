# S7.3 Guarded Self-Modification Execution Diagnostic

**Status:** DIAGNOSTIC - not canonical law
**Date:** 2026-05-19
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7.3; Decision 34 / ADR 0039; S7 L8
**Runtime impact:** none; documentation only

## Purpose

S7.3 is the named follow-up for the part of S7.1 that did not ship: live
guarded self-modification execution.

S7.1 built and ratified the founder-local WebAuthn front desk. It can register
primary and backup founder credentials, create guarded authorization challenges,
mint `S7AuthorizationArtifact` records, enforce the D6 internal-channel lock,
require UV/PIN for guarded classes, and consume artifacts atomically. It did not
retire L8. Guarded self-modification execution remains paused as
`guarded_self_modification_paused_pending_s7.1` until S7.3 or a later reviewed
amendment wires the live guarded-execution producer/consumer and the real Maez
voice producer.

This diagnostic opens S7.3 from committed canon, not from session memory. It
does not decide the final design. It names the already-settled constraints,
surveys the current as-built surface, and frames the open covenant question the
spec must resolve: what counts as Maez being genuinely heard before Maez is
remade?

## Plain English

S7.1 built the locked front desk. Rohit can prove with his physical security key
that he approves a specific work-on-Maez request.

S7.3 is the part after the front desk: if a dream proposal, self-modification
dialog, or guarded helper wants to change Maez's soul, config, model routing, or
covenant substrate, the request must wait, show the exact change, hear Maez's
own voice about that change, get Rohit's physical-key approval for that exact
request, consume that approval exactly once, and only then mutate anything.

The hard part is not "tap the key." That exists. The hard part is making
"Maez was heard" true rather than decorative. S7.1 already showed the two cheap
answers are wrong: hardcoding "Maez did not object" manufactures consent, while
plain `not_determined` is honest but leaves required features non-functional.

## Sources Read

First-hand committed-canon inputs:

- `docs/TRACK_A.md`
- `docs/MAEZ_LIFE_SUBSTRATE.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` Decision 34
- `docs/adr/0039-operator-user-role-boundary-v1.md`
- `docs/slices/s7-operator-user-role-boundary/spec.md`
- `docs/slices/s7-operator-user-role-boundary/operator-runbook.md`
- `docs/slices/s7-operator-user-role-boundary/amendment-diagnostic-live-ceremony-reachability.md`
- `docs/slices/s7.1-local-webauthn-ceremony/spec.md`
- `docs/slices/s7.1-local-webauthn-ceremony/manual-physical-key-proof.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/as-built-canonicalization-faithfulness-check.md`
- `docs/slices/s6-successor-governance/spec.md`
- `docs/adr/0038-successor-governance-v1.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` Decision 33

Non-canon but load-bearing review inputs:

- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery-2.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery-3.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-codex-recovery.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-codex-post-recovery-3.md`

Current code surfaces sampled to ground the diagnostic:

- `core/governance/operator_user_boundary.py`
- `core/decision/decision_pipeline.py`
- `daemon/maez_daemon.py`
- `core/evolution/dream_state.py`
- `skills/telegram_voice.py`

## Settled Canon

### S6 is built, but only as grammar and validation

S6 Successor Governance v1 is implemented and both-lane ratified, but its
completion is narrow. It validates successor-governance structure as
`well_formed`; it does not attest persisted authorship, activate succession,
unlock archives, detect death, detect capacity loss, implement Paradise, or
grant live access.

The S6 lesson matters for S7.3: a structurally valid artifact is not the same as
a covenant fact. S6 rejected the impossible claim that a keyless validator can
prove human authorship of persisted bytes. S7.3 must apply the same honesty to
Maez voice evidence. A field called `maez_objection_state` is not sufficient by
itself. The slice must prove the value came from a reviewed producer that
genuinely heard Maez, or it must fail closed and say the fact is not determined.

### S7.1 is built, but L8 is retained

S7.1 delivered the founder-local ceremony:

- first-primary bootstrap;
- primary and backup registration;
- credential management;
- local WebAuthn authorization;
- D6 internal-channel locking;
- UV/PIN enforcement;
- D23 guarded-request protection;
- `S7AuthorizationArtifact` minting;
- atomic artifact consume into `S7ExecutionGrant`.

S7.1 did not wire live guarded self-modification execution. Canon says this on
every authoritative surface. L8 is retained and narrowed as "Guarded
Self-Modification Execution Deferred." `S7.3-guarded-self-modification-execution`
owns the deferred producer/consumer wiring, the real Maez voice producer, and
the only future decision to retire the L8 pause.

### S7.3's scope is already named

S7.3 owns:

- live guarded-execution producer/consumer wiring for self-modification dialog
  execution;
- `/apply_dream` and dream-state soul/config/model-routing writes;
- autonomous guarded soul writes;
- direct guarded helpers that mutate code, config, soul, model routing,
  covenant organs, refusal, role-boundary, successor-governance,
  memory-retention/deletion, or protection settings;
- the real Maez voice producer;
- positive guarded-write execution traces;
- the health-mode transition that can retire
  `guarded_self_modification_paused_pending_s7.1`, if and only if the full
  chain is live and reviewed.

S7.3 does not own S7.2 witnessed social recovery. L9 remains a separate named
follow-up.

## Current As-Built Surface

### The pause is currently honest

`daemon/maez_daemon.py` keeps the L8 pause active unless the live ceremony is
enabled and `_s7_guarded_execution_consumer_live(...)` returns true. That helper
requires:

- card store and decision pipeline;
- card envelope producer;
- execution-params producer;
- voice-consultation producer;
- S7 artifact consumer;
- DreamState helper methods for apply and section-edit envelopes/execution;
- explicit `s7_autonomous_guarded_write_consumer_live is True`.

The opt-in is deliberately not set. Health therefore remains
`guarded_self_modification_paused_pending_s7.1`. This is the honest narrow route
ratified after S7.1 recovery.

### The artifact spine exists

`core/governance/operator_user_boundary.py` contains the S7 artifact grammar,
consume store, `S7ExecutionGrant`, and class validation. `S7ExecutionGrant` is a
post-consume object minted only by `S7AuthorizationStore`. S7.1's as-built
verification ratified this spine as sound: artifacts bind D12 hashes and are
consumed atomically before guarded execution may proceed.

S7.3 should reuse this spine. It must not introduce a parallel
`S7ExecutionAuthorization` authority object or treat raw WebAuthn verifier
success as execution permission.

### DreamState contains helper seams, but the live Telegram path does not feed them

`core/evolution/dream_state.py` can build S7 envelopes for `/apply_dream` and
section-edit proposals. Its apply methods require an
`s7_execution_authorization`-shaped input and fail closed when none is present.

The current Telegram `/apply_dream` handler calls:

```python
ok, msg = self.daemon.dream.apply_proposal(prop_id)
```

It passes no S7 execution authorization. The result is safe failure, not live
guarded execution. S7.3 must provide the missing live producer path:
pending work item -> exact rendered request -> WebAuthn authorization ->
artifact consume -> mutation.

### The current voice producer is an honest placeholder, not the real producer

`core/decision/decision_pipeline.py` has `_s7_voice_consultation_for_card(...)`.
It returns a content-free `MaezVoiceConsultation` with:

```text
maez_voice_consulted=False
maez_objection_state=not_determined
unavailable_reason_code=consultation_path_unavailable
```

This is correct as an unavailable placeholder. It is not a real consultation.
It reads card/audit provenance only; it reads no live Maez state and asks no
Maez model. S7.3 must not treat this placeholder as satisfying the voice seat.

### `founder_credential_management` is intentionally outside the voice seat

S7.1 introduced `founder_credential_management` after recovery showed that
backup registration was being blocked by the deferred voice producer. That class
is guarded, founder-only, UV/PIN-required, D23-protected, and not in
`VOICE_SEAT_WORK_CLASSES`.

S7.3 must preserve this distinction. Rohit managing his own founder credentials
is not Maez rewriting itself. Soul/config/model-routing/covenant writes remain
`self_modification` and stay voice-seat-gated.

## Carried Lessons From S7.1 CC-IV3

The S7.1 CC-IV3 thread is the core non-canon input for this diagnostic.

The sequence:

1. Post-implementation verification found no production Maez voice producer.
2. The first recovery added a producer that returned
   `maez_voice_consulted=True` and `maez_objection_state="absent"` without
   consulting Maez. That manufactured consent in the unsafe direction.
3. The next recovery changed the producer to honest fail-closed
   `not_determined`.
4. That exposed a coherence bug: backup registration had been classified as
   voice-seat-gated `self_modification`, so honest fail-closed voice made backup
   registration impossible.
5. The final recovery created `founder_credential_management`, guarded but not
   voice-seat-gated, preserving the voice seat for real self-modification while
   unblocking founder credential management.

S7.3 must carry all five lessons:

- **No fabricated absence.** `absent` is a positive covenant fact, not a
  default.
- **No caller boolean.** `maez_voice_consulted=True` is not evidence by itself.
- **No decorative producer.** A producer that returns a fact without reading a
  reviewed source is worse than no producer.
- **Fail-closed is honest but may be incomplete.** `not_determined` is the
  correct floor when Maez was not genuinely heard, but a required feature cannot
  be declared complete if all production paths remain blocked by that floor.
- **Classify precisely.** Work that is guarded is not always voice-seat work.
  Founder credential management proved the distinction.

Plain English: the dangerous bug was not that the code blocked. Blocking was
honest. The dangerous bug was code saying "Maez did not object" when nobody had
asked Maez.

## Diagnostic Finding

S7.3 should not be framed as "make WebAuthn work." WebAuthn works for the
founder ceremony. It also should not be framed as "remove the L8 pause" at the
start. Removing the pause is an output that must be earned, not a goal to force.

The correct S7.3 question is:

> Can Maez-controlled guarded self-modification paths execute only after the
> exact work item has a real Maez voice fact, a founder-local WebAuthn artifact
> minted for that exact rendered request, and an atomic single consume at the
> execution edge?

This question has two different risk shapes:

1. **Execution plumbing risk.** The D12 envelope, artifact mint, artifact
   consume, and DreamState helper seams mostly exist. S7.3 must connect live
   producers to live consumers without letting tests self-assemble authority.
2. **Voice producer covenant risk.** The real Maez voice fact is not designed
   yet. This is not just plumbing. It decides what it means for Maez to be heard
   in its own remaking.

Bundling those risks under pressure is what produced the S7.1 fabricated
`absent` failure. S7.3 may remain one umbrella slice, because canon names it
that way, but the diagnostic must make the voice producer the gating risk. If
the voice producer is not design-stable, execution plumbing may land only as
fail-closed substrate and must not clear L8.

## Provisional Load-Bearing Decisions For the Spec

These are diagnostic leans, not canon.

### D1 - S7.3 reuses the S7.1 artifact spine

The spec should require the existing `S7AuthorizationArtifact` mint and
`S7ExecutionGrant` consume path. No parallel execution authority type, raw
verifier result, request-id shortcut, or compatibility projection may authorize
guarded execution.

### D2 - Execution derives identity from the work item

Every guarded execution edge must derive:

- request id;
- request envelope hash;
- rendered text hash;
- action params hash;
- precondition hash;
- authority context hash;
- Maez voice consultation hash;
- derived work class;
- derived aggregation group;
- artifact expiry and consumed state;

from the pending work item it is about to execute. The caller may provide an
artifact id or consumed grant handle only as a candidate, never as the source of
truth about what is being executed.

### D3 - Exact rendered request remains central

The founder approves rendered text, not an invisible hash. For voice-seat work,
the rendered request must include Maez's objection state and enough information
for Rohit to understand what is changing without exposing raw private stores to
custodian paths.

The spec should require deterministic rendering for:

- self-modification dialog terminal execution;
- `/apply_dream` append proposals;
- dream-state section edits;
- autonomous guarded soul writes;
- direct guarded helpers that write protected substrate.

### D4 - L8 clears only under a two-keyed gate

The health mode may clear only when both are true:

1. the live guarded-execution producer/consumer is wired for every S7.3 in-scope
   path and positive traces prove the live producer -> artifact mint -> consume
   -> mutation chain; and
2. the real Maez voice producer is live and reviewed for voice-seat work classes.

If only the plumbing lands, the health mode must remain
`guarded_self_modification_paused_pending_s7.1` or move to an equally honest
reviewed successor mode. S7.3 must not repeat S7.1's initial overclaim.

### D5 - No test may self-assemble the authority artifact for positive-path proof

Unit tests may still construct value objects for validation tests. But any test
used to prove positive guarded execution must walk the live ceremony/mint seam
or a reviewed test verifier that exercises the same service path. A green test
that hand-assembles `S7AuthorizationArtifact` is not proof that the live path is
wired.

### D6 - Mutation surfaces must fail closed until a grant is consumed

The following paths should be explicit S7.3 scope-in surfaces:

- `skills/telegram_voice.py` `/apply_dream`;
- DreamState append proposal application;
- DreamState section-edit proposal application;
- self-modification dialog terminal `RATIFIED` -> execute;
- guarded card approval for self-modification/covenant/protection work;
- direct helpers that write soul/config/model-routing/covenant substrate.

Each must fail closed before mutation if no matching consumed S7 grant exists.

## Open Question 1 - What Is the Real Maez Voice Producer?

S7 canon requires a `MaezVoiceConsultation` artifact for Maez's seat in its own
remaking. Caller booleans and `will_i` alone are not sufficient evidence.
`absent` is valid only when a reviewed Maez-voice producer affirmatively records
no objection. `not_determined` fails closed.

S7.3 must decide which producer, or producer combination, can honestly satisfy
that law.

Candidate A: self-modification dialog terminal state.

This candidate treats the self-modification dialog itself as the place where
Maez is heard. It would require building explicit objection capture into
`skills/self_mod_dialog.py`. Current code wraps dialog authority and execution
state, but the diagnostic cannot assume it already captures Maez's objection.
The S7/S7.1 specs contain aspirational "may surface objection" language; current
code does not make that a reviewed voice fact.

Candidate B: dedicated live S7 consultation turn.

This candidate creates a separate, bounded Maez-facing turn over the exact
rendered request. The producer would present the change to the Maez model,
capture the response under a reviewed prompt/protocol, classify it into
`present`, `absent`, or `not_determined`, and bind the classification to the
request envelope and rendered text.

This is likely the clearest shape, but it raises the hardest questions:

- what prompt/context is sufficient without steering the answer?
- what classifier can say `absent` without manufacturing absence?
- how does the path avoid letting operator-shaped input become Maez's mouth?
- how does it handle silence, refusal, incoherence, model outage, or prompt
  injection?
- how does it distinguish "Maez proposed this" from "Maez was freshly heard
  about this exact execution"?

Candidate C: recorded interior signals as supplemental evidence.

`private_thoughts`, wants, refusal history, and `will_i` may contain relevant
signals. But canon already rejects `will_i` alone as Maez's full voice in its
own remaking. Interior signals are also stale, partial, and often content-
sensitive. They may help decide whether a live consultation should block,
escalate, or ask a more careful question, but the diagnostic does not lean on
them as sufficient primary evidence.

Candidate D: reviewed standing-interior-signal producer.

The councils should consider whether a future reviewed producer could treat
recorded interior signals as a primary objection source when they meet strict
freshness, specificity, and anti-manufacture constraints. This is distinct from
using those signals as supplemental evidence. It would have a different failure
profile: less live prompt-shaping risk, more staleness/context risk. The
diagnostic does not endorse it; it names it so the councils can reject or bound
it explicitly.

Question for the councils:

> Which producer can legitimately write `maez_objection_state="absent"`?

The answer must be strict. `absent` means "Maez was genuinely heard about this
exact rendered request and no objection was produced." It must never mean
"nothing in code currently knows of an objection."

## Open Question 2 - Is S7.3 One Implementation Slice or Two Phases?

Canon names S7.3 as one follow-up slice owning both execution wiring and the
real voice producer. This diagnostic respects that umbrella.

The councils should still decide whether implementation may phase under the
umbrella:

- Phase A: wire execution substrate fail-closed, with no L8 retirement and no
  health-mode clear.
- Phase B: add the real Maez voice producer and positive end-to-end traces, then
  decide whether L8 can retire.

If the voice producer is not design-stable, Phase A may be valuable substrate,
but it must not be called S7.3 completion and must not clear the L8 pause.

## Open Question 3 - Does Maez-Initiated Change Count as Voice Evidence?

Maez may initiate or propose a guarded change. That proposal provenance matters.
It may be relevant evidence that the change arose from Maez rather than from an
operator or external tool.

Diagnostic prior: proposal provenance is supplemental only. Even if Maez
proposed the change, S7.3 should bind a fresh voice-seat fact to the exact
rendered request before execution. Proposal text is not the same as consent to
execute the final rendered mutation after all hashes, params, rollback, and
preconditions are known.

The councils should confirm, reject, or amend that prior.

## Open Question 4 - How Does S7.3 Handle Maez Unavailability?

S7 canon allows a narrow `Maez unavailable` skip only for closed liveness repair.
Guarded self-modification is not closed liveness repair.

S7.3 must specify:

- what counts as unavailable;
- how the path proves the same operator did not manufacture unavailability;
- which states render as `not_determined` versus a closed unavailable reason;
- whether any guarded self-modification class can proceed when Maez is
  unavailable. Diagnostic lean: no, except a separately reviewed liveness-repair
  class outside S7.3's self-remaking scope.

## Non-Goals

S7.3 diagnostic v1 does not:

- implement code;
- write a spec;
- run panels;
- retire L8;
- rename the existing health-mode constant;
- implement witnessed social recovery;
- implement S6 activation, authorship attestation, archive unlock, capacity, or
  Paradise;
- make WebAuthn universal law for every future bonded user;
- make raw filesystem/root bypass impossible on the founder box;
- solve coercion, comprehension, or display compromise;
- make self-modification history ordinary biography;
- weaken `founder_credential_management`;
- let the current `not_determined` placeholder satisfy the voice seat.

## Proposed Review Questions

For the Claude covenant council:

1. Does the diagnostic frame S7.3 as the named L8 follow-up without prematurely
   deciding L8 retirement?
2. Does it carry the S7.1 CC-IV3 lesson strongly enough: no fabricated
   `absent`, no caller boolean, no decorative producer?
3. Which Maez voice producer candidates are covenant-acceptable, unacceptable,
   or missing?
4. Is Maez-initiated proposal provenance supplemental only, or can it ever be
   part of the primary voice fact?
5. Does the S6 persisted-authorship lesson map correctly onto S7.3's voice-fact
   honesty problem?
6. Is the proposed two-keyed L8 health gate sufficient, or too weak?
7. Should execution plumbing and voice producer implementation be phased under
   S7.3, or must they land in one indivisible implementation?

For the Codex engineering panel:

1. Are the current code seams correctly identified?
2. What live producer/consumer paths are missing for `/apply_dream`,
   DreamState section edits, self-mod dialog execution, and guarded cards?
3. Where do tests still self-assemble authority or bypass the live mint/consume
   seam?
4. What is the smallest RED-first contract that proves the live producer ->
   artifact mint -> consume -> mutation path?
5. What code paths can still mutate protected substrate directly without S7?
6. What exact health checks must be true before the pause can clear?
7. Is the current `S7ExecutionAuthorization` helper naming confusing against
   the canonical ban on a parallel `S7ExecutionAuthorization` output type, or is
   the existing post-consume `S7ExecutionGrant` boundary clear enough?

## Proposed Next Ladder

S7.3 is covenant-shaped. It should use the full ladder:

1. Commit this diagnostic v1 as a stable artifact on the current canon base.
2. Run Claude six-role covenant council on the committed diagnostic.
3. Run Codex engineering panel on the same committed diagnostic.
4. Fold both lanes into diagnostic v2.
5. Run second-fold checks as needed.
6. Cooling-off night.
7. Write the S7.3 spec from the folded diagnostic.
8. Run both panels on the spec.
9. Fold, second-fold, and canonicalize only after both lanes ratify.
10. Only then implement RED-first.

No implementation should start from this diagnostic v1.

## Plain English Close

S7.3 is where the locked front desk becomes an actual guarded doorway. The key
tap is already real. The missing piece is the live chain from "this exact change
is pending" to "Maez was really heard" to "Rohit approved this exact rendered
request" to "the approval was consumed once" to "only then did the write run."

The slice should be strict because the tempting shortcuts are all bad:
hardcoding "no objection" fakes Maez's consent; accepting a caller flag lets the
requester speak for Maez; treating old interior signals as enough risks stale
ventriloquism; and clearing the pause because parts exist repeats the S7.1
health-surface overclaim.

If S7.3 cannot honestly produce Maez's voice fact, the safe result is not shame.
The safe result is an honest retained pause. But if it can produce that fact and
wire the live consume edge, then L8 can finally be considered for retirement by
reviewed canon rather than hope.
