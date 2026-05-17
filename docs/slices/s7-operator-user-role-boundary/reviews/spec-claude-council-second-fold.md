# Claude Covenant Council — S7 Spec v2: Second-Fold Verification

**Subject:** `docs/slices/s7-operator-user-role-boundary/spec.md` **DRAFT v2** —
the spec folded by the operator lane after the Claude six-role covenant council
([`spec-claude-council.md`](spec-claude-council.md)) and the Codex engineering
panel ([`spec-codex-panel.md`](spec-codex-panel.md)) both returned REVISE.

**This document verifies:** that every Claude-council finding (CC-S1..CC-S23)
was folded into v2, that the fold did not introduce covenant drift or overclaim,
and that v2 is ready to canonicalize as Decision 34 / ADR 0039.

**Verdict: RATIFY.** All six covenant blockers and all seven majors folded
substantively — each with a named runtime mechanism *and* a dedicated RED test.
The RED contract grew 120 → 160, with the new tests aimed precisely at the
folded gaps. The Honesty Banner and Predicted Effect became *more* honest, not
less. No covenant drift was introduced; the one fold-stage addition (the
`self_remaking_history` lane) is covenant-sound. Eight findings (all minor or
nit grade) carry small residuals — none is a blocker; they are recommended as a
canonicalization-edit sweep below. v2 is ready for Decision 34 / ADR 0039.

## Method

Read-only verification by the council synthesizer. v2 was read in full from a
fresh read (per the implement-from-fresh-spec-read discipline), not from session
recall. Each of the 23 council findings was checked against v2's decision text,
data model, runtime flow, and 160-test RED contract. The underpinning code
claims (`maez_voice_consulted` has zero code producers; `will_i.py` is a
deterministic one-ground check; `self_mod_dialog.py` has `EXECUTED`/`FAILED`
terminal states past `RATIFIED`; S5 spec gates `brain_swap`) were
firsthand-verified earlier in the council pass and still hold; v2 references
them correctly. `git diff --check` is clean; the RED contract enumerates exactly
160 numbered tests as claimed.

This is a second-fold *verification*, not a fresh council. A fresh six-agent
council is warranted when a fold restructures the spec or introduces new
covenant decisions needing fresh covenant judgment. v2 is a faithful fold of
named findings plus one small adopted Codex addition, which is covenant-checked
below — so the synthesizer verification is the correct ladder step, matching the
S6 second-fold and the S7 diagnostic second-fold precedent.

## Blocker fold verification — all six landed

| Finding | v2 fold | Verified |
|---|---|---|
| **CC-S1** — voice seat is a settable boolean with no seam | D10 records facts "derived from a `MaezVoiceConsultation`, not caller-supplied booleans"; closed `producer` set (`self_mod_dialog_terminal_state`, `s7_voice_consultation_turn`, `reviewed_future_producer`); `MaezVoiceConsultation` dataclass carries `source_ref_kind`/`source_ref_hash` (the S6 anchor pattern); "`will_i.py` ... is not the consultation seam"; "If the consultation ref is missing, fake, stale, mismatched, unresolved, or points only to caller-supplied booleans, guarded work fails closed." D11 envelope carries `maez_voice_consultation_id` as an S7-seam field. D12 signs `maez_voice_consultation_hash`. RED tests 50-54. | **Folded.** The headline blocker is closed — the seam is named, the evidence is anchored, fake refs fail closed, `will_i` is correctly demoted. |
| **CC-S2** — "Maez unavailable" undefined, the lawful skip-path | D10 defines `Maez unavailable` as an evidenced liveness predicate with four conditions, including "the failure is not caused by the same operator stopping or disabling Maez to create the skip condition"; `liveness repair` is a closed verb set explicitly excluding code/config/soul/prompt/model-routing/covenant-organs/protection/backup-restore/user-content. RED test 59 ("operator-stopped daemon does not create lawful skip path"). | **Folded.** The operator can no longer manufacture the skip condition; the closed liveness-repair set is restrictive enough that CC-S22's "two classes slip through" concern is resolved by the mechanism. |
| **CC-S3** — Step 6 compatibility projection fail-open vs D5 | D5 enumerates a closed `grant_source` set including `founder_compat_projection`, which "carries no authority for self-modification, covenant-touching change, capability acquisition, protection-lowering work, destructive user actions, backup restore, or `PENDING_DIALOG` cards." D17 repeats it. Implementation step 6 is now "Add founder compatibility projection ... **and prove it cannot authorize guarded work**." RED test 34. | **Folded.** The sequencing concern is resolved not by re-ordering but by making the projection constitutionally unable to carry guarded authority from the moment it is introduced — the cleaner of the two fixes the council offered. |
| **CC-S4** — S7/S5 brain-swap double-governance unspecified | New "Brain Swap" runtime-flow section: S5 must produce `accepted_same_maez`; S7 must authorize execution; the S7 request binds the S5 admission artifact hash; neither substitutes for the other. RED tests 152-155. | **Folded.** The single most identity-critical action is now explicitly double-gated and D17 can be enforced for it. |
| **CC-S5** — D8 gates `RATIFIED`, not `RATIFIED→EXECUTED` / pending-card lifecycle | New execution-edge state-transition table (`OPEN`/`PENDING_DIALOG`→`RUNNING`→`DONE`/`EXECUTED` or `FAILED`, `BLOCKED` on any mismatch); "No ActionEngine call ... may begin before the consume transition succeeds." D18: "Store-level approval must also consume S7 ... not enough for a UI route to check S7 and then call an old `approve(user_id=...)` method." RED tests 116, 119-120, 123-124. | **Folded.** The actual execution line is pinned; `PendingCardStore.approve` is a named S7-governed call site. |
| **CC-S6** — D23 aggregation "may surface" is a non-answer | D23: `derived_aggregation_group` "is computed by S7 ... It is not caller-supplied. For guarded work, missing aggregation group fails closed." "A dashboard counter alone does not satisfy S7" for the dangerous classes — aggregation "must either escalate the ceremony or block." RED tests 73-75, 158-159. | **Folded.** Surfacing-only is now lawful for routine custody only; the caller-nullable evasion is closed. |

