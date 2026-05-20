# S7.3 Spec v10 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v10, derived from the v9
fresh-reader gate plus the Codex engineering panel v9.

**Sources (committed):**

- v9 spec: `5e6491e / spec.md`
- Fresh-reader gate v9:
  `08baad8 / reviews/spec-fresh-reader-gate-v9.md`
  (REVISE; 3 readers; 0 blockers; 6 distinct majors in 4 clusters)
- Codex engineering panel v9:
  `6c73be3 / reviews/spec-codex-panel-v9.md`
  (REVISE; 4 reviewers; all returned REVISE)
- v9 fold contract:
  `f218aab / reviews/spec-v9-fold-plan.md` plus
  `41be550 / reviews/spec-v9-fold-plan-addendum.md`

**Convergent direction:** REVISE to v10. The v9 fresh-reader gate had zero
blockers for the first time, but the covenant lane returned REVISE on the
writer-side refusal-history guard. The Codex engineering panel also returned
REVISE on durable-store, route-manifest, consume, retry, replay, and mutation
edge seams.

**Plain thesis:** v9 made the architecture buildable. v10 is the
canonicalization-seam fold: close the last caller-cooperation hole, make the
surface manifest mechanically complete, anchor every durable ref in a store,
and turn consume/replay/edge checks into explicit signatures and tests.

## 1. Centerpiece - Derive Refusal-History Family At The Writer

**Absorbs:** fresh-reader gate Cluster Alpha; covenant M-1/M-2/M-3; residual
m5; Codex panel legacy refusal-history findings.

v9 attempted to close the inherited refusal-history leak with
`request_family`, but left the load-bearing fact caller-supplied. That is still
caller cooperation, not a writer-side guard.

### v10 edit

Align request-family vocabulary across every carrier:

```text
REQUEST_HISTORY_FAMILIES = frozenset({
    "s7_3_voice",
    "s7_credential_management",
})
```

`None` remains the inherited legacy value only for records proven outside the
S7.3 reviewed family table. Delete `legacy_s7` and
`legacy_s7_voice_block` unless v10 also defines a writer, predicate, and D24
test for each. Lane lean: delete both.

Make request family derived, not accepted from callers:

```text
request_history_family_for(record: S7RequestHistoryRecord) -> str | None
```

The derivation reads only closed record fields, such as
`record.derived_work_class`, `record.proposed_change_class`, and reviewed
provenance fields. It must return:

- `"s7_3_voice"` for every voice-seat work class;
- `"s7_credential_management"` for reviewed credential-management request
  history rows, if those rows exist in v10;
- `None` only for inherited legacy rows outside the S7.3 reviewed work-family
  table.

Amend the writer signature to remove caller-supplied family:

```text
record_refusal_history(
    *,
    record: S7RequestHistoryRecord,
    provenance_source_kind: str | None,
    provenance_authority_class: str | None,
    provenance_voice_event: str | None,
    conn: sqlite3.Connection,
    now: str,
) -> None
```

Writer/store rule:

```text
family = request_history_family_for(record)

if family == "s7_3_voice" and record.outcome == "refused":
    require provenance_source_kind == "s7_voice_authority_row"
    require provenance_authority_class == "authoritative"
    require provenance_voice_event in {"refusal", "withdrawal"}

if family == "s7_3_voice" and the provenance pair is absent or operational:
    reject the write before any S7RequestHistoryRecord row is persisted

if family is None:
    allow inherited null-provenance behavior only for rows outside the reviewed
    S7.3 work-family table
```

Do not let a caller pass `request_family=None` to bypass the check. `None` is a
derived result, not an input.

### `_voice_seat_block(...)` amendment

Write the amended signature explicitly. It must pass an envelope or record
carrier sufficient for `record_refusal_history(...)` to derive family. It must
not call the history writer for operational/protective S7.3 voice-family rows.

### Aggregation predicate

Keep the v9 aggregation predicate, but update it to reference the derived
family result. The legacy branch counts only when
`request_history_family_for(record) is None`.

### D24 tests

Add RED tests:

