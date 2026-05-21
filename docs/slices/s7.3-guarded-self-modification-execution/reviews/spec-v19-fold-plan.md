# S7.3 Spec v19 Fold Delta-Plan

**Subject:** specific edits to `spec.md` for v19, derived from the Codex
engineering panel v18.

**Sources:**

- v18 spec: `4e05813 / spec.md`
- Codex engineering panel v18:
  `cc50e5d / reviews/spec-codex-panel-v18.md`
- v18 fold contract:
  `6f52a0a / reviews/spec-v18-fold-plan.md`

**Convergent direction:** v18 closed the visible v18 fold surface and two
Codex lenses now ratify cleanly: route/D21/callback ownership and closed
vocabulary/trace-status/D24. The remaining work is not architecture. It is the
leaf layer below the ref-based carriers: hash domains, validator inputs,
credential action namespaces, reservation-token storage, and the exact
backup-registration begin/finish bytes.

**Plain thesis:** v19 closes the last carrier byte edges that v18 exposed. The
invocation hashes stop hashing themselves. History-bridge trace validation
gets the inputs required to recompute `d23_state_for(...)`. Credential action
tokens become their own closed namespace rather than being confused with
proposed-change classes. Reservation tokens become hash-only at rest. Backup
credential registration gets two named challenge phases and a durable finish
use row so replay/result binding can be tested without invention. Execution
invocation nullable columns become consistent with the carrier contract.

**Out of scope:** the WebAuthn registration signature-scope council item is
not a v19 fold item. v19 must make the challenge phases and finish-use bytes
explicit enough for the canonicalization council to judge that question. It
must not pre-empt the council's ruling.

## Must-Cover Checklist

The v19 spec author must land every item below as a named edit. Sections 1-3
absorb blocker-class findings. Sections 4-6 absorb major-class findings.
Section 7 absorbs the minor-class nullability finding. None may be buried in a
generic cleanup paragraph.

| # | Item | Source | v19 section |
|---|---|---|---|
| 1 | Invocation hash-domain exclusion rule | B1 | Section 1 |
| 2 | History-bridge `d23_state_for(...)` validation inputs | B2 | Section 2 |
| 3 | Credential action vocabulary split and bridge | B3 | Section 3 |
| 4 | Singular reservation-token persistence | M1 | Section 4 |
| 5 | Backup-registration two challenge phases | M2 | Section 5 |
| 6 | Finish-time replay/result durable state | M3 | Section 6 |
| 7 | Execution invocation source/ref nullability | m1 | Section 7 |

## 1. Invocation Hash-Domain Exclusion Rule

**Absorbs:** Codex v18 B1.

v18 made `S7GuardedExecutionInvocation` a ref-based carrier, but the carrier
contains `guarded_execution_invocation_hash` and then defines that hash as
`canonical_hash(S7GuardedExecutionInvocation)`. Without an exclusion rule, the
carrier hashes itself.

### v19 edit

Lane lean: keep the hash field on the persisted carrier, but exclude the hash
field from the carrier's own canonical hash domain. Apply the same rule to the
credential invocation carrier so both ref-based invocation carriers use one
pattern.

Add this normative rule beside the uniform persistence round-trip contract:

```text
Invocation-carrier hashes are row integrity hashes, not ordinary payload
fields. `guarded_execution_invocation_hash` is excluded from the
`S7GuardedExecutionInvocation` hash domain. The value is computed as
canonical_hash(S7GuardedExecutionInvocation without
guarded_execution_invocation_hash). `guarded_credential_invocation_hash` is
excluded from the `S7GuardedCredentialInvocation` hash domain. The value is
computed as canonical_hash(S7GuardedCredentialInvocation without
guarded_credential_invocation_hash).
```

Update every store verification clause that currently says
`canonical_hash(reconstructed S7GuardedExecutionInvocation)` or
`canonical_hash(reconstructed S7GuardedCredentialInvocation)` so it names the
field-excluded hash domain:

```text
canonical_hash_without_field(
    reconstructed_invocation,
    "guarded_execution_invocation_hash",
) == reconstructed_invocation.guarded_execution_invocation_hash
```

and:

```text
canonical_hash_without_field(
    reconstructed_invocation,
    "guarded_credential_invocation_hash",
) == reconstructed_invocation.guarded_credential_invocation_hash
```

