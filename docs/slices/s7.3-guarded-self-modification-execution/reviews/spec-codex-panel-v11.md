# Codex Panel v11 - S7.3 Spec v11

**Subject:** `spec.md` at `2bfdbd6` (operator-authored v11 fold), blob
`5da2f1792280c2b4c8fd5735a5a1b2cc8cba1680`, SHA256
`bd554e32cde4f289245f5dc37f5668901089d1b4453c87ad8bbf1fba0f8338a0`,
5291 lines.

**Ran:** 2026-05-20 by the Codex engineering lane. Four blank-context Codex
reviewers were dispatched independently against the committed v11 spec. Each
was walled off from
`docs/slices/s7.3-guarded-self-modification-execution/reviews/` and allowed to
inspect inherited committed code under `core/` as needed.

**Verdict: REVISE.** No reviewer reopened S7.3 architecture or covenant
posture. The panel did broaden v12 beyond the fresh-reader residual manifest
cluster: trace atomicity, invocation-to-consume API shape, request/invocation
store round-trip, ActionEdge persistence, and failure-code partition remain
canonicalization-blocking engineering seams.

## Reviewer Results

| Reviewer | Lens | Verdict | Findings |
|---|---|---:|---:|
| Reviewer 1 | Implementation surface and route completeness | REVISE | 0 blockers, 1 major, 2 minors |
| Reviewer 2 | RED-first implementability | REVISE | 5 blockers, 5 majors, 3 minors, 1 nit |
| Reviewer 3 | Authority/security/covenant-adjacent engineering | REVISE | 1 blocker, 2 majors, 1 minor |
| Reviewer 4 | Internal consistency and closed vocabulary accounting | REVISE | 2 blockers, 6 majors, 3 minors |

## Convergent Findings

### Cluster A - Trace Storage Atomicity Contradiction

**Severity:** Blocker, convergent across reviewers 2, 3, and 4.

D9 states that S7.3 uses a single SQLite file at
`memory/s7_3_guarded_self_modification/state.sqlite3`, includes `s7_traces` in
that table-prefix namespace, and requires trace writes to participate in the
same `BEGIN IMMEDIATE` transaction as consume and mutation-precondition checks.
D22 later says traces live in a separate `traces.sqlite3` file.

Those cannot both be true without reintroducing the cross-store atomicity
problem v11 says it closed. Since v11 explicitly chooses one shared SQLite file,
the panel lane lean is: keep the D22 trace schema, but store traces through
`S7TraceWriter` in `state.sqlite3`.

**v12 fix:** Delete or rewrite the separate `traces.sqlite3` claim. State that
`S7TraceWriter` writes into `state.sqlite3` under the same injected connection
and transaction as consume, rollback precheck, and trace finalization.

### Cluster B - Invocation Carrier vs Loose Consume API

**Severity:** Blocker/major, convergent across reviewers 2, 3, and 4.

v11 says wrappers pass one complete `S7GuardedExecutionInvocation` and fail if
they cannot load it. The consume API still exposes loose kwargs:
`artifact_id`, `consumer_id`, `rendered`, `action_params_hash`,
`authority_context`, `precondition_hash`, `derived_work_class`,
`derived_aggregation_group`, `source_ref_hash`, `reservation_token`, and other
fields. D24 then says wrappers call consume using the invocation carrier
without inventing loose kwargs.

That leaves two implementation contracts: consume takes the carrier, or consume
takes unpacked kwargs.

**v12 fix:** Pick one. Lane lean: public guarded consume accepts
`invocation: S7GuardedExecutionInvocation`; if a lower-level primitive unpacks
fields, name exactly one `unpack_guarded_execution_invocation(...)` helper that
recomputes and verifies `guarded_execution_invocation_hash` before forwarding.

### Cluster C - Request And Invocation Stores Cannot Round-Trip Promised Objects

**Severity:** Blocker, convergent across reviewer 2 and related to reviewer 3.

