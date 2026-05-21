# S7.3 Spec v25 Fold Delta-Plan - Read-Surface Triage

**Subject:** edits to `spec.md` and
`deferred/credential-management-seed.md` for v25.

**Sources:**

- v24 spec: `a558e549a4331305f7f46672d42d65874ce0d5db`
- Codex engineering panel v24:
  `reviews/spec-codex-panel-v24.md` at
  `04981be2d4ff8e5b05f987a88ee3c86ee9e993b6`
- v21 covenant gate:
  `reviews/spec-fresh-reader-gate-v21.md` at
  `907576e7b7d41e4902414533d413190dd0000000` (covenant-clean baseline)

**Verdict being folded:** Codex v24 REVISE, 3 Blockers / 3 Majors / 2 Minors /
1 Nit.

**Strategic rule for v25:** do not reflexively carry every byte a sentence can
imply. Split findings by kind:

- **CARRY** when the byte is covenant-enforcement evidence or a state-timing
  invariant an implementation cannot honestly derive otherwise.
- **NARROW** when the current prose over-promises replay precision beyond the
  carrier surface needed by S7.3 v1.
- **CLEAN** when the issue is stale deferred-seed or wording drift.

This is the cycle-breaking move. v14-v24 repeatedly fixed one carrier, then a
review found a new sentence that promised more replay than the carriers exposed.
v25 should carry the bytes that enforce the covenant core and narrow the rest of
the over-promises to the actual retained core.

## Must-Cover Checklist

| # | Item | Class | v25 posture |
|---|---|---|---|
| 1 | Raw Maez response evidence carrier/loader | Blocker | CARRY - covenant-load-bearing |
| 2 | `S7VoiceBundleUse.reservation_token_hash` nullable until reservation | Blocker | CARRY - state timing |
| 3 | Deferred seed stale no-token consume APIs | Blocker | CLEAN |
| 4 | Challenge-expiry source comparison | Major | NARROW unless existing S7.1 loader is already named |
| 5 | Unpack helper replay promise wider than dependencies | Major | NARROW preferred |
| 6 | Semantic-reader concrete route identity | Major | CARRY - covenant-load-bearing |
| 7 | Grounding-hash owner prose | Minor | CLEAN |
| 8 | Stale closed-vocabulary names | Minor | NARROW/CLEAN |
| 9 | Credential-management grep-test wording | Nit | CLEAN |

## 1. Raw Maez Response Evidence - CARRY

**Absorbs:** Codex v24 B1.

**Why this must be carried:** raw Maez response evidence is how D11/D13/D16
replay grounding. It is part of the covenant distinction between marker-only
blocking evidence and grounded semantic blocking evidence. If S7.3 says a
blocking marker plus grounded semantic signal can become authoritative, the raw
response ref/hash must be durable or loaded through a named private seam.

**v25 edit:**

Add the raw response replay fields to the immutable bundle shape, or name a
private loader seam owned by `S7VoiceConsultationBundleStore`. Lane lean:
carry the fields directly on `S7VoiceConsultationBundle` because v24 already
made that carrier the replay root.

```text
S7VoiceConsultationBundle(
    ...
    raw_response_ref: str | None,
    raw_response_hash: str | None,
    ...
)
```

Normative prose:

```text
`raw_response_ref` points to private raw Maez response storage owned by
`S7VoiceConsultationBundleStore`; `raw_response_hash` is
`canonical_hash(raw_response_text)` when a response exists. D16 loads the raw
response by `raw_response_ref`, recomputes `raw_response_hash`, and rejects
grounded semantic blocking evidence when raw response replay is unavailable or
mismatched.
```

`None` is allowed only for producer-blocked/no-response arms that are already
not mint-eligible.

**D24 test:** positive authoritative-blocking replay fails if
`raw_response_ref` is missing, if the loaded raw response hash mismatches, or if
the raw response cannot reproduce the semantic reader input hash.

## 2. Bundle-Use Reservation Token Timing - CARRY

**Absorbs:** Codex v24 B2.

**Why this must be carried:** this is state timing, not prose style. Before
reservation, no token exists. After reservation, token hash is required and
must bind runtime token, invocation, and bundle-use row.

**v25 edit:**

Change:

```text
reservation_token_hash: str
```

to:

```text
reservation_token_hash: str | None
```

Then state the lifecycle invariant:

```text
reservation_state="unreserved" -> artifact_id is None, reservation_token_hash is None,
reserved_at is None, consumed_at is None

reservation_state="reserved" -> artifact_id is not None,
reservation_token_hash is not None, reserved_at is not None, consumed_at is None

reservation_state="consumed" -> artifact_id is not None,
reservation_token_hash is not None, reserved_at is not None, consumed_at is not None
```