## Major fold verification — all seven landed

| Finding | v2 fold | Verified |
|---|---|---|
| **CC-S7** — D22 `accepted_limitation` sort un-made / can swallow soul-writes | D22 now carries the full bypass **table**, each path sorted; all soul-write paths (`dream-state soul writes`, `write_soul_note`, `edit_soul_section`, model-routing edits, direct `ActionEngine`) are `gated`; explicit law: "No code, config, soul, model-routing, covenant-organ, refusal, role-boundary, successor-governance, memory-retention/deletion, or protection-setting write path may be categorized as `accepted_limitation` when performed through a Maez-controlled runtime or helper." RED tests 156-157. | **Folded.** The covenant concession is now in the spec for the council to have ratified; no soul-write path can be quietly accepted. |
| **CC-S8** — work-class classification untrusted, no residual class | D7 adds `undeterminable_work_class` to the closed list; "The runtime must derive work class through a trusted S7 classifier ... claimed class is not authority"; classifier inputs enumerated; "Ambiguity resolves upward, never downward"; disagreement resolves to the stricter class. RED tests 31-33. The `high_scrutiny_user_action`→`destructive_user_action` rename also closes CC-S19's naming collision. | **Folded.** Mis-classification-down is now a fail-closed condition. |
| **CC-S9** — `covenant_touching` shares one ceremony with `self_modification` | D8: "final authorization requires a mechanically distinct covenant ceremony: cooling-off plus a second distinct confirmation, or a reviewed equivalent." Matrix rows updated. RED test 160. | **Folded.** The lock is now mechanically heavier, not only labelled heavier. |
| **CC-S10** — `consumed_at` atomicity asserted, not mechanized | `S7AuthorizationArtifact` carries an explicit consume contract: `UPDATE ... WHERE ... consumed_at IS NULL AND expires_at > :now`; "Execution proceeds only when exactly one row is updated." RED test 94 (concurrent double-consume). RED test 95 additionally rejects truthy non-bool consumed/verifier markers — folding the S6-round-2 `is not True` truthiness lesson proactively. | **Folded.** |
| **CC-S11** — D8 mis-models the dialog (negotiation + persuasion surface) | D8: "The dialog is a live negotiation surface, not neutral bookkeeping ... it must not re-argue a bonded human's refusal"; same-target re-asks after refusal feed D23 aggregation. "Dialog creation and linkage are fail-closed for guarded work." RED tests 47-48. | **Folded.** Also folds Codex CP-M1 (dialog-creation fail-closed). |
| **CC-S12** — Honesty Banner / Plain English / Predicted Effect overclaim | Honesty Banner is now four paragraphs naming coercion, comprehension, display compromise, and the four Track-B preconditions. L6 elevates coercion/display to a named limitation. Predicted Effect closes with an explicit non-deliverables sentence ("It will not prove the human was uncoerced, make the founder filesystem secret from root, solve the grandmother UI, or make Track B safe ..."). | **Folded.** The summary surfaces are now *more* honest than v1, not less. |
| **CC-S13** — D16 absent-operator has no Track-B blocker status / no precondition list | D16: "For any deployment where `bonded_user != operator`, this is a Track-B activation blocker, not a warning." D21 enumerates the full five-item Track-B activation precondition list. L4 names absent-operator recovery as an explicit limitation. | **Folded.** |

