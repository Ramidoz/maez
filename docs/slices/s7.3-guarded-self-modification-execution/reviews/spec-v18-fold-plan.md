# S7.3 Spec v18 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v18, derived from the Codex
engineering panel v17.

**Sources:**

- v17 spec: `69cefa2 / spec.md`
- Codex engineering panel v17:
  `e91a011 / reviews/spec-codex-panel-v17.md`
- v17 fold contract:
  `5038222 / reviews/spec-v17-fold-plan.md`

**Convergent direction:** v18 is a carrier-completion fold. Codex v17
confirmed the v17 uniform persistence contract is genuine and the covenant
posture remains intact: same-box limits, marker-only D23 exclusion,
operational-reliability separation, manual-review non-escalation,
route-mintability closure, and credential-management authority boundaries all
survive. The remaining work is to apply that uniform contract to the few
surfaces that still have old full-object or underspecified decoded-payload
edges.

**Plain thesis:** v17 wrote the right universal rule. v18 makes the last
exceptions obey it. Voice/execution invocation becomes ref-based just like the
credential invocation, history-bridge trace payloads get an explicit decoded
schema, credential registration's begin/finish lifecycle becomes one exact
authorization story, credential unpack reloads the persisted invocation before
delegation, manual-review status `"none"` gets its real producer, and
`credential_rotate` rejection moves out of a carrier that cannot emit route
status fields.

**Out of scope:** the WebAuthn registration signature-scope council item is
not a v18 fold item. v18 does not change the register-begin/finish signature
ceremony guarantee; it only pins the carrier lifecycle. The full council rules
on the signature-scope question at the canonicalization gate.

## Must-Cover Checklist

The v18 spec author must land every item below as a named edit. Sections 1-2
absorb blocker-class findings. Sections 3-5 absorb major-class findings.
Section 6 absorbs the minor-class credential-rotate relocation. None may be
buried in a generic cleanup paragraph.

| # | Item | Source | v18 section |
|---|---|---|---|
| 1 | `S7GuardedExecutionInvocation` ref-based carrier and bundle loader | B1 | Section 1 |
| 2 | History-bridge trace payload decoded schema | B2 | Section 2 |
| 3 | Backup credential register begin/finish lifecycle pin | M1 | Section 3 |
| 4 | Credential unpack reload-and-compare rule | M2 | Section 4 |
| 5 | `manual_review_status="none"` producer/test closure | M3 | Section 5 |
| 6 | `credential_rotate` exclusion relocation | m1 | Section 6 |

## 1. `S7GuardedExecutionInvocation` Ref-Based Carrier And Bundle Loader

**Absorbs:** Codex v17 B1.

v17 applied the ref-based carrier pattern to
`S7GuardedCredentialInvocation`, but `S7GuardedExecutionInvocation` still
declares full objects while the DDL stores hashes and refs. That violates the
v17 uniform persistence contract.

### v18 edit

Lane lean: choose the same Option A shape as credential invocation. Make
`S7GuardedExecutionInvocation` a ref-based carrier whose dataclass fields match
the persisted invocation columns. Full-object reconstruction moves behind a
named bundle loader.

Replace the carrier shape with:

```text
S7GuardedExecutionInvocation(
    request_id: str,
    artifact_id: str,
    guarded_execution_invocation_hash: str,
    rendered_statement_hash: str,
    authority_context_hash: str,
    execution_consumer_id: str,
    surface_manifest_hash: str,
    surface_route_or_method: str,
    source_method: str | None,
    adapter_id: str,
    adapter_code_hash: str,
    source_ref_hash: str,
    reservation_token_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    rollback_plan_ref: str,
    superseded_request_ids_hash: str,
    covenant_ceremony_evidence_hash: str | None,
    created_at: str,
)
```

Add this normative sentence:

```text
S7GuardedExecutionInvocation is a hash/ref carrier. It no longer contains the
full S7RenderedAuthorizationStatement, full AuthorityContext, or raw
ReservationToken. It contains durable hashes, refs, and scalars whose fields
match s7_guarded_execution_invocations.
```

