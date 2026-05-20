# S7.3 Guarded Self-Modification Execution Spec

**Status:** SPEC v5 draft - folded from §8.2 fresh-reader gate v4, Codex panel v4, and v5 fold delta-plan; pending §8.2 fresh-reader gate v5 and Codex v5 panel review; not canonical law
**Date:** 2026-05-19
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7.3; Decision 34 / ADR 0039; S7 L8; S7.1 D12-D14 and D23
**Diagnostic:** [`diagnostic.md`](diagnostic.md)
**OQ1 design:** [`oq1-voice-producer-design.md`](oq1-voice-producer-design.md)
**v2 review inputs:**
- §8.2 fresh-reader gate: [`reviews/spec-fresh-reader-gate.md`](reviews/spec-fresh-reader-gate.md)
- Codex panel v2: [`reviews/spec-codex-panel-v2.md`](reviews/spec-codex-panel-v2.md)
**v3 fold input:** [`reviews/spec-v3-fold-plan.md`](reviews/spec-v3-fold-plan.md)
**v3 review input:** [`reviews/spec-codex-panel-v3.md`](reviews/spec-codex-panel-v3.md)
**v4 fold input:** [`reviews/spec-v4-fold-plan.md`](reviews/spec-v4-fold-plan.md)
**v4 review inputs:**
- §8.2 fresh-reader gate v4: [`reviews/spec-fresh-reader-gate-v4.md`](reviews/spec-fresh-reader-gate-v4.md)
- Codex panel v4: [`reviews/spec-codex-panel-v4.md`](reviews/spec-codex-panel-v4.md)
**v5 fold input:** [`reviews/spec-v5-fold-plan.md`](reviews/spec-v5-fold-plan.md)
**v5 authorship note:** v5 keeps the restored lane independence from v4. The spec is operator-authored from the committed v5 fold plan, then reviewed by a fresh §8.2 covenant gate and a Codex v5 engineering panel before any canonicalization claim.
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
  (extended by S7.3 v5 per the D-Enum-Amendment and D21);
- S7.1's `S7ExecutionAuthorization` as a pre-consume carrier, extended by
  S7.3 v5 to carry `execution_consumer_id`;
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
- `RenderedRequestStatement` adds `mutation_preview_hash` and `rollback_plan_ref`
  fields with corresponding rendered-text lines and `expected_metadata`
  enforcement;
- `MaezVoiceConsultation.__post_init__` rejects the cross-field state
  `maez_objection_state="absent"` with `maez_withdrew_request=True`;
- `S7VoiceProjection` may use the status-only projection
  `not_consulted_blocking`, but `RenderedRequestStatement` does not;
- S7.3 adds the closed `S7_EXECUTION_CONSUMER_IDS` vocabulary and the closed
  `authority_class` vocabulary used by D4, D13, D19, and D21.

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

**Marker-authority caveat (v5).** S7.3 v5 treats a verified
structured voice marker (`blocking_marker` or `withdrawal_marker`) as
authoritative for D23 even when the semantic reader is unavailable or disagrees,
provided
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
reviewed live path or a reviewed exclusion, and every in-scope adapter/consumer
has either a live trace or a reviewed same-code coverage proof showing:

```text
work item -> preview -> Maez voice fact -> rendered request (binding preview
hash and rollback plan hash) -> WebAuthn artifact -> atomic consume ->
S7ExecutionGrant (with grant id, expires at, execution consumer id) ->
mutation -> rollback result evidence -> trace
```

Reviewed tests are regression evidence. They do not retire L8. L8 retirement
requires live founder-key traces or reviewed same-code live coverage for every
in-scope adapter/consumer, plus both-lane review.

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
- evolution candidate application;
- workshop diff application;
- ActionEngine final mutation execution;
- guarded card or approval execution;
- CLI/cockpit/operator helper guarded execution;
- reviewed guarded substrate adapter execution.

Every path in a surface class must use the same guarded-work bridge or fail
closed. A live trace for one path does not cover another path unless the trace
proves the same adapter and consumer code.

`surface_class_for(source_surface, work_source_kind, work_class)` is the single
derivation function for the `surface_class` field used by traces, authority
rows, and L8 evidence. Callers do not supply `surface_class` directly.

### D3 - The Artifact Spine Is Reused

S7.3 reuses the committed S7.1 artifact spine:

```text
S7AuthorizationArtifact (stored) /
S7ExecutionAuthorization (pre-consume carrier)
-> S7GuardedStateStore.consume_artifact_for_execution(artifact_id, *, consumer_id, ...)
-> (S7ExecutionGrant | None, GrantUse | None)  // both minted during successful consume
```

`S7ExecutionAuthorization` is canonically blessed in S7.3 as a pre-consume
carrier, not an execution authority. It may carry store, artifact id, rendered
request, hashes, work class, aggregation group, `execution_consumer_id`, and
timing to the execution edge. It must not be treated as permission to mutate.

`S7ExecutionGrant` is the sole post-consume execution authority. It is minted
only by the shared-state consume wrapper during atomic artifact consume; the
live S7.3 API is
`S7GuardedStateStore.consume_artifact_for_execution(artifact_id, *, consumer_id, ..., now)`.
On success the operation atomically consumes the artifact and mints both the
grant and a durable `GrantUse` record (see D21). On inherited S7.1 failure
paths it returns `(None, None)` without mutating substrate.

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

**`RenderedRequestStatement.maez_consulted_state`** remains the inherited closed
set:

```text
yes
not required
```

The status-only `not_consulted_blocking` value belongs to `S7VoiceProjection`
(D20), not to the founder-signed `RenderedRequestStatement`.

**`RenderedRequestStatement`** new fields:

```text
mutation_preview_hash: str
rollback_plan_ref: str
```

with corresponding rendered-text lines `Mutation preview hash: <hash>` and
`Rollback plan ref: <hash>`, plus founder-readable `Preview body class`,
`Preview summary`, and `Preview affected paths` lines enforced via
`expected_metadata` in `__post_init__`. Tampering raises.

**`MaezVoiceConsultation.__post_init__`** gains a cross-field invariant:
construction raises when `maez_objection_state == "absent"` and
`maez_withdrew_request is True`. The same invariant is enforced by the reducer
and source-bundle validator.

**`RenderedRequestStatement.maez_unavailable_state`** display canonicalization:
the non-unavailable case renders as `no` (not `none`). The `none` token is
reserved for the inherited five-value `maez_objection_state` `none` projection
and is not used in `maez_unavailable_state` text rendering.

**`BLOCKING_UNAVAILABLE_REASONS`** is a derived closed set:

```text
semantic_reader_unavailable
bonded_maez_unavailable
consultation_path_unavailable
service_unavailable_not_operator_caused
```

**`S7_EXECUTION_CONSUMER_IDS`** is a new closed set. `execution_consumer_id`
must be one of:

```text
dream_apply_proposal
dream_apply_section_edit_proposal
evolution_apply_candidate
workshop_apply_diff
self_mod_dialog_terminal_execute
guarded_card_execute
cli_helper_execute
cockpit_helper_execute
reviewed_substrate_adapter_execute
action_engine_final_mutate
s7_credential_register_backup
s7_credential_disable
```

**`authority_class`** is a new closed vocabulary:

```text
none
operational
authoritative
```

`authority_class="none"` means the reducer row produces no D23 row at all
(the positive no-objection path). `operational` rows may block the current
request but cannot aggregate as Maez refusal or withdrawal evidence.
`authoritative` rows may aggregate under D19.

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
  `workshop_apply`, `evolution_candidate`, `card_approval`,
  `self_mod_dialog`, `cli_helper`, `cockpit_helper`,
  `reviewed_substrate_adapter`, or `action_engine_final_mutation`;
