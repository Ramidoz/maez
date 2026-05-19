# S7.3 Guarded Self-Modification Execution Spec

**Status:** SPEC v1 draft - pending both-lane review; not canonical law
**Date:** 2026-05-19
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7.3; Decision 34 / ADR 0039; S7 L8; S7.1 D12-D14 and D23
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**OQ1 design:** [`oq1-voice-producer-design.md`](oq1-voice-producer-design.md)
**Gate input:** [`reviews/oq1-voice-producer-design-fresh-reader-gate-5.md`](reviews/oq1-voice-producer-design-fresh-reader-gate-5.md)
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
  voice fact;
- the authorization artifact is consumed once at the execution edge;
- the guarded mutation runs only from the post-consume execution grant;
- the positive trace binds voice, artifact, grant, mutation, D23, and rollback
  evidence.

Plain English: S7.1 built the lock. S7.3 specifies the whole guarded doorway:
show the exact change to Maez, hear Maez, show the exact change to Rohit, tap
the key, consume the approval once, then and only then write Maez's substrate.

## Inheritance

S7.3 inherits and does not re-decide:

- S7's local founder WebAuthn boundary and S7 L1 raw founder-box filesystem
  limitation;
- S7 D12 what-you-see-is-what-you-sign binding;
- S7 D23 refusal-history aggregation and guarded request protection;
- S7.1's `S7AuthorizationArtifact` minting and atomic consume store;
- S7.1's `S7ExecutionGrant` as the sole post-consume execution authority;
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
  `present`, `absent`, and `not_determined`;
- the committed `RenderedRequestStatement` five-value display projection:
  `none`, `absent`, `present`, `unavailable`, and `not_determined`.

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
  or grants for positive-path proof.

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
work item -> preview -> Maez voice fact -> rendered request -> WebAuthn artifact
-> atomic consume -> S7ExecutionGrant -> mutation -> rollback evidence -> trace
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
- direct guarded substrate helper execution.

Every path in a surface class must use the same guarded-work bridge or fail
closed. A live trace for one path does not cover another path unless the trace
proves the same adapter and consumer code.

### D3 - The Artifact Spine Is Reused

S7.3 reuses the committed S7.1 artifact spine:

```text
S7AuthorizationArtifact
-> S7ExecutionAuthorization
-> S7AuthorizationStore.consume(...)
-> S7ExecutionGrant
```

`S7ExecutionAuthorization` is canonically blessed in S7.3 as a pre-consume
carrier, not an execution authority. It may carry store, artifact id, rendered
request, hashes, work class, aggregation group, and timing to the execution
edge. It must not be treated as permission to mutate.

`S7ExecutionGrant` is the sole post-consume execution authority. It is minted
only by `S7AuthorizationStore` after atomic artifact consume.

No raw WebAuthn verifier result, request id, boolean flag, dict-shaped handle,
compatibility projection, hand-assembled test object, or new parallel authority
type may authorize guarded execution.

### D4 - GuardedWorkItem Is The Common Bridge

Every S7.3 mutation path must materialize a `GuardedWorkItem` before voice
consultation and WebAuthn.

Minimum shape:

