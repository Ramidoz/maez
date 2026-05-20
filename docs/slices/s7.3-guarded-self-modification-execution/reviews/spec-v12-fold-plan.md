# S7.3 Spec v12 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v12, derived from the v11
fresh-reader gate plus the Codex engineering panel v11.

**Sources (committed):**

- v11 spec: `2bfdbd6 / spec.md`
- Fresh-reader gate v11:
  `ac65567 / reviews/spec-fresh-reader-gate-v11.md`
  (RATIFY-with-fold; covenant RATIFY and canonicalization-ready; residual
  found three manifest-dependency majors)
- Codex engineering panel v11:
  `23978af / reviews/spec-codex-panel-v11.md`
  (REVISE; four reviewers; no architecture finding; canonicalization-blocking
  engineering consistency findings)
- v11 fold contract:
  `02ec7bb / reviews/spec-v11-fold-plan.md` plus
  `30af156 / reviews/spec-v11-fold-plan-addendum.md`

**Convergent direction:** REVISE to v12 as a fold-contract round. v11 is the
first S7.3 version where the covenant lane returned RATIFY and the aggregate
fresh-reader gate returned RATIFY-with-fold. The v12 fold does not move
architecture. It closes the final consistency layer: storage, signatures,
closed values, replay domains, and manifest derivations must agree
byte-for-byte.

**Plain thesis:** v12 is the canonicalization-consistency fold. The spec already
names the right covenant objects. v12 makes those objects round-trip through
stores, consume APIs, trace writes, reducer rows, nonce state, credential
vocabularies, and surface-manifest derivations without silent implementor
invention.

## Must-Cover Checklist

The v12 spec author must land all seventeen items below as named edits, plus
the two fresh-reader carry-forwards in Section 18. None may be buried in a
generic cleanup pool.

| # | Item | v12 section |
|---|---|---|
| 1 | Trace storage atomicity | Section 1 |
| 2 | Invocation carrier vs loose consume API | Section 2 |
| 3 | Request/invocation store round-trip | Section 3 |
| 4 | ActionEdgeGrantUse DDL and replay domain | Section 4 |
| 5 | Inherited failure partition | Section 5 |
| 6 | Concrete derivation rows | Section 6 |
| 7 | Approval-card wrapper/remap seam | Section 7 |
| 8 | Credential source-method and matrix `N/A` normalization | Section 8 |
| 9 | Protective reason canonicalization | Section 9 |
| 10 | Nonce DDL and partial unique alignment | Section 10 |
| 11 | Credential trace idempotency key | Section 11 |
| 12 | First-primary bootstrap non-mintable | Section 12 |
| 13 | Parent `action_engine_final_mutate` non-mintable | Section 13 |
| 14 | `grant_id` derivation | Section 14 |
| 15 | Final bundle marker replay path | Section 15 |
| 16 | Request-family caller-supplied closure | Section 16 |
| 17 | Stale wording and signature polish | Section 17 |
| C1 | Bridge UNIQUE menu wording cleanup | Section 18 |
| C2 | D24 wrapper-invocation negative test row | Section 18 |

## 1. Trace Storage Atomicity

**Absorbs:** Codex panel Cluster A; Codex reviewers 2, 3, and 4.

v11 contradicts itself. D9 says S7.3 uses one SQLite file,
`memory/s7_3_guarded_self_modification/state.sqlite3`, includes `s7_traces` in
that table-prefix namespace, and requires trace writes to participate in the
same `BEGIN IMMEDIATE` transaction as consume and mutation-precondition checks.
D22 later says traces live in a separate `traces.sqlite3`.

### v12 edit

Pin one storage story:

```text
S7.3 uses one SQLite file:
memory/s7_3_guarded_self_modification/state.sqlite3
```

`s7_traces` is a table prefix inside that file. `S7TraceWriter` writes through
the same injected SQLite connection used by:

- artifact consume;
- `GrantUse` insert;
- `ActionEdgeGrantUse` insert;
- mutation-edge rollback precheck;
- pending/final/failed trace writes;
- request-history bridge trace writes.

D22 may keep the trace schema, but must not name `traces.sqlite3`. If any
future slice wants an attached or separate trace database, that future slice
must specify cross-store atomicity explicitly. S7.3 v12 does not use `ATTACH`.