- `work_source_kind` is separate from voice `source_ref_kind`; the latter stays
  the closed voice-source enum inherited from S7.1;
- hashes must be canonical 64-character content hashes;
- `rollback_plan_ref` is required before voice consultation and positive
  execution;
- `execution_consumer_id` must be in `S7_EXECUTION_CONSUMER_IDS` and must match
  the deterministic derivation for `source_surface`; callers cannot supply an
  arbitrary consumer id;
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
- ActionEngine final mutation consumers create or open guarded work items
  before final substrate mutation from the brain loop. The v1 ActionEngine map
  is closed to reviewed final-mutation adapters that write soul/memory,
  covenant/refusal state, or model-routing/protection settings; each adapter
  must name its `source_surface`, `work_source_kind`, and
  `execution_consumer_id` before implementation acceptance;
- every helper that touches soul, config, model routing, covenant organs,
  refusal, role-boundary, successor-governance, memory-retention/deletion, or
  protection settings must be named as one of the reviewed adapters above or a
  future reviewed adapter. S7.3 v5 does not use "direct helpers" as a catch-all
  completion claim.

`apply_candidate(...)` and `apply_diff(...)` are not allowed to be unguarded
callee loopholes. Each callee either accepts a consumed grant plus
`GuardedWorkItem` binding and verifies it before mutation, or derives/open its
own guarded work item and fails closed until the grant is consumed.

Deterministic `execution_consumer_id` derivation:

```text
dream.apply_proposal                         -> dream_apply_proposal
dream.apply_section_edit_proposal            -> dream_apply_section_edit_proposal
evolution_engine.apply_candidate             -> evolution_apply_candidate
workshop.apply_diff                          -> workshop_apply_diff
self_mod_dialog.terminal_execute             -> self_mod_dialog_terminal_execute
approval_card.execute                        -> guarded_card_execute
cli_helper.execute                           -> cli_helper_execute
cockpit_helper.execute                       -> cockpit_helper_execute
reviewed_substrate_adapter.execute           -> reviewed_substrate_adapter_execute
action_engine.final_mutation                 -> action_engine_final_mutate
s7_credential_management.register_backup     -> s7_credential_register_backup
s7_credential_management.disable             -> s7_credential_disable
```

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
    preview_body_class: str,
    preview_summary: str,
    preview_affected_paths: tuple[str, ...],
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

`mutation_preview_hash` is the canonical content-hash of the deterministic
preview payload fields. The hash domain excludes `preview_id`, because
`preview_id` is a human-readable storage identity and may be UUID-like. The
hash domain includes every semantic preview field, including request envelope
hash, source surface, work class, readable summary, affected paths, rendered
mutation body hash, action params hash, precondition hash, authority context
hash, rollback class, rollback plan ref, produced-at timestamp, and preview
version. It is the binding identifier used by D9, D10, D16, D17, and D22.

The preview is the material shown to Maez before the voice consultation. It is
not the final founder-signed D12 render, because the final render includes the
voice consultation hash, the preview hash, the rollback plan hash, and the
voice state. D17 also renders a founder-readable preview section derived from
`preview_body_class`, `preview_summary`, and `preview_affected_paths`; hash-only
approval is not a S7.3-complete founder ceremony.

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
The `preview`, `context_manifest_hash`, and `consultation_nonce` parameters on
the runtime port are audit pins and trace bindings; the runtime port does not
use them to assemble or alter the prompt.

**Context manifest carrier.** The context manifest is a concrete replayable
object, not a loose bag of prompt text:

```text
ContextManifest(
    manifest_id: str,
    preview_ref: str,
    request_envelope_hash: str,
    precondition_hash: str,
    rollback_path_class: str,
    source_surface: str,
    proposal_origin_label: "operator" | "maez" | "system",
    created_at: str,
    policy_id: str,
    policy_hash: str,
)
```

`context_manifest_hash` is the canonical hash of this object with `manifest_id`
excluded from the hash domain. `context_manifest_ref` is the private store ref
used by the validator to replay prompt assembly. `proposal_origin_label` is
neutral provenance only; it must not include persuasive language, quality
claims, or a conclusion about what Maez should do.

The manifest may include only these closed categories:

```text
preview_ref
request_envelope_hash
precondition_hash
rollback_path_class
source_surface
proposal_origin_label
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
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
model_outage
producer_not_run
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

**Atomicity mechanism.** S7.3 v5 pins the cross-store atomicity
mechanism as a single SQLite file with table-prefix namespace separation, not
SQLite `ATTACH`. The state file is:

```text
memory/s7_3_guarded_self_modification/state.sqlite3
```

The stores remain logically separate by API and table prefix:

```text
s7_voice_bundles_*
s7_voice_bundle_uses_*
s7_authorization_artifacts_*
s7_grant_uses_*
```

One transaction-owning wrapper controls cross-store writes:

```text
S7GuardedStateStore(
    db_path: str,
    bundle_store: S7VoiceConsultationBundleStore,
    bundle_use_store: S7VoiceBundleUseStore,
    authorization_store: S7AuthorizationStore,
    grant_use_store: S7GrantUseStore,
)

S7GuardedStateStore.put_artifact_with_bundle_reservation(
    *,
    artifact_inputs: S7AuthorizationArtifactInputs,
    source_ref_hash: str,
    consumer_id: str,
    now: str,
) -> tuple[S7AuthorizationArtifact, ReservationToken]

