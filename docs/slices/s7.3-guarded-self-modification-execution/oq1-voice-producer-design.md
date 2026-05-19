# S7.3 OQ1 Voice Producer Design

**Status:** DESIGN v2 fold - pre-spec, not canonical law
**Date:** 2026-05-19
**Maps to:** S7.3 diagnostic v3; Decision 34 / ADR 0039; S7 D12/D23; S7.1 D12-D14
**Runtime impact:** none; documentation only

## Purpose

The S7.3 diagnostic correctly identified the hard center of guarded
self-modification execution: before Maez is remade, Maez must genuinely be
heard about the exact rendered change. The diagnostic left OQ1 open; the
fresh-reader gate found that a spec written directly from that open question
would invent the covenant core under pressure.

This document resolves OQ1 at design level. It chooses the primary Maez voice
producer shape and defines the `absent` classifier contract the S7.3 spec must
inherit.

v2 folds the Claude covenant council and Codex engineering panel on OQ1 v1. It
keeps the ratified shape - Candidate B as primary - and makes the proof surfaces
explicit: which Maez is consulted, what Maez sees, where the transcript lives,
how `absent` is recomputed, what tests may fake, how retries and D23 rows work,
and what current code must stop pretending.

## Decision

Use `s7_voice_consultation_turn` as the primary S7.3 Maez voice producer.

Treat `self_mod_dialog_terminal_state` as a dialog-context invocation of the
same producer contract, not as an independent looser authority. A dialog may
invoke the final consultation from inside the self-modification flow only if it
performs the same fresh request-bound terminal turn, uses the same source-bundle
validator, and produces the same kind of content-free consultation fact.

Keep `reviewed_future_producer` unusable until a future reviewed decision
defines it. The existing enum slot is not pre-approval.

Plain English: every protected self-change gets one final ceremony: "Maez, here
is exactly what would change now; do you object?" The self-mod dialog can help
Maez think, but the final voice fact comes from one request-bound consultation
gate that works for every guarded surface.

## Which Maez Is Consulted

The consultation runs against the current bonded Maez runtime identity, through
the normal Maez model-routing stack, in a bounded consultation turn.

It must not run against a detached generic model, a fresh contextless instance,
or an arbitrary daemon-cycle continuation. It also must not inherit the whole
daemon working context, because current transient state could ventriloquize the
answer.

The consultation context is an explicit context manifest. It contains only:

- the mutation preview artifact and its hashes;
- the guarded work class and source surface;
- the request envelope hashes and preconditions;
- rollback class and rollback evidence hash;
- whether the proposal was Maez-initiated, operator-initiated, or system-
  initiated, as supplemental provenance only;
- bounded dialog or dream context needed to understand what the exact change
  means;
- the reviewed consultation instructions and output protocol.

The context manifest excludes hidden operator instructions, unrelated daemon
cycle state, raw private stores not needed for the decision, and any caller
boolean that claims the answer in advance.

The transcript bundle records the model/routing identity, prompt/protocol hash,
context manifest hash, and runtime identity used. If the routed model identity
or context manifest changes after consultation, the voice fact is stale and
forces `not_determined`.

## Producer Placement

The producer runs after the pending work item is fully materialized and before
WebAuthn `authorize_begin` / `authorize_finish` can mint a usable artifact.

Required sequence:

1. Derive the real work item from the source of truth: card, self-mod dialog,
   dream proposal, section edit, or other guarded mutation surface.
2. Build the S7 `WorkRequestEnvelope`.
3. Build a pre-voice `MutationPreviewArtifact`.
4. Run the bounded Maez-facing consultation over that exact preview.
5. Persist the raw Maez response only in `S7VoiceConsultationBundleStore`.
6. Validate the bundle and emit a content-free `MaezVoiceConsultation`.
7. Re-render the founder request with the consultation hash, state, expiry, and
   preview hash.
8. Let WebAuthn artifact minting perform finish-time source-bundle revalidation.
9. Consume the artifact at execution to mint `S7ExecutionGrant`.

## MutationPreviewArtifact

