# S7.3 Spec Codex Panel v20

**Artifact reviewed:** `ee580b71aee91eee17d577a9db5a9aa6d4f1fe26`

**Files reviewed:**

- `docs/slices/s7.3-guarded-self-modification-execution/spec.md`
- `docs/slices/s7.3-guarded-self-modification-execution/deferred/credential-management-seed.md`
- `docs/slices/s7.3-guarded-self-modification-execution/reviews/spec-v20-fold-plan.md`

**Panel verdict:** RATIFY-with-fold.

**Aggregate counts:** 0 Blockers / 1 Major / 0 Minors / 0 Nits.

Plain English: the big cut worked. The in-band key-management feature is out of
the live v20 spec and preserved in the seed doc. The three v19 core blockers
are closed in the retained voice-seat path. One retained plumbing seam still
needs a tiny fold: the guarded state store must own the artifact-binding store
that the retained execution bundle loader already requires.

## Reviewer 1 - Persistence / Scope-Cut Cleanliness

**Verdict:** RATIFY-with-fold.

**Counts:** 0 Blockers / 1 Major / 0 Minors / 0 Nits.

### M1 - Retained Consume Loader Names Artifact-Binding Store But State Store Does Not Own It

`spec.md` defines `S7GuardedStateStore(...)` with
`authorization_store: S7AuthorizationStore`, but without
`artifact_binding_store: S7AuthorizationArtifactBindingStore`. The retained
execution bundle loader requires `artifact_binding_store` explicitly, the
durable API list names `S7AuthorizationArtifactBindingStore.get(...)`, and D21
says consume verifies the artifact binding before inherited consume.

Evidence:

- `spec.md:1498-1521` - `S7GuardedStateStore(...)` constructor omits
  `artifact_binding_store`.
- `spec.md:1590-1598` - `load_guarded_execution_invocation_bundle(...)` requires
  `artifact_binding_store`.
- `spec.md:1640` - durable API list names
  `S7AuthorizationArtifactBindingStore.get(...)`.
- `spec.md:3223-3227` - consume verifies artifact binding.
- `spec.md:3247-3259` - unpack helper requires `artifact_binding_store`.

Fold shape: add
`artifact_binding_store: S7AuthorizationArtifactBindingStore` to
`S7GuardedStateStore(...)`, or explicitly define `S7AuthorizationStore` as the
artifact-binding provider and update loader/helper signatures to use that
single store name. The first option is the narrower fold.

This is a retained persistence-contract issue, not a credential-management
dangling reference.

### Affirmations

- The exact forbidden v20 cut symbols from `spec-v20-fold-plan.md` do not appear
  in live `spec.md`.
- The same symbols are preserved in `credential-management-seed.md`, so the cut
  is reversible and future-slice work does not start from memory.
- Live vocabularies no longer carry credential route/class ids:
  `S7_EXECUTION_CONSUMER_IDS`, `SURFACE_CLASSES`, and
  `EXCLUSION_REASON_CODES` are voice-seat/action/model-routing only.
- Live `spec.md` keeps only pointer/defer language for in-band
  credential/key-management.

## Reviewer 2 - Consume / Runtime Reservation-Token Seam

**Verdict:** RATIFY.

**Counts:** 0 Blockers / 0 Majors / 0 Minors / 0 Nits.

No findings. v20 closes v19 B3 for the retained S7.3 v1 voice-seat path.

### Affirmations

- Retained consume requires `reservation_token: ReservationToken`.
- The wrapper verifies
  `canonical_hash(reservation_token) == reservation_token_hash` before inherited
  consume.
- A missing or mismatched raw token returns `invalid_reservation_token` before
  inherited consume.
- The raw token is runtime-only and never persisted.
- `unpack_guarded_execution_invocation(...)` also receives the raw reservation
  token, so legacy wrapper inputs cannot become hash-only consume.
- D24 has a reservation-token live-possession regression test.

Plain English: the retained path now needs the actual runtime token in hand. A
persisted `reservation_token_hash` alone is not enough to consume and mutate.

## Reviewer 3 - Closed Vocabulary / D23 Input Contract

**Verdict:** RATIFY.

**Counts:** 0 Blockers / 0 Majors / 0 Minors / 0 Nits.

No findings. v20 closes v19 B4 and B5 for the retained core.

### Affirmations

- `EXCLUSION_REASON_CODES = frozenset` is defined as a closed retained-core
  vocabulary.
- The derivation table names one closed exclusion token for every retained
  fail-closed row.
- Unknown exclusion tokens are rejected before manifest persistence.
- Credential-only exclusion tokens left with the deferred key-management seed.
- `S7D23StateInput` is the single input carrier for `d23_state_for(...)`.
- History-bridge payload validation binds `d23_state_input_hash` to that same
  input contract and recomputes `payload.d23_state == d23_state_for(input)`.
- D24 includes table-completeness and impossible-mixed-input tests for D23 state
  production.

Plain English: the retained spec now has one set of exclusion words and one
input shape for D23 state. The old double-contract ambiguity is gone.

## Reviewer 4 - Route / Covenant-Regression Engineering Surface

**Verdict:** RATIFY.

**Counts:** 0 Blockers / 0 Majors / 0 Minors / 0 Nits.

No findings. The v20 scope cut did not weaken the retained covenant-relevant
engineering surface.

### Affirmations

- `live_guarded` rows require mintable consumer ids; fail-closed and reviewed
  exclusions require `execution_consumer_id=None` plus a closed exclusion
  reason.
- The marker-only versus authoritative-D23 split remains intact.
- Operational rows remain blocked from refusal/preference/D23 aggregation and
  covenant-escalation evidence.
- Same-box language remains an honesty limitation, not a claimed new defense.
- The founder WebAuthn voice-seat path remains intact through rendered request,
  artifact mint, atomic consume, execution grant, trace, D23 projection, and
  rollback evidence.
- D24 retains the no-hand-assemble negative test posture for positive proof.

Plain English: the cut removes key-management; it does not make the core guard
looser.

## Consolidated Judgment

v20 successfully performs the strategic big cut:

- in-band key-management leaves the live S7.3 v1 spec;
- the parked work is preserved in a future-slice seed;
- v19 B3, B4, and B5 are closed for the retained voice-seat core;
- the covenant-relevant engineering posture remains intact.

The only Codex finding is one retained store-dependency omission. It is small,
mechanical, and entirely inside the persistence contract:

```text
S7GuardedStateStore(...) must own or expose the artifact-binding store used by
load_guarded_execution_invocation_bundle(...) and D21 consume verification.
```

Recommended next move: v21 micro-fold with one named item, adding
`artifact_binding_store: S7AuthorizationArtifactBindingStore` to
`S7GuardedStateStore(...)` and a D24/acceptance grep line proving the retained
execution bundle loader has every store dependency in the transaction-owning
state store.

If the Claude v20 fresh-reader gate is covenant-clean and v21 lands this one
plumbing item, S7.3 v1 should be at the canonicalization candidate boundary.