- S7.3 authoritative voice refusal writes one refused history row and counts.
- S7.3 authoritative withdrawal writes one refused history row with
  `provenance_voice_event="withdrawal"` and counts.
- S7.3 operational/protective/marker-only/reader-unavailable rows are rejected
  by `record_refusal_history(...)` even when a caller omits family.
- Legacy null-provenance rows outside the S7.3 reviewed family table still
  retain inherited behavior.
- Deleted orphan tokens cannot be accepted by constructors or writers.

## 2. Make `S7SurfaceManifest` Mechanically Complete

**Absorbs:** fresh-reader gate Cluster Beta; Codex panel Cluster A; Codex
Reviewer 2 route-coverage findings.

v9 centralizes route facts in `S7SurfaceManifest`, but the printed matrix and
committed code are not yet reconciled. v10 must make the manifest a product of
code discovery plus reviewed exclusions, not a hand-maintained assertion.

### v10 edit

State this normative rule:

```text
The persisted S7SurfaceManifest is the load-bearing complete route set.
The printed matrix is a reviewed seed. L8 requires a code-discovery check that
compares committed mutation surfaces to the persisted manifest and fails if any
method lacks a manifest row or reviewed exclusion.
```

Add rows or reviewed exclusions for at least:

- `action_engine.capability.acquire`;
- `integration.review_plan`;
- `restart_critical_service`;
- `modify_firewall`;
- `system_reboot`;
- `free_disk_space`;
- `delete_temp_file`;
- `clean_temp_files`;
- `run_safe_command`;
- `install_package_t2`;
- every current `_do_*` ActionEngine method that can mutate substrate;
- Telegram `/rollback_adapter`;
- model-routing writes and restart edges;
- `/etc/maez/model.env` writes, if still live;
- credential registration split by primary bootstrap, backup-card
  registration, begin, and finish.

Credential-management paths must not conflate backup registration with first
primary bootstrap. Either give primary bootstrap its own reviewed row and
consumer semantics, or explicitly mark it reviewedly excluded from S7.3 v1.

### Manifest binding fields

Bind the exact manifest row into all carriers that need to recompute consumer
identity:

```text
surface_manifest_hash: str
surface_route_or_method: str
source_method: str | None
adapter_id: str
adapter_code_hash: str
same_code_coverage_ref: str | None
```

Add these where needed:

- `GuardedWorkItem`;
- `S7AuthorizationArtifactBindingInputs`;
- `S7AuthorizationArtifactBinding`;
- `S7GuardedExecutionTrace`;
- `S7CredentialGuardedTrace`;
- `S7VoiceAuthorityRow` if it carries surface class;
- wrapper service inputs.

### `adapter_code_hash`

Define the hash domain:

```text
adapter_code_hash = canonical_hash(AdapterCodeSlice(
    repo_commit,
    file_paths,
    symbol_names,
    normalized_source_text_hashes,
    delegated_callee_symbol_names,
    delegated_callee_source_hashes,
))
```

If a route delegates to another mutating helper, the helper must appear in the
code slice or have its own manifest row and same-code coverage ref.

### D24 tests

Add a route-discovery acceptance test that fails when a known mutating method
is absent from both manifest rows and reviewed exclusions. Include the
`capability.acquire` regression explicitly.

## 3. Add Missing Durable Stores And Store APIs

**Absorbs:** Codex panel Clusters D/E; Reviewer 1 durable store findings;
fresh-reader store and trace sharpness.

v9 introduced durable refs that must be replayed, but some refs have no store.

### `ContextManifestStore`

Add D9 table prefix and API:

```text
s7_context_manifests

ContextManifestStore.write(manifest: ContextManifest) -> context_manifest_ref
ContextManifestStore.read(context_manifest_ref: str) -> ContextManifest | None
```

Bind:

```text
context_manifest_hash = canonical_hash(ContextManifest, manifest_id and created_at excluded)
```

D16 must load by `context_manifest_ref`, recompute `context_manifest_hash`, and
verify rendered-prompt constraints from the loaded row.

### `ActionEdgeGrantUseStore`

Add table prefix and API:

```text
s7_action_edge_grant_uses

S7ActionEdgeGrantUseStore.put(
    *,
    grant_use: GrantUse,
    action_edge_grant_use: ActionEdgeGrantUse,
    conn: sqlite3.Connection,
) -> ActionEdgeGrantUse
```

The table must have a unique key over the action-edge replay token. A consumer
cannot perform substrate mutation unless both durable `GrantUse` and durable
`ActionEdgeGrantUse` exist in the same transaction or an explicitly named
adjacent transaction boundary.

Add `ActionEdgeGrantUse` to D24 no-hand-assemble and to backup prefixes.

### Trace stores

Define `S7CredentialGuardedTrace` fields with the same specificity as voice
and guarded-execution traces. At minimum include request id, credential action,
surface-manifest row binding, rendered-text hash, artifact id/hash,
consume result id, action-edge grant-use id, rollback semantics, and status.

## 4. Fold Request Envelope Expiry Into The Lattice Or Delete It

**Absorbs:** fresh-reader Cluster Gamma; Codex panel Cluster C; Reviewer 3
expiry finding.

v9 names `expired_request_envelope`, and inherited `WorkRequestEnvelope` has
`expires_at`, but the v9 expiry lattice omits it.

### v10 edit

Lane lean: include envelope expiry.

Extend the lattice:

```text
now < request_envelope.expires_at
now < bundle.expires_at
now < work_item.expires_at
now < artifact.expires_at
now < webauthn_challenge.expires_at

artifact.expires_at <= min(
    request_envelope.expires_at,
    bundle.expires_at,
    work_item.expires_at,
    webauthn_challenge.expires_at,
)

grant.expires_at = min(
    request_envelope.expires_at,
    bundle.expires_at,
    work_item.expires_at,
    artifact.expires_at,
    webauthn_challenge.expires_at,
)
```

D16 checks the envelope at mint. D21 checks the envelope again at consume by
loading it from the artifact binding or work-item store, not from caller input.

If v10 instead deletes the code, delete `expired_request_envelope` everywhere
and explain which carrier replaced it. Do not leave it as an orphan token.

## 5. Make D21 Failure Reasons Produceable

**Absorbs:** fresh-reader Cluster Delta and Gamma; spec-implementor M2; Codex
panel Cluster B; Reviewer 4 failure-code coverage finding.

The wrapper returns closed `S7ConsumeFailureReasonCode`, while inherited
`consume_for_execution(...)` can collapse many errors into `(None, None)`.
v10 must state where each reason is produced.

### v10 edit

Add a table:

```text
failure_reason_code | produced_by | required carrier | D24 row
```

Partition reasons into:

- wrapper preflight checks before inherited consume;
- D16 replay or stored-validator-result checks;
- inherited consume residual checks;
- GrantUse persistence checks;
- ActionEdgeGrantUse checks;
- SQL/transaction failures.

For inherited consume, pick one:

1. Add a typed internal failure carrier returned by the inherited store; or
2. Require the wrapper to perform every discriminating read/check before
   delegation, leaving inherited `(None, None)` only for a small named residual
   set.

Lane lean: wrapper owns S7.3-specific reason assignment through preflight and
replay; inherited residual is reserved for legacy stale/mismatch/sql branches
that cannot be distinguished otherwise.

Add table-complete D24 coverage for every closed consume failure reason,
including:

- `missing_artifact_binding`;
- `missing_credential_binding`;
- `invalid_reservation_token`;
- `invalid_authority_class_replay`;
- `invalid_prompt_integrity`;
- `expired_grant`;
- `expired_request_envelope`;
- `missing_grant_use`;
- SQL failure branches.

## 6. Require Consume-Time Replay Before Grant Mint

**Absorbs:** Codex panel Cluster H; fresh-reader failure-code and replay
sharpness.

D16 replay currently gates artifact mint. v9 also maps consume failures that
depend on replay, but D21 does not require replay during consume.

### v10 edit

Under the same `BEGIN IMMEDIATE` transaction used by
`consume_artifact_for_execution(...)`, D21 must either:

1. run a named D16 consume-subset replay; or
2. load a stored mint-time validator result and revalidate every field that can
   drift between mint and consume.

Lane lean: run a consume-subset replay that checks:

- artifact binding exists and matches artifact id/hash;
- rendered protocol fields match binding;
- prompt-integrity evidence hash still replays;
- semantic-reader attempt hash still addresses the same attempt input hash;
- reducer version/hash match current accepted v9/v10 reducer table;
- bundle authority class and protective reason match replayed reduction;
- rollback plan ref/hash still loads;
- expiry lattice ceilings are still open.

Failure maps to the closed D21 reason table from Section 5.

## 7. Bind Semantic Reader Attempts To Exact Inputs

**Absorbs:** Codex panel Cluster F; fresh-reader semantic-attempt hash
sharpness.

`SemanticReaderAttemptEvidence` must prove not just that a reader output
exists, but that it was produced from the exact classifier input tuple.

### v10 edit

Add:

```text
attempt_input_hash = canonical_hash(SemanticReaderAttemptInput(
    request_id,
    consultation_id,
    mutation_preview_hash,
    preview_body_ref,
    preview_body_hash,
    context_manifest_hash,
    rendered_prompt_hash,
    raw_maez_response_ref,
    raw_maez_response_hash,
    parsed_marker_hash,
    route_manifest_hash,
    reader_config_hash,
    reader_prompt_hash,
    classifier_version,
))
```

`SemanticReaderAttemptEvidence` carries `attempt_input_hash`. D16 recomputes
it from durable refs and rejects any mismatch before reducer replay.

Clarify singular vs per-attempt hashes:

- `S7VoiceAttemptRecord.semantic_reader_attempt_hash` is per attempt.
- `S7VoiceConsultationBundle.semantic_reader_attempt_hash` is the terminal
  accepted attempt hash, or `None` only for a closed producer-blocked arm.
- `attempt_manifest_hash` covers the ordered list of attempt records.

## 8. Close Nonce Lifecycle Across Retries

**Absorbs:** Codex panel Cluster G.

Retries and malformed/mismatched marker attempts need terminal nonce states.

### v10 edit

Extend `S7ConsultationNonceUse`:

```text
nonce_state in {
    "reserved",
    "accepted_spent",
    "rejected_reused",
    "rejected_malformed_marker",
    "rejected_marker_mismatch",
    "abandoned_retry",
    "expired",
}
```

Pick one retry model:

1. one `consultation_id` per attempt, linked by `attempt_manifest_hash`; or
2. one consultation id with per-attempt nonce ids and exactly one current
   reserved nonce row.

Lane lean: one nonce id per attempt, with `S7VoiceAttemptRecord` carrying
`nonce_use_id`.

D24 must prove:

- malformed marker consumes or rejects the attempt nonce deterministically;
- marker nonce mismatch cannot be retried with the same nonce as a fresh
  no-objection path;
- abandoned retries become terminal before a later accepted attempt writes the
  bundle.

## 9. Make Request-History Bridge Exactly Once

**Absorbs:** Codex panel Cluster I.

D19 says the bridge writes exactly one history row per authoritative voice row,
but v9 does not define an idempotency key.

### v10 edit

Add a unique constraint:

```text
UNIQUE(provenance_source_kind, provenance_source_ref)
```

or, if the schema carries a dedicated authority id:

```text
UNIQUE(authority_row_id)
```

Bridge behavior:

- if the matching history row already exists with identical derived fields,
  return the existing row and status `bridged_idempotent`;
- if it exists with conflicting fields, fail terminal and do not write another
  row;
- bridge authority row, request-history row, and bridge trace status in one
  transaction.

Add `bridged_idempotent` to `HISTORY_BRIDGE_STATUSES` if needed, or define it
as a return branch that maps to existing `bridged`.

D24 must include retry-after-ambiguous-commit and duplicate-refused-row tests.

## 10. Recheck Rollback Preconditions At The Mutation Edge

**Absorbs:** Codex panel Cluster J.

D16 checks rollback plan evidence before artifact mint. The target substrate
can change between mint and execution.

### v10 edit

