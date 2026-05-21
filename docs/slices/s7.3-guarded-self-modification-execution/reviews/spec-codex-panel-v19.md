# Codex Engineering Panel v19 - S7.3 Guarded Self-Modification Execution Spec

**Reviewed artifact:** `docs/slices/s7.3-guarded-self-modification-execution/spec.md`

**Spec commit:** `13a00d97766d57fafe62c619b5b1880079212078`

**Spec blob:** `3d2e9a26405a9ceaac82c90ef4704609ff016ec0`

**Spec SHA256:** `02601e77e588d05b55ea7788e3ca475797477f8cc52e49181a998070964d2c21`

**Panel date:** 2026-05-20

## Verdict

**REVISE.**

Raw reviewer split:

| Reviewer | Lens | Verdict | B | M | m | n |
|---|---|---:|---:|---:|---:|---:|
| Reviewer 1 | Persistence round-trip and store/DDL implementability | REVISE | 1 | 2 | 1 | 0 |
| Reviewer 2 | Credential path and authorization boundary | REVISE | 2 | 1 | 1 | 0 |
| Reviewer 3 | Route matrix, D21 consume path, and callback ownership | REVISE | 1 | 1 | 1 | 0 |
| Reviewer 4 | Closed vocabulary, trace/status producers, and D24 testability | REVISE | 2 | 1 | 2 | 0 |

Deduped panel shape:

- **Blockers:** 6
- **Majors:** 3
- **Minors:** 5
- **Nits:** 0

Plain English: v19 landed the fold it was asked to land, and it made several
important byte-level surfaces materially better. But the engineering panel
still cannot ratify because the exact credential registration write boundary is
not yet build-contract complete. The biggest remaining theme is not covenant
architecture; it is the final exactness around registration binding, challenge
hash bytes, runtime reservation-token possession, and closed vocabulary tables.

## Blockers

### B1 - Founder WebAuthn binding surface remains undecided for the live credential write

The v19 spec intentionally defers the WebAuthn registration signature-scope
ruling to the canonicalization council, but the engineering contract still has
to tell an implementor what boundary to build. The current text says the
founder-rendered credential statement binds the pre-signing
`credential_authorization_challenge`, creates
`registration_ceremony_challenge` later at `register_begin`, and makes
`register_finish` the actual credential-write edge without a second S7 artifact
consume. It then says v19 does not decide whether the begin-sign / finish-write
two-step satisfies the founder-signs-the-actual-change principle.

Evidence:

- `spec.md:4411-4415` binds the founder-rendered credential statement to the
  pre-signing challenge.
- `spec.md:5598-5601` creates the ceremony challenge at `register_begin`.
- `spec.md:5646-5654` makes `register_finish` the actual credential-write
  edge without a second consume.
- `spec.md:7161-7166` defers the signature-scope ruling.

Why this blocks: a cold implementor cannot tell whether the build contract is
"begin authorization is sufficient for the finish write" or "finish requires a
second founder authorization or an equivalent signed result boundary." The
council may be the correct body to rule, but the rule must exist before the
spec can be canonical implementation law.

Fold shape: v20 must either record the council ruling as a normative rule
inside the spec, or mark backup registration non-live until that ruling lands.
If the one-tap begin authorization remains live, state exactly what the founder
signs, exactly what finish may write, and exactly why result binding is the
mechanical substitute for signing the post-creation credential identity.

### B2 - `S7CredentialRegistrationGrantBinding` has no persisted store/DDL/load contract

The spec names `S7CredentialRegistrationGrantBinding` as the bridge between
`register_begin` and `register_finish`, and `register_finish` loads the binding
by `registration_ceremony_challenge_id`. The table is also named in checklist
text. But the artifact does not define a table schema, uniqueness keys, store
API, or lookup method for that binding.

Evidence:

- `spec.md:5624-5638` defines the binding fields.
- `spec.md:5646-5651` says `register_finish` loads the binding by ceremony
  challenge id.
- `spec.md:5672-5678` passes the binding into
  `S7CredentialRegistrationFinishUseStore.put_if_unused(...)`.
- `spec.md:6915-6919` and `spec.md:6975-6977` require the table but do not
  define it.

Why this blocks: the finish-use row is strong only if the binding itself is
durable and reloadable. Without `S7CredentialRegistrationGrantBindingStore`
and DDL, GREEN implementation must invent how finish locates and verifies the
binding.

Fold shape: add `s7_credential_registration_grant_bindings` DDL, a store API,
and lookup keys. Required keys include a unique binding id, a unique
`registration_ceremony_challenge_id`, artifact id, grant id, both challenge
hashes, rendered/request hashes, expiry fields, and consumed-at time.

### B3 - Runtime reservation-token possession has no live consume carrier path

v19 makes reservation tokens hash-only at rest, which is correct. But the
voice-seat consume path still has to prove live possession of the raw
reservation token before inherited consume. `S7GuardedExecutionInvocation`
carries only `reservation_token_hash`; the consume API and unpack helper do not
take a raw runtime token or wrapper context that contains it.