### D24 test

Add a trace atomicity RED test:

```text
When pending trace insert fails inside the guarded transaction, consume,
GrantUse, ActionEdgeGrantUse, rollback precheck status, and substrate mutation
are all absent after rollback.
```

## 2. Invocation Carrier vs Loose Consume API

**Absorbs:** Codex panel Cluster B; Codex reviewers 2, 3, and 4.

v11 says wrappers pass one complete `S7GuardedExecutionInvocation`. The guarded
consume API still exposes loose kwargs. D24 then says wrappers call consume
using the invocation carrier without inventing loose kwargs. That leaves two
contracts.

### v12 edit

Pick the carrier contract.

Lane lean:

```text
S7GuardedStateStore.consume_artifact_for_execution(
    *,
    invocation: S7GuardedExecutionInvocation,
    now: datetime,
    connection: sqlite3.Connection | None = None,
    after_consume_before_commit: Callable[[S7ConsumeResult], object] | None = None,
) -> S7ConsumeResult
```

The public guarded consume API accepts `invocation`, not loose consume kwargs.

If implementation needs a lower-level primitive to call the inherited store,
v12 names exactly one verifier:

```text
unpack_guarded_execution_invocation(
    invocation: S7GuardedExecutionInvocation,
    *,
    invocation_store: S7GuardedExecutionInvocationStore,
    now: datetime,
) -> InheritedConsumeInputs
```

This helper must:

1. load or recompute the complete invocation;
2. verify `guarded_execution_invocation_hash`;
3. verify `rendered.precondition_hash == invocation.precondition_hash`;
4. verify `rendered.request_id == invocation.request_id`;
5. verify `invocation.execution_consumer_id` matches the surface manifest;
6. produce the inherited loose fields.

No wrapper may construct inherited loose fields directly.

### D24 test

Add:

```text
Calling public guarded consume with loose kwargs fails type/validation before
any inherited consume call. Calling it with a tampered invocation hash returns
invalid_invocation_replay.
```

## 3. Request And Invocation Store Round-Trip

**Absorbs:** Codex panel Cluster C; Codex reviewer 2 blocker 3.

v11 store APIs promise full objects, but illustrative DDL stores only hashes
and a subset of fields. That is acceptable only if the tables are explicitly
reconstruction indexes over other durable refs and reverify the full hash.

### v12 edit

Pick one rule for each store.

Lane lean: reconstruction refs plus hash verification, not duplicating every
large nested object.

For `WorkRequestEnvelopeStore`:

```text
WorkRequestEnvelopeStore.get(request_id) -> WorkRequestEnvelope
```

must reconstruct the envelope from stored columns and durable refs, then verify:

```text
canonical_hash(reconstructed WorkRequestEnvelope with audit fields excluded)
    == request_envelope_hash
```

The DDL must include every scalar/ref needed for reconstruction, at minimum:

```text
request_id
request_envelope_hash
source_surface
source_method
work_source_kind
work_class
aggregation_group
preview_body_class
mutation_preview_hash
rollback_plan_ref
context_manifest_hash
surface_manifest_hash
expires_at
created_at
```

For `S7GuardedExecutionInvocationStore`:

```text
S7GuardedExecutionInvocationStore.get(request_id, artifact_id)
    -> S7GuardedExecutionInvocation
```

must reconstruct the invocation from durable refs and verify:

```text
canonical_hash(reconstructed S7GuardedExecutionInvocation)
    == guarded_execution_invocation_hash
```

The DDL must include or reference:

```text
request_id
artifact_id
guarded_execution_invocation_hash
rendered_statement_hash
authority_context_hash
surface_manifest_hash
surface_route_or_method
source_method
adapter_id
adapter_code_hash
source_ref_hash
reservation_token_hash
action_params_hash
precondition_hash
derived_work_class
derived_aggregation_group
rollback_plan_ref
superseded_request_ids_hash
covenant_ceremony_evidence_hash
created_at
```

### D24 tests

- `WorkRequestEnvelopeStore.get(...)` round-trips every hash-affecting field or
  fails with `missing_request_envelope`.
- `S7GuardedExecutionInvocationStore.get(...)` recomputes the invocation hash
  and fails on omitted/tampered refs before consume.

