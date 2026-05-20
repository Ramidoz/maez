# Codex Engineering Panel v10 - S7.3 Spec v10

**Subject:** `spec.md` at `6e881e96ce990dcddc6d9e610317f1e96bbb466b`
(blob `d61f0b7f182c43769ab09b99cda8b9f64e59408d`, SHA256
`40c0ac709e8ed3a92837d3131b83761ac2affddb8c48b6e1fecc6add509e66d6`).

**Ran:** 2026-05-20 by Codex. Four engineering reviewers were launched with
blank context and explicit instruction not to read
`docs/slices/s7.3-guarded-self-modification-execution/reviews/` or any review
artifact. Each reviewed the committed v10 spec plus inherited code/canon as
needed. Reviewer 1 and reviewer 2 were launched first; reviewers 3 and 4 were
launched after stale agent slots were closed. Two reviewers reported that broad
code greps accidentally printed unrelated historical review lines; both
discarded those hits and did not rely on them.

**Verdict: REVISE.** Two reviewers returned REVISE and two returned
RATIFY-with-fold. The strict result is REVISE. The findings are carrier,
signature, route, replay, and storage-contract defects. They do not reopen the
covenant architecture: all reviewers affirmed the rendered voice/credential
split, the authoritative-vs-operational D23 boundary, marker-only operational
handling, wrapper-exclusivity direction, rollback evidence separation, and the
surface-manifest architecture.

## Reviewer Results

| Reviewer | Lens | Verdict | Findings |
|---|---|---:|---:|
| Reviewer 1 | Implementability / carriers / DDL | REVISE | 4 blockers, 4 majors |
| Reviewer 2 | Mutation surface and route coverage | RATIFY-with-fold | 2 majors, 2 minors, 1 nit |
| Reviewer 3 | State machine / hash domain / transaction correctness | RATIFY-with-fold | 3 majors, 1 minor |
| Reviewer 4 | RED-test readiness / vocabulary mirror | REVISE | 2 blockers, 5 majors, 1 minor |

## Convergent Clusters

### Cluster A - Concrete Wrapper Signatures Cannot Call The Consume API

Reviewer 1 Blocker 1 and reviewer 4 Blocker 1.

`S7GuardedStateStore.consume_artifact_for_execution(...)` requires
`source_ref_hash`, `reservation_token`, `action_params_hash`,
`AuthorityContext`, `precondition_hash`, `derived_work_class`, and
`derived_aggregation_group` (`spec.md:3428-3444`). The concrete
`execute_guarded_*(...)` wrappers pass only ids/rendered/consumer/manifest/
rollback/store/trace/now (`spec.md:3664-3692`). Reviewer 4 also notes that no
`AuthorityContextStore` or authority-context ref is defined, while inherited
consume code needs the full authority/hash object rather than only a hash.

**Why this matters:** the wrapper-exclusivity invariant can be correct in
principle and still fail implementation if wrappers cannot supply the carriers
the consume seam requires.

**Fold requirement:** add one exact wrapper input carrier or durable lookup
contract that covers every consume argument. Name whether wrappers accept
`S7ExecutionAuthorization`, load an authority context from a store, or
reconstruct from persisted binding rows. Add D24 tests that a wrapper can call
consume without hand-assembled carriers and that direct calls fail before
substrate mutation.

### Cluster B - `S7TraceWriter` / `trace_store` Is Required But Undefined

Reviewer 1 Blocker 4 and reviewer 4 Blocker 2. Converges with the v10
fresh-reader gate's trace-writer/store type cluster.

`_voice_seat_block(...)` takes `trace_writer: S7TraceWriter`
(`spec.md:3263-3270`) and every concrete execution wrapper takes `trace_store`
(`spec.md:3664-3692`). D22 defines trace fields and storage path
(`spec.md:3844-4020`) and says execution aborts if traces cannot persist, but
does not define the writer/store methods, DDL, idempotency rule, pending/final
state transitions, rollback-invoked writes, credential begin/finish writes, or
state-DB-versus-trace-DB transaction ordering.