Evidence:

- `spec.md:2030-2052` gives the invocation only `reservation_token_hash`.
- `spec.md:2055-2064` says raw tokens are not persisted.
- `spec.md:5109-5115` and `spec.md:2171-2181` define consume/unpack without a
  raw token input.
- `spec.md:3024-3028` and `spec.md:6734-6738` require
  `canonical_hash(reservation_token)` comparison.

Why this blocks: implementation can satisfy the hash comparison only by
inventing a runtime input seam, or by degrading to "the hash row exists." The
second option would lose the reservation-token possession property.

Fold shape: add a runtime-only voice-seat invocation context or explicit
`reservation_token: ReservationToken` parameter to the wrapper/unpack path.
Credential paths remain tokenless by construction.

### B4 - `EXCLUSION_REASON_CODES` is used as closed but never defined

`S7SurfaceManifestRow` and the route matrix use many
`exclusion_reason_code` literals, and D2 says fail-closed or reviewed-excluded
rows return closed codes. The spec does not define the closed vocabulary or a
table-complete test for it.

Evidence:

- `spec.md:407` carries `exclusion_reason_code`.
- `spec.md:433-441` describes closed fail-closed/reviewed-excluded codes.
- `spec.md:1144-1194` embeds literal exclusion codes in matrix rows.
- `spec.md:6606-6609` and `spec.md:6671-6674` test only the general invariant.

Why this blocks: a closed-vocabulary field without a declared closed set is not
buildable at the canonicalization bar. A cold implementor must invent allowed
tokens and unknown-token rejection.

Fold shape: define `EXCLUSION_REASON_CODES`, include every manifest exclusion
token, add missing values such as the first-primary bootstrap exclusion where
needed, and add a D24 table-complete unknown-token rejection test.

### B5 - `d23_state_for(...)` has two incompatible input contracts

The deterministic D23 table uses inputs that include positive execution and a
compatibility event so it can produce `authorized` and
`legacy_operational_excluded`. The v19 history-bridge context pins a different
input tuple over reducer output, bridge status, history outcome, authority
class, and grounded-signal boolean. That tuple cannot produce all
`D23_STATES`.

Evidence:

- `spec.md:4785-4816` defines the D23 producer table.
- `spec.md:6039-6066` defines the v19 history-bridge context tuple.
- `spec.md:6722-6727` tests the new tuple.

Why this blocks: D23 producer coverage is no longer one canonical function
signature. Implementors must invent whether `d23_state_for(...)` has one
unified input object or separate bridge-only and execution/compatibility
producers.

Fold shape: choose one exact D23 state input carrier. Either make
`S7D23StateInput` include the union of fields needed by all states, or split
`d23_state_for_bridge(...)` from the execution/compatibility producer and
state which closed values each function may produce.

### B6 - Ceremony challenge hash bytes are not fully specified

The spec requires challenge phase to participate in challenge hash domains, but
only the older `challenge_hash` tuple is printed. No exact tuple is printed for
`registration_ceremony_challenge_hash`.

Evidence:

- `spec.md:1477-1480` defines `challenge_hash` over the credential request
  fields and `credential_phase`.
- `spec.md:5603-5618` introduces `CHALLENGE_PHASES` and says phase
  participates in the challenge hash domain.
- `spec.md:6740-6744` tests phase separation.

Why this blocks: the anti-replay guarantee between authorization and ceremony
challenges depends on exact bytes. Without the ceremony tuple, a builder has
to invent the hash domain.

Fold shape: define exact canonical tuples for
`credential_authorization_challenge_hash` and
`registration_ceremony_challenge_hash`, including phase token, challenge id,
request/artifact binding inputs as appropriate, expiry, and any ceremony-only
bytes.

## Majors

### M1 - History-bridge context validation is not wired into trace APIs

v19 adds `load_history_bridge_trace_payload_context(...)` and a context-aware
validator, but `S7TraceWriter.write_history_bridge_trace(...)` and generic
payload validation prose still do not say where authority/history/reducer
stores enter.

Evidence:

- `spec.md:2308-2322` lists trace writer methods.
- `spec.md:3044-3058` describes typed payload validation.
- `spec.md:6016-6067` defines the context loader and validator.

Fold shape: pick one wiring point. Either inject the required stores into
`S7TraceWriter`, pass them to `write_history_bridge_trace(...)`, or make this a
separate trace-reader validation API. D24 must assert the chosen signature.

### M2 - Stale raw `reservation_token` wording remains in artifact mint prose

Most of v19 says only `reservation_token_hash` persists. One normative
artifact-mint paragraph still says the stored binding's `reservation_token`
must equal the returned token.

Evidence:

- `spec.md:2887-2889` and `spec.md:3024-3028` state hash-only storage.
- `spec.md:3079-3088` still references raw stored reservation token.

Fold shape: replace the stale clause with
`binding.reservation_token_hash == canonical_hash(reservation_token)` and state
that the returned raw token is runtime-only.

### M3 - Post-consume callback API remains too broad