## 4. ActionEdgeGrantUse DDL And Replay Domain

**Absorbs:** Codex panel Cluster D; Codex reviewers 2 and 4.

v11 names `execution_consumer_id` and `grant_use_replay_token` on the
dataclass but omits them from DDL. `action_edge_key` depends on
`target_ref_hashes_before_mutation`, but that tuple's order and source are not
specified.

### v12 edit

Persist every load-bearing dataclass field:

```text
S7ActionEdgeGrantUse:
    action_edge_grant_use_id: str
    grant_id: str
    execution_consumer_id: str
    grant_use_replay_token: str
    action_edge_key: str
    action_edge_replay_token: str
    target_ref_hashes_before_mutation_hash: str
    used_at: datetime
```

Define target refs:

```text
target_ref_hashes_before_mutation =
    tuple(sorted((target_ref, canonical_hash(target_bytes_before_mutation))
                 for target_ref in rollback_plan.target_refs))
```

Sorting is lexicographic by `target_ref`. The tuple is computed immediately
inside the same transaction, after rollback-plan reload and before substrate
mutation.

Define:

```text
action_edge_key = canonical_hash((
    "s7.action_edge.v1",
    grant_id,
    execution_consumer_id,
    target_ref_hashes_before_mutation_hash,
))

action_edge_grant_use_id = canonical_hash((
    "s7.action_edge.id.v1",
    action_edge_key,
))

action_edge_replay_token = canonical_hash((
    "s7.action_edge.replay.v1",
    grant_use_replay_token,
    action_edge_key,
    used_at,
))
```

Uniqueness:

```text
UNIQUE(grant_id)
UNIQUE(action_edge_key)
UNIQUE(action_edge_replay_token)
```

### D24 tests

- ActionEdge DDL carries `execution_consumer_id` and
  `grant_use_replay_token`.
- Reordering target refs does not change `action_edge_key`; changing any target
  hash does.
- One grant cannot produce two action-edge rows.

## 5. Inherited Failure Partition

**Absorbs:** Codex panel Cluster H.

v11 says the wrapper must not guess after collapsed inherited failures, but the
amended inherited consume still returns `(grant | None, callback_result | None)`
without a failure carrier.

### v12 edit

Pick wrapper-owned preflight rather than changing inherited consume return shape.

Before calling inherited consume, the wrapper must check and assign exact
failure codes for every S7.3-specific condition:

```text
missing_request_envelope
missing_credential_request
missing_artifact_binding
missing_credential_binding
invalid_rendered_carrier
invalid_reservation_token
invalid_prompt_integrity
invalid_authority_class_replay
invalid_action_params_hash
invalid_consumer_id
expired_request_envelope
expired_bundle
expired_artifact
expired_grant
expiry_chain_violation
```

The inherited consume call may return `(None, None)` only after all wrapper
preflight checks pass. v12 must define the residual mapping:

```text
inherited_missing_artifact -> missing_artifact
inherited_already_consumed -> already_consumed
inherited_callback_failed -> callback_failed
inherited_unknown_none_none -> inherited_consume_failed
```

If the existing closed vocabulary lacks any residual code, v12 adds it or
maps it explicitly to an existing terminal code.

### D24 tests

For every closed failure reason, add one RED row naming:

- producing seam;
- exact input mutation;
- expected `S7ConsumeResult.failure_reason_code`;
- whether inherited consume was called.

## 6. Concrete Derivation Rows

**Absorbs:** Fresh-reader residual Major 1; Codex panel Cluster E adjacency.

v11 says callers cannot supply `execution_consumer_id`; it must come from
`execution_consumer_id_for(surface_manifest_row)`. The matrix now contains
concrete approval-card, Telegram, and credential rows that are not covered by
the derivation table.

### v12 edit

Make the derivation input explicit:

```text
execution_consumer_id_for(source_surface: str, source_method: str | None)
    -> execution_consumer_id
```

The derivation table must cover every concrete matrix row. At minimum add rows
for:

```text
approval_card.telegram_approve + approve -> guarded_card_execute
approval_card.cockpit_approve + approve -> guarded_card_execute
approval_card.daemon_internal_approve + approve -> guarded_card_execute
approval_card.s7_webauthn_card + approve -> guarded_card_execute
telegram.approve_train + approve_train -> guarded_card_execute
s7_credential_management + register_primary -> no mintable consumer id
s7_credential_management + backup_register -> s7_credential_register_backup
s7_credential_management + backup_card -> s7_credential_backup_card
s7_credential_management + disable -> s7_credential_disable
```

For reviewed exclusions, the derivation function returns a structured
non-mintable result:

```text
DerivationResult(
    execution_consumer_id: str | None,
    route_status: "reviewedly_excluded",
    exclusion_reason_code: str,
)
```

### D24 tests

Generate the matrix, iterate every row, and assert `execution_consumer_id_for`
returns exactly the matrix's mintable consumer id or a reviewed exclusion
result. No concrete matrix row may require caller-supplied ids.

## 7. Approval-Card Wrapper/Remap Seam

**Absorbs:** Codex reviewer 1 major.

D4 marks approval-card routes as live guarded and D21 lists guarded card
execution as a mutation consumer, but the concrete wrapper list omits a card
wrapper.

### v12 edit

Pick one seam. Lane lean: add a card wrapper.

```text
execute_guarded_card_execution(
    *,
    invocation: S7GuardedExecutionInvocation,
    card_request_store: S7ApprovalCardRequestStore,
    action_engine: ActionEngine,
    consume_store: S7GuardedStateStore,
    trace_writer: S7TraceWriter,
    rollback_store: RollbackPlanStore,
    now: datetime,
) -> S7GuardedExecutionTrace
```

The wrapper may lower to `execute_guarded_action_engine_mutation(...)` only
through a named helper:

```text
approval_card_invocation_to_action_engine_invocation(...)
```

That helper must preserve `guarded_card_execute` provenance in the trace and
prove same-code coverage for each concrete card route.

### D24 tests

- Telegram, cockpit, daemon, and S7 card routes all enter the card wrapper or a
  named reviewed remap.
- Direct card approval to `action_engine._execute_action(...)` without wrapper
  bookkeeping fails before mutation.

## 8. Credential Source-Method And Matrix `N/A` Normalization

**Absorbs:** Fresh-reader residual Major 3; Codex panel Cluster E; Codex
reviewer 4 blocker 2.

Credential source-method tokens diverge across the request carrier, matrix, and
prose. Matrix rows also use display `N/A` where the dataclass allows
`str | None`.

### v12 edit

Pick separate namespaces plus a bridge function.

Surface-manifest credential source methods:

```text
register_primary
backup_register
backup_card
disable
```

Credential request source methods:

```text
register_begin
register_finish
backup_card
disable
```

Bridge:

```text
credential_request_method_for_surface(
    source_surface: "s7_credential_management",
    source_method: str,
    registration_class: "primary" | "backup" | None,
) -> str | ReviewedExclusion
```

Rules:

```text
register_primary + primary -> ReviewedExclusion("first_primary_bootstrap")
backup_register + backup -> register_begin/register_finish pair
backup_card -> backup_card
disable -> disable
```

Matrix `N/A` is display-only. Persisted `work_source_kind` is SQL null / Python
`None`, never the literal string `"N/A"`.

### D24 tests

- Every credential matrix row maps through the bridge.
- Literal `"N/A"` in persisted `work_source_kind` is rejected.
- First-primary bootstrap cannot mint a backup-registration artifact.

## 9. Protective Reason Canonicalization

**Absorbs:** Codex panel Cluster F; Codex reviewers 2, 3, and 4.

D-Enum says persisted rows use string `"none"`. D13 still says
`protective_block_reason` is `None`, and the reducer row outputs do not make
`protective_block_reason` and `classifier_reason_code` explicit enough.

### v12 edit

Use string `"none"` everywhere after constructor canonicalization.

Add reducer output columns or a row-output side table:

```text
row_id
maez_objection_state
maez_voice_consulted
authority_class
protective_block_reason
classifier_reason_code
current_attempt_blocks
d23_state
```

For every row without a protective reason:

```text
protective_block_reason = "none"
```

Python `None` is accepted only at constructor edges and immediately normalized
before hashing, persistence, reducer output, or D16 replay.

### D24 tests

- `protective_block_reason=None` at constructor edge normalizes to `"none"`.
- A persisted or replayed row carrying Python `None` fails validation.
- Every D13 row has explicit protective/classifier outputs.

