# S7.3 Spec v15 Codex Engineering Panel

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`
at commit `cd3a1b38081dddb7c592ca2235015e08cd88f55b`

**Blob:** `df6f278e26499760a8585ab2f1730e558af64990`

**SHA256:** `368b8e749075987ee394af032acc2718425c0d9a008fb9092ee37ba8424f0cf6`

**Panel discipline:** four blank-context Codex engineering reviewers, walled off
from `docs/slices/s7.3-guarded-self-modification-execution/reviews/`, reading
the committed v15 spec and live code only where needed for implementability,
persistence, or route-name verification.

## Verdict

**REVISE.**

The v15 fold closed the high-level v14 direction: durable cutoff marker exists,
credential id nullability is phase-bound, credential rotation is future-only,
manual-review statuses have producers, approval/deferred routes are named, and
the covenant posture remains intact. The remaining gaps are the final
engineering-contract layer: DDL/store payload completeness and route-matrix
mintability consistency.

| Reviewer | Lens | Verdict | B / M / m / n |
|---|---|---|---|
| Reviewer 1 | RED-first implementability | REVISE | 1 / 1 / 0 / 0 |
| Reviewer 2 | Persistence / DDL / replay | REVISE | 0 / 5 / 1 / 1 |
| Reviewer 3 | Surface manifest / routes | REVISE | 1 / 2 / 0 / 0 |
| Reviewer 4 | Security / authority boundary | RATIFY-with-fold | 0 / 0 / 2 / 0 |

**Raw counts:** 2 blockers, 8 majors, 3 minors, 1 nit.

**Deduped counts:** 2 blockers, 6 majors, 3 minors, 1 nit.

## Blockers

### B1. Credential invocation store still cannot round-trip the declared carrier

`S7GuardedCredentialInvocation` declares full-object fields including
`credential_request`, `rendered: RenderedCredentialRequestStatement`,
`authority_context: AuthorityContext`, `derived_work_class`, and
`derived_aggregation_group`. The `s7_guarded_credential_invocations` DDL stores
hashes for rendered/request/authority context and omits
`derived_work_class`/`derived_aggregation_group`. The prose says the store
reloads the credential request and rendered statement by hash-bound refs, but
the durable store API list has no rendered-statement store/ref API.

This blocks RED-first implementation because the acceptance test demands
`put` then `get` round-trip of every dataclass field, but the spec does not
persist or reconstruct enough bytes to return the declared object without
invention.

Fix shape: pick one explicit shape.

- Option A: make `S7GuardedCredentialInvocation` a hash/ref carrier whose
  dataclass fields match the persisted columns.
- Option B: add durable rendered-authorization and authority-context refs or
  stores, plus DDL/ref fields sufficient to reconstruct the full declared
  dataclass.

Whichever option wins, state whether `derived_work_class` and
`derived_aggregation_group` are persisted on invocation rows or always reloaded
from `S7CredentialGuardedRequest`, and make the canonical hash domain match.

### B2. Fail-closed ActionEngine rows still carry mintable-looking consumer IDs

The manifest prose says `route_status in {fail_closed_until_review,
reviewedly_excluded}` with `execution_consumer_id=None` is non-mintable. But
the printed matrix gives non-null consumer IDs to many
`fail_closed_until_review` ActionEngine rows, including `run_shell`,
`execute_script`, `git_push`, `install_package`, `restart_service`,
`query_system`, and `run_readonly_command`. Those IDs also appear in
`S7_EXECUTION_CONSUMER_IDS` and `S7_ACTION_ENGINE_CONSUMER_IDS`, while
`NON_MINTABLE_EXECUTION_CONSUMER_IDS` contains only
`action_engine_final_mutate`.

This leaves an implementation path where a fail-closed row has a closed,
derivable, mintable-looking consumer id.

Fix shape: make the manifest invariant byte-simple:

```text
route_status == "live_guarded" requires a mintable execution_consumer_id.
route_status in {"fail_closed_until_review", "reviewedly_excluded"} requires
execution_consumer_id=None plus a closed exclusion_reason_code.
```

Then either move reserved future IDs out of `S7_EXECUTION_CONSUMER_IDS`, or add
all reserved future IDs to `NON_MINTABLE_EXECUTION_CONSUMER_IDS` and state D21
rejects them before mint. Add a table test proving no fail-closed row has a
non-null consumer id.

## Majors

### M1. Request-history cutoff marker exists, but row migration is incomplete

v15 adds `S7RequestHistoryMigrationMarker` and new record fields, but does not
define the actual request-history table migration / ALTER contract. The marker
table exists, but the spec does not say how existing or new
`S7RequestHistoryRecord` rows gain durable columns, nor that
`s7_3_cutoff_marker_id` must resolve to the durable marker during reader
validation.

Fix shape: add explicit request-history row migration columns, writer
derivation rules, post-cutoff null rejection, and reader validation that
`s7_3_cutoff_marker_id` resolves to `S7RequestHistoryMigrationMarker`.

### M2. `integration.review_plan` has two source-method names

The derivation table maps:

```text
action_engine.integration.review_plan + integration_review_plan
```

but the exact matrix uses source method `review_plan` for the same route. Live
code dispatches the dotted action through `_do_integration_review_plan`. Since
derivation is keyed by `(source_surface, source_method)`, the spec leaves the
manifest tuple ambiguous.

Fix shape: pick one canonical `source_method` token and use it everywhere:
derivation table, matrix, manifest fixture, D21 authority tests, and code
discovery expected row. Panel lean: use `integration_review_plan`.

### M3. `append_to_file` route is still ambiguous against live shell delegation

The matrix marks `ActionEngine append_to_file` live-guarded with
`action_engine_append_to_file`, and the spec forbids shell-shaped delegation for
append. Live code still has public `append_to_file(...)` delegating to
`run_shell`, while the direct writer is `_do_append_to_file(...)`.

Fix shape: either mark public `action_engine.append_to_file` fail-closed until
rewritten to direct-write, or pin the manifest adapter symbol to
`ActionEngine._do_append_to_file` and require wrapper exclusivity proving the
public shell-delegating method cannot satisfy S7.3. The acceptance test should
assert the manifest adapter symbol is not `ActionEngine.append_to_file` while
that public method delegates to `run_shell`.

### M4. Trace DDL cannot fulfill the trace carrier contracts

D22 requires replayable voice, execution, credential, and bridge trace payload
fields. The DDL only creates a generic `s7_traces` header table with
`trace_hash`; there is no payload table or typed column set to reload and
verify the claimed minimum fields.

Fix shape: add per-kind payload tables keyed by `trace_id`, or add a versioned
trace-payload table with canonical JSON plus strict schema validators and
idempotency constraints per trace kind.

### M5. ActionEdge replay domain has a target-ref type mismatch

`ActionEdgeGrantUse` declares `target_refs_before_mutation:
tuple[str, ...]`, while the replay domain is an ordered tuple of
`(target_ref, target_ref_hash)` pairs. The child DDL stores both ref and hash,
so the carrier type is the weak link.

Fix shape: rename or add:

```text
target_ref_hashes_before_mutation: tuple[tuple[str, str], ...]
```

Derive `target_ref_hashes_before_mutation_hash` from durable child rows and
reject any action-edge carrier that only holds raw refs.

### M6. WorkRequestEnvelope store DDL cannot round-trip the inherited carrier

The spec says request-envelope persistence covers load-bearing request,
render, action, and authority fields, but the `s7_work_request_envelopes` DDL
omits inherited fields such as claimed work class, requesting subsystem,
affected refs, predicted effect class, and free text ref hash.

Fix shape: either persist every envelope field in structured columns, or
persist a canonical envelope blob/ref plus indexed load-bearing columns and
verify `request_envelope_hash` on read.

## Minors

### m1. Credential compatibility summary wording is inverted

Two summary passages say legacy `S7ExecutionAuthorization` is
"compatibility-only for credential paths." The normative D21 text correctly
says the opposite: inherited `S7ExecutionAuthorization` is only for pre-v14
voice-seat compatibility and cannot authorize credential mutation.

Fix shape: change both summaries to:

```text
legacy S7ExecutionAuthorization is compatibility-only for inherited voice-seat
paths and explicitly non-mintable for credential paths.
```

### m2. Deprecated `consume_verified(...)` equality should include both binding IDs

The equality pin names `binding.expected_execution_consumer_id` but not
`binding.execution_consumer_id`.

Fix shape:

```text
execution_authorization.execution_consumer_id
  == expected_execution_consumer_id
  == binding.execution_consumer_id
  == binding.expected_execution_consumer_id