No other carrier hash may include itself. If a future S7.3 row uses a row
integrity hash field, that field must either be outside the dataclass or be
named in the field-exclusion list before any store is considered conformant to
the uniform persistence contract.

### D24 tests

Add RED tests for:

- computing `guarded_execution_invocation_hash` over all fields except
  `guarded_execution_invocation_hash`;
- computing `guarded_credential_invocation_hash` over all fields except
  `guarded_credential_invocation_hash`;
- changing any non-hash invocation field changes the corresponding invocation
  hash;
- changing only the hash field does not alter the field-excluded hash domain;
- store round-trip verification uses the field-excluded hash domain for both
  execution and credential invocation carriers;
- a future row integrity hash field without an exclusion rule fails the uniform
  persistence contract test.

Acceptance grep strings:

- `guarded_execution_invocation_hash is excluded from the S7GuardedExecutionInvocation hash domain`
- `canonical_hash(S7GuardedExecutionInvocation without guarded_execution_invocation_hash)`
- `guarded_credential_invocation_hash is excluded from the S7GuardedCredentialInvocation hash domain`
- `canonical_hash(S7GuardedCredentialInvocation without guarded_credential_invocation_hash)`
- `canonical_hash_without_field`

## 2. History-Bridge `d23_state_for(...)` Validation Inputs

**Absorbs:** Codex v18 B2.

v18 gave `S7HistoryBridgeTracePayload` a decoded shape and requires
`validate_history_bridge_trace_payload(payload)` to verify
`d23_state == d23_state_for(...)`. The payload does not carry enough inputs to
recompute `d23_state_for(...)`, and the validator has no loader dependencies.

### v19 edit

Lane lean: use a named context loader rather than bloating the decoded payload
with fields that belong to authority/history rows. The payload remains the
persisted bridge trace payload. The validator receives a loaded context that
contains the exact `d23_state_for(...)` input tuple.

Add this loader seam:

```text
load_history_bridge_trace_payload_context(
    *,
    payload: S7HistoryBridgeTracePayload,
    authority_row_store: S7AuthorityRowStore,
    request_history_store: RequestHistoryStore,
    reducer_trace_store: S7ReducerTraceStore,
    conn: sqlite3.Connection,
) -> S7HistoryBridgeTracePayloadContext
```

Add this context shape:

```text
S7HistoryBridgeTracePayloadContext(
    payload: S7HistoryBridgeTracePayload,
    reducer_output: D13ReducerOutput | None,
    bridge_status: HISTORY_BRIDGE_STATUSES,
    history_outcome: S7HistoryOutcome | None,
    authority_class: AUTHORITY_CLASSES | None,
    has_grounded_semantic_blocking_signal: bool,
)
```

Then pin the input tuple:

```text
The d23_state_for input tuple is:
(
    reducer_output,
    bridge_status,
    history_outcome,
    authority_class,
    has_grounded_semantic_blocking_signal,
)
```

Update the validator signature:

```text
validate_history_bridge_trace_payload(
    payload: S7HistoryBridgeTracePayload,
    *,
    context: S7HistoryBridgeTracePayloadContext,
) -> None
```

The validator verifies:

- `context.payload == payload`;
- the SQL indexed columns match the decoded payload;
- every non-null reference in `payload` resolves through the named stores used
  by `load_history_bridge_trace_payload_context(...)`;
- `payload.history_bridge_status == context.bridge_status`;
- `payload.d23_state == d23_state_for(...)` over the exact input tuple above;
- an unreachable or missing context field fails closed before trace
  finalization.

### D24 tests

Add RED tests for:

- `validate_history_bridge_trace_payload(...)` cannot be called without a
  loaded `S7HistoryBridgeTracePayloadContext`;
- missing authority row, request-history row, or reducer trace required by the
  payload fails closed;
- mutating any field in the `d23_state_for input tuple` changes or rejects the
  recomputed state;
- every branch that emits a history-bridge trace can load a context accepted by
  the validator;
- impossible mixed inputs still hard-fail through `d23_state_for(...)`.

Acceptance grep strings:

- `load_history_bridge_trace_payload_context`
- `S7HistoryBridgeTracePayloadContext`
- `d23_state_for input tuple`
- `validate_history_bridge_trace_payload(`
- `context.payload == payload`