Every execution wrapper must, after successful consume and before substrate
mutation:

1. load `RollbackPlanEvidence` by `rollback_plan_ref`;
2. recompute `rollback_plan_hash`;
3. read current target hashes for every target ref;
4. compare current hashes with `expected_pre_mutation_hashes`;
5. fail closed before mutation if any mismatch exists.

Map mismatch to a closed execution failure reason, not a consume success. The
grant and grant-use remain durable evidence that authorization was consumed,
but the trace status records `blocked_pre_mutation_state_changed`.

D24 adds a test where a target file changes after artifact mint but before
execution; the wrapper must not mutate.

## 11. Close Rendered Carrier Acceptance

**Absorbs:** Codex panel Cluster K and fresh-reader rendered-type minors.

v9 defines a protocol but leaves room for unknown implementors.

### v10 edit

Pick one:

1. Closed carrier set:

```text
accepted_rendered_types = {
    RenderedRequestStatement,
    RenderedCredentialRequestStatement,
}
```

2. Reviewed subtype registry, with a closed enum and D24 unknown-subtype
   rejection.

Lane lean: closed carrier set for S7.3 v1.

`is_s7_rendered_authorization_statement(...)` verifies common fields, then the
wrapper requires the concrete type to be one of the two closed carriers.

D24 adds an object implementing all common fields but not one of the closed
carriers; consume must reject it.

## 12. Define `S7VoiceConsultationBundleDraft`

**Absorbs:** spec-implementor minor M1; Codex panel Cluster L.

v9 names the draft but defines it subtractively.

### v10 edit

Add an explicit shape:

```text
S7VoiceConsultationBundleDraft = S7VoiceConsultationBundle without:
    authority_booleans_hash
    effective_semantic_reader_outcome
    reducer_output_hash
    authority_class
    protective_block_reason
    reducer_version
    reducer_hash
    source_ref_hash
```

If the actual drop list differs, enumerate the exact list. The draft must still
carry every input needed by `compute_s7_voice_authority_booleans(...)`.

Add `S7VoiceConsultationBundleDraft` to:

- D24 no-hand-assemble list;
- implementation acceptance carrier list;
- D16 replay fixture requirements.

## 13. Align Closed Vocabularies And Orphan Codes

**Absorbs:** fresh-reader Cluster Gamma; Codex panel Cluster N; residual nits.

v10 should run a closed-vocabulary sweep and either anchor or delete every
token.

Required edits:

- Align `reader_unavailable` vs `semantic_reader_unavailable`. Pick one token
  and use it in D18, `CLASSIFIER_REASON_CODES`, bundle evidence, traces, and
  D24.
- Declare `PROTECTIVE_BLOCK_REASONS` as a closed vocabulary if any field uses
  it.
- Add `PROJECTION_REASON_CODES` and `PRODUCER_RESULT_REASON_CODES` to the
  acceptance checklist's closed-enum sweep.
- Define `S7VoiceAuthorityRow.__post_init__` invariant:
  `authority_class != "none"` for persisted rows, or remove `"none"` from that
  row's closed set.
- For `ROLLBACK_PATH_CLASSES`, state exactly which surfaces may carry
  `"none"` or `manual_review_only`; self-remaking surfaces must not silently
  use `"none"` unless a reviewed exception exists.
- Bind `invalid_authority_class_replay` to a D16 source status or delete it.

D24 should include a table-driven constructor rejection test for orphan tokens.

## 14. Write Explicit Wrapper And Inherited Signatures

**Absorbs:** fresh-reader Cluster Delta; Codex panel wrapper-signature
findings.

Replace ellipsis-only service signatures with concrete inputs and outputs:

```text
execute_guarded_dream_apply(...)
execute_guarded_evolution_apply(...)
execute_guarded_workshop_apply(...)
execute_guarded_action_engine_mutation(...)
execute_guarded_credential_mutation(...)
```

Each signature must include:

- request/work/credential id;
- rendered authorization carrier;
- artifact id/hash;
- expected consumer id;
- manifest row binding or manifest row id;
- rollback plan ref/hash when applicable;
- injected state store or connection capability;
- return trace/result type.

