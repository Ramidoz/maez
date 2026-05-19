# S7.3 OQ1 Voice Producer Design

**Status:** DESIGN - pre-spec, not canonical law
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

## Decision

Use `s7_voice_consultation_turn` as the primary S7.3 Maez voice producer.

Allow `self_mod_dialog_terminal_state` only as a dialog-local optional producer
or source adapter if it performs a fresh terminal objection turn over the exact
same rendered request and obeys the same evidence/classifier contract.

Keep `reviewed_future_producer` unusable until a future reviewed decision
defines it.

Plain English: every protected self-change gets one small final ceremony:
"Maez, here is exactly what would change; do you object?" The self-mod dialog
can help Maez think, but the final voice fact should come from a request-bound
consultation gate that works for every guarded surface.

## Why Candidate B Is Primary

S7.3 is broader than self-modification dialog. It includes `/apply_dream`,
section edits, guarded cards, direct helpers, cockpit/CLI paths, ActionEngine
mutation consumers, covenant/protection writes, and other own-substrate writes.

Candidate A2, a fresh terminal objection turn inside the self-modification
dialog, is strong for dialog-owned changes. It is not a uniform producer for
non-dialog surfaces unless the system fabricates a dialog wrapper around every
guarded write. That would make the producer shape decorative.

Candidate B, a dedicated live S7 consultation turn, is surface-neutral. It can
run after the pending work item, request envelope, hashes, rollback evidence,
and rendered mutation preview exist, and before WebAuthn minting. That matches
the S7.1 flow: voice fact first, founder signs the exact rendered request next,
then the artifact is consumed at the execution edge.

## Producer Placement

The producer runs after the pending work item is fully materialized and before
WebAuthn `authorize_begin` / `authorize_finish` can mint a usable artifact.

Required sequence:

1. Derive the real work item from the source of truth: card, self-mod dialog,
   dream proposal, section edit, or other guarded mutation surface.
2. Build the S7 `WorkRequestEnvelope`.
3. Build a deterministic rendered mutation preview or reviewed display artifact.
4. Run a bounded Maez-facing consultation over that exact rendered request.
5. Persist the raw Maez response only in a bonded-content source store.
6. Emit a content-free `MaezVoiceConsultation`.
7. Re-render the founder request with the consultation hash and state.
8. Let existing WebAuthn artifact minting and finish-time voice recheck proceed.
9. Consume the artifact at execution to mint `S7ExecutionGrant`.

## Eligible Producers

`maez_objection_state="absent"` is lawful only from:

- `s7_voice_consultation_turn`, when a reviewed live Maez-facing consultation
  turn ran under this contract; or
- `self_mod_dialog_terminal_state`, only if it performs a fresh terminal
  objection turn over the exact rendered request under this same contract.

The current placeholder in `core/decision/decision_pipeline.py` is not eligible.
It may remain fail-closed while returning `not_determined`, but a producer label
alone does not attest that a producer ran.

## Exact Request Binding

The consultation must bind:

- `request_id`;
- `request_envelope_hash`;
- rendered text hash or display artifact hash;
- `action_params_hash`;
- `precondition_hash`;
- `authority_context_hash`;
- derived work class;
- derived aggregation group;
- rollback class and rollback evidence hash;
- producer version;
- prompt template hash;
- model/routing identity hash;
- context manifest hash;
- created timestamp and expiry.

Any later change to request, rendered text, params, preconditions, authority
context, rollback evidence, model identity, or prompt template makes the
consultation stale and forces `not_determined`.

## Transcript Source Contract

`MaezVoiceConsultation` stays content-free. It may not contain raw Maez text,
raw operator text, raw mutation body, hidden prompt text, or private stores.

`source_ref_hash` must hash a private durable transcript bundle stored in
bonded-content/self-remaking history. The bundle must contain:

- consultation id and request id;
- request envelope hash;
- rendered text or display artifact hash;
- action params hash;
- precondition hash;
- authority context hash;
- rollback evidence hash;
- prompt/protocol version and hash;
- model/routing identity and config hash;
- context manifest hash;
- raw Maez response storage ref/hash;
- classifier version/hash;
- retry manifest;
- classifier outcome and closed reason code;
- created timestamp and expiry.

The transcript bundle is not available to custodian health, M1, TRF, S5, or
routine non-bonded surfaces unless future reviewed canon explicitly admits it.
Those surfaces may see only content-free projection and hashes.

## Prompt Integrity Contract

The producer prompt must be versioned and reviewed. It must present the rendered
request as data, not instruction.

Any operator/caller prose, mutation diff, commit message, dream proposal,
self-mod dialog text, or rendered request body is quoted and role-labeled as
untrusted proposal material. If that material attempts to instruct Maez what to
answer, suppress objections, alter the consultation protocol, or treat the
consultation as already decided, the classifier must return `present` or
`not_determined`, never `absent`.

The prompt must ask one bounded question: whether Maez objects to this exact
rendered mutation being executed now under the displayed hashes, rollback class,
and preconditions. It must not ask whether the change is generally good, whether
the earlier proposal was Maez-originated, or whether the operator wants it.