## 3. Credential Action Vocabulary Split And Bridge

**Absorbs:** Codex v18 B3.

The live credential carriers use `credential_action: "register_backup" |
"disable"`, while `CREDENTIAL_PROPOSED_CHANGE_CLASSES` uses
`credential_register_backup`, `credential_disable`, and `credential_rotate`.
v18 says `S7CredentialGuardedRequest.__post_init__` rejects actions outside
`CREDENTIAL_PROPOSED_CHANGE_CLASSES`, which rejects the live values.

### v19 edit

Lane lean: keep two namespaces and bridge them explicitly. Proposed-change
classes describe what a request is about before credential-route
normalization. Credential actions describe the live guarded credential
mutation after normalization.

Add:

```text
CREDENTIAL_ACTIONS = {
    "register_backup",
    "disable",
}
```

Keep:

```text
CREDENTIAL_PROPOSED_CHANGE_CLASSES = {
    "credential_register_backup",
    "credential_disable",
    "credential_rotate",
}
```

Add the bridge:

```text
credential_action_for_proposed_change_class(
    proposed_change_class: CREDENTIAL_PROPOSED_CHANGE_CLASSES,
) -> CREDENTIAL_ACTIONS | ReviewedExclusion
```

Bridge table:

| proposed_change_class | result |
|---|---|
| `credential_register_backup` | `register_backup` |
| `credential_disable` | `disable` |
| `credential_rotate` | `ReviewedExclusion(route_status="reviewedly_excluded", exclusion_reason_code="credential_rotate_future_slice")` |

Update constructor language:

```text
S7CredentialGuardedRequest.__post_init__ validates
`credential_action in CREDENTIAL_ACTIONS`. It does not validate
`credential_action` against `CREDENTIAL_PROPOSED_CHANGE_CLASSES`.
```

Update normalization language:

```text
credential_rotate is reviewedly excluded before credential action
materialization. No S7CredentialGuardedRequest, S7GuardedCredentialInvocation,
RenderedCredentialRequestStatement, artifact binding, or credential trace row
may carry `credential_action="credential_rotate"` or
`credential_action="rotate"`.
```

### D24 tests

Add RED tests for:

- `credential_action_for_proposed_change_class("credential_register_backup")`
  returns `"register_backup"`;
- `credential_action_for_proposed_change_class("credential_disable")` returns
  `"disable"`;
- `credential_action_for_proposed_change_class("credential_rotate")` returns
  the reviewed exclusion before request materialization;
- `S7CredentialGuardedRequest.__post_init__` accepts only
  `CREDENTIAL_ACTIONS`;
- no live credential carrier or trace row accepts proposed-change-class tokens
  in the `credential_action` field;
- no route normalizer may silently coerce an unknown credential token into a
  live credential action.

Acceptance grep strings:

- `CREDENTIAL_ACTIONS`
- `credential_action_for_proposed_change_class`
- `credential_rotate is reviewedly excluded before credential action materialization`
- `S7CredentialGuardedRequest.__post_init__ validates`
- `credential_action in CREDENTIAL_ACTIONS`

## 4. Singular Reservation-Token Persistence

**Absorbs:** Codex v18 M1.

The artifact binding area still reads as if raw `reservation_token` persists,
while the v18 invocation carrier and schema note say only
`reservation_token_hash` persists and the raw token is runtime-only. v19 must
make the storage rule singular.

### v19 edit

Lane lean: hash-only at rest.

Add this rule beside artifact binding and D21 consume replay:

```text
reservation_token_hash is the only persisted reservation-token value. Raw
`reservation_token` is runtime-only wrapper input. No S7.3 table persists raw
reservation tokens.
```

Update `S7AuthorizationArtifactBindingInputs`,
`S7AuthorizationArtifactBinding`, `s7_authorization_artifact_bindings`, and
any replay text so they use:

```text
reservation_token_hash: str
```

and never:

```text
reservation_token: ReservationToken
```

for persisted rows.

Consume-time verification:

```text
If a wrapper presents a raw reservation_token, D21 computes
canonical_hash(reservation_token) and compares it to the persisted
reservation_token_hash before inherited consume. The raw token is never
written to state.sqlite3, a trace payload, an artifact binding row, or a bundle
use row.
```

### D24 tests

