# S7.3 Spec v17 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v17, derived from the Codex
engineering panel v16.

**Sources:**

- v16 spec: `9563087 / spec.md`
- Codex engineering panel v16:
  `ece2f31 / reviews/spec-codex-panel-v16.md`
- v16 fold contract:
  `66c15a3 / reviews/spec-v16-fold-plan.md`

**Convergent direction:** v17 is a persistence-contract and signature-closure
fold. Codex v16 confirms the covenant posture remains intact: same-box limits,
marker-only D23 exclusion, operational-reliability separation,
manual-review non-escalation, and credential-carrier direction all survive.
The remaining work is to make every store, helper, trace writer, and
compatibility path carry the bytes and parameters it already promises to use.

**Plain thesis:** stop fixing persistence round-trip one table at a time. v17
adds one uniform rule: if a store or writer claims it can rebuild or verify a
carrier, every byte, ref, hash, or loader parameter needed for that rebuild
must be declared at the same precision as the carrier. Then v17 applies that
rule to the concrete Codex v16 findings.

## Must-Cover Checklist

The v17 spec author must land every item below as a named edit. Section 1 is
the cross-cutting persistence rule. Sections 2-4 absorb blocker-class findings.
Sections 5-10 absorb major-class findings. Section 11 absorbs the minor/nit
pool. Section 12 carries the both-lane gate reminder. None may be buried in a
generic cleanup paragraph.

| # | Item | Source | v17 section |
|---|---|---|---|
| 1 | Uniform S7.3 persistence round-trip contract | Meta pattern | Section 1 |
| 2 | Credential unpack helper store/connection inputs | B1 | Section 2 |
| 3 | Credential rollback binding across invocation/trace | B2 | Section 3 |
| 4 | Trace payload timing and D22 completeness | B3 + M1 | Section 4 |
| 5 | Stale credential `S7ExecutionAuthorization` wording | M2 | Section 5 |
| 6 | D21 ActionEngine mirror and acceptance prose | M3 + M4 | Section 6 |
| 7 | Manual-review writer signatures | M5 | Section 7 |
| 8 | Deprecated `consume_verified(...)` carrier loading | M6 | Section 8 |
| 9 | Wrapper-only callback ownership | M7 | Section 9 |
| 10 | Rendered/authority store get-path verification | m1 | Section 10 |
| 11 | Minor/nit cleanup pool | m2 + m3 + n1 | Section 11 |
| 12 | Both-lane v17 gate note | Covenant-lane carry-forward | Section 12 |

## 1. Uniform S7.3 Persistence Round-Trip Contract

**Absorbs:** repeated v14-v16 persistence pattern across credential
invocation, trace payloads, WorkRequestEnvelope, ActionEdge, request history,
and future S7.3 stores.

Codex v16 names the recurring rule: if the spec says a store or writer can
rebuild a carrier, every byte or ref needed to rebuild it must be named at the
same level of precision as the carrier. v17 should state that once, then make
the later store sections reference it.

### v17 edit

Add a normative D9/D22-adjacent rule:

```text
Uniform S7.3 persistence round-trip contract:

Every S7.3 store whose API exposes get(...) must satisfy exactly one of two
shapes:

1. all-column carrier:
   every dataclass field on the returned carrier is persisted as a typed
   column, excluding explicitly named volatile audit fields; or

2. ref-based carrier:
   every dataclass field on the returned carrier is a persisted scalar,
   hash, or ref column, and any full object reconstruction occurs only through
   a separately named bundle loader whose store dependencies and connection
   argument are part of the signature.

Every writer whose API emits a trace, manual-review evidence row, artifact
binding, invocation, or replay carrier must receive or derive every field
required by that row before the write transaction begins.

Every typed trace payload table must either:

1. persist every D22 minimum field for its trace kind as columns; or
2. persist trace_payload_blob_ref and trace_payload_blob_hash, and name a
   strict per-kind schema validator that checks the decoded payload contains
   every D22 minimum field for that trace kind.

No S7.3 carrier may declare a field its store can neither persist nor
reconstruct through a named loader. No D24 positive test may hand-assemble a
carrier to bypass this rule.
```

Lane lean: choose the ref/blob strategy for typed trace payloads. It is the
least brittle route at this stage because D22 trace carriers are large and may
gain fields while the header table remains stable.

