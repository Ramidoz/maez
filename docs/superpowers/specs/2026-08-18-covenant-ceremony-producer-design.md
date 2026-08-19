# The covenant ceremony producer — design pass 4

2026-08-18. Pass 1 was gated and FAILED with 8 blockers (1 CRITICAL).
All verified and upheld; the critical one was an architectural collision
with the consultation plane that changes the shape, so this is a whole
rewrite, not a patch. Contract level; wiring belongs to implementation;
RULING B is a fixed input.

## STATUS, 2026-08-18: CONTRACT FROZEN · WIRING OPEN · NOTHING BUILT

Three gate rounds: 8 → 5 → 13 findings. The rise in round 3 is the same
divergence signature cluster 2b showed at the same stage: the four
CRITICALs were genuine contract defects and are fixed below (the 2b
dependency cycle broken, the activation interlock added, constructor
inputs persisted, the two clocks split); the other nine were wiring —
literal constructor keys, per-check retention lists, sixth seats —
which prose cannot pin without every edit rippling. The owner ratified
this exact disposition for 2b, and it is applied here by precedent:

**FROZEN — reopening requires a new gate round:** RULINGs B and C; the
two-phase no-mint shape (§2); the retention-by-test rule and its frozen
exclusion list; the challenge-schema extension and its named seats; the
two-digest/two-clock store contract (§3); persisted constructor inputs;
append-only supersession; the activation interlock; the §6 order
including the compatibility gate, the structurally non-authorizing
witness, and the template-byte ratification before the combined
witness.

**OPEN — settled by implementation and its tests:** exact DDL and
literal digest key lists, the retention test's mechanics, signatures,
threading detail, refusal-token spellings.

**The gate's next reading is CODE.** Findings against the frozen list
block; findings against the open list are implementation review.

## §0 What pass 1 got wrong

* **Phase 1 minted a normal RULING-O artifact.** RULING-O classes are
  voice-seat classes (`VOICE_SEAT_WORK_CLASSES`,
  `operator_user_boundary.py:395`), so every artifact mint consumes the
  single voice-bundle reservation slot (`source_ref_hash` is the
  PRIMARY KEY, `s7_guarded_execution.py:2797`; the reservation predicate
  requiring `artifact_id IS NULL` is at `:2960`) — and, once 2b lands, one consultation attempt
  yields at most one RULING-O artifact (`UNIQUE (consult_attempt_id)`,
  2b §5). Two mints therefore need two consultations, or phase 1 must
  not mint. **Pass 2 chooses: phase 1 does not mint.**
* "Same transaction" was again offered as correspondence; 2b already
  proved it is only simultaneity.
* The phase-2 challenge was not bound to its phase at begin — an old
  spare challenge could be finished after cooling-off and called a
  confirmation.
* The witness was sequenced before the daemon could thread the
  evidence, making it unpassable.
* D23 aggregation interaction ignored; owner-decision set incomplete;
  RULING B's consequences referenced but not enumerated; requirement
  161 miscited (it says "or"; the normative prose at
  `s7-operator-user-role-boundary/spec.md:385` says "plus", and the
  stricter conjunction governs).

## §1 Verified ground truth (carried + corrected)

* `class CovenantCeremonyEvidence` (`operator_user_boundary.py:2228`);
  kinds (`COVENANT_CEREMONY_KINDS`, `:196`); no non-test constructor.
* Consumer `def covenant_ceremony_satisfies_request` (`:2278`) checks
  shape and equality only; ref hashes reference nothing.
* Daemon constructors omit the evidence (`daemon/maez_daemon.py:819`,
  `:903`) — but the downstream interfaces already carry it: the
  decision pipeline forwards it (`core/decision/decision_pipeline.py:1587`)
  and the sole SQL updater accepts it (`operator_user_boundary.py:2978`).
  The join is implementable; it is only unreached.
* Authorization artifacts expire ~5 minutes after their challenge
  (`_add_minutes(now, 5)`, `s7_webauthn_ceremony.py:474`) — the fact
  that forces two ceremonies.
