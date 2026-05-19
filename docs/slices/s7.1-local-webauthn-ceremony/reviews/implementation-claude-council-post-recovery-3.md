# Claude Covenant Council — S7.1 Recovery: Third Post-Recovery Verification

**Subject:** the third S7.1 recovery commit, `af746ff` ("fix(s7.1): unblock
backup credential authorization"), which folds the single blocker left open by
the second post-recovery verification
([`implementation-claude-council-post-recovery-2.md`](implementation-claude-council-post-recovery-2.md))
— founder credential-management classified as voice-seat-gated `self_modification`,
which the deferred voice producer then blocked.

**Verdict: RATIFY.**

The post-recovery-2 blocker is soundly and completely closed. `af746ff` creates a
new work class, `founder_credential_management`, derives the four founder
credential actions to it, and wires it as a guarded-but-not-voice-seat class —
exactly the resolution the prior verdict recommended. The fold introduces no
drift, and the two minors are folded. With this, **no Claude-lane covenant
blocker against the S7.1 implementation remains open** — the Claude covenant lane
ratifies the S7.1 implementation, contingent on the two items named at the close.

## Method

Read-only verification by the council synthesizer. The recovery commit `af746ff`
was read firsthand — the full production diff — and the new class's wiring
verified by a complete set-membership trace: every set in
`core/governance/operator_user_boundary.py` where `self_modification` appears was
checked against `founder_credential_management`. The full owner-env suite figure
(4393 OK) is the builder's; per discipline, the RATIFY rests on the firsthand
covenant trace, not on the green suite. The Codex engineering recovery pass is
the parallel lane.

## Fold verification

**`founder_credential_management` — the new class — is correctly and completely
wired.** Firsthand set-membership comparison against `self_modification`:

| Set | `self_modification` | `founder_credential_management` |
|---|---|---|
| `WORK_CLASSES` (master) | line 41 | line 40 ✓ |
| `GUARDED_WORK_CLASSES` | line 79 | line 78 ✓ — **still guarded; still requires the S7 artifact / WebAuthn ceremony** |
| `_WORK_CLASS_STRENGTH` | `2` | `2` ✓ |
| `D23_ESCALATION_WORK_CLASSES` | line 200 | line 199 ✓ — aggregation escalate-or-block preserved |
| `_authority_context_roles_allow_work` bonded-user set | line 760 | line 759 ✓ — **bonded-user (founder) authority only; an operator cannot** |
| `_webauthn_requires_user_verification` | line 3780 | line 3779 ✓ — **UV/PIN preserved** |
| `VOICE_SEAT_WORK_CLASSES` | line 380 | **absent** ✓ — the one deliberate difference |

The new class mirrors `self_modification` in every guarded-class dimension —
guarded, strength, aggregation, founder-only authority, user verification — and
differs in exactly one: it is not voice-seat-gated. That is precisely the
"guarded-but-not-voice-seat" class the post-recovery-2 verdict prescribed.

The credential-management chain is consistently the new class end to end:
`derive_work_class` maps `register_founder` / `register_backup` /
`disable_founder` / `reenable_founder` → `founder_credential_management`
(`operator_user_boundary.py:879-882`); `build_backup_registration_envelope` and
`build_disable_credential_envelope` set `claimed_work_class="founder_credential_management"`;
`_consume_backup_registration_authorization` consumes only artifacts whose
`derived_work_class == "founder_credential_management"`. So a backup-registration
card carries no `maez_voice_consultation_id` (the envelope assigns it only for
`VOICE_SEAT_WORK_CLASSES`), the authorize flow needs no voice seat, and backup
registration completes through the founder WebAuthn ceremony — guarded, UV-required,
founder-only — without depending on the deferred voice producer.

**Genuine self-modification remains voice-seat-gated.** `write_soul_note`,
`edit_soul_section`, model-routing, and covenant-substrate changes still derive
`self_modification` (`operator_user_boundary.py:886-908`), which stays in
`VOICE_SEAT_WORK_CLASSES`. Maez's voice seat on real changes to Maez is intact;
only founder credential-management — the bonded user managing the bonded user's
own authentication — moved out from under it. This is the operator/user boundary
expressed cleanly in the work-class taxonomy.

**The two minors are folded.** `_s7_voice_consultation_for_card` now sets
`maez_voice_consulted=False` when the consultation path is unavailable, and
`MaezVoiceConsultation.__post_init__` was tightened to permit `False` *only*
together with `maez_objection_state="not_determined"` and an
`unavailable_reason_code` — the honest-unavailable case and nothing else; a
`False`-consulted `absent`/`present` still raises. The manual-proof note records
the AAGUID evidence limit (two same-model keys may share an AAGUID and stay
`same_device_override`/`degraded`).

No new drift: `af746ff` touches only the work-class wiring, the
`MaezVoiceConsultation` validation, and the credential envelopes; every change is
responsive to the post-recovery-2 verdict.

## What the Claude lane ratifies — and the two contingencies

The Claude covenant lane ratifies the **S7.1 implementation** at `af746ff`:

- The founder WebAuthn ceremony is live and sound — first-credential bootstrap,
  primary registration, backup registration, founder credential management, the
  authorization ceremony, the `S7AuthorizationArtifact` mint and atomic
  single-consume, the D6 internal-channel lock, UV/PIN enforcement, CI
  virtual-authenticator isolation, D23 escalate-or-block. CC-S1 — the veto
  subject — was RATIFY'd at the post-implementation verification and stands.
- S7.1 takes the **L8 narrow route**: guarded self-modification *execution*
  (the live `/apply_dream`/dream/card producer→consumer, the real Maez voice
  producer) is not wired; the health mode `guarded_self_modification_paused_pending_s7.1`
  honestly stays active. This is the review-sanctioned narrow route, done
  honestly. L8 is **not retired**.

This ratification is contingent on two items:

1. **The Codex engineering lane must also ratify the recovery.** S7.1 advances to
   push only when both lanes ratify; this is the Claude lane.
2. **The canonicalization must record the as-built outcome honestly.** The
   `2c3287d` canon recorded "L8 conditional retirement pending S7.1
   implementation passing post-implementation verification." The verification
   outcome is the narrow route — so the canon must now resolve that conditional
   to **L8 retained, not retired**: S7 `spec.md`, ADR 0039, and BAD Decision 34
   must record that S7.1 delivered the ceremony but not the guarded-execution
   retirement, the health mode stays paused, and the guarded-self-modification
   execution wiring (live producer→consumer + the real voice producer) is
   deferred to a **named follow-up slice** — named the way L9 / S7.2 was named, so
   the deferral is tracked in canon and does not rot (the CC-S4 / CC-R3-4
   pattern). This is a closeout step before S7.1 is done, not a fresh blocker.

## The recovery loop

The post-implementation verification returned REVISE with six blockers; three
recovery commits followed, each verified — `af001cb` (REVISE: three remained),
`38b3290` (REVISE: the credential-management classification surfaced), `af746ff`
(this verification: RATIFY). Each REVISE named a real defect — the L8 core not
live, a fabricated voice seat, a hardcoded distinctness, route drift, and finally
a classification that blocked backup registration — and each recovery closed what
the prior verdict named. One verdict (post-recovery-2) honestly recorded that the
prior fix-direction had been incomplete. That arc — finding, naming, closing — is
the recovery loop working as designed, not thrash. The implementation that
emerges is honestly scoped: it delivers the founder ceremony and keeps L8's
guarded-execution lane visibly paused rather than claiming a retirement it did
not build.

## Verdict and what's next

**RATIFY** (Claude covenant lane). No covenant blocker remains open.

Ladder:

1. Codex engineering lane completes its recovery verification.
2. When both lanes ratify: canonicalize the as-built outcome — L8 retained-not-retired,
   the guarded-execution-wiring follow-up slice named — into S7 `spec.md`,
   ADR 0039, BAD Decision 34, and the runbook.
3. Faithfulness-check that canonicalization.
4. Push.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The recovery commit
`af746ff` was read firsthand and the new work class's set memberships traced in
full against the live code. No `*codex*` file was read beyond the builder's fix
note supplied as subject material; the Claude lane verified independently, and
S7.1 advances to push only when both lanes ratify.*