`WorkRequestEnvelopeStore.get(...) -> WorkRequestEnvelope` is load-bearing, but
the illustrative DDL stores only request id, hash, expiry, and created_at.
`S7GuardedExecutionInvocationStore.get(...) -> S7GuardedExecutionInvocation`
is also load-bearing, but the table stores only the invocation hash plus a
subset of fields, omitting rendered, authority context, adapter ids, rollback
ref, supersession ids, and ceremony evidence.

If these stores are reconstruction indexes over other durable stores, the spec
must say so and require the recomputed full-object hash to match the persisted
hash. Otherwise wrapper exclusivity becomes trusted local convention.

**v12 fix:** Either store every field needed to round-trip the object, or define
the reconstruction refs and hash verification rule explicitly for each store.

### Cluster D - ActionEdgeGrantUse Persistence And Replay Domain

**Severity:** Blocker/major, convergent across reviewers 2 and 4.

The `ActionEdgeGrantUse` dataclass includes `execution_consumer_id` and
`grant_use_replay_token`, but the illustrative DDL omits both. The
`action_edge_key` formula depends on `target_ref_hashes_before_mutation`, but
the tuple order, target-ref source, and persisted column/ref are not defined.

**v12 fix:** Persist the load-bearing fields named by the dataclass, define the
ordered target-ref hash tuple and its source, and ensure
`action_edge_replay_token` is recomputable from persisted refs.

### Cluster E - Credential Source-Method And Manifest Null Normalization

**Severity:** Blocker/major, convergent across fresh-reader residual gate and
Codex reviewers 2 and 4.

`S7CredentialGuardedRequest.source_method` allows:

```text
register | backup_card | disable | register_finish
```

The manifest matrix uses:

```text
register_primary | backup_register | backup_card | disable
```

Prose also uses `register_begin` and `register_finish`. Credential rows also
show `N/A` in `work_source_kind`, while `S7SurfaceManifestRow.work_source_kind`
is `str | None`.

**v12 fix:** Align the credential source-method vocabulary or declare a bridge
function between surface-manifest source methods and credential request source
methods. State that matrix `N/A` is display-only and persists as null, not the
literal string `"N/A"`.

### Cluster F - Protective Reason Canonicalization Conflict

**Severity:** Major, convergent across reviewers 2, 3, and 4.

D-Enum says persisted and replayed rows use string `"none"`, not Python `None`.
D13 still says `protective_block_reason` is `None` except named blocks, and the
reducer table does not make `protective_block_reason` and
`classifier_reason_code` row outputs fully explicit.

**v12 fix:** Replace D13's `None` wording with string `"none"` and add
`protective_block_reason` / `classifier_reason_code` outputs to reducer rows or
an explicit row-output table.

### Cluster G - Nonce Carrier/DDL Alignment

**Severity:** Major, convergent across reviewers 2 and 4.

Nonce DDL stores `attempt_index` and uses it in uniqueness and transition rules.
`S7ConsultationNonceUse` omits `attempt_index`, while
`transition_nonce_use(...)` requires it. One reviewer also noted that the
partial uniqueness condition should be expressed as a SQLite partial unique
index, not table-constraint prose.

**v12 fix:** Add `attempt_index` to `S7ConsultationNonceUse`; express the active
reserved-nonce uniqueness as an explicit partial unique index.

### Cluster H - Failure-Code Partition Still Has Collapsed Inherited Branches

**Severity:** Blocker/major, strongest from reviewer 2.

The wrapper must not guess after collapsed inherited failures, but the amended
inherited consume still returns only:

```text
tuple[S7ExecutionGrant | None, object | None]
```

with no failure carrier. Either the wrapper must preflight every residual branch
explicitly, or inherited consume needs a typed failure result.

**v12 fix:** Pin the partition: wrapper-side preflight owns every named
failure-code branch before inherited consume, and inherited residual returns map
only to explicitly named residual codes; or amend inherited consume to return a
typed failure result.

## Single-Lens Or Narrow Findings

### Approval-Card Execution Lacks D21 Wrapper Seam

**Source:** Reviewer 1. **Severity:** Major.