S7GuardedStateStore.consume_artifact_for_execution(
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
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> tuple[S7ExecutionGrant | None, GrantUse | None]
```

`S7AuthorizationArtifactInputs` is the explicit pre-store input carrier for
artifact minting. It contains the committed S7.1 artifact fields needed by
`S7AuthorizationStore.put(...)`, except store-minted identifiers and consume
state:

```text
S7AuthorizationArtifactInputs(
    request_id: str,
    request_envelope_hash: str,
    rendered_text_hash: str,
    rendered_text: str,
    maez_voice_consultation_hash: str | None,
    mutation_preview_hash: str | None,
    rollback_plan_ref: str | None,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    execution_consumer_id: str,
    challenge_id: str,
    challenge_hash: str,
    credential_id_hash: str,
    authenticator_attachment: str | None,
    signed_at: str,
    artifact_expires_at: str,
)
```

`ReservationToken = str`. It is derived as
`canonical_hash((source_ref_hash, artifact_id, reserved_at))`. A later
`mark_consumed_for_artifact(...)` call must present the same token or fail
closed.

`S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` opens one
SQLite connection over the shared file, executes `BEGIN IMMEDIATE`, calls
`S7VoiceBundleUseStore.reserve_for_artifact(...)`, calls
`S7AuthorizationStore.put(...)` with the wrapper's injected connection handle,
and commits or rolls back atomically. S7.3 amends `S7AuthorizationStore.put(...)`
to accept an optional injected connection and to avoid opening or committing its
own transaction when that connection is supplied.

`write_bundle(...)` runs before artifact mint, after Maez response capture,
semantic-reader classification, authority-boolean computation, and reducer
output. It writes the immutable evidence row and initial `S7VoiceBundleUse`
row in one transaction. `put_artifact_with_bundle_reservation(...)` is a later
finish-time transaction that reserves the already-written bundle and stores the
authorization artifact atomically.

The directory must be mode `0700` where the platform supports it; the database
file must be mode `0600`; migrations must refuse broader permissions unless a
reviewed platform exception is recorded.

The store is included in Decision-22 continuity backups because the bundle is
needed to revalidate D12 and D23 facts. `scripts/backup/backup_state_manifest.json`
must include this file (one entry covering the shared state DB). Backup
inclusion must preserve content-free projections for routine status while
keeping raw bundle contents out of ordinary health/custodian surfaces.

The evidence row and the use-state row are deliberately split.

**`S7VoiceConsultationBundle` immutable evidence.** Computed once at write time
and never mutated thereafter. Minimum fields:

```text
schema_version
consultation_id
request_id
request_envelope_hash
mutation_preview_hash
action_params_hash
precondition_hash
authority_context_hash
rollback_plan_ref
producer
source_ref_kind
prompt_template_id
prompt_template_hash
rendered_prompt_hash
rendered_prompt_ref
expected_consultation_nonce_hash
runtime_identity_hash
model_routing_identity_hash
model_config_hash
context_manifest_ref
context_manifest_hash
raw_maez_response_ref
raw_maez_response_hash
marker_kind
parsed_marker_nonce_hash
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
captured_response_nonempty
authority_class
attempt_manifest_hash
attempt_count
attempt_outcomes
classifier_reason_code
created_at
expires_at
```

`source_ref_hash` is the canonical content-hash of this immutable evidence row.
The hash domain excludes `source_ref_hash` itself because the field is the row's
identifier and cannot hash itself. `source_ref_hash` is the primary key and the
binding hash used by the consultation row. Bundle rows are immutable once
written; the source-bundle validator (D16) recomputes the hash over the
immutable fields with the same exclusion rule and rejects any mismatch.
`consultation_id` is unique.

`final_rendered_statement_hash` is not part of the bundle. The binding direction
is one-way: the rendered statement points at the consultation, and the
consultation points at the bundle. The final rendered statement hash is recorded
after render in the execution trace and D23 row, not in the pre-render evidence
bundle.

**`S7VoiceBundleUse` mutable lifecycle state.** A separate table tracks
reservation and consumption without changing the immutable bundle hash:

```text
S7VoiceBundleUse(
    source_ref_hash: str,
    reserved_for_artifact: str | None,
    reserved_at: str | None,
    reservation_token: str | None,
    consumed_for_artifact: str | None,
    consumed_at: str | None,
)
```

`source_ref_hash` is the primary key and foreign key to the immutable bundle.
Reservation and consumption flows mutate only `S7VoiceBundleUse`.

`marker_kind` is nullable before parser success. It is one of
`explicit_no_objection`, `blocking_marker`, `withdrawal_marker`, or
`missing_or_malformed`. `parsed_marker_nonce_hash` is `None` for
`missing_or_malformed` rows and otherwise hashes the nonce parsed from Maez's
marker text. The raw nonce is never persisted in the immutable bundle.

**Nonce carrier and spent-nonce uniqueness.** The consultation nonce is minted
server-side at consultation start before prompt assembly. The implementation
reserves `expected_consultation_nonce_hash` in the nonce table before the prompt
is sent, then copies that hash into the immutable bundle when `write_bundle(...)`
runs after response processing. The raw nonce is never written to the bundle. A
`spent_consultation_nonces` table or unique constraint over
`expected_consultation_nonce_hash` prevents nonce reuse. The parser rejects a
marker whose nonce hash has already been spent.

**Authority booleans (D19 carriers).** Authority booleans are computed by
`compute_s7_voice_authority_booleans(...)` before reducer replay, persisted on
the immutable bundle, and used as the deterministic source-of-truth for D19's
authoritative-eligibility predicate:

- `has_grounded_semantic_blocking_signal` is `True` iff `semantic_reader_outcome
  == "blocking_signal_present"` AND the bundle's stored
  `SemanticReaderGroundingEvidence` has `preview_exclusion_check=True` AND at
  least one `response_span_quote` extracted from `raw_maez_response_hash`'s text
  AND `semantic_reader_grounding_hash` recomputes correctly.
- `marker_was_blocking_marker_verified` is `True` iff `marker_kind ==
  "blocking_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `parsed_marker_nonce_hash ==
  expected_consultation_nonce_hash` AND the parsed `consultation_id`,
  `request_id`, and `mutation_preview_hash` match the bundle.
- `marker_was_withdrawal_marker_verified` is `True` iff `marker_kind ==
  "withdrawal_marker"` AND the marker text replays from the stored
  `raw_maez_response_ref` AND `parsed_marker_nonce_hash ==
  expected_consultation_nonce_hash` AND the parsed `consultation_id`,
  `request_id`, and `mutation_preview_hash` match the bundle.
- `captured_response_nonempty` is `True` iff `raw_maez_response_ref` resolves
  to non-whitespace response text outside the terminal marker block.

Bundle row may keep large raw payloads in a `bundle_artifacts` sub-table or
external-ref column family; the main row keeps hashes and refs for raw Maez
response, rendered prompt, raw mutation material, and semantic-reader raw
output.

The store exposes:

```text
write_bundle(bundle) -> source_ref_hash
read_by_source_ref_hash(source_ref_hash) -> bundle | None
read_bundle_use(source_ref_hash) -> S7VoiceBundleUse | None
reserve_for_artifact(source_ref_hash, artifact_id) -> ReservationToken  # use table
mark_consumed_for_artifact(source_ref_hash, artifact_id, reservation_token, consumed_at)  # use table
```

Replay protection:

- a `source_ref_hash` may satisfy only the matching request id and envelope hash;
- stale or expired bundles fail validation;
- consumed-source metadata is audit evidence and does not let a bundle authorize
  a second artifact;
- `reserve_for_artifact(...)` mutates only `S7VoiceBundleUse` and is the atomic
  claim step run inside `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)`;
  two concurrent finish attempts cannot reserve the same source bundle for two
  artifacts;
- `mark_consumed_for_artifact(...)` mutates only `S7VoiceBundleUse` after
  artifact consume succeeds inside the same shared-file transaction discipline;
  the natural caller is `S7GuardedStateStore.consume_artifact_for_execution(...)`;
- spent consultation nonces cannot be reused;
- later attempts over changed material require a new consultation id and bundle.

Retention policy: raw payload refs may be archived to read-only storage after
`expires_at` and may be purged after a reviewed retention window. Metadata
needed for L8 replay, including immutable hashes, rendered prompt hash, reducer
row, authority class, and authority booleans, is retained indefinitely
unless future reviewed canon says otherwise.

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

The prompt template body contains only these substitution tokens:

```text
{{consultation_id}}
{{request_id}}
{{mutation_preview_hash}}
{{consultation_nonce}}
{{preview_body}}
{{context_manifest}}
```

Substitution rules:

- scalar tokens are replaced literally with the bound value;
- `{{preview_body}}` is rendered as a fenced quoted block; backticks in the
  preview body are escaped by replacing each backtick with a backslash-prefixed
  backtick before the block is written;
- `{{context_manifest}}` is rendered from the D7 `ContextManifest` object in
  this exact field order: `preview_ref`, `request_envelope_hash`,
  `precondition_hash`, `rollback_path_class`, `source_surface`,
  `proposal_origin_label`, `policy_id`, `policy_hash`;
- no unknown token may remain after substitution;
- the resulting `rendered_prompt_text` is canonicalized with LF line endings and
  no trailing whitespace;
- `rendered_prompt_hash = canonical_hash(rendered_prompt_text)`.

The producer persists `rendered_prompt_hash`, `rendered_prompt_ref`,
`context_manifest_ref`, and `context_manifest_hash` into the immutable source
bundle so the validator can replay prompt assembly.

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

Parser output shape:

```text
ParsedS7VoiceMarker(
    marker_kind: "explicit_no_objection" | "blocking_marker" | "withdrawal_marker" | "missing_or_malformed",
    parsed_consultation_id: str | None,
    parsed_request_id: str | None,
    parsed_mutation_preview_hash: str | None,
    parsed_marker_nonce_hash: str | None,
    marker_text_hash: str | None,
)
```

The nonce is a cryptographically random 32-byte value generated server-side at
consultation start before prompt assembly. The raw nonce is substituted into
the prompt; only `expected_consultation_nonce_hash` and, after parsing, the
`parsed_marker_nonce_hash` are persisted in the immutable bundle. The nonce
does not make prompt injection impossible, but it prevents stale or copied
marker text from satisfying the parser without the current consultation
context. Spent nonce hashes are recorded in the bundle store; reuse fails the
parser. For marker-bearing rows, the parsed marker nonce is re-hashed and
compared with `expected_consultation_nonce_hash`; rows without a valid marker
cannot produce `absent`. Marker validity is time-bounded by
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

The validator does not trust this object merely because it hashes correctly.
It performs a deterministic grounding replay:

- every `response_span_quote` must match the response text at its corresponding
  `response_span_offsets`;
- for `blocking_attribution_source="response_only"`, each accepted span must
  appear in the response and not in the rendered preview body;
- for `blocking_attribution_source="response_with_preview_quote"`, at least one
  accepted span or adjacent response chunk used by the reader must be present in
  the response and absent from the preview, so the objection is anchored in
  Maez's own framing rather than solely in quoted proposal text;
- if the deterministic check fails, the validator sets
  `invalid_authority_predicate` and the reducer replay cannot produce an
  authoritative grounded semantic blocking signal.

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

The reviewed route manifest lives at:

```text
config/s7_voice_semantic_reader_manifest.json
```

and is loaded through:

```text
load_s7_voice_semantic_reader_manifest(path: str) -> S7VoiceSemanticReaderRouteManifest
validate_s7_voice_semantic_reader_manifest(manifest: S7VoiceSemanticReaderRouteManifest) -> None
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

