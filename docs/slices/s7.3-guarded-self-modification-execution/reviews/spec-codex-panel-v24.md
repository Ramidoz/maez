# S7.3 Spec v24 Codex Engineering Panel

**Artifact reviewed:** `spec.md` at commit `a558e549a4331305f7f46672d42d65874ce0d5db`

**Companion artifact reviewed:** `deferred/credential-management-seed.md` at the same commit

**Verdict:** REVISE

**Counts:** 3 Blockers / 3 Majors / 2 Minors / 1 Nit

## Bottom Line

v24 closes several v23 findings. The live spec now carries model identity fields
on the voice bundle, has a pre-artifact bundle-use lookup seam, updates the
deferred seed to hash-only reservation-token persistence, broadens the unpack
helper dependencies, and expands D24's read-surface completeness test.

The next engineering layer is still not fully closed. The main remaining issues
are raw Maez response evidence, nullable pre-reservation token-hash state,
challenge-expiry replay against a source record, and several stale/too-wide
read-surface promises.

This remains engineering persistence/read-surface closure. The covenant and the
scope cut remain intact.

## Reviewer Results

| Reviewer | Lens | Verdict | Counts |
|---|---|---:|---:|
| 1 | v23 closure / seed reservation-token model | REVISE | 1 / 1 / 0 / 0 |
| 2 | End-to-end buildability | REVISE | 2 / 2 / 2 / 1 |
| 3 | Closed vocab / scope-cut integrity | RATIFY | 0 / 0 / 0 / 0 |
| 4 | Residual D24 / stale wording | RATIFY | 0 / 0 / 0 / 0 |

## Blockers

### B1 - Raw Maez Response Evidence Has No Visible Carrier Or Loader

D7 says `BondedMaezRuntimeTurn` records `raw_response_hash`, and the producer
records `raw_response_ref` in `S7VoiceConsultationBundleStore`. D11/D13 require
raw response text/hash for grounding replay. D16 promises to compare model
identity and replay evidence against the source runtime turn. But
`S7VoiceConsultationBundle` carries neither `raw_response_ref` nor
`raw_response_hash`, and the durable store API lists no raw-response loader.

**Fix:** add `raw_response_ref` and `raw_response_hash` to the voice bundle or
name a private raw-response loader seam owned by `S7VoiceConsultationBundleStore`
and used by D16/D22 replay.

### B2 - `S7VoiceBundleUse.reservation_token_hash` Is Non-Null Before Reservation

`S7VoiceBundleUse` declares `reservation_token_hash: str`, but D16 validates the
pre-artifact row while it is still `reservation_state="unreserved"` and
`artifact_id is None`. The token hash is written only later in
`put_artifact_with_bundle_reservation(...)`.

**Fix:** make `reservation_token_hash: str | None` until reservation, with D16
requiring `None` for unreserved rows and D21 requiring non-null equality after
reservation.

### B3 - Deferred Seed Still Exposes No-Token Consume APIs

The deferred seed still contains older shorthand/API paths that describe
`consume_artifact_for_execution(*, invocation, now)` or omit `reservation_token`,
even though later seed prose now requires runtime token possession and
hash-only persistence.

**Fix:** update the stale seed signatures/prose so every consume path that can
mark a bundle-use row consumed receives a runtime `reservation_token` and checks
its hash against invocation and bundle-use rows.

## Majors

### M1 - Artifact-Binding Challenge Expiry Is Not Independently Replayed

`S7AuthorizationArtifactBinding.challenge_expires_at` is carried and checked for
not-expired, but the replay text does not compare it against a loaded WebAuthn
challenge/expiry source record. The expiry lifecycle says D21 loads challenge
expiry, but the unpack/helper signature lacks the source dependency.

**Fix:** add the challenge/expiry store dependency or name the inherited S7.1
loader seam, then require equality against `artifact_binding.challenge_expires_at`.

### M2 - Unpack Helper Still Promises Replay Failures Beyond Its Dependencies

`unpack_guarded_execution_invocation(...)` now receives many stores, but still
does not receive prompt-integrity, semantic-reader-attempt, voice-attempt,
context-policy, or nonce-use dependencies that D16 uses for full replay. Yet its
failure partition includes prompt-integrity and authority-class replay failures.

**Fix:** either add those dependencies or narrow unpack to hash/ref carrier
loading and leave full D16 replay to the source-bundle validator.

### M3 - Semantic-Reader Concrete Identity Is Not Fully Pinned

D12 requires provider, provider model, snapshot/version, decoding parameters,
prompt hash, and route config hash to be pinned for each consultation. The
current carrier path exposes `semantic_reader_attempt_hash`, and attempt evidence
carries config/version/prompt fields, but not the full route manifest identity
tuple.

**Fix:** add the missing semantic-reader route identity fields to
`SemanticReaderAttemptEvidence` or to a named route-identity carrier loaded by
D16.

## Minors

### m1 - Grounding Hash Owner Is Stale

D11 refers to the bundle's `semantic_reader_grounding_hash`, but the field lives
on `SemanticReaderAttemptEvidence`, not `S7VoiceConsultationBundle`.

### m2 - Several Closed Vocabulary Names Are Declared But Not Defined

`MARKER_PARSE_STATUSES`, `SEMANTIC_READER_RESULT_KINDS`, and
`REDUCER_OUTPUT_STATES` are named as closed vocabularies that "remain", but the
v24 live spec does not define them.

## Nit

### n1 - Credential-Management Grep Test Is Self-Contradictory

D24 says `no credential-management symbol in spec.md`, but the spec
intentionally contains deferred-seed references and the test line itself contains
the phrase. Make the test say "no live retained dependency except deferred-seed
references."

## Affirmations

- v24 is materially stronger than v23. It carries the model identity tuple,
  names the pre-artifact bundle-use lookup, broadens unpack dependencies, and
  makes D24's read-surface test cover secondary carriers/loaders.
- Reservation-token live possession remains the right shape: raw token at
  runtime, hashes only in durable rows, fail before inherited consume.
- Closed vocabularies and scope cut remain intact.

## Recommended v25 Fold Scope

1. Add raw-response ref/hash carrier or loader seam.
2. Make `S7VoiceBundleUse.reservation_token_hash` nullable until reservation and
   define state-specific invariants.
3. Clean stale no-token consume APIs from the deferred seed.
4. Add a challenge-expiry source loader/comparison.
5. Align unpack helper dependencies with its promised replay failures, or narrow
   the helper promise.
6. Pin semantic-reader route identity fields.
7. Fix the grounding-hash owner prose.
8. Define or remove stale closed vocabulary names.
9. Tighten the credential-management grep test wording.

## Plain English

v24 improved the spec again, but Codex still found more "you promised to replay
this, but no carrier carries the bytes" issues. The biggest one is simple:
grounding replay needs Maez's raw response evidence, but the visible bundle shape
does not carry the raw response ref/hash or name a loader for it. Another is
state timing: a bundle-use row cannot have a reservation-token hash before the
reservation exists.

This is still not a covenant failure. It is the same byte-contract layer being
forced all the way down.
