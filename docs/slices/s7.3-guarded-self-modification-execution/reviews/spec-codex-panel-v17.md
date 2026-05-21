# Codex Engineering Panel v17 - S7.3 Guarded Self-Modification Execution Spec

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`

**Spec commit:** `69cefa240a4b9bf48bdc58b1faed3be845b6eda1`

**Spec blob:** `16f2734e4c378423acc1f3e9cb70ac4c9f04512c`

**Spec SHA256:** `6dc7694577938e0c6a961684921c926483b814ad5ceddc708e287591f6ada992`

**Panel date:** 2026-05-20

## Verdict

**REVISE.**

Raw reviewer split:

| Reviewer | Lens | Verdict | B | M | m | n |
|---|---|---:|---:|---:|---:|---:|
| Reviewer 1 | Persistence round-trip and store/DDL implementability | REVISE | 2 | 0 | 0 | 0 |
| Reviewer 2 | Credential path and authorization boundary | REVISE | 0 | 2 | 1 | 0 |
| Reviewer 3 | Route matrix, consumer-id mintability, and callback ownership | RATIFY | 0 | 0 | 0 | 0 |
| Reviewer 4 | Closed vocabulary, trace/status producers, and D24 testability | RATIFY-with-fold | 0 | 1 | 0 | 0 |

Deduped panel shape:

- **Blockers:** 2
- **Majors:** 3
- **Minors:** 1
- **Nits:** 0

Plain English: v17 did the high-leverage move correctly. The uniform
persistence contract is real, credential invocation is now a hash/ref carrier,
route mintability is clean, ActionEdge replay is implementable, and callback
ownership is wrapper-only. The remaining failures are narrower than v16, but
two are still build-blocking: the same ref-based reshape that fixed credential
invocation has not yet been applied to the voice/execution invocation carrier,
and the history-bridge trace payload validator lacks a declared decoded schema.
Those are persistence-contract completion gaps, not covenant architecture.

## Blockers

### B1 - `S7GuardedExecutionInvocationStore.get(...)` cannot round-trip its declared carrier

v17 makes `S7GuardedCredentialInvocation` a ref-based carrier, but
`S7GuardedExecutionInvocation` still declares full object fields while its DDL
stores hashes/refs.

Evidence:

- `spec.md:1951-1971` declares `S7GuardedExecutionInvocation` with full
  `rendered: S7RenderedAuthorizationStatement`,
  `authority_context: AuthorityContext`, and raw
  `reservation_token: ReservationToken`.
- `spec.md:2120-2121` says
  `S7GuardedExecutionInvocationStore.get(request_id, artifact_id, *, conn)`
  returns `S7GuardedExecutionInvocation | None`.
- `spec.md:2310-2316` says the store reconstructs the invocation and verifies
  `canonical_hash(reconstructed S7GuardedExecutionInvocation)`.
- `spec.md:2640-2663` persists only `rendered_statement_hash`,
  `authority_context_hash`, and `reservation_token_hash` in
  `s7_guarded_execution_invocations`.
- `spec.md:2701-2703` says the raw reservation token is runtime-only and never
  persists as plaintext.

Why this blocks: a builder cannot implement `get(...)` returning the declared
carrier without inventing either a voice/execution bundle loader and token
rules, or changing the carrier to match persisted columns. This is the same
class v17 correctly fixed for credential invocation, but still present for the
voice/execution invocation carrier.

Fold shape: apply the v17 uniform contract to this carrier too. Pick one:

1. make `S7GuardedExecutionInvocation` a ref-based carrier whose dataclass
   fields match the persisted columns, then define
   `load_guarded_execution_invocation_bundle(...)` with all required stores,
   `conn`, rendered/authority loading, and reservation-token verification; or
2. persist every declared full-object field in an all-column/blob form,
   including a defined raw-token handling rule.

Lane lean: option 1. It mirrors the successful credential Option A shape and
keeps full-object reconstruction behind a named bundle loader.

### B2 - `validate_history_bridge_trace_payload(...)` has no decoded payload schema

v17 requires every typed trace payload validator to check every D22 minimum
field for its trace kind. The spec names the history-bridge payload table and
validator, but it never declares the decoded history-bridge trace payload
minimum shape.

Evidence:

- `spec.md:1878-1891` says typed trace payloads either persist every D22
  minimum field or store a blob/ref plus a strict per-kind validator.
- `spec.md:2163-2164` names `S7TraceWriter.write_history_bridge_trace(...)`.
- `spec.md:2829-2838` defines `s7_history_bridge_trace_payloads`.
- `spec.md:2855-2859` names
  `validate_history_bridge_trace_payload(payload) -> None`.
- `spec.md:5519-5569` defines voice, execution, and credential trace minimum
  fields, but no history-bridge trace payload minimum shape.

Why this blocks: the validator cannot know what the decoded blob must contain.
An implementor must invent whether the decoded payload is just the SQL columns,
a fuller D22 trace object, or some bridge-specific evidence record.

Fold shape: add a `S7HistoryBridgeTracePayload` or
`HistoryBridgeTracePayload` minimum field declaration beside the other D22
trace shapes. The schema must at least cover the SQL columns
(`trace_id`, `provenance_source_kind`, `provenance_source_ref`,
`history_bridge_status`, `history_record_id`, `d23_state`) and any additional
D22 evidence fields required for `trace_hash` recomputation.

## Majors

### M1 - `register_begin` / `register_finish` authorization boundary is ambiguous

The spec now correctly treats backup credential registration as a two-step
mutation edge, but it leaves one implementor choice unresolved: whether
`register_finish` consumes a second artifact, or whether finish is authorized
only by the persisted grant/challenge binding created at begin.

Evidence:

- `spec.md:2385-2387` says `register_begin` requires
  `credential_id_hash is None`, while `register_finish`, `backup_card`, and
  `disable` require non-null `credential_id_hash`.
- `spec.md:5382-5403` says `register_begin` may consume the S7 authorization
  if it persists a finish-time grant/challenge binding, and `register_finish`
  is the actual credential-write edge.
- `spec.md:6173-6177` says credential begin, finish, backup-card, and disable
  consume through `S7GuardedCredentialInvocation` and
  `unpack_guarded_credential_invocation`.

Why this matters: the current wording supports two incompatible
implementations: a second finish-time consume with a non-null credential-id
carrier, or a single begin-time consume plus a finish-time binding-authorized
write. Those have different replay, expiry, and trace obligations.

Fold shape: choose one explicitly. Lane lean: `register_begin` consumes the S7
artifact and creates the finish-time `S7CredentialRegistrationGrantBinding`;
`register_finish` does not perform a second artifact consume, but verifies the
binding, challenge, grant, expiry, and credential id before the actual
credential write. If the spec instead wants a second consume, it must define
the second artifact and invocation lifecycle.

### M2 - `unpack_guarded_credential_invocation(...)` does not explicitly reload the persisted invocation carrier

The helper accepts `credential_invocation_store`, but the described algorithm
starts by loading the full bundle and verifying request/rendered/authority
hashes. It does not explicitly say it reloads the persisted invocation and
compares it to the supplied invocation before producing inherited consume
inputs.

Evidence:

- `spec.md:2047-2064` defines `unpack_guarded_credential_invocation(...)` with
  `credential_invocation_store`.
- `spec.md:2067-2077` says the helper calls the bundle loader and verifies
  bundle fields before forwarding inherited consume inputs.
- `spec.md:472-476` forbids hand-assembled carriers from serving as positive
  proof.
- `spec.md:2356-2359` again describes bundle loading and hash verification,
  but not the persisted-invocation equality check.

Why this matters: without an explicit reload-and-compare rule, a test could
pass a hand-assembled invocation whose hashes point at real stored objects but
whose scalar carrier fields were never persisted as that invocation.

Fold shape: require:

```text
stored_invocation =
    credential_invocation_store.get(invocation.request_id, invocation.artifact_id, conn=conn)