Add RED tests for:

- `s7_authorization_artifact_bindings` has `reservation_token_hash` and no raw
  `reservation_token` column;
- artifact-binding carrier shapes contain `reservation_token_hash` only;
- wrapper consume succeeds only when `canonical_hash(raw reservation_token) ==
  reservation_token_hash`;
- raw reservation tokens never appear in trace payloads, bundle-use rows,
  artifact binding rows, or invocation rows;
- a mismatch between raw token and persisted hash fails before inherited
  consume.

Acceptance grep strings:

- `reservation_token_hash is the only persisted reservation-token value`
- `Raw `reservation_token` is runtime-only wrapper input`
- `No S7.3 table persists raw reservation tokens`
- `canonical_hash(reservation_token)`

## 5. Backup-Registration Two Challenge Phases

**Absorbs:** Codex v18 M2.

v18 says credential artifact mint loads an existing challenge by
`challenge_id` / `challenge_hash`, while `register_begin` creates the
registration challenge in the same transaction as artifact consume. That is a
temporal contradiction unless the two challenges are named separately.

### v19 edit

Lane lean: name two distinct challenge phases and state their binding rules.

Add:

```text
credential_authorization_challenge
```

Definition:

```text
The credential_authorization_challenge exists before founder signing. The
rendered credential request statement, artifact binding inputs, and
S7AuthorizationArtifactBinding bind its challenge_id, challenge_hash, and
expires_at. This is the challenge over which the founder WebAuthn authorization
gesture is made.
```

Add:

```text
registration_ceremony_challenge
```

Definition:

```text
The registration_ceremony_challenge is created by register_begin in the same
transaction as artifact consume, S7CredentialRegistrationGrantBinding
creation, and grant-use persistence. It is the WebAuthn creation challenge
presented to the new backup credential.
```

State the relationship:

```text
The two challenges are distinct by phase and purpose. They may not be silently
treated as the same row. S7CredentialRegistrationGrantBinding stores both
credential_authorization_challenge_hash and
registration_ceremony_challenge_hash. register_begin requires the
authorization challenge to match the artifact binding and creates the ceremony
challenge after artifact consume succeeds. register_finish verifies the
registration result against registration_ceremony_challenge_hash.
```

If the implementation chooses to make both phases share one underlying
WebAuthn challenge store, the row must carry a closed `challenge_phase` value:

```text
CHALLENGE_PHASES = {
    "credential_authorization_challenge",
    "registration_ceremony_challenge",
}
```

The phase value participates in the challenge hash domain so a challenge row
for one phase cannot be replayed as the other.

### D24 tests

Add RED tests for:

- artifact mint fails if `credential_authorization_challenge` is missing or
  expired;
- rendered credential statement binds
  `credential_authorization_challenge_hash`;
- `register_begin` creates `registration_ceremony_challenge` after artifact
  consume succeeds;
- `S7CredentialRegistrationGrantBinding` stores both challenge hashes;
- a ceremony challenge cannot be substituted for an authorization challenge;
- an authorization challenge cannot be substituted for a ceremony challenge;
- `register_finish` verifies the WebAuthn result against
  `registration_ceremony_challenge_hash`.

Acceptance grep strings:

- `credential_authorization_challenge`
- `registration_ceremony_challenge`
- `credential_authorization_challenge_hash`
- `registration_ceremony_challenge_hash`
- `CHALLENGE_PHASES`

## 6. Finish-Time Replay/Result Durable State

**Absorbs:** Codex v18 M3.

v18 says `register_finish` verifies single-use replay state and the new
`credential_id_hash` before writing the credential, but the durable binding
shape does not name enough finish-time state to enforce that.

### v19 edit

Lane lean: keep `S7CredentialRegistrationGrantBinding` immutable and add a
separate finish-use row. The finish-use row is the single-use replay guard for
the credential-write edge.

Add:

```text
S7CredentialRegistrationFinishUse(
    credential_registration_grant_binding_id: str,
    finish_used_at: str,
    credential_id_hash: str,
    registration_result_hash: str,
    registration_result_challenge_hash: str,
    registration_ceremony_challenge_hash: str,
    rendered_text_hash: str,
    request_envelope_hash: str,
    inserted_credential_row_id: str,
)
```

DDL:

```sql
CREATE TABLE s7_credential_registration_finish_uses (
    credential_registration_grant_binding_id TEXT NOT NULL,
    finish_used_at TEXT NOT NULL,
    credential_id_hash TEXT NOT NULL,
    registration_result_hash TEXT NOT NULL,
    registration_result_challenge_hash TEXT NOT NULL,
    registration_ceremony_challenge_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    inserted_credential_row_id TEXT NOT NULL,
    UNIQUE(credential_registration_grant_binding_id),
    UNIQUE(credential_id_hash)
);
```

Add store API:

```text
S7CredentialRegistrationFinishUseStore.put_if_unused(
    *,
    binding: S7CredentialRegistrationGrantBinding,
    finish_use: S7CredentialRegistrationFinishUse,
    registration_result: WebAuthnRegistrationResult,
    conn: sqlite3.Connection,
) -> None
```

The store verifies:

- no existing finish-use row exists for
  `credential_registration_grant_binding_id`;
- `finish_use.registration_ceremony_challenge_hash ==
  binding.registration_ceremony_challenge_hash`;
- `finish_use.registration_result_challenge_hash ==
  binding.registration_ceremony_challenge_hash`;
- `finish_use.rendered_text_hash == binding.rendered_text_hash`;
- `finish_use.request_envelope_hash == binding.request_envelope_hash`;
- `finish_use.credential_id_hash` equals the credential id produced by
  `registration_result`;
- `finish_use.registration_result_hash == canonical_hash(registration_result)`;
- challenge expiry and grant expiry are still valid at `finish_used_at`;
- the credential row insert and finish-use insert occur in the same
  `BEGIN IMMEDIATE` transaction.

Then update register-finish prose:

```text
register_finish writes the credential only through
S7CredentialRegistrationFinishUseStore.put_if_unused(...). A finish callback
that cannot create the finish-use row does not write the credential.
```

### D24 tests

Add RED tests for:

- `register_finish` creates exactly one `S7CredentialRegistrationFinishUse`
  row per `S7CredentialRegistrationGrantBinding`;
- replaying the same binding fails on
  `UNIQUE(credential_registration_grant_binding_id)`;
- reusing the same `credential_id_hash` fails on
  `UNIQUE(credential_id_hash)`;
- wrong result challenge hash, rendered text hash, request envelope hash,
  registration result hash, expired challenge, or expired grant fails before
  credential write;
- credential row insert and finish-use insert are atomic in one transaction;
- a callback that writes a credential without a finish-use row fails D24.

Acceptance grep strings:

- `S7CredentialRegistrationFinishUse`
- `finish_used_at`
- `registration_result_hash`
- `registration_result_challenge_hash`
- `UNIQUE(credential_registration_grant_binding_id)`
- `register_finish writes the credential only through S7CredentialRegistrationFinishUseStore.put_if_unused`

## 7. Execution Invocation Source/Ref Nullability

**Absorbs:** Codex v18 m1.

`S7GuardedExecutionInvocation` declares `source_ref_hash: str` and
`reservation_token_hash: str`, but illustrative DDL permits NULL. That leaves
the persisted carrier looser than the dataclass.

### v19 edit

Lane lean: guarded execution invocation is the positive voice-seat consume
carrier; its DDL should match the non-null dataclass. Compatibility or
no-bundle paths must use their explicitly named compatibility carriers rather
than storing a partial guarded execution invocation.

Update `s7_guarded_execution_invocations` DDL:

```sql
source_ref_hash TEXT NOT NULL,
reservation_token_hash TEXT NOT NULL,
```

Add this sentence:

```text
S7GuardedExecutionInvocation is not the compatibility/no-bundle carrier.
Positive guarded execution invocations require non-null source_ref_hash and
non-null reservation_token_hash. A path that lacks either value fails before
S7GuardedExecutionInvocationStore.put(...).
```

If a future compatibility path needs nullable source refs or reservation-token
hashes, it must name a separate carrier and cannot reuse
`S7GuardedExecutionInvocation`.

### D24 tests

Add RED tests for:

- `s7_guarded_execution_invocations.source_ref_hash` is `NOT NULL`;
- `s7_guarded_execution_invocations.reservation_token_hash` is `NOT NULL`;
- `S7GuardedExecutionInvocationStore.put(...)` rejects missing
  `source_ref_hash`;
