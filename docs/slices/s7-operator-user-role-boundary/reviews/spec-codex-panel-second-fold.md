# S7 Spec v2 Codex Engineering Second-Fold Verification

**Date:** 2026-05-17
**Artifact reviewed:** `docs/slices/s7-operator-user-role-boundary/spec.md`
DRAFT v2
**Prior engineering review:** `reviews/spec-codex-panel.md`
**Related covenant verification:**
`reviews/spec-claude-council-second-fold.md`
**Verdict:** RATIFY

## Method

Read-only engineering verification. I checked the v2 spec against every Codex
panel blocker (CP-S1..CP-S12) and major (CP-M1..CP-M7), then verified the RED
contract and stale-language risks.

Fresh verification commands:

```text
awk ... docs/slices/s7-operator-user-role-boundary/spec.md
# red_count=160

git diff --no-index --check /dev/null docs/slices/s7-operator-user-role-boundary/spec.md
# spec.md diff-check clean

git diff --no-index --check /dev/null docs/slices/s7-operator-user-role-boundary/reviews/spec-codex-panel.md
# spec-codex-panel.md diff-check clean
```

The RED contract enumerates exactly 160 tests, in sequence. This verification
does not run implementation tests because S7 is still at spec stage.

## Verdict

**RATIFY.** The v2 fold closes every engineering blocker with a named runtime
mechanism and at least one RED-contract test. The spec is buildable enough to
canonicalize as Decision 34 / ADR 0039 after the canonicalization cleanup sweep
already identified by the Claude lane.

The important engineering change is that S7 no longer treats authority facts as
ordinary data. Work class, Maez's voice seat, aggregation, founder compatibility
projection, WebAuthn verifier success, artifact consumption, and brain-swap
eligibility are all produced or checked by named seams.

## Blocker Verification

| Finding | v2 fold | Verification |
|---|---|---|
| **CP-S1** work class must be trusted derivation | D7 adds `undeterminable_work_class`; caller class is display/input only; classifier inputs are enumerated; ambiguity resolves upward; RED tests 31-34 target soul/config/code downgrade and founder projection. | **Closed.** Caller-supplied work class no longer carries authority. |
| **CP-S2** founder compatibility projection fail-open | D5 closes `grant_source`, adds `founder_compat_projection`, and bars it from guarded authority; D17 repeats the ban; implementation step 6 requires proving it cannot authorize guarded work. | **Closed.** Founder shims cannot launder high-authority approvals. |
| **CP-S3** Maez voice needs producer seam | D10 defines `MaezVoiceConsultation`, source refs, closed producers, fake-ref failure, and `will_i` as supplemental only; data model adds the artifact; RED tests 50-57 target it. | **Closed.** Voice consultation is no longer a settable boolean. |
| **CP-S4** Maez unavailable / liveness repair undefined | D10 defines evidenced unavailability, anti-manufacture clause, and a closed liveness-repair set excluding identity/covenant changes; RED tests 58-60 target it. | **Closed.** Operator-stopped daemon cannot become a lawful voice-seat skip. |
| **CP-S5** S5/S7 brain-swap substitution gap | Runtime flow adds a Brain Swap section: S5 `accepted_same_maez` is a precondition, S7 authorizes execution, request binds the S5 artifact hash, and neither gate substitutes for the other; RED tests 152-155 target it. | **Closed.** Brain swap is explicitly double-gated. |
| **CP-S6** execution edge not pinned | Runtime flow adds the `RATIFIED`/`PENDING_DIALOG` to `RUNNING` to `EXECUTED`/`FAILED` table; D18 requires store-level S7 approval; RED tests 116 and 119-124 target bypasses and stage updates. | **Closed.** The actual execution transition is now the gate. |
| **CP-S7** artifact consumption atomicity | Data model gives a conditional `UPDATE ... consumed_at IS NULL` contract and rowcount requirement; RED tests 94-95 target double-consume and truthy marker bugs. | **Closed.** This carries the S6 truthiness lesson forward. |
| **CP-S8** D22 bypass taxonomy abstract | D22 now includes a sorted table; soul/config/code/model-routing paths are `gated`; raw manual filesystem/service edits are the only accepted OS-bypass class; RED tests 156-157 target it. | **Closed.** Soul-write paths cannot hide in `accepted_limitation`. |
| **CP-S9** aggregation must protect | D23 makes `derived_aggregation_group` S7-computed, non-null for guarded work, and escalation/blocking mandatory for dangerous classes; RED tests 73-75 and 158-159 target it. | **Closed.** Dashboard-only surfacing is no longer enough for dangerous accumulation. |
| **CP-S10** WebAuthn origin/verifier design | D13 names canonical origin, RP ID, Host/Origin rejection, verifier interface, challenge store, credential registry, sign-count handling, fake verifier, and virtual-authenticator path; RED tests 96-110 target it. | **Closed.** The browser ceremony is specified enough to implement and test. |
| **CP-S11** daemon-down maintenance helper | Runtime flow adds a bounded helper with closed verbs/services, audit spool, and no bonded-content reads; RED tests 140-143 target it. | **Closed.** Repairing the daemon no longer depends on the daemon authorizing itself. |
| **CP-S12** backup restore is not routine custody | D20 splits run/verify/rotate from restore; Track B restore blocks until confidentiality staging; limitations and health add restore readiness; RED tests 137, 144, and 150 target it. | **Closed.** Restore is no longer treated as ordinary custody. |