D4 marks Telegram, cockpit, daemon, and S7-card WebAuthn approval-card paths as
`live_guarded` rows using `guarded_card_execute`. D21 lists guarded card
execution as a mutation consumer. The concrete wrapper list names dream,
evolution, workshop, ActionEngine, model-routing, and credential wrappers, but
no approval-card wrapper.

A cold implementer would have to invent whether approval cards get
`execute_guarded_card_execution(...)`, lower into
`execute_guarded_action_engine_mutation(...)`, or fail closed per concrete card
subtype.

**v12 fix:** Add the card wrapper or explicitly remap each approval-card row to
an existing reviewed wrapper with same-code coverage.

### First-Primary Credential Bootstrap Carries Backup Consumer ID

**Source:** Reviewer 1. **Severity:** Minor.

The matrix marks first-primary credential bootstrap as `reviewedly_excluded` but
still assigns `s7_credential_register_backup`, while prose says it is excluded
until a future bootstrap slice names its own consumer id and trace semantics.

**v12 fix:** Make the row non-mintable/excluded without assigning the backup
consumer id, or assign a reviewed-excluded bootstrap-specific id that cannot
mint.

### Parent `action_engine_final_mutate` Remains In Closed Consumer Set

**Source:** Reviewer 1. **Severity:** Minor.

The enum includes `action_engine_final_mutate` while the spec says L8 positive
evidence must use concrete child ids.

**v12 fix:** Mark parent id non-mintable/non-positive or remove it from the
mintable closed set.

### `grant_id` Derivation Uses Uncarried Fresh Nonce

**Source:** Reviewer 2. **Severity:** Major.

The spec gives a `grant_id` formula involving a fresh nonce, but that nonce is
not otherwise carried on `S7ExecutionGrant` or `GrantUse`.

**v12 fix:** Either persist the nonce/ref used in the derivation or change the
formula to use existing persisted fields.

### Final Bundle Omits `marker_text_hash`

**Source:** Reviewer 2. **Severity:** Major/bookkeeping.

The draft/parser/attempt evidence carry marker text hashes and authority
booleans depend on marker replay, but the final bundle field list omits
`marker_text_hash`. If raw-response replay is the sole source, say so
explicitly.

**v12 fix:** Add the field or state that final bundle replay obtains marker text
only through raw-response and semantic-attempt refs.

### Credential Trace Idempotency Key References Missing Fields

**Source:** Reviewer 4. **Severity:** Major.

D9 defines credential trace idempotency as
`(request_id, credential_operation, credential_id_hash)`, but the credential
trace carries `credential_action`, challenge fields, and binding refs, not
`credential_operation` or `credential_id_hash`.

**v12 fix:** Rename `credential_operation` to `credential_action` and either
add `credential_id_hash` to the trace or change the idempotency key to carried
fields.

### Request-Family Derivation Leaves Caller-Supplied-Looking Field

**Source:** Reviewer 4. **Severity:** Major.

`S7RequestHistoryRecord` has both `request_family` and
`request_family_derived`. The spec says the writer derives the family and
callers cannot supply `request_family_derived`, but it does not clearly reject
or ignore caller-supplied `request_family`.

**v12 fix:** Make the caller-supplied family impossible or ignored; persist only
the derived family, or state that `request_family` is legacy-read-only and not
accepted by S7.3 writers.

### Surface Manifest `created_at` Missing From Shape

**Source:** Reviewer 4. **Severity:** Minor.

The spec says `S7SurfaceManifest.manifest_id` and `created_at` are persisted and
excluded from hash, but the shown `S7SurfaceManifest` shape has no `created_at`
field.

**v12 fix:** Add `created_at` to the shown shape or delete the claim.

### Trace Status / D23 State Producer Gaps

**Source:** Reviewer 4. **Severity:** Minor.

`legacy_operational_excluded` and `blocked_pre_mutation_state_changed` are
accounted for, but `authorized`, `bridge_failed`, `rollback_failed`, and
`manual_review_required` need explicit producer seams or reviewed-unreachable
rationale.

**v12 fix:** Add producer/reachability rows.

### Attempt Input Audit Field

**Source:** Reviewer 2. **Severity:** Minor.

`attempt_input_hash` claims to bind classifier input but includes
`attempt_started_at`, which is audit context rather than classifier input.

