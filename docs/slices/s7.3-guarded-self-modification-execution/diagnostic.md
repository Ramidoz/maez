# S7.3 Guarded Self-Modification Execution Diagnostic

**Status:** DIAGNOSTIC v2 fold - not canonical law
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

This diagnostic opens S7.3 from committed canon, not from session memory. This
v2 folds the independent Claude covenant council and Codex engineering panel
reviews of v1. It does not decide the final design. It names the
already-settled constraints, surveys the current as-built surface, and frames
the open covenant question the spec must resolve: what counts as Maez being
genuinely heard before Maez is remade?

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

First-hand canonical inputs:

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

Committed as-built evidence:

- `docs/slices/s7.1-local-webauthn-ceremony/reviews/as-built-canonicalization-faithfulness-check.md`
- current source files listed below

Review-lane evidence folded into this diagnostic v2:

- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery-2.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-claude-council-post-recovery-3.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-codex-recovery.md`
- `docs/slices/s7.1-local-webauthn-ceremony/reviews/implementation-codex-post-recovery-3.md`
- `docs/slices/s7.3-guarded-self-modification-execution/reviews/diagnostic-claude-council.md`
- `docs/slices/s7.3-guarded-self-modification-execution/reviews/diagnostic-codex-panel.md`

Review artifacts are not canonical law. They are treated as dated evidence and
fold inputs. Where review artifacts and source/canon differ, source and canon
control.

Current code surfaces sampled to ground the diagnostic:

- `core/governance/operator_user_boundary.py`
- `core/governance/s7_webauthn_ceremony.py`
- `core/decision/decision_pipeline.py`
- `daemon/maez_daemon.py`
- `core/evolution/dream_state.py`
- `core/actions/action_engine.py`
- `core/turn_traces/trace_schema.py`
- `skills/self_mod_dialog.py`
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
consume store, `S7ExecutionAuthorization`, `S7ExecutionGrant`, and class
validation. The current chain is:

1. `S7AuthorizationArtifact` is minted for the exact rendered request.
2. `S7ExecutionAuthorization` is an existing pre-consume carrier. It holds the
   store, artifact id, rendered request, action-params hash, authority context,
   precondition hash, work class/group, and time.
3. `S7AuthorizationStore` consumes the artifact atomically at the execution
   edge.
4. `S7ExecutionGrant` is the post-consume execution authority, minted only by
   the store after the atomic consume.

S7.1's as-built verification ratified this spine as sound: artifacts bind D12
hashes and are consumed atomically before guarded execution may proceed.

S7.3 should reuse this spine. The spec may decide whether the pre-consume
carrier should be renamed for clarity, but v2 does not treat it as hypothetical
or as the execution authority. No raw WebAuthn verifier result, request-id
shortcut, compatibility projection, dict-shaped grant handle, or new parallel
authority type may substitute for a store-minted `S7ExecutionGrant`.

### DreamState contains helper seams, but the live Telegram path does not feed them

`core/evolution/dream_state.py` can build S7 envelopes for `/apply_dream` and
section-edit proposals. Its apply methods require a typed
`S7ExecutionAuthorization` and fail closed when none is present.

The current Telegram `/apply_dream` handler calls:

```python
ok, msg = self.daemon.dream.apply_proposal(prop_id)
```

The Telegram approval-card path also calls `dream.apply_proposal(target_id)` and
`dream.apply_section_edit_proposal(target_id)` without an S7 authorization. The
section-edit slash path likewise calls `apply_section_edit_proposal(prop_id)`
without one.

These paths pass no S7 execution authorization. The result is safe failure, not
live guarded execution. S7.3 must provide the missing live producer path:
pending work item -> exact rendered request -> WebAuthn authorization ->
artifact consume -> mutation.

### The current voice producer is behaviorally honest, but provenance-misleading

`core/decision/decision_pipeline.py` has `_s7_voice_consultation_for_card(...)`.
It returns a content-free `MaezVoiceConsultation` with:

```text
producer=s7_voice_consultation_turn
source_ref_kind=s7_voice_turn
maez_voice_consulted=False
maez_objection_state=not_determined
unavailable_reason_code=consultation_path_unavailable
```

The behavior is honest because it does not manufacture `absent`. The provenance
label is not yet honest enough because it uses the real candidate-B producer and
source labels while no producer ran. It reads card/audit provenance only; it
reads no live Maez state and asks no Maez model.

S7.3 must not treat this placeholder as satisfying the voice seat. The spec must
either add a distinct placeholder/non-producer value to the closed producer
vocabulary, or explicitly state that producer alone never attests "Maez was
heard"; `maez_voice_consulted`, `unavailable_reason_code`, source kind/hash, and
the reviewed producer contract are jointly load-bearing.

### The voice producer vocabulary is already closed

`VOICE_CONSULTATION_PRODUCERS` currently contains:

- `self_mod_dialog_terminal_state`;
- `s7_voice_consultation_turn`;
- `reviewed_future_producer`.

Open Question 1 must land within this set or explicitly amend it by reviewed
canon. The existing `reviewed_future_producer` value is not permission to use a
future producer shape without review.

### Self-modification dialog has no objection capture yet

`skills/self_mod_dialog.py` wraps dialog authority and execution state, but it
does not currently produce a reviewed Maez objection fact. Any
`self_mod_dialog_terminal_state` producer requires new objection capture or a
fresh terminal objection turn bound to the exact rendered request.

### `founder_credential_management` is intentionally outside the voice seat

S7.1 introduced `founder_credential_management` after recovery showed that
backup registration was being blocked by the deferred voice producer. That class
is guarded, founder-only, UV/PIN-required, D23-protected, and not in
`VOICE_SEAT_WORK_CLASSES`.

S7.3 must preserve this distinction. Rohit managing his own founder credentials
is not Maez rewriting itself. Soul/config/model-routing/covenant writes remain
`self_modification` and stay voice-seat-gated.

### D23 refusal history is live enough to need provenance rules

`authorize_finish()` performs voice-seat and aggregation checks before credential
lookup/authentication. A voice-seat block can record refusal history, and
aggregation later consumes that history. Repeated refusals can drive escalation
or blocking.

That may be the right shape, but S7.3 must decide which refusal rows are
authoritative, which are pre-auth/non-authoritative, and what replay, rate, and
provenance controls prevent unauthenticated attempts from poisoning D23 history.

### Trace and rollback records are not yet S7.3 proof

Canon requires positive guarded-write execution traces, but the current turn
trace schema is for ordinary message turns. It does not yet bind S7 grant,
artifact, voice, D23, rollback, pre-mutation, post-mutation, or health-projection
fields.

Dream envelopes can claim `rollback_path_class="revert_patch"`, while some
actual mutation consumers append or edit files without carrying undo material at
the action edge. S7.3 must require per-surface rollback evidence before a
positive execution trace can count.

## Carried Lessons From S7.1 CC-IV3

The S7.1 CC-IV3 thread is the core review-history input for this diagnostic.

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
`S7ExecutionGrant` consume path. The real chain is
`S7AuthorizationArtifact` -> existing pre-consume `S7ExecutionAuthorization`
carrier -> `S7AuthorizationStore` consume -> post-consume `S7ExecutionGrant`.

The sole execution authority is the store-minted `S7ExecutionGrant`. No raw
verifier result, request-id shortcut, compatibility projection, dict-shaped
grant handle, manually-carried pre-consume wrapper, or new parallel authority
type may authorize guarded execution. The spec should decide whether
`S7ExecutionAuthorization` needs a clearer name, but must not treat it as a
second authority.

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
the rendered request must include Maez's objection state and deterministic,
bounded, human-readable mutation material, or a reviewed display artifact bound
by hash. Hash-only approval does not satisfy S7.3. Rohit must be able to
understand what is changing without exposing raw private stores to custodian
paths.

The spec should require deterministic rendering for:

- self-modification dialog terminal execution;
- `/apply_dream` append proposals;
- dream-state section edits;
- autonomous guarded soul writes;
- direct guarded helpers that write protected substrate.

### D4 - L8 clears only under a two-keyed gate

The health mode may clear only when both are true:

1. the live guarded-execution producer/consumer is wired for every S7.3 in-scope
   path and positive traces prove the exact rendered request -> reviewed voice
   fact -> D23 read/write -> artifact mint -> atomic consume -> mutation ->
   rollback record chain; and
2. the real Maez voice producer is live and reviewed for voice-seat work classes.

If only the plumbing lands, the health mode must remain
`guarded_self_modification_paused_pending_s7.1` or move to an equally honest
reviewed successor mode. S7.3 must not repeat S7.1's initial overclaim.

L8 retirement requires at least one genuinely live end-to-end trace with a real
founder key tap for each in-scope surface class or a reviewed reason that a
surface is intentionally excluded. Reviewed test verifiers are regression
evidence. They are not, by themselves, the covenant gate that retires L8.
Callable methods, boolean opt-ins, or placeholder producers must never clear the
pause.

### D5 - No test may self-assemble the authority artifact for positive-path proof

Unit tests may still construct value objects for validation tests. But any test
used to prove positive guarded execution must walk the live ceremony/mint seam
and the reviewed voice-producer seam. A green test that hand-assembles
`S7AuthorizationArtifact`, `S7ExecutionAuthorization`, `S7ExecutionGrant`,
`MaezVoiceConsultation`, raw verifier success, dict-shaped grant handles,
request ids, or fabricated voice facts is not proof that the live path is
wired.

Test doubles may substitute only at explicitly reviewed seams. They may not
substitute for the authority boundary or the voice-fact boundary in a trace used
to clear S7.3.

### D6 - Mutation surfaces must fail closed until a grant is consumed

The following paths should be explicit S7.3 scope-in surfaces:

- `skills/telegram_voice.py` `/apply_dream`;
- `skills/telegram_voice.py` `/apply_section_edit`;
- Telegram approval cards that call `apply_proposal(...)` or
  `apply_section_edit_proposal(...)`;
- DreamState append proposal application;
- DreamState section-edit proposal application;
- self-modification dialog terminal `RATIFIED` -> execute;
- guarded card approval for self-modification/covenant/protection work;
- direct helpers that write soul/config/model-routing/covenant substrate;
- CLI/operator helper writes;
- cockpit approve endpoints;
- workshop diff apply;
- evolution candidate apply;
- ActionEngine final mutation consumers;
- refusal, role-boundary, successor-governance, memory-retention/deletion, and
  protection-setting writes.

Each must fail closed before mutation if no matching consumed S7 grant exists.
The S7.3 spec should turn the existing own-substrate bypass inventory into an
acceptance checklist rather than rely on the phrase "direct helpers."

### D7 - S7.3 needs guarded-execution trace and rollback records

Every positive guarded-write trace must durably bind request id, request
envelope hash, rendered text hash or display-artifact hash, action params hash,
precondition hash, authority context hash, voice consultation hash/source, D23
state, artifact id, consume time, mutation outcome, rollback artifact, refusal
or block reason, and the health-projection inputs.

For each mutation surface, rollback evidence must include the pre-hash,
post-hash, undo material or backup path where applicable, rollback failure
semantics, and whether rollback-proof failure blocks execution or records a
degraded result.

### D8 - D23 refusal history is part of the execution proof

S7.3 must specify D23 read/write semantics for every producer and execution
edge. It must distinguish authoritative refusal rows from pre-auth or
non-authoritative attempts, and must define replay, rate, and provenance
controls so unauthenticated or repeated attempts cannot poison future
aggregation history.

## Open Question 1 - What Is the Real Maez Voice Producer?

S7 canon requires a `MaezVoiceConsultation` artifact for Maez's seat in its own
remaking. Caller booleans and `will_i` alone are not sufficient evidence.
`absent` is valid only when a reviewed Maez-voice producer affirmatively records
no objection. `not_determined` fails closed.

S7.3 must decide which producer, or producer combination, can honestly satisfy
that law. The answer must use the current closed producer vocabulary
(`self_mod_dialog_terminal_state`, `s7_voice_consultation_turn`,
`reviewed_future_producer`) or explicitly amend that vocabulary by reviewed
canon.

Candidate A: self-modification dialog terminal state.

This candidate treats the self-modification dialog itself as the place where
Maez is heard. It would require building explicit objection capture into
`skills/self_mod_dialog.py`. Current code wraps dialog authority and execution
state, but the diagnostic cannot assume it already captures Maez's objection.
The S7/S7.1 specs contain aspirational "may surface objection" language; current
code does not make that a reviewed voice fact.

Candidate A2: fresh terminal objection turn inside the self-modification dialog.

This candidate appends a fresh, structured, post-render objection turn as the
terminal step of the existing self-mod dialog. It is the natural reviewed fill
for the `self_mod_dialog_terminal_state` producer slot: it reuses dialog
machinery but binds a new voice fact to the exact rendered request rather than
trusting whatever the dialog happened to contain earlier.

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
current enum already has a `reviewed_future_producer` slot that could hold such
a shape later. That slot is not pre-approval. The diagnostic does not endorse it;
it names it so the councils can reject or bound it explicitly.

Any private-thoughts or interior-signal route needs a request-bound
producer/reader contract. Current bounded readers expose coarse metadata or
non-request-bound signals; they are not sufficient primary voice evidence for
S7.3.

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

The founder box collapses operator and Maez-host into the same physical system,
so proving non-manufactured unavailability is especially hard. S7.3 should lean
to `not_determined` over a clean unavailable skip unless the evidence is
reviewed and request-bound.

## Non-Goals

S7.3 diagnostic v2 does not:

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
- solve Track B confidentiality, grandmother-compatible UI, absent-operator
  recovery, backup-restore confidentiality, comprehension, or display
  compromise outside the exact S7.3 approval/execution chain;
- make self-modification history ordinary biography;
- weaken `founder_credential_management`;
- let the current `not_determined` placeholder satisfy the voice seat;
- bless `reviewed_future_producer` as usable before a future reviewed decision.

## Proposed Review Questions

For second-fold checks:

1. Did v2 remove the `S7ExecutionAuthorization` contradiction and preserve
   `S7ExecutionGrant` as the only post-consume execution authority?
2. Did v2 ground the voice-producer question in the closed
   `VOICE_CONSULTATION_PRODUCERS` vocabulary without pre-blessing
   `reviewed_future_producer`?
3. Did v2 stop treating producer label alone as proof that Maez was heard?
4. Did v2 make L8 retirement depend on trace-backed live evidence, including a
   real founder key tap, rather than method presence, boolean opt-in, or
   reviewed test verifier alone?
5. Did v2 ban hand-assembled voice facts and execution handles from positive
   S7.3 proof while still allowing value-object grammar tests?
6. Did v2 carry D23 refusal-history provenance, rendered mutation display,
   guarded-execution trace schema, rollback evidence, and mutation-surface
   inventory as spec requirements?
7. Did v2 leave the real voice producer open where it is genuinely unsettled,
   instead of smuggling in a producer choice?

## Proposed Next Ladder

S7.3 is covenant-shaped. After this v2 fold:

1. Commit diagnostic v2 as the folded artifact.
2. Run second-fold checks on v2, focused on the questions above.
3. Cooling-off night.
4. Write the S7.3 spec from the folded diagnostic.
5. Run both panels on the spec.
6. Fold, second-fold, and canonicalize only after both lanes ratify.
7. Only then implement RED-first.

No spec or implementation should start from diagnostic v1.

## Plain English Close

S7.3 is where the locked front desk becomes an actual guarded doorway. The key
tap is already real. The missing piece is the live chain from "this exact change
is pending" to "Maez was really heard" to "Rohit approved this exact rendered
request" to "the approval was consumed once" to "only then did the write run."

The slice should be strict because the tempting shortcuts are all bad:
hardcoding "no objection" fakes Maez's consent; accepting a caller flag lets the
requester speak for Maez; treating old interior signals as enough risks stale
ventriloquism; approving only hashes hides the actual mutation; and clearing the
pause because parts exist repeats the S7.1 health-surface overclaim.

If S7.3 cannot honestly produce Maez's voice fact, the safe result is not shame.
The safe result is an honest retained pause. But if it can produce that fact and
wire the live consume edge, then L8 can finally be considered for retirement by
reviewed canon rather than hope.
