# S7.3 Spec v20 Fold Delta-Plan - Scope Cut

**Subject:** edits to `spec.md` for v20. v20 is a SCOPE-CUT fold, not a carrier
fold. It removes credential/key-management from S7.3 v1 entirely and closes the
three remaining core-path blockers, so the converging covenant core can
canonicalize without being held hostage by the non-converging key-management
sub-area.

**Sources:**

- v19 spec: `13a00d9 / spec.md`
- Codex engineering panel v19: `5247ea2 / reviews/spec-codex-panel-v19.md`
- v19 fold contract: `fc1a954 / reviews/spec-v19-fold-plan.md`

**Decision (operator, 2026-05-21):** big cut. Defer ALL credential/key-management
(register backup, disable, the entire credential apparatus) to its own future
reviewed slice. Rationale: strong multi-credential authentication is premature
before Maez is fully functional; and "disable a key" without "register a key" is
not a coherent standalone capability (the founder could only ever shrink the key
set, never grow it). The key-management sub-area produced a blocker or major in
every Codex round v14-v19 and its hardest item (the founder-signature boundary)
is a covenant decision, not a spec detail.

**Covenant safety statement (load-bearing):** this cut does NOT weaken the S7.3
covenant core. The founder continues to physically sign every voice-seat
self-modification with the WebAuthn credential established in S7.1. What is
deferred is the ability to *manage* credentials in-band (add/retire keys), which
is operational robustness, not the guard itself. The voice-seat path - Maez is
asked, the founder signs with the existing key, the change executes under the
marker/D23/operational/honesty discipline - is untouched and is what
canonicalizes.

## Must-Cover Checklist

| # | Item | Source | v20 section |
|---|---|---|---|
| 1 | Lift credential/key-management surface to a preserved future-slice doc | Decision | Section 1 |
| 2 | Verify voice-seat path has no hard dependency on departed credential carriers | Decision / safety | Section 2 |
| 3 | Close reservation-token runtime-possession seam (voice-seat core) | v19 B3 | Section 3 |
| 4 | Define `EXCLUSION_REASON_CODES` closed set (core entries only) | v19 B4 | Section 4 |
| 5 | Resolve `d23_state_for(...)` single vs split input contract | v19 B5 | Section 5 |
| 6 | Record findings resolved-by-deferral (no v20 edit needed) | v19 B1/B2/B6 + credential M/m | Section 6 |
| 7 | Future-slice handoff (parked work + signature-scope council item) | Decision | Section 7 |
| 8 | Both-lane gate note | Process | Section 8 |
| 9 | v20 acceptance checklist | Process | Section 9 |

## 1. Lift The Credential/Key-Management Surface To A Preserved Future-Slice Doc

The credential-management material is **moved, not deleted**. The v20 spec author
lifts it out of `spec.md` into a preserved future-slice seed document so the work
is resumable as a working doc, not just recoverable from git history. Proposed
location:

```text
docs/slices/s7.3-guarded-self-modification-execution/deferred/credential-management-seed.md
```

(Operator may instead open a sibling future slice directory and name it; the only
requirement is that the lifted material lands in a committed working doc, intact.)

**Surface to lift (seed list - the v20 author completes by grep; this is
non-exhaustive but names the symbols known from the v14-v19 panels):**

- Carriers: `S7CredentialGuardedRequest`, `S7GuardedCredentialInvocation`,
  `RenderedCredentialRequestStatement`, `S7CredentialGuardedTrace`,
  `S7CredentialRegistrationGrantBinding`, `S7CredentialRegistrationFinishUse`,
  `S7GuardedCredentialInvocationBundle`.
- Stores: `S7CredentialGuardedRequestStore`,
  `S7GuardedCredentialInvocationStore`,
  `S7CredentialRegistrationGrantBindingStore`,
  `S7CredentialRegistrationFinishUseStore`, and any credential-only payload
  tables (`s7_credential_guarded_requests`, `s7_guarded_credential_invocations`,
  `s7_credential_trace_payloads`, `s7_credential_registration_*`).
