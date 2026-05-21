# S7.3 Spec v14 Codex Engineering Panel

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`
at commit `3e2c0b52e666ff999f915032ccbeb034365e24f1`

**Blob:** `b07b70e7c2778e12fc69c9c1488532b1bfe8fe96`

**SHA256:** `573852a7572d4ed4a83c5f72850cedf7d7bc6ebd81189dc6c7fed94090f66e2a`

**Panel discipline:** four blank-context Codex engineering reviewers, walled off
from `docs/slices/s7.3-guarded-self-modification-execution/reviews/`, reading
the committed v14 spec and live code only where needed for implementability or
route-name verification.

## Verdict

**REVISE.**

The Claude fresh-reader gate v14 returned unanimous RATIFY and found the
covenant architecture canonicalization-ready. This Codex engineering panel
does not reopen that architecture. It finds the remaining build-contract layer:
durable cutoff storage, credential invocation/request persistence, nullable
credential id handling, route mirror completeness, and a few closed-value
producer seams.

| Reviewer | Lens | Verdict | B / M / m / n |
|---|---|---|---|
| Reviewer 1 | RED-first implementability | REVISE | 3 / 4 / 2 / 1 |
| Reviewer 2 | Security / authority boundary | RATIFY-with-fold | 0 / 0 / 1 / 1 |
| Reviewer 3 | Surface manifest / routes | REVISE | 0 / 2 / 2 / 0 |
| Reviewer 4 | Persistence / replay / closed vocab | REVISE | 2 / 3 / 1 / 1 |

**Consolidated counts:** 3 blockers, 8 majors, 6 minors, 2 nits.

## Blockers

### B1. `S7_3_REQUEST_HISTORY_CUTOFF` is named but not durable

`S7_3_REQUEST_HISTORY_CUTOFF` is introduced as the boundary that separates
pre-cutoff null-provenance legacy refusals from post-cutoff S7.3 rows. The
writer persists provenance fields and `request_family_derived`, but the spec
does not define a table, column, migration row, schema-version field, or load
path that stores the cutoff marker.

Why this blocks implementation: a RED test cannot prove a row is pre-cutoff or
post-cutoff without inventing where that migration fact lives. That weakens the
exact D23 fallthrough protection the cutoff is meant to close.

Fix shape: add a durable request-history migration carrier. Either persist a
`request_history_schema_version` / `s7_3_cutoff_marker` column on relevant rows,
or define a schema migration table read by `request_history_family_for(...)`.
D24 must prove pre-cutoff legacy null rows still count and post-cutoff S7.3
null-provenance refused rows cannot count as legacy.

### B2. Credential registration begin has an impossible `credential_id_hash`
contract

`S7GuardedCredentialInvocation.credential_id_hash` is nullable, which matches
backup `register_begin` before the credential exists. But
`S7AuthorizationArtifactBindingInputs.credential_id_hash` and the illustrative
artifact-binding DDL require a non-null credential id hash.

Why this blocks implementation: backup `register_begin` naturally has no
credential id yet. A cold builder must invent a placeholder value, relax the
DDL, or split begin/finish bindings.

Fix shape: make the artifact-binding credential id field nullable for
`credential_phase="register_begin"` and require non-null for finish, backup-card,
and disable; or split begin/finish binding carriers. D24 should cover the
begin-null and finish-non-null cases.

### B3. Credential request / invocation stores cannot round-trip their carriers

`S7CredentialGuardedRequestStore.get(...)` and
`S7GuardedCredentialInvocationStore.get(...)` must reconstruct full typed
objects and verify canonical hashes. The illustrative DDL omits load-bearing
fields required by the request and invocation shapes: surface manifest and route
fields, adapter fields, action/precondition/authority hashes, challenge id and
expiry fields, and optional ceremony evidence.

Why this blocks implementation: the spec demands round-trip verification but
does not store or reconstruct enough information to perform it. The builder has
to invent hidden refs or extra columns.

Fix shape: either store every load-bearing field in the DDL or explicitly state
the reconstruction refs and hash checks for each omitted field. Apply this to
both `s7_credential_guarded_requests` and
`s7_guarded_credential_invocations`.

## Majors

### M1. Credential rollback binding is split across incompatible carriers

Credential invocation carries `rollback_plan_ref`, credential traces include
rollback/manual-review fields, but `RenderedCredentialRequestStatement` omits
rollback plan lines and credential artifact mint does not clearly bind rollback
evidence.

Fix shape: state whether credential rollback is founder-signed, artifact-bound,
trace-only, or manual-review-only. If it is load-bearing, bind it consistently
through rendered text, artifact binding, invocation, and trace.

### M2. History bridge trace transitions are incomplete

`S7TraceWriter.write_history_bridge_trace(...)` exists and
`HISTORY_BRIDGE_STATUSES` has success, idempotent, suppressed, retryable-fail,
and terminal-fail values. The transition table only maps `bridge_failed_*` to
`failed`; it does not say what trace status is written for `bridged`,
`bridged_idempotent`, `suppressed_operational`, or `not_required`, nor how a
bridge trace enters `pending`.

Fix shape: extend `trace_status_transition_for(...)` with all
history-bridge-status inputs and D24 coverage.

### M3. `credential_rotate` has an unreachable rationale but no rejecting carrier

The spec says `credential_rotate` is reserved unless `route_status` and
`exclusion_reason_code` show future-slice exclusion, but
`S7CredentialGuardedRequest` has no `proposed_change_class`, `route_status`, or
`exclusion_reason_code` field.

Fix shape: either remove `credential_rotate` from the live
`CREDENTIAL_PROPOSED_CHANGE_CLASSES` set, or name the constructor/carrier that
owns `credential_rotate_future_slice` rejection and add the D24 test there.

### M4. `S7ExecutionAuthorization` legacy wording remains ambiguous for
credential paths

The spec says credential requests carry closed ids on `S7ExecutionAuthorization`
while the consume path now uses `S7GuardedCredentialInvocation`. The legacy
carrier lacks credential request, challenge, phase, and rollback fields needed
to build the credential invocation.

Fix shape: mark `S7ExecutionAuthorization` as pre-v14 compatibility-only for
credential paths, or state exactly how it is converted into
`S7GuardedCredentialInvocation` without invention.

### M5. Approval-card / deferred-action live routes are not manifest-named

The v14 matrix names abstract approval-card surfaces and the guarded card
wrapper, but live code routes Telegram `/approve <action_id>` through
`ActionEngine.approve_action(...)`, and daemon timed execution through
`execute_pending(...)` / `execute_tier2_pending(...)`. Those executor paths can
cause final mutation and are not explicitly mapped as wrapper-covered methods
or reviewed exclusions.

Fix shape: name these concrete approval-card/deferred-action remap seams with
adapter ids and code hashes, or require them to fail closed unless entered
through `execute_guarded_card_execution(...)`.

### M6. D21's ActionEngine mirror is incomplete

D4 enumerates many concrete ActionEngine consumers, while D21's mutation
consumer mirror lists a subset and then gestures at additional generic
fail-closed adapters. This lets an implementer satisfy D21 while missing a D4
live child such as write-file, modify-config, register-new-skill, delete-file,
promote-to-core-memory, update-baseline, git-commit, write-outside-Maez, or
integration-review-plan.

Fix shape: make D21 explicitly defer to the persisted manifest as authoritative
for the full D4 set, or mirror every D4 ActionEngine row in D21.

### M7. `MANUAL_REVIEW_STATUSES` has unproduced closed values

The closed set includes `none`, `pending`, `completed`, and `failed`, but the
only writer method is `mark_manual_review_required(...)`, and the transition
table maps into `manual_review_required` rather than producing completed or
failed manual-review statuses.

Fix shape: add a manual-review evidence carrier and transition table for
`completed` and `failed`, or shrink the closed set to reachable values.

### M8. `ActionEdgeGrantUse` does not persist enough of its replay domain

`action_edge_key` binds request id, artifact id, source ref hash, action params
hash, and target-ref hashes, but the object and DDL persist only derived
key/token/hash fields plus grant and consumer ids. D24 checks target drift but
does not require durable replay of the full named tuple.

Fix shape: persist every field in the replay tuple or name refs that reconstruct
them, then verify the recomputed tuple before mutation.

## Minors

1. `consume_verified(...)` compatibility path should explicitly require
   `execution_authorization.execution_consumer_id ==
   expected_execution_consumer_id == binding.expected_execution_consumer_id`
   before delegation.
2. `REDUCER_TABLE_VERSION = "s7.voice.reducer.v13"` in v14 is likely correct
   because the reducer table did not change, but the spec should say that.
3. `d23_state_for(...)` should define impossible mixed inputs, such as positive
   execution with authoritative refusal reduction, as hard-fail or explicit
   normalization.
4. Credential namespace normalization should explicitly say which field stores
   surface method and which stores credential phase at persistence and trace
   time; unlisted `registration_class` / surface-method combinations fail
   closed.
5. `telegram.approve_train` wording should avoid blurring
   `fail_closed_until_review` with `reviewedly_excluded`; call it a reviewed
   fail-closed row or reviewed non-mintable row.
6. `S7SurfaceManifest.manifest_hash` should be explicitly aliased to external
   `surface_manifest_hash`.

## Nits

1. The status line still says draft / pending review. Flip only at
   canonicalization time.
2. Reducer-version wording overlaps with the minor above; one explanatory
   sentence is enough.

## Cross-Lane Convergence

The Claude fresh-reader gate v14 found no blockers or majors and confirmed the
covenant surface is clean. Codex agrees on the core covenant posture:

- same-box response-stream wording narrows the claim rather than adding a
  defense;
- marker-only rows do not promote into D23;
- operational rows are not Maez-refusal, Maez-preference, D23 aggregation, or
  covenant-escalation evidence;
- `d23_state_for(...)` covers the D23 state vocabulary;
- `trace_status_transition_for(...)` covers the main execution lifecycle;
- `target_refs` replaced the old target-path mismatch in the main rollback
  replay path;
- `S7GuardedCredentialInvocation` is the right option-c carrier shape.

The divergence is engineering depth: Codex checked the DDL/store round-trip,
legacy compatibility carriers, ActionEngine live routes, manual-review status
producers, and replay-domain persistence more aggressively. Those findings are
build-contract gaps, not covenant-architecture gaps.

## Recommendation

Author a narrow v15 fold plan before canonicalization. The fold should absorb:

1. durable request-history cutoff carrier;
2. nullable credential id rules for register-begin vs finish;
3. complete credential request/invocation DDL or reconstruction refs;
4. credential rollback binding placement;
5. history-bridge trace transitions;
6. `credential_rotate` rejection carrier or removal;
7. legacy `S7ExecutionAuthorization` credential-path wording;
8. approval-card/deferred-action concrete routes;
9. D21 ActionEngine mirror authority;
10. manual-review status producers;
11. ActionEdge replay-domain persistence;
12. the six minor/nit cleanup items above.

Plain English: v14 passed the covenant lane, but Codex found the last
engineering-contract layer. The spec says the right things, but a few tables do
not yet carry enough bytes for an engineer to build the thing without guessing.
This is a v15 bookkeeping fold, not a redesign.