- `S7GuardedExecutionInvocationStore.put(...)` rejects missing
  `reservation_token_hash`;
- compatibility/no-bundle paths do not create partial guarded execution
  invocation rows.

Acceptance grep strings:

- `source_ref_hash TEXT NOT NULL`
- `reservation_token_hash TEXT NOT NULL`
- `S7GuardedExecutionInvocation is not the compatibility/no-bundle carrier`

## 8. Both-Lane Gate And Council Sequencing Note

v19 remains a carrier/lifecycle fold. It follows v15-v18 persistence changes
that the Claude covenant lane must re-read before canonicalization. The v19
gate must run both lanes on the same committed blob:

- Claude Section 8.2 fresh-reader gate: covenant re-read, with explicit focus
  on whether the ref-based invocation carriers, hash-domain exclusions,
  credential action namespace split, reservation-token hash-only storage, and
  backup-registration challenge/finish-use bytes preserve the v14 covenant
  posture.
- Codex engineering panel: persistence and lifecycle re-read, with explicit
  focus on the seven v19 sections and the uniform persistence contract.

The WebAuthn registration signature-scope item remains reserved for the full
canonicalization council. v19 does not decide whether the
founder-signs-at-begin / writes-at-finish two-step satisfies the
founder-signs-the-actual-change principle. v19 only makes the mechanism
byte-explicit enough for the council to judge.

If the v19 gate finds a concrete contradiction in the challenge or finish-use
bytes, fold that contradiction. If the bytes are explicit and both lanes
ratify, the next canonicalization step must convene the council ruling before
the final header flip and tag.

## 9. v19 Acceptance Checklist

Before v19 gate dispatch, grep the committed spec for these strings:

```text
guarded_execution_invocation_hash is excluded from the S7GuardedExecutionInvocation hash domain
canonical_hash(S7GuardedExecutionInvocation without guarded_execution_invocation_hash)
guarded_credential_invocation_hash is excluded from the S7GuardedCredentialInvocation hash domain
canonical_hash(S7GuardedCredentialInvocation without guarded_credential_invocation_hash)
canonical_hash_without_field
load_history_bridge_trace_payload_context
S7HistoryBridgeTracePayloadContext
d23_state_for input tuple
context.payload == payload
CREDENTIAL_ACTIONS
credential_action_for_proposed_change_class
credential_rotate is reviewedly excluded before credential action materialization
credential_action in CREDENTIAL_ACTIONS
reservation_token_hash is the only persisted reservation-token value
Raw `reservation_token` is runtime-only wrapper input
No S7.3 table persists raw reservation tokens
credential_authorization_challenge
registration_ceremony_challenge
credential_authorization_challenge_hash
registration_ceremony_challenge_hash
CHALLENGE_PHASES
S7CredentialRegistrationFinishUse
finish_used_at
registration_result_hash
registration_result_challenge_hash
UNIQUE(credential_registration_grant_binding_id)
register_finish writes the credential only through S7CredentialRegistrationFinishUseStore.put_if_unused
source_ref_hash TEXT NOT NULL
reservation_token_hash TEXT NOT NULL
S7GuardedExecutionInvocation is not the compatibility/no-bundle carrier
```

Also run the normal artifact checks:

```text
git diff --check -- docs/slices/s7.3-guarded-self-modification-execution/spec.md
LC_ALL=C grep -nP '[^\x00-\x7F]' docs/slices/s7.3-guarded-self-modification-execution/spec.md
Run the standard gendered-pronoun scan used by the S7.3 ladder.
```

## Plain English Close

v18 made the right plumbing visible, and the remaining bugs are the kind that
only show up once the plumbing has names: a hash accidentally included itself,
a validator lacked the context required to recompute its state, a credential
field mixed two vocabularies, and the backup-key registration flow still
needed to name the two different challenges involved.

v19 answers those byte questions directly. It says what bytes go into each
hash, where reservation tokens may live, what a credential action token is,
which challenge is signed before begin, which challenge is created at begin,
and which durable row proves finish was used once and bound to the result.

No covenant rule moves. No architecture reopens. The fold exists so the next
gate can ask the real final question with the bytes on the table: now that the
backup-registration mechanism is explicit, does the council accept its
signature-scope guarantee as S7.3 law?