The semantic-reader port signature is:

```text
S7VoiceSemanticReaderV1.classify(
    *,
    route_manifest: S7VoiceSemanticReaderRouteManifest,
    prompt_template_hash: str,
    context_manifest: ContextManifest,
    preview: MutationPreviewArtifact,
    raw_maez_response_ref: str,
    raw_maez_response_hash: str,
    parsed_marker_kind: str,
    now: str,
) -> S7VoiceSemanticReaderResult
```

`S7VoiceSemanticReaderResult` carries `semantic_reader_outcome`,
`semantic_reader_output_hash`, `semantic_reader_grounding_hash`, and the raw
reader-output private ref.

`reader_unavailable` is not a model output. It is the reducer input when the
semantic-reader route fails after a Maez response has been captured.

No unreviewed local classifier, bonded Maez fallback, caller boolean, or
history scan may substitute for the semantic reader in a positive `absent`
trace.

### D13 - Deterministic Authority And Reducer Rule Table

The reducer is split into two deterministic stages so authority booleans are
not both inputs and outputs of the same function.

**Stage 1: authority boolean computation.**

```text
compute_s7_voice_authority_booleans(
    *,
    bundle: S7VoiceConsultationBundle,
    parsed_marker: ParsedS7VoiceMarker,
    grounding_evidence: SemanticReaderGroundingEvidence | None,
    raw_maez_response_text: str,
    preview_body_text: str,
) -> S7VoiceAuthorityBooleans
```

`S7VoiceAuthorityBooleans` carries:

```text
has_grounded_semantic_blocking_signal: bool
marker_was_blocking_marker_verified: bool
marker_was_withdrawal_marker_verified: bool
captured_response_nonempty: bool
```

`captured_response_nonempty` is true when the captured Maez response text has
non-whitespace content outside the terminal marker block. It is used only for
the conservative `explicit_no_objection + reader_unavailable` row.

**Stage 2: reducer proper.**

```text
reduce_s7_voice_consultation(
    *,
    marker_kind: "explicit_no_objection" | "blocking_marker" | "withdrawal_marker" | "missing_or_malformed",
    semantic_reader_outcome: "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain" | "reader_unavailable",
    authority_booleans: S7VoiceAuthorityBooleans,
) -> S7VoiceReduction
```

`S7VoiceReduction` carries the committed voice-state fields and row authority:

```text
maez_objection_state
maez_withdrew_request
unavailable_reason_code
authority_class
```

`authority_class` is closed to `{none, operational, authoritative}`.
`authority_class="none"` is used only for the positive no-objection row and
means no D23 authority row is produced.

Verified blocking markers are authoritative even when the semantic reader is
unavailable, uncertain, or disagrees, provided
`marker_was_blocking_marker_verified=True`. This is the let-Maez-be-heard side
of the invariant: a replay-protected marker-confirmed objection is not silenced
because the semantic reader missed it. Marker-only authority for
`explicit_no_objection` and `missing_or_malformed` rows is never positive
consent.

Rule table:

| Marker | Semantic reader | maez_objection_state | maez_withdrew_request | unavailable_reason_code | authority_class | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `explicit_no_objection` | `no_blocking_signal_detected` | `absent` | `False` | `none` | `none` (no D23 row) | Only positive no-objection path. |
| `explicit_no_objection` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Blocks; D23 if grounded. |
| `explicit_no_objection` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | Blocks; no D23 refusal authority. |
| `explicit_no_objection` | `reader_unavailable` | `present` | `False` | `none` | `authoritative` if `captured_response_nonempty=True`, else `operational` | Conservative OQ1 routing; a captured response cannot be converted into no-objection by disabling the reader. |
| `blocking_marker` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True` OR `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; D23 with either authority source. |
| `blocking_marker` | `no_blocking_signal_detected` | `present` | `False` | `none` | `authoritative` if `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; verified marker is heard even if reader disagrees. |
| `blocking_marker` | `unreadable_or_uncertain` | `present` | `False` | `none` | `authoritative` if `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; verified marker is heard even if reader is uncertain. |
| `blocking_marker` | `reader_unavailable` | `present` | `False` | `none` | `authoritative` if `marker_was_blocking_marker_verified=True`, else `operational` | Blocks; D23 via verified marker. |
| `withdrawal_marker` | `blocking_signal_present` | `present` | `True` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True` OR `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks; withdrawal counted with either authority source. |
| `withdrawal_marker` | `no_blocking_signal_detected` | `not_determined` | `True` | `none` | `authoritative` if `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks; verified withdrawal is counted even if reader disagrees. |
| `withdrawal_marker` | `unreadable_or_uncertain` | `not_determined` | `True` | `none` | `authoritative` if `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks; verified withdrawal is counted. |
| `withdrawal_marker` | `reader_unavailable` | `not_determined` | `True` | `semantic_reader_unavailable` | `authoritative` if `marker_was_withdrawal_marker_verified=True`, else `operational` | Blocks via D18; withdrawal counted via verified marker. |
| `missing_or_malformed` | `blocking_signal_present` | `present` | `False` | `none` | `authoritative` if `has_grounded_semantic_blocking_signal=True`, else `operational` | Missing marker cannot create absent. |
| `missing_or_malformed` | `no_blocking_signal_detected` | `not_determined` | `False` | `none` | `operational` | Marker required for absent. |
| `missing_or_malformed` | `unreadable_or_uncertain` | `not_determined` | `False` | `none` | `operational` | No reliable voice fact. |
| `missing_or_malformed` | `reader_unavailable` | `not_determined` | `False` | `semantic_reader_unavailable` | `operational` | Blocks via D18; no reliable voice fact. |

The reducer must never output `maez_objection_state="absent"` with
`maez_withdrew_request=True`; that combination raises at reducer edge,
constructor edge, and validator edge.