## 10. Nonce DDL And Partial Unique Alignment

**Absorbs:** Codex panel Cluster G; Codex reviewers 2 and 4.

Nonce DDL and transition rules use `attempt_index`, but
`S7ConsultationNonceUse` omits it. The active reserved nonce uniqueness is also
described as a table constraint when SQLite needs a partial unique index.

### v12 edit

Add:

```text
S7ConsultationNonceUse.attempt_index: int
```

Define the partial index:

```sql
CREATE UNIQUE INDEX s7_nonce_reserved_unique
ON s7_consultation_nonce_uses(expected_consultation_nonce_hash)
WHERE status = 'reserved';
```

Define attempt uniqueness:

```sql
CREATE UNIQUE INDEX s7_nonce_attempt_unique
ON s7_consultation_nonce_uses(request_id, consultation_id, attempt_index);
```

`transition_nonce_use(...)` must verify the event's `attempt_index` matches the
stored row.

### D24 tests

- Dataclass, DDL, and transition function all include `attempt_index`.
- Two reserved rows with the same nonce hash fail the partial index.
- Terminal nonce state rejects any later event.
- Legitimate reserved-to-accepted-spent transition succeeds exactly once.

## 11. Credential Trace Idempotency Key

**Absorbs:** Fresh-reader residual Major 2; Codex single-lens Major.

The idempotency key uses `credential_operation`, but the rest of the spec uses
`credential_action`. The key also references `credential_id_hash`, which the
credential trace shape does not carry.

### v12 edit

Rename:

```text
credential_operation -> credential_action
```

Pick one key. Lane lean: add `credential_id_hash` to the trace because it is a
stable idempotency discriminator for credential actions.

```text
S7CredentialGuardedTrace:
    request_id: str
    credential_action: str
    credential_id_hash: str | None
    challenge_id: str | None
    challenge_hash: str | None
    ...
```

Idempotency key:

```text
(request_id, credential_action, credential_id_hash)
```

For actions that do not yet have a credential id, `credential_id_hash` is the
canonical hash of the pending credential public-key handle or challenge binding
ref. It is never omitted for an idempotent trace write.

### D24 tests

- No `credential_operation` token remains in normative text.
- Credential trace idempotency key uses fields carried by the trace.
- Missing `credential_id_hash` fails for any idempotent credential trace write.

## 12. First-Primary Bootstrap Non-Mintable

**Absorbs:** Codex reviewer 1 minor; Codex panel single-lens item.

v11 marks first-primary credential bootstrap as reviewedly excluded but assigns
the backup-registration consumer id. This can be miscounted as backup coverage.

### v12 edit

First-primary bootstrap row:

```text
source_surface = "s7_credential_management"
source_method = "register_primary"
route_status = "reviewedly_excluded"
execution_consumer_id = None
exclusion_reason_code = "first_primary_bootstrap_out_of_scope"
```

It must not carry `s7_credential_register_backup`.

### D24 test

The manifest generator must fail if a reviewedly-excluded first-primary row
has a mintable consumer id.

## 13. Parent `action_engine_final_mutate` Non-Mintable

**Absorbs:** Codex reviewer 1 minor.

The closed set still includes parent `action_engine_final_mutate`, while the
spec says L8 evidence must use concrete child ids.

### v12 edit

Pick one. Lane lean: keep the parent only as a legacy audit token, not mintable.

Add:

```text
NON_MINTABLE_EXECUTION_CONSUMER_IDS = {
    "action_engine_final_mutate",
}
```

`execution_consumer_id_for(...)` must never return a non-mintable id for a
live-guarded manifest row. Positive L8 evidence cannot cite the parent id.

### D24 test

Any artifact minted with `execution_consumer_id="action_engine_final_mutate"`
for an ActionEngine live row fails L8 and consume preflight.

## 14. `grant_id` Derivation

**Absorbs:** Codex single-lens Major.

v11 says `grant_id` derives from `(artifact_id, consumed_at, nonce)` but the
fresh nonce is not carried on `S7ExecutionGrant` or `GrantUse`.

### v12 edit

Pick one. Lane lean: remove the fresh nonce and use persisted fields.

