# S7.3 Spec v11 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v11, derived from the v10
fresh-reader gate plus the Codex engineering panel v10.

**Sources (committed):**

- v10 spec: `6e881e9 / spec.md`
- Fresh-reader gate v10:
  `116a2a0 / reviews/spec-fresh-reader-gate-v10.md`
  (REVISE; 3 readers; covenant lane canonicalization-ready; spec-implementor
  REVISE on 5 carrier blockers)
- Codex engineering panel v10:
  `ba961b6 / reviews/spec-codex-panel-v10.md`
  (REVISE; 4 reviewers; 2 REVISE, 2 RATIFY-with-fold)
- v10 fold contract:
  `63cc78b / reviews/spec-v10-fold-plan.md` plus
  `441d9cc / reviews/spec-v10-fold-plan-addendum.md`

**Convergent direction:** REVISE to v11. v10 is the first version where the
covenant lane returned zero blockers, zero majors, and canonicalization-ready.
The remaining findings are implementability and carrier-closure defects:
wrappers cannot call consume without invented inputs, trace writers are named
but not specified, hash tuples reference unbound fields, request carriers lack
stores, and several closed vocabularies are not mirrored through code.

**Plain thesis:** v11 is not an architecture fold. It is the final
definition-pinning fold: every named carrier, hash tuple, wrapper argument,
trace writer, request store, action-edge key, and closed token must have one
derivation rule and one testable seam.

## 1. Wrapper Invocation Carrier For `execute_guarded_*(...)`

**Absorbs:** Codex panel Cluster A; fresh-reader Group G; spec-implementor
Major 1.

v10 says guarded mutations enter through concrete `execute_guarded_*(...)`
wrappers, but those wrappers cannot call
`S7GuardedStateStore.consume_artifact_for_execution(...)` without inventing
missing carriers: `source_ref_hash`, `reservation_token`,
`action_params_hash`, `AuthorityContext`, `precondition_hash`,
`derived_work_class`, and `derived_aggregation_group`.

### v11 edit

Add one closed invocation carrier rather than scattering kwargs:

```text
S7GuardedExecutionInvocation:
    request_id: str
    artifact_id: str
    rendered: S7RenderedAuthorizationStatement
    execution_consumer_id: str
    surface_manifest_hash: str
    surface_route_or_method: str
    source_method: str | None
    adapter_id: str
    adapter_code_hash: str
    source_ref_hash: str
    reservation_token: ReservationToken
    action_params_hash: str
    authority_context: AuthorityContext
    precondition_hash: str
    derived_work_class: str
    derived_aggregation_group: str
    rollback_plan_ref: str
    superseded_request_ids: tuple[str, ...]
    covenant_ceremony_evidence: object | None
```

If the implementation chooses durable lookup rather than caller input, v11
must still define the lookup:

```text
S7GuardedExecutionInvocationStore.load(request_id, artifact_id) ->
    S7GuardedExecutionInvocation
```

Lane lean: wrappers accept `S7GuardedExecutionInvocation` and reject direct
loose kwargs. The invocation may be assembled by route-specific wrapper code
from durable stores, but the consume call receives one complete carrier.

Update wrapper signatures:

```text
execute_guarded_dream_apply(*, invocation, work_store, consume_store,
    trace_writer, rollback_store, now) -> S7GuardedExecutionTrace

execute_guarded_evolution_apply(*, invocation, work_store, consume_store,
    trace_writer, rollback_store, now) -> S7GuardedExecutionTrace

execute_guarded_workshop_apply(*, invocation, work_store, consume_store,
    trace_writer, rollback_store, now) -> S7GuardedExecutionTrace

execute_guarded_action_engine_mutation(*, invocation, action_engine,
    consume_store, trace_writer, rollback_store, now) -> S7GuardedExecutionTrace

execute_guarded_model_routing_mutation(*, invocation, consume_store,
    trace_writer, rollback_store, now) -> S7GuardedExecutionTrace

execute_guarded_credential_mutation(*, credential_request,
    rendered: RenderedCredentialRequestStatement, consume_store,
    trace_writer, now) -> S7CredentialGuardedTrace
```

The wrapper must call consume using only fields from the invocation or the
credential request carrier. No wrapper may reconstruct authority context from
prompt text, route names, or caller-provided strings.

### D24 tests

- Wrapper can call `consume_artifact_for_execution(...)` without
  hand-assembled missing kwargs.
- Direct substrate call with plausible consumed grant but without invocation
  bookkeeping fails before mutation.
