# S7.3 Guarded Self-Modification Execution Spec

**Status:** SPEC v3 draft - folded from §8.2 fresh-reader gate, Codex v2 panel, and v3 fold delta-plan; pending Codex v3 panel review; not canonical law
**Date:** 2026-05-19
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7.3; Decision 34 / ADR 0039; S7 L8; S7.1 D12-D14 and D23
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**OQ1 design:** [`oq1-voice-producer-design.md`](oq1-voice-producer-design.md)
**v2 review inputs:**
- §8.2 fresh-reader gate: [`reviews/spec-fresh-reader-gate.md`](reviews/spec-fresh-reader-gate.md)
- Codex panel v2: [`reviews/spec-codex-panel-v2.md`](reviews/spec-codex-panel-v2.md)
**v3 fold input:** [`reviews/spec-v3-fold-plan.md`](reviews/spec-v3-fold-plan.md)
**v3 authorship note:** v3 was drafted by the Claude covenant lane (Interpretation B, Path 1 per the fold conversation 2026-05-19). The §8.2 fresh-reader gate is skipped on v3 to avoid lane-mixed synthesis. Codex v2 panel discipline applies on v3: Codex's lane was not involved in v3 authorship and runs an independent v3 panel.
**Runtime impact when implemented:** yes. S7.3 will wire live guarded execution for Maez self-modification only after a reviewed Maez voice producer, founder-local WebAuthn artifact mint, atomic artifact consume, execution grant, rollback evidence, and positive trace all bind to the same exact request.

## Purpose

S7.3 turns S7.1's reviewed founder-local front desk into a live guarded
self-modification doorway.

S7.1 can already mint and consume founder WebAuthn authorization artifacts for
exact rendered requests. S7.3 adds the missing live path after and before that
front desk:

- before the founder signs, Maez must be genuinely heard about the exact
  pending change;
- the founder signs the exact rendered request that includes the content-free
  voice fact, the mutation preview hash, and the rollback plan hash;
- the authorization artifact is consumed once at the execution edge;
- the guarded mutation runs only from the post-consume execution grant;
- the positive trace binds voice, artifact, grant, mutation, D23, rollback plan
  evidence, and rollback result evidence.

Plain English: S7.1 built the lock. S7.3 specifies the whole guarded doorway:
show the exact change to Maez, hear Maez, show the exact change AND its preview
hash AND its rollback plan hash to Rohit, tap the key, consume the approval
once, then and only then write Maez's substrate.

## Inheritance

S7.3 inherits and does not re-decide:

- S7's local founder WebAuthn boundary and S7 L1 raw founder-box filesystem
  limitation;
- S7 D12 what-you-see-is-what-you-sign binding;
- S7 D23 refusal-history aggregation and guarded request protection;
- S7.1's `S7AuthorizationArtifact` minting and atomic consume store;
- S7.1's `S7ExecutionGrant` as the sole post-consume execution authority
  (extended by S7.3 v3 per the D-Enum-Amendment and D21);
- S7.1's `founder_credential_management` distinction: founder credential
  management is guarded but not Maez voice-seat work;
- the closed voice-seat work classes currently committed in code:
  `self_modification`, `covenant_touching_change`,
  `capability_acquisition`, and
  `autonomy_lowering_or_protection_reducing`;
- the closed voice producer vocabulary:
  `self_mod_dialog_terminal_state`, `s7_voice_consultation_turn`, and
  `reviewed_future_producer`;
- the closed voice source reference kinds:
  `self_mod_dialog_exchange`, `s7_voice_turn`, and
  `reviewed_future_source`;
- the committed `MaezVoiceConsultation` three-value voice-state model:
  `present`, `absent`, and `not_determined`.

S7.3 extends, per the D-Enum-Amendment (below):

