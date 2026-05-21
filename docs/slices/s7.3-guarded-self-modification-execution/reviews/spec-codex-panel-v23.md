# S7.3 Spec v23 Codex Engineering Panel

**Artifact reviewed:** `spec.md` at commit `00d12e090e45da346336f20fdf2b94da505fccd1`

**Companion artifact reviewed:** `deferred/credential-management-seed.md` at the same commit

**Verdict:** REVISE

**Counts:** 4 Blockers / 2 Majors / 1 Minor / 0 Nits

## Bottom Line

v23 closes the exact v22 blockers in the live spec: the voice bundle now carries
`rendered_prompt_ref` and `context_manifest_hash`, and the bundle-use row carries
`reservation_token_hash` bound to the runtime token/invocation hash before
inherited consume.

The broader persistence lens still found build-contract gaps in the same family:
model identity replay lacks durable carrier fields, source-bundle validation
requires a bundle-use lookup seam it cannot perform before artifact mint, the
artifact-binding replay comparison list is incomplete, and the deferred seed
still contains stale raw-token wording that contradicts the live hash-only rule.

This is engineering persistence/completeness, not covenant. The scope cut and
credential deferral remain intact.

## Reviewer Results

| Reviewer | Lens | Verdict | Counts |
|---|---|---:|---:|
| 1 | v22 blocker closure / bundle persistence | REVISE | 2 / 0 / 0 / 0 |
| 2 | Carrier/store/consume buildability | REVISE | 2 / 2 / 1 / 0 |
| 3 | Closed vocab / scope-cut integrity | RATIFY | 0 / 0 / 0 / 0 |
| 4 | Residual D24 / stale wording | RATIFY | 0 / 0 / 0 / 0 |

## Blockers

### B1 - Bundle Validation Still Lacks Model Identity Carrier Fields

D7 records `runtime_identity_hash`, `model_routing_identity_hash`, and
`model_config_hash`. D14/D16 make prompt/model identity validation
load-bearing. `S7VoiceAttemptRecord` carries only `runtime_identity_hash`, and
`S7VoiceConsultationBundle` does not carry the model-routing or model-config
hashes. A positive `absent` row cannot be replay-validated without implementer
invention.

**Fix:** carry the model identity tuple on `S7VoiceConsultationBundle` or a named
secondary carrier loaded by D16, and update D16/D24 to verify it.

### B2 - Source-Bundle Validation Needs A Pre-Artifact Bundle-Use Lookup

`validate_s7_voice_source_bundle(...)` receives `bundle_store`, but no
`S7VoiceBundleUseStore`, while the validator must prove the matching
`S7VoiceBundleUse` row is unreserved and unconsumed. The only named bundle-use
API is `get_for_artifact(source_ref_hash, artifact_id, *, conn)`, which cannot
run before artifact mint.

**Fix:** add a buildable pre-artifact lookup seam, such as
`S7VoiceBundleUseStore.get_for_source_ref(source_ref_hash, *, conn)`, pass the
store and connection into `validate_s7_voice_source_bundle(...)`, and specify
that unreserved rows have no artifact id until reservation.

### B3 - Deferred Seed Still Persists A Raw Reservation Token

The deferred credential/key-management seed still defines `S7VoiceBundleUse`
with `reservation_token: str | None` and no `reservation_token_hash`. That
contradicts the live v23 hash-only rule and makes the future seed unsafe as a
starting point.

**Fix:** update the seed to use `reservation_token_hash` only. The raw token must
remain runtime-only there too.

### B4 - Deferred Seed Consume Signature Does Not Carry Runtime Reservation Token

The deferred seed's `S7GuardedStateStore.consume_artifact_for_execution(...)`
signature omits `reservation_token`, while later prose says consumption requires
the matching token. That repeats the live v22/v23 seam in the parked future
material.

**Fix:** add `reservation_token: ReservationToken` to the seed consume signature
and bind it to the invocation/bundle-use token hash in the seed prose.

## Majors

### M1 - Artifact-Binding Replay Does Not Require Every Comparison

`S7AuthorizationArtifactBinding` carries request id, rendered statement hash,
request envelope hash, action params hash, precondition hash, authority context
hash, execution consumer id, source ref hash, and challenge expiry. The execution
bundle loader explicitly verifies only a subset. The remaining fields are
load-bearing for stale request/action/precondition/expiry rejection.

**Fix:** require replay comparisons for every artifact-binding field against the
invocation, rendered statement, request envelope, work item, action params,
precondition, authority context, source bundle, and challenge expiry records.

### M2 - `unpack_guarded_execution_invocation(...)` Signature Is Narrower Than Its Promised Validation

D21 says wrapper/unpack verification covers source manifest, action params,
preconditions, expiry lattice, and reservation token. The helper signature only
receives invocation/rendered/authority/artifact-binding/bundle-use stores. It
cannot independently load work item, request envelope, surface manifest,
rollback plan, or bundle expiry.

**Fix:** either narrow the helper's promised validation to what it can load, or
add the missing store dependencies and connection to the helper signature.

## Minor

### m1 - D24 Carrier Completeness Test Is Too Narrow

D24's artifact/bundle carrier-shape test targets six carriers, but D16 also
reads `ContextManifest`, `PromptIntegrityEvidence`, `SemanticReaderAttemptEvidence`,
`S7VoiceAttemptRecord`, rollback plan evidence, and surface manifest fields.

**Fix:** broaden the test target to include named loader seams and secondary
carriers, not only the six artifact/bundle blocks.

## Affirmations

- v23 closes the exact v22 live-spec blocker fields:
  `context_manifest_hash`, `rendered_prompt_ref`, and `reservation_token_hash`
  are present in the relevant carrier blocks.
- `S7GuardedStateStore(...)` owns the broad store family needed by the
  transaction wrapper.
- The invocation hash self-exclusion rule remains clear.
- The closed vocabularies and scope cut remain intact: credential/key-management
  is still deferred, rollback vocabulary is live in `spec.md`, dangerous routes
  remain fail-closed/reserved, and the execution/future/non-mintable sets remain
  disjoint.

## Recommended v24 Fold Scope

1. Add durable model identity replay fields or a named secondary loader seam.
2. Add the pre-artifact bundle-use lookup seam and pass it into source-bundle
   validation.
3. Bring the deferred seed's reservation-token model up to the live hash-only
   rule.
4. Require full artifact-binding replay comparisons.
5. Add or narrow `unpack_guarded_execution_invocation(...)` dependencies.
6. Broaden D24's carrier/read-surface completeness test.

## Plain English

v23 fixed the exact holes v22 found, but the deeper engineering read found the
same pattern one layer wider. The spec now carries the prompt replay fields and
reservation-token hash, but still needs the model identity bytes, a way to look
up the bundle-use row before an artifact exists, full comparison of the
artifact-binding fields, and the same hash-only reservation-token rule copied
into the parked future seed.

The covenant is still not the problem. This is the database/spec contract being
forced to name every byte it later reads.
