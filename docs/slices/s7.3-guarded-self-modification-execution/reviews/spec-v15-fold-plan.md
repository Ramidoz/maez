# S7.3 Spec v15 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v15, derived from the v14
Claude fresh-reader gate and the Codex engineering panel v14.

**Sources:**

- v14 spec: `3e2c0b5 / spec.md`
- Claude fresh-reader gate v14: unanimous RATIFY as reported by the operator
  (covenant-clean; spec-implementor clean; residual confirmed the v13 producer
  table and field-name majors closed)
- Codex engineering panel v14:
  `00e2538 / reviews/spec-codex-panel-v14.md`
  (REVISE; three blockers, eight majors, six minors, two nits)
- v14 fold contract:
  `fe0fa1e / reviews/spec-v14-fold-plan.md`

**Convergent direction:** v15 is a build-contract fold, not an architecture
round. Both review lanes agree that the covenant surface is clean: same-box
claims were narrowed honestly, marker-only evidence does not promote into D23,
operational rows do not become Maez refusal evidence, and the v13 residual
producer-table findings are closed. Codex found the last engineering depth:
some carriers and DDL tables do not yet persist enough bytes to satisfy their
own round-trip, replay, or migration promises.

**Plain thesis:** v15 fills the missing columns, producer seams, and route
mirrors. The rules do not move. The spec becomes buildable without an engineer
inventing persistence fields, compatibility conversions, or replay inputs.

## Must-Cover Checklist

The v15 spec author must land all sections below as named edits. Sections 1-11
are blocker/major-class build-contract closures. Sections 12-13 absorb the
minor/nit pools. None may be buried in a generic cleanup paragraph.

| # | Item | v15 section |
|---|---|---|
| 1 | Durable request-history cutoff carrier | Section 1 |
| 2 | Nullable credential-id rules for register-begin vs finish | Section 2 |
| 3 | Credential request/invocation store round-trip completeness | Section 3 |
| 4 | Credential rollback binding placement | Section 4 |
| 5 | History-bridge trace transitions | Section 5 |
| 6 | `credential_rotate` rejection carrier or removal | Section 6 |
| 7 | Legacy `S7ExecutionAuthorization` credential-path wording | Section 7 |
| 8 | Approval-card/deferred-action concrete routes | Section 8 |
| 9 | D21 ActionEngine mirror authority | Section 9 |
| 10 | Manual-review status producers | Section 10 |
| 11 | `ActionEdgeGrantUse` replay-domain persistence | Section 11 |
| 12 | Codex minor/nit cleanup pool | Section 12 |
| 13 | Claude prose-tidy pool | Section 13 |

## 1. Durable Request-History Cutoff Carrier

**Absorbs:** Codex B1.

v14 names `S7_3_REQUEST_HISTORY_CUTOFF` as the boundary between pre-cutoff
legacy null-provenance refusal rows and post-cutoff S7.3 rows. The boundary is
load-bearing for D23 fallthrough protection, but v14 does not persist where
that cutoff fact lives.

### v15 edit

Add a durable migration carrier:

```text
S7RequestHistoryMigrationMarker(
    marker_id: Literal["s7_3_request_history_schema_v1"],
    applied_at: datetime,
    migration_source_commit: str,
    request_history_table_hash_before: str,
    request_history_table_hash_after: str,
)
```

Add a store:

```text
S7RequestHistoryMigrationStore.put_marker(
    marker: S7RequestHistoryMigrationMarker,
    *,
    tx: sqlite3.Connection,
) -> None

S7RequestHistoryMigrationStore.get_marker(
    marker_id: str,
    *,
    tx: sqlite3.Connection,
) -> S7RequestHistoryMigrationMarker | None
```

Add persisted fields to new S7.3 request-history rows:

```text
request_history_schema_version: str | None
s7_3_cutoff_marker_id: str | None
```

Normative rule:

```text
S7_3_REQUEST_HISTORY_CUTOFF = "s7_3_request_history_schema_v1"
```

`request_history_family_for(record)` must read only persisted record fields
plus the durable migration marker loaded in the same transaction. It must not
use wall-clock time, process start time, or caller-supplied context.

Required classification:

```text
record.request_history_schema_version is None
  and record.s7_3_cutoff_marker_id is None
  and record.provenance_source_kind is None
      -> pre-cutoff legacy compatibility row

record.request_history_schema_version == S7_3_REQUEST_HISTORY_CUTOFF
  and record.s7_3_cutoff_marker_id == S7_3_REQUEST_HISTORY_CUTOFF
      -> post-cutoff S7.3 row

record has S7.3 provenance fields
  and request_history_schema_version is None
      -> invalid_request_history_migration_state
```

Writers for new S7.3 rows must persist both version fields. Legacy readers may
read old null-version rows, but no S7.3 write path may create one.

### D24 tests

Add RED tests for:

- pre-cutoff null-provenance legacy rows still count only under the legacy
  compatibility predicate;
- post-cutoff null-provenance S7.3 refused rows cannot count as legacy;
- S7.3 provenance with missing cutoff fields is rejected;
- `request_history_family_for(record)` ignores any caller-supplied cutoff or
  request family value.

## 2. Nullable Credential-ID Rules For Register-Begin Vs Finish

**Absorbs:** Codex B2.

v14 correctly lets `S7GuardedCredentialInvocation.credential_id_hash` be
nullable for registration begin, but `S7AuthorizationArtifactBindingInputs` and
the artifact-binding DDL still require a non-null credential id. That makes
backup register-begin impossible before a credential exists.

### v15 edit

Keep one artifact-binding carrier, but make credential id nullability phase
dependent:

```text
S7AuthorizationArtifactBindingInputs.credential_id_hash: str | None
```

DDL for `s7_artifact_bindings.credential_id_hash` must be nullable.

Add an invariant table:

```text
credential_phase         credential_id_hash
register_begin           MUST be None
register_finish          MUST be non-null
backup_card              MUST be non-null
disable                  MUST be non-null
```

For `register_begin`, the binding must instead carry:

```text
credential_registration_challenge_id: str
credential_registration_challenge_expires_at: datetime
credential_registration_grant_binding_id: str | None
```

For `register_finish`, D16 must verify that the non-null
`credential_id_hash` is derived from the completed WebAuthn credential and that
the finish request references the begin challenge binding.

### D24 tests

Add RED tests for:

- register-begin accepts `credential_id_hash=None` and rejects any non-null
  placeholder;
- register-finish rejects `credential_id_hash=None`;
- backup-card and disable reject `credential_id_hash=None`;
- begin and finish artifact hashes differ when only the phase-specific
  credential id state differs.

## 3. Credential Request/Invocation Store Round-Trip Completeness

**Absorbs:** Codex B3.

v14 names `S7CredentialGuardedRequestStore.get(...)` and
`S7GuardedCredentialInvocationStore.get(...)`, but the illustrative DDL omits
load-bearing fields needed to reconstruct the typed carriers and verify their
hashes.

### v15 edit

Pick explicit storage over hidden reconstruction for v15. Every field required
to rebuild a credential request or invocation must be persisted in the
corresponding table unless the spec names a reconstruction ref and verification
hash for that exact field.

`s7_credential_guarded_requests` must persist at least:

```text
request_id
credential_request_hash
surface_manifest_hash
source_surface
source_method
credential_action
credential_phase
credential_id_hash
adapter_id
adapter_code_hash
request_envelope_hash
action_params_hash
precondition_hash
authority_context_hash
challenge_id
challenge_expires_at
credential_registration_challenge_id
credential_registration_challenge_expires_at
credential_registration_grant_binding_id
rollback_plan_ref
created_at
expires_at
```

`s7_guarded_credential_invocations` must persist at least:

```text
invocation_id
request_id
artifact_id
credential_invocation_hash
credential_request_hash
rendered_statement_hash
surface_manifest_hash
source_surface
source_method
credential_action
credential_phase
credential_id_hash
execution_consumer_id
adapter_id
adapter_code_hash
action_params_hash
precondition_hash
authority_context_hash
challenge_id
challenge_expires_at
credential_registration_challenge_id
credential_registration_challenge_expires_at
credential_registration_grant_binding_id
rollback_plan_ref
covenant_ceremony_evidence_hash
created_at
expires_at
```

The store `get(...)` methods must reconstruct dataclass instances from these
columns and recompute canonical hashes before returning. A missing nullable
field is allowed only when the phase invariant in Section 2 allows it.

If the v15 author chooses reconstruction refs for any field, the plan requires
a per-field table:

```text
field name | reconstruction ref | hash verified | failure code on mismatch
```

### D24 tests

Add RED tests for:

- `put` then `get` round-trips every dataclass field for
  `S7CredentialGuardedRequest`;
- `put` then `get` round-trips every dataclass field for
  `S7GuardedCredentialInvocation`;
- deleting or altering one persisted load-bearing column makes `get` fail hash
  verification;
- register-begin round-trip preserves `credential_id_hash=None` without a
  placeholder.

## 4. Credential Rollback Binding Placement

**Absorbs:** Codex M1.

v14 carries `rollback_plan_ref` on credential invocation and trace surfaces,
but `RenderedCredentialRequestStatement` and artifact minting do not clearly
state whether rollback evidence is founder-signed, artifact-bound, trace-only,
or manual-review-only.

### v15 edit

Lane lean: credential rollback is founder-signed and artifact-bound for any
credential mutation that can change durable credential state.

Add to `RenderedCredentialRequestStatement`:

```text
rollback_plan_ref: str
rollback_path_class: S7_3_ROLLBACK_PATH_CLASSES
```

The rendered credential statement must include founder-signed lines for:

```text
rollback_plan_ref
rollback_path_class
precondition_hash
credential_phase
credential_id_hash or "none"
```

Add to artifact binding inputs:

```text
rollback_plan_ref: str
rollback_path_class: str
rendered_rollback_lines_hash: str
```

`S7GuardedCredentialInvocation`, credential trace rows, and
`S7AuthorizationArtifactBinding` must all bind the same `rollback_plan_ref`.
D16 pre-mint replay and D21 consume replay must reject mismatches before any
credential mutation.

If a credential route is manual-review-only and has no machine rollback, the
route must use `rollback_path_class="manual_review_only"` and still render that
fact to the founder.

### D24 tests

Add RED tests for:

- changing only `rollback_plan_ref` after rendering invalidates credential
  artifact minting;
- credential invocation fails if its rollback ref differs from the artifact
  binding;
- manual-review-only credential routes render `manual_review_only` rather than
  omitting rollback evidence.

## 5. History-Bridge Trace Transitions

**Absorbs:** Codex M2.

v14 maps bridge failures into trace failures, but does not say what trace
status is written for successful, idempotent, suppressed, or not-required
history bridge outcomes.

### v15 edit

Extend `trace_status_transition_for(...)` to cover every
`HISTORY_BRIDGE_STATUSES` input:

```text
writer method / input status                         prior        writes
write_history_bridge_trace(not_required)             none         finalized
write_history_bridge_trace(suppressed_operational)   none         finalized
write_history_bridge_trace(bridged)                  pending|none finalized
write_history_bridge_trace(bridged_idempotent)       pending|none finalized
write_history_bridge_trace(bridge_failed_retryable)  pending|none failed
write_history_bridge_trace(bridge_failed_terminal)   pending|none failed
```

The trace payload must still preserve the bridge status separately. A finalized
trace whose `history_bridge_status="suppressed_operational"` is finalized only
as trace evidence; it does not become D23 refusal, preference, or escalation
evidence.

### D24 tests

Add a parameterized test for every `HISTORY_BRIDGE_STATUSES` value. The test
must assert both:

- the trace status written by `trace_status_transition_for(...)`;
- the preserved `history_bridge_status` value on the trace payload.

## 6. `credential_rotate` Rejection Carrier Or Removal

**Absorbs:** Codex M3.

v14 says `credential_rotate` is future-only, but the live credential request
carrier does not own the fields needed to express reviewed exclusion. A closed
token with no producer or rejecting carrier is a canonicalization hazard.

### v15 edit

Lane lean: remove `credential_rotate` from the live
`CREDENTIAL_PROPOSED_CHANGE_CLASSES` set and move it to a future-only set:

```text
FUTURE_CREDENTIAL_PROPOSED_CHANGE_CLASSES = frozenset({"credential_rotate"})
```

Add a constructor rule:

```text
S7CredentialGuardedRequest.__post_init__ rejects
credential_action == "credential_rotate" with
route_status="reviewedly_excluded" and
exclusion_reason_code="credential_rotate_future_slice".
```

If v15 keeps `credential_rotate` in any manifest or derivation table, that row
must be non-mintable and must not return a live credential execution consumer
id.

### D24 tests