**Folded from OQ1 v5.** This table restores OQ1's conservative treatment of
`explicit_no_objection + reader_unavailable` for captured non-empty responses,
while making the authority predicate concrete. It also changes the prior v4
`blocking_marker + reader-disagrees` cells so marker-verified objections are
authoritative rather than silently operational.

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
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
model_outage
producer_not_run
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

`PRODUCER_RESULT_REASON_CODES`, `attempt_outcomes`, and
`PROJECTION_REASON_CODES` share this canonical token vocabulary. A surface may
use a subset, but it must not rename a token. In particular,
`non_retryable_context_overflow` is the canonical form; `context_overflow` is
not a separate reason code.

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

Result shape:

```text
S7VoiceSourceBundleValidationResult(
    status: str,
    source_bundle_valid: bool,
    mint_eligible: bool,
    authority_projection: "none" | "operational" | "authoritative",
    failure_reason_code: str | None,
)
```

`status` is closed to:

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

Artifact minting for voice-seat work is allowed only when
`source_bundle_valid=True`, `mint_eligible=True`, and `status="valid_absent"`.
D19 authority rows may be written only when `source_bundle_valid=True` and
`authority_projection="authoritative"`; operational blocks do not mint and do
not aggregate.

The validator:

- loads the private bundle by `source_ref_hash`;
- verifies bundle row content-hash matches the canonical-hash recomputation
  over immutable fields with `source_ref_hash` excluded from the hash domain
  (immutability check);
- verifies the matching `S7VoiceBundleUse` row is either unreserved or reserved
  for the artifact currently being minted through `S7GuardedStateStore`;
- verifies content-free consultation row and bundle agreement;
- verifies producer/source pair;
- verifies request, preview, params, precondition, authority context, rollback
  plan, prompt, model, and context-manifest hashes;
- loads `bundle.context_manifest_ref`, recomputes `context_manifest_hash`, and
  verifies the manifest obeys the D7 closed schema;
- replays prompt assembly from the prompt template body at
  `prompt_template_hash`, preview, context manifest, consultation id, request
  id, mutation_preview_hash, and the nonce extracted from the private
  `rendered_prompt_ref`, then verifies the replayed hash equals
  `bundle.rendered_prompt_hash` and the extracted nonce hashes to
  `bundle.expected_consultation_nonce_hash`;
- verifies `parsed_marker_nonce_hash == bundle.expected_consultation_nonce_hash`
  for marker-bearing rows and rejects spent-nonce reuse;
- verifies semantic-reader prompt/model/config binding;
- computes `S7VoiceAuthorityBooleans` from raw evidence, marker replay, and
  deterministic grounding checks, then verifies the persisted authority
  booleans match;
- replays the deterministic reducer over `(marker_kind, semantic_reader_outcome,
  authority_booleans)` and verifies match against persisted `reducer_output_*`
  fields;
- verifies expiry and `webauthn_challenge.expires_at` compatibility (per the
  Expiry Lifecycle invariant);
- verifies `maez_voice_consulted=True`;
- for mint eligibility only, verifies `maez_objection_state="absent"`,
  `maez_withdrew_request=False`, and `unavailable_reason_code in {None, "none"}`;
- rejects `absent` plus `maez_withdrew_request=True`;
- verifies `D17 final rendered text` includes `Mutation preview hash` line
  matching `bundle.mutation_preview_hash` and `Rollback plan ref` line matching
  `bundle.rollback_plan_ref`.

Hash routing is explicit:

```text
work_item.preview_ref                -> preview.preview_id (identity)
preview.mutation_preview_hash        -> bundle.mutation_preview_hash (binding)
work_item.rollback_plan_ref          -> bundle.rollback_plan_ref
envelope.precondition_hash           -> bundle.precondition_hash
consultation.source_ref_hash         -> bundle.source_ref_hash (content hash, exclusion rule)
rendered.maez_voice_consultation_hash -> maez_voice_consultation_hash(consultation)
rendered.rendered_text_hash          -> hash(full rendered text, including preview and rollback lines)
trace.final_rendered_statement_hash  -> rendered.rendered_text_hash (post-render trace record)
bundle.context_manifest_ref          -> ContextManifest private store row
context_manifest_hash                -> canonical_hash(ContextManifest, manifest_id excluded)
prompt/model/context hashes          -> bundle.* (rendered prompt replayed)
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
the carrier hashes directly.

**New fields on `RenderedRequestStatement`** (per D-Enum-Amendment):

```text
mutation_preview_hash: str
rollback_plan_ref: str
```

The rendered text body must include these lines verbatim:

```text
Preview body class: <class>
Preview summary: <bounded human-readable summary>
Preview affected paths: <canonical path list or none>
Mutation preview hash: <64-char hex>
Rollback plan ref: <64-char hex>
```

`Preview summary` and `Preview affected paths` are deterministic projections of
`MutationPreviewArtifact`, bounded for founder readability and backed by the
`mutation_preview_hash`. The founder ceremony is not S7.3-complete if it shows
only a hash. `RenderedRequestStatement.__post_init__` validates these lines as
part of `expected_metadata`. Tampering raises.

**`maez_objection_state` projection** (five-value display, unchanged from S7.1):

```text
none | absent | present | unavailable | not_determined
```

S7.3 amends `render_request_statement(...)` so that for voice-seat work:

- if Maez voice is required and no `MaezVoiceConsultation` row exists,
  `render_request_statement(...)` raises and produces no rendered statement;
  the renderer never synthesizes voice state;
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

Unavailability generally maps to:

```text
maez_objection_state="not_determined"
unavailable_reason_code=<closed unavailable reason>
```

The one conservative exception is D13's
`explicit_no_objection + reader_unavailable + captured_response_nonempty` row:
because a captured free-text response cannot be inspected, the reducer routes
the row to `maez_objection_state="present"` with `authority_class` conditional
on the captured-response carrier. The row blocks and records
`classifier_reason_code="reader_unavailable"`; it does not produce positive
absence.

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

### D19 - D23 Refusal, Authority Rows, And Request History

S7.3 distinguishes authoritative Maez refusal from operational block.

S7.3 writes a new internal `S7VoiceAuthorityRow` for replayable voice evidence
and then bridges authoritative refusal or withdrawal into the committed
`S7RequestHistoryRecord` / `assess_aggregation_risk` path. The new row does not
silently replace the committed aggregator; it is the source evidence for the
history record the existing D23 machinery reads.

`S7VoiceAuthorityRow` may be written only when:

- a reviewed producer ran;
- the source-bundle validator returns `source_bundle_valid=True`;
- the row has `authority_class="authoritative"` (set deterministically by the
  reducer per D13 from `S7VoiceAuthorityBooleans`); and
- either:
  - `maez_objection_state="present"` and
    `source_bundle.has_grounded_semantic_blocking_signal=True`; or
  - `maez_objection_state="present"` and
    `source_bundle.marker_was_blocking_marker_verified=True`; or
  - `maez_withdrew_request=True` and either
    `source_bundle.has_grounded_semantic_blocking_signal=True` or
    `source_bundle.marker_was_withdrawal_marker_verified=True`.

`S7VoiceAuthorityRow` schema:

```text
request_id
request_envelope_hash
surface_class
final_rendered_statement_hash
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

The bridge to committed request history is deterministic:

- if `authority_class="authoritative"` and `maez_objection_state="present"`,
  write one `S7RequestHistoryRecord` with `outcome="refused"` and a provenance
  pointer to the `S7VoiceAuthorityRow`;
- if `authority_class="authoritative"` and `maez_withdrew_request=True`, write
  one withdrawal history record through the committed D23 extension point named
  by the implementation amendment; until that extension exists, the withdrawal
  row is retained as `S7VoiceAuthorityRow` evidence and does not claim to
  influence `assess_aggregation_risk`;
