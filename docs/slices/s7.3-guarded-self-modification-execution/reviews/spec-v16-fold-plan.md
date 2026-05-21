# S7.3 Spec v16 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v16, derived from the Codex
engineering panel v15.

**Sources:**

- v15 spec: `cd3a1b3 / spec.md`
- Codex engineering panel v15:
  `99a93fa / reviews/spec-codex-panel-v15.md`
- v15 fold contract:
  `2732f0f / reviews/spec-v15-fold-plan.md`

**Convergent direction:** v16 is a persistence-and-route-cleanup fold. The
v15 Codex panel explicitly confirmed that the covenant posture remains intact:
same-box limits, marker-only D23 exclusion, operational reliability separation,
manual-review non-escalation, and credential carrier direction all survive. The
remaining work is byte-level build contract closure.

**Plain thesis:** if a store claims it can rebuild a carrier, the spec must
name the bytes or refs that make that possible. If a route is fail-closed, the
spec must not give it a mintable-looking consumer id. v16 makes those two rules
true everywhere.

## Must-Cover Checklist

The v16 spec author must land all nine items below as named edits. Sections
1-2 are blocker-class. Sections 3-8 are major-class. Section 9 absorbs the
minor/nit pool. None may be buried in a generic cleanup paragraph.

| # | Item | v16 section |
|---|---|---|
| 1 | Credential invocation/rendered/authority-context store round-trip | Section 1 |
| 2 | Fail-closed route rows and non-mintable consumer ids | Section 2 |
| 3 | Request-history row migration columns and cutoff marker validation | Section 3 |
| 4 | `integration_review_plan` source-method normalization | Section 4 |
| 5 | `append_to_file` direct-writer adapter binding | Section 5 |
| 6 | Typed trace payload persistence | Section 6 |
| 7 | ActionEdge target-ref hash tuple carrier | Section 7 |
| 8 | WorkRequestEnvelope persistence completeness | Section 8 |
| 9 | Minor/nit cleanup pool | Section 9 |

## 1. Credential Invocation/Rendered/Authority-Context Store Round-Trip

**Absorbs:** Codex v15 B1 and persistence M2.

This is the stubborn two-round survivor. v15 still declares
`S7GuardedCredentialInvocation` with full-object fields
`credential_request`, `rendered`, and `authority_context`, while the DDL stores
mostly hashes. There is also no rendered-statement store/ref API. The v16 fold
must pick one of the two Codex options completely. No third partial shape.

### v16 edit

Lane lean: choose Option A. Make `S7GuardedCredentialInvocation` a hash/ref
carrier whose dataclass fields match persisted columns. The live wrapper may
load full objects from stores, but the persisted invocation carrier itself
stores refs and hashes.

Replace the invocation shape with:

```text
S7GuardedCredentialInvocation(
    invocation_id: str,
    request_id: str,
    artifact_id: str,
    credential_request_hash: str,
    rendered_credential_statement_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    surface_manifest_hash: str,
    source_surface: str,
    source_method: str,
    credential_action: str,
    credential_phase: "register_begin" | "register_finish" | "backup_card" | "disable",
    adapter_id: str,
    adapter_code_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    derived_work_class: "founder_credential_management",
    derived_aggregation_group: str,
    rollback_plan_ref: str,
    challenge_id: str,
    challenge_hash: str,
    challenge_expires_at: str,
    credential_id_hash: str | None,
    covenant_ceremony_evidence_hash: str | None,
    guarded_credential_invocation_hash: str,
    created_at: str,
    expires_at: str,
)
```

`S7GuardedCredentialInvocation` no longer contains the full
`S7CredentialGuardedRequest`, full `RenderedCredentialRequestStatement`, or
full `AuthorityContext` object. It contains their durable hashes/refs. This
makes the dataclass and DDL match.

Add explicit load seam:

```text
load_guarded_credential_invocation_bundle(
    *,
    invocation: S7GuardedCredentialInvocation,
    credential_request_store: S7CredentialGuardedRequestStore,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    conn: sqlite3.Connection,
) -> S7GuardedCredentialInvocationBundle
```

Bundle shape:

```text
S7GuardedCredentialInvocationBundle(
    invocation: S7GuardedCredentialInvocation,
    credential_request: S7CredentialGuardedRequest,
    rendered: RenderedCredentialRequestStatement,
    authority_context: AuthorityContext,
)
```

Add stores:

```text
S7RenderedAuthorizationStatementStore.put(rendered, *, conn) -> rendered_text_hash
S7RenderedAuthorizationStatementStore.get(rendered_text_hash, *, conn) -> S7RenderedAuthorizationStatement | None
AuthorityContextStore.put(context, *, conn) -> authority_context_hash
AuthorityContextStore.get(authority_context_hash, *, conn) -> AuthorityContext | None
```

For credential invocation, `derived_work_class` and
`derived_aggregation_group` are persisted on the invocation row and must equal
the same fields on `S7CredentialGuardedRequest`. Mismatch fails before consume.

`S7GuardedCredentialInvocationStore.get(request_id, artifact_id)` reconstructs
only the hash/ref carrier and verifies:

```text
canonical_hash(reconstructed S7GuardedCredentialInvocation)
    == guarded_credential_invocation_hash
```

`unpack_guarded_credential_invocation(...)` then loads the bundle through
`load_guarded_credential_invocation_bundle(...)`, verifies the rendered and
authority context hashes, and only then produces inherited consume inputs.

Also add `rollback_plan_ref` to `S7CredentialGuardedRequest` because v15 prose
and DDL already require the store to reload it. Remove the stale prose saying
`RenderedCredentialRequestStatement` has no rollback plan lines; v16 keeps the
v15 rule that credential rollback is founder-signed and artifact-bound.

### D24 tests

Add RED tests for:

- `S7GuardedCredentialInvocation` dataclass fields exactly match persisted
  invocation columns;
- invocation `put` then `get` round-trips the hash/ref carrier without hidden
  full-object fields;
- `load_guarded_credential_invocation_bundle(...)` loads request, rendered
  statement, and authority context by hash and rejects any mismatch;
- invocation `derived_work_class` or `derived_aggregation_group` mismatch
  against the credential request fails before consume;
- rendered credential rollback lines are present and bound to artifact binding,
  invocation, and trace.

## 2. Fail-Closed Route Rows And Non-Mintable Consumer IDs

**Absorbs:** Codex v15 B2.

v15 says fail-closed/reviewed-excluded rows are non-mintable, but many
fail-closed ActionEngine matrix rows still carry non-null consumer ids that
also appear in mintable closed sets. That creates a mintable-looking path.

### v16 edit

Add the manifest invariant:

```text
route_status == "live_guarded"
    -> execution_consumer_id MUST be non-null
       and in S7_EXECUTION_CONSUMER_IDS
       and not in NON_MINTABLE_EXECUTION_CONSUMER_IDS

route_status in {"fail_closed_until_review", "reviewedly_excluded"}
    -> execution_consumer_id MUST be None
       and exclusion_reason_code MUST be non-null
```

Lane lean: fail-closed rows do not carry consumer ids at all. Reserved future
ids may appear only in a separate reviewed-future vocabulary, not in
`S7_EXECUTION_CONSUMER_IDS`.

Update the printed matrix so every `fail_closed_until_review` and
`reviewedly_excluded` row has:

```text
execution_consumer_id = N/A
```

This includes at least:

```text
action_engine.run_shell
action_engine.execute_script
action_engine.run_script
action_engine.sudo_command
action_engine.git_push
action_engine.install_package
action_engine.kill_process
action_engine.restart_service
action_engine.write_outside_maez
action_engine.restart_critical_service
action_engine.modify_firewall
action_engine.system_reboot
action_engine.free_disk_space
action_engine.delete_temp_file
action_engine.clean_temp_files
action_engine.run_safe_command
action_engine.query_system
action_engine.run_readonly_command
action_engine.install_package_t2
telegram.approve_train
telegram.rollback_adapter
cli_helper.execute
cockpit_helper.execute
reviewed_substrate_adapter.execute
self_mod_dialog.terminal_execute
deferred-action rows
first-primary credential bootstrap
```

If the spec keeps named reserved ids for future review, move them to:

```text
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
```

and state they are not accepted by artifact mint or consume in S7.3 v1.

### D24 tests

Add RED tests for:

- no row with `route_status!="live_guarded"` has a non-null consumer id;
- every fail-closed/reviewed-excluded row has a closed exclusion reason;
- every id in `S7_EXECUTION_CONSUMER_IDS` appears on at least one live-guarded
  row or has a reviewed unreachable rationale in
  `NON_MINTABLE_EXECUTION_CONSUMER_IDS`;
- D21 rejects `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` before mint.

## 3. Request-History Row Migration Columns And Cutoff Marker Validation

**Absorbs:** Codex v15 M1.

v15 added the marker table and row fields, but not the request-history row
migration / ALTER contract or reader validation that the marker id resolves.

### v16 edit

Add migration DDL:

```sql
ALTER TABLE s7_request_history_records
ADD COLUMN request_history_schema_version TEXT;

ALTER TABLE s7_request_history_records
ADD COLUMN s7_3_cutoff_marker_id TEXT;
```

If the committed table has a different name, v16 must name the real table and
state the same two columns land there.

Add reader validation:

```text
validate_request_history_cutoff(record, marker_store, *, conn) -> None
```

Rules:

```text
record.s7_3_cutoff_marker_id is not None
    -> marker_store.get_marker(record.s7_3_cutoff_marker_id) must exist

record.request_history_schema_version == S7_3_REQUEST_HISTORY_CUTOFF
    -> record.s7_3_cutoff_marker_id == S7_3_REQUEST_HISTORY_CUTOFF

record has S7.3 provenance fields
    -> request_history_schema_version and s7_3_cutoff_marker_id must both be
       S7_3_REQUEST_HISTORY_CUTOFF
```

Add writer rule: `S7RequestHistoryWriter.record_refusal_history(...)` sets both
fields for every new S7.3 row, even non-refusal audit rows.

### D24 tests

Add RED tests for:

- migration adds both request-history columns;
- S7.3 row whose marker id does not resolve is rejected by reader validation;
- new S7.3 writer persists both fields;
- legacy pre-cutoff row with both fields null still reads only under the legacy
  compatibility path.

## 4. `integration_review_plan` Source-Method Normalization

**Absorbs:** Codex v15 M2.

The derivation table uses `integration_review_plan` while the matrix uses
`review_plan` for the same route. The derivation key is
`(source_surface, source_method)`, so this must be byte-stable.

### v16 edit

Use this canonical tuple everywhere:

```text
source_surface = "action_engine.integration.review_plan"
source_method = "integration_review_plan"
execution_consumer_id = "action_engine_integration_review_plan"
```

Update derivation table, printed matrix, D21 mirror, D24 tests, and any
manifest fixture language to the same token. `review_plan` must not appear as a
source method for this route.

### D24 tests

Add RED tests for:

- `execution_consumer_id_for("action_engine.integration.review_plan",
  "integration_review_plan") == "action_engine_integration_review_plan"`;
- no manifest row uses source method `review_plan` for this source surface;
- code-discovery expected row maps `_do_integration_review_plan` to the
  canonical tuple.

## 5. `append_to_file` Direct-Writer Adapter Binding

**Absorbs:** Codex v15 M3.

The spec says `append_to_file` is direct-write only, but live public
`append_to_file(...)` delegates through shell. The direct writer is the private
`_do_append_to_file(...)` method.

### v16 edit

Pin the adapter symbol explicitly:

```text
source_surface = "action_engine.append_to_file"
source_method = "append_to_file"
adapter_symbol = "ActionEngine._do_append_to_file"
execution_consumer_id = "action_engine_append_to_file"
route_status = "live_guarded"
```

Add a compatibility exclusion:

```text
ActionEngine.append_to_file public shell-delegating method is not S7.3 L8
evidence. It must either be rewritten to call the guarded direct writer, or it
must fail closed for guarded paths. The manifest adapter symbol for positive
S7.3 append evidence is ActionEngine._do_append_to_file.
```

### D24 tests

Add RED tests for:

- manifest adapter symbol for append is `ActionEngine._do_append_to_file`;
- public `ActionEngine.append_to_file` cannot satisfy S7.3 while it delegates
  to `run_shell`;
- shell-shaped append grant fails L8;
- direct-writer append grant succeeds only through consumed artifact,
  `GrantUse`, and `ActionEdgeGrantUse`.