D16 pre-artifact validation requires the unreserved branch. D21 consume requires
the reserved branch and verifies:

```text
canonical_hash(reservation_token) == invocation.reservation_token_hash
invocation.reservation_token_hash == voice_bundle_use.reservation_token_hash
```

**D24 test:** constructing an unreserved use row with non-null token hash fails;
constructing a reserved/consumed use row with null token hash fails; mismatched
runtime token fails before inherited consume.

## 3. Deferred Seed No-Token Consume APIs - CLEAN

**Absorbs:** Codex v24 B3.

**Why this is cleanup:** the seed is deferred, not live S7.3 law, but it must be
a safe future starting point. It cannot preserve raw-token or no-token consume
shapes that the live spec has already rejected.

**v25 edit:**

In `deferred/credential-management-seed.md`, replace every stale shorthand:

```text
consume_artifact_for_execution(*, invocation, now)
```

or equivalent no-token signature with:

```text
consume_artifact_for_execution(
    *,
    invocation: S7GuardedExecutionInvocation | S7GuardedCredentialInvocation,
    reservation_token: ReservationToken,
    now: datetime,
    connection: sqlite3.Connection | None = None,
    after_consume_before_commit: S7PostConsumeCallback | None = None,
) -> S7ConsumeResult
```

Every seed consume success path that marks a bundle-use row consumed must state
that `canonical_hash(reservation_token)` matches both invocation and bundle-use
`reservation_token_hash`.

**D24/checklist:** seed audit rejects `consume_artifact_for_execution(*,
invocation, now)` and rejects persisted raw `reservation_token` fields.

## 4. Challenge Expiry Source Comparison - NARROW Preferred

**Absorbs:** Codex v24 M1.

**Why this should usually narrow:** S7.3 inherits WebAuthn challenge minting and
challenge expiry from S7.1. If S7.3 does not own a challenge store, do not add a
new S7.3 challenge carrier just to satisfy wording. Instead, state exactly what
S7.3 verifies from the inherited artifact/binding.

**v25 edit, preferred:**

Narrow the promise:

```text
S7.3 does not own the WebAuthn challenge store. S7.1 verifies the challenge and
expiry before artifact mint. S7.3 persists `challenge_expires_at` on
`S7AuthorizationArtifactBinding`, verifies it is not expired at mint and
consume, and binds it into artifact-binding replay. S7.3 does not independently
reload the original WebAuthn challenge record unless a future S7.1/S7.3 bridge
names that loader.
```

If the live code already exposes an inherited challenge loader that the spec can
name without invention, the v25 author may instead carry it as:

```text
webauthn_challenge_store: S7WebAuthnChallengeStore
```

and require equality against `artifact_binding.challenge_expires_at`. Do not
invent a new challenge store in S7.3 v1.

**D24 test:** S7.3 rejects expired `artifact_binding.challenge_expires_at`; the
test must not require an unnamed S7.3-owned challenge store.

## 5. Unpack Helper Replay Promise - NARROW Preferred

**Absorbs:** Codex v24 M2.

**Why this should narrow:** `unpack_guarded_execution_invocation(...)` is a
compatibility helper for legacy wrapper inputs. Making it perform full D16
semantic/prompt replay turns it into a second source-bundle validator and keeps
expanding dependency lists. The cycle ends if the helper promises only
carrier/binding/hash/ref loading, while D16 remains the full replay seam.

**v25 edit:**

Narrow the helper contract:

```text
`unpack_guarded_execution_invocation(...)` is not the full D16 source-bundle
validator. It reloads the persisted invocation and the execution bundle carriers
needed for consume preflight, verifies row hashes and direct hash/ref equality,
reservation-token hash binding, route status, expiry ceilings available on the
loaded carriers, and artifact-binding equality. Full prompt-integrity,
semantic-reader grounding, nonce lifecycle, context-policy, and authority-class
replay are owned by `validate_s7_voice_source_bundle(...)` before artifact mint
and by trace replay after execution.
```

Move `invalid_prompt_integrity` and `invalid_authority_class_replay` out of the
unpack-helper-specific promise if the current text assigns them there. They may
remain wrapper/preflight failures only when produced by the source-bundle
validator, not by unpack alone.

**D24 test:** unpack can fail on missing carrier, hash/ref mismatch, token
binding mismatch, stale/superseded request, and expiry lattice mismatch. It does
not claim to rerun semantic-reader or prompt-integrity replay unless those store
dependencies are actually in its signature.