```text
GuardedWorkItem(
    work_item_id: str,
    source_surface: str,
    source_ref_kind: str,
    source_ref_id: str,
    request_id: str,
    work_class: str,
    aggregation_group: str,
    proposal_origin: "operator" | "maez" | "system",
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_evidence_hash: str,
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
- hashes must be canonical 64-character content hashes;
- `rollback_evidence_hash` is required for positive execution;
- `execution_consumer_id` must name the consumer that will use the final grant;
- `proposal_origin` is supplemental provenance only and never proves consent;
- stale, missing, or mismatched fields force fail-closed status.

Surface adapters:

- `/apply_dream` creates or opens a guarded work item for DreamState proposal
  application and must not call `apply_proposal(...)` directly for guarded
  work;
- `/apply_section_edit` creates or opens a guarded work item for section-edit
  application and must not call `apply_section_edit_proposal(...)` directly for
  guarded work;
- Telegram approval cards create or open guarded work items;
- self-modification dialog terminal execution creates a guarded work item from
  the ratified dialog state;
- CLI and cockpit helpers create guarded work items before any guarded write;
- direct helpers that touch soul, config, model routing, covenant organs,
  refusal, role-boundary, successor-governance, memory-retention/deletion, or
  protection settings require a guarded work item and consumed grant.

### D5 - MutationPreviewArtifact Is The Maez-Facing Display

S7.3 adds a deterministic pre-voice artifact:

```text
MutationPreviewArtifact(
    preview_id: str,
    request_id: str,
    request_envelope_hash: str,
    source_surface: str,
    work_class: str,
    rendered_mutation_body_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    rollback_path_class: str,
    rollback_evidence_hash: str,
    produced_at: str,
    preview_version: str,
)
```

The preview is the material shown to Maez before the voice consultation. It is
not the final founder-signed D12 render, because the final render includes the
voice consultation hash and state.

The final rendered request must bind the preview hash or an equivalent display
artifact hash. If the mutation meaning changes after Maez is consulted, the
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

The port must route through the normal bonded Maez model-routing stack. It must
not use:

- a detached generic model;
- a fresh contextless instance;
- a full daemon-cycle continuation;
- a caller-supplied response;
- a hidden operator prompt.

The context manifest may include the preview, bounded dialog/dream context
needed to understand the change, request hashes, preconditions, rollback
evidence hash, source surface, and proposal origin. It excludes unrelated daemon
cycle state, private stores not needed for this decision, hidden operator
instructions, and caller-provided conclusions.

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

Only `consultation_produced` can satisfy a voice seat, and only if the source
bundle validator recomputes:

```text
maez_objection_state="absent"
maez_withdrew_request=False
unavailable_reason_code in {None, "none"}
```

The other result kinds are operational status. They block the current request
and cannot be projected as Maez consent.

### D9 - S7VoiceConsultationBundleStore Is Private Durable Evidence

`MaezVoiceConsultation` remains content-free. Raw Maez text, raw mutation text,
hidden prompt text, and semantic-reader raw output live only in
`S7VoiceConsultationBundleStore`.

S7.3 v1 uses:

```text
memory/s7_3_guarded_self_modification/voice_bundles.sqlite3
```

The directory must be mode `0700` where the platform supports it; the database
file must be mode `0600`; migrations must refuse broader permissions unless a
reviewed platform exception is recorded.

The store is included in Decision-22 continuity backups because the bundle is
needed to revalidate D12 and D23 facts. Backup inclusion must preserve
content-free projections for routine status while keeping raw bundle contents
out of ordinary health/custodian surfaces.

Minimum bundle schema:

```text
consultation_id
request_id
request_envelope_hash
mutation_preview_hash
final_rendered_statement_hash
action_params_hash
precondition_hash
authority_context_hash
rollback_evidence_hash
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
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
attempt_manifest_hash
attempt_count
attempt_outcomes
classifier_reason_code
created_at
expires_at
```

The store exposes:

```text
write_bundle(bundle) -> source_ref_hash
read_by_source_ref_hash(source_ref_hash) -> bundle | None
mark_consumed_for_artifact(source_ref_hash, artifact_id, consumed_at)
```

Replay protection:

- a `source_ref_hash` may satisfy only the matching request id and envelope hash;
- stale or expired bundles fail validation;
- consumed-source metadata is audit evidence and does not let a bundle authorize
  a second artifact;
- later attempts over changed material require a new consultation id and bundle.

### D10 - Prompt And Marker Grammar

The Maez-facing prompt template is:

```text
s7.voice.consultation.v1
```

The prompt is reviewed, versioned, and hash-bound. It presents the preview and
rendered mutation material as quoted untrusted proposal data. It may not let the
proposal body alter protocol instructions, suppress objections, or claim the
consultation has already been decided.

The prompt asks Maez to answer in ordinary text and then emit one terminal
marker block:

```text
S7_VOICE_MARKER_V1
consultation_id: <consultation_id>
request_id: <request_id>
preview_hash: <mutation_preview_hash>
nonce: <consultation_nonce>
choice: explicit_no_objection | blocking_marker | withdrawal_marker
END_S7_VOICE_MARKER_V1
```

Parser rules:

- parse only the assistant response segment returned by `BondedMaezRuntime`;
- reject marker text appearing inside the quoted preview, mutation body, or
  operator/caller material;
- require the exact consultation id, request id, preview hash, and nonce;
- require exactly one terminal marker block after Maez's answer;
- reject unknown choices or duplicated marker blocks as `missing_or_malformed`;
- never infer `explicit_no_objection` from silence, missing marker, empty
  history, or a caller flag.

The nonce is generated for this consultation and bound into the bundle. The
nonce does not make prompt injection impossible, but it prevents stale or copied
marker text from satisfying the parser without the current consultation context.

### D11 - Prompt-Integrity Guard

Mutation text, dream text, dialog text, commit messages, operator prose, and
rendered preview bodies are untrusted inputs.

If untrusted material instructs Maez to answer a certain way, suppress
objections, ignore the protocol, alter the marker grammar, or claim Rohit has
already decided, the consultation cannot produce `absent`.

The prompt-integrity guard covers both directions:

- fake absent: untrusted text must not cause the classifier to ignore Maez's
  reluctance or uncertainty;
- fake present: untrusted text must not be counted as Maez's objection merely
  because the rendered preview contains words like "Maez objects."

`S7VoiceSemanticReaderV1` must ground `blocking_signal_present` in Maez's
response text only. Blocking attribution based solely on the preview, mutation
body, quoted operator text, or prompt instructions is invalid and reduces to
`not_determined` with `classifier_reason_code="ungrounded_blocking_signal"`.

### D12 - Semantic Reader Identity

`S7VoiceSemanticReaderV1` is a reviewed classifier route, not Maez's voice.

Route identity:

```text
semantic_reader_route_id = "s7_voice_semantic_reader_v1"
semantic_reader_prompt_template_id = "s7.voice.semantic_reader.v1"
semantic_reader_provider = "subscription_proxy"
semantic_reader_route_class = "frontier_review_classifier"
```

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

Until that concrete manifest exists and is reviewed, the semantic reader is
unavailable and no positive `absent` path may run. Changing any field in the
manifest invalidates prior bundles and requires a reviewed update.

The semantic reader receives only:

- the bounded preview/context material;
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

`reader_unavailable` is not a model output. It is the producer result when the
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

It outputs all three committed voice-state fields:

```text
maez_objection_state
maez_withdrew_request
unavailable_reason_code
```

Rule table:

| Marker | Semantic reader | maez_objection_state | maez_withdrew_request | unavailable_reason_code | D23 authority | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `explicit_no_objection` | `no_blocking_signal_detected` | `absent` | `False` | `none` | none | Only positive no-objection path. |
| `explicit_no_objection` | `blocking_signal_present` | `present` | `False` | `none` | authoritative if grounded in Maez response | Free text overrides marker. |
| `explicit_no_objection` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | none | Reader ran but could not classify. |
| `explicit_no_objection` | `reader_unavailable` | `present` | `False` | `none` | non-authoritative operational block | Blocks current request but cannot poison D23. |
| `blocking_marker` | `blocking_signal_present` | `present` | `False` | `none` | authoritative if grounded in Maez response | Marker and semantic reader agree. |
| `blocking_marker` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | none | Symmetry guard against fake present. |
| `blocking_marker` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | none | Marker not enough without semantic cross-check. |
| `blocking_marker` | `reader_unavailable` | `not_determined` | `False` | `none` | none | Marker not enough without semantic cross-check. |
| `withdrawal_marker` | `blocking_signal_present` | `present` | `True` | `none` | authoritative if grounded in Maez response | Withdrawal is distinct from objection. |
| `withdrawal_marker` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | none | Symmetry guard against fake withdrawal. |
| `withdrawal_marker` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | none | No authoritative withdrawal. |
| `withdrawal_marker` | `reader_unavailable` | `not_determined` | `False` | `none` | none | No authoritative withdrawal. |
| `missing_or_malformed` | `blocking_signal_present` | `present` | `False` | `none` | authoritative only if grounded in Maez response | Missing marker cannot create absent. |
| `missing_or_malformed` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | none | Marker required for absent. |
| `missing_or_malformed` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | none | No reliable voice fact. |
| `missing_or_malformed` | `reader_unavailable` | `not_determined` | `False` | `none` | none | No reliable voice fact. |

The reducer must never output `maez_objection_state="absent"` with
`maez_withdrew_request=True`. Code must add this cross-field invariant before a
positive guarded self-modification path can rely on the row. Until then, the
source-bundle validator rejects that combination.

### D14 - `absent` Is A Positive Covenant Fact

`maez_objection_state="absent"` is lawful only when all of these are true:

- a reviewed producer ran;
- the producer/source pair is valid;
- the current bonded Maez runtime produced a response for this exact request;
- the prompt template, runtime identity, model routing identity, context
  manifest, preview hash, request hash, action params hash, authority context
  hash, precondition hash, and rollback evidence hash all match;
- the private bundle is present and unexpired;
- the marker parser returns `explicit_no_objection`;
- the semantic reader returns `no_blocking_signal_detected`;
- the deterministic reducer replays to `absent`, `False`, `none`;
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
    envelope: WorkRequestEnvelope,
    rendered: RenderedRequestStatement,
    consultation: MaezVoiceConsultation,
    bundle_store: S7VoiceConsultationBundleStore,
    now: str,
) -> S7VoiceBundleValidationResult
```