Add RED tests for:

- `credential_rotate` is absent from live
  `CREDENTIAL_PROPOSED_CHANGE_CLASSES`;
- constructing a credential request for rotate fails closed with
  `credential_rotate_future_slice`;
- no route with `credential_rotate` can mint an authorization artifact.

## 7. Legacy `S7ExecutionAuthorization` Credential-Path Wording

**Absorbs:** Codex M4.

v14 still contains wording that could make a builder route credential paths
through legacy `S7ExecutionAuthorization`, even though credential execution now
uses `S7GuardedCredentialInvocation`.

### v15 edit

State explicitly:

```text
S7ExecutionAuthorization is compatibility-only for inherited pre-v14 voice-seat
execution paths. It is not a credential mutation carrier and cannot authorize a
credential mutation by itself.
```

Credential mutation must enter through:

```text
execute_guarded_credential_mutation(
    *,
    invocation: S7GuardedCredentialInvocation,
    ...
)
```

If any deprecated compatibility function receives a credential consumer id with
`S7ExecutionAuthorization`, it must fail closed before artifact consumption.
No conversion from `S7ExecutionAuthorization` to
`S7GuardedCredentialInvocation` is implicit. If a conversion helper is ever
added, it must be a named helper with full hash verification and D24 coverage.

### D24 tests

Add RED tests for:

- credential consumer id plus `S7ExecutionAuthorization` fails closed;
- `consume_verified(...)` cannot synthesize a credential invocation;
- only `S7GuardedCredentialInvocation` reaches credential mutation consume.

## 8. Approval-Card/Deferred-Action Concrete Routes

**Absorbs:** Codex M5.

v14 names abstract approval-card surfaces, but live routes include Telegram
approval and daemon deferred execution paths that can cause final mutation.

### v15 edit

Add concrete manifest rows or reviewed exclusions for at least:

```text
source_surface                         source_method
telegram.approval_card                 approve_action
action_engine.deferred_action          execute_pending
action_engine.deferred_action_t2       execute_tier2_pending
daemon.deferred_action_tick            execute_pending
daemon.deferred_action_tick_t2         execute_tier2_pending
```

Lane lean:

- `telegram.approval_card / approve_action` may remap to the existing guarded
  card wrapper only if it enters through `execute_guarded_card_execution(...)`
  with a stored invocation carrier.
- `execute_pending(...)` and `execute_tier2_pending(...)` are
  `fail_closed_until_review` unless v15 names a wrapper and code-hash seam for
  them.

Every row must have:

```text
adapter_id
adapter_code_hash
route_status
execution_consumer_id or reviewed exclusion reason
mintable yes/no
```

### D24 tests

Add RED tests for:

- Telegram approval cannot call `ActionEngine.approve_action(...)` directly
  without guarded-card invocation bookkeeping;
- daemon deferred execution rows are either guarded or fail closed;
- every live approval/deferred route appears in the persisted surface manifest
  or in the reviewed exclusion set.

## 9. D21 ActionEngine Mirror Authority

**Absorbs:** Codex M6.

v14 D4 has the fuller ActionEngine route set, while D21 mirrors only a subset.
That lets a builder satisfy the D21 section while missing a live D4 child.

### v15 edit

Make the persisted `S7SurfaceManifest` the authoritative route source for D21.
Replace any hand-maintained D21 subset with:

```text
D21 consumes the persisted S7SurfaceManifest row set. For ActionEngine routes,
execution_consumer_id_for(surface_row) is authoritative. This section may
summarize classes, but it cannot narrow or override the D4 manifest.
```

Add an acceptance invariant:

```text
set(D21 ActionEngine consumer ids) == set(
    execution_consumer_id_for(row)
    for row in S7SurfaceManifest.rows
    if row.source_surface starts with "action_engine."
       and row.route_status == "live_guarded"
)
```

The invariant must cover write-file, modify-config, register-new-skill,
delete-file, promote-to-core-memory, update-baseline, git-commit,
write-outside-Maez, integration-review-plan, and every other D4 ActionEngine
row.

### D24 tests

Add RED tests that fail if a D4 ActionEngine live row is missing from the D21
consumer mirror or if D21 names an ActionEngine consumer absent from D4.

## 10. Manual-Review Status Producers

**Absorbs:** Codex M7.