**v12 fix:** Rename the hash domain to classifier-attempt input or remove the
audit field from the classifier-input tuple and hash it elsewhere.

### Stale Wording And Signature Polish

**Source:** Reviewer 2. **Severity:** Minor/nit.

- A stale `v9` wording remains in a v11 section.
- Python-ish signatures use lowercase `callable`; use `Callable[...]` if the
  blocks are meant to be grep-stable signatures.

## Affirmations

The Codex panel preserved the core v11 trajectory:

- `S7GuardedExecutionInvocation`, request stores, `S7TraceWriter`,
  `attempt_input_hash`, bundle draft, action-edge use, nonce transitions,
  rollback migration, and failure-code vocabulary are the right kind of spec
  material.
- Marker-only evidence remains current-attempt operational and cannot poison
  D23.
- D19 bridge semantics are strong: exactly one request-history row per
  eligible authority row, idempotent retry, writer-derived family, and
  suppression of S7.3 operational legacy refusal writes.
- ActionEngine shell delegation risks are aimed at real inherited code; in
  particular, `append_to_file` still delegates through shell in committed code
  and v11 correctly fails that for L8 unless replaced by a direct-write adapter.
- The D24 test catalog is strong enough to drive RED-first implementation once
  the contradictions above are removed.
- Same-box caveats are honest and not overstated.
- No-hand-assembled positive proof remains explicit and broad.

## Cross-Check Against Fresh-Reader Gate v11

The Codex panel converges with the fresh-reader residual-hunter on:

- credential source-method drift;
- credential trace idempotency key terminology;
- protective reason canonicalization;
- nonce carrier/DDL alignment;
- approval-card route concreteness as a dependent surface-manifest issue.

The Codex panel broadens v12 beyond the initial manifest-dependency fold on:

- trace storage atomicity;
- invocation carrier vs loose consume API;
- request and invocation store round-trip;
- ActionEdge persistence/replay fields;
- inherited consume failure partition.

No finding asks to reopen the covenant architecture. The broadening is
engineering-contract closure at the same canonicalization bar.

## Recommendation - v12 Fold Scope

v12 remains a consistency fold, but no longer only the fresh-reader residual
manifest cluster. It should absorb:

1. trace storage atomicity: one SQLite file, `s7_traces` through
   `S7TraceWriter`, same transaction;
2. invocation-to-consume API: carrier parameter or one verified unpacking seam;
3. request/invocation store round-trip or reconstruction refs with hash
   verification;
4. ActionEdgeGrantUse DDL and replay domain;
5. failure-code partition for collapsed inherited consume failures;
6. derivation table for every concrete matrix row;
7. approval-card wrapper/remap seam;
8. credential source-method/null normalization;
9. protective reason canonicalization in D13/reducer outputs;
10. nonce carrier/DDL/partial unique index alignment;
11. credential trace idempotency key field names;
12. first-primary credential bootstrap non-mintable row;
13. parent `action_engine_final_mutate` non-mintable/non-positive treatment;
14. grant-id derivation;
15. final bundle marker-text replay path;
16. request-history family caller-supplied field closure;
17. smaller stale wording, status producer, and signature polish.

This is broader than the fresh-reader gate predicted, but still not a redesign.
It is the set of places where v11 named the right objects but left storage,
signature, or closed-vocabulary dependents out of sync.

## Plain English

Codex did not find a new architecture problem. It found the final boring-hard
layer: the spec now names the right carriers, but a few of those carriers still
do not round-trip through the store tables or the consume API exactly as written.

The biggest issue is trace atomicity. v11 says trace writes are in the same
transaction as consume, then later says traces live in a separate SQLite file.
That cannot both be true. The second biggest issue is the invocation carrier:
v11 says wrappers pass one complete invocation, but the consume API still takes
loose kwargs. Pick one.

So v12 is no longer the tiny three-line residual fold. It is still not design
work. It is a canonicalization consistency fold: one database, one invocation
contract, round-trippable stores, replayable action-edge rows, aligned
credential tokens, and exact reducer/status outputs.