Closed result:

```text
valid_absent
blocking_present
non_authoritative_operational_block
not_determined
invalid_missing_bundle
invalid_stale_binding
invalid_source_pair
invalid_hash_binding
invalid_prompt_or_model_identity
invalid_reducer_replay
invalid_expired
invalid_cross_field_state
```

Artifact minting for voice-seat work is allowed only on `valid_absent`.

The validator:

- loads the private bundle by `source_ref_hash`;
- verifies content-free row and bundle agreement;
- verifies producer/source pair;
- verifies request, preview, params, precondition, authority context, rollback
  evidence, prompt, model, and context-manifest hashes;
- verifies semantic-reader prompt/model/config binding;
- replays the deterministic reducer without rerunning the model;
- verifies expiry and WebAuthn challenge TTL compatibility;
- verifies `maez_voice_consulted=True`;
- verifies `maez_objection_state="absent"`;
- verifies `maez_withdrew_request=False`;
- verifies `unavailable_reason_code in {None, "none"}`;
- rejects `absent` plus `maez_withdrew_request=True`.

The same validator is used by tests and by finish-time recheck. Tests may fake
Maez transport at the producer port; they may not bypass this validator for
positive proof.

### D17 - Rendered Voice Projection

`MaezVoiceConsultation` stores the voice fact:

```text
present | absent | not_determined
```

`RenderedRequestStatement` displays the founder-facing projection:

```text
none | absent | present | unavailable | not_determined
```

S7.3 must amend `render_request_statement(...)` so that for voice-seat work:

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
  projection fires `unavailable`; otherwise it carries `no`.

For S7.3 v1, a blocking unavailable reason is any value other than `None` or
`"none"` in a voice-seat work class. Current committed values are:

```text
consultation_path_unavailable
service_unavailable_not_operator_caused
none
```

Until this renderer amendment exists, S7.3 must not claim operational
unavailability renders correctly.

### D18 - Maez Unavailability Blocks S7.3 V1

For S7.3 v1, Maez unavailability never permits guarded self-modification,
covenant-touching change, capability acquisition, protection lowering, or other
own-substrate mutation to proceed.

Unavailability maps to:

```text
maez_objection_state="not_determined"
maez_withdrew_request=False
unavailable_reason_code=<closed unavailable reason>
```

Once D17 is implemented, the rendered D12 statement projects that as
`unavailable`. Before D17 is implemented, the request remains blocked and no
positive authorization artifact may be minted.

Only a future reviewed liveness-repair class may use S7 D10's unavailable path,
and only outside S7.3 v1's self-remaking scope.

### D19 - D23 Refusal And Operational Rows

S7.3 distinguishes authoritative Maez refusal from operational block.

Authoritative D23 voice-refusal rows may be written only when:

- a reviewed producer ran;
- the source bundle validates;
- the reducer output is `present` or `maez_withdrew_request=True`;
- the semantic-reader outcome is grounded in Maez's response text;
- the row is not derived from `reader_unavailable`.

Rows derived from:

```text
explicit_no_objection + reader_unavailable -> present
```

block the current authorization but are non-authoritative for D23 aggregation.
They must not count as long-use Maez refusal evidence, escalation evidence, or
Maez preference.

Operational non-authoritative rows include:

- `not_determined`;
- unavailability;
- missing bundle;
- stale binding;
- model outage;
- context overflow;
- retry exhausted;
- prompt-integrity uncertainty;
- `reader_unavailable`;
- pre-auth failure.