stored_invocation == invocation
canonical_hash(stored_invocation) == guarded_credential_invocation_hash
```

before bundle loading or inherited delegation. Missing or mismatched stored
invocation fails closed before consume.

### M3 - `MANUAL_REVIEW_STATUSES="none"` has semantics but no exact producer/test closure

`MANUAL_REVIEW_STATUSES` includes `none`, `pending`, `completed`, and `failed`.
The manual-review writer methods produce `pending`, `completed`, and `failed`
from `ManualReviewEvidence`, while D24 says those methods produce every
manual-review status. That incorrectly implies `"none"` is produced by a
manual-review evidence write.

Evidence:

- `spec.md:877` declares `MANUAL_REVIEW_STATUSES`.
- `spec.md:2224-2238` maps the three manual-review writer methods to
  `pending`, `completed`, and `failed`.
- `spec.md:6255-6259` says the manual-review producer test produces every
  `MANUAL_REVIEW_STATUSES` value from complete `ManualReviewEvidence` inputs.

Why this matters: `"none"` is a canonical trace default for traces with no
manual review, not a manual-review evidence row. The current test wording
leaves the producer of `"none"` under-specified.

Fold shape: split the producer closure explicitly. Normal trace writers store
`manual_review_status="none"` for traces with no review; the three
manual-review methods produce only `pending`, `completed`, and `failed`. Add a
D24 row that asserts both halves.

## Minor

### m1 - `credential_rotate` rejection is assigned to a carrier without the named fields

`credential_rotate` is correctly non-live, but the rejection wording says
`S7CredentialGuardedRequest.__post_init__` rejects it with
`route_status="reviewedly_excluded"` and
`exclusion_reason_code="credential_rotate_future_slice"`. That request carrier
does not declare `route_status` or `exclusion_reason_code`.

Evidence:

- `spec.md:1317-1323` begins the `S7CredentialGuardedRequest` carrier without
  route-status fields.
- `spec.md:1398-1402` assigns the reviewed-exclusion fields to
  `S7CredentialGuardedRequest.__post_init__`.

Fold shape: move the reviewed exclusion to manifest/normalizer output, or
define a structured rejection result before request materialization. The
request constructor should reject unsupported `credential_action` without
pretending to emit fields it does not carry.

## Affirmations

- The uniform persistence contract is the right shape and is genuinely
  universal: `get(...)` stores must be all-column or ref-based with named
  loaders, typed trace payloads must be complete or blob/ref-validated, and
  D24 has a universal round-trip test.
- Credential invocation is much stronger than v16. The carrier is hash/ref
  shaped, the DDL matches it, derived work class and aggregation group persist
  on the row, and the bundle loader takes explicit stores plus `conn`.
- Route mintability is clean. Live rows carry mintable ids; fail-closed and
  reviewedly-excluded rows carry `execution_consumer_id=None` plus closed
  exclusion reasons. `query_system` and `run_readonly_command` have no reserved
  future consumer id in S7.3 v1.
- `append_to_file` is pinned to `ActionEngine._do_append_to_file`; shell-shaped
  aliases no longer provide L8 evidence.
- D21 no longer maintains a hand-copied ActionEngine mirror; the persisted
  `S7SurfaceManifest` is the authority.
- Callback ownership is wrapper-only: inherited consume has no callback
  parameter, and deprecated `consume_verified(...)` loads an existing
  invocation instead of synthesizing one.
- ActionEdge replay is byte-implementable: target refs and hashes are
  persisted in a child table, and replay-token/key domains are stated.
- D23 and trace-status closure remain strong: `d23_state_for(...)` covers the
  D23 states, and every `TRACE_STATUSES` value has a named writer transition.
- Covenant posture appears unaffected. Same-box, marker/D23, operational
  reliability, manual-review, and credential-management posture are not
  reopened by these findings.

## v18 Fold Recommendation

v18 should stay narrowly on the persistence-contract completion layer:

1. Apply the ref-based carrier pattern to `S7GuardedExecutionInvocation` or
   provide a complete all-column/blob persistence rule.
2. Declare the history-bridge trace payload minimum schema used by
   `validate_history_bridge_trace_payload(...)`.
3. Pin the backup credential registration lifecycle: begin consumes once and
   finish verifies the binding, or finish consumes a second explicitly-defined
   artifact.
4. Require `unpack_guarded_credential_invocation(...)` to reload and compare
   the persisted invocation carrier before inherited delegation.
5. Split `manual_review_status="none"` producer/test closure from the
   manual-review evidence writer methods.
6. Move `credential_rotate` reviewed-exclusion fields to the manifest or
   normalizer layer, or name a structured rejection result before request
   materialization.

No covenant rule moves. No architecture reopen. The fold closes the remaining
places where the uniform persistence contract was true in principle but not
yet applied to every declared carrier and typed payload.
