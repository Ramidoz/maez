# The covenant ceremony producer — design pass 1

2026-08-18. The build that unblocks everything RULING-O: today both
gravest work classes are structurally unauthorizable because
`CovenantCeremonyEvidence` has no honest producer, and cluster 2b's
live witness is impossible for the same reason (2b §10 D1).

Written the way that survived the 2b campaign: contract frozen here,
wiring left to implementation and its tests; single construct anchors,
machine-derived; RULING B (owner-ratified 2026-08-15) is a fixed input
— the proof is against repository-owned callers through supported
interfaces, store integrity assumed, consequences of raw mutation named
rather than defended against.

## §1 Verified ground truth

* `class CovenantCeremonyEvidence` (`operator_user_boundary.py:2228`)
  supports two kinds (`COVENANT_CEREMONY_KINDS`, `:196`):
  `cooling_off_second_confirmation` (two strictly-ordered timestamps +
  `second_confirmation_ref_hash`) and `reviewed_equivalent`
  (`reviewed_equivalent_ref_hash`). Repo-wide grep: **no non-test
  constructor.**
* The consumer (`def covenant_ceremony_satisfies_request`, `:2278`)
  checks isinstance, request-id and envelope-hash equality, and that
  the second confirmation is not in the future. **The ref hashes are
  validated for shape only** (`_validate_hash64`) — they reference
  nothing, and nothing revalidates them at consume. An honest producer
  without a consuming join would be decorative.
* Both daemon construction sites build `S7ExecutionAuthorization`
  without evidence (`daemon/maez_daemon.py:819`, `:903` — the field
  defaults `None`, `operator_user_boundary.py:3517`), so the consume
  path refuses highest-risk classes today. Fail-closed, unstated —
  the full-body audit's finding, still true.
* **Authorization artifacts expire ~5 minutes after their challenge**
  (`expires_at=_add_minutes(now, 5)`, `s7_webauthn_ceremony.py:474`;
  artifact `expires_at=str(challenge["expires_at"])`). A cooling-off
  measured in hours therefore CANNOT reuse the first tap's artifact.
  This single fact fixes the shape: two taps, two ceremonies, durable
  evidence between them, and only the second tap's artifact is ever
  consumed.
* The consume seat is the sole SQL updater
  (`def consume_for_execution_on_connection`,
  `operator_user_boundary.py:2966`), already consults
  `def _highest_risk_ceremony_required` (`:2270`), and is the seat
  where cluster 2b's B2 revalidation will also live. The covenant
  revalidator and B2 are siblings at one seat.
* Canon: "cooling-off plus a second distinct confirmation, or a
  reviewed equivalent named in the request"
  (`s7-operator-user-role-boundary/spec.md:385`; requirement 161,
  `:1627`).

## §2 The relation this producer exists to hold

```text
a founder tap authorized THIS request
  ... a cooling-off provably elapsed ...
a SECOND, distinct founder tap confirmed THIS SAME request
  = one durable, sealed evidence row per phase
  = a CovenantCeremonyEvidence assembled ONLY from those rows
  = re-derived from the rows inside the consuming transaction
```

Each link:

| Link | Held by |
|---|---|
| tap 1 happened, for this request | phase-1 row written in the same ceremony transaction as tap 1's artifact mint |
| the cooling-off elapsed | wall-clock comparison of the two rows' `recorded_at`, re-checked at consume — never trusted from the carrier |
| tap 2 is distinct and later | phase-2 row references phase 1 by hash; strictly later timestamp; different challenge id |
| the carrier is honest | producer assembles evidence from the rows; `second_confirmation_ref_hash` = the phase-2 row's binding hash |
| consumption re-proves it | mandatory revalidator in the sole SQL updater, keyed on `_highest_risk_ceremony_required` — same discipline as 2b §7: not a caller callback |

## §3 The durable store — the proven shape, third use

`s7_covenant_ceremony_phases_v1`, in the ceremony database, following
`_R11_EXEMPTION_EVIDENCE_DDL` (`s7_guarded_execution.py:73`) exactly as
the owner-read receipt does: CHECK-pinned constants, a binding hash
sealed over every column above it, a DDL-contract fingerprint compared
before insert and before use, insert inside the existing ceremony
transaction.

Columns (contract level; exact DDL is implementation): phase
(`first_authorization` | `second_confirmation`), request_id,
request_envelope_hash, derived_work_class (CHECK: the two RULING-O
classes only), challenge_id, credential_ref, user_presence/verification
(CHECK = 1), artifact_id of the phase's mint, for phase 2 the
`first_phase_binding_sha256` it confirms, recorded_at, binding hash
last. One phase-1 row per request; one phase-2 row per phase-1 row
(UNIQUE) — a confirmation cannot be reused, within store integrity
(RULING B's stated boundary, not re-argued here).

## §4 The producer and the consuming join

* **Phase 1** rides the existing authorize ceremony: when
  `authorize_finish` succeeds for a RULING-O class, the phase-1 row is
  written atomically with the artifact mint. That artifact will expire
  unconsumed — expected; it is evidence of authorization, not authority.
* **Phase 2** is a fresh, ordinary authorize ceremony for the SAME
  request (same envelope hash), refused unless a phase-1 row exists,
  the cooling-off has elapsed, and the challenge is new. Its mint
  writes the phase-2 row atomically and THIS artifact is consumable.
* **Assembly**: one function builds `CovenantCeremonyEvidence` from the
  two rows and nothing else — timestamps from `recorded_at`, ref hash
  = phase-2 binding hash. Module-private constructor discipline per the
  repo's own idiom (`_VALIDATOR_TOKEN`, `s7_guarded_execution.py:504`),
  carrying that idiom's honest caveat verbatim.
* **The join that makes it real**: `consume_for_execution_on_connection`
  gains a mandatory covenant revalidation for highest-risk classes —
  rows exist, contracts match, seals re-derive, request/envelope equal
  the artifact's, cooling-off re-checked against the rows, evidence
  fields equal row fields. Refusal rolls back. Without this, the
  existing shape-only check would admit caller-built evidence and the
  producer would be decoration.

## §5 PENDING OWNER — two decisions, nothing freezes before them

1. **The cooling-off duration.** Canon requires it and names no number.
   This is a protection parameter for the gravest changes to Maez, so
   it is the owner's, recorded like RULING B. Proposal to accept or
   amend: **24 hours**, matching the owner's own overnight practice for
   new-capability slices; a floor the code refuses to go beneath, not a
   default anyone can lower in config.
2. **Whether phase 1 needs its own words.** The rendered statement the
   owner taps for phase 1 could say plainly "first of two — a second
   confirmation after cooling-off will be required before this can
   execute". Recommended (the owner must not tap on a false picture —
   the R11 rule), but it touches D17 rendered bytes, so it is the
   owner's to confirm.

## §6 Sequencing

1. Owner rules on §5. 2. Gate this design (Codex). 3. Tests-first
build — the producer is ADDITIVE and dormant-by-nature: writing
evidence rows activates nothing, and both classes stay refused until a
caller passes assembled evidence, which no live caller does until the
witness. 4. Live witness with the owner: two real taps, a real
cooling-off between them, on a witness-grade request — the same session
can then serve as cluster 2b's unblocked witness path. 5. Only then any
consumer wiring.

## §7 Out of scope

`reviewed_equivalent` (stays unproducible/fail-closed; its own design);
owner-read (cluster 2b, sibling at the same seat); D23 aggregation;
any change to what the ceremonies mean — this builds the missing
producer for a ceremony canon already defines.