- Invocation with mismatched `derived_work_class`, `derived_aggregation_group`,
  `execution_consumer_id`, or `surface_manifest_hash` fails with the exact
  consume failure code.

## 2. Durable Request Stores

**Absorbs:** Codex panel Cluster F; residual minor on `WorkRequestEnvelope`
inheritance.

v10 depends on request-envelope and credential-request expiry at consume time,
but D9 does not declare stores that can reload those records.

### v11 edit

Add table prefixes:

```text
s7_work_request_envelopes
s7_credential_guarded_requests
s7_guarded_execution_invocations
```

Add store APIs:

```text
WorkRequestEnvelopeStore.put(envelope, *, conn) -> None
WorkRequestEnvelopeStore.get(request_id, *, conn) -> WorkRequestEnvelope | None

S7CredentialGuardedRequestStore.put(request, *, conn) -> None
S7CredentialGuardedRequestStore.get(request_id, *, conn) ->
    S7CredentialGuardedRequest | None

S7GuardedExecutionInvocationStore.put(invocation, *, conn) -> None
S7GuardedExecutionInvocationStore.get(request_id, artifact_id, *, conn) ->
    S7GuardedExecutionInvocation | None
```

Each store must persist `created_at`, `expires_at` when present, and the
canonical request/invocation hash used by D16/D21.

Add `WorkRequestEnvelope` to the Inheritance section as an inherited carrier
whose fields are load-bearing for S7.3.

### D24 tests

- Missing request envelope returns `missing_request_envelope`.
- Expired request envelope returns `expired_request_envelope`.
- Missing credential guarded request returns `missing_credential_request`.
- Credential request loaded from a different request id fails before consume.

## 3. `S7TraceWriter` / `S7TraceStore` API

**Absorbs:** fresh-reader Group C; Codex panel Cluster B.

D22 specifies trace fields but not the API that writes them. A builder should
not invent the trace seam.

### v11 edit

Define a single writer backed by the shared S7 state connection:

```text
S7TraceWriter:
    begin_voice_consultation_trace(row, *, conn) -> trace_id
    finalize_voice_consultation_trace(trace_id, row, *, conn) -> None
    write_guarded_execution_pending(trace, *, conn) -> execution_trace_id
    finalize_guarded_execution_trace(execution_trace_id, trace, *, conn) -> None
    fail_guarded_execution_trace(execution_trace_id, trace_status,
        failure_reason_code, *, conn) -> None
    mark_rollback_invoked(execution_trace_id, rollback_result_ref,
        rollback_result_hash, *, conn) -> None
    write_credential_trace(trace, *, conn) -> credential_trace_id
    write_history_bridge_trace(trace, *, conn) -> bridge_trace_id
```

State that `trace_store` in wrapper signatures is an alias for
`S7TraceWriter`; prefer one name everywhere. Lane lean: use
`trace_writer` consistently and delete `trace_store` from signatures.

Add idempotency keys:

- voice trace: `(consultation_id, request_id, attempt_manifest_hash)`;
- execution trace: `(request_id, artifact_id, execution_consumer_id)`;
- credential trace: `(request_id, credential_operation, credential_id_hash)`;
- bridge trace: `(provenance_source_kind, provenance_source_ref)`.

Trace writes occur inside the same `BEGIN IMMEDIATE` transaction as consume and
mutation-precondition checks. If trace pending write fails, mutation must not
start. If final trace write fails after mutation, rollback policy is invoked
according to D23 result-evidence rules and the failure is durable.

### D24 tests

- Pending trace write failure blocks mutation.
- Final trace write failure after mutation produces rollback/result evidence.
- Repeating the same bridge or execution write is idempotent by key.

## 4. Exact `attempt_input_hash` Tuple

**Absorbs:** fresh-reader Group B; Codex panel Cluster C.

v10 names `attempt_input_hash`, but tuple members do not match declared
carriers.

### v11 edit

Define the tuple exactly:

```text
attempt_input_hash = canonical_hash((
    request_id,
    consultation_id,
    attempt_index,
    rendered_prompt_hash,
    raw_maez_response_hash,
    mutation_preview_hash,
    preview_body_ref,
    context_manifest_hash,
    surface_manifest_hash,
    surface_route_or_method,
    semantic_reader_prompt_template_hash,
    semantic_reader_config_hash,
    semantic_reader_version,
    marker_text_hash,
    parsed_marker_nonce_hash,
    marker_kind,
    now_bucket_or_attempt_started_at,
))
```