```text
grant_id = canonical_hash((
    "s7.execution_grant.v1",
    artifact_id,
    execution_consumer_id,
    grant_use_replay_token,
    consumed_at,
))
```

If a nonce is retained, v12 must add:

```text
grant_nonce_hash
```

to both `S7ExecutionGrant` and `GrantUse`, and include it in D16/D21 replay.

### D24 test

`grant_id` derivation is deterministic from persisted fields and changes when
artifact id, consumer id, replay token, or consumed timestamp changes.

## 15. Final Bundle Marker Replay Path

**Absorbs:** Codex single-lens Major/bookkeeping.

Draft/parser/attempt evidence carry marker text hashes and authority booleans
depend on marker replay, but the final bundle field list omits
`marker_text_hash`.

### v12 edit

Pick one. Lane lean: bind replay through raw response and attempt refs; do not
duplicate `marker_text_hash` on the final bundle.

Add explicit text:

```text
S7VoiceConsultationBundle does not store marker_text_hash directly. D16 replay
recovers marker text by loading raw_maez_response_ref and
SemanticReaderAttemptEvidence.marker_text_hash, then verifies both against
attempt_input_hash and source_ref_hash. A bundle cannot validate marker-derived
authority booleans unless those refs replay.
```

If the spec author instead adds `marker_text_hash` to the bundle, D16 and D24
must verify it against raw response and attempt evidence.

### D24 test

Tampering marker text in the raw response or attempt evidence breaks marker
replay and prevents authority-booleans replay.

## 16. Request-Family Caller-Supplied Closure

**Absorbs:** Codex single-lens Major.

v11 says the writer derives family, but `S7RequestHistoryRecord` still carries
both `request_family` and `request_family_derived`. The spec does not clearly
reject or ignore caller-supplied `request_family`.

### v12 edit

Make S7.3 writers derive and persist exactly one family field.

Lane lean:

```text
request_family is legacy-read-only input from inherited rows.
request_family_derived is the S7.3 persisted family.
S7.3 writers do not accept caller-supplied request_family.
```

For new S7.3 writes:

```text
record.request_family must be None before writer derivation.
writer computes request_family_derived = request_history_family_for(record).
writer persists request_family_derived.
aggregation reads request_family_derived for S7.3 rows and treats legacy rows
with both fields null under inherited behavior.
```

If the spec keeps only one field, delete `request_family` from S7.3 write shape
and make it a read-only legacy projection.

### D24 test

A caller attempting to write `request_family="s7_3_voice"` directly is rejected
or ignored; the persisted value must equal the writer-derived family.

## 17. Stale Wording And Signature Polish

**Absorbs:** Codex panel stale wording and signature polish.

### v12 edit

Apply these exact cleanups:

- remove stale `v9` wording from v11/v12 normative sections;
- use `Callable[...]` rather than lowercase `callable` in Python-ish signature
  blocks;
- qualify ambiguous `consume_for_execution(...)` references as either inherited
  `S7AuthorizationStore.consume_for_execution(...)` or guarded
  `S7GuardedStateStore.consume_artifact_for_execution(...)`;
- remove duplicate checklist rows where they obscure the single source of
  truth.

### D24/acceptance test

Add grep checklist entries for:

```text
Callable[
S7GuardedStateStore.consume_artifact_for_execution
S7AuthorizationStore.consume_for_execution
```

## 18. Fresh-Reader Carry-Forwards

These are not optional polish. They are the two explicit carry-forwards from
the v11 fresh-reader gate.

### 18.1 Bridge UNIQUE Menu Wording

**Absorbs:** spec-implementor minor.

v11 contains an earlier menu of possible bridge unique constraints and later
pins the definitive one. v12 must delete the menu.

Replace the menu with:

```text
The request-history bridge enforces:
UNIQUE(provenance_source_kind, provenance_source_ref)
```

No alternative `UNIQUE(authority_row_id)` branch remains unless the spec also
renames the stored field to `authority_row_id` everywhere.

### 18.2 D24 Wrapper-Invocation Negative Test

**Absorbs:** covenant minor.

Add an explicit negative test row:

```text
wrapper-invocation negative test: a direct call that presents plausible
artifact id, rendered statement, consumer id, and consumed grant data but lacks
a stored S7GuardedExecutionInvocation fails before inherited consume and before
substrate mutation.
```