## 6. Typed Trace Payload Persistence

**Absorbs:** Codex v15 M4.

v15 declares replayable trace payload fields, but DDL has only a generic
`s7_traces` header with `trace_hash`. The store cannot reload typed payloads.

### v16 edit

Add one of two complete shapes. Lane lean: per-kind payload tables.

Keep `s7_traces` as the shared header:

```sql
CREATE TABLE s7_traces (
    trace_id TEXT NOT NULL PRIMARY KEY,
    trace_kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    trace_status TEXT NOT NULL,
    trace_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finalized_at TEXT
);
```

Add payload tables:

```text
s7_voice_trace_payloads(trace_id, request_id, consultation_id,
  attempt_manifest_hash, source_ref_hash, reducer_hash, d23_state,
  authority_class, history_bridge_status, final_rendered_statement_hash, ...)

s7_execution_trace_payloads(trace_id, request_id, artifact_id,
  execution_consumer_id, grant_id, grant_use_replay_token, action_edge_key,
  rollback_plan_ref, rollback_result_ref, d23_state, ...)

s7_credential_trace_payloads(trace_id, request_id, artifact_id,
  credential_action, credential_phase, challenge_id, credential_id_hash,
  rollback_plan_ref, manual_review_status, ...)

s7_history_bridge_trace_payloads(trace_id, provenance_source_kind,
  provenance_source_ref, history_bridge_status, history_record_id,
  d23_state, ...)
```

The exact column list may be longer, but v16 must include every D22 minimum
field required for replay by trace kind. `S7TraceWriter` writes the header and
matching payload row in the same transaction. `trace_hash` is computed over
the typed payload plus header fields excluding volatile audit fields.

Alternative allowed shape: one versioned canonical JSON payload table, but only
if the spec names strict schema validators for each `trace_kind` and
idempotency constraints per trace kind.

### D24 tests

Add RED tests for:

- every trace kind writes exactly one header and one typed payload row;
- `S7TraceWriter.get(trace_id)` reloads and verifies `trace_hash`;
- deleting or mutating a payload field breaks hash verification;
- idempotency keys remain unique per trace kind.

## 7. ActionEdge Target-Ref Hash Tuple Carrier

**Absorbs:** Codex v15 M5.

v15 carrier field `target_refs_before_mutation: tuple[str, ...]` conflicts with
the replay domain, which is a tuple of `(target_ref, target_ref_hash)` pairs.
The DDL child table already stores both values.

### v16 edit

Replace or supplement the raw-ref field with:

```text
target_ref_hashes_before_mutation: tuple[tuple[str, str], ...]
```

`ActionEdgeGrantUse` must carry:

```text
target_ref_hashes_before_mutation: tuple[tuple[target_ref, target_ref_hash], ...]
target_ref_hashes_before_mutation_hash: str
```

The ordered tuple is reconstructed from
`s7_action_edge_grant_use_target_refs` ordered by `ordinal`. A carrier with
only raw refs and no hashes is invalid.

### D24 tests

Add RED tests for:

- action-edge carrier rejects raw-ref-only replay data;
- child rows reconstruct the ordered `(target_ref, target_ref_hash)` tuple;
- changing either the ref or the hash changes
  `target_ref_hashes_before_mutation_hash`;
- mutation edge refuses to run if recomputed target bytes do not match the
  stored tuple.

## 8. WorkRequestEnvelope Persistence Completeness

**Absorbs:** Codex v15 M6.

v15 says `WorkRequestEnvelopeStore.get(...)` can reconstruct the inherited
carrier, but the DDL omits inherited fields such as claimed work class,
requesting subsystem, affected refs, predicted effect class, and free-text ref
hash.

### v16 edit

Pick one complete storage strategy. Lane lean: canonical blob/ref plus indexed
load-bearing columns.

Add to `s7_work_request_envelopes`:

```text
request_envelope_blob_ref TEXT NOT NULL
request_envelope_blob_hash TEXT NOT NULL
claimed_work_class TEXT NOT NULL
requesting_subsystem TEXT NOT NULL
affected_refs_hash TEXT NOT NULL
predicted_effect_class TEXT NOT NULL
free_text_ref_hash TEXT
```