The spec says the callback is wrapper-owned, but the API accepts a generic
`after_consume_before_commit` and the D24 test checks timing rather than
effect class. For credential registration, the callback must create internal
binding/audit rows, not mutate substrate through an unbounded callable.

Evidence:

- `spec.md:5109-5115` accepts `after_consume_before_commit`.
- `spec.md:5144-5155` runs the callback before commit.
- `spec.md:2288-2290` defines a generic audit-object return.
- `spec.md:6702-6705` tests timing/rollback.

Fold shape: restrict callback effects to named internal row writes, especially
credential registration binding creation. Explicitly forbid substrate mutation,
callee invocation, shell/action execution, or arbitrary user callback work in
the post-consume callback seam.

## Minors

### m1 - Credential request reload prose omits fields present in dataclass and DDL

The consume-time reload list omits `execution_consumer_id`,
`surface_route_or_method`, `same_code_coverage_ref`, and `created_at`, despite
the dataclass/DDL and completeness tests requiring full round-trip.

Fold shape: update the reload list or replace the enumerated prose with "every
dataclass field, including..." plus the omitted names.

### m2 - `credential_rotate` history acceptance is slightly contradictory

`credential_rotate` is excluded before live request materialization, but
`request_history_family_for(...)` can still read it through
`CREDENTIAL_PROPOSED_CHANGE_CLASSES`, while a D24 row says it cannot appear on
a live S7.3 v1 credential request or history row.

Fold shape: distinguish rejected proposal audit records from live S7.3
credential history rows, or state that rotate is excluded before both request
and history materialization.

### m3 - One D2 fail-closed phrasing is weaker than the later invariant

Early D2 text says fail-closed-until-review rows with no mintable consumer id
return `None`. Later text correctly says every fail-closed/reviewed-excluded
row requires `execution_consumer_id=None`.

Fold shape: make the earlier sentence unconditional.

### m4 - Closed-enum acceptance mirror omits v19 closed sets

`CREDENTIAL_ACTIONS` and `CHALLENGE_PHASES` are closed namespaces with tests,
but the main closed-enum checklist still omits them.

Fold shape: add both names to the closed-vocabulary acceptance mirror.

### m5 - v19 grep checklist is not exact enough as a mechanical gate

Some required strings are line-wrapped in body prose but listed as single-line
grep targets, and the reservation-token raw-token phrase is not consistently
literal.

Fold shape: make the acceptance strings grepable exactly as printed, or split
long strings into shorter exact fragments.

## Affirmations

- Invocation hash-domain exclusion is the correct shape: both invocation row
  integrity hashes are excluded from their own canonical domains through
  `canonical_hash_without_field`.
- `S7GuardedExecutionInvocation` and `S7GuardedCredentialInvocation` are now
  ref/hash carriers with named bundle loaders and explicit `conn`
  dependencies.
- Execution invocation nullability is aligned for the positive voice-seat
  carrier: `source_ref_hash` and `reservation_token_hash` are non-null in
  carrier prose, DDL, and tests.
- `CREDENTIAL_ACTIONS` versus `CREDENTIAL_PROPOSED_CHANGE_CLASSES` is
  conceptually clean: proposed classes normalize to live actions or reviewed
  exclusion before carrier materialization.
- Backup credential registration is much stronger than v18: one artifact
  consume at begin, a ceremony challenge created at begin, and a single-use
  finish row at the write edge.
- Route mintability, approval-card/deferred-action posture, ActionEngine
  manifest authority, direct `append_to_file`, and compatibility consume
  boundaries remain closed apart from the runtime reservation-token input seam.
- `TRACE_STATUSES`, `MANUAL_REVIEW_STATUSES`, consume failure reasons, and the
  no-hand-assembly rule remain substantially testable.

## v20 Fold Recommendation

v20 should stay a carrier/lifecycle/closed-vocabulary fold. It should not
reopen the voice covenant architecture.

Recommended named sections:

1. Council/signature-scope decision carrier: make the backup-registration
   founder-signature boundary normative or keep backup registration non-live.
2. `S7CredentialRegistrationGrantBindingStore` plus DDL and lookup keys.
3. Runtime reservation-token input seam for voice-seat consume/unpack.
4. `EXCLUSION_REASON_CODES` closed vocabulary and table-complete tests.
5. Unified or split `d23_state_for(...)` input contract.
6. Exact challenge-hash tuples for authorization and ceremony challenges.
7. History-bridge context-store wiring into writer or reader API.
8. Stale raw-reservation-token wording cleanup.
9. Post-consume callback effect-class restriction.
10. Minor cleanup pool: credential reload list, rotate history acceptance,
    early fail-closed wording, closed-enum mirror, and grep exactness.

Plain English: v19 got the plumbing mostly into the right rooms. The remaining
work is making the last doors unambiguous: what the founder's tap authorizes
for backup-key registration, where the begin-to-finish binding is stored, how
the live wrapper proves possession of the reservation token without storing it,
what all exclusion reason words are, and which exact inputs produce each D23
state. These are still build-contract blockers, but they are sharply named.
