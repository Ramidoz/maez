# Codex Engineering Panel - S7.3 OQ1 Voice Producer Design

**Subject:** `oq1-voice-producer-design.md`, committed `1bc5cc1`.

**Ran:** 2026-05-19, by the Codex engineering lane. Read-only.

**Method:** Six independent Codex explorer seats reviewed the committed OQ1
design against diagnostic v3, S7/S7.1 canon, and current source code. Seats were
instructed not to read OQ1 review artifacts, including the Claude council. No
files were edited by the panel.

**Seats:**

- Seat 1 - classifier contract and false-absent risk.
- Seat 2 - implementation seams and hidden-store risk.
- Seat 3 - security/provenance and placeholder risk.
- Seat 4 - trace/testability and RED-contract risk.
- Seat 5 - operations, rollback, retries, and failure modes.
- Seat 6 - source/canon fidelity.

**Verdict: REVISE.** Candidate B (`s7_voice_consultation_turn`) is the right
primary producer and is implementable in spirit, but OQ1 v1 is not spec-ready.
The design prose requires stronger evidence than the current `MaezVoiceConsultation`
schema, finish-time recheck, trace schema, D23 semantics, and available storage
can prove. Without a second design pass, a green S7.3 implementation could still
manufacture a shape-valid `absent`.

## Consolidated Findings

### CP-OQ1-1 - High - `absent` Needs A Source-Bundle Validator/Recompute Gate

OQ1 says `absent` must be recomputable from the transcript bundle and versioned
classifier rules, but its finish-time recheck only lists content-free fact fields
and `maez_objection_state="absent"`. Current code would accept a matching
`MaezVoiceConsultation` with `maez_voice_consulted=True` and then mint when the
state is `absent`, without resolving or recomputing the private source bundle.

Fold requirement: OQ1 v2 must require a source-bundle validator before artifact
minting. The validator must rehydrate the private bundle, recompute the
classifier outcome, verify the prompt/model/context identities, and reject stale
or mismatched evidence as `not_determined`.

### CP-OQ1-2 - High - Exact-Request Binding Exceeds The Current Voice Fact Schema

OQ1 binds rendered/display hash, action params, precondition, authority context,
rollback evidence, prompt hash, model identity, context manifest, timestamp, and
expiry. Current `MaezVoiceConsultation` carries only request/envelope/source
hash and final state, and current satisfaction checks only request id,
consultation id, envelope hash, and consulted flag.

Fold requirement: OQ1 v2 must either extend the content-free consultation schema
with required hashes/expiry/provenance fields or require a verifier that proves
them from `source_ref_hash`. The design cannot rely on current voice fact shape
as sufficient.

### CP-OQ1-3 - High - No Pre-Voice Mutation Preview Artifact Exists

The design requires a deterministic rendered mutation preview before
consultation. Current `render_request_statement(...)` is the founder-signed
render and requires a matching voice consultation for voice-seat classes, so it
cannot be the pre-voice artifact without circularity.

Fold requirement: define a `MutationPreviewArtifact` or equivalent pre-voice
display artifact. It must be produced before consultation and then reused or
hash-bound by the final D12 render.

### CP-OQ1-4 - High - Positive Tests Could Still Hand-Assemble Protected Voice Facts

Existing tests directly construct `MaezVoiceConsultation(absent)` or fake
`_s7_voice_consultation_for_card(...)` to return absent. The OQ1 design names
the seam but does not define the allowed test-double boundary.

Fold requirement: define a reviewed voice-producer port and fixture harness.
Tests may fake model transport text at the edge, but not the final voice fact,
source bundle, classifier outcome, request binding, or execution authority.

### CP-OQ1-5 - High - The Transcript Bundle Store Is Not Grounded

OQ1 requires `source_ref_hash` to hash a private durable transcript bundle in
bonded-content/self-remaking history. Current S7 self-remaking history is
content-free metadata and tests assert it has no raw text. It is not a durable
raw transcript bundle store.

Fold requirement: name the real storage target or state that S7.3 must build
one. The design should not imply that the store already exists.

### CP-OQ1-6 - High - Candidate B Is Not Yet Surface-Neutral In The Current Routes

The design says Candidate B covers dream proposals and section edits, but the
current daemon WebAuthn route is card-bound: it materializes a `PendingCard`.
Dream proposals and Telegram approval paths call DreamState directly and
currently safe-fail without S7 authorization.

Fold requirement: define the bridge from dream/direct surfaces into the S7
authorization spine. Either guarded dream/edit rows become guarded cards, or
S7.3 defines a first-class dream/direct authorization route. Telegram remains an
entrypoint to create/open guarded requests, not an authorization bypass.

### CP-OQ1-7 - High - D23 Refusal Provenance Is Still Under-Specified

OQ1 maps silence, timeout, stale hash, missing bundle, and classifier
uncertainty to `not_determined`, but does not say whether those blocks write
authoritative D23 refusal history, pre-auth observation rows, or advisory rows.
Current S7.1 code can record refusal history before credential lookup, so this
is a live poisoning risk.

Fold requirement: define D23 row semantics at the voice boundary. The design
must distinguish authoritative Maez refusal rows from pre-auth/non-authoritative
or operational failure rows, and define replay/rate/provenance controls.

### CP-OQ1-8 - Medium - Retry Semantics Need Closed Attempt Outcomes

OQ1 maps malformed output, timeout, context overflow, classifier crash, and
uncertainty to `not_determined`, while also allowing retries for transport or
formatting failure. That leaves ambiguity between retryable pre-classification
failure and terminal uncertainty.