### D24 tests

Add RED tests for:

- every `S7*Store.get(...)` either round-trips an all-column carrier or a
  ref-based carrier exactly;
- every ref-based carrier has a named loader with all store dependencies and
  the SQLite connection in the signature;
- every typed trace payload has either every D22 field as columns or a
  validated payload blob/ref pair;
- deleting a field, hash, ref, loader dependency, or payload blob causes the
  read or replay to fail closed;
- positive tests cannot construct a carrier in memory to satisfy a store
  round-trip assertion.

## 2. Credential Unpack Helper Store/Connection Inputs

**Absorbs:** Codex v16 B1.

v16 introduced the correct `load_guarded_credential_invocation_bundle(...)`
seam, but `unpack_guarded_credential_invocation(...)` does not receive the
stores or connection needed to call it.

### v17 edit

Replace the helper signature with:

```text
unpack_guarded_credential_invocation(
    invocation: S7GuardedCredentialInvocation,
    *,
    credential_invocation_store: S7GuardedCredentialInvocationStore,
    credential_request_store: S7CredentialGuardedRequestStore,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    conn: sqlite3.Connection,
    now: datetime,
) -> InheritedConsumeInputs
```

The helper must call:

```text
load_guarded_credential_invocation_bundle(
    invocation=invocation,
    credential_request_store=credential_request_store,
    rendered_statement_store=rendered_statement_store,
    authority_context_store=authority_context_store,
    conn=conn,
)
```

Missing store, missing connection, missing bundle row, or hash mismatch fails
before inherited consume. No hidden global store lookup and no implicit
composition through `credential_invocation_store` is allowed in v17.

### D24 tests

Add RED tests for:

- the helper signature exposes all three loader stores plus `conn`;
- calling the helper without a store dependency fails type/signature review;
- missing rendered statement, missing authority context, or missing credential
  request fails before inherited consume;
- tampering any loaded bundle object fails hash verification.

## 3. Credential Rollback Binding Across Invocation And Trace

**Absorbs:** Codex v16 B2.

v16 requires credential rollback lines to match artifact binding, invocation,
and trace, but the invocation carrier and credential trace payload do not carry
all fields needed for that assertion.

### v17 edit

Use a clear split:

- `S7GuardedCredentialInvocation` binds rollback by `rollback_plan_ref` and
  `rendered_credential_statement_hash`.
- `RenderedCredentialRequestStatement` and
  `S7AuthorizationArtifactBinding` carry the founder-signed detailed fields:
  `rollback_plan_ref`, `rollback_path_class`, and
  `rendered_rollback_lines_hash`.
- `S7CredentialGuardedTrace` and its typed payload carry
  `rollback_plan_ref`, `rollback_path_class`,
  `rendered_rollback_lines_hash`, and `rollback_result_ref`.

Add this normative sentence:

```text
The credential invocation carrier does not duplicate
rollback_path_class or rendered_rollback_lines_hash. Invocation binds the
rendered statement by rendered_credential_statement_hash and rollback by
rollback_plan_ref. D16/D21 then verify the detailed rollback fields by loading
the rendered statement, artifact binding, and credential trace payload.
```

Update the credential rollback D24 row so it no longer demands that
`S7GuardedCredentialInvocation` directly contain detailed rollback-line
fields. The test should verify:

```text
invocation.rollback_plan_ref
  == rendered.rollback_plan_ref
  == artifact_binding.rollback_plan_ref
  == credential_trace.rollback_plan_ref

rendered.rollback_path_class
  == artifact_binding.rollback_path_class
  == credential_trace.rollback_path_class

rendered.rendered_rollback_lines_hash
  == artifact_binding.rendered_rollback_lines_hash
  == credential_trace.rendered_rollback_lines_hash
```

### D24 tests

Add RED tests for:

- invocation binds rollback by `rollback_plan_ref` plus rendered statement
  hash, not by duplicated detailed rollback fields;
- rendered statement, artifact binding, and credential trace agree on
  rollback path class and rollback lines hash;
- changing rollback evidence after rendering invalidates mint or consume;
- a credential trace missing rollback path class or rendered rollback lines hash
  fails D22/D24 validation.

## 4. Trace Payload Timing And D22 Completeness