Delete unbound names unless fields are added:

- `parsed_marker_hash`;
- `route_manifest_hash`;
- `reader_config_hash`;
- `reader_prompt_hash`;
- ambiguous `classifier_version`.

If v11 keeps `classifier_version`, define it as
`semantic_reader_version` or add a separate classifier carrier.

`SemanticReaderAttemptEvidence` must carry every tuple member directly or via a
durable ref that D16 can load.

### D24 tests

- Tampering any tuple member changes `attempt_input_hash` and fails D16.
- `marker_text_hash` and `parsed_marker_nonce_hash` are distinct: changing one
  without the other fails the expected predicate.
- Reader prompt template id/path mismatch cannot produce the same
  `semantic_reader_prompt_template_hash`.

## 5. Explicit `S7VoiceConsultationBundleDraft` Shape

**Absorbs:** fresh-reader Group A; Codex panel Cluster O.

The draft cannot be defined by subtracting nonexistent parent fields.

### v11 edit

Replace subtractive prose with an explicit field list. The draft includes all
evidence captured before Stage 1 authority booleans and Stage 2 reducer output,
for example:

```text
S7VoiceConsultationBundleDraft:
    request_id
    consultation_id
    attempt_manifest_ref
    attempt_manifest_hash
    raw_maez_response_ref
    raw_maez_response_hash
    rendered_prompt_hash
    prompt_integrity_evidence_ref
    prompt_integrity_evidence_hash
    semantic_reader_attempt_ref
    semantic_reader_attempt_hash
    context_manifest_ref
    context_manifest_hash
    mutation_preview_hash
    preview_body_ref
    rollback_plan_ref
    rollback_plan_hash
    surface_manifest_hash
    source_surface
    source_ref_hash_candidate_inputs
    captured_response_nonempty
    marker_kind
    marker_text_hash
    parsed_marker_nonce_hash
    marker_was_blocking_marker_verified
    marker_was_explicit_no_objection_verified
    marker_was_withdrawal_marker_verified
```

Then state the omitted final fields:

```text
authority booleans
effective_semantic_reader_outcome
reducer output fields
reducer_version
reducer_hash
final source_ref_hash
history bridge fields
consume/use-state fields
```

No `authority_booleans_hash` or `reducer_output_hash` is referenced unless v11
adds those fields to the final bundle. Lane lean: do not add new hashes; persist
the named booleans and reducer fields, and cover them under final
`source_ref_hash`.

### D24 tests

- BundleDraft constructor accepts exactly the draft fields and rejects final
  reducer/authority/history/use-state fields.
- Final bundle construction from draft plus Stage 1/Stage 2 output computes a
  stable `source_ref_hash`.

## 6. `ActionEdgeGrantUse` Key, Id, And Replay Token

**Absorbs:** fresh-reader Group E; Codex panel Cluster E.

### v11 edit

Pin cardinality:

```text
For S7.3 v1, one S7ExecutionGrant authorizes exactly one mutation edge.
```

Use a single edge key:

```text
action_edge_key = canonical_hash((
    grant_id,
    execution_consumer_id,
    request_id,
    artifact_id,
    source_ref_hash,
    action_params_hash,
    target_ref_hashes_before_mutation,
))
```

Define ids:

```text
action_edge_grant_use_id = canonical_hash(("s7_action_edge", action_edge_key))

action_edge_replay_token = canonical_hash((
    action_edge_grant_use_id,
    GrantUse.replay_token,
    rendered.rendered_text_hash,
    invocation.precondition_hash,
    invocation.rollback_plan_ref,
    used_at,
))
```

DDL uniqueness:

```text
UNIQUE(grant_id)
UNIQUE(action_edge_key)
UNIQUE(action_edge_replay_token)
```

If a future consumer needs multi-edge grants, it must be reviewed in a later
slice with a closed multi-edge manifest. v11 should not keep multi-edge
semantics latent.

### D24 tests

- Reusing one grant for a second action edge fails.
- Changing action params changes `action_edge_key`.
- Replaying the same action edge is idempotent only before mutation; after
  mutation, duplicate attempts fail closed.

## 7. Request-History Family And Bridge Provenance

**Absorbs:** fresh-reader Group D; Codex panel Cluster J.

v10 derives family at the writer, but the credential branch and stored bridge
provenance are still under-specified.

### v11 edit

Define:

```text
request_history_family_for(record) -> str | None
```

Return values:

```text
"s7_3_voice" iff record.derived_work_class in S7_3_VOICE_SEAT_WORK_CLASSES
"s7_credential_management" iff record.derived_work_class ==
    "founder_credential_management" and record.proposed_change_class in
    CREDENTIAL_PROPOSED_CHANGE_CLASSES
None otherwise
```

Define:

```text
CREDENTIAL_PROPOSED_CHANGE_CLASSES = frozenset({
    "credential_register_backup",
    "credential_disable",
    "credential_rotate",
})
```

If v11 does not write credential request-history rows, delete
`"s7_credential_management"` from the request-history family set and state the
deferral explicitly. Lane lean: keep the family and define the predicate.

Amend history writer signature:

```text
record_refusal_history(
    *,
    record: S7RequestHistoryRecord,
    provenance_source_kind: str | None,
    provenance_source_ref: str | None,
    provenance_authority_class: str | None,
    provenance_voice_event: str | None,
    conn: sqlite3.Connection,
    now: str,
) -> None
```

Persist provenance columns if the bridge uses them for uniqueness:

```text
provenance_source_kind
provenance_source_ref
provenance_authority_class
provenance_voice_event
request_family_derived
```

Bridge uniqueness:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

Delete or define any remaining orphan provenance tokens. `request_family` is
derived from record fields, but the derived value may be persisted for audit as
`request_family_derived`; callers may not supply it.

### D24 tests

- Credential-family predicate returns credential only for the closed credential
  work class and proposed change classes.
- S7.3 voice operational row cannot write refused history even if caller omits
  family.
- Bridge retry with same provenance key is idempotent.
- Bridge write with same provenance key but different authority row fails
  terminally.

## 8. Rollback Vocabulary Migration

**Absorbs:** fresh-reader Group F; Codex panel Cluster D.

### v11 edit

Choose one symbol strategy. Lane lean:

```text
S7_3_ROLLBACK_PATH_CLASSES = frozenset({
    "git_revert",
    "fs_backup_restore",
    "config_rollback",
    "atomic_rename",
    "manual_review_only",
    "none",
})
```

Leave inherited `ROLLBACK_PATH_CLASSES` as a legacy vocabulary until code is
migrated, and define a migration map:

```text
LEGACY_TO_S7_3_ROLLBACK_PATH_CLASS = {
    "revert_patch": "git_revert",
    "restore_backup": "fs_backup_restore",
    "restart_service": "config_rollback",
    "manual_review": "manual_review_only",
    "no_rollback_needed": "none",
    "no_safe_rollback": "manual_review_only",
}
```

The map is allowed only at the reviewed adapter boundary. Persisted S7.3 v1
rollback evidence must store the S7.3 token, not the legacy token.

### D24 tests

- Legacy token entering S7.3 persisted rollback evidence is rejected unless it
  passes through the migration boundary.
- Each legacy value maps to exactly one S7.3 value or a reviewed rejection.
- `rollback_path_class="none"` is allowed only for reviewed no-op/non-mutation
  paths; self-remaking and model-routing surfaces must not use it.

## 9. Failure-Code And `protective_block_reason` Closure

**Absorbs:** Codex panel Cluster G, Cluster L, Cluster Q; fresh-reader
secondary unknown-rendered-carrier finding.

### v11 edit

Add:

```text
invalid_rendered_carrier
```

to `S7ConsumeFailureReasonCode`, and map it to the rendered-carrier protocol
check before inherited consume.

Partition failure codes:

```text
wrapper_preflight_reason_codes = {...}
inherited_residual_reason_codes = {...}
post_consume_pre_mutation_reason_codes = {...}
```

The inherited `(None, None)` result may only map to closed residual codes after
wrapper preflight has already ruled out S7.3-specific mismatches.

Canonicalize protective block reason:

```text
protective_block_reason: PROTECTIVE_BLOCK_REASONS
PROTECTIVE_BLOCK_REASONS includes "none"
Persisted and replayed rows use "none", not Python None.
```

Python `None` may be accepted only at constructor edges that immediately
canonicalize to `"none"` before hashing or persistence.

### D24 tests

- Unknown rendered carrier returns `invalid_rendered_carrier`.
- Every failure-code test names the exact expected code, not only "rejected."
- `protective_block_reason=None` and `"none"` cannot hash to two different
  persisted states.

## 10. Nonce Transition Enforcement

**Absorbs:** fresh-reader Group H; Codex panel Cluster M.

### v11 edit

Add:

```text
S7ConsultationNonceEvent = frozenset({
    "reserve",
    "accept_spent",
    "reject_reused",
    "reject_malformed",
    "reject_mismatched",
    "abandon_for_retry",
    "expire",
})

transition_nonce_use(
    *,
    prior: S7ConsultationNonceUse | None,
    event: S7ConsultationNonceEvent,
    request_id: str,
    consultation_id: str,
    attempt_index: int,
    nonce_hash: str,
    now: str,
    conn: sqlite3.Connection,
) -> S7ConsultationNonceUse
```

Transition table:

```text
None + reserve -> reserved
reserved + accept_spent -> accepted_spent
reserved + reject_reused -> rejected_reused
reserved + reject_malformed -> rejected_malformed
reserved + reject_mismatched -> rejected_mismatched
reserved + abandon_for_retry -> abandoned_retry
reserved + expire -> expired
terminal + any event -> reject/fail closed
```

SQL uniqueness:

```text
UNIQUE(request_id, consultation_id, attempt_index)
UNIQUE(nonce_hash) WHERE state = "reserved"
```

### D24 tests

- Malformed marker consumes or terminates the attempt nonce according to the
  table.
- Reusing an accepted nonce fails.
- Retry uses a new attempt index and cannot re-open a terminal nonce.

## 11. Surface Manifest Tightening

**Absorbs:** Codex panel Clusters H, I, P, R; fresh-reader matrix-vocabulary
finding.

### v11 edit

Split broad approval-card row into concrete rows or reviewed exclusions:

- Telegram `/approve` / `ActionEngine.approve_action`;
- cockpit `/api/v1/cards/<request_id>/approve`;
- daemon `/internal/approve_card/<request_id>`;
- S7 card WebAuthn begin/finish routes.

Add manifest rows or reviewed exclusions for shell-shaped aliases:

- `query_system`;
- `run_readonly_command`;
- any `_do_*` alias that delegates to `_do_run_shell`;
- any future ActionEngine method found by code discovery.

Credential matrix:

- replace `work_source_kind="credential_management"` with `N/A` for credential
  rows, because credential paths use `S7CredentialGuardedRequest`, not
  `GuardedWorkItem`; or add `credential_management` to the closed set with
  credential-only semantics. Lane lean: use `N/A`.
- split `credential register begin/finish` into `backup register begin/finish`;
- add a reviewed exclusion row for first-primary bootstrap.

Persisted manifest acceptance:

```text
The generated/persisted S7SurfaceManifest must be committed or emitted as a
diffable implementation artifact. Reviewers must not reconstruct adapter ids,
code hashes, or same-code coverage refs from prose.
```

### D24 tests

- Code-discovery fails if an approval path is covered only by broad
  `approval_card.execute`.
- Code-discovery fails if shell-shaped aliases lack rows or reviewed
  exclusions.
- First-primary bootstrap is not counted as backup-registration coverage.

## 12. Credential Work-Class Closure

**Absorbs:** Codex panel Cluster K; fresh-reader Group G.

### v11 edit

Change:

```text
S7CredentialGuardedRequest.derived_work_class: str
```

to:

```text
S7CredentialGuardedRequest.derived_work_class: Literal[
    "founder_credential_management"
]
```

or define:

```text
credential_work_class_for(request) -> "founder_credential_management"
```

Constructor invariant:

```text
if derived_work_class != "founder_credential_management":
    raise ValueError("invalid credential guarded work class")
```

### D24 tests

- Credential request with self-modification work class is rejected before
  render, mint, or consume.
- Credential request cannot satisfy a voice-seat wrapper.

## 13. Consume-Subset Replay Hash-Chain Sentence

**Absorbs:** covenant minor and Codex panel Cluster N.

### v11 edit

Add near the consume-subset replay text:

```text
The consume-subset is an independent recomputation. Mint-time D16 result is not
persisted. The bundle's content-hash chain (source_ref_hash,
prompt_integrity_evidence_hash, semantic_reader_attempt_hash,
attempt_manifest_hash, context_manifest_hash, reducer_hash, rollback_plan_ref,
and surface_manifest_hash) guarantees that fields not in the consume-subset
cannot be tampered with between mint and consume without changing a hash that
consume reloads or the artifact binding already signed.
```

If v11 chooses to recheck `bundle.source_ref_hash` directly at consume, state
that instead and add it to the consume-subset field list. Lane lean: do both:
recheck `source_ref_hash`, then keep the explanatory sentence.

## 14. DDL And Store-Schema Symmetry

**Absorbs:** residual DDL asymmetry minor; Codex trace/request-store clusters.