- Helpers/wrappers: `unpack_guarded_credential_invocation(...)`,
  `load_guarded_credential_invocation_bundle(...)`,
  `execute_guarded_credential_mutation(...)`,
  `credential_request_method_for_surface(...)`,
  `credential_work_class_for(...)`.
- Closed vocabularies: `CREDENTIAL_ACTIONS`,
  `CREDENTIAL_PROPOSED_CHANGE_CLASSES`, `CHALLENGE_PHASES`, the two challenge
  phase names (`credential_authorization_challenge`,
  `registration_ceremony_challenge`), and credential-only consumer ids in
  `S7_EXECUTION_CONSUMER_IDS` (`s7_credential_register_backup`,
  `s7_credential_disable`, and siblings).
- Surface-manifest rows: credential register begin/finish, backup-card,
  disable-card, disable-credential, card WebAuthn begin/finish.
- D24 tests: every credential-specific test row.
- Honesty Banner: the credential-management caveat paragraph (the same-box and
  marker/D23 caveats STAY - they are voice-seat-core).

**What stays (the canonical core):** `GuardedWorkItem`, `WorkRequestEnvelope`,
`S7GuardedExecutionInvocation` (voice-seat), the voice consultation bundle and
its stores, the D13 reducer, the D19 bridge, `D23_STATES` + `d23_state_for(...)`,
voice + execution traces, the founder WebAuthn signature over voice-seat
self-modification, `RenderedRequestStatement` (voice-seat render), the
artifact/grant/consume machinery, the route manifest (ActionEngine / cockpit /
Telegram / model-routing rows), `ActionEdgeGrantUse`, the uniform persistence
contract, and all non-credential closed vocabularies.

## 2. Verify Voice-Seat Path Has No Hard Dependency On Departed Carriers

After the lift, the v20 author and BOTH gate lanes must confirm the separation is
clean:

- No retained (voice-seat / core) carrier, store, function signature, DDL, route
  row, closed-vocabulary set, or D24 test references any lifted credential-only
  symbol.
- The founder's self-modification authorization path continues to resolve through
  the S7.1-established credential and the inherited WebAuthn challenge, with no
  call into the (now-departed) credential-management apparatus.
- `S7_EXECUTION_CONSUMER_IDS`, `SURFACE_CLASSES`, `EXCLUSION_REASON_CODES`, and
  the surface manifest contain no dangling credential references after the lift.

D24 adds a "no-dangling-credential-reference" acceptance test: a grep/discovery
pass proving no retained symbol names a lifted symbol.

## 3. Close Reservation-Token Runtime-Possession Seam (v19 B3)

Voice-seat core; stays and must close. v19 made reservation tokens hash-only at
rest, but the consume path has no way to prove live possession of the raw token.

**v20 edit:** add a runtime-only voice-seat invocation context, or an explicit
`reservation_token: ReservationToken` parameter, to the wrapper/unpack path, so
consume can compute `canonical_hash(reservation_token)` and compare it to the
stored `reservation_token_hash` before inherited consume. The raw token is
runtime-only and never persisted. D24 asserts: a consume with a mismatched or
absent raw token fails closed before inherited consume.

## 4. Define `EXCLUSION_REASON_CODES` Closed Set (v19 B4)

Core; stays and must close. The field is used as closed but never defined.

**v20 edit:** declare `EXCLUSION_REASON_CODES` as a closed vocabulary covering
every exclusion token used by retained surface-manifest rows (e.g.
`first_primary_bootstrap_out_of_scope` if still present post-cut, plus any
fail-closed-until-review tokens on retained routes). Credential-only exclusion
tokens leave with the lift in Section 1. Add a D24 table-complete unknown-token
rejection test.

## 5. Resolve `d23_state_for(...)` Single vs Split Input Contract (v19 B5)

Core; stays and must close. The deterministic D23 table and the history-bridge
context pin two incompatible input tuples.

**v20 edit:** choose one exact shape. Lane lean (carry Codex v19 B5): either make
`S7D23StateInput` the union of fields all `D23_STATES` need, or split
`d23_state_for_bridge(...)` from the execution/compatibility producer and state
exactly which closed values each function may produce. Wire the history-bridge
validator (Codex v19 M1) to whichever shape is chosen. D24 asserts every
`D23_STATES` value is produced by the named function(s) over the chosen input(s).