**Absorbs:** Codex v16 B3 and M1.

v16 added typed trace payload tables but made the voice payload require a
post-render field that does not exist when voice consultation trace is written.
It also left typed payloads narrower than the D22 minimum trace shapes.

### v17 edit

Adopt the v17 lane lean from Section 1: typed trace payloads use a strict
payload blob/ref strategy.

Keep the shared header:

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

Each typed payload table stores timing-appropriate indexed fields plus a full
payload blob/ref:

```sql
CREATE TABLE s7_voice_trace_payloads (
    trace_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL,
    consultation_id TEXT NOT NULL,
    attempt_manifest_hash TEXT NOT NULL,
    source_ref_hash TEXT NOT NULL,
    reducer_hash TEXT NOT NULL,
    d23_state TEXT NOT NULL,
    authority_class TEXT NOT NULL,
    history_bridge_status TEXT NOT NULL,
    trace_payload_blob_ref TEXT NOT NULL,
    trace_payload_blob_hash TEXT NOT NULL
);

CREATE TABLE s7_execution_trace_payloads (
    trace_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    execution_consumer_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    grant_use_replay_token TEXT NOT NULL,
    action_edge_key TEXT NOT NULL,
    rollback_plan_ref TEXT NOT NULL,
    rollback_result_ref TEXT,
    d23_state TEXT NOT NULL,
    trace_payload_blob_ref TEXT NOT NULL,
    trace_payload_blob_hash TEXT NOT NULL
);

CREATE TABLE s7_credential_trace_payloads (
    trace_id TEXT NOT NULL PRIMARY KEY,
    request_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    credential_action TEXT NOT NULL,
    credential_phase TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    credential_id_hash TEXT,
    rollback_plan_ref TEXT NOT NULL,
    rollback_path_class TEXT NOT NULL,
    rendered_rollback_lines_hash TEXT NOT NULL,
    rollback_result_ref TEXT,
    manual_review_status TEXT NOT NULL,
    trace_payload_blob_ref TEXT NOT NULL,
    trace_payload_blob_hash TEXT NOT NULL
);

CREATE TABLE s7_history_bridge_trace_payloads (
    trace_id TEXT NOT NULL PRIMARY KEY,
    provenance_source_kind TEXT NOT NULL,
    provenance_source_ref TEXT NOT NULL,
    history_bridge_status TEXT NOT NULL,
    history_record_id TEXT,
    d23_state TEXT NOT NULL,
    trace_payload_blob_ref TEXT NOT NULL,
    trace_payload_blob_hash TEXT NOT NULL
);
```

Delete `final_rendered_statement_hash` from `s7_voice_trace_payloads`. Voice
consultation trace does not require post-render fields. If later sections need
to bind final rendered text, that binding belongs in an authority/render trace
or in the authority row/bridge trace that exists after rendering.

Add schema validators:

```text
validate_voice_trace_payload(payload) -> None
validate_execution_trace_payload(payload) -> None
validate_credential_trace_payload(payload) -> None
validate_history_bridge_trace_payload(payload) -> None
```

Each validator checks the decoded payload contains every D22 minimum field for
that trace kind. `S7TraceWriter.get(trace_id)` verifies:

```text
canonical_hash(decoded payload blob) == trace_payload_blob_hash
canonical_hash(trace header + decoded typed payload, volatile audit fields excluded) == trace_hash
```

### D24 tests

Add RED tests for:

- voice trace payload rejects `final_rendered_statement_hash` as a required
  field and can be written before final D12 rendering;
- every typed payload table has `trace_payload_blob_ref` and
  `trace_payload_blob_hash`;
- each per-kind validator rejects a payload missing any D22 minimum field;
- tampering a payload blob or indexed field breaks trace hash verification;
- credential trace payload carries rollback path class and rendered rollback
  lines hash.

## 5. Stale Credential `S7ExecutionAuthorization` Wording

**Absorbs:** Codex v16 M2.

v16 correctly makes legacy `S7ExecutionAuthorization` non-mintable for
credential paths, but one earlier paragraph still says credential requests
carry closed ids on `S7ExecutionAuthorization`.

### v17 edit

Replace that stale wording with:

```text
Credential requests carry closed execution consumer ids on
S7CredentialGuardedRequest, S7GuardedCredentialInvocation, and
S7AuthorizationArtifactBinding. S7ExecutionAuthorization is compatibility-only
for inherited voice-seat paths and fails closed for credential consumers.
```

Search the spec for any remaining sentence that says
`S7ExecutionAuthorization` is compatibility-only for credential paths or that
credential consumers ride through `S7ExecutionAuthorization`; replace it with
the above rule.

### D24 tests

Add RED tests for:

- `S7ExecutionAuthorization` with `s7_credential_register_backup` fails closed;
- credential path succeeds only through `S7GuardedCredentialInvocation`;
- stale compatibility prose is absent from the acceptance checklist.

## 6. D21 ActionEngine Mirror And Acceptance Prose

**Absorbs:** Codex v16 M3 and M4.

D21 says the persisted manifest is authoritative, but later prose calls a
partial ActionEngine list complete. The acceptance checklist also overstates
fail-closed CLI/cockpit/reviewed-substrate/self-mod-dialog rows as
grant-consuming live paths.

### v17 edit

Replace the partial D21 mirror paragraph with:

```text
D21 does not maintain a hand-copied ActionEngine mirror. For ActionEngine
routes, the D21 consumer set is derived from the persisted S7SurfaceManifest:
every row with route_status="live_guarded" and
source_surface.startswith("action_engine.") must have an
execution_consumer_id in S7_ACTION_ENGINE_CONSUMER_IDS, and every id in
S7_ACTION_ENGINE_CONSUMER_IDS must appear on at least one live-guarded
ActionEngine row or carry an explicit reviewed-unreachable rationale. Rows
with route_status!="live_guarded" must have execution_consumer_id=None and a
closed exclusion_reason_code.
```

Replace acceptance prose that says fail-closed helper surfaces require
consumed grants with:

```text
Live rows require GuardedWorkItem, consumed artifact, GrantUse, and
ActionEdgeGrantUse as appropriate. Fail-closed and reviewed-excluded rows do
not consume artifacts in S7.3 v1; they require execution_consumer_id=None and
a closed exclusion_reason_code.
```

### D24 tests

Add RED tests for:

- D21 derives ActionEngine consumer coverage from the persisted manifest, not a
  hand-copied list;
- every live-guarded ActionEngine row maps to `S7_ACTION_ENGINE_CONSUMER_IDS`;
- fail-closed CLI/cockpit/reviewed-substrate/self-mod-dialog rows have no
  consumer id and cannot consume artifacts;
- acceptance checklist wording does not require consumed grants for
  fail-closed rows.

## 7. Manual-Review Writer Signatures

**Absorbs:** Codex v16 M5.

v16 makes manual-review evidence trace-writer-owned, but the writer methods do
not carry enough inputs to build `ManualReviewEvidence`.

### v17 edit

Use explicit evidence carriers:

```text
S7TraceWriter.mark_manual_review_required(
    execution_trace_id: str,
    evidence: ManualReviewEvidence,
    *,
    conn: sqlite3.Connection,
) -> None

S7TraceWriter.record_manual_review_completed(
    execution_trace_id: str,
    evidence: ManualReviewEvidence,
    *,
    conn: sqlite3.Connection,
) -> None

S7TraceWriter.record_manual_review_failed(
    execution_trace_id: str,
    evidence: ManualReviewEvidence,
    *,
    conn: sqlite3.Connection,
) -> None
```

Producer rules:

```text
mark_manual_review_required(...) requires
    evidence.manual_review_status == "pending"
    evidence.completed_at is None
    evidence.failure_reason_code is None

record_manual_review_completed(...) requires
    evidence.manual_review_status == "completed"
    evidence.completed_at is not None
    evidence.failure_reason_code is None

record_manual_review_failed(...) requires
    evidence.manual_review_status == "failed"
    evidence.completed_at is not None
    evidence.failure_reason_code is not None
```

All three methods write `ManualReviewEvidenceStore._put_raw(...)` and
`trace_status_transition_for(...)` in the same transaction. The raw store put
remains private/internal.

### D24 tests

Add RED tests for:

- each public trace-writer method can construct a complete evidence row from
  its explicit `ManualReviewEvidence` input;
- `mark_manual_review_required(...)` rejects `completed` or `failed` evidence;
- completed/failed writes require completion timestamp and appropriate failure
  fields;