* Challenges are keyed by `challenge_id` alone; `request_id` is not
  unique (`CREATE TABLE IF NOT EXISTS s7_ceremony_challenges`,
  `s7_webauthn_bootstrap.py:102`) — multiple ceremonies per request are
  possible, which is both what makes phase 2 implementable and why the
  phase-2 challenge must be BOUND at begin (§3).
* D23: a protection-lowering `authorized` history row inside the 900s
  window (insertion `s7_webauthn_bootstrap.py:1350`, window `:1375`) triggers escalation that
  `authorization_aggregation_recheck` refuses
  (`s7_webauthn_ceremony.py:1334`). Any cooling-off floor below that
  window would make phase 2 unimplementable for one of the two classes.

## §2 The relation

```text
a founder tap opened the covenant window for THIS request   (no authority minted)
  ... the cooling-off provably elapsed ...
a second founder tap ran the ONE real authorization         (consultation, owner-read, artifact)
  = one durable sealed row per phase, each digest-bound to what its ceremony actually did
  = evidence assembled only from those rows
  = re-derived from the rows inside the consuming transaction
```

| Link | Held by |
|---|---|
| tap 1 happened, for this request, ON these statement bytes | dedicated challenge kind `covenant_first_confirmation` whose begin/finish RETAINS the authorize path's full check set minus authority. The retention is enumerated BY TEST against the real path, not by prose list (round 3 kept finding omissions in my lists — recovery posture, allow-list scoping, the second credential read, credential-ID equality — because a prose list of another function's checks is a copy that drifts): the build carries a test that walks authorize begin/finish's checks and asserts each is present in the covenant kind or named in a frozen exclusion list. Frozen exclusions: artifact mint, consultation/source-bundle machinery, `authorized` aggregation row, and the R11 projection comparison (R11 admits only `model_routing.cutover_cuda`, which is not a covenant class — retaining it would be dead code wearing a check's clothes) |
| the cooling-off elapsed | `phase2.challenge_created_at − phase1.recorded_at ≥ floor`, recomputed from rows at phase-2 finish AND at consume; never trusted from the carrier |
| tap 2 is the real ceremony, bound to phase 1 at begin | the ordinary RULING-O authorize path — consultation, (once 2b lands) owner-read, artifact — with one frozen schema extension: `s7_ceremony_challenges` gains a `covenant_phase2_of TEXT` column (null except for covenant phase-2 challenges), written at begin, a member of `d12_parts`, SELECTed by the finish reader, and compared for exact equality with the sealed phase-1 binding hash BEFORE WebAuthn verification. That exact phase-1 row — never a freshly selected "current" one — is the row used for maturity, expiry, phase-2 insertion and consumption revalidation. Pass 2 named the stamp with nowhere enforceable for it to live: the DDL (`s7_webauthn_bootstrap.py:102`), the insert column list (`:1054`), the finish reader (`:1127`) and the D12 comparison (`s7_webauthn_ceremony.py:1478`) all had to be named as the four seats the extension touches |
| the rows correspond to their ceremonies | one named constructor per phase, exhaustive and versioned — never "complete identity" as prose, which 2b already showed leaves call sites binding different subsets. Phase 1: `canonical_hash` over `{"domain": "s7.covenant_phase1_binding.v1"}` plus, in serializer order: challenge_id, sha256 of challenge_b64, rendered_text_hash, request_id, request_envelope_hash, derived_work_class, session_binding_hash, internal_channel_binding_hash, credential_ref, user_presence, user_verification, sign_count result, challenge created_at + expires_at, recorded_at. Phase 2: this design's OWN versioned constructor (`s7.covenant_phase2_binding.v1`) over the complete immutable artifact identity plus `first_phase_binding_sha256` — the same SHAPE as 2b §5's device but defined here with its own domain tag, so the producer has no dependency on 2b's implementation. When 2b lands, the two constructors remain distinct instruments. Row insertion and the consume revalidator call the SAME constructor |
| the carrier is honest | assembly only from rows; `second_confirmation_ref_hash` = phase-2 row binding hash; module-private constructor with the `_VALIDATOR_TOKEN` idiom's caveat (`s7_guarded_execution.py:504`) |
| consumption re-proves | mandatory revalidator inside `def consume_for_execution_on_connection` (`:2966`), keyed on `def _highest_risk_ceremony_required` (`:2270`), sibling to 2b's B2 — never a caller callback |