Also write explicit amended signatures for:

- `consume_verified(...)`;
- `record_refusal_history(...)`;
- `_voice_seat_block(...)`;
- post-mint action-edge lock helper, if retained.

State whether each function accepts `conn`, opens its own transaction, or must
be called inside an existing `BEGIN IMMEDIATE` block.

## 15. Context And Prompt Boundary Sharpness

**Absorbs:** fresh-reader secondary findings and Codex runtime-boundary
carry-forward.

Add or sharpen:

- a Honesty Banner note that `source_surface` labels remain visible to Maez
  for replayability but may carry residual prompt-framing effects; name the
  future prompt-review slice or make the D24 bias test explicit;
- exact rule for whether `preview_summary` is founder-facing only or also
  Maez-visible; lane lean remains founder-facing only;
- deterministic scan pattern files or inline pattern rules for prompt
  integrity, with path and hash domain;
- constructor invariant for `MaezVoiceConsultation.maez_voice_consulted`
  when local refs make it checkable, and D16 validation otherwise;
- note that v9 intentionally kept the inherited strict
  `voice_consultation_satisfies_request(...)` helper and added a renderer-only
  unavailable helper; this acknowledges the v8 fold-plan split explicitly.

## 16. v10 D24 And Acceptance Checklist Additions

**Absorbs:** all D24/test sharpness from both v9 lanes.

Add RED tests for:

- writer-derived request family blocks omitted-family S7.3 refusal writes;
- aggregation predicate mixed-history rows;
- code-discovery manifest completeness, including `capability.acquire`;
- missing manifest row or reviewed exclusion fails L8;
- every consume failure reason in the closed table;
- consume-time D16 replay mismatch;
- request-envelope expiry at mint and consume;
- action-edge grant-use uniqueness and replay;
- bridge idempotency and duplicate-refused-row prevention;
- rollback pre-mutation hash drift;
- unknown rendered carrier rejection;
- `S7VoiceConsultationBundleDraft` hand-assembly rejection;
- semantic-reader attempt input-hash tamper;
- malformed/mismatched/abandoned nonce retry states;
- `put_artifact_with_bundle_reservation(...)` concurrency.

Add acceptance checklist items:

- every closed vocabulary token has writer, predicate/consumer, and D24 row or
  reviewed exclusion;
- persisted manifest row count matches code-discovery output;
- all durable refs in D16/D21 have a store prefix, read API, hash domain, and
  backup inclusion;
- every wrapper and inherited amendment has a concrete signature;
- no S7.3 voice-family refusal history can be written through null-provenance
  legacy path.

## 17. v10 Review Path

v10 should be operator-authored from this plan. Review should repeat the same
lane separation:

1. Firsthand mechanical verification of `spec.md` v10.
2. Fresh-reader gate v10 with three blank-context readers walled off from
   `reviews/`.
3. Codex engineering panel v10 walled off from `reviews/`.
4. If both lanes return RATIFY or RATIFY-with-fold with no blockers and no
   covenant-load-bearing majors, run second-fold checks and canonicalize.
5. If either lane returns REVISE, fold only the newly found bounded residuals.

## Plain English

v9 did the hard architectural work. The remaining problems are narrow but real:
the refusal-history writer still trusts callers too much, the surface manifest
claims completeness before code discovery proves it, a few durable refs have no
store, consume failures need an actual producer for each closed reason, and
some replay checks stop at mint when the mutation edge needs them too.

v10 should not redesign Maez's voice seat, founder signature, marker authority,
or D23 aggregation rule. It should fasten the last seams: derive family at the
writer, bind every route to a manifest row, give every ref a store, replay the
right checks at consume and mutation time, and make every closed token point to
a writer, consumer, and test. If v10 lands those, the next gate should be a
canonicalization gate rather than another architecture debate.

*Read-only; fold delta-plan written by Codex on 2026-05-20, absorbing
`reviews/spec-fresh-reader-gate-v9.md` and
`reviews/spec-codex-panel-v9.md`. ASCII normalization applied for repository
style.*