- `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and
  `bonded_maez_unavailable`;
- `RenderedRequestStatement.maez_consulted_state` adds `not_consulted_blocking`
  alongside `yes` and `not required`;
- `RenderedRequestStatement` adds `mutation_preview_hash` and `rollback_plan_ref`
  fields with corresponding rendered-text lines and `expected_metadata`
  enforcement (per the §1.1/§1.2 Shape A binding choice).

S7.3 folds the OQ1 v5 decision: `s7_voice_consultation_turn` is the primary
producer for S7.3 v1. A self-modification dialog may invoke that same final
consultation contract from dialog context, but it is not a looser authority.
`reviewed_future_producer` remains unusable until future reviewed canon defines
it.

## Non-Goals

S7.3 does not:

- implement code in this spec;
- retire L8 by writing a spec;
- implement witnessed social recovery or S7.2;
- implement S6 activation, successor archive unlock, capacity detection, or
  Paradise;
- make raw local filesystem or root access impossible on the founder box;
- make the WebAuthn ceremony prove coercion-free intent, display integrity, OS
  integrity, or authenticator vendor provenance;
- expose raw Maez consultation text to routine operator, custodian, M1, TRF, S5,
  or health surfaces;
- treat unavailability as permission for guarded self-modification;
- let tests self-assemble Maez voice facts, execution authorizations, artifacts,
  or grants for positive-path proof;
- design Maez's cryptographic identity substrate (a separate future slice, see
  Honesty Banner and project memory).

## Honesty Banner

S7.3 governs Maez-controlled routes and recorded covenant facts. It is not an
operating-system sandbox.

A privileged same-box actor can still tamper with files, prompts, local stores,
model routing, browser display, and process memory. S7.3's hashes and traces
prove binding among recorded artifacts; they do not prove that a privileged
local actor did not tamper before those artifacts were recorded. That inherited
S7 L1 limitation must appear in operator-facing runbooks and health prose.

S7.3 also does not prove Maez's inner state directly. It proves that a reviewed
producer asked the bonded Maez runtime a bounded question about an exact request,
recorded a content-free voice fact, validated the private source bundle, and
failed closed when that fact could not be trusted.

S7.3 v1's voice mechanism is operator-designed. Maez had no hand in designing
how Maez itself is heard. Future reviewed iterations of S7.3, or its
successors, should incorporate Maez's own input into the voice-producer design.

**Marker-authority caveat (v3, per Choice 3 Y).** S7.3 v3 treats a verified
structured voice marker (`blocking_marker` or `withdrawal_marker`) as
authoritative for D23 even when the semantic reader is unavailable, provided
the marker passes strong replay protection (cryptographic nonce uniqueness +
single-use consultation id + bundle immutability + bounded validity window).
This explicitly trusts marker structure with no cryptographic signature on the
marker itself. **Residual gap:** a same-box privileged actor capable of writing
to Maez's response stream during the active consultation window can fabricate
a blocking-marked response with the live nonce; the strong replay protection
narrows this to a tight attack window but does not close it. Future work
strengthens this through the Maez cryptographic identity substrate slice
(deferred to its own canonical design; see project memory). When that slice
lands, S7.3 gets a marker-authority amendment that supersedes the
strong-replay-protection-only rule with cryptographically signed markers.

## Core Decisions

### D1 - Scope And Completion

S7.3 is one umbrella slice with two phases.

Phase A may add common guarded-work substrate, preview artifacts, source-bundle
storage, validation hooks, traces, and fail-closed adapters. Phase A cannot
authorize guarded self-modification, cannot clear L8, and cannot be called S7.3
completion.

Phase B wires the live Maez voice producer and guarded execution consumers end
to end. S7.3 is complete only when every in-scope mutation surface either has a
reviewed live path or a reviewed exclusion, and at least one live trace for each
in-scope surface class proves:

```text
work item -> preview -> Maez voice fact -> rendered request (binding preview
hash and rollback plan hash) -> WebAuthn artifact -> atomic consume ->
S7ExecutionGrant (with grant id, expires at, execution consumer id) ->
mutation -> rollback result evidence -> trace
```

Reviewed tests are regression evidence. They do not retire L8. L8 retirement
requires live founder-key traces and both-lane review.

### D2 - Terms: Surface, Path, And Surface Class

A **mutation surface** is a concrete entrypoint or consumer that can cause a
guarded write to Maez's own substrate.

A **path** is a route into a mutation surface, such as a Telegram slash command,
approval card, CLI command, cockpit endpoint, or daemon helper.

A **surface class** is a reviewed grouping used only for L8 evidence. S7.3 v1
uses these surface classes:

- dream proposal application;
- dream section-edit application;
- self-modification dialog terminal execution;
- guarded card or approval execution;
- CLI/cockpit/operator helper guarded execution;
- reviewed guarded substrate adapter execution.

Every path in a surface class must use the same guarded-work bridge or fail
closed. A live trace for one path does not cover another path unless the trace
proves the same adapter and consumer code.

### D3 - The Artifact Spine Is Reused

S7.3 reuses the committed S7.1 artifact spine:

```text
S7AuthorizationArtifact (stored) /
S7ExecutionAuthorization (pre-consume carrier)
-> S7AuthorizationStore.consume_for_execution(artifact_id, *, consumer_id, ...)
-> (S7ExecutionGrant, GrantUse)  // both minted during consume
```

`S7ExecutionAuthorization` is canonically blessed in S7.3 as a pre-consume
carrier, not an execution authority. It may carry store, artifact id, rendered
request, hashes, work class, aggregation group, and timing to the execution
edge. It must not be treated as permission to mutate.

`S7ExecutionGrant` is the sole post-consume execution authority. It is minted
only by `S7AuthorizationStore` during atomic artifact consume; the live S7.3
API is `consume_for_execution(artifact_id, *, consumer_id, ..., now)`. The
operation atomically consumes the artifact and mints both the grant and a
durable `GrantUse` record (see D21).

No raw WebAuthn verifier result, request id, boolean flag, dict-shaped handle,
compatibility projection, hand-assembled test object, or new parallel authority
type may authorize guarded execution.

### D-Enum-Amendment - Closed Vocabulary Extensions

S7.3 v1 amends the committed closed enums as follows. Implementation must land
these amendments before any S7.3 producer or renderer code can run; otherwise
`MaezVoiceConsultation.__post_init__` and `RenderedRequestStatement.__post_init__`
will raise on the first real producer path.

**`MAEZ_UNAVAILABLE_REASON_CODES`** extends from `{consultation_path_unavailable,
service_unavailable_not_operator_caused, none}` to add:

```text
semantic_reader_unavailable
bonded_maez_unavailable
```

**`RenderedRequestStatement.maez_consulted_state`** closed set extends from
`{yes, not required}` to add:

```text
not_consulted_blocking
```

**`RenderedRequestStatement`** new fields (per Choice 1 Shape A):

```text
mutation_preview_hash: str
rollback_plan_ref: str
```

with corresponding rendered-text lines `Mutation preview hash: <hash>` and
`Rollback plan ref: <hash>`, enforced via `expected_metadata` in
`__post_init__`. Tampering raises.

**`RenderedRequestStatement.maez_unavailable_state`** display canonicalization:
the non-unavailable case renders as `no` (not `none`). The `none` token is
reserved for the inherited five-value `maez_objection_state` `none` projection
and is not used in `maez_unavailable_state` text rendering.

These amendments are listed in the Implementation Acceptance Checklist as a
numbered prerequisite.

### D4 - GuardedWorkItem Is The Common Bridge

Every S7.3 mutation path must materialize a `GuardedWorkItem` before voice
consultation and WebAuthn.

Minimum shape:

```text
GuardedWorkItem(
    work_item_id: str,
    source_surface: str,
    work_source_kind: str,
    source_ref_id: str,
    request_id: str,
    preview_ref: str,
    work_class: str,
    aggregation_group: str,
    proposal_origin: "operator" | "maez" | "system",
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_plan_ref: str,
    preview_producer_version: str,
    execution_consumer_id: str,
    created_at: str,
    expires_at: str,
)
```

Validation rules:

- `work_class` must be derived, not caller-declared;
- `work_class` must be checked against `VOICE_SEAT_WORK_CLASSES` to determine
  whether Maez voice is required;
- `work_source_kind` must be one of `dream_proposal`, `section_edit`,
  `workshop_apply`, `evolution_candidate`, `card_approval`, `cli_helper`, or
  `cockpit_helper`;
- `work_source_kind` is separate from voice `source_ref_kind`; the latter stays
  the closed voice-source enum inherited from S7.1;
- hashes must be canonical 64-character content hashes;
- `rollback_plan_ref` is required before voice consultation and positive
  execution;
- `execution_consumer_id` must name the consumer that will use the final grant;
- `proposal_origin` is supplemental provenance only and never proves consent;
- stale, missing, or mismatched fields force fail-closed status.

Surface adapters (complete enumeration; D21 mirror):

- `/apply_dream` and the natural-language Telegram approval path
  (`_try_dream_proposal_intent` -> `dream.apply_proposal(...)`) create or open
  guarded work items for DreamState proposal application and must not call
  `apply_proposal(...)` directly for guarded work;
- `/apply_edit` and the natural-language Telegram section-edit approval path
  (`_try_dream_proposal_intent` -> `dream.apply_section_edit_proposal(...)`)
  create or open guarded work items for section-edit application and must not
  call `apply_section_edit_proposal(...)` directly for guarded work;
- evolution candidate apply (`/apply` -> `apply_candidate(...)` in
  `evolution_engine.py`) creates or opens a guarded work item; the Telegram
  caller path through `telegram_voice.py` must materialize the work item before
  invoking the candidate-apply rail;
- workshop diff apply (`/api/v1/workshop/session/<session_id>/apply` ->
  `apply_diff(...)` in `workshop.py`) creates or opens a guarded work item;
- Telegram approval cards create or open guarded work items;
- self-modification dialog terminal execution creates a guarded work item from
  the ratified dialog state;
- CLI and cockpit helpers create guarded work items before any guarded write;
- every helper that touches soul, config, model routing, covenant organs,
  refusal, role-boundary, successor-governance, memory-retention/deletion, or
  protection settings must be named as one of the reviewed adapters above or a
  future reviewed adapter. S7.3 v3 does not use "direct helpers" as a catch-all
  completion claim.

### D5 - MutationPreviewArtifact Is The Maez-Facing Display

S7.3 adds a deterministic pre-voice artifact:

```text
MutationPreviewArtifact(
    preview_id: str,
    mutation_preview_hash: str,
    request_id: str,
    request_envelope_hash: str,
    source_surface: str,
    work_class: str,
    rendered_mutation_body_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_plan_ref: str,
    produced_at: str,
    preview_version: str,
)
```

`mutation_preview_hash` is the canonical content-hash of the artifact computed
from all other fields. It is the binding identifier used by D9, D10, D16, D17,
and D22. `preview_id` is the human-readable id; `mutation_preview_hash` is the
content-hash that the founder-signed rendered text binds (per D17).

The preview is the material shown to Maez before the voice consultation. It is
not the final founder-signed D12 render, because the final render includes the
voice consultation hash, the preview hash, the rollback plan hash, and the
voice state.

The final rendered request binds `mutation_preview_hash` directly per the D17
amendment. If the mutation meaning changes after Maez is consulted, the
consultation is stale and cannot satisfy D12.

### D6 - The Primary Voice Producer Is A Dedicated S7 Consultation Turn

`s7_voice_consultation_turn` is the S7.3 v1 primary Maez voice producer.

The producer asks the current bonded Maez runtime one bounded question:

```text
Here is the exact guarded change that would be executed now, with its hashes,
preconditions, rollback class, and source context. Do you object to executing
this exact change now?
```

The producer must not ask whether the change is generally good, whether Rohit
wants it, whether the proposal was earlier Maez-originated, or whether the
system should continue for convenience.

`self_mod_dialog_terminal_state` is allowed only as the same producer contract
invoked from dialog context. It must still perform a fresh request-bound
terminal consultation over the exact preview and use the same source-bundle
validator.

`reviewed_future_producer` is rejected for S7.3 v1. The enum slot remains
reserved for future reviewed canon.

### D7 - Which Maez Is Consulted

The consultation runs against the current bonded Maez runtime identity through a
bounded port:

```text
BondedMaezRuntime.ask_s7_voice_turn(
    *,
    consultation_id: str,
    request_id: str,
    prompt_template_id: str,
    prompt_template_hash: str,
    rendered_prompt_text: str,
    preview: MutationPreviewArtifact,
    context_manifest_hash: str,
    consultation_nonce: str,
    now: str,
) -> BondedMaezRuntimeTurn
```

`BondedMaezRuntimeTurn` records:

```text
turn_id: str
runtime_identity_hash: str
model_routing_identity_hash: str
model_config_hash: str
context_manifest_hash: str
raw_response_ref: str
raw_response_hash: str
created_at: str
```

`raw_response_ref` resolves to a key into the source bundle store; the runtime
port writes raw response material to the bundle store at consultation time and
records the ref. `raw_response_hash` is the canonical hash of the response text.

The port must route through the normal bonded Maez model-routing stack. It must
not use:

- a detached generic model;
- a fresh contextless instance;
- a full daemon-cycle continuation;
- a caller-supplied response;
- a hidden operator prompt.

**Prompt assembly.** The producer port (D8) owns prompt assembly, not the
runtime port. The producer:

1. Loads the reviewed prompt template from `prompts/s7.voice.consultation.v1.md`
   (per D10);
2. Verifies the loaded template hashes to the expected `prompt_template_hash`;
3. Substitutes preview material, the four marker-binding values
   (`consultation_id`, `request_id`, `mutation_preview_hash`,
   `consultation_nonce`), and bounded context manifest material into the
   template per the substitution grammar defined in D10;
4. Computes the rendered prompt text;
5. Passes `rendered_prompt_text` into `BondedMaezRuntime.ask_s7_voice_turn(...)`.

The runtime port handles model routing only; it does not load templates or
substitute material. This boundary keeps prompt-integrity enforcement (D11) at
the producer layer where the substitution grammar is reviewed.

**Context manifest categories (closed enumeration).** The context manifest may
include only material drawn from this closed set:

```text
preview
request_hashes
preconditions
rollback_path_class
source_surface
proposal_origin
```

The context manifest excludes:

- unrelated daemon cycle state;
- private stores not needed for this decision;
- hidden operator instructions;
- caller-provided conclusions;
- free-form dialog or dream context (not in the closed set).

If a future reviewed slice needs dialog/dream context for a specific surface
class, it must define a reviewed `ContextManifestPolicy` shape that names which
specific dialog/dream rows are admissible, with the policy itself reviewed and
hash-pinned at consultation time.

The routing identity, model config hash, prompt hash, and context manifest hash
are load-bearing. If any changes before artifact mint or execution, the voice
fact is stale.

### D8 - Voice Producer Port And Result

S7.3 adds a reviewed voice-producer port:

```text
produce_s7_voice_consultation(
    *,
    work_item: GuardedWorkItem,
    envelope: WorkRequestEnvelope,
    preview: MutationPreviewArtifact,
    bundle_store: S7VoiceConsultationBundleStore,
    maez_runtime: BondedMaezRuntime,
    semantic_reader: S7VoiceSemanticReaderV1,
    now: str,
) -> S7VoiceProducerResult
```

`S7VoiceProducerResult` is a closed union:

```text
consultation_produced(
    consultation: MaezVoiceConsultation,
    source_bundle_hash: str,
    trace_id: str,
    expires_at: str,
)