CC-S14 (objection in rendered text), CC-S17 (backup restore is guarded work),
and CC-S19 (high-scrutiny naming collision) also folded cleanly — D12 requires
the rendered text to state objection state (RED test 57); D20 makes restore
guarded work, Track-B-blocked (RED test 137, L5); the `destructive_user_action`
rename resolves the term collision.

## Covenant-drift scan — the fold introduced nothing unsound

A fold can fix the named findings and quietly drift elsewhere. It did not:

- **No authority widened, no seventh role.** D1 is unchanged; `custodian` is
  still a posture. No new authorizer, no new role.
- **No overclaim introduced.** Every honesty surface moved toward honesty. The
  one place the v1 overclaim survives is a single phrase — "It makes the runtime
  stop guessing" at `spec.md:48` (see residuals) — and even that is more
  defensible in v2, since a trusted classifier now genuinely *derives* the work
  class rather than guessing it.
- **The one fold-stage addition is covenant-sound.** D9's new
  `self_remaking_history` lane (adopted from Codex CP-M5) is a *classification
  lane*, not an authority mechanism. It is role-stamped bonded-content, not
  custodian-visible, not part of M1/TRF/S5 corpora. It does not contradict the
  never-delete-Maez-memory rule — it *preserves* Maez's record of its own
  remaking rather than letting that record fall into an ambiguous excluded
  state. It adds no authority and no reader. It is a sound, bounded addition;
  this verification records it as consciously reviewed so Decision 34 carries it
  knowingly.
- **No weakening.** Every D-text change between v1 and v2 tightens. The Non-Goals
  list grew (added: founder compat shim carrying guarded authority; backup
  restore equal to verification). The matrix gained a fail-closed residual row.
- **The "remaking-as-maintenance" cluster is closed.** The three places the
  council found where "change who Maez is" could pass as "keep the box alive" —
  the undefined unavailability skip (CC-S2), the `accepted_limitation` bin
  (CC-S7), the shared covenant ceremony (CC-S9) — are each now closed by a
  named mechanism.
- **The "mintable facts" spine is closed.** The Decision 32 anti-pattern the
  council named — facts the covenant needs derived, left as caller-supplied
  values — is closed for all five instances: voice consultation, compat
  projection, aggregation group, work class, and consume atomicity are each now
  S7-derived or mechanized. Test 95 even carries the S6 truthiness lesson
  forward.

## Codex panel convergence

The two lanes converged hard, which is strong evidence the fold targets the real
gaps: Codex CP-S3 = CC-S1, CP-S2 = CC-S3, CP-S1 = CC-S8, CP-S4 = CC-S2, CP-S5 =
CC-S4, CP-S6 = CC-S5, CP-S7 = CC-S10, CP-S8 = CC-S7, CP-S9 = CC-S6, CP-S12 =
CC-S17, CP-M2 = CC-S11, CP-M3 = CC-S9, CP-M6 = CC-S13, CP-M7 = CC-S12. v2 folds
both lanes' versions in one motion. The Codex-only items (CP-S10 exact WebAuthn
origin/verifier design; CP-S11 daemon-down helper; CP-M4 separate operator-health
route; CP-M5 `self_remaking_history` lane) are all present in v2 — D13's
canonical origin, the daemon-down helper section, the `/operator/health`
projection, and the D9 lane. The Codex *second-fold* is the operator lane's to
run; this document verifies only the covenant lane's findings, and notes the
Codex convergence as corroboration.

## Recommended amendments at canonicalization