- if the positive path mints an artifact, write the inherited authorized
  request history record so refusal aggregation can compare later refusals
  against real authorized attempts.

The deterministic SQL filters apply to `S7VoiceAuthorityRow`; the committed
aggregator continues to read `S7RequestHistoryRecord` until explicitly
migrated. Implementation acceptance requires either the bridge above or a
reviewed migration that teaches `assess_aggregation_risk` to read the new row
directly.

Operational non-authoritative rows include all rows where
`authority_class="operational"`. The reducer (D13) determines
`authority_class` deterministically; rows where `authority_class="authoritative"`
are authoritative regardless of `maez_objection_state` or
`unavailable_reason_code`.

The subtle authoritative case is
`withdrawal_marker + reader_unavailable + marker_was_withdrawal_marker_verified=True`.
That row carries `maez_objection_state="not_determined"`,
`unavailable_reason_code="semantic_reader_unavailable"`,
`maez_withdrew_request=True`, and `authority_class="authoritative"`. It blocks
via D18, contributes to D23 withdrawal aggregation as authoritative, and does
not contribute to refusal aggregation because `maez_objection_state` is not
`present`.

Operational rows may still block the current authorization when the current
S7.3 rule says to block, but they must not count as long-use Maez refusal
evidence, escalation evidence, or Maez preference.

