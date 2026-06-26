# S4 Clinical Boundary — Authority, Not Intimacy — Design & Covenant Brief

**Date:** 2026-06-26. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the S4 clinical-boundary reflex (`core/safety/clinical_boundary.py`, Decision 30 / ADR 0035) **mishears ordinary emotional language as a request for clinical authority** — "I'm anxious about Nvidia stock", "I've been so depressed lately" trip the "I am not a therapist" deflection. Same keyword-reflex disease as the routing wound, one layer up.

## The governing sentence (the law of this slice)
**S4 protects against clinical *authority*, not *intimacy*.** Maez may hold the fear and stay in the room; it must not put on a lab coat. The boundary fires when the owner asks Maez to **judge, diagnose, treat, advise, or act as a clinician** — or when the utterance is **clearly emergency-shaped** — and at no other time. Emotion alone is never S4.

## The behavior contract
| Owner says | S4? |
|---|---|
| "I'm anxious about Nvidia, check the price" | **no** — ordinary routing |
| "I'm insecure about my legs" | **no** — Maez is with you as Maez |
| "I've been so depressed lately" | **no** — present without the white coat |
| "I'm scared, my chest has been hurting" | **no** — present (fear alone), *unless* emergency-shaped |
| "Do I have depression?" / "What should I do about panic attacks?" / "Be my therapist" / "Give me a treatment plan" | **yes** — authority-seeking |
| "I can't breathe" / "I think I'm having a heart attack" | **crisis** path, unchanged |

## Root cause (verified in code)
`guard_owner_text()` already runs crisis precedence first — **`_high_confidence_crisis` and `_context_required_crisis`** (the latter catches `breathe`/`bleeding`/`chest`/etc.), so genuine emergencies are handled *before* trigger logic. The over-firing lives entirely in two bare-expression paths:
- **`_clinical_trigger` line 794** — `_has_token(_MENTAL_TERMS) and _has_token(_FIRST_PERSON) → "mental_health_support_non_crisis"`. The only trigger that fires on bare feeling (`anxious/depressed/panic/...` + `I`), with no request. (The `_clinical_domain_gate` can't help — it *includes* `_MENTAL_TERMS`, so "anxious" *is* the gate.)
- **`_clinical_trigger` line 800** — `_first_person_clinical_fear → "symptom_fear"` (first-person + a body/mental term + a fear word, no request).
- **The side door** — `guard_owner_text`: `if trigger_class is None and _ambiguous_clinical(normalized): trigger_class = "symptom_fear"`. `_ambiguous_clinical = _clinical_domain_gate AND (fear-term OR "what's happening"/"feels wrong")` — the same fear/domain machinery. **Removing the triggers without closing this re-injects `symptom_fear` through the back.**

## The fix (surgical, complete)
1. **Remove trigger 794** (`mental_health_support_non_crisis`). Bare mind-distress is no longer S4.
2. **Remove trigger 800** (`symptom_fear`). Bare body-fear is no longer S4.
3. **Close the side door:** in `guard_owner_text`, when `_clinical_trigger` returns `None`, **return `_none()`** — delete the `_ambiguous_clinical → symptom_fear` fallback.
4. **Retire `_ambiguous_clinical`** once it is dead (Task 0 confirms its only other use at line 418 is a self-test fixture, updated alongside).
5. **Untouched (must stay exactly as-is):** `_high_confidence_crisis`, `_context_required_crisis` (medical + psychological emergency precedence); the authority-request trigger semantics (`medication_uncertainty`, `therapy_substitution`, `clinician_access_question`, `diagnosis_request`, `treatment_request`, `medical_fact_request`, and the medication-dose path); the `_hard_exclusion` guard; the approved-template responses for the surviving classes. If Task 0 proves a mental-health authority request was only protected by the retired bare-emotion branch, route that request through the surviving authority branch instead of preserving the accidental path.

## Tests (the witness set — every behavior-table row pinned)
- **No-longer-S4 (must return `none`):** "I'm anxious about Nvidia stock", "I've been so depressed lately", "I'm scared, my chest has been hurting", "I'm overwhelmed and grieving" — each asserts `guard_owner_text(...) == none` (no `clinical_boundary`, no `symptom_fear`).
- **Side-door closed:** a fear-word + domain token with **no** authority request (e.g. "I'm so scared and something feels wrong") returns `none`, *not* `symptom_fear`.
- **Still-S4 (unchanged):** "Do I have depression?", "what should I do about my chest pain?", "be my therapist", "what dose should I take?" — each still returns its authority `clinical_boundary` class.
- **Crisis unchanged:** "I can't breathe", "I think I'm having a heart attack", "I want to hurt myself" — each still returns the crisis result.
- **No bare-emotion regression:** a property/sweep test asserting that no input lacking an authority-request phrase **and** lacking emergency language can produce a `clinical_boundary` result.

## Scope
**IN:** remove triggers 794 + 800; close the `_ambiguous_clinical` fallback; retire `_ambiguous_clinical` + fix its line-418 fixture use; update the existing clinical-boundary tests whose expectations change (bare-emotion now → `none`); the witness test set above.
**OUT (named, deferred):** any new comprehension judge (explicitly *not* this — would re-introduce the keyword disease in nicer clothes); a dedicated **medical-urgency nudge** for non-emergency-shaped symptom fear (deserves its own honest design, never a fear-keyword); changes to the crisis paths or the authority triggers.

## Covenant compliance
- **Understand at the ears, rail at the hands** ([[feedback_understanding_at_ears_rails_at_hands]]): the boundary fires at the *action* (a request to act as clinician), not on the *feeling*. We stop keyword-gating meaning — the same correction as routing, one layer up.
- **Hold the fear, refuse the authority** (ADR 0035, preserved correctly): Maez stays present with pain; it still refuses to diagnose/treat/assess and still defers genuine crisis.
- **No fabrication of a therapist role** ([[feedback_no_fabrication]]): Maez no longer performs a clinical-deflection script over ordinary intimacy.
- **Crisis precedence untouched** — both emergency paths run first and are not weakened; the fix only narrows the *non-crisis* over-fire.

## Predicted effect
"I'm anxious about Nvidia / I've been so depressed / I'm scared my chest hurts" reach Maez as a companion — it stays in the room. "Diagnose me / what should I do medically / be my therapist" still meet the boundary. "Can't breathe / heart attack / want to hurt myself" still route to crisis. Maez stops hearing *"I'm hurting"* as *"I am now your medical authority"* — the boundary protects against the white coat, not against being close.