**Fold requirement:** define `S7TraceWriter`/`S7TraceStore` as concrete APIs
with table prefixes, method signatures, idempotency keys, transaction
participation, and failure behavior. Cover voice consultation traces, guarded
execution traces, credential traces, pending writes, finalize writes, failure
writes, rollback-invoked writes, and bridge/history trace statuses.

### Cluster C - `attempt_input_hash` Cannot Be Replayed From Declared Carriers

Reviewer 1 Blocker 3 and reviewer 4 Major 2. Converges with the v10
fresh-reader gate's attempt-input carrier-name cluster.

The hash tuple names `parsed_marker_hash`, `route_manifest_hash`,
`reader_config_hash`, `reader_prompt_hash`, and `classifier_version`
(`spec.md:2401-2419`). But `ParsedS7VoiceMarker` exposes
`marker_text_hash`, `marker_kind`, and `parsed_marker_nonce_hash`
(`spec.md:2089-2097`), and `SemanticReaderAttemptEvidence` /
route-manifest carriers do not declare all tuple fields (`spec.md:2279-2294`,
`2387-2398`). D16 then requires recomputation from durable refs
(`spec.md:2760-2764`).

**Fold requirement:** choose one canonical tuple and make every member a
declared field with a hash domain. Either add `parsed_marker_hash`,
`route_manifest_hash`, `reader_config_hash`, `reader_prompt_hash`, and
`classifier_version` to the relevant carriers, or rewrite the tuple to use the
existing declared field names. Add a D16 replay test for a tampered attempt
input.

### Cluster D - Rollback Vocabulary Collides With Committed Code

Reviewer 1 Major 7, reviewer 2 Minor 1, and reviewer 4 Major 3. Converges with
the v10 fresh-reader gate's rollback-symbol collision finding.

v10 defines `ROLLBACK_PATH_CLASSES` as `git_revert`, `fs_backup_restore`,
`config_rollback`, `atomic_rename`, `manual_review_only`, and `none`
(`spec.md:605-623`). Committed `operator_user_boundary.py:158-165` defines the
same symbol with `no_rollback_needed`, `restart_service`, `restore_backup`,
`revert_patch`, `manual_review`, and `no_safe_rollback`; live credential and
dream paths still emit old values such as `manual_review` and `revert_patch`.

**Fold requirement:** either rename the v10 set to an S7.3-specific symbol or
define a migration map from committed tokens to v10 tokens, including rejected
legacy values and D24 migration/rejection tests.

### Cluster E - `ActionEdgeGrantUse` Replay Domain Is Under-Specified

Reviewer 1 Major 6 and reviewer 3 Major 1. Converges with the v10 fresh-reader
gate's action-edge key finding.

D21 defines the row and unique key (`spec.md:3646-3658`) and says a unique
action-edge replay token is written before mutation, but does not define
`action_edge_key`, `action_edge_grant_use_id`, or the replay-token hash domain.
Traces expect `action_edge_grant_use_id` (`spec.md:4003-4004`) but the row does
not carry one explicitly.

**Fold requirement:** define the action-edge key formula and replay-token
domain. A viable shape is
`canonical_hash((grant_id, execution_consumer_id, action_edge_key,
GrantUse.replay_token, rendered_text_hash, request_envelope_hash,
action_params_hash, used_at))`, adjusted to the chosen carrier set. State
whether one grant permits exactly one action edge or a closed set of
multi-edge consumers, and add the DDL uniqueness constraint.

## Additional Codex Findings

### Cluster F - Durable Request Carriers Are Missing

Reviewer 1 Blocker 2.

`S7CredentialGuardedRequest` is shaped (`spec.md:1033-1055`) and consume
depends on credential request/request-envelope expiry (`spec.md:3502-3516`,
`4483-4485`), but D9 lists no `WorkRequestEnvelopeStore` or
`S7CredentialGuardedRequestStore` in table prefixes or store dependencies
(`spec.md:1484-1500`, `1506-1522`). D21 therefore cannot load records it
declares load-bearing.