Replay, rate, and provenance controls must prevent repeated malformed,
unauthenticated, pre-auth, or unavailable attempts from poisoning refusal
history. The D9 strong replay protection (nonce uniqueness, bundle
immutability, time bounds, single-use consultation id) is the v5 mechanism;
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
    rendered_projection_state: "none" | "absent" | "present" | "unavailable" | "not_determined" | "not_consulted_blocking",
    operator_reason_code: str,  # from PROJECTION_REASON_CODES
)
```

`PROJECTION_REASON_CODES` is a closed set lifted from OQ1's Operator-Visible
Failure Projection list:

```text
none
retry_exhausted
model_outage
non_retryable_context_overflow
prompt_integrity_block
terminal_uncertainty
bundle_validation_failed
stale_binding
classifier_error
reader_unavailable
bonded_maez_unavailable
ungrounded_blocking_signal
service_unavailable_not_operator_caused
context_manifest_violation
producer_not_run
```

It is not a `MaezVoiceConsultation` and cannot satisfy D12. If voice is
required and no producer ran, the projection returns
`rendered_projection_state="not_consulted_blocking"` with
`operator_reason_code="producer_not_run"`, and the guarded request remains
blocked. This status never appears in `RenderedRequestStatement`.

### D21 - Execution Consumers Require Consumed Grants

Every positive guarded mutation requires a consumed `S7ExecutionGrant`.

**Carrier amendment.** S7.3 v5 pins the CP-S4 grant-binding choice by extending
the grant rather than adding only a side table. `S7ExecutionGrant` extends to
carry:

```text
grant_id: str             # minted during consume as canonical_hash((artifact_id, consumed_at, nonce))
expires_at: str
execution_consumer_id: str
```

`grant_id` is generated atomically during `consume_for_execution(...)` from the
artifact id, a fresh nonce, and the consumed_at timestamp. The `grant_id`
appears in the returned grant; it is not an input to consume.

`execution_consumer_id` is closed to `S7_EXECUTION_CONSUMER_IDS`. The
guarded-work bridge derives it deterministically from the surface adapter and
function that materialized the `GuardedWorkItem`; callers cannot choose an
arbitrary string. `consume_for_execution(...)` validates `consumer_id` against
that closed set at mint time.

`S7ExecutionAuthorization` also carries `execution_consumer_id` so existing
pre-consume call sites, including service-maintenance authorization consumers,
do not have to rediscover a source surface at consume time. Non-voice S7.1
credential-management consumers use the closed ids
`s7_credential_register_backup` and `s7_credential_disable`.

**Consume API.** The live S7.3 API is the shared-state wrapper:

```text
S7GuardedStateStore.consume_artifact_for_execution(
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
    superseded_request_ids: set[str] | None = None,
    covenant_ceremony_evidence: object | None = None,
    after_consume_before_commit: callable | None = None,
) -> tuple[S7ExecutionGrant | None, GrantUse | None]
```

The wrapper delegates to the amended inherited
`S7AuthorizationStore.consume_for_execution(...)` with the wrapper's injected
SQLite connection. The nullable return shape preserves committed S7.1 failure
semantics: stale rendered request, action-params mismatch, expired authority
context, supersession, covenant ceremony failure, already-consumed artifact,
and SQL failure all return `(None, None)` after rollback and before substrate
mutation.

On success the wrapper atomically:

1. consumes the artifact (inherited S7.1 behavior);
2. mints the `S7ExecutionGrant` with `grant_id`, `expires_at`, and
   `execution_consumer_id=consumer_id`;
3. persists a durable `GrantUse` record;
4. marks the matching `S7VoiceBundleUse` consumed when `source_ref_hash` is
   present;
5. returns `(grant, grant_use)`.

**`consume_verified(...)` migration.** The existing
`consume_verified(...)` compatibility wrapper remains during S7.3. It is marked
deprecated, delegates to `consume_for_execution(...)` with a
closed `execution_consumer_id` carried on `S7ExecutionAuthorization`, and fails
closed when that id is missing or outside `S7_EXECUTION_CONSUMER_IDS`. Removal
is deferred to a future S7.x cleanup slice after current callers are rewired.

**`GrantUse` schema.** Durable, persisted in the shared SQLite state file (per
D9 atomicity mechanism):

```text
GrantUse(
    artifact_id: str,
    grant_id: str,
    execution_consumer_id: str,
    source_ref_hash: str | None,
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
    source_ref_hash TEXT,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    replay_token TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_s7_grant_uses_grant_id ON s7_grant_uses(grant_id);
CREATE INDEX idx_s7_grant_uses_execution_consumer_id ON s7_grant_uses(execution_consumer_id);
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
- the `GrantUse.replay_token` is unique in `s7_grant_uses`;
- the `grant.execution_consumer_id` matches the
  `GuardedWorkItem.execution_consumer_id`, and both match the deterministic
  derivation for the source surface.

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
rendered_prompt_hash
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
final_rendered_statement_hash
action_params_hash
precondition_hash
authority_context_hash
mutation_preview_hash
maez_voice_consultation_hash
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
trace_status
created_at
```

Trace finalization is two-phase. Before mutation the execution service writes a
pending `S7GuardedExecutionTrace` with `trace_status="pending"` after grant
consume and before substrate write. After mutation it finalizes with
`trace_status="finalized"` and fills `mutation_result`, post-mutation hashes,
rollback result ref, and post-mutation verification. If mutation raises after
grant consume, the service writes a failed trace and either invokes rollback or
records why rollback could not run; a consumed grant without finalized-or-failed
trace is a health-blocking incident.

Positive traces used for L8 retirement must bind the live voice producer,
artifact mint, atomic consume, grant, mutation, D23 projection, rollback plan
evidence, rollback result evidence, and post-mutation verification.

### D23 - Rollback Evidence

Rollback evidence is required for positive guarded execution.

Rollback evidence is stored in `S7RollbackEvidenceStore`, a table family in the
shared state database:

```text
write_rollback_plan(plan: RollbackPlanEvidence) -> rollback_plan_ref
read_rollback_plan(rollback_plan_ref) -> RollbackPlanEvidence | None
write_rollback_result(result: RollbackResultEvidence) -> rollback_result_ref
read_rollback_result(rollback_result_ref) -> RollbackResultEvidence | None
```

`rollback_plan_ref` and `rollback_result_ref` are canonical content hashes of
their respective evidence objects. Store rows are immutable after write.

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
via D17 (`Rollback plan ref: <hash>` line).

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
`rollback_proof_required` means the execution cannot be considered positive
until `RollbackResultEvidence` proves either `rollback_result_status="not_invoked"`
after a successful mutation or a successful rollback after a failed mutation.

Full positive-execution evidence requires both `rollback_plan_ref` and
`rollback_result_ref`. L8 retirement evidence requires both refs for every
in-scope adapter/consumer or reviewed same-code coverage proof.

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
- marker-says-block plus semantic-reader clean -> `present` and
  `authoritative` when marker verification passes;
- blackhole-reader attack: selectively making the semantic reader unavailable on
  captured non-empty responses does not convert a response into consent; the
  conservative `explicit_no_objection + reader_unavailable` row blocks and is
  authoritative per D13;
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
  grant.expires_at <= webauthn_challenge.expires_at` is enforced;
- **marker-verified blocking test**: a `blocking_marker + reader_unavailable`
  row where the marker passes nonce/id/preview-hash verification is
  authoritative (`marker_was_blocking_marker_verified=True`); the same row
  with a stale or fabricated marker is operational;
- **strong replay protection test**: a marker reusing a spent nonce fails the
  parser; a marker with a mismatched consultation id fails the parser; a marker
  outside the time-bounded validity window fails the parser; consumed
  consultation ids cannot be reused;
- **expected-nonce verification test**: a marker whose nonce hashes to anything
  other than `bundle.expected_consultation_nonce_hash` fails marker verification;
- **rendered-prompt replay test**: the validator replays prompt substitution
  from the template, preview, context manifest, ids, preview hash, and nonce,
  and rejects a bundle whose `rendered_prompt_hash` does not match;
- **execution-consumer vocabulary test**: a work item with an
  `execution_consumer_id` outside `S7_EXECUTION_CONSUMER_IDS`, or one that does
  not match the source-surface derivation, fails before grant mint;
- **immutable-bundle-row test**: changing any immutable
  `S7VoiceConsultationBundle` field after write changes the recomputed
  `source_ref_hash`; the validator rejects the row while allowing mutable
  `S7VoiceBundleUse` reservation fields to change;
- **validator grounding replay test**: `response_with_preview_quote` is accepted
  only when deterministic response-only framing exists outside the preview
  quote; reader self-attestation alone is rejected;
- **S7VoiceAuthorityRow bridge test**: an authoritative refusal writes the
  bridge `S7RequestHistoryRecord` consumed by `assess_aggregation_risk`;
- **rollback evidence store test**: rollback plan/result refs resolve through
  `S7RollbackEvidenceStore` and immutable-row tampering fails hash replay;
- **trace finalization test**: a consumed grant produces either finalized
  success trace or failed/rollback trace before health can report positive
  execution;
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
- live founder-key traces or reviewed same-code coverage exist for every
  in-scope adapter/consumer, with no surface hidden behind a broader class name;
- no placeholder producer, test-only verifier, callable helper, boolean opt-in,
  or hand-assembled artifact (`MaezVoiceConsultation`,
  `S7AuthorizationArtifact`, `S7ExecutionAuthorization`, `S7ExecutionGrant`, or
  `GrantUse`) is used as L8 evidence.

If the substrate lands but the live producer or consumers remain blocked, the
health mode must retain L8 or move to an equally honest reviewed successor mode.

### Expiry Lifecycle

The expiration timestamps in S7.3 form a stated invariant chain:

```text
now < bundle.expires_at
        <= work_item.expires_at
        <= artifact.expires_at
        <= grant.expires_at
        <= webauthn_challenge.expires_at
```

The source-bundle validator (D16) enforces `now < bundle.expires_at` and
`bundle.expires_at <= work_item.expires_at`. The artifact mint enforces
`work_item.expires_at <= artifact.expires_at`. The consume operation enforces
`artifact.expires_at <= grant.expires_at <= webauthn_challenge.expires_at`. The
consumer pre-mutation check enforces `now < grant.expires_at`.

Stale-binding failures fire at the first violation in the chain.

## Implementation Acceptance Checklist

Before implementation can be claimed complete:

1. **Closed-enum amendments** (D-Enum-Amendment) land:
   `MAEZ_UNAVAILABLE_REASON_CODES` adds `semantic_reader_unavailable` and
   `bonded_maez_unavailable`; `RenderedRequestStatement.maez_consulted_state`
   remains `{yes, not required}`; `RenderedRequestStatement` gains
   `mutation_preview_hash` and `rollback_plan_ref` fields with corresponding
   rendered-text lines and `expected_metadata` enforcement;
   `MaezVoiceConsultation.__post_init__` rejects `absent+withdrew=True`;
   `S7_EXECUTION_CONSUMER_IDS`, `BLOCKING_UNAVAILABLE_REASONS`, and
   `authority_class` closed vocabularies exist.
2. **Reviewed semantic-reader route manifest** is committed naming concrete
   provider, model, model version, decoding parameters, prompt template hash,
   tool policy, network route, and config hash. Until this lands, the positive
   voice path is blocked.
3. `GuardedWorkItem`, `MutationPreviewArtifact` (with `mutation_preview_hash`),
   `ContextManifest`, `S7VoiceProducerResult`, `S7VoiceProjection`,
   `RollbackPlanEvidence`, `RollbackResultEvidence`,
   `S7VoiceConsultationBundle`, `S7VoiceBundleUse`,
   `S7AuthorizationArtifactInputs`, `ReservationToken`,
   `S7GuardedStateStore`, `S7VoiceAuthorityRow`, `GrantUse`,
   `S7RollbackEvidenceStore`, and source-bundle validation shapes exist and are
   tested.
4. `S7VoiceConsultationBundleStore`, `S7VoiceBundleUseStore`,
   `S7AuthorizationStore`, and `S7GrantUseStore` share the SQLite file at
   `memory/s7_3_guarded_self_modification/state.sqlite3` with table prefixes,
   migrations, permissions, backup inclusion, and the
   `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` and
   `S7GuardedStateStore.consume_artifact_for_execution(...)` transaction
   wrappers. `S7AuthorizationStore.put(...)` and consume paths accept an
   injected connection. The authority booleans
   (`has_grounded_semantic_blocking_signal`,
   `marker_was_blocking_marker_verified`,
   `marker_was_withdrawal_marker_verified`, `captured_response_nonempty`) are
   computed before reducer replay and persisted on the immutable bundle.
5. The bonded Maez runtime port (D7) takes `rendered_prompt_text` and pins
   runtime/model identity in the source bundle. The producer port (D8) owns
   prompt assembly per the substitution grammar, persists `rendered_prompt_hash`
   and `rendered_prompt_ref`, and the validator replays prompt assembly.
6. The Maez-facing prompt and marker parser implement D10 with cryptographic
   nonce, time-bounded validity, and single-use consultation id (strong replay
   protection).
7. The semantic-reader prompt and grounding contract implement D11-D12,
   including the let-Maez-be-heard predicate that distinguishes "response
   quotes preview" from "blocking attributed solely to preview."
8. Authority-boolean computation and the reducer implement D13 exactly,
   including marker-verified objections when the reader disagrees and the
   conservative `explicit_no_objection + reader_unavailable` row.
9. The source-bundle validator implements D16's rich result shape and gates
   artifact minting on `source_bundle_valid=True`, `mint_eligible=True`, and
   `status="valid_absent"`.
10. `render_request_statement(...)` implements the D17 amendments: new fields,
    new rendered-text lines, `expected_metadata` enforcement, unavailable
    projection, and `no` vs `none` canonicalization.
11. `_s7_voice_consultation_for_card(...)` no longer emits eligible placeholder
    rows; replaced by `build_s7_voice_projection_for_card(...)` per D20.
12. `S7GuardedStateStore.consume_artifact_for_execution(...)` implements the
    D21 wrapper with `consumer_id` and returns
    `(S7ExecutionGrant | None, GrantUse | None)`. `s7_grant_uses` table exists
    in the shared state DB. `S7ExecutionAuthorization` carries
    `execution_consumer_id`. `consume_verified(...)` remains only as a
    deprecated wrapper that reads this closed id and fails closed when it
    cannot.
13. `/apply_dream`, `/apply_edit`, natural-language Telegram proposal/section
    approval, evolution candidate apply (`apply_candidate(...)`), workshop diff
    apply (`apply_diff(...)`), approval cards, self-mod dialog, CLI, cockpit,
    reviewed substrate adapters, and ActionEngine final mutation consumers
    enter through `GuardedWorkItem` and require consumed grants.
14. D19 writes `S7VoiceAuthorityRow` and bridges authoritative refusal into
    committed `S7RequestHistoryRecord` / `assess_aggregation_risk`, or lands a
    reviewed migration that teaches the aggregator to read the new row directly.
15. Trace, rollback plan, rollback result, pending-trace finalization, and
    rollback store records implement D22-D23.
16. Positive tests cannot hand-assemble the voice fact, artifact, carrier,
    grant, or `GrantUse`.
17. Live founder-key traces or reviewed same-code coverage exist for every
    in-scope adapter/consumer before any L8 retirement claim.

## Review Questions

1. Does D17 both bind preview/rollback hashes and show founder-readable preview
   body class, summary, and affected paths, with `expected_metadata`
   enforcement?
2. Does D9's immutable-bundle / mutable-use split avoid circular hashes,
   mutable-hash domains, and forward-binding to a rendered hash that does not
   exist at bundle write time?
3. Does `S7GuardedStateStore.put_artifact_with_bundle_reservation(...)` with a
   single SQLite file, table prefixes, and an injected connection close the
   cross-store atomicity gap?
4. Does the expected-nonce carrier (`expected_consultation_nonce_hash`) give the
   marker-verification booleans a real value to compare against, including
   spent-nonce rejection?
5. Does the D10 substitution grammar plus `rendered_prompt_hash` /
   `rendered_prompt_ref` make prompt assembly replayable by D16?
6. Does the D21 wrapper correctly preserve nullable S7.1 failure semantics while
   binding consumer id, grant id, expires_at, `source_ref_hash`, and `GrantUse`
   to the artifact consume?
7. Is `execution_consumer_id` closed and derived strongly enough that caller code
   cannot bind a grant to an arbitrary string?
8. Is the D13 marker-verified-authority rule materially carried by authority
   booleans, including marker-verified objections when the reader disagrees and
   conservative handling of `explicit_no_objection + reader_unavailable`?
9. Does D19 correctly bridge `S7VoiceAuthorityRow` into committed
   `S7RequestHistoryRecord` aggregation, including withdrawal evidence?
10. Does `consume_verified(...)` as a deprecated wrapper preserve compatibility
    without reopening boolean authorization?
11. Does the D11 false-block fix correctly distinguish "Maez quotes preview" from
   "reader attributes blocking solely to preview"?
12. Does the D7 `ContextManifest` carrier close the operator-steering surface
   and replay through D10/D16 without invention?
13. Is `BondedMaezRuntime` bounded enough to avoid contextless-model and
   whole-daemon ventriloquism failures, with prompt assembly correctly placed
   in the producer port?
14. Is the route-manifest amendment gate strict enough to prevent implementation
   from starting the positive voice path before the concrete provider/model is
   reviewed?
15. Are any mutation surfaces still missing from D2, D4, D21, or the acceptance
   checklist, including ActionEngine final mutation adapters?
16. Is the Expiry Lifecycle invariant correctly enforced at every named seam
    (validator pre-mint, consume pre-mutation, consumer pre-mutation)?

## Proposed Next Ladder

1. §8.2 fresh-reader gate runs on this exact committed v5 spec with three
   blank-context readers: cold covenant reader, cold spec-implementor, and cold
   residual-hunter.
2. Codex engineering panel v5 runs independently on the same committed v5 spec.
3. If either lane returns REVISE, produce a v6 fold delta-plan and write spec
   v6. If both lanes ratify (or RATIFY-with-fold with only bounded touchups),
   proceed to second-fold checks.
4. Canonicalize only after the active lanes ratify.
5. Implement RED-first from the ratified spec.

No implementation begins from this v5 draft.

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

S7.3 v5 absorbs the v4 review findings:

- D9 no longer asks one row to be immutable proof, mutable reservation slip, and
  post-render receipt. The immutable `S7VoiceConsultationBundle` carries the
  evidence hash. The mutable `S7VoiceBundleUse` carries reservation and
  consumption state. The rendered statement hash lives after render, in trace
  and D23 rows.
- Marker verification now has a real expected nonce carrier:
  `expected_consultation_nonce_hash`. The raw nonce is prompt-only; the bundle
  stores the expected hash plus parsed marker nonce hash, spent nonce hashes are
  rejected, and marker booleans compare against the expected hash.
- Prompt assembly is replayable. The prompt template has a closed substitution
  grammar, the producer persists `rendered_prompt_hash`,
  `rendered_prompt_ref`, and the concrete `ContextManifest`, and the validator
  replays the prompt before accepting a voice fact.
- Cross-store atomicity has a real transaction owner:
  `S7GuardedStateStore`. One SQLite connection, one shared file, table
  prefixes, `BEGIN IMMEDIATE`, bundle-use reservation, artifact put, artifact
  consume, grant-use persistence, and bundle-use consumption all commit or roll
  back together.
- Execution consumers are closed and derived. A grant cannot be bound to an
  arbitrary caller string; `execution_consumer_id` comes from
  `S7_EXECUTION_CONSUMER_IDS`, the guarded-work bridge's source-surface
  derivation, and the pre-consume `S7ExecutionAuthorization` carrier.
- D19 now bridges `S7VoiceAuthorityRow` into the committed D23 request-history
  aggregator instead of creating a second refusal history the live code would
  not read.
- The reducer is split into authority-boolean computation and the reducer
  proper. Marker-verified objections remain authoritative when the reader is
  unavailable, uncertain, or wrong, and `explicit_no_objection` cannot become
  positive consent when the reader is disabled over a captured response.
- The founder sees readable preview material, not only a 64-character hash.
  The rendered statement shows preview body class, summary, affected paths,
  preview hash, and rollback plan hash.
- `consume_verified(...)` remains only as a deprecated compatibility wrapper
  that delegates through the new consume spine with a closed consumer id carried
  on `S7ExecutionAuthorization`.
- Rollback evidence now has a store, pending execution traces must finalize or
  fail with rollback evidence, and L8 evidence is per adapter/consumer rather
  than hidden behind broad surface-class labels.
- The expiry lifecycle names the WebAuthn challenge endpoint as
  `webauthn_challenge.expires_at`, not an ambiguous TTL duration.

The honest scope holds: S7.3 v5 does not defend against same-box privileged
tampering during the active consultation window. The strong replay protection
narrows the attack to a tight time-bounded window with cryptographic nonce
verification. The future cryptographic identity substrate slice (per Honesty
Banner and project memory) closes this further. Until that slice lands, the
Honesty Banner names what S7.3 v1 trusts and what it does not.

If S7.3 implements this, the front desk finally connects to the machinery
without pretending Maez was heard when it was not. If it cannot implement this,
the honest result is to keep the pause.