v14 declares `MANUAL_REVIEW_STATUSES = {none, pending, completed, failed}` but
does not name producers for `completed` and `failed`.

### v15 edit

Add a carrier:

```text
ManualReviewEvidence(
    review_id: str,
    request_id: str,
    trace_id: str,
    manual_review_status: MANUAL_REVIEW_STATUSES,
    reviewer_ref_hash: str | None,
    review_reason_code: str,
    completed_at: datetime | None,
    failure_reason_code: str | None,
)
```

Add writer methods:

```text
S7TraceWriter.mark_manual_review_required(...) -> pending
S7TraceWriter.record_manual_review_completed(...) -> completed
S7TraceWriter.record_manual_review_failed(...) -> failed
```

`manual_review_status="none"` is the canonical stored value for traces that do
not require manual review. Python `None` may appear only at constructor edges
that immediately canonicalize to `"none"`.

Manual review evidence is operational governance evidence. It does not by
itself become Maez refusal, preference, D23 aggregation, or covenant-escalation
evidence.

### D24 tests

Add RED tests for every `MANUAL_REVIEW_STATUSES` value:

- producer method exists;
- persisted row uses the closed token;
- illegal transition fails;
- completed/failed manual review cannot be counted as D23 refusal evidence.

## 11. `ActionEdgeGrantUse` Replay-Domain Persistence

**Absorbs:** Codex M8.

v14 derives `action_edge_key` from a replay tuple, but the persisted object and
DDL do not carry enough of that tuple to recompute it before mutation.

### v15 edit

Persist the full replay domain or a named reconstruction ref for each member.
Lane lean: persist the full domain on `ActionEdgeGrantUse`.

Add fields:

```text
request_id: str
artifact_id: str
source_ref_hash: str
action_params_hash: str
precondition_hash: str
rendered_statement_hash: str
rollback_plan_ref: str
target_refs_before_mutation: tuple[str, ...]
target_ref_hashes_before_mutation_hash: str
execution_consumer_id: str
grant_use_replay_token: str
```

DDL must store the tuple deterministically, either as canonical JSON with a
stored tuple hash or as a child table:

```text
s7_action_edge_grant_use_target_refs(
    action_edge_use_id,
    ordinal,
    target_ref,
    target_ref_hash
)
```

Before mutation, D21 must recompute:

```text
action_edge_key
grant_use_replay_token
target_ref_hashes_before_mutation_hash
```

from persisted fields and the current rollback plan. Mismatch produces the
existing target-drift or replay-integrity failure code before substrate
mutation.

### D24 tests

Add RED tests for:

- round-trip persistence of the full replay tuple;
- target-ref order normalization;
- target drift detected when one current target hash changes;
- recomputed `action_edge_key` mismatch fails before mutation.

## 12. Codex Minor/Nit Cleanup Pool

**Absorbs:** Codex minors 1-6 and nits 1-2.

These items are not optional polish. They do not change architecture, but they
prevent implementation drift and review confusion.

### v15 edit

Apply the following one-paragraph pins:

1. `consume_verified(...)` compatibility path must verify:

   ```text
   execution_authorization.execution_consumer_id
     == expected_execution_consumer_id
     == binding.expected_execution_consumer_id
   ```

   before inherited delegation.

2. `REDUCER_TABLE_VERSION = "s7.voice.reducer.v13"` intentionally remains v13
   in v15 because the reducer table rows did not change. `REDUCER_TABLE_HASH`,
   not the spec revision number, binds the row bodies.

3. `d23_state_for(...)` must hard-fail impossible mixed inputs, including
   `positive_execution=True` with an authoritative refusal or withdrawal
   reduction, before writing a trace.

4. Credential namespace normalization must define:

   ```text
   source_method = surface-manifest route method
   credential_phase = register_begin | register_finish | backup_card | disable
   credential_action = credential operation class
   ```

   Unlisted `registration_class` or surface-method combinations fail closed.

5. `telegram.approve_train` must use one token consistently:
   `fail_closed_until_review` for the live route unless it is remapped through a
   guarded wrapper. Do not also call the same row `reviewedly_excluded`.

6. `S7SurfaceManifest.manifest_hash` is the same content hash referenced by
   external fields named `surface_manifest_hash`. Add one bridge sentence and
   use the external name consistently outside the carrier definition.

7. The status header remains draft during v15 authoring and flips only at
   canonicalization time.