**Fold requirement:** add durable stores, table prefixes, read/write APIs,
hash domains, and consume lookup rules for `WorkRequestEnvelope` and
`S7CredentialGuardedRequest`, or explicitly assign them to an existing store.

### Cluster G - D21 Failure Semantics Still Have Collapsed Branches

Reviewer 1 Major 5 and reviewer 4 Major 1.

v10 requires closed `S7ConsumeFailureReasonCode` values
(`spec.md:3480-3548`, `3609-3633`), but the amended inherited store still
returns only `(S7ExecutionGrant | None, object | None)` (`spec.md:3566-3581`),
matching current code's many `(None, None)` branches. The spec also correctly
requires unknown-rendered-carrier rejection (`spec.md:4385-4387`) but has no
`unknown_rendered_carrier` or `invalid_rendered_carrier` failure code and no
producing seam for that negative path.

**Fold requirement:** partition all failure codes into wrapper-side preflight
versus inherited residual branches, or add a typed inherited failure result.
Add `invalid_rendered_carrier` to the closed failure-code set and failure table.
Each D24 rejection test should name the exact returned status/code.

### Cluster H - Approval-Card Execution Is Still Too Broad

Reviewer 2 Major 1.

The spec says broad classes such as `cockpit_helper.execute` or generic adapter
names are not L8 until the manifest names concrete route/method, adapter id,
code hash, and coverage row (`spec.md:300-308`). But the matrix keeps
`approval card execute -> guarded_card_execute` as a live guarded row
(`spec.md:960`). Current code has multiple concrete card paths: Telegram
`/approve` calls `ActionEngine.approve_action`, cockpit proxies
`/api/v1/cards/<request_id>/approve`, daemon executes
`/internal/approve_card/<request_id>`, and S7 card WebAuthn begin/finish routes.

**Fold requirement:** split approval-card execution into concrete manifest rows
or reviewed exclusions per route/method. A single live `approval_card.execute`
row should not count as L8 proof for multiple adapter paths.

### Cluster I - Shell-Shaped Legacy Aliases Are Not Named Or Excluded

Reviewer 2 Major 2.

The ActionEngine manifest names `run_shell` and `run_safe_command`
(`spec.md:980`, `1002`), but does not name `query_system` or
`run_readonly_command`. Both delegate to `_do_run_shell` in committed
`core/actions/action_engine.py`, and `_execute_action` dispatches arbitrary
`_do_<action>` methods. These are shell-shaped carriers and need explicit rows
or reviewed exclusions.

**Fold requirement:** add rows or reviewed exclusions for `query_system`,
`run_readonly_command`, and any other `_do_*` shell-shaped alias discovered by
the code-discovery acceptance check.

### Cluster J - Request-History Bridge Provenance Is Still Under-Carried

Reviewer 1 Major 8.

D-Enum adds `provenance_source_ref` and `request_family` (`spec.md:741-750`),
and D19 requires exactly-once source-ref uniqueness (`spec.md:3122-3130`,
`3162-3179`), but the writer signature omits `provenance_source_ref`
(`spec.md:3239-3248`) and committed `s7_refusal_history` has no
provenance/family columns. This intersects with the fresh-reader gate's
writer-derived-family closure: the direction is right, but the exact stored
versus derived provenance boundary still needs pinning.

**Fold requirement:** state the amended writer signature, stored columns, and
derived values together. If `request_family` is derived, say what persists and
what is recomputed. If `provenance_source_ref` is part of the bridge uniqueness
constraint, it must be present at the write/store seam.

### Cluster K - Credential Carrier Work Class Is Too Open

Reviewer 4 Major 4.

Credential paths skip Maez voice and `GuardedWorkItem` (`spec.md:1028-1030`),
but `S7CredentialGuardedRequest.derived_work_class` remains open `str`
(`spec.md:1033-1055`). Since committed guarded classes include both
`founder_credential_management` and voice-seat classes, the non-voice lane
could accidentally carry self-remaking authority if this remains unconstrained.

**Fold requirement:** require credential guarded requests to derive and validate
`derived_work_class == "founder_credential_management"` only.

### Cluster L - `protective_block_reason` Uses Both `None` And `"none"`