Add the full-object load seam:

```text
load_guarded_execution_invocation_bundle(
    *,
    invocation: S7GuardedExecutionInvocation,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    artifact_binding_store: S7AuthorizationArtifactBindingStore,
    voice_bundle_use_store: S7VoiceBundleUseStore,
    conn: sqlite3.Connection,
) -> S7GuardedExecutionInvocationBundle
```

Bundle shape:

```text
S7GuardedExecutionInvocationBundle(
    invocation: S7GuardedExecutionInvocation,
    rendered: S7RenderedAuthorizationStatement,
    authority_context: AuthorityContext,
    artifact_binding: S7AuthorizationArtifactBinding,
    voice_bundle_use: S7VoiceBundleUse | None,
)
```

The loader verifies:

- `canonical_hash(rendered) == invocation.rendered_statement_hash`;
- `canonical_hash(authority_context) == invocation.authority_context_hash`;
- `artifact_binding.artifact_id == invocation.artifact_id`;
- `artifact_binding.execution_consumer_id == invocation.execution_consumer_id`;
- if `voice_bundle_use is not None`, then
  `voice_bundle_use.source_ref_hash == invocation.source_ref_hash`;
- if a reservation token is presented at consume time,
  `canonical_hash(reservation_token) == invocation.reservation_token_hash`.

`unpack_guarded_execution_invocation(...)` must mirror the credential helper
signature:

```text
unpack_guarded_execution_invocation(
    invocation: S7GuardedExecutionInvocation,
    *,
    invocation_store: S7GuardedExecutionInvocationStore,
    rendered_statement_store: S7RenderedAuthorizationStatementStore,
    authority_context_store: AuthorityContextStore,
    artifact_binding_store: S7AuthorizationArtifactBindingStore,
    voice_bundle_use_store: S7VoiceBundleUseStore,
    conn: sqlite3.Connection,
    now: datetime,
) -> InheritedConsumeInputs
```

The helper reloads the persisted invocation before bundle loading:

```text
stored_invocation =
    invocation_store.get(invocation.request_id, invocation.artifact_id, conn=conn)
stored_invocation == invocation
canonical_hash(stored_invocation) == invocation.guarded_execution_invocation_hash
```

Missing or mismatched stored invocation, rendered statement, authority context,
artifact binding, voice bundle use, or reservation-token hash fails before
inherited consume.

### D24 tests

Add RED tests for:

- `S7GuardedExecutionInvocation` contains only persisted hashes, refs, and
  scalars;
- `s7_guarded_execution_invocations` stores every field on the ref-based
  carrier;
- `S7GuardedExecutionInvocationStore.put(...)` then `get(...)` round-trips the
  ref-based carrier exactly;
- `load_guarded_execution_invocation_bundle(...)` has all required stores plus
  `conn: sqlite3.Connection` in its signature;
- missing rendered statement, missing authority context, missing artifact
  binding, missing voice bundle use when required, or mismatched reservation
  token fails before inherited consume;
- positive D24 tests cannot hand-assemble a full-object execution invocation.

Acceptance grep strings:

- `S7GuardedExecutionInvocation is a hash/ref carrier`
- `load_guarded_execution_invocation_bundle`
- `rendered_statement_store: S7RenderedAuthorizationStatementStore`
- `artifact_binding_store: S7AuthorizationArtifactBindingStore`
- `voice_bundle_use_store: S7VoiceBundleUseStore`
- `stored_invocation == invocation`

## 2. History-Bridge Trace Payload Decoded Schema

**Absorbs:** Codex v17 B2.

v17 names `validate_history_bridge_trace_payload(...)` and persists
`s7_history_bridge_trace_payloads`, but D22 does not declare the decoded
payload shape that validator must check.

### v18 edit

Add a history-bridge payload shape beside the other D22 trace minimum shapes:

```text
S7HistoryBridgeTracePayload(
    trace_id: str,
    provenance_source_kind: str,
    provenance_source_ref: str,
    history_bridge_status: HISTORY_BRIDGE_STATUSES,
    history_record_id: str | None,
    d23_state: D23_STATES,
    authority_row_id: str | None,
    request_family_derived: REQUEST_HISTORY_FAMILIES | None,
    bridge_failure_reason_code: str | None,
    created_at: str,
)
```