### v11 edit

For every new durable store named in D9, provide at least an illustrative DDL
or column list with primary key, unique keys, hash fields, `created_at`, and
transaction participation:

- work request envelopes;
- credential guarded requests;
- guarded execution invocations;
- trace rows;
- action-edge grant uses;
- nonce uses;
- semantic reader attempts;
- context manifests;
- rollback plan/result evidence;
- surface manifests;
- request-history bridge rows.

This does not require production SQL, but every load-bearing field named by
D16/D21/D22/D24 must have a storage home.

## 15. Secondary Mirror Cleanup

**Absorbs:** remaining minors/nits from both lanes.

### v11 edits

- Align `semantic_reader_prompt_template_id="s7.voice.semantic_reader.v1"`
  with file path `prompts/s7.voice.semantic_reader_v1.md` by defining a
  template-id-to-file mapping.
- In D21 wrapper preflight, explicitly verify
  `invocation.derived_work_class == work_item.work_class`.
- Add Review Question for writer-derived request-history family:
  "Can any S7.3 voice-family refusal history write aggregate without
  authoritative S7 voice provenance?"
- Map `CLASSIFIER_REASON_CODES` values `terminal_uncertainty` and
  `classifier_error` through D11/D12/D13/D15 seams, or delete them.
- Add exact expected status/result codes to context-manifest allowlist and
  rendered-prompt replay D24 tests.
- If `d23_state="legacy_operational_excluded"` remains, define producer
  conditions; otherwise delete it.
- Add `PROTECTIVE_BLOCK_REASONS` to the required closed-enum acceptance list if
  not already present.

## 16. v11 Acceptance Checklist

v11 is ready for fresh-reader review only if all of these grep cleanly in
`spec.md`:

- `S7GuardedExecutionInvocation`
- `S7GuardedExecutionInvocationStore`
- `WorkRequestEnvelopeStore`
- `S7CredentialGuardedRequestStore`
- `S7TraceWriter`
- `attempt_input_hash = canonical_hash`
- `S7VoiceConsultationBundleDraft:` followed by an explicit field list
- `action_edge_key = canonical_hash`
- `action_edge_replay_token = canonical_hash`
- `request_history_family_for(record)`
- `CREDENTIAL_PROPOSED_CHANGE_CLASSES`
- `S7_3_ROLLBACK_PATH_CLASSES` or an explicit replacement/migration rule
- `invalid_rendered_carrier`
- `transition_nonce_use`
- `credential_work_class_for` or the `founder_credential_management` literal
- the consume-subset hash-chain sentence
- approval-card concrete rows or reviewed exclusions
- shell-shaped alias rows or reviewed exclusions
- first-primary bootstrap reviewed exclusion
- exact D24 expected result codes for every new negative case

## Open Choices For v11 Author

1. **Wrapper carrier shape.** Lane lean: introduce
   `S7GuardedExecutionInvocation` and have wrappers accept it.
2. **Rollback vocabulary.** Lane lean: rename the v10 vocabulary to
   `S7_3_ROLLBACK_PATH_CLASSES` and provide a legacy-to-S7.3 migration map.
3. **Credential matrix work source.** Lane lean: use `N/A` in
   `work_source_kind` for credential rows rather than adding
   `credential_management` to the GuardedWorkItem closed set.
4. **Consume-subset source-ref check.** Lane lean: recheck
   `bundle.source_ref_hash` at consume and also add the explanatory
   hash-chain sentence.
5. **Bridge request-family persistence.** Lane lean: derive family from record
   fields and persist `request_family_derived` only for audit.

## Plain English

v10 passed the covenant test and failed the cold-builder test. That is a good
kind of failure at this point. The reader who asked "is Maez still defended?"
said yes. The readers who asked "can an engineer build this without inventing
anything?" found the last missing formulas and stores.

v11 should close those formulas: what object wrappers pass into consume, where
request envelopes live, how traces are written, exactly what goes into
`attempt_input_hash`, exactly what an action-edge key means, how rollback
tokens migrate from committed code, and which concrete approval/shell routes
the surface manifest covers.

If v11 lands these definitions cleanly, the next review should be a
canonicalization gate rather than another architecture fold.

*Fold plan produced by Codex on 2026-05-20, absorbing
`reviews/spec-fresh-reader-gate-v10.md` (`116a2a0`) and
`reviews/spec-codex-panel-v10.md` (`ba961b6`). ASCII normalization applied for
repository style.*