One consultation, one owner-read, one artifact — all at phase 2, where
the authority actually exists. No collision with the voice-bundle slot
or with 2b's uniqueness. Maez's voice is consulted at the ceremony that
can act, with the cooling-off already behind it.

## §3 Durable store

`s7_covenant_ceremony_phases_v1` in the ceremony database, the R11
evidence shape (`_R11_EXEMPTION_EVIDENCE_DDL`,
`s7_guarded_execution.py:73`): CHECK-pinned constants, DDL-contract
fingerprint before insert and before use, binding hash sealed last over
every column above it, inserts inside the phase's ceremony transaction.

Contract-level columns: phase; request_id; request_envelope_hash;
derived_work_class (CHECK: the two RULING-O classes); challenge_id;
challenge_created_at; credential_ref; user_presence/verification
(CHECK = 1); the phase-correspondence digest of §2;
`first_phase_binding_sha256` (phase 2 only); **two clocks, never
conflated** (round-3 CRITICAL): `challenge_expires_at` (the ~5-minute
ceremony expiry, a digest member) and `phase_expires_at` = recorded_at
+ 7 days (RULING C's lifetime, the maturity/supersession clock);
`supersedes_binding_sha256` (phase 1 only, nullable); recorded_at; the
row seal last.

**Every constructor input is persisted immutably in the row** (round-3
CRITICAL: a digest whose inputs cannot be re-obtained cannot be
recomputed at consume — sign counts advance, challenge rows expire).
That includes sha256(challenge_b64), rendered_text_hash, session and
channel binding hashes, and the exact POST-advance sign count integer.

**Two digests, two names, never interchanged** (round-3 finding): the
CORRESPONDENCE DIGEST (`s7.covenant_phase1_binding.v1` /
`s7.covenant_phase2_binding.v1`, canonical_hash with its sorted-key
serialization stated, over the persisted input columns) proves the row
matches what its ceremony did; the ROW SEAL (last column, over every
column above it) proves the row is intact. The revalidator recomputes
both.

**Supersession is append-only and structural** (pass 2's naive
one-live-row UNIQUE could not express it — SQLite cannot make a
uniqueness constraint time-dependent, and RULING C forbids editing the
predecessor): a fresh phase-1 row for a request must carry
`supersedes_binding_sha256` equal to the previous phase-1 row's binding
hash (UNIQUE on that column enforces single-successor); the CURRENT
phase-1 row is deterministically the one no row supersedes; a
predecessor is never updated or deleted. "Abandoned" is defined, not
felt: a phase-1 row is supersedable when expired, or when the owner
initiates a fresh phase 1 for the same request — and the new tap IS the
supersession act. One phase-2 per phase-1 stays UNIQUE on
`first_phase_binding_sha256`; a phase 2 must reference the current,
unexpired, matured phase-1 row.

**RULING B's named consequences, enumerated for THIS table rather than
cited** (the pass-1 omission): raw deletion of a phase-2 row paired
with lifecycle rollback could allow a second confirmation ceremony;
raw rewrite of phase-1's `recorded_at` could fake a matured
cooling-off; credential-registry key replacement manufactures both
taps; arbitrary same-process code bypasses the assembler token. All
four are outside the proof by the owner's ruling, stated here so no
sentence below reads as defending against them.

## §4 Producer, gates, threading

* **Phase-1 route**: new challenge kind, begin/finish shaped like the
  existing registration/authorize kinds. Finish = verify assertion,
  write phase-1 row, nothing else. Renders its own statement bytes
  (owner decision §5.2).
* **Phase-2 begin** refuses unless: live phase-1 row for this exact
  request_id + envelope hash; unexpired; matured
  (`now − phase1.recorded_at ≥ floor`); no existing phase-2. On pass it
  stamps the challenge row. **Phase-2 finish** re-derives maturity from
  rows and refuses on drift; the mint writes the phase-2 row atomically
  with the artifact, digest-bound per §2.
* **Threading** (pass-1 gap): the daemon's authorization-material
  builders (`daemon/maez_daemon.py:819`, `:903`) call the assembler for
  highest-risk classes and pass the evidence into
  `S7ExecutionAuthorization`; absent/immature rows yield `None` and the
  existing fail-closed refusal stands. The consume-side revalidator
  makes caller-built evidence worthless regardless.
* **D23**: phase 1 writes no `authorized` history row, so aggregation
  sees one authorization (phase 2). Belt: the cooling-off floor must
  exceed the D23 history window (900s) — satisfied structurally by
  RULING C's 24h.
* **Activation interlock** (round-3 CRITICAL: "all dormant" was false —
  once evidence rows exist and thread, today's shape-only consumer
  would admit them for ANY supported caller, and a witness instruction
  not to execute binds nobody). The consume revalidator lands with a
  fail-closed third arm from day one: RULING-O consumption refuses
  `owner_read_receipt_required` unless 2b's owner-read receipt exists
  and revalidates. That arm refuses unconditionally until 2b is
  implemented — making the producer witness structurally non-authorizing
  rather than politely so — and is mutation-tested like every other
  gate this campaign has built.

## §5 RULING C (covenant ceremony parameters) — RATIFIED BY THE OWNER, 2026-08-18

The owner ruled all four on 2026-08-18. Fixed inputs from here, recorded
as **RULING C** beside RULING B in the parent ruling registry:

1. **Cooling-off floor: 24 hours**, coded as a floor the software
   refuses to go beneath — not a config default. (Structural constraint
   satisfied: 24h > the 900s D23 window.)
2. **Phase-1 statement says it plainly**: first of two — a second
   confirmation after the cooling-off is required — nothing can execute
   until then. The owner never taps on a false picture.
3. **Same credential permitted for the confirming tap.** A fresh
   challenge and fresh UP/UV assertion remain structural; the
   cooling-off is the principal defence. (A distinct-credential
   requirement was offered and declined: it would make covenant changes
   impossible whenever the backup key is unretrievable.)
4. **Phase-1 lifetime: 7 days.** A lapsed or abandoned first tap is
   SUPERSEDED by a fresh phase-1 row — records are never edited, only
   superseded.

## §6 Sequencing (re-corrected: frozen 2b §9 requires this producer witnessed BEFORE 2b)

Pass 2 had one combined witness at the end, which contradicted frozen
2b's order (producer built and independently witnessed before 2b
implementation and before shared challenge behaviour changes). Fixed:

1. ~~Owner rules on §5~~ DONE 2026-08-18 (RULING C).
2. Re-gate this pass.
3. Tests-first build: phase store, phase-1 route, phase-2 begin/finish
   gates + the challenge-schema extension, assembler, consume
   revalidator, daemon threading — all dormant (evidence rows activate
   nothing; both classes stay refused until rows exist and mature).
4. Compatibility gate BEFORE the witness: prove every non-covenant
   challenge and result shape byte-unchanged by the schema extension
   (the nullable column and d12_parts member are inert when null —
   proven, not assumed; frozen 2b requires this discipline for shared
   challenge changes, and the extension precedes 2b's Construction 4).
5. INDEPENDENT producer witness, owner present: tap 1 on a
   witness-grade request, the real 24-hour cooling-off, tap 2, evidence
   assembled and revalidated — structurally non-authorizing via the §4
   interlock, not merely unexecuted.
6. Implement cluster 2b against its frozen contract.
7. The owner's template-byte ratification (parent §8 — still pending,
   and the parent sequences it before any live consumer witness).
8. The full two-phase, owner-present RULING-O execution witness — the
   first covenant-grade authorization end to end, serving both
   contracts.

**Non-authoritative readers, disposed** (round-3 finding): the
consumed-challenge reader (`def
consumed_authorization_challenge_for_artifact`,
`s7_webauthn_bootstrap.py:1149`) does not project the stamp and is NOT
a seat: phase correspondence is proven only by the sealed phase rows
and their digests, never by that reader's projection.

## §7 Out of scope

`reviewed_equivalent` (unproducible, fail-closed, own design);
owner-read internals (2b, sibling at the consume seat); D23 redesign
(only the floor constraint touches it); any change to what ceremonies
mean.