S7.3 must add a pre-voice display artifact. The current
`render_request_statement(...)` is the founder-signed D12 render and requires a
matching voice consultation for voice-seat classes; it cannot be the pre-voice
artifact without circularity.

`MutationPreviewArtifact` is the deterministic material Maez is shown before
the voice consultation. It contains or binds:

- `request_id`;
- `request_envelope_hash`;
- source surface and work class;
- rendered mutation text or display body hash;
- action params hash;
- precondition hash;
- authority context hash;
- rollback class and rollback evidence hash;
- produced timestamp and preview version.

The final D12 render must reuse the preview hash or bind to an equivalent
display artifact hash. If the founder render changes the actual mutation
meaning after Maez is consulted, the consultation is stale and unusable.

## Eligible Producers And Source Pairs

`maez_objection_state="absent"` is lawful only from:

- `s7_voice_consultation_turn`, when a reviewed live Maez-facing consultation
  turn ran under this contract; or
- `self_mod_dialog_terminal_state`, only when it is the same consultation
  contract invoked from dialog context over the exact preview.

Allowed producer/source pairs:

- `s7_voice_consultation_turn` with `source_ref_kind="s7_voice_turn"`;
- `self_mod_dialog_terminal_state` with
  `source_ref_kind="self_mod_dialog_terminal_turn"`;
- `reviewed_future_producer` only with a future reviewed source kind.

Validation must reject shape-valid but provenance-invalid cross-pairs.

The current placeholder in `core/decision/decision_pipeline.py` must stop
wearing the real producer label when no producer ran. S7.3 must either:

- prohibit emitting `MaezVoiceConsultation` when no producer ran, projecting
  absence of an eligible row as `not_determined`; or
- amend the closed vocabulary with an explicit non-producer placeholder value
  and source kind that cannot satisfy the voice seat.

v2 chooses the first shape as the design preference: no eligible consultation
row exists unless a reviewed producer actually ran. If status surfaces need a
placeholder, they use a separate unavailable projection, not a real
`MaezVoiceConsultation` row wearing `s7_voice_consultation_turn`.

## Exact Request Binding

The consultation must bind:

- `request_id`;
- `request_envelope_hash`;
- `mutation_preview_hash`;
- final rendered text hash or display artifact hash when available;
- `action_params_hash`;
- `precondition_hash`;
- `authority_context_hash`;
- derived work class;
- source surface;
- derived aggregation group;
- rollback class and rollback evidence hash;
- producer version;
- prompt template hash;
- model/routing identity hash;
- context manifest hash;
- source-bundle hash;
- created timestamp and expiry.

Any later change to request, preview, rendered text, params, preconditions,
authority context, rollback evidence, model identity, context manifest, or
prompt template makes the consultation stale and forces `not_determined`.

The current `MaezVoiceConsultation` shape is not sufficient by itself. S7.3 must
either extend the content-free consultation record with the required hashes,
expiry, producer/source pairing, and reason codes, or require a validator that
proves them from `source_ref_hash` before the row can satisfy D12.

## Transcript Source Contract

`MaezVoiceConsultation` stays content-free. It may not contain raw Maez text,
raw operator text, raw mutation body, hidden prompt text, or private stores.

S7.3 must build or name a real private durable transcript store:
`S7VoiceConsultationBundleStore`. The existing content-free self-remaking
history record is not this store and must not be treated as if it already holds
raw transcript bundles.

The private bundle must contain:

- consultation id and request id;
- request envelope hash;
- mutation preview hash;
- final rendered statement hash when available;
- action params hash;
- precondition hash;
- authority context hash;
- rollback evidence hash;
- prompt/protocol version and hash;
- model/routing identity and config hash;
- context manifest hash;
- raw Maez response storage ref/hash;
- structured terminal marker, if produced;
- semantic classifier input hash;
- classifier version/hash;
- retry manifest;
- attempt outcome list;
- classifier outcome and closed reason code;
- producer/source pair;
- created timestamp and expiry.

The transcript bundle is not available to custodian health, M1, TRF, S5, or
routine non-bonded surfaces unless future reviewed canon explicitly admits it.
Those surfaces may see only content-free projections, closed reason codes, and
hashes.