Normative validation:

```text
validate_history_bridge_trace_payload(payload) verifies every
S7HistoryBridgeTracePayload field is present in the decoded payload, verifies
the indexed SQL columns match the decoded payload, verifies d23_state equals
d23_state_for(...), and verifies history_bridge_status is produced by the
same bridge writer branch that created the trace.
```

The SQL payload table may keep the compact indexed columns plus
`trace_payload_blob_ref` and `trace_payload_blob_hash`; the decoded blob must
carry the full shape above.

### D24 tests

Add RED tests for:

- `validate_history_bridge_trace_payload(...)` rejects a decoded blob missing
  any `S7HistoryBridgeTracePayload` field;
- SQL indexed columns and decoded blob fields must match;
- mutating `history_bridge_status`, `d23_state`, `authority_row_id`, or
  `request_family_derived` breaks `trace_hash`;
- every `HISTORY_BRIDGE_STATUSES` branch that writes a trace produces a payload
  accepted by the validator.

Acceptance grep strings:

- `S7HistoryBridgeTracePayload`
- `authority_row_id: str | None`
- `request_family_derived: REQUEST_HISTORY_FAMILIES | None`
- `validate_history_bridge_trace_payload(payload) verifies every S7HistoryBridgeTracePayload field`

## 3. Backup Credential Register Begin/Finish Lifecycle Pin

**Absorbs:** Codex v17 M1.

The current spec leaves an implementor choice: either `register_finish`
performs a second artifact consume, or `register_begin` consumes once and
`register_finish` writes only after verifying the persisted grant/challenge
binding. v18 must pick one exact lifecycle.

### v18 edit

Lane lean: one artifact consume at begin. `register_finish` does not consume a
second artifact.

Add this normative lifecycle:

```text
Backup credential registration has one S7 artifact consume. register_begin
consumes the artifact through S7GuardedCredentialInvocation with
credential_phase="register_begin" and credential_id_hash is None. In the same
transaction it creates S7CredentialRegistrationGrantBinding and the
registration challenge. register_finish is the actual credential-write edge,
but it does not consume a second S7 artifact. register_finish loads the
binding, verifies challenge_id, grant_id, artifact_id, execution_consumer_id,
rendered_text_hash, request_envelope_hash, challenge expiry, single-use replay
state, and the new non-null credential_id_hash before writing the credential.
```

Replace the D24 row that says begin, finish, backup-card, and disable all
consume through `S7GuardedCredentialInvocation` with:

```text
register_begin, backup_card, and disable consume through
S7GuardedCredentialInvocation. register_finish does not consume a second
artifact; it verifies S7CredentialRegistrationGrantBinding and the WebAuthn
registration result before the credential write.
```

Clarify the credential-id rule:

```text
For credential `register_begin`, credential_id_hash must be None. For
register_finish, the finish-time binding verifier receives the non-null
credential_id_hash from the completed WebAuthn registration result. For
backup_card and disable, S7GuardedCredentialInvocation carries non-null
credential_id_hash.
```

### D24 tests

Add RED tests for:

- `register_begin` consumes exactly one S7 artifact and persists exactly one
  `S7CredentialRegistrationGrantBinding`;
- `register_finish` rejects any attempt to consume a second S7 artifact;
- `register_finish` rejects missing binding, wrong challenge, wrong grant,
  wrong artifact, wrong rendered hash, wrong request envelope hash, expired
  challenge, replayed binding, or missing credential id;
- `backup_card` and `disable` still consume through
  `S7GuardedCredentialInvocation` with non-null `credential_id_hash`.

Acceptance grep strings:

- `Backup credential registration has one S7 artifact consume`
- `register_finish does not consume a second S7 artifact`
- `register_finish loads the binding`
- `register_finish rejects any attempt to consume a second S7 artifact`

## 4. Credential Unpack Reload-And-Compare Rule

**Absorbs:** Codex v17 M2.