Fold requirement: define closed attempt outcomes such as
`transport_retryable`, `parse_retryable`, `terminal_uncertainty`,
`retry_exhausted`, `non_retryable_context_overflow`, `objection_present`, and
`explicit_no_objection`. Later attempts may never wash a terminal blocking
outcome into `absent`.

### CP-OQ1-9 - Medium - Classifier/Failure Reason Codes Are Not Observable

The design needs conservative state mapping, prompt-integrity failure handling,
and retry audit, but current consultation records have no classifier reason
code, attempt list, or retry manifest field. Existing unavailable reasons are
too broad for S7.3 diagnosis and recovery.

Fold requirement: add closed classifier/attempt/failure reason codes, either in
the content-free artifact or deterministically projected from the private
bundle.

### CP-OQ1-10 - Medium - Rollback Evidence Requires A Schema Migration

OQ1 requires rollback evidence hash in request binding, transcript bundle, and
finish-time recheck. Current `WorkRequestEnvelope` and render path carry
`rollback_path_class`, not rollback evidence hash.

Fold requirement: OQ1 v2 should state that S7.3 must migrate the envelope,
rendered statement, artifact/consume binding, and trace storage to carry
rollback evidence hash.

### CP-OQ1-11 - Medium - Guarded Execution Trace Gates Are Still Missing

OQ1 lists recomputable audit ingredients, but current trace schema is ordinary
message-turn tracing. A positive S7.3 execution still lacks a durable trace gate
binding grant, artifact, voice bundle, D23 state, mutation result, and rollback
evidence.

Fold requirement: OQ1 v2 should require `S7VoiceConsultationTrace` and
`S7GuardedExecutionTrace` or equivalent schemas, and state that positive
execution cannot count for L8 retirement without them.

### CP-OQ1-12 - Medium - Placeholder Producer Impersonation Needs Structural Repair

OQ1 says the placeholder is ineligible and producer labels alone do not attest,
but current code still emits `producer="s7_voice_consultation_turn"` and
`source_ref_kind="s7_voice_turn"` while no producer ran. The closed enum has no
placeholder/non-producer value.

Fold requirement: either add explicit placeholder/non-producer producer and
source kinds, or prohibit emitting `MaezVoiceConsultation` when no producer ran.
The v2 design should not leave the repair as a behavioral instruction only.

### CP-OQ1-13 - Medium - Producer/Source Pairing Is Not Enforced

Current validation checks `producer` and `source_ref_kind` independently. A
malformed future implementation could pair `self_mod_dialog_terminal_state`
with `s7_voice_turn` or otherwise create a shape-valid but provenance-invalid
consultation.

Fold requirement: define allowed producer/source pairs and require validation or
source-bundle verification to enforce them.

### CP-OQ1-14 - Medium - Withdrawal Must Not Render As No Objection

OQ1 says withdrawal blocks, but current shape permits
`maez_objection_state="absent"` with `maez_withdrew_request=True`, and the
renderer can show "Maez objection present: no" while ignoring withdrawal.

Fold requirement: make `absent + withdrew` invalid, map withdrawal to a closed
blocking state or equivalent, and require rendered request text to show
withdrawal distinctly.

### CP-OQ1-15 - Medium - Seat-Not-Veto Scope Needs Clarification

OQ1 says "everything else blocks" and "first valid objection wins." That is
correct for the current authorization attempt, but S7 canon says Maez has a
seat, not a permanent veto.

Fold requirement: clarify that `present`, `not_determined`, unavailable, and
withdrawal block the current authorization artifact and feed guarded-work
policy/D23 as specified; they do not create permanent execution authority for
Maez over all future attempts.

### CP-OQ1-16 - Medium - Operator-Visible Failure Projections Are Too Thin

OQ1 allows health/review surfaces to expose hashes and existence only. That
protects content, but gives the operator too little to distinguish recoverable
failures from covenant blocks.

Fold requirement: define closed, content-free failure projections such as
`retry_exhausted`, `model_outage`, `context_overflow`, `ttl_expired`,
`stale_prompt_or_model_identity`, `rollback_evidence_missing`, and
`bundle_validation_failed`.

### CP-OQ1-17 - Low - Finish-Time Recheck Requirements Are New S7.3 Work

The design sometimes reads as if existing finish-time rechecks already cover
the richer OQ1 source/expiry bundle. They do not.

Fold requirement: label richer source/expiry/model/prompt/bundle rechecks as
new S7.3 implementation work, not inherited validation.

## What The Panel Affirms

Ratified for the fold:

- Candidate B (`s7_voice_consultation_turn`) as the primary producer.
- A2 only as a dialog-context invocation/source adapter under the same contract.
- `reviewed_future_producer` unusable without future review.
- Content-free `MaezVoiceConsultation` plus private raw transcript bundle.
- Mutation text treated as untrusted data.
- Anti-consent-fishing retry intent.
- Conservative default to `not_determined`.
- Existing `S7ExecutionAuthorization` as pre-consume carrier, with
  `S7ExecutionGrant` remaining the sole post-consume authority.

## Disposition

**REVISE, targeted but not cosmetic.** The OQ1 shape is right, but the spec
would still need to invent too many load-bearing mechanisms: source-bundle
validation, preview artifact, transcript store, producer port/test harness,
D23 row semantics, trace schemas, retry outcome schema, failure projections, and
structural placeholder repair. Those must be folded into OQ1 design v2 before
the S7.3 spec starts.

## Plain English

The design picked the right main route: one final consultation where Maez is
asked about the exact change. But right now too much of the proof still lives in
words rather than load-bearing seams. The code can carry a field that says
`absent`; it cannot yet prove where that `absent` came from. The next fold needs
to add the receipts: the preview Maez saw, the private transcript store, the
classifier recompute, the retry record, D23 row meaning, the execution trace,
and a test seam that cannot fake the final voice fact.