```

Also state `consume_verified(...)` must load or reconstruct the full guarded
invocation through `S7GuardedStateStore` durable stores before delegation, or
fail closed.

### m3. Manual-review evidence producer boundary is porous

The store API accepts arbitrary `ManualReviewEvidence` via `put(evidence)`,
while the status contract says statuses are produced by trace-writer
transitions.

Fix shape: make raw `put` private/internal, expose `put_pending`,
`complete`, and `fail` only through `S7TraceWriter`, and bind evidence rows to
legal trace transitions.

## Nit

### n1. Prose sits inside the illustrative SQL fence

The sentence explaining `reservation_token_hash` sits inside the open SQL block
between `CREATE TABLE` statements.

Fix shape: close the SQL fence before the prose, or make the sentence a SQL
comment.

## Affirmations

- Durable request-history cutoff marker exists and is the right carrier shape;
  the remaining issue is row migration/reader validation detail.
- Credential id nullability is correctly phase-bound:
  register-begin uses `credential_id_hash=None`; finish, backup-card, and
  disable require non-null.
- Credential rotation is future-only and rejected/non-mintable.
- Approval-card and deferred-action routes are concretely named or reviewed
  fail-closed.
- Manual-review statuses have producer intent and D24 coverage; the remaining
  issue is store API exposure.
- Same-box and marker/D23 covenant posture remains intact.
- Manual review and operational reliability evidence cannot become D23 refusal
  or covenant-escalation evidence.

## Recommendation

Fold narrowly again. The v16 surface is now:

1. credential invocation/rendered/authority-context store round-trip;
2. fail-closed route rows and non-mintable consumer ids;
3. request-history row migration columns and cutoff marker validation;
4. `integration_review_plan` source-method normalization;
5. `append_to_file` direct-writer adapter binding;
6. typed trace payload persistence;
7. ActionEdge target-ref hash tuple carrier;
8. WorkRequestEnvelope persistence completeness;
9. three minor wording/API hardening items and the SQL fence nit.

Plain English: v15 moved the right way, but Codex still found the last
"database carries enough bytes" layer. The most important remaining lesson is
simple: if the spec says a store can rebuild an object, the table must either
store that object or name the exact durable refs used to rebuild it. v16 should
be a persistence-and-route-cleanup fold, not a covenant or architecture round.