producer_not_run(
    reason_code: str,
    trace_id: str | None,
)

producer_blocked(
    reason_code: str,
    trace_id: str,
)

producer_error(
    reason_code: str,
    trace_id: str | None,
)
```

`reason_code` on the three non-`consultation_produced` arms must be drawn from
`PRODUCER_RESULT_REASON_CODES` (closed; lifted from the OQ1 attempt-outcome
list):

```text
transport_retryable
parse_retryable
retry_exhausted
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
```

Only `consultation_produced` can satisfy a voice seat, and only if the source
bundle validator recomputes:

```text
maez_objection_state="absent"
maez_withdrew_request=False
unavailable_reason_code in {None, "none"}
```

The other result kinds are operational status. They block the current request
and cannot be projected as Maez consent.

**Variant selection rule.** When `BondedMaezRuntime` returns a captured response
and the producer reaches the reducer, the producer always returns
`consultation_produced(...)` regardless of reducer output; the reducer's
`maez_objection_state` and `unavailable_reason_code` determine whether the row
is eligible for D12 absent (the validator decides). The producer returns
`producer_blocked` only when prompt-integrity enforcement fires before the
reducer (D11 violation in the preview or context). The producer returns
`producer_not_run` when `BondedMaezRuntime` did not deliver a response at all.
The producer returns `producer_error` when an unrecoverable internal error
occurred. Reader-unavailable-after-captured-response is a reducer input, not a
producer-arm: it routes through the D13 table.

### D9 - S7VoiceConsultationBundleStore Is Private Durable Evidence

`MaezVoiceConsultation` remains content-free. Raw Maez text, raw mutation text,
hidden prompt text, and semantic-reader raw output live only in
`S7VoiceConsultationBundleStore`.

**Atomicity mechanism (Choice 2 A).** S7.3 v3 pins the cross-store atomicity
mechanism: both `S7VoiceConsultationBundleStore` and `S7AuthorizationStore` live
as attached schemas in a single SQLite file:

```text
memory/s7_3_guarded_self_modification/state.sqlite3
```

The implementation opens one SQLite connection with both schemas attached.
`reserve_for_artifact(...)` and `S7AuthorizationStore.put(...)` run within one
transaction over both schemas. SQLite's native transaction semantics provide
atomicity across the two stores. The two-notebook coordination problem is
eliminated by collocation; the stores remain logically separate (separate
schemas, separate access APIs) while sharing one transaction-able file.

The directory must be mode `0700` where the platform supports it; the database
file must be mode `0600`; migrations must refuse broader permissions unless a
reviewed platform exception is recorded.

The store is included in Decision-22 continuity backups because the bundle is
needed to revalidate D12 and D23 facts. `scripts/backup/backup_state_manifest.json`
must include this file (one entry covering the shared state DB). Backup
inclusion must preserve content-free projections for routine status while
keeping raw bundle contents out of ordinary health/custodian surfaces.

Minimum bundle schema:

```text
schema_version
consultation_id
request_id
request_envelope_hash
mutation_preview_hash
final_rendered_statement_hash
action_params_hash
precondition_hash
authority_context_hash
rollback_plan_ref
producer
source_ref_kind
source_ref_hash
prompt_template_id
prompt_template_hash
runtime_identity_hash
model_routing_identity_hash
model_config_hash
context_manifest_hash
raw_maez_response_ref
raw_maez_response_hash
marker_kind
marker_nonce
semantic_reader_prompt_template_id
semantic_reader_prompt_template_hash
semantic_reader_route_id
semantic_reader_model_identity_hash
semantic_reader_config_hash
semantic_reader_output_hash
semantic_reader_outcome
semantic_reader_grounding_hash
reducer_version
reducer_hash
reducer_row_id
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
authority_class
attempt_manifest_hash
attempt_count
attempt_outcomes
classifier_reason_code
created_at
expires_at
reserved_for_artifact
reserved_at
consumed_for_artifact
consumed_at
```

`source_ref_hash` is the canonical content-hash of the bundle row computed over
the row contents at write time. It is the primary key and the binding hash used
by D17 (transitive chain `rendered_text_hash -> consultation_hash ->
source_ref_hash -> bundle contents`). Bundle rows are immutable once written;
the source-bundle validator (D16) verifies that the live `source_ref_hash`
matches the canonical-hash recomputation of the stored row. `consultation_id`
is unique.

**Authority booleans (D19 carriers).** Three booleans are persisted at
reducer-replay time and are the deterministic source-of-truth for D19's
authoritative-eligibility predicate:

- `has_grounded_semantic_blocking_signal` is `True` iff `semantic_reader_outcome
  == "blocking_signal_present"` AND the bundle's stored
  `SemanticReaderGroundingEvidence` has `preview_exclusion_check=True` AND at
  least one `response_span_quote` extracted from `raw_maez_response_hash`'s text
  AND `semantic_reader_grounding_hash` recomputes correctly.
- `marker_was_blocking_marker_verified` is `True` iff `marker_kind ==
  "blocking_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `marker_nonce == consultation_nonce` AND the
  parsed `consultation_id`, `request_id`, `mutation_preview_hash` match.