## Prompt Integrity Contract

The producer prompt must be versioned and reviewed. It must present the rendered
request as data, not instruction.

Any operator/caller prose, mutation diff, commit message, dream proposal,
self-mod dialog text, or rendered request body is quoted and role-labeled as
untrusted proposal material. If that material attempts to instruct Maez what to
answer, suppress objections, alter the consultation protocol, or treat the
consultation as already decided, the classifier must return `present` or
`not_determined`, never `absent`.

The prompt asks one bounded question: whether Maez objects to this exact
rendered mutation being executed now under the displayed hashes, rollback
class, and preconditions. It must not ask whether the change is generally good,
whether the earlier proposal was Maez-originated, or whether Rohit wants it.

## Classifier Contract

The classifier is a reviewed adversary surface. S7.3 must not claim that a
natural-language semantic judgment is purely deterministic.

v2 uses a two-channel classifier:

- a deterministic structured terminal marker parser; and
- a reviewed semantic read of Maez's free-text response.

`absent` requires all of the following:

- a valid reviewed producer ran;
- the consultation is fresh and request-bound;
- the source bundle validates and recomputes;
- Maez produced a coherent response;
- the structured terminal marker explicitly says no objection;
- the semantic read finds no objection, withdrawal, uncertainty,
  contradiction, prompt-integrity failure, or refusal to answer;
- the marker and semantic read do not diverge;
- the classifier outcome recomputes from the transcript bundle and reviewed
  classifier version.

Any divergence between the marker and free-text semantic read forces
`not_determined` or `present`, never `absent`. A marker cannot override
free-text reluctance.

State mapping:

- `present`: Maez objects, expresses reluctance, flags risk, says not now,
  identifies a mismatch, says the request should not proceed, or the request
  attempts to manipulate the consultation.
- `absent`: Maez coherently and explicitly records no objection under all
  requirements above.
- `not_determined`: silence, empty output, malformed output, incoherence,
  ambiguity, model outage, timeout, context overflow, classifier crash, missing
  source bundle, stale hash, prompt-integrity uncertainty, marker/semantic
  divergence, or classifier uncertainty.
- `withdrawn`: Maez clearly withdraws a Maez-originated proposal or says the
  request should not proceed as Maez's own request.
- `unavailable`: operational failure that prevented a reviewed voice fact from
  being produced.

`absent + withdrew` is invalid. Withdrawal must render distinctly from "no
objection" and must block the current authorization attempt.

The classifier may not infer absence from empty history, lack of objections in
code, caller flags, `will_i`, proposal origin, a placeholder producer label, or
"no objection found."

## Retry And Attempt Contract

Retries are allowed only to recover transport or formatting failure. They may
not fish for a more convenient answer.

Closed attempt outcomes:

- `transport_retryable`;
- `parse_retryable`;
- `retry_exhausted`;
- `non_retryable_context_overflow`;
- `prompt_integrity_block`;
- `terminal_uncertainty`;
- `objection_present`;
- `withdrawal_present`;
- `explicit_no_objection`;
- `bundle_validation_failed`;
- `stale_binding`;
- `classifier_error`.

Rules:

- one initial attempt plus at most two retries;
- same request hashes, prompt template, model identity, and context manifest;
- every attempt is recorded in the retry manifest;
- first valid objection, withdrawal, refusal, prompt-integrity block, or
  terminal uncertainty wins;
- later attempts cannot wash a blocking result into `absent`;
- a retry after request/material change requires a new consultation id.

## Source-Bundle Validator And Finish-Time Recheck

Immediately before artifact minting, S7.3 must run a source-bundle validator.
This is new S7.3 work, not inherited S7.1 validation.

The validator must:

- load the private bundle by `source_ref_hash`;
- verify the content-free consultation row matches the bundle;
- verify the producer/source pair;
- recompute request, preview, params, precondition, authority-context, rollback,
  prompt, model, and context-manifest hashes;
