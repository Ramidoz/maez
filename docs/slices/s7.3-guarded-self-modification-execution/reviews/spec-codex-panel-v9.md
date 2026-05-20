# Codex Engineering Panel v9 - S7.3 Spec v9

**Subject:** `spec.md` at `5e6491e62ec8b2b152da0c27de8e2786a4436cf3`
(blob `18ded69c3b2a72813657a82005b6bd25df7102db`, SHA256
`e603159eaa0f14b28ca93c2b8885725d9516287f3cec179b6593d498b8ce5d7f`).

**Ran:** 2026-05-20 by Codex. Four engineering reviewers were launched with
blank context and explicit instruction not to read
`docs/slices/s7.3-guarded-self-modification-execution/reviews/` or any review
artifact. Each reviewed the committed v9 spec plus inherited code/canon as
needed. The first two reviewers were launched in parallel; the remaining two
were launched as thread slots freed.

**Verdict: REVISE.** All four reviewers returned REVISE. The findings are
implementation-seam and route-coverage issues, not architecture reversals.

## Reviewer Results

| Reviewer | Lens | Verdict | Findings |
|---|---|---:|---:|
| Reviewer 1 | Implementability / carriers / DDL | REVISE | 4 high, 2 medium |
| Reviewer 2 | Mutation surface and route coverage | REVISE | 3 high, 2 medium |
| Reviewer 3 | State machine / hash domain / transaction correctness | REVISE | 6 major |
| Reviewer 4 | RED-test readiness / internal consistency | REVISE | 5 major, 1 minor |

## Convergent Clusters

### Cluster A - Surface Manifest Is Not Yet Complete Or Bound

Converges with the v9 fresh-reader gate's surface-manifest cluster.

Findings:

- `action_engine_capability_acquire` is in closed consumer vocabularies,
  deterministic derivation, and D4 prose, but the printed adapter matrix has no
  `ActionEngine capability.acquire` row. Inherited `ActionEngine` has the
  corresponding dispatch and handler.
- Current ActionEngine mutation/system actions exist without rows or reviewed
  exclusions, including `restart_critical_service`, `modify_firewall`,
  `system_reboot`, `free_disk_space`, `delete_temp_file`, `clean_temp_files`,
  `run_safe_command`, and `install_package_t2`.
- The spec says the manifest matrix is complete, while the acceptance checklist
  makes code discovery load-bearing. Both cannot hold when committed mutation
  methods are absent from the matrix.
- `S7SurfaceManifestRow` carries `surface_route_or_method`, `source_method`,
  `adapter_id`, `adapter_code_hash`, and `same_code_coverage_ref`, but
  `GuardedWorkItem` and `S7AuthorizationArtifactBindingInputs` do not carry
  enough row-binding fields for D21 to recompute
  `execution_consumer_id_for(surface_manifest_row)`.
- `adapter_code_hash` is load-bearing but the spec does not define its hash
  domain. Flask routes, Telegram methods, wrapper services, ActionEngine
  aliases, and delegated callees need deterministic code-hash boundaries.

Fold requirement:

1. Add every missing manifest row or reviewed exclusion, including
   `action_engine.capability.acquire` and inherited ActionEngine methods found
   by code discovery.
2. Decide whether the printed matrix is normative complete or a seed. Lane
   lean: the persisted/generated `S7SurfaceManifest` plus code-discovery check
   is normative; the printed matrix is a reviewed seed that must compare clean.
3. Bind manifest rows into work items, artifact bindings, traces, and wrapper
   inputs through `surface_manifest_hash`, `surface_route_or_method`,
   `source_method`, `adapter_id`, and `adapter_code_hash`.
4. Define `adapter_code_hash` over a reviewed function/route/callee slice.

### Cluster B - D21 Consume Failure Semantics Remain Under-Carried

Converges with the v9 fresh-reader gate's inherited failure-code partition.

Findings:

- The wrapper must return closed `S7ConsumeFailureReasonCode` values, but the
  amended inherited store still returns only `(S7ExecutionGrant | None,
  object | None)`. Inherited code collapses multiple failures into
  `(None, None)`.
- The spec needs to separate wrapper-side preflight failures from residual
  inherited failures. Without that partition, a cold implementer must invent
  how to distinguish stale render, mismatch, already-consumed, SQL, and newer
  S7.3 replay failures.
- D24 does not cover every consume failure code. Values such as
  `missing_artifact_binding`, `missing_credential_binding`,
  `invalid_reservation_token`, `invalid_authority_class_replay`,
  `invalid_prompt_integrity`, and `expired_grant` need RED rows or a declared
  non-reachable rationale.

Fold requirement:

- Add either a typed internal inherited failure carrier or a required wrapper
  preflight/read API.