`WorkRequestEnvelopeStore.get(request_id)` loads the canonical envelope blob by
`request_envelope_blob_ref`, verifies `request_envelope_blob_hash`, verifies
the indexed columns match the decoded envelope, and verifies:

```text
canonical_hash(decoded WorkRequestEnvelope with volatile audit fields excluded)
    == request_envelope_hash
```

If implementation chooses structured columns instead, v16 must list every
inherited `WorkRequestEnvelope` field as a column.

### D24 tests

Add RED tests for:

- envelope `put` then `get` round-trips the inherited carrier;
- mismatch between indexed column and canonical blob fails read;
- changing `affected_refs`, `claimed_work_class`, or `free_text_ref_hash`
  changes `request_envelope_hash`;
- volatile audit fields remain excluded from the hash domain.

## 9. Minor/Nit Cleanup Pool

**Absorbs:** Codex v15 m1-m3 and n1.

These items are not optional polish. They are small, but each prevents a future
implementor from reading the wrong boundary.

### v16 edit

Apply these changes:

1. Replace summary wording that says legacy `S7ExecutionAuthorization` is
   compatibility-only for credential paths with:

   ```text
   legacy S7ExecutionAuthorization is compatibility-only for inherited
   voice-seat paths and explicitly non-mintable for credential paths.
   ```

2. Strengthen deprecated `consume_verified(...)` equality:

   ```text
   execution_authorization.execution_consumer_id
     == expected_execution_consumer_id
     == binding.execution_consumer_id
     == binding.expected_execution_consumer_id
   ```

   State that `consume_verified(...)` must load or reconstruct the full guarded
   invocation through `S7GuardedStateStore` durable stores before delegation,
   or fail closed.

3. Make manual-review evidence writes trace-writer-owned. `ManualReviewEvidenceStore`
   raw `put` is private/internal; public writes are:

   ```text
   S7TraceWriter.mark_manual_review_required(...)
   S7TraceWriter.record_manual_review_completed(...)
   S7TraceWriter.record_manual_review_failed(...)
   ```

   Each writes evidence and trace transition in the same transaction.

4. Fix the illustrative SQL block so prose is not inside the SQL fence. Either
   close the fence before prose or make the sentence a SQL comment.

### D24 tests

Add RED tests for:

- credential consumer id on legacy `S7ExecutionAuthorization` remains
  fail-closed;
- deprecated consume equality checks both binding ids;
- manual-review evidence cannot be inserted through a public raw store path;
- SQL snippets parse or are fenced without prose contamination.

## 10. v16 Acceptance Checklist

The v16 spec author must run a grep-style checklist before committing. The
exact text may vary, but the following concepts must be findable in the spec
body:

```text
S7GuardedCredentialInvocation is a hash/ref carrier
load_guarded_credential_invocation_bundle
S7RenderedAuthorizationStatementStore
AuthorityContextStore
derived_work_class and derived_aggregation_group are persisted on the invocation row
route_status == "live_guarded" requires a mintable execution_consumer_id
route_status in {"fail_closed_until_review", "reviewedly_excluded"} requires execution_consumer_id=None
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS
validate_request_history_cutoff
ALTER TABLE s7_request_history_records
integration_review_plan
ActionEngine._do_append_to_file
s7_voice_trace_payloads
s7_execution_trace_payloads
s7_credential_trace_payloads
s7_history_bridge_trace_payloads
target_ref_hashes_before_mutation: tuple[tuple[str, str], ...]
request_envelope_blob_ref
request_envelope_blob_hash
legacy S7ExecutionAuthorization is compatibility-only for inherited voice-seat paths
binding.execution_consumer_id == binding.expected_execution_consumer_id
ManualReviewEvidenceStore raw put is private
```

The acceptance checklist is a pre-gate smoke test. It does not replace D24
tests or the two-lane review gate.

## Plain English Close

v15 fixed the big direction but still left some "trust me, the table can
rebuild it" promises without enough bytes on disk. v16 closes that stubborn
layer directly. Credential invocation becomes a hash/ref carrier that matches
its table. Fail-closed rows stop carrying consumer ids. Trace, envelope,
request-history, and ActionEdge storage gain the missing payload shape.

No covenant rule moves. No architecture is reopened. This is the fold that
makes the persistence layer match the promises the spec already makes.
