# S7.3 Spec v25 Codex Engineering Panel

**Subject:** engineering review of `spec.md` v25 after the read-surface triage
fold.

**Reviewed commit:** `7735b7c87741b323baf339f121dc90e7af3fd797`

**Base fold plan:** `dc922ed2776d0b24052cddba670cb6c124b8cea1`

**Verdict:** RATIFY

No blockers. No majors. No minors. No nits.

The Codex lane finds the v25 read-surface fold complete enough for the Claude
Section 8.2 candidate gate.

## Mechanical Verification

```text
commit: 7735b7c87741b323baf339f121dc90e7af3fd797
author: Maez <maez@rohit.dev>
subject: docs(s7.3): fold v25 read-surface triage

spec.md blob: a25fc91a46bd7c0490cff23a3fc77a751c03f205
spec.md sha256: b3d759aadd2dce7206f4130bd9df11c0e2f2a22718abd01da593a128168ceabc
spec.md lines: 4112

credential-management-seed.md blob: 92bb5ddf61c44abaf256e96a067fdd9b8eee9201
credential-management-seed.md sha256: f690c5c1730b569f3a566777763d33fd4eeedc3db437c5c10ea4916279d1ed31
credential-management-seed.md lines: 7420
```

Mechanical checks:

```text
ASCII: pass
gendered-pronoun scan: pass
git diff --check: pass
scoped files only: pass
```

Unrelated workspace dirt remains outside the reviewed commit and was ignored.

## Reviewer Verdicts

| Reviewer | Lens | Verdict |
|---|---|---|
| Reviewer 1 | carry/narrow closure and persistence read-surface | RATIFY |
| Reviewer 2 | live-path / covenant-edge buildability | RATIFY |
| Reviewer 3 | vocabulary and scope-cut mechanical audit | RATIFY |
| Reviewer 4 | residual D24 / acceptance checklist audit | RATIFY |

The two fresh reviewers initially caught a deferred-seed mismatch: the seed still
contained tokenless consume examples and still implied credential invocations
could reuse the S7.3 v1 voice-seat consume wrapper. That was folded into the
amended reviewed commit before this final verdict. Both reviewers rechecked the
amended commit:

- Reviewer 1: RATIFY. Prior B1 closed; `consume_verified(...)` carries
  `reservation_token`; the voice-seat consume wrapper is narrowed to
  `S7GuardedExecutionInvocation` plus runtime `ReservationToken`; credential
  consume is deferred to a future credential-specific seam.
- Reviewer 2: RATIFY. Prior blocker and prior major closed; the final bounded
  nit about negative-test examples was folded by clarifying the checklist that
  negative examples are allowed only when the surrounding text says they fail.

## v25 Fold Coverage

### CARRY 1 - Raw Maez Response Evidence

RATIFY.

`S7VoiceConsultationBundle` now carries:

```text
raw_response_ref: str | None
raw_response_hash: str | None
```

The spec names `S7VoiceConsultationBundleStore.read_raw_response(...)` and D16
requires replay by loading the raw response, recomputing its hash, and rejecting
grounded semantic blocking evidence when replay is unavailable or mismatched.
`None` is confined to producer-blocked or no-response arms that are not
mint-eligible.

This is not decorative storage. It is the carrier byte that makes the
grounded-vs-marker-only distinction replayable.

### CARRY 2 - Reservation Token Timing

RATIFY.

`S7VoiceBundleUse.reservation_token_hash` is nullable before reservation and
non-null after reservation:

```text
reservation_state="unreserved" -> reservation_token_hash is None
reservation_state="reserved" -> reservation_token_hash is not None
```

Consume requires the runtime `ReservationToken`, verifies
`canonical_hash(reservation_token) == reservation_token_hash`, and binds that
hash to the reserved `S7VoiceBundleUse` row before inherited consume.

The deferred seed no longer contains a positive tokenless consume path. The old
compatibility wrapper now carries `reservation_token`, and credential-management
consume is explicitly deferred until a future slice defines its own
live-possession binding.

### CARRY 3 - Semantic Reader Route Identity

RATIFY.

v25 adds `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES` and persists the route
identity fields on `SemanticReaderAttemptEvidence`:

```text
semantic_reader_provider
semantic_reader_provider_model
semantic_reader_model_snapshot
semantic_reader_decoding_params_hash
semantic_reader_prompt_hash
semantic_reader_route_config_hash
```

D16 recomputes the reviewed route identity from those fields and requires
membership in `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES` before accepting a
semantic-reader attempt. The closed-vocabulary audit also covers the new reviewed
identity set.

### NARROW 1 - Challenge Expiry Source

RATIFY.

v25 correctly narrows the challenge-expiry promise. S7.3 does not claim to own
or reload the WebAuthn challenge store. S7.1 verifies the challenge and expiry
before artifact mint. S7.3 persists `challenge_expires_at`, binds it into
artifact replay, and verifies it is not expired at mint and consume.

This narrows an over-promise without weakening the founder-ceremony freshness
boundary.

### NARROW 2 - Unpack Helper Scope

RATIFY.

