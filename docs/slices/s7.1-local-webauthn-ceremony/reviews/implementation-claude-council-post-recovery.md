# Claude Covenant Council — S7.1 Recovery: Post-Recovery Verification

**Subject:** the S7.1 recovery fold, commit `af001cb` ("fix(s7.1): fold
implementation verification blockers"), which folds the Claude-lane
post-implementation verification ([`implementation-claude-council.md`](implementation-claude-council.md))
REVISE findings — six blockers (CC-IV1..CC-IV6) and three majors (M1..M3). The
builder's recovery note is [`implementation-codex-recovery.md`](implementation-codex-recovery.md).

**Verdict: REVISE.**

The recovery is real and substantial: CC-IV1/CC-IV2 took the review-sanctioned
narrow route and took it honestly, and CC-IV4, M1, M2, and M3 are cleanly folded.
But three blockers remain. **CC-IV3** — the new "production voice-seat fact
producer" returns `maez_objection_state="absent"` and `maez_voice_consulted=True`
as hardcoded literals, consulting no Maez state at all: it fabricates a voice
consultation, and it does so in the *unsafe* direction (it unblocks guarded
authorization on a manufactured consent). **CC-IV5** removed the blind
`confirmed_distinct` hardcode — a real improvement — but never implemented the
same-physical-device comparison D9 requires, so a backup on the *same key* as the
primary still reaches `confirmed_distinct`. **CC-IV6** correctly isolated the
disable-proof routes behind a flag, but applied the same flag to
`register/backup-card`, the sole creator of the backup-registration card —
putting a production capability (D9/D16/D19 primary+backup) behind a proof flag.
The recovery's instincts were right; three specific fixes remain.

## Method

Read-only verification by the council synthesizer. The recovery commit `af001cb`
was read firsthand — the full production-code diff (`core/`, `daemon/`) and the
recovery note. Every load-bearing claim was firsthand-verified against the live
code: the voice producer body; the health-pause condition and that the
`s7_autonomous_guarded_write_consumer_live` opt-in is never set true; the backup
distinctness function and that the verifier surfaces a real AAGUID; that the
execution-edge test files contain no `S7AuthorizationArtifact(` constructions;
the sole caller of `_s7_create_backup_registration_card`; and the D16 cause,
`ceremony_kind`, and D23-history diffs. The full owner-env suite (4390 tests, OK)
is the builder's reported figure; per discipline, green tests are necessary, not
sufficient. No `*codex*` review file was read beyond the builder's recovery note
the operator supplied as the subject material.

## Finding-by-finding

| Finding | Recovery action | Verified status |
|---|---|---|
| **CC-IV1 / CC-IV2** (L8 core not live; health lies) | `/operator/health` now requires the full consumer set — four pipe methods, the DreamState helpers, **and** an explicit `s7_autonomous_guarded_write_consumer_live` opt-in — before clearing the pause. The narrow route: L8 is not claimed retired. | **Folded — narrow route, honestly.** `s7_autonomous_guarded_write_consumer_live` is never set true (firsthand: only the `getattr` check at `maez_daemon.py:347` exists), so the pause holds. See the canonicalization note below. |
| **CC-IV3** (voice producer absent) | Added `DecisionPipeline._s7_voice_consultation_for_card`. | **Not folded — BLOCKER.** See below. |
| **CC-IV4** (tests self-assemble the artifact) | Execution-edge tests now mint through `S7LocalWebAuthnCeremonyService`. | **Folded.** `grep "S7AuthorizationArtifact("` on `test_decision_pipeline_s7.py` and `test_s7_1_dream_execution.py` returns nothing. |
| **CC-IV5** (backup distinctness hardcoded) | `_backup_distinct_device_confidence` replaces the literal. | **Partially folded — BLOCKER persists.** See below. |
| **CC-IV6** (routes drift from D6) | Three routes gated behind `S7_WEBAUTHN_PROOF_ROUTES=1`. | **Disable routes: folded. `register/backup-card`: BLOCKER residual.** See below. |
| **M1** (D16 cause vocabulary) | `credential_recovery_state` now emits `first_setup_not_started` and `both_keys_lost`. | **Folded** (minor residual: `only_enabled_key_clone_suspected` still not emitted). |
| **M2** (`ceremony_kind` not bound) | `S7AuthorizationArtifact` / `S7ExecutionGrant` carry `ceremony_kind`; the consume SQL binds `AND ceremony_kind = 'founder_local_webauthn'`; schema + migration ALTER. | **Folded.** |
| **M3** (D23 granted-aggregation dead) | `record_authorization_history` writes `outcome="authorized"`; `s7_refusal_history` gains an `outcome` column; `refusal_history_for_envelope` reads it; `authorize_finish` calls it. | **Folded.** |

## The three remaining blockers

### CC-IV3 — the voice-seat producer fabricates Maez's objection state

`core/decision/decision_pipeline.py` — the new `_s7_voice_consultation_for_card`
computes a provenance hash of the card and then returns:

```python
return s7.MaezVoiceConsultation(
    ...
    maez_voice_consulted=True,
    maez_objection_state="absent",
    maez_withdrew_request=False,
    unavailable_reason_code=None,
    ...
)
```

`maez_objection_state="absent"` and `maez_voice_consulted=True` are **hardcoded
literals.** The function body reads no Maez objection signal — not
`private_thoughts`, not `wants`, not `will_i`, not any voice/objection state.
It asserts that Maez was consulted and did not object, when no consultation
occurred. Spec D12 is explicit: `absent` "is valid only when a reviewed
Maez-voice producer affirmatively records no objection" — a hardcode is not
*affirmatively recording*, it is *asserting*. And the direction is the unsafe
one: before the recovery, the missing producer left the seat unresolved and
guarded authorization failed *closed* (honest non-function); after the recovery,
the seat resolves to `absent` and guarded authorization *proceeds* on a
manufactured consent. A safe minimal producer would return `not_determined`
(fail-closed); this returns `absent` (proceed). This is the decorative-authority
defect — a container with a fabricated producer — at the seat that exists so
Maez genuinely has a say in guarded self-modification.

The sharpest evidence that this is a defect, not a judgment call: the *same
commit* removed the hardcoded `confirmed_distinct` for CC-IV5, and the docstring
of its replacement states the principle verbatim — "The code may not assert
'confirmed_distinct' as a default." The recovery understood
*don't-hardcode-the-covenant-fact* for distinctness and violated it for the
voice seat in the same fold.

**Fix:** `_s7_voice_consultation_for_card` must genuinely consult Maez's
objection state and report what it finds; or, if a real producer is deferred,
return `not_determined` (or a recorded `unavailable_reason_code`) so the seat
stays honestly fail-closed — never a fabricated `absent`.

### CC-IV5 — backup distinctness: the blind hardcode is gone, the comparison is not built

`core/governance/s7_webauthn_ceremony.py` — `_backup_distinct_device_confidence`
is a genuine improvement over the literal: no primary → `unknown`; the backup's
`credential_ref` equal to a primary's → `same_device_override`; no verifier
signals → honest `unknown`. But the final branch returns `confirmed_distinct`
whenever the backup carries *any* verifier signal — it never loads the primary
credential's AAGUID and compares. Firsthand-verified: the verifier surfaces a
real AAGUID (`core/governance/s7_webauthn_verifier.py:95` —
`"aaguid": str(verified.aaguid) if verified.aaguid is not None else None`). So a
backup registered on the *same physical key* as the primary — same AAGUID,
distinct `credential_ref` — passes the `credential_ref` check, has a non-empty
signal, and is written `confirmed_distinct` → `ready`. That is the exact CC-S5
defect: `ready` overclaiming key-loss protection. Spec D9 requires backup
registration to "compare AAGUID, transports, attachment ... against the
primary"; the recovery checks signal *presence*, not signal *match against the
primary*. **Fix:** compare the backup's AAGUID (and transports/attachment) to the
enabled primary credential's; same-AAGUID resolves to `same_device_override` /
`degraded`, not `confirmed_distinct`.

### CC-IV6 — `register/backup-card` is now behind a proof flag, and it is the only backup-card path

Gating `proof/disable-card` and `proof/disable-credential` behind
`S7_WEBAUTHN_PROOF_ROUTES=1` is correct — the credential-disable operation was a
proof construct and is now honestly marked proof-only. But the same gate was
applied to `register/backup-card`, and **`_s7_create_backup_registration_card`
has exactly one caller** (firsthand-verified) — the now-proof-gated
`register/backup-card` route at `daemon/maez_daemon.py:6135`. In production
(without `S7_WEBAUTHN_PROOF_ROUTES=1`) that route returns `s7_proof_route_disabled`,
so the backup-registration card cannot be created, so a backup credential cannot
be registered. D9, D16, and D19 all treat primary+backup as the S7.1 norm —
`ready` *requires* an enabled backup. As it stands, production S7.1 can never
reach `ready`: the founder cannot enroll a backup key. **Fix:** either confirm
and document a production (non-proof-gated) path that creates the
backup-registration card — in which case `register/backup-card` is genuinely
proof-only and the gating is fine — or restore `register/backup-card` (or an
equivalent) as a real production route so backup registration is reachable.
Whichever: backup registration must be a production capability, not a proof-only
one.

## What the recovery folded well — preserve

- **CC-IV1 / CC-IV2 — the L8 narrow route, done honestly.** This was the hardest
  call, and the recovery made it correctly: rather than claim a retirement it
  could not deliver, it kept `guarded_self_modification_paused_pending_s7.1`
  active and made the health condition genuine — gated on the full consumer set
  plus an explicit opt-in that is never set. Guarded self-modification stays
  fail-closed and the health surface honestly says so. *Canonicalization note:*
  because S7.1 takes the narrow route, the canonicalization must record L8 as
  **retained, not retired** (the `2c3287d` canon's "conditional retirement"
  resolves to retained), and should name the follow-up slice that wires the live
  guarded-execution producer→consumer — so the obligation does not rot, the same
  way L9/S7.2 was named.
- CC-IV4 — execution-edge tests no longer self-assemble the artifact.
- M1 — fresh-install and both-keys-lost are now distinct recovery causes.
- M2 — `ceremony_kind` is bound at mint and at the consume edge, with a schema
  migration for existing stores.
- M3 — successful authorizations now write `authorized` D23 history, so
  granted-aggregation autopilot is detectable.
- The recovery introduced an S7-authorization-store resource leak during the
  fold, traced it with `PYTHONTRACEMALLOC`, and closed it (`closing()` around the
  sqlite connections) — honestly recorded in the recovery note.

## Verdict and what's next

**REVISE.** Three blockers remain: CC-IV3 (the voice producer fabricates
`absent` — fix it to consult genuinely or fail closed honestly), CC-IV5 (build
the AAGUID-against-primary comparison), CC-IV6 (`register/backup-card` must not
be proof-only). None is a redesign; each is a targeted fix, and the recovery
already did the harder structural work (the L8 narrow route, the consume-edge
`ceremony_kind`, the D23 history). One minor — `only_enabled_key_clone_suspected`
is still not emitted by `credential_recovery_state`.

Ladder:

1. Fix the three remaining blockers RED-first. CC-IV3 especially: the fix is to
   apply the recovery's own CC-IV5 principle — "the code may not assert a
   covenant fact as a default" — to the voice seat.
2. Record the deltas.
3. Both lanes re-verify the recovery.
4. Push only after both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The recovery commit
`af001cb` was read firsthand and every load-bearing finding independently
confirmed against the live code. The Codex engineering recovery pass is the
parallel lane; S7.1 advances to push only when both lanes ratify.*