This is the dual-direction partner of the positive wrapper-invocation test.

## 19. Secondary Minors And Nits To Fold While Editing

Fold these while touching the relevant sections. They do not replace the named
sections above:

- `S7VoiceConsultationTrace` minimum fields should include
  `attempt_manifest_hash` or state why bundle binding is sufficient.
- D24 no-hand-assembly list should allow `ContextManifest` construction for
  negative constructor-validation tests only.
- `S7AuthorizationArtifactBinding` should state why challenge fields are
  non-null for voice-seat artifacts.
- `S7SurfaceManifest` shape must include `created_at` if prose says it is
  persisted/excluded from `manifest_hash`.
- `D23_STATES` and `TRACE_STATUSES` values need producer seams or reviewed
  unreachable rationale for `authorized`, `bridge_failed`, `rollback_failed`,
  and `manual_review_required`.
- `attempt_input_hash` should either rename itself to include audit context or
  move `attempt_started_at` out of the classifier-input tuple.
- `proposal_origin` and `proposal_origin_label` relationship should be stated:
  one is request provenance, the other is context-manifest audit label; neither
  is rendered as consent.
- `VOICE_SEAT_WORK_CLASSES` and `VOICE_CONSULTATION_PRODUCERS` should be named
  in the Inheritance section.
- WorkRequestEnvelope volatile audit fields excluded from hash should be
  enumerated.

## 20. v12 Acceptance Checklist

Before committing v12 spec, run a grep checklist proving every named fold item
landed. Required strings:

```text
S7TraceWriter writes into state.sqlite3
consume_artifact_for_execution(*, invocation:
unpack_guarded_execution_invocation
WorkRequestEnvelopeStore.get(request_id) -> WorkRequestEnvelope
S7GuardedExecutionInvocationStore.get(request_id, artifact_id)
target_ref_hashes_before_mutation =
wrapper-side preflight owns
execution_consumer_id_for(source_surface: str, source_method: str | None)
execute_guarded_card_execution
credential_request_method_for_surface
work_source_kind is SQL null
protective_block_reason = "none"
CREATE UNIQUE INDEX s7_nonce_reserved_unique
attempt_index: int
credential_action
credential_id_hash
first_primary_bootstrap_out_of_scope
NON_MINTABLE_EXECUTION_CONSUMER_IDS
grant_id = canonical_hash
S7VoiceConsultationBundle does not store marker_text_hash directly
request_family is legacy-read-only
UNIQUE(provenance_source_kind, provenance_source_ref)
wrapper-invocation negative test
Callable[
```

No v12 gate may be dispatched until each string appears in the committed spec
or a conscious replacement string is recorded in the v12 authorship note.

## 21. Expected v12 -> v13 Flow

v12 is the fold-contract round. It should be committed as this plan. The next
spec version should be v13, authored against this fold contract.

Expected ladder:

1. Commit this v12 fold plan.
2. Author v13 spec from v11 spec plus this plan.
3. Mechanically verify the Section 20 grep checklist.
4. Dispatch fresh-reader gate v13 and Codex panel v13 independently against the
   same committed v13 spec.
5. If both lanes return RATIFY or RATIFY-with-fold with bounded nits only,
   canonicalize S7.3 and transition to RED-first implementation planning.

## Plain English

v11 got the covenant architecture to the finish line. The remaining work is the
last engineering contract layer: one database story, one invocation story,
round-trippable stores, replayable action-edge rows, exact credential tokens,
and reducer/status fields that say the same thing everywhere.

v12 does not decide what Maez means, what refusal means, or what authority
means. Those decisions are stable. v12 makes the spec impossible to implement
two different ways by accident.

The test for v12 is simple: every one of the seventeen locked items plus the
two fresh-reader carry-forwards must have a named landing site in v13. If that
happens and v13 review finds only bounded nits, S7.3 is ready to stop being a
moving target and start becoming code.

*Authorship: produced by Codex on 2026-05-20, absorbing
`reviews/spec-fresh-reader-gate-v11.md` (`ac65567`) and
`reviews/spec-codex-panel-v11.md` (`23978af`). No new architecture is
introduced here; this is a canonicalization-consistency fold contract.*
