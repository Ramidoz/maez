# Claude Covenant Council — S7.1 Spec: Second-Fold Verification

**Subject:** spec v2 — `docs/slices/s7.1-local-webauthn-ceremony/spec.md`,
committed at `690e765` ("docs(s7.1): fold spec review findings"). The v2 fold of
the S7.1 spec, after the Claude covenant council
([`spec-claude-council.md`](spec-claude-council.md)) returned **REVISE — VETO**
and the Codex engineering panel ([`spec-codex-panel.md`](spec-codex-panel.md))
returned REVISE.

**This document verifies:** that the Claude council's findings — the seven
consolidated blockers (CC-S1, the veto trigger; CC-S2..CC-S7) and the ten themed
majors (CC-S8..CC-S17), plus the load-bearing minors — were folded into v2
correctly, and that the fold introduced no drift. Most critically: whether v2's
bootstrap and internal-channel repair meets the veto's two stated lift conditions.

**Verdict: RATIFY — the veto lifts.** v2 meets both CC-S1 veto-lift conditions,
and meets condition B1 by doing *both* sanctioned options — honest narrowing
*and* an enforced UID/TTY gate. Every Claude council blocker and major is folded:
the seven blockers fully, the ten majors substantively, the load-bearing minors
addressed — including the anti-self-assembly rule now written as a numbered RED
line. The fold introduced no drift, no new gap, and no overclaim — it *removed*
several (the "L8 Resolution" header, the decorative record-hash "detection"
claim, the fresh-install/recovery conflation, D2's over-reaching boundary claim).
Two minor tightenings (T-1, T-2 below) are recommended for the canonicalization
stage; neither is a second-fold blocker. Spec v2 is ready to proceed down the
ladder.

## Method

Read-only verification by the council synthesizer. Spec v2 was read in full from
a fresh read of the committed text (`690e765`). Each Claude council finding was
checked against v2's actual text, and the fold drift-checked against v1. The
three "weaker than inherited S7 canon" charges (CC-S2 UV/PIN, CC-S11 voice-seat,
CC-S12 aggregation) were firsthand-verified against S7 canon at the council
stage (`S7 spec.md` D10, D13, D23); this second-fold verifies v2's text now
carries the repair. The spec is a proposal — there is no code to firsthand-probe
— so the second-fold verifies the spec's *text* now carries the council's
findings. This is the established synthesizer second-fold, matching the S7.1
diagnostic second-fold precedent. The Codex engineering second-fold is the
operator's parallel lane; the spec advances to the canonicalization stage when
both lanes' second-folds ratify. No `*codex-panel*` file was read.

## The veto-lift verification

The veto was exercised by Logical/veto on CC-S1 — the first-credential bootstrap
— on B1 and B2 jointly. The council doc stated two lift conditions. Against them:

1. **B1 — distinguish the owner's invocation from an operator's, or honestly
   narrow the claim; pick one.** Met — and over-met: v2 does *both*. *Honest
   narrowing:* D2's enforceable claim is now exactly "cockpit HTTP access alone
   and originless local daemon HTTP calls cannot enroll the first founder
   credential," and D2 explicitly does *not* claim software can distinguish
   Rohit from an operator holding Rohit's OS account, repo shell, or raw
   filesystem — "That residual is inherited S7 L1." *Enforced gate:* the
   bootstrap CLI "runs only from an interactive TTY," "refuses when the effective
   UID does not own `memory/s7_1_webauthn/`," "refuses non-interactive
   invocation," and records UID/TTY provenance. The Honesty Banner now names the
   bootstrap token as a bearer secret inside the L1 limitation (folding
   Outside-View MINOR-1). The council doc required the spec to *pick one* of the
   two options; v2 took both — strictly stronger than the condition.

2. **B2 — close the race: cap live intents, a conditional-rowcount consume SQL
   in the credential-insert transaction with a primary-count guard, concurrent
   RED tests.** Met. D2 caps live intents ("refuses ... if any unconsumed,
   unexpired bootstrap intent already exists"). The first-primary finish
   transaction is a conditional `UPDATE ... WHERE ... consumed_at IS NULL AND
   expires_at > :now AND NOT EXISTS(SELECT 1 ... primary AND enabled = 1)` — the
   conditional-rowcount consume with the primary-count guard inside the `WHERE`.
   "The credential insert and the bootstrap consume happen in the same
   transaction ... exactly one bootstrap row is consumed and exactly one primary
   credential row is inserted." Sibling intents are invalidated before commit; a
   persistent `bootstrap_closed_at` marker means deleting credential rows does
   not reopen first bootstrap (folding Creative M3). RED tests 10–17 cover
   conditional-rowcount SQL, one-transaction consume+insert, concurrent
   first-registration, sibling invalidation, `bootstrap_closed_at`, and
   lost/expired-token reissue.

**The internal-channel half of CC-S1 — load-bearing for the veto by the
council's own framing — is folded.** D6 adds an authenticated cockpit-to-daemon
internal channel; originless local `curl` to `/internal/s7/webauthn/...` write
routes fails closed with `s7_internal_channel_untrusted` before any
bootstrap/verifier/credential work; D2 adds "the token is never accepted on a
daemon internal route unless the request also arrives through the authenticated
cockpit-to-daemon channel"; and the spec states explicitly "no implementation
may claim CC-S1 closed while leaving internal registration routes reachable by
arbitrary local `curl`." The fold treated CC-S1 and the internal-route gap as
one defect closed from both sides — exactly the integration the council flagged
as required for CC-S1 to be genuinely closed.

**All conditions met. The first link of the authority chain — the bootstrap, the
authority root — is now soundly specified, not merely named. The veto lifts.**

## Finding-by-finding fold verification

| Finding | v2 fold | Verified |
|---|---|---|
| **CC-S1** (blocker, veto) | D2 honest narrowing + enforced TTY/UID gate + conditional-rowcount finish transaction + single-live-intent cap + `bootstrap_closed_at` + sibling invalidation; D6 authenticated internal channel + `s7_internal_channel_untrusted`. | **Folded — veto-lift conditions met** (above). |
| **CC-S2** (UV/PIN) | D9 fields `uv_capable` / `uv_required_for_guarded`; D11 sets `uv_required=True` for the four guarded classes — "a presence-only assertion cannot mint artifacts for self-modification, covenant-touching, capability-acquisition, or protection-lowering work"; `CeremonyChallenge.uv_required`; D18 `uv_policy_state`; RED 62, 65, 105. | **Folded.** Now operationalized in a decision, the data model, the flow, the projection, and tests. |
| **CC-S3** (L8 dream consumer) | D15 "Positive autonomous/direct flow" (7 steps) + the "Autonomous Guarded Write" runtime flow; "not treated as accomplished until positive-path tests walk the live producer and consumer for `/apply_dream`"; RED 96–99 — the *negative* **and** the *positive* path. | **Folded.** The container is now a specified flow with positive-path tests. |
| **CC-S4** (L9 not canonized) | D17 names the canonicalization targets — S7 `spec.md` Named Limitations, ADR 0039, BAD Decision 34, the operator runbook; Implementation Order item 19. | **Folded.** The deferral no longer lives only in the slice's own page. |
| **CC-S5** (backup distinctness) | D9 compares AAGUID/transports/attachment against the primary, records `distinct_device_confidence`, same-device override leaves status `degraded` not `ready`; D16 "`ready` must not be inferred from credential count alone"; RED 41–42. | **Folded.** The diagnostic's same-physical-authenticator honesty clause is restored and strengthened. |
| **CC-S6** (artifact substitution) | D14 step 7 — the execution edge "derives the request identity and D12 hashes from the work item ... not from caller-supplied handles"; the consume SQL `WHERE` binds the full D12 hash set; "tests must prove that substitution fails"; RED 80. | **Folded.** |
| **CC-S7** (virtual authenticator) | D19 — isolated test DB path outside live memory, test origin/RP not served by production cockpit, "production cockpit launched without a remote-debugging port"; RED 53–54. | **Folded.** The isolation mechanism is specified, not asserted. |
| **CC-S8** (manual-recovery dead end) | D16 `manual_recovery_cause` enum + "S7.1 has no local witnessed recovery procedure" stated plainly for the terminal causes; D18 `manual_recovery_cause`; RED 110–111. | **Folded.** The dead end is named honestly. |
| **CC-S9** (registry integrity) | D8 record-hash claim downgraded to corruption/schema-drift detection with an explicit external-root caveat; D9 `disabled_by_authorization_id` / `reenabled_by_authorization_id`; RED 45, 51. | **Folded** — see tightening T-2 (audit-JSONL). |
| **CC-S10** (`grant_source`) | D14 consume SQL adds `AND grant_source = 'founder_webauthn' AND ceremony_kind = 'founder_local_webauthn'`; RED 81–82. | **Folded.** Founder-scoping is now in the consume `WHERE`, not only prose. |
| **CC-S11** (voice seat) | D12 — valid `unavailable` "blocks all non-liveness repair classes"; the authorization finish step "re-queries or re-validates the voice-seat fact immediately before minting"; RED 87, 89. | **Folded.** Both the canon-alignment and the TOCTOU gap. |
| **CC-S12** (D23 escalate-or-block) | D13 — guarded-class aggregated re-asks "must escalate the ceremony or block. Warning-only text is insufficient"; RED 93. | **Folded.** No longer weaker than S7 canon D23. |
| **CC-S13** (challenge session binding) | D11 binds a session / internal-channel continuation secret created at `begin`, required at `finish`; `CeremonyChallenge.session_binding_hash` / `internal_channel_binding_hash`; RED 57, 64. | **Folded.** |
| **CC-S14** (`constant_zero`) | D10 — constant-zero forces health `degraded` + `clone_detection_state="counter_unavailable"` + an unavoidable signing-text warning; RED 76. | **Folded.** The policy RED 76 referenced now exists. |
| **CC-S15** (D4 audit branch) | D4 — a failed license/security/dependency/API audit blocks implementation and returns the decision to spec review; `fido2` named as the explicit fallback; RED 23. | **Folded.** |
| **CC-S16** (`degraded` friction floor) | D16 — every guarded signing statement in `degraded` carries an unavoidable "no confirmed backup security key" line; RED 109. | **Folded.** Friction moved into the signed text. |
| **CC-S17** (L8 framing / numbering) | D15 header "**Proposed** L8 Resolution ..."; Named Limitations now lists L8 (inherited, retirement conditional) and L9 (marked "Proposed new canonical limitation"). | **Folded.** |
| Load-bearing minors | Anti-self-assembly rule now numbered RED 83; `bootstrap_state` enum restored (D2); Honesty Banner names the bootstrap token; fresh-install de-conflated from recovery (`bootstrap_state:"absent"`, "distinct from `manual_recovery_required`"); 64 KiB body bound (D7); restore-vs-validly-empty-registry resolved by anchoring closure to `bootstrap_closed_at`. | **Folded.** |

## Drift check

- **No weakening.** v2 keeps everything v1 had that the council verified sound —
  the canonical `S7AuthorizationArtifact` (no phantom type), the full D12
  binding (now *extended* with session/channel/UV fields, not reduced), the
  single-producer topology (now *hardened* with the internal channel),
  `not_determined` fail-closed, the "registered WebAuthn security key" humility,
  the RED-first contract. The data models are extended, not replaced.
- **No overclaim — several removed.** The "L8 Resolution" header became "Proposed
  L8 Resolution"; the record-hash "detection" claim is honestly scoped to
  accidental corruption with the external-root caveat; the fresh-install
  `manual_recovery_required: true` conflation is gone (now `bootstrap_state:
  "absent"`); D2's over-reaching operator/cockpit claim became the honestly
  narrowed enforceable claim. v2 is honestly labelled "SPEC DRAFT v2 ONLY ... not
  canonical law."
- **No new gap.** Every v2 addition is responsive to a council finding. The D6
  internal-channel "reviewed equivalent" lock is decision-oriented latitude with
  a stated required property ("proves the caller is the cockpit service, not an
  arbitrary local process") and RED-pinned behavior (RED 29–32) — not a hole. The
  D2 honest narrowing names its residual (an operator with Rohit's full OS
  account) as inherited S7 L1 — that is the honest floor and the
  council-sanctioned CC-S1 fix, not a fresh gap.
- **No diagnostic re-opening.** No ratified diagnostic-v2 decision (D1–D17) was
  reversed; the fold is additive refinement.
- **Over-call respected.** The council doc did not carry Body-Coherence's F-2 (it
  wrongly claimed S7 has no L6). v2's Named Limitations correctly keeps L6 as
  "Inherited from S7" — the fold acted on the corrected finding set, not the
  over-call.
- **RED contract.** Firsthand-counted: 115 numbered tests, the nine sections sum
  to 115, sequential 1–115, no gaps. The council's required new tests are present
  — concurrent first-registration (12), internal channel / originless `curl`
  (29–32), CI isolation (53–54), session binding (57), UV presence-only rejection
  (65), artifact substitution / `grant_source` / `ceremony_kind` / no-self-assembly
  (80–83), `unavailable` blocks + voice-seat finish recheck (87, 89), D23
  escalate-or-block (93), positive `/apply_dream` execute-after-consume (98–99).

## Recommended tightenings — for canonicalization, not second-fold blockers

- **T-1.** D5 substantively defends the single-flag staging policy ("This is
  deliberate ..."), but the explicit one-sentence acknowledgement Body-Coherence
  F-1 asked for — that a staged registration-before-authorization enable was
  *considered and rejected, and why* — is still not on the page. The council
  rated this a minor with a role-split (Outside-View and Logical/veto read it as
  adequately handled); it is a one-line canonicalization-stage polish item.
- **T-2.** CC-S9's record-hash limb was resolved honestly by downgrading the
  detection claim (D8). The audit JSONL is still `0600` with no append-only or
  hash-chain property, while D16's `both_keys_lost` / clone-suspected runbook
  instruction is "preserve evidence." For S7.1 the honest downgrade is acceptable
  and not a blocker; canonicalization should ensure the runbook and D16 do not
  lean on the audit log as *tamper-proof* evidence, and a future slice should
  give the audit log an append-only or external-chain property if it is to carry
  forensic weight.

Both are one-line items for the canonicalization draft. Neither blocks the
second-fold: the substance of every blocker and major is folded.

## Verdict and what's next

**RATIFY.** Spec v2 faithfully folds every Claude council blocker and major, the
veto lifts, and the fold introduced no drift. v2 is ready to proceed.

Ladder:

1. Claude covenant council on the spec — done; REVISE, VETO.
2. Codex engineering panel on the spec — done; REVISE (operator's lane).
3. Fold both lanes into spec v2 — done (`690e765`).
4. **Both-lane second-fold — Claude lane: this document, RATIFY (veto lifts).**
   The Codex engineering second-fold is the operator's parallel lane; the spec
   advances when both second-folds ratify.
5. Canonicalize the S7.1 spec — and, per D17, write L8/L9 into S7 `spec.md`,
   ADR 0039, and BAD Decision 34.
6. Faithfulness check.
7. Cooling-off — owner discipline; planning and implementation do not share a
   day; a waiver is the owner's alone to grant, per-slice, residual named.
8. RED-first implementation, both-lane post-implementation verification, push.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. Spec v2 was read in full
from a fresh read of the committed text (`690e765`); each Claude council finding
was verified against v2's actual text, the RED contract firsthand-counted, and
the fold drift-checked against v1. No `*codex-panel*` file was read — the Claude
lane second-folds blind to the Codex lane; the lanes second-fold separately.*