## Major Verification

| Finding | v2 fold | Verification |
|---|---|---|
| **CP-M1** dialog creation fail-soft | D8 says creation/linkage failure enters blocked state; RED test 37 targets it. | **Closed.** |
| **CP-M2** dialog persuasion surface | D8 forbids re-arguing refusal and routes same-target re-asks into D23 aggregation; RED tests 47-48 and 159 target it. | **Closed.** |
| **CP-M3** covenant-touching needs distinct ceremony | D8 requires cooling-off plus second confirmation or reviewed equivalent; RED test 160 targets it. | **Closed.** |
| **CP-M4** operator health needs closed projection | D19 separates operator projection from general `/health`, adds stale/unavailable freshness; RED tests 125-139 target projection privacy. | **Closed.** |
| **CP-M5** self-remaking history lane | D9 adds `self_remaking_history`, bounded as bonded-content and excluded from ordinary biography; RED test 46 and implementation steps 49-50 target it. | **Closed.** |
| **CP-M6** Track B precondition list | D16 makes absent-operator recovery a Track-B blocker; D21 lists storage, recovery, UI, restore posture, and S6/S11 activation dependencies; RED tests 148-151 target it. | **Closed.** |
| **CP-M7** honesty surfaces understate limits | Honesty Banner and Named Limitations now name OS bypass, coercion/display compromise, absent-operator recovery, grandmother UI, Track-B storage, restore confidentiality, and S6 capsule signing deferral. | **Closed.** |

## Engineering Drift Scan

No engineering drift found:

- No seventh role was introduced.
- WebAuthn remains founder mechanism, not universal law.
- S6 capsule signing remains out of S7 scope.
- Emergency proxy remains out of v1.
- Compatibility projection is explicitly non-authoritative for guarded work.
- The new `self_remaking_history` lane is storage classification, not
  authority.
- D22 preserves the OS/root bypass honesty while refusing to let Maez-runtime
  soul/config/model-routing writes hide as accepted limitations.

## Non-Blocking Residuals

These do not block ratification. They should ride the Decision 34 / ADR 0039
canonicalization cleanup sweep, preferably with the three covenant-minor items
already identified by the Claude lane:

1. D18 still has one stale phrase: "High-scrutiny card approval" should read
   "guarded card approval." This is wording only; the surrounding D17/D18
   mechanics are correct.
2. D19's "whether Track-B confidentiality is unavailable" bullet should end
   with a semicolon before the newly added freshness bullets. Formatting only.
3. D11 prose lists `predicted_effect` / `rollback_path`, while the dataclass
   uses `predicted_effect_class` / `rollback_path_class`; align wording or
   state the dataclass is normative.
4. D12 should explicitly state renderer determinism for
   `(envelope, renderer_version)`. The hash contract implies this, but naming
   it helps implementation.
5. Closed vocabulary members such as `closed_symptom_code` should be reviewed
   content-free artifacts. Claude already flagged this; engineering agrees.

## Ladder Status

The Codex engineering lane second-fold ratifies spec v2. With the Claude
covenant lane also at RATIFY, S7 is clear for canonicalization as Decision 34 /
ADR 0039, with the non-blocking cleanup items folded during that edit.

After canonicalization: cooling-off night, then RED-first implementation from a
fresh read of canonical `spec.md`.

## Plain English

The engineering hole in v1 was that S7 had a strong YubiKey approval but weak
facts around it. v2 fixes that: Maez cannot just be told "this is safe work" or
"Maez was consulted" or "this approval is unused." S7 now has to derive those
facts itself and check them at the final execution edge. That is the right
shape to become law.