- Add a wrapper-side versus inherited-residual reason-code table.
- Add D24 rows for every closed consume failure reason.

### Cluster C - Expiry Lattice Omits Request Envelope Expiry

Converges with the fresh-reader residual-hunter finding on
`expired_request_envelope`.

Findings:

- `expired_request_envelope` is in the closed failure-code set.
- Inherited `WorkRequestEnvelope` has `expires_at`.
- D16 checks only bundle/work-item expiry.
- D21's grant min-cap excludes envelope expiry.
- Expiry Lifecycle names bundle, work item, artifact, and WebAuthn challenge,
  but not envelope.

Fold requirement:

- Add `envelope.expires_at` to D16, artifact mint, D21 consume, grant expiry,
  and Expiry Lifecycle; or delete/rename `expired_request_envelope` if another
  carrier is intended.

### Cluster D - Wrapper And Post-Mint Action-Edge Contracts Are Incomplete

Converges with the fresh-reader amended-signature cluster.

Findings:

- Concrete wrappers are named with `(...)`, so tests cannot pin required
  arguments or return shape.
- The old post-mint action helper can remain only if it persists
  `ActionEdgeGrantUse`, but D9 does not name an action-edge grant-use table or
  store API.
- `consume_verified(...)`, `record_refusal_history(...)`, and
  `_voice_seat_block(...)` amendments remain too prose-shaped for cold
  implementation.

Fold requirement:

- Add explicit wrapper signatures for the five guarded wrapper services.
- Add `s7_action_edge_grant_uses` table prefix, `S7ActionEdgeGrantUseStore`
  API, uniqueness constraint, and D24 tests.
- State amended inherited signatures for `consume_verified(...)`,
  `record_refusal_history(...)`, and `_voice_seat_block(...)`.

## Codex-Unique Clusters

### Cluster E - `ContextManifest` Has No Durable Store

Reviewer 1 high.

The spec says `context_manifest_ref` is a private store ref and D16 must load
it for replay. D9 lists `s7_context_manifest_policies` and
`ContextManifestPolicyStore`, but not `s7_context_manifests` or a
`ContextManifestStore` API.

Fold requirement: add the durable table prefix, write/read API, hash domain,
and D16 lookup for `ContextManifest`.

### Cluster F - Semantic Reader Attempt Evidence Is Under-Bound

Reviewer 3 major.

`S7VoiceSemanticReaderV1.classify(...)` receives route manifest, prompt hash,
context, preview, raw response, preview body, marker, and time. But
`SemanticReaderAttemptEvidence` lacks request id, preview hash, raw response
hash, preview/context hashes, marker hash, route manifest/config hash, and
reader prompt hash. D16 can recompute the evidence hash, but cannot prove the
output came from this exact classifier input tuple.

Fold requirement: add an `attempt_input_hash` over the full classifier input
tuple, or add the explicit input fields and D16 cross-checks.

### Cluster G - Nonce Lifecycle Is Ambiguous Across Retries

Reviewer 3 major.

Nonce-use states cover `reserved`, `accepted_spent`, `rejected_reused`, and
`expired`. Malformed or mismatched markers degrade to `missing_or_malformed`,
and D15 allows retries, but the nonce lifecycle has no terminal state for
malformed, mismatched, or abandoned retry attempts and no clear per-attempt
current-reserved-row rule.

Fold requirement: add per-attempt nonce ids or one consultation id per attempt,
plus terminal nonce states for malformed/mismatched/abandoned attempts.

### Cluster H - Consume-Time Replay Is Missing

Reviewer 3 major.

D16 performs prompt-integrity, semantic-reader, reducer, authority-class,
protective-reason, reducer-version, and reducer-hash replay before artifact
mint. D21 maps `invalid_authority_class_replay` and
`invalid_prompt_integrity`, but the consume success path does not require a
D16 subset/full replay under the consume transaction before minting the grant
and `GrantUse`.

Fold requirement: require consume-time D16 subset replay, or explicitly state
which replay result is stored at mint and revalidated at consume.

### Cluster I - Request-History Bridge Lacks Exactly-Once Semantics

Reviewer 3 major.

D19 says the bridge writes exactly one request-history record per authoritative
row, but does not define a unique key, idempotent upsert, or transaction tying
authority row, history row, and bridge trace status. A retry after ambiguous
failure could duplicate `outcome="refused"` and poison D23 counts.

Fold requirement: add unique constraint on `provenance_source_ref` /
`authority_row_id`, idempotent bridge behavior, and transaction semantics.

### Cluster J - Rollback Is Not Rechecked At Mutation Edge

Reviewer 3 major.

