# Codex Engineering Panel v18 - S7.3 Guarded Self-Modification Execution Spec

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`

**Spec commit:** `4e058132893a7cde8ded217c809e2f7da2fac39d`

**Spec blob:** `27999e034ff87c0b698e9c11809cb5a660ad6b41`

**Spec SHA256:** `2e0de2474fc856a56d07854a820ca73e5f54eeae968bf112f2d43e1544b7f38e`

**Panel date:** 2026-05-20

## Verdict

**REVISE.**

Raw reviewer split:

| Reviewer | Lens | Verdict | B | M | m | n |
|---|---|---:|---:|---:|---:|---:|
| Reviewer 1 | Persistence round-trip and store/DDL implementability | REVISE | 2 | 1 | 1 | 0 |
| Reviewer 2 | Credential path and authorization boundary | REVISE | 1 | 2 | 0 | 0 |
| Reviewer 3 | Route matrix, D21 consume path, and callback ownership | RATIFY | 0 | 0 | 0 | 0 |
| Reviewer 4 | Closed vocabulary, trace/status producers, and D24 testability | RATIFY | 0 | 0 | 0 | 0 |

Deduped panel shape:

- **Blockers:** 3
- **Majors:** 3
- **Minors:** 1
- **Nits:** 0

Plain English: v18 closed the six items it was asked to close at the visible
carrier level. The route and closed-vocabulary lanes now ratify. The remaining
findings are the next layer down: hash-domain self-reference, validator input
scope, credential action vocabulary normalization, and backup-registration
challenge/binding persistence. Covenant posture still appears intact. This is
not a design reopen; it is the byte-level completion of the v18 mechanics.

## Blockers

### B1 - `S7GuardedExecutionInvocation` is self-hashing

The v18 ref-based execution invocation includes
`guarded_execution_invocation_hash` as a field, then defines
`guarded_execution_invocation_hash = canonical_hash(S7GuardedExecutionInvocation)`
and requires the store to verify the reconstructed carrier against that hash.
No exclusion rule states that the hash field is omitted from its own hash
domain.

Evidence:

- `spec.md:1969-1991` includes `guarded_execution_invocation_hash` in
  `S7GuardedExecutionInvocation`.
- `spec.md:2359` defines
  `guarded_execution_invocation_hash = canonical_hash(S7GuardedExecutionInvocation)`.
- `spec.md:2403-2406` requires
  `canonical_hash(reconstructed S7GuardedExecutionInvocation) ==
  guarded_execution_invocation_hash`.

Why this blocks: a builder cannot deterministically compute a carrier hash
that includes itself. Implementation must either invent an exclusion rule or
move the hash outside the dataclass.

Fold shape: state that `guarded_execution_invocation_hash` is excluded from
the canonical hash domain, or remove it from the dataclass and treat it as the
row hash column. The same rule should be checked for
`guarded_credential_invocation_hash` so both ref-based invocation carriers use
the same pattern.

### B2 - History-bridge payload validation lacks inputs for `d23_state_for(...)`

v18 gives `S7HistoryBridgeTracePayload` a decoded shape, but
`validate_history_bridge_trace_payload(payload)` must verify
`d23_state == d23_state_for(...)`. The payload does not carry enough inputs to
recompute `d23_state_for(...)`, and the validator signature has no store or
loader dependencies.

Evidence:

- `spec.md:4693-4712` defines `d23_state_for(...)` over reducer output,
  bridge status, and history outcome.
- `spec.md:5795-5812` defines `S7HistoryBridgeTracePayload`.
- `spec.md:5814-5820` requires the validator to verify `d23_state` equals
  `d23_state_for(...)`.

Why this blocks: the validator cannot recompute the state from the payload it
receives. A builder must invent either more payload fields or a loader seam for
authority/history rows.

Fold shape: pick one exact validation shape:

1. add the required `d23_state_for(...)` inputs to
   `S7HistoryBridgeTracePayload`; or
2. change the validator signature to accept named authority/history stores and
   `conn`, then load the required inputs before recomputing.

Lane lean: add the minimal inputs to the decoded payload if they are already
part of the bridge trace's evidence domain; otherwise name
`load_history_bridge_trace_payload_context(...)` with explicit stores and
`conn`.

### B3 - Credential action vocabulary rejects live carrier values

The live credential carriers and rendered credential statement use
`credential_action: "register_backup" | "disable"`, while
`CREDENTIAL_PROPOSED_CHANGE_CLASSES` uses
`credential_register_backup` / `credential_disable`. v18 then says
`S7CredentialGuardedRequest.__post_init__` rejects credential actions outside
`CREDENTIAL_PROPOSED_CHANGE_CLASSES`. That rejects the live carrier values.
The same area still has a stale `credential_rotate` exclusion producer in the
closed-set prose.

Evidence:

- `spec.md:958-963` declares `CREDENTIAL_PROPOSED_CHANGE_CLASSES` with
  `credential_register_backup`, `credential_disable`, and
  `credential_rotate`.
- `spec.md:1331-1347` uses `credential_action: "register_backup" | "disable"`
  on `S7CredentialGuardedRequest`.
- `spec.md:1414-1419` moves `credential_rotate` to normalization but also
  says `__post_init__` rejects actions outside
  `CREDENTIAL_PROPOSED_CHANGE_CLASSES`.
- `spec.md:4301-4318` uses `credential_action` in the rendered credential
  statement.

Why this blocks: a cold implementor must invent whether the canonical action
tokens are the short route actions (`register_backup`, `disable`) or the
proposed-change-class tokens (`credential_register_backup`,
`credential_disable`). The constructor rule currently rejects the carrier
tokens the spec itself uses.

Fold shape: separate the two namespaces or collapse them deliberately. Lane
lean: keep `CREDENTIAL_PROPOSED_CHANGE_CLASSES` for proposed-change classes,
add a closed `CREDENTIAL_ACTIONS = {"register_backup", "disable"}`, and make
`S7CredentialGuardedRequest.__post_init__` validate `credential_action` against
`CREDENTIAL_ACTIONS`. Define a bridge function from proposed change class to
credential action. Keep `credential_rotate` reviewedly excluded at
normalization before request materialization.

## Majors

### M1 - Reservation-token persistence is contradictory

The artifact binding carrier and DDL still appear to persist raw
`reservation_token`, while the v18 execution invocation uses
`reservation_token_hash` and the schema note says raw reservation tokens are
runtime-only and never persist as plaintext.

Evidence:

- `spec.md:2615-2623` includes reservation-token fields on artifact binding.
- `spec.md:2655` persists the artifact binding fields.
- `spec.md:2808-2810` says `reservation_token_hash` is persisted for replay and
  raw `reservation_token` never persists as plaintext.

Why this matters: D21 consume replay and `S7VoiceBundleUse` validation need a
single storage rule. Raw-token persistence versus hash-only persistence changes
DDL, replay, and threat posture.

Fold shape: make the rule singular. Lane lean: persist only
`reservation_token_hash`; raw reservation token is runtime-only wrapper input.
Any artifact-binding carrier text and DDL must use `reservation_token_hash`,
and consume compares `canonical_hash(reservation_token)` to the stored hash.

### M2 - Backup registration challenge lifecycle is ambiguous

Credential artifact mint loads an existing WebAuthn challenge by
`challenge_id` / `challenge_hash`, and the rendered credential statement signs
that challenge hash/expiry. Later, `register_begin` says it creates the
registration challenge in the same transaction as artifact consume.

Evidence:

- `spec.md:3016` says credential artifact mint loads an existing challenge by
  `challenge_id` / `challenge_hash`.
- `spec.md:4318` includes credential challenge hash/expiry in rendered
  credential statement lines.
- `spec.md:5487-5491` says `register_begin` creates the registration challenge
  in the same transaction as artifact consume.
- `spec.md:5522-5524` says the wrapper-owned callback inserts the binding in
  the same transaction as artifact consume, challenge creation, and grant-use
  persistence.

Why this matters: if these are the same challenge, the challenge cannot both
exist before artifact mint and be created at begin consume. If they are
different challenges, the spec needs separate names and binding rules.

Fold shape: name the two challenge phases exactly. Lane lean:
`credential_authorization_challenge` exists before founder signing and is the
challenge in rendered/artifact binding; `registration_ceremony_challenge` is
created at begin and bound to the consumed grant. The binding must name both
hashes and their equality or non-equality rules.

### M3 - Finish-time replay/result binding lacks durable state

v18 says `register_finish` verifies single-use replay state and the new
`credential_id_hash` before writing the credential, but the durable
`S7CredentialRegistrationGrantBinding` shape does not name enough state to
enforce that.

Evidence:

- `spec.md:5495-5506` defines
  `S7CredentialRegistrationGrantBinding` with challenge/grant/artifact/rendered
  ids, expiry, and `consumed_at`.
- `spec.md:5513-5518` says finish verifies challenge, grant, artifact,
  rendered text, request envelope, expiry, single-use replay state, and
  non-null credential id.
- `spec.md:6467-6473` D24 asks for replay rejection and WebAuthn result
  binding.

Why this matters: no store API or schema fields name finish state such as
`finish_used_at`, result hash, credential id hash, or result challenge hash.
The test cannot go green without inventing persistence.

Fold shape: define `S7CredentialRegistrationGrantBindingStore` and extend the
binding row with the finish-time state needed for replay and result binding:
at minimum `finish_used_at`, `credential_id_hash`, `registration_result_hash`,
and the relevant challenge/result hash equality rule. If the binding is meant
to stay immutable, add a separate `S7CredentialRegistrationFinishUse` row with
a unique constraint on `credential_registration_grant_binding_id`.

## Minor

### m1 - Execution invocation source/ref nullability is inconsistent

`S7GuardedExecutionInvocation` declares `source_ref_hash: str` and
`reservation_token_hash: str`, but illustrative DDL makes `source_ref_hash`
and `reservation_token_hash` nullable.

Evidence:

- `spec.md:1981-1982` declares non-null string fields.
- `spec.md:2762-2763` permits SQL NULL for these columns.

Fold shape: either make the dataclass fields nullable for compatibility
branches, or make DDL `NOT NULL`. Lane lean: voice-seat positive paths require
non-null values; compatibility/no-bundle paths should not use this carrier
unless explicitly named.

## Affirmations

- v18 correctly applies the ref-based carrier direction to
  `S7GuardedExecutionInvocation` and gives it a named bundle loader with
  explicit store dependencies plus `conn`.
- Route and mintability surface ratifies: live rows require mintable ids;
  fail-closed and reviewedly-excluded rows require `None`; reserved future ids
  are rejected before mint/consume.
- Approval-card, deferred-action, ActionEngine, `append_to_file`,
  `query_system`, and `run_readonly_command` route posture remains closed.
- `consume_verified(...)` remains compatibility-only and loads an existing
  persisted invocation rather than synthesizing one from
  `S7ExecutionAuthorization`.
- Callback ownership remains wrapper-only; inherited consume has no callback
  parameter.
- `MANUAL_REVIEW_STATUSES` closure is now correct: `"none"` is a trace default,
  not manual-review evidence, and D24 tests the split.
- D23 states, trace statuses, consume failure reasons, and v18 D24 coverage are
  testable without invention at the closed-vocabulary layer.
- Covenant posture appears unaffected. The findings above are byte-level
  carrier, vocabulary, and lifecycle-persistence gaps.

## v19 Fold Recommendation

v19 should remain a carrier/persistence fold:

1. Add the invocation hash-domain exclusion rule, or move invocation hashes out
   of the hashed dataclass for both execution and credential invocation
   carriers.
2. Give history-bridge trace validation enough inputs for `d23_state_for(...)`
   via payload fields or a named loader seam.
3. Normalize credential action vocabulary by separating
   `CREDENTIAL_ACTIONS` from `CREDENTIAL_PROPOSED_CHANGE_CLASSES`, or collapse
   the namespaces deliberately.
4. Make reservation-token persistence singular: hash-only or raw, not both.
5. Split and name the backup-registration authorization challenge versus
   registration ceremony challenge, or prove they are the same object without
   temporal contradiction.
6. Add finish-time replay/result persistence for backup credential
   registration, either on the binding row or a separate finish-use row.
7. Resolve execution invocation `source_ref_hash` / `reservation_token_hash`
   nullability.

No covenant rule moves. No architecture reopen. The WebAuthn signature-scope
question remains a canonicalization-council ruling, but v19 must first make the
challenge and finish-use bytes explicit enough for that council to judge the
actual mechanism.