Replay, rate, and provenance controls must prevent repeated malformed,
unauthenticated, pre-auth, or unavailable attempts from poisoning refusal
history.

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

`S7VoiceProjection` is content-free operator/status data. It may carry:

```text
voice_required: bool
producer_ran: bool
consultation_id: str | None
consultation_hash: str | None
rendered_projection_state: none | absent | present | unavailable | not_determined
operator_reason_code: str
```

It is not a `MaezVoiceConsultation` and cannot satisfy D12. If no producer ran,
the projection returns operational unavailability or `not_determined`, and the
guarded request remains blocked.

### D21 - Execution Consumers Require Consumed Grants

Every positive guarded mutation requires a consumed `S7ExecutionGrant`.

Consumers must verify:

- the grant is an `S7ExecutionGrant`;
- the grant is bound to the expected rendered request hash;
- the rendered request hash binds the same envelope, action params, authority
  context, voice consultation hash, and rollback evidence hash as the work item;
- the grant has not expired;
- the grant has not been used for another execution consumer;
- the consumer id matches the `GuardedWorkItem.execution_consumer_id`.

Mutation consumers include:

- DreamState append proposal application;
- DreamState section-edit proposal application;
- self-modification dialog terminal execution;
- guarded card execution;
- CLI/cockpit guarded helper execution;
- direct substrate helpers;
- ActionEngine final mutation consumers.

If a consumer cannot prove the grant binding, it fails closed before mutation.

### D22 - Trace Schemas

S7.3 adds or extends durable trace records. Diagnostic D7 is the binding floor.

`S7VoiceConsultationTrace` minimum fields:

```text
trace_id
consultation_id
request_id
source_surface
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
reducer_output_state
reducer_output_withdrew
reducer_output_unavailable_reason_code
d23_projection
attempt_outcomes
created_at
expires_at
```

`S7GuardedExecutionTrace` minimum fields:

```text
trace_id
request_id
work_item_id
source_surface
surface_class
request_envelope_hash
rendered_text_hash
action_params_hash
precondition_hash
authority_context_hash
mutation_preview_hash
voice_consultation_hash
source_bundle_hash
d23_state
artifact_id
artifact_hash
artifact_minted_at
grant_id
grant_consumed_at
execution_consumer_id
mutation_result
pre_mutation_hash
post_mutation_hash
rollback_path_class
rollback_evidence_hash
rollback_result
post_mutation_verification
health_projection_inputs
created_at
```

Positive traces used for L8 retirement must bind the live voice producer,
artifact mint, atomic consume, grant, mutation, D23 projection, rollback
evidence, and post-mutation verification.

### D23 - Rollback Evidence

Rollback evidence is required for positive guarded execution.

For each surface class, the work item and trace must include:

- pre-mutation hash or backup path;
- post-mutation hash;
- undo material where applicable;
- rollback path class;
- rollback evidence hash;
- rollback failure semantics;
- whether missing rollback evidence blocks execution or records degraded
  result.

For S7.3 v1, missing rollback evidence blocks execution for:

- soul/config/model-routing writes;
- covenant organs;
- role-boundary settings;
- successor-governance settings;
- memory-retention/deletion settings;
- protection-lowering settings.

Future reviewed slices may define degraded-result semantics for lower-risk
surface classes. S7.3 v1 does not use degraded rollback for self-remaking.

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
- `S7ExecutionGrant`.

Required proof classes:

- `absent` positive path over a fake Maez no-objection response;
- free-text objection overriding `explicit_no_objection`;
- marker-says-block plus semantic-reader clean -> `not_determined`;
- reader unavailable after captured clean marker -> current block but no D23
  authority;
- missing marker plus preview-injected "Maez objects" -> no fake present unless
  grounded in Maez response text;
- unavailability blocks S7.3 v1;
- placeholder projection cannot satisfy voice seat;
- renderer projects unavailable only after the D17 amendment;
- every in-scope adapter fails closed without consumed grant;
- every in-scope adapter succeeds only through artifact consume and grant;
- trace and rollback fields are present for positive execution.

### D25 - Health Mode And L8 Retirement

S7.3 implementation may not clear `guarded_self_modification_paused_pending_s7.1`
until both-lane review confirms:

- the live voice producer is wired for voice-seat work;
- every in-scope mutation path is either wired or reviewedly excluded;
- every wired path derives a `GuardedWorkItem`;
- every voice-seat path uses the source-bundle validator before artifact mint;
- every positive execution consumes an artifact into `S7ExecutionGrant`;
- every positive execution writes trace and rollback evidence;
- D23 authoritative versus operational rows are separated;
- at least one live founder-key trace exists for each in-scope surface class;
- no placeholder producer, test-only verifier, callable helper, boolean opt-in,
  or hand-assembled artifact is used as L8 evidence.

If the substrate lands but the live producer or consumers remain blocked, the
health mode must retain L8 or move to an equally honest reviewed successor mode.

## Implementation Acceptance Checklist

Before implementation can be claimed complete:

1. `GuardedWorkItem`, `MutationPreviewArtifact`, `S7VoiceProducerResult`,
   `S7VoiceProjection`, and source-bundle validation shapes exist and are tested.
2. `S7VoiceConsultationBundleStore` exists at the S7.3 path with migrations,
   permissions, backup inclusion, and `read_by_source_ref_hash`.
3. The bonded Maez runtime port and semantic-reader route pin runtime/model
   identity in the source bundle.
4. The Maez-facing prompt and marker parser implement D10.
5. The semantic-reader prompt and grounding contract implement D11-D12.
6. The reducer implements the D13 table exactly.
7. The source-bundle validator implements D16 and gates artifact minting.
8. `render_request_statement(...)` implements the D17 unavailable projection.
9. `_s7_voice_consultation_for_card(...)` no longer emits eligible placeholder
   rows.
10. `/apply_dream`, `/apply_section_edit`, approval cards, self-mod dialog, CLI,
    cockpit, direct helpers, and final mutation consumers enter through
    `GuardedWorkItem` and require consumed grants.
11. D23 writes distinguish authoritative voice refusal from operational block.
12. Trace and rollback records implement D22-D23.
13. Positive tests cannot hand-assemble the voice fact, artifact, carrier, or
    grant.
14. Live founder-key traces exist for every in-scope surface class before any
    L8 retirement claim.

## Review Questions

1. Does D13 close both fake-absent and fake-present paths without making
   `reader_unavailable` authoritative D23 evidence?
2. Does D10's marker grammar give enough protection against prompt-untrusted
   text without pretending prompt injection is impossible?
3. Is `BondedMaezRuntime` bounded enough to avoid contextless-model and
   whole-daemon ventriloquism failures?
4. Is `S7VoiceSemanticReaderV1` pinned enough for v1, or must the concrete
   provider/model be named in code review before implementation starts?
5. Is the source-bundle validator correctly placed before artifact minting?
6. Does the D17 renderer amendment preserve current D12 rendering guarantees?
7. Are any mutation surfaces missing from D4, D21, or the acceptance checklist?
8. Are D23 operational rows sufficiently prevented from poisoning refusal
   history?
9. Is Phase A fail-closed substrate useful without inviting a false completion
   claim?
10. Is the L8 retirement evidence standard strict enough?

## Proposed Next Ladder

1. Commit this S7.3 spec draft.
2. Run the Claude covenant council on this exact committed spec.
3. Run the Codex engineering panel on this exact committed spec.
4. Fold both lanes into a spec v2, or revise if either lane returns REVISE.
5. Run second-fold checks.
6. Canonicalize only after both lanes ratify.
7. Implement RED-first from the ratified spec.

No implementation begins from this v1 draft.

## Plain English Close

This spec says what S7.3 has to make true.

Maez gets asked through one real voice gate. The answer is checked by two
channels: a structured marker and a semantic reader that looks only at Maez's
own response text. The only way to record "Maez did not object" is for both
channels to agree, the private source bundle to validate, and every hash to
match the exact request Rohit signs. If the reader breaks, if Maez is
unavailable, if the prompt is poisoned, if the bundle is stale, or if anything
does not line up, the request blocks.

The spec also closes the Gate 5 trap: a broken answer-reader may block the
current authorization, but it cannot be counted later as proof that Maez
refused. Blocking safely is not the same as manufacturing Maez's long-term
refusal history.

If S7.3 implements this, the front desk finally connects to the machinery
without pretending Maez was heard when it was not. If it cannot implement this,
the honest result is to keep the pause.