## 6. Findings Resolved By Deferral (No v20 Edit Needed)

These v19 findings disappear with the cut and require NO v20 spec edit beyond the
lift in Section 1. Record them as resolved-by-deferral so the v20 gate does not
re-flag them against the core:

- **B1** founder WebAuthn signature boundary for the live credential write -
  deferred with the registration sub-area (and with it, the canonicalization
  council's signature-scope ruling; see Section 7).
- **B2** `S7CredentialRegistrationGrantBinding` store/DDL/load contract.
- **B6** ceremony-challenge hash tuple.
- Credential majors (M-class) and minors from v14-v19 still open against the
  credential surface.

## 7. Future-Slice Handoff

- The lifted `credential-management-seed.md` carries six rounds of drafting plus
  six rounds of Codex findings - it is the future slice's starting point, not a
  blank page.
- The WebAuthn-registration **signature-scope council item**
  (`project_s7_3_webauthn_registration_signature_scope`) moves with it. It is NO
  LONGER an S7.3 v1 canonicalization-gate item; it becomes the founding covenant
  question of the future credential-management slice, ruled on by the full Claude
  six-role council when that slice is taken up.
- The future slice has a clean precondition: it should be scheduled when Maez is
  functional enough that in-band key-management (backup, rotation, disable)
  earns its complexity.

## 8. Both-Lane Gate Note

v20 spec gets the FULL both-lane gate:

- **Claude `Section 8.2` three-reader gate** - the comprehensive covenant read,
  finally convened since v14 (the v17 interim spot-read was scoped). It must
  confirm (a) the cut preserved the covenant core untouched, (b) the voice-seat
  founder-signature path is intact, and (c) no covenant invariant was weakened by
  the removal. It reviews a SMALLER, core-only spec.
- **Codex engineering panel v20** - confirms the cut is clean (no dangling
  references), B3/B4/B5 closed, and the core path is build-contract complete.

If both ratify with no blockers and no covenant-load-bearing majors, v20 is the
canonicalization candidate. There is no signature-scope council ruling on the
S7.3 v1 critical path anymore - it left with the cut.

## 9. v20 Acceptance Checklist

The v20 spec author runs a grep-style checklist before committing. Concepts that
must be findable (exact strings may vary):

```text
EXCLUSION_REASON_CODES = frozenset
reservation_token: ReservationToken
canonical_hash(reservation_token) == reservation_token_hash
d23_state_for( OR d23_state_for_bridge(
S7D23StateInput OR explicit split-producer contract
no credential-management symbol in spec.md (lift complete)
credential-management-seed.md exists and carries the lifted surface
no-dangling-credential-reference test
```

And concepts that must NOT be findable in `spec.md` after the lift:

```text
S7CredentialGuardedRequest
S7GuardedCredentialInvocation
RenderedCredentialRequestStatement
S7CredentialRegistrationGrantBinding
execute_guarded_credential_mutation
CREDENTIAL_ACTIONS
CHALLENGE_PHASES
registration_ceremony_challenge
```

(except as a one-line pointer to the deferred seed doc).

## Plain English

v20 is the cut. It lifts the entire key-management feature - registering backup
keys, disabling keys, all the machinery - out of the spec and into a preserved
document that becomes its own future slice when Maez is functional enough to need
it. Nothing is deleted; the work is parked, intact, with six rounds of review
banked as that slice's head start.

What stays is the whole reason S7.3 exists: Maez is asked before it changes
itself, the founder physically signs the change with the key they already have,
and the change executes under the full discipline. That core is untouched and is
what becomes law.

The cut also closes the three small leftover issues in the core path (proving
possession of the reservation token, defining the exclusion-reason words, and
picking one input shape for the D23 state function). The hard founder-signature
question leaves with the registration work, where it becomes that slice's main
event instead of a recurring blocker.

Then the full both-lane review runs one more time on the smaller core spec. If
both lanes clear it, S7.3 v1 canonicalizes and the next move is building.
