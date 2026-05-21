# Codex Engineering Panel v16 - S7.3 Guarded Self-Modification Execution Spec

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`

**Spec commit:** `9563087212640b675954f6b798116ca8fd5195d3`

**Spec blob:** `af4fd5dec7ce457ca1d08f89cb933470bcbabba3`

**Spec SHA256:** `57729e48e773db53b9ff6b94329faa38749056ca6a7753fee3741251059c053d`

**Panel date:** 2026-05-20

## Verdict

**REVISE.**

Raw reviewer split:

| Reviewer | Lens | Verdict | B | M | m | n |
|---|---|---:|---:|---:|---:|---:|
| Reviewer 1 | Persistence round-trip | REVISE | 2 | 1 | 1 | 0 |
| Reviewer 2 | Route/mintability | RATIFY-with-fold | 0 | 3 | 2 | 0 |
| Reviewer 3 | Cold implementor / RED-test | REVISE | 0 | 2 | 1 | 1 |
| Reviewer 4 | D21/D22 execution contract | REVISE | 1 | 3 | 0 | 0 |

Deduped panel shape:

- **Blockers:** 3
- **Majors:** 6
- **Minors:** 3
- **Nits:** 1

Plain English: v16 made the right structural moves. The stubborn credential
carrier is now hash/ref-shaped, fail-closed routes mostly stopped carrying
mintable ids, WorkRequestEnvelope persistence is buildable, request-history
cutoff storage is materially closed, and ActionEdge replay is much stronger.
But the spec still has several places where a cold implementor would have to
invent missing bytes, store arguments, or callback ownership rules. That means
v17 is required before canonicalization.

## Blockers

### B1 - `unpack_guarded_credential_invocation(...)` cannot call the bundle loader as specified

`load_guarded_credential_invocation_bundle(...)` requires these inputs:

- `credential_request_store`
- `rendered_statement_store`
- `authority_context_store`
- `conn`

But `unpack_guarded_credential_invocation(...)` only receives
`credential_invocation_store` and `now`, then prose says it first calls the
bundle loader.

Evidence:

- `spec.md:1966-1973` defines the bundle loader inputs.
- `spec.md:2012-2019` defines the unpack helper without those stores or the
  connection.
- `spec.md:2023-2027` says the helper first calls the loader.

Why this blocks: a builder must invent hidden store composition or add
unstated helper parameters.

Fold shape: add the needed store and connection parameters to
`unpack_guarded_credential_invocation(...)`, or state that
`S7GuardedCredentialInvocationStore` is a composite object that owns those
stores and connection. The former is clearer.

### B2 - Credential rollback binding names fields not persistable through invocation and trace schemas

The spec requires credential rollback lines to match rendered statement,
artifact binding, invocation, and trace. But the invocation carrier/DDL do not
carry `rollback_path_class` or `rendered_rollback_lines_hash`, and
`s7_credential_trace_payloads` also omits fields required by the credential
trace shape.

Evidence:

- `spec.md:4065` says `RenderedCredentialRequestStatement` carries
  `rollback_path_class` and `rendered_rollback_lines_hash`.
- `spec.md:2453-2455` stores those fields on artifact binding.
- `spec.md:1927-1953` and `spec.md:2570-2599` omit them from
  `S7GuardedCredentialInvocation` and its DDL.
- `spec.md:5497` includes rollback path class on the credential trace shape,
  while `spec.md:2703-2714` omits it from `s7_credential_trace_payloads`.
- `spec.md:6061-6064` demands the rollback binding test match artifact
  binding, invocation, and trace.

Why this blocks: the named D24 test cannot be implemented without inventing
fields or weakening the test.

Fold shape: either persist `rollback_path_class` and
`rendered_rollback_lines_hash` on `S7GuardedCredentialInvocation` and its DDL,
or revise the binding rule so invocation binds rollback by `rollback_plan_ref`
only while trace/artifact/rendered rows carry the detailed rollback line
fields. The trace payload must carry the fields required for whichever rule is
chosen.

### B3 - Voice trace payload DDL requires a post-render field the voice trace cannot have

`S7VoiceConsultationTrace` is begun/finalized by the voice trace writer before
the final founder-rendered D12 statement exists. But `s7_voice_trace_payloads`
requires `final_rendered_statement_hash TEXT NOT NULL`.

Evidence:

- `spec.md:2079-2080` names begin/finalize voice trace methods.
- `spec.md:5351-5397` lists the voice trace minimum fields without
  `final_rendered_statement_hash`.
- `spec.md:2677-2688` makes `final_rendered_statement_hash` non-null on
  `s7_voice_trace_payloads`.
- `spec.md:2725-2729` requires exactly one header and one typed payload row,
  with `trace_hash` over that payload.

Why this blocks: implementation must choose between a fake placeholder, a late
payload mutation outside the stated write model, or moving a post-render value
backward in time.

Fold shape: remove `final_rendered_statement_hash` from
`s7_voice_trace_payloads`, or split voice consultation trace from a later
authority/render trace that legitimately has the rendered hash.

## Majors

### M1 - Typed trace payload DDL is narrower than declared trace minimum shapes

v16 adds per-kind payload tables, but the tables persist only a subset of the
fields required by D22 trace shapes. Execution and credential traces are the
clearest examples: mutation hashes, artifact hash, action-edge id, credential
write result, rollback result, and several minimum fields are not present in
the payload DDL.

Evidence:

- `spec.md:2725-2729` says `trace_hash` verifies header plus typed payload.
- `spec.md:5399-5458` and `spec.md:5462-5519` declare larger execution and
  credential trace minimum shapes.
- `spec.md:2690-2701` and `spec.md:2703-2714` define narrower payload tables.

Fold shape: add `trace_payload_blob_ref` and `trace_payload_blob_hash` to each
typed payload table, with strict per-kind schema validation, or expand each
payload table to include every D22 minimum field for that trace kind.

### M2 - Stale credential wording still puts credential consumer ids on `S7ExecutionAuthorization`

One earlier section says credential requests carry closed
`execution_consumer_id` values on `S7ExecutionAuthorization`, while D21 says
legacy `S7ExecutionAuthorization` is compatibility-only for inherited
voice-seat paths and explicitly non-mintable for credential paths.

Evidence:

- `spec.md:1370-1372` contains the stale carrier wording.
- `spec.md:4757-4766` contains the correct v16 rule.

Fold shape: replace the stale wording with: credential requests carry closed
consumer ids on `S7CredentialGuardedRequest`,
`S7GuardedCredentialInvocation`, and artifact binding only;
`S7ExecutionAuthorization` fails closed for credential consumers.

### M3 - D21 ActionEngine mirror prose is stale against the D4 matrix

D21 correctly says the persisted manifest is authoritative, but a later D21
paragraph calls itself a complete D4 mirror while listing only a subset of
live-guarded ActionEngine rows.

Evidence:

- `spec.md:5095-5103` correctly defers to every live-guarded ActionEngine row
  in the persisted manifest.
- `spec.md:5306-5324` overstates a partial list as the complete D4 mirror.
- `spec.md:1211-1223` includes live rows such as `modify_config`,
  `register_new_skill`, `delete_file`, `write_file`,
  `promote_to_core_memory`, `update_baseline`, `git_commit`, and
  `integration_review_plan`.

Fold shape: make the D21 paragraph defer to `S7_ACTION_ENGINE_CONSUMER_IDS`
plus persisted manifest `route_status`, rather than hand-listing a partial
mirror.

### M4 - Acceptance prose overstates fail-closed surfaces as grant-consuming live paths

The implementation checklist still says self-mod dialog, CLI, cockpit, and
reviewed substrate adapters enter through `GuardedWorkItem` and require
consumed grants. The v16 matrix marks those rows fail-closed with no consumer
id.

Evidence:

- `spec.md:6332-6338` has the overstated checklist prose.
- `spec.md:1190-1195` marks those rows fail-closed with `N/A` consumer ids.
- `spec.md:6160-6162` keeps self-mod dialog terminal blocked.

Fold shape: say live rows require consumed grants; fail-closed and
reviewedly-excluded rows require `execution_consumer_id=None` plus a closed
exclusion reason.

### M5 - Manual-review writer signatures cannot construct the evidence shape

The public manual-review evidence writes are now trace-writer-owned, which is
right. But the method signatures do not carry enough inputs to build the
`ManualReviewEvidence` row.

Evidence:

- `spec.md:2070-2074` says public writes go through `S7TraceWriter` and write
  evidence plus trace transition.
- `spec.md:2086-2088` shows the current method signatures.
- `spec.md:2135-2147` defines `ManualReviewEvidence`.
- `spec.md:2639-2647` defines the manual-review evidence DDL.

Specific problem: `mark_manual_review_required(...)` lacks `review_id`,
`request_id`, and `review_reason_code`; completion/failure lack enough
reviewer/time/failure fields.

Fold shape: make trace-writer methods accept `ManualReviewEvidence` or
explicit required inputs, or define deterministic derivation for `review_id`
and `review_reason_code` from execution trace plus closed reason. Also remove
or constrain the caller-supplied `manual_review_status` parameter on
`mark_manual_review_required(...)`; that method should produce `pending`.

### M6 - Deprecated `consume_verified(...)` lacks a carrier-loading rule

The live API is carrier-only, but the deprecated compatibility wrapper takes
`S7ExecutionAuthorization` and says it delegates to
`S7GuardedStateStore.consume_artifact_for_execution(...)`. The spec does not
say how it obtains the required `S7GuardedExecutionInvocation`.

Evidence:

- `spec.md:4771-4777` defines carrier-only consume.
- `spec.md:4780-4783` rejects loose kwargs.
- `spec.md:4740-4754` shows `S7ExecutionAuthorization` lacks full invocation
  fields.
- `spec.md:5168-5198` defines the deprecated wrapper.

Fold shape: state that `consume_verified(...)` loads an already persisted
`S7GuardedExecutionInvocation` from
`S7GuardedExecutionInvocationStore.get(rendered.request_id, artifact_id)`,
verifies the equality chain, then calls
`consume_artifact_for_execution(invocation=loaded_invocation, ...)`. Missing
invocation fails closed. It must not construct invocation fields from
`S7ExecutionAuthorization`.

### M7 - Callback ownership is inconsistent between wrapper and inherited consume

The wrapper owns `after_consume_before_commit`, but the amended inherited
`S7AuthorizationStore.consume_for_execution(...)` also takes a callback typed
as `Callable[[S7ConsumeResult], object]` while returning only the inherited
two-tuple. The inherited store cannot honestly supply a wrapper-owned
`S7ConsumeResult` with durable `GrantUse`.

Evidence:

- `spec.md:1887-1893` and `spec.md:4771-4777` expose the wrapper callback.
- `spec.md:4806-4817` says the wrapper runs it after consume, `GrantUse`
  persistence, and bundle-use consumption.
- `spec.md:4911-4935` also places the same callback type on inherited
  consume.

Fold shape: make callback ownership wrapper-only. Remove the callback from the
inherited amended signature, or type it to the inherited primitive result and
state the wrapper passes no callback downward.

## Minors

### m1 - Rendered/authority store get-path verification should be explicit

`S7RenderedAuthorizationStatementStore` and `AuthorityContextStore` have APIs
and DDL, but their get-path verification is less explicit than
`WorkRequestEnvelopeStore.get(...)`.

Evidence:

- `spec.md:2523-2534` defines rendered statement blob/ref DDL.
- `spec.md:2536-2543` defines authority context blob/ref DDL.

Fold shape: add a one-line rule that each store loads the blob, verifies blob
hash, reconstructs the carrier, and verifies canonical hash.

### m2 - Telegram approval-card conditional should be wrapper rejection, not route derivation

The derivation table says `telegram.approval_card + approve_action` maps to
`guarded_card_execute only through execute_guarded_card_execution; otherwise
fail_closed_until_review`, but does not name an exclusion reason for the
otherwise branch. The matrix makes the live route concrete through the card
wrapper.

Evidence:

- `spec.md:1114` has the conditional row.
- `spec.md:1180` has the concrete live matrix row.

Fold shape: frame the non-wrapper path as wrapper rejection, not a second route
derivation result.

### m3 - Future-id rationale missing for shell-shaped aliases

`query_system` and `run_readonly_command` have fail-closed matrix rows and
special alias language, but `REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS` does not
reserve ids for them.

Evidence:

- `spec.md:1231-1232` marks both rows fail-closed.
- `spec.md:1264-1266` names them as shell-shaped aliases.
- `spec.md:638-667` lists reviewed-future ids without them.

Fold shape: either reserve future ids for these aliases or state they
intentionally have no future id because any reviewed version must route through
a newly named non-shell adapter.

## Nit

### n1 - Stale v15 wording remains in checklist prose

Some acceptance/checklist prose still says v15 where it now means v16.

Evidence:

- `spec.md:6340` says direct append adapter satisfies the item in S7.3 v15.

Fold shape: update stale v15 references where the sentence is describing the
current v16 draft rather than historical v15 behavior.

## Cross-Lane Convergence

The most important convergence:

- Credential carrier stale wording was found by Reviewers 1, 2, and 3.
- Typed trace payload incompleteness was found by Reviewers 1, 3, and 4.
- Manual-review writer shape was found by Reviewers 3 and 4.
- Route/mintability spine was affirmed by the route reviewer, with only stale
  prose and future-id rationale left.
- Covenant posture was not reopened by any reviewer.

## Affirmations

- The v16 hash/ref move for `S7GuardedCredentialInvocation` is the right
  structural direction.
- `WorkRequestEnvelope` persistence is now cold-implementable with blob/ref,
  blob hash, indexed load-bearing columns, and drift checks.
- Request-history cutoff persistence is substantially closed with marker
  carrier, ALTER migration, row fields, and validation.
- ActionEdge replay-domain persistence is materially improved: target refs and
  hashes are stored before mutation, reconstructed from child rows, and replayed
  through unique keys.
- The route/mintability invariant is now explicit: live-guarded rows require
  mintable ids; fail-closed/reviewed-excluded rows require null ids and closed
  exclusion reasons.
- `append_to_file` is pinned to `ActionEngine._do_append_to_file`; shell
  delegation cannot satisfy positive S7.3 evidence.
- `integration_review_plan` is normalized as the sole source-method token for
  that route.
- The same-box, marker/D23, operational-reliability, and manual-review
  covenant posture remains intact. v17 should be another engineering-contract
  fold, not a covenant or architecture round.

## v17 Fold Scope

The recommended v17 fold is narrow:

1. Add store/connection inputs or explicit composite-store ownership for
   `unpack_guarded_credential_invocation(...)`.
2. Reconcile credential rollback binding across rendered statement, artifact
   binding, invocation, trace, and D24 tests.
3. Fix voice trace payload timing by removing post-render fields or splitting
   trace kinds.
4. Complete typed trace payload persistence with payload blob/ref or full D22
   columns.
5. Remove stale credential `S7ExecutionAuthorization` wording.
6. Replace stale D21 partial mirror and checklist prose with manifest/set
   authority.
7. Make manual-review trace-writer methods able to construct complete evidence
   rows.
8. Pin deprecated `consume_verified(...)` to load an existing
   `S7GuardedExecutionInvocation`.
9. Make callback ownership wrapper-only.
10. Fold the three minor cleanups and stale v15 wording.

Plain English: v16 did the big turn correctly, but it left a few bolts loose.
The biggest repeated lesson is the same one from v15: if the spec says a store
or writer can rebuild a carrier, every byte or ref needed to rebuild it must
be named at the same level of precision as the carrier. v17 should be a small
persistence-and-signature fold, not a design round.