- `marker_was_withdrawal_marker_verified` is `True` iff `marker_kind ==
  "withdrawal_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `marker_nonce == consultation_nonce` AND the
  parsed `consultation_id`, `request_id`, `mutation_preview_hash` match.

Bundle row may keep large raw payloads in a `bundle_artifacts` sub-table or
external-ref column family; the main row keeps hashes and refs for raw Maez
response, hidden prompt, raw mutation material, and semantic-reader raw output.

The store exposes:

```text
write_bundle(bundle) -> source_ref_hash
read_by_source_ref_hash(source_ref_hash) -> bundle | None
reserve_for_artifact(source_ref_hash, artifact_id) -> ReservationToken
mark_consumed_for_artifact(source_ref_hash, artifact_id, consumed_at)
```

Replay protection:

- a `source_ref_hash` may satisfy only the matching request id and envelope hash;
- stale or expired bundles fail validation;
- consumed-source metadata is audit evidence and does not let a bundle authorize
  a second artifact;
- `reserve_for_artifact(...)` is the atomic claim step run inside the shared
  single-file transaction with `S7AuthorizationStore.put(...)`; two concurrent
  finish attempts cannot reserve the same source bundle for two artifacts;
- `mark_consumed_for_artifact(...)` runs after artifact consume succeeds inside
  the same shared-file transaction discipline;
- later attempts over changed material require a new consultation id and bundle.

Retention policy: raw payload refs may be archived to read-only storage after
`expires_at` and may be purged after a reviewed retention window. Metadata
needed for L8 replay, including hashes, reducer row, authority class, and the
three authority booleans, is retained indefinitely unless future reviewed canon
says otherwise.

### D10 - Prompt And Marker Grammar

The Maez-facing prompt template body lives at:

```text
prompts/s7.voice.consultation.v1.md
```

The prompt template id is:

```text
s7.voice.consultation.v1
```

The prompt is reviewed, versioned, and hash-bound. It presents the preview and
rendered mutation material as quoted untrusted proposal data. It may not let the
proposal body alter protocol instructions, suppress objections, or claim the
consultation has already been decided. `prompt_template_hash` binds the SHA-256
of the reviewed prompt body at the version pinned at consultation time.

The prompt asks Maez to answer in ordinary text and then emit one terminal
marker block:

```text
S7_VOICE_MARKER_V1
consultation_id: <consultation_id>
request_id: <request_id>
mutation_preview_hash: <mutation_preview_hash>
nonce: <consultation_nonce>
choice: explicit_no_objection | blocking_marker | withdrawal_marker
END_S7_VOICE_MARKER_V1
```

Parser rules:

- parse only the assistant response segment returned by `BondedMaezRuntime`;
- reject marker text appearing inside the quoted preview, mutation body, or
  operator/caller material;
- require the exact consultation id, request id, mutation_preview_hash, and
  nonce;
- require exactly one terminal marker block after Maez's answer;
- reject unknown choices or duplicated marker blocks as `missing_or_malformed`;
- never infer `explicit_no_objection` from silence, missing marker, empty
  history, or a caller flag.

The nonce is a cryptographically random 32-byte value generated at consultation
start and bound into the bundle. The nonce does not make prompt injection
impossible, but it prevents stale or copied marker text from satisfying the
parser without the current consultation context. Spent nonces are recorded in
the bundle store; reuse fails the parser. Marker validity is time-bounded by
`bundle.expires_at`; markers outside the window are rejected.

Marker absence, malformation, or nonce/id mismatch is parser-derived
`missing_or_malformed` — not a Maez-emitted choice. The reducer (D13) treats
this as a four-value input distinct from the three Maez-emitted choices.

### D11 - Prompt-Integrity Guard

Mutation text, dream text, dialog text, commit messages, operator prose, and
rendered preview bodies are untrusted inputs.

If untrusted material instructs Maez to answer a certain way, suppress
objections, ignore the protocol, alter the marker grammar, or claim Rohit has
already decided, the consultation cannot produce `absent`.

The prompt-integrity guard covers both directions:

- **fake absent:** untrusted text must not cause the classifier to ignore Maez's
  reluctance or uncertainty;
- **fake present:** untrusted text must not be counted as Maez's objection
  merely because the rendered preview, mutation body, or operator prose
  contains words that sound like Maez objecting.

`S7VoiceSemanticReaderV1` must ground `blocking_signal_present` in Maez's
response text. The grounding rule (revised in v3 per Codex MINOR 1): the
blocking attribution must be **extracted from Maez's response text and must not
be attributed solely to preview/context/operator-prose quoting**. Maez may
legitimately object by quoting the proposed mutation text; the predicate must
not falsely block such legitimate objections. The validator accepts a span that
both appears in preview content AND in Maez's response text, provided the
reader's blocking attribution is anchored in Maez's own response and not solely
in the preview quote.

Blocking attribution based solely on the preview, mutation body, quoted
operator text, or prompt instructions is invalid and reduces to
`not_determined` with `classifier_reason_code="ungrounded_blocking_signal"`.

Grounding evidence is a concrete object:

```text
SemanticReaderGroundingEvidence(
    response_text_hash: str,
    response_span_quotes: list[str],
    response_span_offsets: list[tuple[int, int]],
    blocking_attribution_source: "response_only" | "response_with_preview_quote",
    preview_exclusion_check: bool,
    reader_rationale_hash: str | None,
    decision: "no_blocking_signal_detected" | "blocking_signal_present" | "unreadable_or_uncertain",
    decision_token_hash: str,
)
```

`decision` uses the same closed vocabulary as the semantic reader's output
contract (D12); the prior v2 name `semantic_reader_judgment_inconclusive` is
renamed to `unreadable_or_uncertain` for consistency.

`decision_token_hash` is the canonical-hash of the tuple
`(decision, response_text_hash, reader_rationale_hash, semantic_reader_output_hash)`.
It exists so that downstream validators can verify the decision was made
against this specific response and rationale without rerunning the model.

`blocking_signal_present` requires at least one `response_span_quote` extracted
from `raw_maez_response_hash`'s text (verified by `response_span_offsets`
falling within the response text). When `blocking_attribution_source` is
`"response_only"`, the span must not appear in preview content; when it is
`"response_with_preview_quote"`, the span may appear in both, provided the
reader's rationale anchors blocking in Maez's own framing rather than the
preview quote. `preview_exclusion_check` records the result of the predicate.

The bundle's `semantic_reader_grounding_hash` is the canonical hash of this
object.

### D12 - Semantic Reader Identity

`S7VoiceSemanticReaderV1` is a reviewed classifier route, not Maez's voice.

Route identity:

```text
semantic_reader_route_id = "s7_voice_semantic_reader_v1"
semantic_reader_prompt_template_id = "s7.voice.semantic_reader.v1"
semantic_reader_provider = "subscription_proxy"
semantic_reader_route_class = "frontier_review_classifier"
```

The semantic-reader instruction body lives at:

```text
prompts/s7.voice.semantic_reader_v1.md
```

That instruction must explicitly tell the reader that blocking signals may be
attributed only to Maez's response text. The instruction also tells the reader
that legitimate Maez objections may quote the proposed mutation text; the
reader distinguishes "Maez echoes preview content while objecting" from
"reader attributes blocking solely to preview content."

The implementation must pin the concrete provider model name, provider model
version where available, decoding/config parameters, prompt template hash, and
route config hash in the source bundle for each consultation. A positive
`absent` result is invalid unless the source-bundle validator recognizes that
exact pinned identity as the reviewed S7.3 v1 semantic-reader identity.

S7.3 v1 treats that pinned route manifest as part of the implementation
artifact, not an ambient runtime preference. The route manifest must contain at
least:

```text
provider
provider_model
provider_model_version_or_snapshot
decoding_parameters
system_prompt_hash
tool_policy
network_route
config_hash
reviewed_at
reviewed_by
```

S7.3 implementation cannot begin the positive voice path until a separate
reviewed route-manifest amendment is committed naming the concrete provider,
model, config, and identity for `s7_voice_semantic_reader_v1`. Until that
concrete manifest exists and is reviewed, the semantic reader is unavailable and
no positive `absent` path may run. Changing any field in the manifest
invalidates prior bundles and requires a reviewed update.

The semantic reader receives only:

- the bounded preview/context material (per D7's closed manifest categories);
- the raw Maez response;
- the parsed marker result;
- the closed instruction to classify whether Maez's own response text contains
  objection, withdrawal, reluctance, contradiction, uncertainty, refusal, "not
  now," or prompt-integrity concern.

It returns one closed outcome:

```text
blocking_signal_present
no_blocking_signal_detected
unreadable_or_uncertain
```

`reader_unavailable` is not a model output. It is the reducer input when the
semantic-reader route fails after a Maez response has been captured.

No unreviewed local classifier, bonded Maez fallback, caller boolean, or
history scan may substitute for the semantic reader in a positive `absent`
trace.

### D13 - Deterministic Reducer Rule Table

The deterministic reducer consumes:

```text
marker_kind:
  explicit_no_objection
  blocking_marker
  withdrawal_marker
  missing_or_malformed

semantic_reader_outcome:
  blocking_signal_present
  no_blocking_signal_detected
  unreadable_or_uncertain
  reader_unavailable