`unpack_guarded_execution_invocation(...)` is explicitly not the full D16
source-bundle validator. It owns carrier, binding, hash, ref, reservation-token,
and expiry replay for legacy wrapper input loading.

Full prompt-integrity, semantic-reader grounding, nonce lifecycle,
context-policy, and authority-class replay are owned by
`validate_s7_voice_source_bundle(...)` before artifact mint and by trace replay
after execution.

D24 now adds the live-path assertion:

```text
every live artifact-mint path that can lead to guarded mutation runs validate_s7_voice_source_bundle(...)
```

No path may reach mutation through unpack-only.

### NARROW 3 - Grounding Hash Owner

RATIFY.

The owner is now `SemanticReaderAttemptEvidence.semantic_reader_grounding_hash`,
not the consultation bundle. This matches the semantic-reader evidence carrier
and removes the old owner ambiguity.

### NARROW 4 - Stale Closed-Vocabulary Names

RATIFY.

The spec no longer advertises `MARKER_PARSE_STATUSES`,
`SEMANTIC_READER_RESULT_KINDS`, or `REDUCER_OUTPUT_STATES` as separate uppercase
closed vocabularies. Marker parse statuses, semantic-reader result kinds, and
reducer output states are defined inline by the concrete carrier and table rows.

### NARROW 5 - Deferred Seed API Cleanup

RATIFY.

The parked credential seed no longer preserves a positive no-token consume API:

- `consume_verified(...)` carries `reservation_token`;
- the call to `consume_artifact_for_execution(...)` passes that token;
- the voice-seat consume API accepts only `S7GuardedExecutionInvocation` plus
  runtime `ReservationToken`;
- credential-management consume is deferred until a future slice defines a
  credential-specific consume seam and live-possession binding.

Negative-test examples remain allowed only when the surrounding text states the
call fails before inherited consume.

## Mechanical Audit Results

The v25 acceptance strings from the fold plan are present:

```text
raw_response_ref: str | None
raw_response_hash: str | None
raw response replay rejects missing or mismatched raw_response_hash
reservation_token_hash: str | None
reservation_state="unreserved" -> reservation_token_hash is None
reservation_state="reserved" -> reservation_token_hash is not None
consume_artifact_for_execution(*, invocation, reservation_token,
no consume_artifact_for_execution(*, invocation, now)
S7.3 does not own the WebAuthn challenge store
unpack_guarded_execution_invocation(...) is not the full D16 source-bundle validator
semantic_reader_provider:
semantic_reader_provider_model:
semantic_reader_model_snapshot:
semantic_reader_decoding_params_hash:
semantic_reader_route_config_hash:
SemanticReaderAttemptEvidence.semantic_reader_grounding_hash
no live retained credential-management dependency in spec.md except deferred-seed references
```

The standing vocabulary audit remains exact:

```text
S7_EXECUTION_CONSUMER_IDS: 20
NON_MINTABLE_EXECUTION_CONSUMER_IDS: 1
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS: 22
SURFACE_CLASSES: 11

S7_EXECUTION_CONSUMER_IDS intersect NON_MINTABLE_EXECUTION_CONSUMER_IDS: 0
S7_EXECUTION_CONSUMER_IDS intersect REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS: 0
NON_MINTABLE_EXECUTION_CONSUMER_IDS intersect REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS: 0
```

The deferred-seed stale-positive grep found no remaining positive hits for:

```text
S7AuthorizationArtifactBinding(reservation_token=None)
stored binding reservation_token
invocation: S7GuardedExecutionInvocation | S7GuardedCredentialInvocation
consume_artifact_for_execution(*, invocation, now)
tokenless consume_artifact_for_execution(invocation=loaded_invocation, now=now)
credential invocation through S7GuardedStateStore.consume_artifact_for_execution(...)
S7GuardedCredentialInvocation through the voice-seat consume wrapper
```

The only remaining mention of `consume_artifact_for_execution(*, invocation:)`
is a negative-test example that explicitly fails before inherited consume.

## Cross-Lane Implication

The Codex engineering lane is now clean on the read-surface layer that blocked
v24. The next gate is the Claude Section 8.2 candidate read, with the focus the
operator already named:

- raw-response replay must actually enforce grounded semantic evidence;
- semantic-reader route identity must actually bind the reviewed reader
  contract;
- every live artifact-mint path that can lead to mutation must run
  `validate_s7_voice_source_bundle(...)` before mint;
- no path may reach mutation by using unpack-only replay.

## Plain English

v25 does the important split correctly. The bytes the covenant really depends on
are carried: Maez's raw response can be replayed, the semantic reader's reviewed
identity is pinned, and reservation-token possession is checked at the right
time. The things that were over-promised are narrowed instead of spawning more
tables.

The first review pass caught one last parked-document problem: the future
credential seed still had old examples that looked like tokenless consume paths.
That is fixed in the reviewed commit. The live S7.3 v1 path is now voice-seat
only: Maez is asked, the founder signs, the source bundle is validated before
mint, the runtime reservation token is presented at consume, and mutation runs
only under the consumed grant.

Codex ratifies v25 for the candidate covenant gate.