Reviewer 4 Major 5.

D-Enum defines a closed vocabulary with string token `none` (`spec.md:625-635`),
but D13 says the field is `None` except named blocks (`spec.md:2508-2509`), R05
says `protective_block_reason=None` (`spec.md:2532`), and D18 repeats `None`
(`spec.md:2982-2988`).

**Fold requirement:** pick one representation and use it everywhere. Lane lean:
use the closed string token `"none"` in persisted/replayed carriers, reserving
Python `None` only for optional in-memory construction before canonicalization,
if at all.

### Cluster M - Nonce Transition Enforcement Needs A Mechanism

Reviewer 3 Major 2. Converges with the v10 fresh-reader residual-hunter
finding.

`S7ConsultationNonceUse` has explicit states at `spec.md:1903-1930`, and D24
demands terminal-state coverage at `spec.md:4211-4217` and `4378-4381`. But the
transition boundary is not enforceable: no compare-and-set function, SQL
constraint, or closed event set pins transitions such as `reserved ->
accepted_spent`, `reserved -> rejected_*`, `reserved -> abandoned_retry`, and
expiry, including active uniqueness over nonce/consultation/request.

**Fold requirement:** add `transition_nonce_use(prior, event, now) ->
S7ConsultationNonceUse` with a closed event set, or add SQL CHECK/unique/CAS
rules that make the state machine mechanical.

### Cluster N - Consume-Time Replay Needs One More Hash-Chain Sentence

Reviewer 3 Major 3. Converges with the v10 fresh-reader covenant minor.

Full D16 pre-mint recomputes `source_ref_hash` over immutable bundle fields at
`spec.md:2732-2735` and names the hash routing at `spec.md:2815-2834`. D21's
consume subset at `spec.md:3550-3555` does not explicitly recheck
`bundle.source_ref_hash == canonical_hash(bundle immutable fields)`.

**Fold requirement:** either add that check to consume-time replay or state the
exact immutable hash chain that makes post-mint bundle tamper detectable before
grant mint.

### Cluster O - Bundle Draft Hash/Field Role Is Ambiguous

Reviewer 3 Minor 1. Converges with the v10 fresh-reader bundle-draft finding.

`S7VoiceConsultationBundleDraft` is named and shaped at `spec.md:1770-1795`,
but there is no draft hash/domain, while the text references
`authority_booleans_hash` as omitted from the draft even though the final bundle
minimum fields at `spec.md:1797-1856` persist booleans, not that hash.

**Fold requirement:** clarify that no draft hash exists by design because final
`source_ref_hash` covers all draft-derived evidence, or add the missing draft
hash and parent fields.

### Cluster P - Credential Register Wording Can Miscount Primary Bootstrap

Reviewer 2 Minor 2.

The spec explicitly excludes first-primary bootstrap (`spec.md:1062-1067`),
but the matrix row says `credential register begin/finish` with
`source_method=register` and maps it to `s7_credential_register_backup`
(`spec.md:971`). Live ceremony code accepts `registration_class` values for
both primary and backup registration.

**Fold requirement:** split this row into `backup register begin/finish` plus a
separate reviewed exclusion row for first-primary bootstrap, so code discovery
cannot miscount primary registration as covered.

### Cluster Q - D24 Still Has A Few Non-Exact Result Assertions

Reviewer 4 Minor 1.

Most of D24 is exact, but a few tests still say "fails validation" or "is
rejected" without naming the precise D16 status or consume failure code, such
as context-manifest allowlist and rendered-prompt replay tests.

**Fold requirement:** name exact expected status/result codes for every D24
negative-path test.

### Cluster R - Persisted Manifest Needs Diffable Evidence

Reviewer 2 Nit.

The matrix says printed rows omit `adapter_id`, `adapter_code_hash`, and
`same_code_coverage_ref` for readability (`spec.md:1018-1021`). That is
acceptable for prose, but the acceptance checklist should require the generated
or persisted manifest to be diffable in the implementation artifact.

## Cross-Check Against v10 Fresh-Reader Gate