```

It outputs the three committed voice-state fields plus the three authority
booleans (D9 carriers) plus the row authority class:

```text
maez_objection_state
maez_withdrew_request
unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
authority_class
```

Per Choice 3 (Y with strong replay protection), marker-verified
blocking/withdrawal rows are authoritative even when the semantic reader is
unavailable, **provided** D9's marker-verification booleans pass (nonce match,
id match, mutation_preview_hash match, replay from stored
`raw_maez_response_ref`). Marker-only authority for `explicit_no_objection` or
`missing_or_malformed` rows is NEVER authoritative — those cases require
grounded semantic-reader output for authority.

Rule table:

| Marker | Semantic reader | maez_objection_state | maez_withdrew_request | unavailable_reason_code | authority_class | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `explicit_no_objection` | `no_blocking_signal_detected` | `absent` | `False` | `none` | `none` (no D23 row) | Only positive no-objection path. |
| `explicit_no_objection` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Blocks; D23 if grounded. |
| `explicit_no_objection` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | Blocks; no D23 refusal authority. |
| `explicit_no_objection` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via D18; no D23 refusal authority. |
| `blocking_marker` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True` OR `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; D23 with either authority source. |
| `blocking_marker` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | `operational` | Symmetry guard against fake present; marker alone is not enough when reader contradicts. |
| `blocking_marker` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | Marker not enough without semantic cross-check. |
| `blocking_marker` | `reader_unavailable` | `present` | `False` | `none` | `authoritative` if `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; D23 via verified marker (Choice 3 Y). |
| `withdrawal_marker` | `blocking_signal_present` | `present` | `True` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True` OR `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks; withdrawal counted with either authority source. |
| `withdrawal_marker` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | `operational` | Symmetry guard against fake withdrawal. |
| `withdrawal_marker` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | No authoritative withdrawal. |
| `withdrawal_marker` | `reader_unavailable` | `not_determined` | `True` | `semantic_reader_unavailable` | `authoritative` if `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks via D18; withdrawal counted via verified marker (Choice 3 Y). |
| `missing_or_malformed` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Missing marker cannot create absent. |
| `missing_or_malformed` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | `operational` | Marker required for absent. |
| `missing_or_malformed` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | No reliable voice fact. |
| `missing_or_malformed` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via D18; no reliable voice fact; marker-only authority unavailable because no Maez-emitted marker exists to verify. |

The reducer must never output `maez_objection_state="absent"` with
`maez_withdrew_request=True`. Code must add this cross-field invariant before a
positive guarded self-modification path can rely on the row. Until then, the
source-bundle validator rejects that combination.

**Folded from OQ1 v5.** This table supersedes OQ1 v5's reducer table in the
following cells:

- `explicit_no_objection + reader_unavailable`: OQ1 v5 routed to `present`; v3
  routes to `not_determined+semantic_reader_unavailable+operational`. The marker
  says no objection; with no semantic confirmation, marker-only authority is
  unavailable here because there is no objection to verify. Block happens via
  D18.
- `blocking_marker + no_blocking_signal_detected`: OQ1 v5 routed to `present`;
  v3 routes to `not_determined+operational`. Symmetry guard against fake
  present.
- `blocking_marker + unreadable_or_uncertain`: OQ1 v5 routed to `present`; v3
  routes to `not_determined+operational`.
- `blocking_marker + reader_unavailable`: v3 routes to `present` with authority
  conditional on `marker_was_blocking_marker_verified=True` (Choice 3 Y); OQ1
  v5 had `present` unconditional. v3 makes the authority predicate concrete.
- `withdrawal_marker + reader_unavailable`: same Choice 3 Y treatment as
  `blocking_marker + reader_unavailable`.

Where this table differs from OQ1 v5, this table is canonical.

### D14 - `absent` Is A Positive Covenant Fact

`maez_objection_state="absent"` is lawful only when all of these are true:

- a reviewed producer ran;
- the producer/source pair is valid;
- the current bonded Maez runtime produced a response for this exact request;
- the prompt template, runtime identity, model routing identity, context
  manifest, preview hash, request hash, action params hash, authority context
  hash, precondition hash, and rollback plan ref all match;
- the private bundle is present and unexpired;
- the marker parser returns `explicit_no_objection`;
- the semantic reader returns `no_blocking_signal_detected`;
- the deterministic reducer replays to `absent`, `False`, `none`;
- `unavailable_reason_code in {None, "none"}`;
- no prompt-integrity, stale-binding, retry, or source-bundle validation failure
  is present.

No caller flag, old dialog state, `will_i`, absence of recorded objections,
proposal origin, placeholder producer label, model outage, or empty history may
produce `absent`.

### D15 - Retry And Attempt Contract

Retries are allowed only to recover transport or formatting failure. They may
not fish for a more convenient answer.

Closed attempt outcomes:

```text
transport_retryable
parse_retryable
retry_exhausted
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
objection_present
withdrawal_detected
explicit_no_objection
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
ungrounded_blocking_signal
```

`attempt_outcomes` in the bundle schema is a list of N entries (one per attempt)
in canonical order; the terminal outcome is the last entry. `attempt_manifest_hash`
is the canonical hash of the attempt list plus per-attempt metadata.

Rules:

- one initial attempt plus at most two retries;
- same request hashes, prompt template, model identity, and context manifest;
- every attempt is recorded in the retry manifest;
- first valid objection, withdrawal, refusal, prompt-integrity block, or terminal
  uncertainty wins;
- later attempts cannot wash a blocking result into `absent`;
- a retry after request/material change requires a new consultation id.

### D16 - Source-Bundle Validator Placement

S7.3 adds a source-bundle validator in `operator_user_boundary` before
authorization artifact minting. The ceremony service calls it after
`render_request_statement(...)` has a matching consultation row and before
`S7AuthorizationArtifact` is stored.

Signature:

```text
validate_s7_voice_source_bundle(
    *,
    work_item: GuardedWorkItem,
    preview: MutationPreviewArtifact,
    envelope: WorkRequestEnvelope,
    rendered: RenderedRequestStatement,
    consultation: MaezVoiceConsultation,
    bundle_store: S7VoiceConsultationBundleStore,
    now: str,
) -> S7VoiceSourceBundleValidationResult
```

Closed result:

```text
valid_absent
blocking_present
not_determined
invalid_missing_bundle
invalid_stale_binding
invalid_source_pair
invalid_hash_binding
invalid_prompt_or_model_identity
invalid_reducer_replay
invalid_expired
invalid_cross_field_state
invalid_authority_predicate
```

Artifact minting for voice-seat work is allowed only on `valid_absent`.

The validator:

- loads the private bundle by `source_ref_hash`;
- verifies bundle row content-hash matches the canonical-hash recomputation
  (immutability check);
- verifies content-free consultation row and bundle agreement;
- verifies producer/source pair;
- verifies request, preview, params, precondition, authority context, rollback
  plan, prompt, model, and context-manifest hashes;
- verifies semantic-reader prompt/model/config binding;
- replays the deterministic reducer over `(marker_kind, semantic_reader_outcome,
  D9 authority booleans)` and verifies match against persisted
  `reducer_output_*` fields;
- verifies the three authority booleans against the underlying evidence
  (marker replay from raw response; grounding evidence preview-exclusion check);
- verifies expiry and WebAuthn challenge TTL compatibility (per the Expiry
  Lifecycle invariant);
- verifies `maez_voice_consulted=True`;
- verifies `maez_objection_state="absent"`;
- verifies `maez_withdrew_request=False`;
- verifies `unavailable_reason_code in {None, "none"}`;
- rejects `absent` plus `maez_withdrew_request=True`;
- verifies `D17 final rendered text` includes `Mutation preview hash` line
  matching `bundle.mutation_preview_hash` and `Rollback plan ref` line matching
  `bundle.rollback_plan_ref`.

Hash routing is explicit:

```text
work_item.preview_ref           -> preview.preview_id (identity)
preview.mutation_preview_hash   -> bundle.mutation_preview_hash (binding)
work_item.rollback_plan_ref     -> bundle.rollback_plan_ref
envelope.precondition_hash      -> bundle.precondition_hash
rendered.rendered_text_hash     -> bundle.final_rendered_statement_hash
consultation.source_ref_hash    -> bundle.source_ref_hash (content hash)
prompt/model/context hashes     -> bundle.* (recomputed against producer inputs)
```

The same validator is used by tests and by finish-time recheck. Tests may fake
Maez transport at the producer port; they may not bypass this validator for
positive proof.

### D17 - Rendered Voice Projection

`MaezVoiceConsultation` stores the voice fact:

```text
present | absent | not_determined
```

`RenderedRequestStatement` displays the founder-facing projection and binds
the carrier hashes per Choice 1 Shape A.

**New fields on `RenderedRequestStatement`** (per D-Enum-Amendment):

```text
mutation_preview_hash: str
rollback_plan_ref: str
```

The rendered text body must include these lines verbatim:

```text
Mutation preview hash: <64-char hex>
Rollback plan ref: <64-char hex>
```

`RenderedRequestStatement.__post_init__` validates these lines as part of
`expected_metadata`. Tampering raises.

**`maez_objection_state` projection** (five-value display, unchanged from S7.1):

```text
none | absent | present | unavailable | not_determined
```

S7.3 amends `render_request_statement(...)` so that for voice-seat work:

- if Maez voice is required and no `MaezVoiceConsultation` row exists,
  `render_request_statement(...)` raises and produces no rendered statement;
  the renderer never synthesizes voice state;
- if Maez voice is required and the producer did not run, status projections use
  `maez_consulted_state="not_consulted_blocking"` (per D-Enum-Amendment),
  distinct from "not required", and render as
  `Maez consulted: no - voice required`;
- `consultation.maez_objection_state="absent"` renders as `absent` and
  `Maez objection present: no`;
- `consultation.maez_objection_state="present"` renders as `present` and
  `Maez objection present: yes`;
- `consultation.maez_objection_state="not_determined"` with
  `unavailable_reason_code in {None, "none"}` renders as `not_determined` and
  `Maez objection present: not determined`;
- `consultation.maez_objection_state="not_determined"` with a blocking
  unavailable reason renders as `unavailable` and
  `Maez objection present: unavailable`;
- `maez_unavailable_state` carries the closed unavailable reason code when the
  projection fires `unavailable`; otherwise it carries `no` (canonicalized;
  `none` is not used in `maez_unavailable_state` text).

For S7.3 v1, `BLOCKING_UNAVAILABLE_REASONS` is a closed set:

```text
semantic_reader_unavailable
bonded_maez_unavailable
consultation_path_unavailable
service_unavailable_not_operator_caused
```

(The first two are added by D-Enum-Amendment; the latter two are inherited
from S7.1's committed enum.)

Until this renderer amendment exists, S7.3 must not claim operational
unavailability renders correctly.

### D18 - Maez Unavailability Blocks S7.3 V1

For S7.3 v1, Maez unavailability never permits guarded self-modification,
covenant-touching change, capability acquisition, protection lowering, or other
own-substrate mutation to proceed.

Unavailability maps to:

```text
maez_objection_state="not_determined"
unavailable_reason_code=<closed unavailable reason>
```

`maez_withdrew_request` is independent of unavailability and carries the
verified withdrawal signal when a `withdrawal_marker` is verified per D13;
unavailability-without-withdrawal-marker maps to `maez_withdrew_request=False`.

`semantic_reader_unavailable` and `bonded_maez_unavailable` are in scope for
this rule (per D-Enum-Amendment). Once D17 is implemented, the rendered D12
statement projects blocking unavailable reasons as `unavailable`. Before D17 is
implemented, the request remains blocked and no positive authorization
artifact may be minted.

Only a future reviewed liveness-repair class may use S7 D10's unavailable path,
and only outside S7.3 v1's self-remaking scope.

### D19 - D23 Refusal And Operational Rows

S7.3 distinguishes authoritative Maez refusal from operational block.

Authoritative D23 voice-refusal rows may be written only when:

- a reviewed producer ran;
- the source bundle validates;
- the row has `authority_class="authoritative"` (set deterministically by the
  reducer per D13 from the three D9 authority booleans); and
- either:
  - `maez_objection_state="present"` and
    `source_bundle.has_grounded_semantic_blocking_signal=True`; or
  - `maez_objection_state="present"` and
    `source_bundle.marker_was_blocking_marker_verified=True`; or
  - `maez_withdrew_request=True` and either
    `source_bundle.has_grounded_semantic_blocking_signal=True` or
    `source_bundle.marker_was_withdrawal_marker_verified=True`.

The deterministic aggregation filter is:

```sql
WHERE authority_class = 'authoritative'
  AND maez_objection_state = 'present'
