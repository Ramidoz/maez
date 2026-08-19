# The covenant ceremony producer — design pass 2

2026-08-18. Pass 1 was gated and FAILED with 8 blockers (1 CRITICAL).
All verified and upheld; the critical one was an architectural collision
with the consultation plane that changes the shape, so this is a whole
rewrite, not a patch. Contract level; wiring belongs to implementation;
RULING B is a fixed input.

## §0 What pass 1 got wrong

* **Phase 1 minted a normal RULING-O artifact.** RULING-O classes are
  voice-seat classes (`VOICE_SEAT_WORK_CLASSES`,
  `operator_user_boundary.py:395`), so every artifact mint consumes the
  single voice-bundle reservation slot (`source_ref_hash` is the
  PRIMARY KEY, `s7_guarded_execution.py:2796`; reservation requires
  `artifact_id IS NULL`) — and, once 2b lands, one consultation attempt
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
  window (`s7_webauthn_bootstrap.py:1370`) triggers escalation that
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
| tap 1 happened, for this request | dedicated challenge kind `covenant_first_confirmation`: a real UP/UV WebAuthn ceremony whose finish writes ONLY the phase-1 row — no artifact, no consultation consumed, no `authorized` aggregation row |
| the cooling-off elapsed | `phase2.challenge_created_at − phase1.recorded_at ≥ floor`, recomputed from rows at phase-2 finish AND at consume; never trusted from the carrier |
| tap 2 is the real ceremony | the ordinary RULING-O authorize path, unchanged — consultation, (once 2b lands) owner-read, artifact — except its BEGIN refuses without a matured phase-1 row and stamps `covenant_phase2_of` = phase-1 binding hash onto the challenge row |
| the rows correspond to their ceremonies | each phase row carries a canonical digest over the complete identity of what its ceremony produced (challenge id + assertion facts for phase 1; the 2b §5 artifact-binding device for phase 2), computed inside the mint/finish function — the 2b lesson, not simultaneity |
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
`first_phase_binding_sha256` (phase 2 only); `expires_at` (phase 1
only — see §5); recorded_at; binding hash. UNIQUE: one live phase-1 per
request (supersession per §5), one phase-2 per phase-1.

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
  exceed the D23 history window (900s) — stated as a hard constraint on
  §5.1, so no lawful owner ruling can create the collision.

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

## §6 Sequencing (corrected per the gate)

1. ~~Owner rules on §5~~ DONE 2026-08-18 (RULING C). 2. Re-gate this pass. 3. Tests-first build of
store + routes + assembler + revalidator + daemon threading, all
dormant (evidence rows activate nothing; both classes stay refused
until rows exist and mature). 4. Owner-present witness: tap 1, real
cooling-off, tap 2, execution consumed — end to end through the
threaded path, which by then exists. That session also serves cluster
2b's witness once 2b is implemented. 5. Nothing else.

## §7 Out of scope

`reviewed_equivalent` (unproducible, fail-closed, own design);
owner-read internals (2b, sibling at the consume seat); D23 redesign
(only the floor constraint touches it); any change to what ceremonies
mean.