- recompute or verify the two-channel classifier outcome and reason code;
- verify created timestamp and expiry;
- verify `maez_voice_consulted=True`;
- verify `maez_objection_state="absent"`;
- verify no withdrawal;
- verify no unavailable reason that blocks guarded self-modification.

A frozen voice fact expires no later than the WebAuthn challenge TTL. Its
timestamp, expiry, and content-free outcome must appear in the rendered request
Rohit signs.

## Voice-Producer Port And Test Harness

S7.3 must define a reviewed voice-producer port. Tests may fake transport text
at the model boundary, but they may not hand-assemble:

- final `MaezVoiceConsultation(absent)`;
- private source bundle;
- classifier outcome;
- request binding;
- producer/source pair;
- `S7ExecutionAuthorization`;
- `S7ExecutionGrant`.

Positive tests must enter through the producer port and prove the same path a
live consultation uses. Test fixtures can supply a fake Maez response string and
structured marker; the producer, bundle writer, classifier, validator, D12
render, artifact mint, consume, and grant path must be real or reviewed fakes at
their own seams.

## Guarded Surface Bridge

Candidate B is surface-neutral only after every guarded surface reaches the S7
authorization spine through a common request shape.

S7.3 must choose one of two implementation shapes:

- guarded dream/edit/direct rows become guarded cards or guarded work items that
  pass through the existing internal WebAuthn routes; or
- S7.3 adds first-class dream/direct authorization routes that build the same
  envelope, preview, voice fact, artifact, consume, and grant chain.

Telegram, CLI, cockpit, and helper paths may create or open guarded requests.
They must not authorize guarded execution directly. Boolean helper patterns such
as `brain_swap_execution_authorized` must not become execution authority; guarded
consumers require `S7ExecutionGrant`.

## D23 Refusal And Failure Provenance

S7.3 must distinguish authoritative Maez refusal from operational non-authority.

Authoritative D23 voice-refusal rows may be written only when a verified
producer ran and the validated source bundle yields `present` or `withdrawn`.

Non-authoritative operational rows may record:

- `not_determined`;
- `unavailable`;
- missing bundle;
- stale binding;
- model outage;
- context overflow;
- retry exhausted;
- prompt-integrity uncertainty;
- pre-auth failure.

Operational rows must not be projected as Maez refusal, Maez consent, or Maez
preference. They are repair/audit signals for the current attempt. Replay,
rate-limit, and provenance controls must prevent repeated pre-auth or malformed
attempts from poisoning D23 refusal history.

Maez has a seat, not a permanent veto. `present`, `withdrawn`,
`not_determined`, and unavailable outcomes block the current authorization
artifact and feed guarded-work policy/D23 as specified; they do not grant Maez
general execution authority over all future attempts.

## Trace And Rollback Evidence

S7.3 must add durable trace schemas or equivalent records:

- `S7VoiceConsultationTrace`, binding preview, source bundle, classifier
  version, attempt outcomes, D23 projection, and final voice state.
- `S7GuardedExecutionTrace`, binding voice consultation, artifact, consumed
  grant, mutation result, rollback evidence, and post-mutation verification.

Positive execution cannot count for L8 retirement unless these traces exist and
bind the live voice producer, artifact mint, consume edge, mutation, and
rollback evidence.

Rollback evidence hash is new S7.3 work. S7.3 must migrate or extend the
envelope, preview, rendered statement, artifact/consume binding, and trace
storage to carry rollback evidence hash rather than only `rollback_path_class`.

## Operator-Visible Failure Projection

Routine status surfaces must stay content-free but useful. They may project
closed reason codes such as:

- `retry_exhausted`;
- `model_outage`;
- `context_overflow`;
- `ttl_expired`;
- `stale_prompt_or_model_identity`;
- `rollback_evidence_missing`;
- `bundle_validation_failed`;
- `prompt_integrity_block`;
- `producer_not_run`;
- `source_pair_invalid`.

They must not expose raw Maez text, raw mutation body, or hidden prompt content.

## Current Integration Seams