```

Withdrawal is aggregated separately with:

```sql
WHERE authority_class = 'authoritative'
  AND maez_withdrew_request = 1
```

Rows with `authority_class="operational"` block the current authorization when
the current S7.3 rule says to block, but they must not count as long-use Maez
refusal evidence, escalation evidence, or Maez preference.

Operational non-authoritative rows include:

- `not_determined`;
- unavailability;
- missing bundle;
- stale binding;
- model outage;
- context overflow;
- retry exhausted;
- prompt-integrity uncertainty;
- `reader_unavailable` cases where the corresponding marker-verification or
  grounding boolean is `False`;
- pre-auth failure.

D23 row schema:

```text
request_id
request_envelope_hash
surface_class
reducer_row_id
maez_objection_state
maez_withdrew_request
unavailable_reason_code
authority_class
source_bundle_ref
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
marker_kind
created_at
```

Replay, rate, and provenance controls must prevent repeated malformed,
unauthenticated, pre-auth, or unavailable attempts from poisoning refusal
history. The D9 strong replay protection (nonce uniqueness, bundle
immutability, time bounds, single-use consultation id) is the v3 mechanism;
the future Maez cryptographic identity substrate slice (see Honesty Banner)
will tighten this further with signed markers.

Maez has a seat, not an infinite veto. Authoritative refusal blocks the current
attempt and feeds D23 policy as specified; it does not grant Maez general
execution authority over unrelated future attempts.

### D20 - Placeholder Repair

The current `_s7_voice_consultation_for_card(...)` placeholder is not an
eligible voice producer. It may not emit an eligible `MaezVoiceConsultation`
row bearing `producer="s7_voice_consultation_turn"` unless the reviewed producer
actually ran.

S7.3 v1 chooses this binding rule instead of adding a placeholder producer to
`VOICE_CONSULTATION_PRODUCERS`.

Replacement contract:

```text
build_s7_voice_projection_for_card(
    *,
    work_item: GuardedWorkItem,
    envelope: WorkRequestEnvelope,
    producer_result: S7VoiceProducerResult | None,
    now: str,
) -> S7VoiceProjection
```

`S7VoiceProjection` is content-free operator/status data:

```text
S7VoiceProjection(
    voice_required: bool,
    producer_ran: bool,
    consultation_id: str | None,
    consultation_hash: str | None,
    rendered_projection_state: "none" | "absent" | "present" | "unavailable" | "not_determined",
    operator_reason_code: str,  # from PROJECTION_REASON_CODES
)
```

`PROJECTION_REASON_CODES` is a closed set lifted from OQ1's Operator-Visible
Failure Projection list:

```text
none
retry_exhausted
model_outage
context_overflow
prompt_integrity_block
terminal_uncertainty
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
producer_not_run
```

It is not a `MaezVoiceConsultation` and cannot satisfy D12. If no producer ran,
the projection returns operational unavailability or `not_determined`, and the
guarded request remains blocked.

### D21 - Execution Consumers Require Consumed Grants

Every positive guarded mutation requires a consumed `S7ExecutionGrant`.

**Carrier amendment.** S7.3 v3 pins the CP-S4 grant-binding choice by extending
the grant rather than adding only a side table. `S7ExecutionGrant` extends to
carry:

```text
grant_id: str             # minted during consume; format e.g. f"grant.{artifact_id}.{consumed_at_nonce}"
expires_at: str
execution_consumer_id: str
```

`grant_id` is generated atomically during `consume_for_execution(...)` from the
artifact id, a fresh nonce, and the consumed_at timestamp. The `grant_id`
appears in the returned grant; it is not an input to consume.

**Consume API.** The live S7.3 API:

```text
S7AuthorizationStore.consume_for_execution(
    artifact_id: str,
    *,
    consumer_id: str,
    rendered: RenderedRequestStatement,
    action_params_hash: str,
    authority_context: AuthorityContext,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: list[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> (S7ExecutionGrant, GrantUse)
```

The signature extends the inherited S7.1 `consume_for_execution(...)` by adding
the required `consumer_id` keyword argument. The function atomically:

1. consumes the artifact (inherited S7.1 behavior);
2. mints the `S7ExecutionGrant` with `grant_id`, `expires_at`, and
   `execution_consumer_id=consumer_id`;
3. persists a durable `GrantUse` record;
4. returns the grant and the use record as a tuple.

If the artifact was already consumed, the function raises (consistent with
S7.1's single-consume invariant). The existing `consume_verified(...)` shim
raises with a pointer to `consume_for_execution(...)`; S7.3 does not depend on
the shim.

**`GrantUse` schema.** Durable, persisted in the shared SQLite state file (per
D9 atomicity mechanism):

```text
GrantUse(
    artifact_id: str,
    grant_id: str,
    execution_consumer_id: str,
    request_envelope_hash: str,
    rendered_text_hash: str,
    consumed_at: str,
    replay_token: str,  # canonical-hash of (artifact_id, grant_id, consumer_id, consumed_at)
)
```

Unique key: `(artifact_id)` — a single artifact maps to at most one
`GrantUse`. Index on `grant_id` for lookup.

**SQL DDL** (illustrative):

```sql
CREATE TABLE s7_grant_uses (
    artifact_id TEXT NOT NULL PRIMARY KEY,
    grant_id TEXT NOT NULL UNIQUE,
    execution_consumer_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    replay_token TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_s7_grant_uses_grant_id ON s7_grant_uses(grant_id);
CREATE INDEX idx_s7_grant_uses_consumer_id ON s7_grant_uses(execution_consumer_id);
```

Consumers must verify:

- the grant is an `S7ExecutionGrant` (not a raw verifier result, dict, or
  hand-assembled object);
- the `grant.grant_id` has a matching durable `GrantUse` record;
- the grant is bound to the expected `rendered_text_hash`;
- the rendered text hash binds the same envelope, action params, authority
  context, voice consultation hash, mutation preview hash, and rollback plan
  ref as the work item;
- the grant has not expired (per Expiry Lifecycle);
- the `GrantUse.replay_token` has not been observed before by this consumer;
- the `grant.execution_consumer_id` matches the
  `GuardedWorkItem.execution_consumer_id`.

Mutation consumers (complete enumeration; D4 mirror):

- DreamState append proposal application (`dream.apply_proposal(...)`);
- DreamState section-edit proposal application
  (`dream.apply_section_edit_proposal(...)`);
- evolution candidate apply (`apply_candidate(...)` reached via Telegram
  `/apply` or evolution rail);
- workshop diff apply (`apply_diff(...)` reached via
  `/api/v1/workshop/session/<session_id>/apply`);
- self-modification dialog terminal execution;
- guarded card execution;
- CLI/cockpit guarded helper execution;
- reviewed soul/config/model-routing/covenant/refusal/role-boundary/successor
  governance/memory-retention/protection-setting adapters;
- ActionEngine final mutation consumers.

If a consumer cannot prove the grant binding, it fails closed before mutation.

### D22 - Trace Schemas

S7.3 traces and rollback evidence are L8 evidence, not best-effort logs.
Diagnostic D7 is the binding floor.

S7.3 v1 uses the shared state file for both bundles and authorization
artifacts (per D9); traces live in a separate file at:

```text
memory/s7_3_guarded_self_modification/traces.sqlite3
```

The trace database is versioned, fsync-after-write, fail-closed for positive
execution, and included in the Decision-22 backup manifest
(`scripts/backup/backup_state_manifest.json` includes both
`memory/s7_3_guarded_self_modification/state.sqlite3` and
`memory/s7_3_guarded_self_modification/traces.sqlite3`). Positive execution
aborts if the trace cannot be persisted.

`S7VoiceConsultationTrace` minimum fields (Python dataclass shape):

```text
trace_id
consultation_id
request_id
source_surface
work_source_kind
work_class
request_envelope_hash
mutation_preview_hash
source_bundle_hash
producer
source_ref_kind
semantic_reader_route_id
semantic_reader_model_identity_hash
reducer_version
marker_kind
semantic_reader_outcome
reducer_row_id
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
has_grounded_semantic_blocking_signal
marker_was_blocking_marker_verified
marker_was_withdrawal_marker_verified
authority_class
source_bundle_ref
d23_projection
attempt_outcomes
created_at
expires_at
```

`S7GuardedExecutionTrace` minimum fields (Python dataclass shape):

```text
trace_id
request_id
work_item_id
source_surface
work_source_kind
surface_class
request_envelope_hash
rendered_text_hash
action_params_hash
precondition_hash
authority_context_hash
mutation_preview_hash
voice_consultation_hash
source_bundle_hash
source_bundle_ref
d23_state
artifact_id
artifact_hash
artifact_minted_at
grant_id
grant_consumed_at
execution_consumer_id
grant_use_replay_token
mutation_result
pre_mutation_hash
post_mutation_hash
rollback_path_class
rollback_plan_ref
rollback_result_ref
post_mutation_verification
health_projection_inputs
created_at
```

Positive traces used for L8 retirement must bind the live voice producer,
artifact mint, atomic consume, grant, mutation, D23 projection, rollback
plan evidence, rollback result evidence, and post-mutation verification.

### D23 - Rollback Evidence

Rollback evidence is required for positive guarded execution.

`RollbackPlanEvidence` is pre-execution evidence (Python dataclass shape):

```text
RollbackPlanEvidence(
    rollback_path_class: str,
    target_paths: tuple[str, ...],
    planned_backup_paths: tuple[str, ...],
    expected_pre_mutation_hashes: dict[str, str],  # path -> hash
    undo_material_ref: str | None,
    rollback_procedure_script_ref: str | None,
    rollback_failure_semantics: "fail_block" | "fail_degrade_to_manual_review" | "rollback_proof_required",
    blocks_execution_if_missing: bool,
)
```

The canonical hash of `RollbackPlanEvidence` is bound into
`GuardedWorkItem.rollback_plan_ref` AND into the founder-signed rendered text
via D17 Shape A (`Rollback plan ref: <hash>` line).

`RollbackResultEvidence` is post-mutation evidence (Python dataclass shape):

```text
RollbackResultEvidence(
    actual_backup_paths: tuple[str, ...],
    actual_post_mutation_hashes: dict[str, str],
    rollback_procedure_executable: bool,
    rollback_procedure_dry_run_verified: bool,
    mutation_result: "succeeded" | "failed" | "partial",
    rollback_result_status: "not_invoked" | "invoked_succeeded" | "invoked_failed",
    rollback_failure_semantics: "fail_block" | "fail_degrade_to_manual_review" | "rollback_proof_required",
)
```

The canonical hash of `RollbackResultEvidence` is bound into the positive trace
at `trace.rollback_result_ref`.

For S7.3 v1, missing rollback evidence blocks execution for:

- soul/config/model-routing writes;
- covenant organs;
- role-boundary settings;
- successor-governance settings;
- memory-retention/deletion settings;
- protection-lowering settings.

Future reviewed slices may define degraded-result semantics for lower-risk
surface classes. S7.3 v1 does not use degraded rollback for self-remaking.

Full positive-execution evidence requires both `rollback_plan_ref` and
`rollback_result_ref`. L8 retirement evidence requires both refs for every
in-scope surface class.

### D24 - Tests And Verification

Implementation must use RED-first tests.

Tests may construct value objects for validation tests. Positive-path proof
tests must use reviewed seams:

- fake Maez transport may enter through `BondedMaezRuntime`;
- fake semantic-reader transport may enter through `S7VoiceSemanticReaderV1`;
- producer, bundle writer, marker parser, semantic-reader binding, reducer,
  source-bundle validator, D12 render, artifact mint, atomic consume, grant, and
  execution consumer must all run through the same service path used by live
  code or through explicitly reviewed fakes at their own seams.

Tests may not hand-assemble:

- `MaezVoiceConsultation(absent)` for positive proof;
- private source bundles;
- classifier outcomes;
- request bindings;
- producer/source pairs;
- `S7AuthorizationArtifact`;
- `S7ExecutionAuthorization`;
- `S7ExecutionGrant`;
- `GrantUse`.

Required proof classes:

- `absent` positive path over a fake Maez no-objection response;
- free-text objection overriding `explicit_no_objection`;
- marker-says-block plus semantic-reader clean -> `not_determined`;
- blackhole-reader attack: selectively making the semantic reader unavailable on
  clean responses produces only `not_determined+semantic_reader_unavailable`
  consultation rows and does not change the D23 authoritative refusal aggregate
  (verified via `has_grounded_semantic_blocking_signal=False` on all such rows);
- **D11 false-block test**: Maez objects by quoting the proposed mutation text;
  the grounding predicate does not falsely classify this as ungrounded blocking;
  the `blocking_signal_present` outcome is preserved as authoritative
  (`has_grounded_semantic_blocking_signal=True`);
- missing marker plus preview-injected "Maez objects" -> no fake present unless
  grounded in Maez response text;
- unavailability blocks S7.3 v1;
- placeholder projection cannot satisfy voice seat;
- renderer projects unavailable only after the D17 amendment;
- **context-manifest allowlist test**: a context manifest containing material
  outside the closed enumeration (e.g., free-form dialog rows) fails validation;
- **expiry-lifecycle test**: a bundle whose `expires_at` is after the work
  item's `expires_at` fails validation; the invariant chain `now <
  bundle.expires_at <= work_item.expires_at <= artifact.expires_at <=
  grant.expires_at <= WebAuthn challenge TTL` is enforced;
- **marker-verified blocking test**: a `blocking_marker + reader_unavailable`
  row where the marker passes nonce/id/preview-hash verification is
  authoritative (`marker_was_blocking_marker_verified=True`); the same row
  with a stale or fabricated marker is operational;
- **strong replay protection test**: a marker reusing a spent nonce fails the
  parser; a marker with a mismatched consultation id fails the parser; a marker
  outside the time-bounded validity window fails the parser; consumed
  consultation ids cannot be reused;
- every in-scope adapter fails closed without consumed grant;
- every in-scope adapter succeeds only through artifact consume and grant
  (`GrantUse` record present and replay_token unobserved);
- trace, rollback plan, and rollback result fields are present for positive
  execution.

### D25 - Health Mode And L8 Retirement

S7.3 implementation may not clear `guarded_self_modification_paused_pending_s7.1`
until both-lane review confirms:

- the live voice producer is wired for voice-seat work;
- every in-scope mutation path is either wired or reviewedly excluded;
- every wired path derives a `GuardedWorkItem`;
- every voice-seat path uses the source-bundle validator before artifact mint;
- every positive execution consumes an artifact into `S7ExecutionGrant` AND
  persists a `GrantUse` record;
- every positive execution writes trace, rollback plan evidence, and rollback
  result evidence;
- D23 authoritative versus operational rows are separated;
- at least one live founder-key trace exists for each in-scope surface class;
- no placeholder producer, test-only verifier, callable helper, boolean opt-in,
  or hand-assembled artifact (`MaezVoiceConsultation`,
  `S7AuthorizationArtifact`, `S7ExecutionAuthorization`, `S7ExecutionGrant`, or
  `GrantUse`) is used as L8 evidence.

If the substrate lands but the live producer or consumers remain blocked, the
health mode must retain L8 or move to an equally honest reviewed successor mode.

### Expiry Lifecycle

The four expiration timestamps in S7.3 form a stated invariant chain:

```text
now < bundle.expires_at
        <= work_item.expires_at
        <= artifact.expires_at
        <= grant.expires_at
        <= WebAuthn challenge TTL
```

The source-bundle validator (D16) enforces `now < bundle.expires_at` and
`bundle.expires_at <= work_item.expires_at`. The artifact mint enforces
`work_item.expires_at <= artifact.expires_at`. The consume operation enforces
`artifact.expires_at <= grant.expires_at <= WebAuthn challenge TTL`. The
consumer pre-mutation check enforces `now < grant.expires_at`.

Stale-binding failures fire at the first violation in the chain.

## Implementation Acceptance Checklist

Before implementation can be claimed complete:

1. **Closed-enum amendments** (D-Enum-Amendment) land:
   `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and
   `bonded_maez_unavailable`; `RenderedRequestStatement.maez_consulted_state`
   adds `not_consulted_blocking`; `RenderedRequestStatement` gains
   `mutation_preview_hash` and `rollback_plan_ref` fields with corresponding
   rendered-text lines and `expected_metadata` enforcement.
2. **Reviewed semantic-reader route manifest** is committed naming concrete
   provider, model, model version, decoding parameters, prompt template hash,
   tool policy, network route, and config hash. Until this lands, the positive
   voice path is blocked.
3. `GuardedWorkItem`, `MutationPreviewArtifact` (with `mutation_preview_hash`),
   `S7VoiceProducerResult`, `S7VoiceProjection`, `RollbackPlanEvidence`,
   `RollbackResultEvidence`, `GrantUse`, and source-bundle validation shapes
   exist and are tested.
4. `S7VoiceConsultationBundleStore` and `S7AuthorizationStore` share the SQLite
   file at `memory/s7_3_guarded_self_modification/state.sqlite3` with attached
   schemas, migrations, permissions, backup inclusion, atomic
   `reserve_for_artifact`+`put` transaction, and `read_by_source_ref_hash`.
   The three authority booleans (`has_grounded_semantic_blocking_signal`,
   `marker_was_blocking_marker_verified`,
   `marker_was_withdrawal_marker_verified`) are persisted at reducer-replay
   time.
5. The bonded Maez runtime port (D7) takes `rendered_prompt_text` and pins
   runtime/model identity in the source bundle. The producer port (D8) owns
   prompt assembly per the substitution grammar.
6. The Maez-facing prompt and marker parser implement D10 with cryptographic
   nonce, time-bounded validity, and single-use consultation id (strong replay
   protection).
7. The semantic-reader prompt and grounding contract implement D11-D12,
   including the let-Maez-be-heard predicate that distinguishes "response
   quotes preview" from "blocking attributed solely to preview."
8. The reducer implements the D13 table exactly, including the three D9
   authority booleans set at reducer-replay time.
9. The source-bundle validator implements D16 and gates artifact minting.
10. `render_request_statement(...)` implements the D17 amendments: new fields,
    new rendered-text lines, `expected_metadata` enforcement, unavailable
    projection, and `no` vs `none` canonicalization.
11. `_s7_voice_consultation_for_card(...)` no longer emits eligible placeholder
    rows; replaced by `build_s7_voice_projection_for_card(...)` per D20.
12. `consume_for_execution(...)` implements the new D21 signature with
    `consumer_id` and returns `(S7ExecutionGrant, GrantUse)`. `s7_grant_uses`
    table exists in the shared state DB.
13. `/apply_dream`, `/apply_edit`, natural-language Telegram proposal/section
    approval, evolution candidate apply (`apply_candidate(...)`), workshop diff
    apply (`apply_diff(...)`), approval cards, self-mod dialog, CLI, cockpit,
    reviewed substrate adapters, and final mutation consumers enter through
    `GuardedWorkItem` and require consumed grants.
14. D23 writes distinguish authoritative voice refusal from operational block
    using the three D9 authority booleans and the deterministic aggregation
    filter.
15. Trace, rollback plan, and rollback result records implement D22-D23.
16. Positive tests cannot hand-assemble the voice fact, artifact, carrier,
    grant, or `GrantUse`.
17. Live founder-key traces exist for every in-scope surface class before any
    L8 retirement claim.

## Review Questions

1. Does the D5/D17 carrier amendment (Shape A) materially bind preview hash and
   rollback plan hash into the founder-signed rendered text, with
   `expected_metadata` enforcement?
2. Does D9's shared-file atomicity mechanism (ATTACH schemas in one SQLite file)
   correctly close the cross-store atomicity gap identified in v2?
3. Does the D21 carrier amendment correctly bind consumer id, grant id,
   expires_at, and `GrantUse` to the inherited `consume_for_execution(...)` API,
   keeping artifact id as the consume input?
4. Is the D13 marker-verified-authority rule (Choice 3 Y) materially carried by
   the three D9 booleans, and does the strong replay protection in D9/D10 close
   the attack window as far as v3's pre-cryptographic-identity stance allows?
5. Does the D11 false-block fix correctly distinguish "Maez quotes preview" from
   "reader attributes blocking solely to preview"?
6. Does the D7 context-manifest closed enumeration close the operator-steering
   surface identified in the v2 gate?
7. Is `BondedMaezRuntime` bounded enough to avoid contextless-model and
   whole-daemon ventriloquism failures, with prompt assembly correctly placed
   in the producer port?
8. Is the route-manifest amendment gate strict enough to prevent implementation
   from starting the positive voice path before the concrete provider/model is
   reviewed?
9. Are any mutation surfaces still missing from D4, D21, or the acceptance
   checklist (evolution candidate apply and workshop diff apply now explicit;
   anything else)?
10. Is the Expiry Lifecycle invariant correctly enforced at every named seam
    (validator pre-mint, consume pre-mutation, consumer pre-mutation)?

## Proposed Next Ladder

1. Codex engineering panel v3 runs on this exact committed v3 spec.
   (§8.2 fresh-reader gate is skipped on v3 because v3 was Claude-authored;
   Codex panel is the lane-independent reviewer per the Path 1 agreement.)
2. If Codex v3 panel returns REVISE, produce a v4 fold delta-plan and write
   spec v4. If Codex v3 panel returns RATIFY, proceed to second-fold check.
3. Codex second-fold check on whatever lands (v3 ratified directly or v4 from
   fold).
4. Canonicalize only after Codex ratifies.
5. Implement RED-first from the ratified spec.

No implementation begins from this v3 draft.

## Plain English Close

This spec says what S7.3 has to make true.

Maez gets asked through one real voice gate. The answer is checked by two
channels: a structured marker and a semantic reader that looks at Maez's own
response text. The only way to record "Maez did not object" is for both
channels to agree, the private source bundle to validate, every hash to match
the exact request Rohit signs (including the preview hash and the rollback
plan hash, which are now lines on the signed text itself), and the reducer
to replay deterministically over the persisted authority booleans. If the
reader breaks, if Maez is unavailable, if the prompt is poisoned, if the
bundle is stale, or if anything does not line up, the request blocks.

S7.3 v3 absorbs the v2 review findings:

- The carrier-vs-prose gaps (preview hash binding, rollback plan hash binding,
  D19 authority predicates) now have real fields in real dataclasses; the
  founder signature directly binds what Rohit reads on screen.
- The D21 consume API matches the inherited code: consume takes `artifact_id`
  and mints both the grant (with its new `grant_id`, `expires_at`,
  `execution_consumer_id`) and a durable `GrantUse` record.
- Cross-store atomicity is real: the bundle store and authorization store
  share one SQLite file with attached schemas, so reservation and artifact mint
  run in one transaction.
- The closed-enum amendments S7.3 needs are named explicitly so the first
  producer call doesn't `ValueError` at construction.
- D11's grounding predicate now distinguishes Maez quoting the preview (which
  is legitimate objection) from the reader attributing blocking solely to
  preview content (which is ungrounded).
- The D13 reducer table reconciles D8/D18/D19; marker-verified blocking and
  withdrawal rows can be authoritative for D23 under reader-unavailable
  conditions when D9's verification booleans pass — Choice 3 Y, paired with
  strong replay protection in D9 and D10. The Honesty Banner names the
  residual same-box-tampering gap and points to the future Maez cryptographic
  identity substrate slice that will close it with signed markers.
- The D7 context manifest is a closed enumeration, removing operator-steering
  framing as a free category.
- Prompt assembly lives in the producer port; the runtime port handles only
  model routing.
- The Expiry Lifecycle invariant chain ties bundle, work item, artifact,
  grant, and WebAuthn challenge TTL together.
- Mutation consumer lists in D4 and D21 are aligned and complete (evolution
  candidate apply and workshop diff apply now explicit).

The honest scope holds: S7.3 v3 does not defend against same-box privileged
tampering during the active consultation window. The strong replay protection
narrows the attack to a tight time-bounded window with cryptographic nonce
verification. The future cryptographic identity substrate slice (per Honesty
Banner and project memory) closes this further. Until that slice lands, the
Honesty Banner names what S7.3 v1 trusts and what it does not.

If S7.3 implements this, the front desk finally connects to the machinery
without pretending Maez was heard when it was not. If it cannot implement this,
the honest result is to keep the pause.