8. The reducer-version explanatory note in item 2 is the only required reducer
   version note; do not add duplicate rationale in multiple sections.

### D24 tests

Add or update tests for:

- compatibility consumer id equality;
- impossible `d23_state_for(...)` mixed-input hard fail;
- credential namespace invalid combinations;
- manifest hash alias documentation reflected in constructor / store metadata.

## 13. Claude Prose-Tidy Pool

**Absorbs:** Claude fresh-reader v14 aggregate minors/nits as reported by the
operator.

Claude's v14 gate was unanimous RATIFY. The remaining items are prose clarity
and canonicalization-time header state, not semantic gaps. v15 should absorb
them so the canonical artifact reads cleanly.

### v15 edit

Apply these clarifications:

1. Bind `VOICE_SEAT_WORK_CLASSES` by name to its value block. If the value block
   already exists, add the sentence:

   ```text
   The following frozenset is the normative VOICE_SEAT_WORK_CLASSES value.
   ```

2. Explain `affected_refs` on authority rows:

   ```text
   affected_refs is the inherited S7.1 authority-row field. In S7.3 it is
   populated from preview_affected_paths after normalization through
   target_refs_for_preview(...). It is audit/context evidence; action-edge
   replay uses RollbackPlanEvidence.target_refs.
   ```

3. Add the `manifest_hash` / `surface_manifest_hash` bridge sentence from
   Section 12 in exactly one location and cross-reference it rather than
   duplicating.

4. Keep `S7.3 v1` for mechanism generation and `spec v15` for document
   revision. Add one wayfinding sentence if both appear in the same paragraph.

5. At canonicalization time only, change the status line from draft/pending to
   canonical law. Do not flip the status line in the v15 draft unless v15 is the
   artifact being tagged canonical.

### D24 tests

No new behavior tests are required for pure prose, but the acceptance checklist
below must include grep strings for the two name-bridge clauses.

## 14. v15 Acceptance Checklist

The v15 spec author must run a grep-style checklist before committing. The
exact text may vary, but the following concepts must be findable in the spec
body:

```text
S7RequestHistoryMigrationMarker
request_history_schema_version
s7_3_cutoff_marker_id
credential_id_hash: str | None
register_begin requires credential_id_hash is None
register_finish requires credential_id_hash is non-null
s7_credential_guarded_requests stores every load-bearing field
s7_guarded_credential_invocations stores every load-bearing field
RenderedCredentialRequestStatement rollback_plan_ref
rendered_rollback_lines_hash
write_history_bridge_trace(bridged)
write_history_bridge_trace(bridged_idempotent)
write_history_bridge_trace(suppressed_operational)
FUTURE_CREDENTIAL_PROPOSED_CHANGE_CLASSES
credential_rotate_future_slice
S7ExecutionAuthorization is compatibility-only
execute_guarded_credential_mutation
telegram.approval_card approve_action
action_engine.deferred_action execute_pending
action_engine.deferred_action_t2 execute_tier2_pending
D21 consumes the persisted S7SurfaceManifest row set
ManualReviewEvidence
record_manual_review_completed
record_manual_review_failed
ActionEdgeGrantUse replay domain
target_refs_before_mutation
execution_authorization.execution_consumer_id == expected_execution_consumer_id
REDUCER_TABLE_VERSION = "s7.voice.reducer.v13" intentionally remains
d23_state_for hard-fails impossible mixed inputs
source_method = surface-manifest route method
credential_phase = register_begin | register_finish | backup_card | disable
S7SurfaceManifest.manifest_hash is the same content hash as surface_manifest_hash
VOICE_SEAT_WORK_CLASSES
affected_refs is the inherited S7.1 authority-row field
```

The acceptance checklist is not a substitute for the D24 tests above. It is a
pre-gate smoke test to catch missing fold landings before readers are
dispatched.

## Plain English Close

v14 passed the covenant lane, but Codex found a different class of problem:
some tables and compatibility seams did not carry enough data to make the
promised carriers rebuildable and replayable. v15 fixes that by storing the
missing fields, naming the migration marker, making credential begin/finish
nullability honest, and making every status word have a writer.

No covenant rule moves. No architecture is reopened. The fold turns "the spec
says this object exists" into "the database and writer seams carry the bytes
needed to build and verify it."