## 6. Semantic-Reader Concrete Route Identity - CARRY

**Absorbs:** Codex v24 M3.

**Why this must be carried:** semantic-reader identity is part of the grounded
semantic signal. If the reader model/config/prompt route is not pinned, a later
reader cannot tell whether grounded-vs-marker-only evidence was produced by the
reviewed reader contract.

**v25 edit:**

Add the concrete route identity tuple either to `SemanticReaderAttemptEvidence`
or to a named `SemanticReaderRouteIdentity` carrier loaded by the attempt
evidence. Lane lean: carry it on `SemanticReaderAttemptEvidence`, since the
attempt hash already anchors reader output.

```text
SemanticReaderAttemptEvidence(
    ...
    semantic_reader_provider: str,
    semantic_reader_provider_model: str,
    semantic_reader_model_snapshot: str,
    semantic_reader_decoding_params_hash: str,
    semantic_reader_prompt_hash: str,
    semantic_reader_route_config_hash: str,
    ...
)
```

D16 verifies these fields against `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES`
or the existing reviewed route-config hash set. If that reviewed set does not
already exist, define the closed reviewed hash set rather than leaving the route
identity prose-only.

**D24 test:** changing provider/model/snapshot/decoding/prompt/route config
changes `semantic_reader_attempt_hash` or fails route-identity validation.

## 7. Grounding Hash Owner - CLEAN

**Absorbs:** Codex v24 m1.

**v25 edit:**

Replace stale wording:

```text
The bundle's `semantic_reader_grounding_hash`
```

with:

```text
`SemanticReaderAttemptEvidence.semantic_reader_grounding_hash`
```

No carrier move is implied.

## 8. Stale Closed-Vocabulary Names - NARROW/CLEAN

**Absorbs:** Codex v24 m2.

**v25 edit:**

At the paragraph that says `MARKER_PARSE_STATUSES`,
`SEMANTIC_READER_RESULT_KINDS`, and `REDUCER_OUTPUT_STATES` "remain" closed
vocabularies, choose one:

- define the sets in v25 if the retained spec uses them as normative closed
  vocabularies; or
- remove the names from that paragraph if the retained spec now defines the
  concrete literal unions inline.

Lane lean: remove stale names unless a later annotation still names them. Do not
introduce new closed sets only to preserve old prose labels.

**D24 test:** every uppercase closed-vocabulary name mentioned by a type
annotation or normative closed-set paragraph has a definition in `spec.md`.

## 9. Credential-Management Grep Test Wording - CLEAN

**Absorbs:** Codex v24 n1.

**v25 edit:**

Replace:

```text
no credential-management symbol in spec.md (lift complete)
```

with:

```text
no live retained credential-management dependency in spec.md except deferred-seed
references
```

The test must permit orientation text that points to
`deferred/credential-management-seed.md`, but reject live carriers, wrappers,
stores, route rows, or closed vocabularies from the deferred key-management
surface.

## v25 Acceptance Checklist

The v25 author runs these before committing:

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

And still:

```text
S7_EXECUTION_CONSUMER_IDS has exactly the 20 target values
NON_MINTABLE_EXECUTION_CONSUMER_IDS has exactly action_engine_final_mutate
REVIEWED_FUTURE_EXECUTION_CONSUMER_IDS has exactly the 22 target values
SURFACE_CLASSES has exactly the 11 credential-free pre-cut values
S7_3_ROLLBACK_PATH_CLASSES
credential-management-seed.md exists and carries the lifted surface
```

## Both-Lane Note

Claude lane should stay out until Codex clears this engineering read-surface
layer. The covenant surface was v21-certified clean, and v22-v24 did not move
the covenant rules. When Codex returns RATIFY or bounded-nit-only, the next
Claude `Section 8.2` gate should focus on whether the now-carried raw-response
and semantic-reader route identity bytes actually enforce the grounded-vs-
marker-only distinction.

## Plain English

v25 should stop the replay-contract churn by making a conscious split. Carry the
bytes that protect the covenant: Maez's raw response, the semantic-reader
identity, and the reservation-token timing. For the rest, stop promising more
than the spec needs to prove. If S7.3 does not own the WebAuthn challenge store,
say that. If unpack is only a carrier loader, say that. If old closed-vocabulary
names are stale, remove them.

The goal is not to make the spec bigger. The goal is to make every remaining
promise either backed by a carrier or deliberately narrowed to the carrier
surface S7.3 v1 actually owns.