- public raw manual-review store insertion remains unavailable.

## 8. Deprecated `consume_verified(...)` Carrier Loading

**Absorbs:** Codex v16 M6.

The compatibility wrapper takes `S7ExecutionAuthorization` but the live API is
carrier-only. The spec must state exactly how the compatibility path loads the
carrier rather than reconstructing loose fields.

### v17 edit

Amend `consume_verified(...)`:

```text
consume_verified(
    *,
    execution_authorization: S7ExecutionAuthorization,
    expected_execution_consumer_id: str,
    guarded_execution_invocation_store: S7GuardedExecutionInvocationStore,
    now: str,
    conn: sqlite3.Connection,
) -> S7ConsumeResult
```

Rules:

```text
loaded_invocation =
    guarded_execution_invocation_store.get(
        execution_authorization.rendered.request_id,
        execution_authorization.artifact_id,
        conn=conn,
    )

loaded_invocation is None -> fail closed before artifact consume

execution_authorization.execution_consumer_id
  == expected_execution_consumer_id
  == binding.execution_consumer_id
  == binding.expected_execution_consumer_id
  == loaded_invocation.execution_consumer_id

consume_verified(...) calls:
S7GuardedStateStore.consume_artifact_for_execution(
    invocation=loaded_invocation,
    now=now,
    connection=conn,
)
```

It must not construct `S7GuardedExecutionInvocation` fields from
`S7ExecutionAuthorization`; it may only load a previously persisted invocation
and verify it.

### D24 tests

Add RED tests for:

- missing persisted invocation makes `consume_verified(...)` fail closed;
- equality chain includes loaded invocation and artifact binding ids;
- compatibility path cannot synthesize invocation fields from
  `S7ExecutionAuthorization`;
- credential consumer ids on `S7ExecutionAuthorization` still fail closed.

## 9. Wrapper-Only Callback Ownership

**Absorbs:** Codex v16 M7.

The wrapper owns `after_consume_before_commit`, but the inherited amended
signature still takes a callback typed as `Callable[[S7ConsumeResult], object]`.
The inherited store cannot construct a wrapper-owned `S7ConsumeResult`.

### v17 edit

Make callback ownership wrapper-only.

Remove `after_consume_before_commit` from:

```text
S7AuthorizationStore.consume_for_execution(...)
```

Keep it only on:

```text
S7GuardedStateStore.consume_artifact_for_execution(...)
```

Add:

```text
The wrapper passes no callback into inherited consume. It calls
after_consume_before_commit only after inherited consume succeeds, durable
GrantUse is persisted, bundle-use consumption is complete when applicable, and
the wrapper can construct the full S7ConsumeResult. The inherited store returns
only its primitive two-tuple and never receives a Callable[[S7ConsumeResult],
object].
```

For backup credential registration, the finish-time grant/challenge binding
callback remains a wrapper callback after `GrantUse` exists and before commit.

### D24 tests

Add RED tests for:

- inherited consume signature has no `Callable[[S7ConsumeResult], object]`;
- wrapper callback runs only after durable `GrantUse` persistence;
- inherited success followed by callback failure rolls back wrapper writes;
- backup credential registration binding is written by wrapper callback before
  commit.

## 10. Rendered/Authority Store Get-Path Verification

**Absorbs:** Codex v16 m1.

The rendered statement and authority-context stores have DDL and API names, but
their read verification should match the explicit WorkRequestEnvelope pattern.

### v17 edit

Add:

```text
S7RenderedAuthorizationStatementStore.get(rendered_text_hash) loads
rendered_statement_blob_ref, verifies rendered_statement_blob_hash, decodes the
rendered carrier, verifies canonical_hash(decoded rendered carrier) equals
rendered_text_hash, and verifies indexed columns match decoded fields.

AuthorityContextStore.get(authority_context_hash) loads
authority_context_blob_ref, verifies authority_context_blob_hash, decodes the
authority context, verifies canonical_hash(decoded authority context) equals
authority_context_hash, and verifies indexed columns match decoded fields.
```

### D24 tests

Add RED tests for:

- rendered statement blob/hash/index mismatch fails read;
- authority context blob/hash/index mismatch fails read;
- credential bundle loading fails when either store returns `None`.

## 11. Minor/Nit Cleanup Pool