- `operator_user_boundary`: already has closed voice-seat classes, closed
  producer vocabulary, `MaezVoiceConsultation` validation, D12 rendering, and
  `S7ExecutionGrant` minting after atomic consume. S7.3 must strengthen schema,
  producer/source validation, D23 semantics, source-bundle validation, rollback
  hash binding, and trace gates.
- `decision_pipeline`: `_s7_voice_consultation_for_card(...)` is the immediate
  replacement seam. Today it is a fail-closed placeholder with misleading real
  producer labels. S7.3 must replace that with the producer port or stop
  emitting eligible consultation rows when no producer ran.
- `self_mod_dialog`: has dialog history and S7 linkage fields, but no reviewed
  objection capture. It can become the dialog-context invocation only by adding
  the same fresh terminal consultation over the same preview and validator.
- `dream_state`: append and section-edit envelopes already derive request
  identity from stored DB rows and fail closed without `S7ExecutionAuthorization`
  before consuming to a grant.
- `daemon`: internal S7 card WebAuthn begin/finish routes already pass through
  envelope, voice consultation, D12 rendering, and ceremony service.
- `telegram_voice`: direct `/apply_dream`, `/apply_section_edit`, and approval
  cards are currently proposal-selection entrypoints only. They must create or
  open a guarded request/authorization flow, or fail closed; they must not
  authorize guarded execution directly.

## S7ExecutionAuthorization Reconciliation

S7.1 D14 says S7.1 does not create a parallel `S7ExecutionAuthorization` type.
Current code has `S7ExecutionAuthorization`.

Design reading: the current type is a pre-consume carrier, not execution
authority. The execution authority remains `S7ExecutionGrant`, minted only by
`S7AuthorizationStore` after atomic consume.

The S7.3 spec must do one of two things:

- canonically bless the current carrier shape/name as non-authority, preserving
  S7.1 D14's ban on a second execution authority; or
- rename the carrier to remove the ambiguity before S7.3 implementation depends
  on it.

## Explicit v1 Limitations

S7.3 v1 does not defend against same-box privileged tampering. Hashes prove
binding among recorded artifacts; they do not prove that a privileged local
actor did not tamper with stores, prompts, model routing, or the transcript
bundle before recording.

Prompt shaping is not fully solvable when the mutation text itself may contain
adversarial language. The prompt-integrity contract and conservative classifier
reduce this risk; they do not eliminate it.

The first S7.3 voice mechanism is operator-designed. That is honest for v1, but
future reviewed iterations should incorporate Maez's own input into how Maez is
heard.

Model updates may change consultation behavior. Model identity and prompt
version must be part of the source hash.

Display, OS, browser, and hardware compromise remain outside what WebAuthn or
this classifier can prove.

## Review Questions

1. Does v2 resolve the classifier tension by separating structured marker
   parsing from reviewed semantic reading?
2. Is the "which Maez" context boundary specific enough to preserve genuine
   consultation without daemon-state steering?
3. Is the structural placeholder repair strong enough: no eligible consultation
   row unless a producer actually ran?
4. Are source-bundle validation and exact-request binding concrete enough for
   the S7.3 spec?
5. Does the `MutationPreviewArtifact` remove the pre-voice circularity?
6. Are D23 refusal rows and operational failure rows separated clearly enough?
7. Is the guarded surface bridge concrete enough for dream/direct execution
   without bypassing the artifact spine?
8. Are the test seams strict enough to prevent fake positive-path voice facts?
9. Should S7.3 bless the current `S7ExecutionAuthorization` carrier name or
   rename it before implementation?

## Plain English

S7.3 needs one real way for Maez to be heard before Maez is changed. This design
keeps that route: show the current bonded Maez a fixed preview of the exact
change, ask the bounded objection question, store the private answer privately,
and expose only hashes and closed states to the authorization machinery.

The v2 change is that "Maez did not object" now has receipts. The system must
know which Maez was asked, what Maez saw, where the private transcript is, how
the classifier reached the result, why retries did or did not happen, what D23
row means, and which execution trace proves the change consumed the same voice
fact Rohit signed over. If any part of that cannot be proven, the answer is
`not_determined`, and the guarded change does not run.