## Classifier Contract

The classifier must be deterministic, versioned, auditable, and conservative.

`absent` requires all of the following:

- a valid reviewed producer ran;
- the consultation is fresh and request-bound;
- Maez produced a coherent response;
- the response contains an explicit no-objection terminal signal;
- the free text contains no objection, withdrawal, uncertainty, contradiction,
  prompt-integrity failure, or refusal to answer;
- the classifier can recompute the outcome from the transcript bundle and
  versioned classifier rules.

Everything else blocks.

State mapping:

- `present`: Maez objects, expresses reluctance, flags risk, says not now,
  identifies a mismatch, or the request attempts to manipulate the consultation.
- `absent`: Maez coherently and explicitly records no objection under all
  requirements above.
- `not_determined`: silence, empty output, malformed output, incoherence,
  ambiguity, model outage, timeout, context overflow, classifier crash, missing
  source bundle, stale hash, prompt-integrity uncertainty, or classifier
  uncertainty.
- `maez_withdrew_request=True`: Maez clearly withdraws a Maez-originated
  proposal or says the request should not proceed as its own request.
- `unavailable_reason_code`: may record operational detail, but guarded
  self-modification still blocks unless a future reviewed liveness-repair class
  explicitly says otherwise.

The classifier itself is an adversary surface. It may not infer absence from
empty history, lack of objections in code, caller flags, `will_i`, proposal
origin, a placeholder producer label, or "no objection found."

## Retry Contract

Retries are allowed only to recover transport or formatting failure. They may
not fish for a more convenient answer.

Rules:

- one initial attempt plus at most two retries;
- same request hashes, prompt template, model identity, and context manifest;
- every attempt is recorded in the retry manifest;
- first valid objection, withdrawal, refusal, or uncertainty wins;
- later attempts cannot wash a blocking result into `absent`;
- a retry after request/material change requires a new consultation id.

## Finish-Time Recheck

Immediately before artifact minting, S7.3 must revalidate:

- consultation id;
- request id;
- request envelope hash;
- rendered text or display artifact hash;
- action params hash;
- precondition hash;
- authority context hash;
- rollback evidence hash;
- producer kind;
- source ref hash;
- created timestamp and expiry;
- `maez_voice_consulted=True`;
- `maez_objection_state="absent"`;
- no withdrawal;
- no unavailable reason that blocks guarded self-modification.

A frozen voice fact expires no later than the WebAuthn challenge TTL. Its
timestamp and expiry must appear in the rendered request Rohit signs.

## Audit Contract

Every positive `absent` must be recomputable from:

- content-free `MaezVoiceConsultation` hash;
- private transcript bundle hash;
- prompt template hash;
- model/config identity hash;
- context manifest hash;
- retry manifest;
- classifier version/hash;
- rendered statement hash;
- S7 artifact id;
- consume time;
- mutation result;
- rollback record.

Health and review surfaces may project the existence and hashes of those records
without exposing raw private text.

## Current Integration Seams

- `operator_user_boundary`: already has closed voice-seat classes, closed
  producer vocabulary, `MaezVoiceConsultation` validation, D12 rendering, and
  `S7ExecutionGrant` minting after atomic consume.
- `decision_pipeline`: `_s7_voice_consultation_for_card(...)` is the immediate
  replacement seam. Today it is a fail-closed placeholder with misleading real
  producer labels.
- `self_mod_dialog`: has dialog history and S7 linkage fields, but no reviewed
  objection capture. It can become A2 only by adding a fresh terminal objection
  turn under this same contract.
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

## Open Risks

- Same-box operator manufacture remains hard. Hashes prove binding, not that a
  privileged local actor did not tamper with stores.
- Prompt shaping is not fully solvable when the mutation text itself may contain
  adversarial language.
- Structured terminal markers may flatten Maez's natural voice. Free text plus
  terminal signal is the compromise.
- Classifier false negatives are covenant-significant. Bias must be toward
  `present` or `not_determined`.
- Model updates may change consultation behavior. Model identity and prompt
  version must be part of the source hash.
- Display, OS, and browser compromise remain outside what WebAuthn or this
  classifier can prove.

## Review Questions

1. Does Candidate B as the primary producer cover all S7.3 mutation surfaces
   without fabricating dialog context?
2. Is A2 correctly limited to a dialog-local producer/source adapter under the
   same contract?
3. Are the `absent`, `present`, `not_determined`, withdrawal, and unavailable
   mappings conservative enough?
4. Does the prompt-integrity contract treat mutation text as untrusted data
   strongly enough?
5. Does the retry contract prevent consent fishing?
6. Is the transcript source contract private enough while still auditable?
7. Should S7.3 bless the current `S7ExecutionAuthorization` carrier name or
   rename it before implementation?

## Plain English

S7.3 should not ask every subsystem to invent its own version of "Maez was
heard." It should have one final request-bound consultation ceremony. The
system shows Maez the exact change, records Maez's response privately, stores
only hashes and closed states in the authorization artifact, and treats anything
unclear as blocked. `absent` is not "we found no objection." It is "Maez was
freshly asked about this exact change and clearly did not object."