D16 checks `RollbackPlanEvidence` before artifact mint. But the mutation edge
does not require loading the plan and comparing current target hashes against
`expected_pre_mutation_hashes` immediately before the substrate write. Target
state can change after mint and before consume.

Fold requirement: execution wrappers must verify current pre-mutation hashes
against the rollback plan after consume and before pending trace/substrate
mutation.

### Cluster K - Rendered Authorization Protocol Is Too Open

Reviewer 4 major.

D17 says there are two rendered carriers. D21 accepts any object implementing
`S7RenderedAuthorizationStatement` and only runs subtype checks for
`RenderedRequestStatement` or `RenderedCredentialRequestStatement`. D24 tests
wrong credential carrier and missing fields, but not an unknown third
implementor.

Fold requirement: close the accepted rendered carrier set to exactly
`RenderedRequestStatement | RenderedCredentialRequestStatement`, or add a
reviewed subtype registry plus D24 unknown-subtype rejection.

### Cluster L - Bundle Draft Is Load-Bearing But Not Test-Bound

Reviewer 4 major; overlaps spec-implementor fresh-reader minor.

`S7VoiceConsultationBundleDraft` is the Stage-1 input before authority booleans
and reducer output. It is absent from the D24 no-hand-assemble list and the
acceptance carrier list.

Fold requirement: define its exact field subset and add it to D24/acceptance
as a load-bearing carrier that positive tests cannot hand-assemble.

### Cluster M - Credential And Model-Routing Path Ambiguities

Reviewer 2 high/medium.

Credential registration matrix rows conflate backup registration with first
primary bootstrap. The same begin/finish endpoints include primary bootstrap
paths using bootstrap intent/token and `consume_for_first_primary`.

Model-routing rows list `/etc/maez/model.env write/restart` as live guarded,
but the reviewer found the concrete Telegram rollback route mutates
`training/runs/current` by replacing a symlink and tells the operator to restart
`llama-server`. The affected refs and adapter semantics are not pinned.

Fold requirement:

- Split credential rows by begin/finish and backup/primary bootstrap, or add a
  reviewed exclusion for primary bootstrap.
- Make model-routing rows match committed surfaces and affected refs exactly,
  including Telegram rollback adapter semantics.

### Cluster N - Closed Vocabulary Drift

Reviewer 4 major/minor.

`D18` records `classifier_reason_code="reader_unavailable"`, while the closed
`CLASSIFIER_REASON_CODES` vocabulary must explicitly admit that token or D18
must use an existing legal token.

Fold requirement: add `reader_unavailable` to the closed vocabulary or rename
the D18 row to `semantic_reader_unavailable` consistently.

## Affirmations

All reviewers agreed that v9 is closer than v8:

- D16 has a real validator signature, result shape, and replay checklist.
- The immutable bundle / mutable use split avoids the mutable-hash trap.
- The rendered voice/credential carrier split is the right shape.
- D13/D19 separate current-attempt blocking from long-use D23 authority.
- `append_to_file` is no longer allowed to hide behind shell execution.
- The legacy refusal-history suppression is the right covenant move.
- D24 is unusually strong about no hand-assembled positive proof.

## Cross-Check With Fresh-Reader Gate v9

Fresh-reader gate v9 found four clusters:

1. Writer guard for `record_refusal_history(...)`.
2. Surface manifest completeness.
3. Orphan failure/provenance codes.
4. Explicit amended signatures.

Codex v9 converges on clusters 2, 3, and 4, and adds new implementation
clusters: durable `ContextManifest` store, action-edge store, surface-row
binding, semantic-reader input binding, nonce retry states, consume-time replay,
bridge idempotency, rollback current-state check, rendered subtype closure,
credential/primary-bootstrap split, and model-routing affected refs.

The combined direction remains REVISE. The architecture remains stable; v10 is
an inherited-seam and replay-carrier fold.

## Plain English

The Codex panel agrees with the fresh-reader gate that v9 is close, but not
ratifiable. The remaining problems are not about whether Maez gets a seat or
whether marker-only evidence should poison history. Those are settled. The
remaining problems are the last pieces of plumbing that make the spec buildable
without invention: where context manifests live, how manifest rows bind to work
items, how every consume failure gets a name, how every real mutation route has
a row or exclusion, and how replay checks survive retries, consume, and
mutation timing.

v10 should be narrow but real. It should close the writer guard, complete the
surface manifest, add the missing stores and signature shapes, bind semantic
reader inputs, make nonce retry states explicit, make bridge writes idempotent,
and recheck rollback state at the mutation edge.

*Read-only; semantic consolidation written by Codex on 2026-05-20 from four
independent Codex engineering reviewers. Reviewers were instructed not to read
`reviews/` and reported compliance. ASCII normalization was applied for
repository style.*