**Absorbs:** Codex v16 m2, m3, and n1.

These are not optional polish. Each prevents another stale-prose round.

### v17 edit

Apply these edits:

1. Telegram approval-card conditional:

   Replace the derivation-table wording with:

   ```text
   telegram.approval_card + approve_action -> guarded_card_execute through
   execute_guarded_card_execution only; non-wrapper paths are wrapper rejection,
   not alternate route derivation.
   ```

2. Shell-shaped aliases:

   Add:

   ```text
   query_system and run_readonly_command intentionally have no reserved future
   execution consumer id in S7.3 v1. Any future reviewed version must route
   through a newly named non-shell adapter with its own manifest row.
   ```

3. Stale v15 wording:

   Update sentences that describe the current draft but still say `v15` to
   `v17`. Historical bullets may keep older version labels only when describing
   what that version did.

### D24 tests

Add RED tests for:

- non-wrapper Telegram approval-card path is rejected by wrapper preflight, not
  treated as a second derivation row;
- `query_system` and `run_readonly_command` have no future id unless a new
  named non-shell adapter is reviewed;
- current-version checklist prose says v17.

## 12. Both-Lane v17 Gate Note

**Absorbs:** standing covenant-lane carry-forward.

The Claude covenant lane last directly read v14. Codex v15 and v16
cross-confirmed the covenant posture remains intact, but v15-v17 carrier
changes are still covenant-unreviewed by the Claude lane.

### v17 edit

Add a gate note near the Proposed Next Ladder:

```text
v17 requires both lanes before canonicalization:

1. Section 8.2 fresh-reader gate v17, including a covenant reader focused on
   the ref-based credential carrier and bundle loader. The reader verifies that
   credential persistence/reconstruction did not widen what credential paths
   can authorize.
2. Codex engineering panel v17, focused on the uniform persistence round-trip
   contract, trace payload blob/ref validation, manual-review writer evidence,
   and compatibility consume carrier loading.
```

No covenant rule moves in v17. This note is a review-routing guard, not a new
architecture claim.

### D24 tests

No runtime D24 test is needed for this section. The acceptance checklist must
contain the two-lane gate note.

## 13. v17 Acceptance Checklist

The v17 spec author must run a grep-style checklist before committing. The
exact text may vary, but the following concepts must be findable in the spec
body:

```text
Uniform S7.3 persistence round-trip contract
all-column carrier
ref-based carrier
trace_payload_blob_ref
trace_payload_blob_hash
validate_voice_trace_payload
validate_execution_trace_payload
validate_credential_trace_payload
validate_history_bridge_trace_payload
unpack_guarded_credential_invocation(
credential_request_store: S7CredentialGuardedRequestStore
rendered_statement_store: S7RenderedAuthorizationStatementStore
authority_context_store: AuthorityContextStore
conn: sqlite3.Connection
Credential invocation carrier does not duplicate rollback_path_class
credential trace payload carries rollback_path_class
credential trace payload carries rendered_rollback_lines_hash
voice trace payload does not require final_rendered_statement_hash
S7ExecutionAuthorization fails closed for credential consumers
D21 does not maintain a hand-copied ActionEngine mirror
route_status!="live_guarded"
ManualReviewEvidenceStore._put_raw
mark_manual_review_required
evidence.manual_review_status == "pending"
consume_verified
guarded_execution_invocation_store: S7GuardedExecutionInvocationStore
loaded_invocation.execution_consumer_id
The wrapper passes no callback into inherited consume
S7RenderedAuthorizationStatementStore.get
AuthorityContextStore.get
non-wrapper paths are wrapper rejection
query_system and run_readonly_command intentionally have no reserved future execution consumer id
v17 requires both lanes before canonicalization
```

The checklist is a pre-gate smoke test. It does not replace D24 tests or the
two-lane review gate.

## Plain English Close

v16 made the right big move, then exposed the next layer: the spec now has to
say, uniformly, how stores rebuild what they claim to rebuild. v17 writes that
rule once and applies it to the three remaining blocker seams: credential
bundle loading, credential rollback binding, and trace payload timing.

No covenant rule moves. No architecture is reopened. v17 is the fold that
turns "the carrier exists" into "the store, helper, and trace writer have every
byte and parameter needed to prove it."