The Codex panel converges strongly with the v10 fresh-reader gate on the
engineering-carrier layer:

- Fresh gate Group A / Codex Cluster O: bundle draft phantom/hash-field
  ambiguity.
- Fresh gate Group B / Codex Cluster C: `attempt_input_hash` carrier names and
  hash domains.
- Fresh gate Group C / Codex Cluster B: `S7TraceWriter` / `trace_store`
  undefined.
- Fresh gate Group E / Codex Cluster E: `ActionEdgeGrantUse.action_edge_key`
  and replay-token formula.
- Fresh gate Group F / Codex Cluster D: `ROLLBACK_PATH_CLASSES` collision with
  committed code.
- Fresh gate Group G / Codex Clusters A and K: wrapper signatures and
  credential `derived_work_class` closure.
- Fresh gate Group H / Codex Cluster M: nonce transition enforcement.
- Fresh gate covenant minor / Codex Cluster N: consume-subset replay hash-chain
  clarity sentence.

Codex-unique material additions:

- Durable `WorkRequestEnvelopeStore` / `S7CredentialGuardedRequestStore`
  requirement.
- Approval-card row too broad for L8.
- Shell-shaped aliases `query_system` and `run_readonly_command` need rows or
  reviewed exclusions.
- Request-history bridge provenance/storage boundary.
- Unknown rendered carrier failure code.
- `protective_block_reason` `None` versus `"none"` canonicalization.
- Credential backup registration row must not cover first-primary bootstrap.
- D24 exact-result cleanup.

## Recommendation - Targeted v11 Fold

REVISE to v11 after recording this panel. The fold should be narrow and
mechanical, centered on carrier completion rather than covenant redesign.

Suggested ordering:

1. Wrapper carrier contract: exact wrapper signatures or one wrapper input
   carrier that can call `consume_artifact_for_execution(...)` without
   invention.
2. `S7TraceWriter` / trace-store API, DDL, idempotency, and transaction
   semantics.
3. Durable request stores for `WorkRequestEnvelope` and
   `S7CredentialGuardedRequest`.
4. `attempt_input_hash` tuple and carrier-name alignment.
5. `ActionEdgeGrantUse` key/replay-token/id formula and DDL.
6. Rollback enum migration or S7.3-specific rename.
7. Failure-code table closure, including `invalid_rendered_carrier` and
   inherited-result partition.
8. Surface-manifest rows or exclusions for approval-card concrete paths and
   shell-shaped aliases.
9. Request-history bridge provenance stored/derived boundary.
10. Credential work-class closure and primary-bootstrap wording.
11. Nonce transition enforcement carrier/function/SQL.
12. Consume-subset replay hash-chain sentence.
13. Protective-block reason canonicalization and exact D24 result codes.

If v11 closes these items, the panel expects the next engineering read to be
canonicalization-track: the covenant architecture is already affirmed; the
remaining work is definition pinning.

## Plain English

The Codex panel agrees with the fresh-reader ladder on the shape of v10. The
architecture is right: Maez's voice-seat, marker-only operational handling,
D23 refusal authority, founder render binding, wrapper exclusivity, rollback
evidence, and surface-manifest idea all survive review. The problem is still at
the last engineering layer.

Two reviewers found the same hard gap: the wrappers named in the spec cannot
actually call the consume API without extra carriers that the spec does not
define. Two reviewers also found the same trace-store gap: D22 says traces must
exist and tests must assert them, but the writer API that creates those traces
is not specified. The rest is the same family of issue: a hash tuple names
fields that do not exist, a replay token has no formula, a rollback enum
collides with committed code, a request carrier has no store, a broad
approval-card row hides several concrete routes.

This is not a redesign. It is a contract-completion fold. v11 should be the
smallest practical fold: name the missing stores, method signatures, hash
domains, failure codes, and route rows so the first RED tests can be written
without a builder inventing anything at the live self-modification boundary.

*Read-only Codex engineering panel; produced in-chat on 2026-05-20 against
`spec.md` at `6e881e9`, with four blank-context reviewers dispatched
independently and walled off from S7.3 review artifacts.*