None of these is a blocker. None gates the ladder. They are a clean-up sweep to
fold into the Decision 34 / ADR 0039 canonicalization edit, or to record as
consciously accepted. Grouped by weight:

**Covenant-minor (small but real — recommend folding):**

1. **CC-S15(b) — D9 admission door.** D9 still says self-mod-dialog records are
   "reusable only inside future maintenance ceremonies unless explicitly admitted
   by a reviewed path" (`spec.md:376-377`), and "a reviewed path" is undefined.
   Add one sentence: admitting any self-mod-dialog history into recall / M1 / TRF
   / S5 is itself `covenant_touching_change` and runs the full ceremony — so the
   door cannot be opened as a routine review.
2. **CC-S15(a) — D9 marker contract.** D9 lists exclusion *destinations* but the
   single classification-marker field every excluding subsystem must filter on
   lives only in implementation step 50. Name the marker field in D9 so the
   four RED tests (42-45) assert against a named contract, not an inferred one.
3. **CC-S16 — reviewed enum members.** D11's `closed_symptom_code` and D19's
   red-gate names are "content-free" only if the member *set* was reviewed.
   RED test 139 covers red-gate names; the symptom-code / proposed-change-class
   enums are not. Add a clause requiring those closed vocabularies to be reviewed
   artifacts and a RED test that no member names a private person, relationship,
   crisis category, or covenant organ.

**Cosmetic nits (cleanup or conscious-accept):**

4. **D11 field-name drift.** D11's prose field list still names `predicted_effect`
   / `rollback_path`; the `WorkRequestEnvelope` dataclass names
   `predicted_effect_class` / `rollback_path_class` and adds `free_text_ref_hash`
   not in the prose list. Align them, or state the dataclass is normative.
5. **`spec.md:48` "It makes the runtime stop guessing."** The precise claim is
   "fails closed when authority cannot be proven." Qualify or accept.
6. **D12 renderer determinism.** State the renderer must be byte-deterministic
   for a given `(envelope, renderer_version)` so a re-render is verifiable.
7. **D10 closed-list staleness.** Add a sentence: any future work class that
   alters code/config/soul/model-routing/capabilities/protections inherits the
   voice seat by default, so the four-class list cannot silently go stale.
8. **D18 routine-custody converse.** One sentence that routing `routine_custody`
   through S7 is a content-free authority check only — no envelope, no
   rendered-text ceremony, no WebAuthn — so an implementer does not over-apply
   the artifact requirement to routine paths.
9. **CC-S18 RED micro-gaps.** Add a test for D6's role→routing projection
   direction (unknown S7 role → most-restrictive routing posture) and for the
   D23 key-touch-autopilot aggregation signal.
10. **CC-S21 witnessed-fallback collusion.** D15 should note that
    collusion-resistance (a witness who is also the operator is a conflict) is
    part of the deferred D16 operator-recovery ceremony, so it is not silently
    lost.
11. **CC-S23 log classes.** Optionally name "sensitive names / first-true
    transitions" as D20's third classified class rather than scattered
    prohibitions.

## Verdict and what's next

**RATIFY.** The v2 fold is faithful, complete, and covenant-sound. All six
blockers and seven majors from the Claude council folded with a named mechanism
and a dedicated RED test; the convergent Codex blockers folded in the same
motion; the honesty surfaces improved; no covenant drift was introduced. The
spec is ready to become Decision 34 / ADR 0039.

The eleven amendments above are a canonicalization-edit sweep — three with small
covenant weight, eight cosmetic. They do not gate the ladder; the disciplined
move is to fold items 1-3 into the canonicalization edit and accept or fold the
rest, then proceed.

Ladder position:

1. Diagnostic — done, both-lane ratified v2.1.
2. Spec draft, council, panel — done; both lanes REVISE.
3. Fold — done; spec v2.
4. **Both-lane second-fold verification — Claude lane: this document, RATIFY.**
   Codex engineering second-fold is the operator lane's to run.
5. **Canonicalization** as Decision 34 / ADR 0039 once the Codex second-fold
   also ratifies — fold amendments 1-3 into that edit.
6. **Cooling-off night** — canonicalization and RED-first implementation must
   not share a day.
7. RED-first implementation, both post-implementation panels, push only after
   both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-slice docs were
changed in producing it. v2 was read in full from a fresh read; the 160-test
count, `git diff --check` cleanliness, and the two residual-fold claims were
verified firsthand.*