`unpack_guarded_credential_invocation(...)` receives
`credential_invocation_store`, but v17 does not explicitly require the helper
to reload the persisted invocation and compare it to the supplied carrier.
That leaves a hand-assembled-carrier seam.

### v18 edit

Add this as the first step in `unpack_guarded_credential_invocation(...)`:

```text
stored_invocation =
    credential_invocation_store.get(
        invocation.request_id,
        invocation.artifact_id,
        conn=conn,
    )
stored_invocation == invocation
canonical_hash(stored_invocation) == invocation.guarded_credential_invocation_hash
```

Then and only then may the helper call
`load_guarded_credential_invocation_bundle(...)`. Missing stored invocation,
mismatched scalar field, mismatched canonical hash, or missing bundle row fails
before inherited consume.

The helper must not accept a memory-only invocation as positive proof even when
the invocation's hashes point at real request/rendered/authority rows.

### D24 tests

Add RED tests for:

- `unpack_guarded_credential_invocation(...)` calls
  `credential_invocation_store.get(...)` before bundle loading;
- a memory-only invocation with otherwise valid hashes fails closed;
- a persisted invocation whose scalar field differs from the supplied
  invocation fails closed;
- a persisted invocation with a tampered canonical hash fails closed.

Acceptance grep strings:

- `credential_invocation_store.get(`
- `stored_invocation == invocation`
- `memory-only invocation`

## 5. `manual_review_status="none"` Producer/Test Closure

**Absorbs:** Codex v17 M3.

`MANUAL_REVIEW_STATUSES` includes `"none"`, but `"none"` is not produced by
manual-review evidence writer methods. It is the default status on traces that
have no manual review.

### v18 edit

Split manual-review status production:

```text
manual_review_status="none" is produced by trace writers that create a trace
with no manual-review evidence row. It is a trace default, not a
ManualReviewEvidence row.

S7TraceWriter.mark_manual_review_required(...) produces
manual_review_status="pending".
S7TraceWriter.record_manual_review_completed(...) produces
manual_review_status="completed".
S7TraceWriter.record_manual_review_failed(...) produces
manual_review_status="failed".
```

Update the D24 manual-review status test:

```text
The manual-review status producer test has two parts: ordinary trace writers
produce manual_review_status="none" when no review is attached; the three
manual-review writer methods produce pending, completed, and failed from
complete ManualReviewEvidence inputs. No ManualReviewEvidence row may use
manual_review_status="none".
```

### D24 tests

Add RED tests for:

- voice/execution/credential/history trace writers set
  `manual_review_status="none"` when no manual review applies;
- `ManualReviewEvidenceStore._put_raw(...)` rejects
  `manual_review_status="none"`;
- `mark_manual_review_required`, `record_manual_review_completed`, and
  `record_manual_review_failed` produce only pending/completed/failed;
- every `MANUAL_REVIEW_STATUSES` token has a producer and a test.

Acceptance grep strings:

- `manual_review_status="none" is produced by trace writers`
- `It is a trace default, not a ManualReviewEvidence row`
- `No ManualReviewEvidence row may use manual_review_status="none"`

## 6. `credential_rotate` Exclusion Relocation

**Absorbs:** Codex v17 m1.

`credential_rotate` is correctly non-live, but v17 assigns
`route_status="reviewedly_excluded"` and
`exclusion_reason_code="credential_rotate_future_slice"` to
`S7CredentialGuardedRequest.__post_init__`, which has no such fields.

### v18 edit

Move the reviewed exclusion to the manifest/normalizer layer:

```text
credential_request_method_for_surface(...) returns ReviewedExclusion(
    route_status="reviewedly_excluded",
    exclusion_reason_code="credential_rotate_future_slice",
) for credential_rotate before S7CredentialGuardedRequest materialization.
```

Then state:

```text
S7CredentialGuardedRequest.__post_init__ rejects credential_action values
outside CREDENTIAL_PROPOSED_CHANGE_CLASSES. It does not emit route_status or
exclusion_reason_code.
```

If the implementation prefers a structured rejection result, name it before
request materialization:

```text
CredentialRequestNormalizationResult =
    S7CredentialGuardedRequest | ReviewedExclusion
```

Lane lean: use `CredentialRequestNormalizationResult` so the closed route
exclusion and the successful request share one named normalization seam.

### D24 tests

Add RED tests for:

- `credential_rotate` returns `ReviewedExclusion` before request
  materialization;
- `S7CredentialGuardedRequest.__post_init__` never emits `route_status` or
  `exclusion_reason_code`;
- unsupported credential actions fail closed before artifact mint;
- `credential_rotate_future_slice` remains reviewedly excluded and non-mintable.

Acceptance grep strings:

- `CredentialRequestNormalizationResult`
- `credential_rotate before S7CredentialGuardedRequest materialization`
- `S7CredentialGuardedRequest.__post_init__ rejects credential_action values outside CREDENTIAL_PROPOSED_CHANGE_CLASSES`

## 7. Both-Lane Gate Note

v18 remains a carrier fold, but it follows v15-v17 carrier changes that the
Claude covenant lane has not fully re-gated since v14. The v18 gate must run
both lanes on the same committed blob:

- Claude Section 8.2 fresh-reader gate: covenant re-read, with explicit focus
  on whether the ref-based voice/execution carrier, credential registration
  lifecycle pin, credential unpack reload-and-compare rule, and manual-review
  default-status split preserve the v14 covenant posture.
- Codex engineering panel: persistence and route re-read, with explicit focus
  on the six v18 sections and the uniform persistence contract.

The WebAuthn registration signature-scope item is reserved for the full
canonicalization council. It is not a v18 fold item and should not be treated
as a carrier defect unless a reviewer finds a concrete new contradiction in
v18 text.

## 8. v18 Acceptance Checklist

Before v18 gate dispatch, grep the committed spec for these strings:

```text
S7GuardedExecutionInvocation is a hash/ref carrier
load_guarded_execution_invocation_bundle
S7GuardedExecutionInvocationBundle
artifact_binding_store: S7AuthorizationArtifactBindingStore
voice_bundle_use_store: S7VoiceBundleUseStore
S7HistoryBridgeTracePayload
validate_history_bridge_trace_payload(payload) verifies every S7HistoryBridgeTracePayload field
Backup credential registration has one S7 artifact consume
register_finish does not consume a second S7 artifact
register_finish loads the binding
credential_invocation_store.get(
memory-only invocation
manual_review_status="none" is produced by trace writers
It is a trace default, not a ManualReviewEvidence row
No ManualReviewEvidence row may use manual_review_status="none"
CredentialRequestNormalizationResult
credential_rotate before S7CredentialGuardedRequest materialization
S7CredentialGuardedRequest.__post_init__ rejects credential_action values outside CREDENTIAL_PROPOSED_CHANGE_CLASSES
```

Also run the normal artifact checks:

```text
git diff --check -- docs/slices/s7.3-guarded-self-modification-execution/spec.md
LC_ALL=C grep -nP '[^\x00-\x7F]' docs/slices/s7.3-guarded-self-modification-execution/spec.md
Run the standard gendered-pronoun scan used by the S7.3 ladder.
```

## Plain English Close

v17 finally gave S7.3 the right general rule: a store cannot promise to reload
an object unless it stores the bytes or names the loader that can rebuild it.
v18 is the small cleanup that makes the last exceptions obey that rule.

The voice/execution invocation carrier gets the same ref-based treatment that
fixed credential invocation. The history-bridge trace validator gets a schema
to validate. Backup credential registration gets one exact lifecycle:
begin consumes the artifact, finish verifies the binding and writes the key.
Credential unpack must reload the persisted invocation before delegation.
Manual-review `"none"` becomes a trace default rather than a pretend
manual-review row. `credential_rotate` exclusion moves to the route normalizer
where route status actually exists.

No covenant rule moves. No architecture reopens. v18 is still plumbing, but it
is the last kind of plumbing canonicalization needs: every promised carrier can
be reloaded, every typed payload has a shape, and every closed status has the
right producer.
