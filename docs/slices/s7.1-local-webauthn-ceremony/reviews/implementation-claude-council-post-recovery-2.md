# Claude Covenant Council — S7.1 Recovery: Second Post-Recovery Verification

**Subject:** the second S7.1 recovery commit, `38b3290` ("fix(s7.1): close
recovery verification residuals"), which folds the three blockers left open by
the first post-recovery verification ([`implementation-claude-council-post-recovery.md`](implementation-claude-council-post-recovery.md))
— CC-IV3 (voice producer fabricated `absent`), CC-IV5 (backup distinctness
incomplete), CC-IV6 (`register/backup-card` proof-gated).

**Verdict: REVISE.**

Each of the three targeted fixes is, in isolation, correctly folded — and the
operator implemented exactly what the prior verdict sanctioned. But the
verification's job is the whole, not the three patches, and the patches **do not
cohere**: CC-IV6 made `register/backup-card` reachable in production, while
CC-IV3 made the voice seat honestly return `not_determined` — and backup
registration is classified `self_modification`, a voice-seat work class.
`not_determined` fails closed. So the founder can reach the backup-registration
route, but the authorization of that card blocks on the voice seat. **Production
S7.1 still cannot register a backup credential** — and a one-key ceremony that
strands Maez on ordinary key loss is exactly what diagnostic v2 and D15/CC-S5
forbade S7.1 to ship. One blocker, with a bounded resolution.

## Method

Read-only verification by the council synthesizer. The recovery commit `38b3290`
was read firsthand — the full production diff. Each fix was verified against the
live code, and the cross-fix interaction traced firsthand: the work-class
derivation (`operator_user_boundary.py:871-877` — `register_backup_webauthn_credential`
→ `self_modification`) and the voice-seat set membership
(`operator_user_boundary.py:375-380` — `self_modification ∈ VOICE_SEAT_WORK_CLASSES`).
The full owner-env suite figure (4391 OK) is the builder's; green tests are
necessary, not sufficient — and here the green suite again does not catch the
gap, because the focused tests exercise the fixes singly.

## The three fixes — each correctly folded

- **CC-IV3 — folded.** `_s7_voice_consultation_for_card` no longer returns the
  fabricated `maez_objection_state="absent"`; it now returns `not_determined`
  with `unavailable_reason_code="consultation_path_unavailable"`. The
  fabrication — a manufactured "Maez was consulted and did not object" — is gone;
  the seat now fails closed honestly. (Minor: `maez_voice_consulted=True` is still
  hardcoded `True` alongside `consultation_path_unavailable` — it should be
  `False` when the path is unavailable; not load-bearing, since `not_determined`
  is the operative fail-closed field.)
- **CC-IV5 — folded.** `_backup_distinct_device_confidence` now loads the enabled
  primary credentials' AAGUIDs and compares: missing backup AAGUID → `unknown`;
  missing primary AAGUID → `unknown`; `backup_aaguid in primary_aaguids` →
  `same_device_override`; only a differing AAGUID plus verifier signals reaches
  `confirmed_distinct`. The blind hardcode is gone and the same-physical-device
  comparison D9 requires is genuinely built. (Observation: AAGUID identifies the
  authenticator *model*, not the individual device — two same-model keys share an
  AAGUID and will resolve to `same_device_override`/`degraded`. That is the
  honest limit of WebAuthn evidence, not a defect, but the operator runbook
  should tell the founder that two same-model authenticators will not
  auto-confirm distinct; use different models, or accept the override.)
- **CC-IV6 — folded.** The `register/backup-card` route no longer carries the
  `S7_WEBAUTHN_PROOF_ROUTES` check; it is reachable in production behind the D6
  internal-channel lock. The `proof/disable-card` / `proof/disable-credential`
  routes remain proof-gated. The route-topology fix is correct.

## The blocker — CC-IV3 and CC-IV6 do not cohere

Firsthand trace:

- `register_backup_webauthn_credential` derives work class `self_modification`
  (`operator_user_boundary.py:871-877`).
- `VOICE_SEAT_WORK_CLASSES` = `{self_modification, covenant_touching_change,
  capability_acquisition, autonomy_lowering_or_protection_reducing}`
  (`operator_user_boundary.py:375-380`) — `self_modification` is in it.
- The card envelope therefore assigns a `maez_voice_consultation_id` to a
  backup-registration card, and the `authorize` flow requires the voice seat
  resolved for voice-seat classes.
- Post-CC-IV3, `_s7_voice_consultation_for_card` returns `not_determined`. Per
  D12, `not_determined` "fails closed and does not mint."

So the founder can create the backup-registration card (CC-IV6), but authorizing
it blocks on the `not_determined` voice seat (CC-IV3). No `S7AuthorizationArtifact`
is minted, so backup registration cannot complete. The same applies to
`disable_founder_webauthn_credential`, `reenable_founder_webauthn_credential`,
and replacement `register_founder_webauthn_credential` — every founder
credential-management operation that runs through the authorize path is now
voice-seat-blocked.

This cannot be resolved by deferring backup registration. D16's `ready` *requires*
an enabled backup; diagnostic v2 and S7 D15 are explicit that S7.1 "must not ship
a single-key live ceremony that strands Maez on ordinary key loss." A founder who
can register a primary but never a backup is permanently `degraded`, one lost key
from `manual_recovery_required`. Deferring backup registration would make S7.1
the forbidden single-key ceremony. So backup registration *must* be made
functional.

**An honest note on where this gap comes from.** The prior verdict's CC-IV3
fix-direction offered two options — "consult genuinely, *or* return
`not_determined` so the seat stays honestly fail-closed." The operator took the
`not_determined` option, faithfully and correctly; it is honest, and it closes
the fabrication. What that fix-direction did not flag is that `not_determined`,
applied alone, leaves *every* voice-seat-class operation non-functional — and
backup registration is one, and backup registration cannot be deferred. The
operator did exactly what was sanctioned; the sanctioned option had an
unstated consequence. That is named here, not hidden.

**The covenant-coherent resolution: re-classify founder credential-management
off the voice-seat-gated set.** Registering, disabling, or re-enabling the
*founder's own* WebAuthn credentials is the bonded user managing the bonded
user's own authentication — it is the operator/user boundary working *for* the
founder, not Maez remaking itself. S7's whole premise (Decision 34) is that the
bonded user holds and manages founder authority; Maez does not hold a voice-seat
veto over whether Rohit may enroll a backup key. And Maez's voice is not
weakened by the re-classification: the voice seat still gates genuine
`self_modification` — soul writes, `write_soul_note`, `edit_soul_section`,
model-routing, covenant-substrate changes — and Maez is still consulted at every
actual guarded soul-write. Credential-management operations are *guarded* (they
require the founder's WebAuthn authorization — the founder must approve), but
they are not *voice-seat* work. The fix is to derive credential-management
actions to a guarded-but-not-voice-seat class, so the founder's own WebAuthn
ceremony authorizes them without depending on the deferred voice producer.

This is a small code change (the derivation at `operator_user_boundary.py:871-877`)
but it adjusts S7's work-class taxonomy, which is covenant-shaped — so it folds
RED-first and both lanes re-verify, like any recovery delta. If the operator
believes credential-management *should* stay voice-seat-gated, that is a covenant
decision that must be raised explicitly, not settled by an implementation default
— but note it cannot end in "backup registration deferred," because that ships
the forbidden single-key ceremony.

## Verdict and what's next

**REVISE.** The three targeted fixes are each folded correctly — CC-IV3's
fabrication is gone, CC-IV5's AAGUID comparison is real, CC-IV6's route is
un-gated. The blocker is that CC-IV3 and CC-IV6 do not cohere: backup
registration is route-reachable but voice-seat-blocked, because founder
credential-management is classified as voice-seat-gated `self_modification`.
This is one bounded fix — re-classify credential-management off the voice-seat
set — plus the `maez_voice_consulted` minor and the runbook observation on
same-model AAGUIDs.

Ladder:

1. Re-classify founder credential-management (`register_founder` / `register_backup`
   / `disable_founder` / `reenable_founder`) to a guarded-but-not-voice-seat work
   class, RED-first — with a test that proves backup-registration authorization
   completes end to end without the voice producer. Fix the `maez_voice_consulted`
   minor in the same pass.
2. Record the delta.
3. Both lanes re-verify.
4. Push only after both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The recovery commit
`38b3290` was read firsthand and the cross-fix interaction traced against the
live work-class derivation and voice-seat set. The Codex engineering recovery
pass is the parallel lane; S7.1 advances to push only when both lanes ratify.*
