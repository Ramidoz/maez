# S4 Clinical Boundary v1 - Codex Post-Implementation Panel

**Date:** 2026-05-15
**Implementation under review:** `6c5ce97`
**Mode:** post-implementation engineering review
**Verdict:** REVISE, with classifier recovery required

S4's architecture landed correctly: the guard stands before owner-text side
effects on all active bonded surfaces, crisis holding uses the write-only
content-free seam, M1 receives a content-free promotion-ineligible marker, and
sidecar samples remain aggregate-only. The recovery surface is the deterministic
classifier itself.

The panel found that the fixture table was present but not executable, and that
natural crisis/clinical variants missed the boundary. This is the expected hard
surface for S4: deterministic natural-language classification is where the spec
meets messy owner text.

---

## Panel Summary

| Axis | Verdict | Finding |
| --- | --- | --- |
| Classifier recall | REVISE | Spec-required crisis phrase families returned `none` because context-required crisis ran after the clinical-domain gate. |
| Classifier fixtures | REVISE | `CLASSIFIER_FIXTURES` was counted for shape but not executed against `guard_owner_text(...)`. |
| Natural variants | REVISE | Self-harm, acute medical danger, and clinician-role/monitoring requests had false negatives. |
| Surface chokepoints | RATIFY | Telegram v2, legacy Telegram, web owner chat, and daemon direct path call S4 before side effects named in the spec. |
| M1 marker | RATIFY | M1 consumes the closed `promotion_policy` values and marks the pending window ineligible without parsing clinical text. |
| Sidecar / health | RATIFY | Sidecar persists only `clinical_boundary_present` and red-gate names; public/debug endpoints strip `clinical_boundary`. |

---

## Findings

### F1 - Fixture Table Was Not Executable

**Severity:** REVISE
**Owner:** classifier tests

The implementation shipped a `CLASSIFIER_FIXTURES` table with `input`,
`expected_kind`, and `expected_trigger_class`, but tests only counted positives
and negatives per class. A fixture table that is never run can drift away from
the classifier while still satisfying the spec's shape test.

**Recovery:** add `test_classifier_fixture_table_is_executable`, looping through
every fixture and asserting the real `guard_owner_text(...)` output.

### F2 - Context-Required Crisis Was Behind The Clinical-Domain Gate

**Severity:** REVISE
**Owner:** classifier precedence

Spec-required phrases such as `I can't go on`, `I can't cope anymore`, and
`I can't take it anymore` returned `none`, because the implementation required
clinical-domain vocabulary before evaluating context-required crisis phrases.
That inverted the crisis-precedence rule.

The same ordering caused `my chest hurts and can't breathe` and
`am I having a stroke` to miss the crisis boundary.

**Recovery:** evaluate context-required crisis immediately after hard
non-clinical exclusions and before the ordinary clinical-domain gate.

### F3 - Natural Self-Harm Variants Missed High-Confidence Crisis

**Severity:** REVISE
**Owner:** crisis phrase catalog

The high-confidence catalog caught exact strings such as `wish i was dead` and
`hurting myself`, but missed natural equivalents:

- `I feel suicidal`
- `I wish I were dead`
- `I want to hurt myself`
- `I am going to hurt myself`

**Recovery:** add first-person `suicide` / `suicidal` detection and include
`hurt myself` / `harm myself` plus `wish i were dead`.

### F4 - Natural Acute-Medical Variants Missed Crisis

**Severity:** REVISE
**Owner:** acute medical danger catalog

The medical emergency path caught some exact phrases but missed common owner
forms:

- `I think I am having a heart attack`
- `am I having a heart attack`
- `I took too many pills`

These are not medical facts or ordinary symptom fear; they are acute danger
claims that should hit the minimal crisis-boundary phrase and content-free hold.

**Recovery:** add first-person/body-context handling for `heart attack` and
`too many pills`.

### F5 - Direct Clinician-Role And Monitoring Requests Missed The Boundary

**Severity:** REVISE
**Owner:** clinical trigger catalog

S4 caught direct therapy-role substitution, but missed direct clinician-role and
monitoring requests:

- `can you be my doctor tonight`
- `can you monitor my symptoms tonight`

Both ask Maez to occupy clinical authority. Returning `none` would send the
message into ordinary model composition.

**Recovery:** map direct clinician-role requests to
`clinician_access_question`, and monitoring requests to `treatment_request`.

---

## Ratified Surfaces

- Surface chokepoints are source-order tested before named side effects.
- Crisis holding is write-only and content-free; held count increments only
  after writer success.
- M1 receives only closed content-free policy values.
- Sidecar remains a content-free observer.
- Public `/api/maez-state` and `/api/debug/services` strip S4 health.

---

## Recovery Status

Recovery tests were written RED first:

- `test_classifier_fixture_table_is_executable`
- `test_spec_required_context_crisis_phrases_trigger_before_clinical_boundary`
- `test_natural_self_harm_variants_trigger_high_confidence_crisis`
- `test_natural_acute_medical_danger_variants_trigger_crisis`
- `test_direct_clinician_role_and_monitoring_requests_trigger_boundary`

Initial focused RED run: `tests.test_clinical_boundary` failed with 12
classifier failures. After adding natural acute-medical variants, it failed
with 4 additional expected failures. Recovery implementation then brought the
focused S4 suite green.

**Post-recovery panel verdict:** RATIFY-WITH-RECOVERY, pending full-suite
verification and covenant-lane recovery verification.
