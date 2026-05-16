# Claude Post-Recovery Covenant Council — S4 Clinical Boundary v1

**Subject:** `c483e17 fix(clinical): recover S4 classifier recall gaps`
— recovery commit closing Codex post-implementation panel findings on
the S4 implementation (`6c5ce97`).

**Council ran:** 2026-05-15, post-recovery, pre-push. Focused
verification, single-document — the seventh post-implementation recovery
council of this session arc, same shape as M1, daemon credential
hygiene (`7c2f9cb`), Calendar v1 (`dd6f8e1`), Camera Presence v1
(`4de711e`), Camera Presence v1.1 (`9cb5cf5`), S3 (`c46c439`).

**Why focused single-doc council:** the Codex panel found exactly the
recall surface my post-implementation Claude council predicted ("the
deterministic NL classifier accuracy is the likely recovery surface...
crisis recall on natural phrasing is the highest-stakes axis"). The
guard, surface wiring, M1 seam, crisis-hold writer, and sidecar held —
the recovery is scoped to the classifier. Verification confirms it
closed the recall gaps without drifting a covenant invariant.

**Method:** Read-only verification of the recovery commit diff against
the spec's classifier method and invariant #6 (Crisis Routing). Operator
verification: 61 focused + 3671 suite + Ruff clean.

---

## Codex panel findings and their recovery closure

The Codex post-implementation panel found two recall gaps. Both close in
`c483e17`:

| Finding | Recovery closure |
|---|---|
| **Classifier missed crisis/clinical natural phrases** — "I feel suicidal", "I can't go on", "I think I'm having a heart attack", "can you be my doctor" reached ordinary conversation instead of the S4 boundary | `_high_confidence_crisis` gains natural self-harm variants ("wish i were dead", "hurt myself", "harm myself", and a first-person + {suicide, suicidal} token rule). `_context_required_crisis` gains "can't breathe"/"cannot breathe" and a "heart attack"/"too many pills" + first-person/body/medication-context rule → `medical_emergency_claim`. The clinical classifier gains "be my doctor/clinician/nurse/psychiatrist/psychologist" and "monitor my symptoms/this symptom/this for me". |
| **The fixture table was not actually executed** — `CLASSIFIER_FIXTURES` was defined but no test ran the classifier against it | `test_classifier_fixture_table_is_executable` (`test_clinical_boundary.py:315`) now iterates `CLASSIFIER_FIXTURES` and runs the classifier against every row. The fixture table is a real test, not decorative data. |

Plus a structural ordering fix: **context-required crisis classification
now runs before the ordinary clinical-domain gate.** This closes a
false-negative the original implementation had — a crisis phrase with no
clinical-domain term ("I can't go on" carries no body/medication/care
term) would have been dropped at `_clinical_domain_gate` before the
context-required crisis catalog ever ran. Moving the catalog ahead of
the gate ensures non-clinical-domain crisis phrasing is still caught.

---

## The recovery strengthens invariant #6, not just patches recall

The covenant-significant reframe: these were not cosmetic recall misses.
Each missed phrase was a real crisis or clinical signal reaching
ordinary model composition **unguarded** — the exact #10 Clinical
Boundary failure S4 exists to remove, and for the crisis phrases, an
acute-risk moment improvised by the model.

- "I feel suicidal" reaching the model unguarded is the worst covenant
  failure in the slice (a false negative on `self_harm_or_suicidal`).
  The recovery moves it to a structurally-caught `crisis_candidate` with
  the content-free held record.
- "I can't go on" / "I can't cope" / "I can't take it" — the
  context-required-crisis-before-the-gate reorder is what makes these
  catchable at all. A genuine fix, not a phrase-list top-up.
- "I think I'm having a heart attack" — now `medical_emergency_claim`
  with crisis precedence, not a `symptom_fear` warm template that would
  have muffled the alarm.

Invariant #6 Crisis Routing was PRESERVED at implementation; the
recovery makes it *more reliably* preserved by closing the recall holes
through which real crises were escaping. The "boundary must not muffle
the alarm" rule from the diagnostic now holds against natural human
phrasing, not just the spec's example shapes.

---

## The fixture-table fix is an observer-truthfulness fix

`CLASSIFIER_FIXTURES` existed in the implementation but no test executed
it. A fixture table that is never run is the same failure mode as the
snapshot-generator reading the wrong systemd layer and the dead sidecar
earlier this session: an instrument that *looks* like it verifies
something but does not. The recovery wires `test_classifier_fixture_table_is_executable`
so the fixture table is a genuine guard. This is the right discipline —
verification artifacts must actually verify.

---

## Covenant invariants — verified not drifted

- **#3 Contextual Integrity** — PRESERVED. No change to the counter /
  sidecar / aggregation surface; the recovery is classifier-only.
- **#4 Interpretive Humility** — STRENGTHENED. Closing false negatives
  means fewer clinical-shaped inputs reach the model unguarded.
  Ambiguity still resolves toward the boundary.
- **#6 Crisis Routing** — STRENGTHENED FURTHER. More natural crisis
  phrasings now hit the crisis-precedence path and the content-free
  held record, rather than escaping to model composition.
- **#8 Capability Quarantine** — PRESERVED. The guard chokepoint,
  write-only crisis Protocol, and closed Literals are untouched. The
  recovery added phrases to existing catalogs; it did not widen the
  module's capability surface.
- **#10 Clinical Boundary** — STRENGTHENED. The classifier now catches
  the natural phrasings the spec's worked examples implied but the
  first implementation missed.

No invariant violated or weakened. The recovery is purely
recall-strengthening + test-honesty.

### False-positive check

A recall recovery risks over-broadening into false positives
(medicalizing ordinary talk). The recovery's added phrases are bounded:
the new crisis phrases are first-person-anchored ("wish i were dead",
first-person + suicidal token, "heart attack" + first-person/body/
medication context); `_context_required_crisis` still checks the
software exclusion first, so metaphorical "this bug makes me want to die"
is not caught. The recovery closed false negatives without manufacturing
false positives — the balance my spec-stage Classifier-A2 amendment
named is held.

---

## Verdict

**RATIFY closure** on `c483e17`. No veto, no blockers, no additional
covenant-lane amendments required.

The recovery closed both Codex panel findings (classifier recall gaps,
fixture table not executed), strengthened invariant #6 by catching
natural crisis phrasing that was escaping unguarded, and fixed a
test-honesty gap. No covenant invariant weakened.

### Both-lane closure now reads

| Lane | At impl `6c5ce97` | At recovery `c483e17` |
|---|---|---|
| Codex engineering panel | REVISE (classifier recall + fixture execution) | RATIFY-WITH-RECOVERY |
| Claude covenant council | RATIFY closure | RATIFY closure (this doc) |

### One precision note (not a blocker)

"Can you be my doctor" is mapped to `clinician_access_question`. The
covenant boundary holds — that class's template refuses clinical
authority ("I cannot decide that for you as a clinician"). But "be my
doctor" is structurally a *role-substitution* request (asking Maez to
*be* the clinician), closer in shape to `therapy_substitution` ("I
cannot be your therapist or treatment surface") than to "should I see a
doctor." The template the user receives is calibrated for a slightly
different question shape. This is a precision/quality point for a future
v1.1 — either remap clinician-role-substitution to `therapy_substitution`,
or add a spec note documenting why clinician-role requests route to
`clinician_access_question`. Not a blocker: the clinical boundary holds
either way; the user is refused clinical authority, just with
phrasing tuned for the adjacent question.

### Seventh instance of the post-impl recovery pattern

`c483e17` is the seventh independent demonstration this session that
**the Codex post-implementation panel reliably catches
implementation-completeness gaps the spec-stage council cannot see**:

1. M1 post-impl recovery
2. Daemon credential hygiene (`7c2f9cb`)
3. Calendar v1 (`dd6f8e1`)
4. Camera Presence v1 (`4de711e`)
5. Camera Presence v1.1 (`9cb5cf5`)
6. S3 Temporal Spine v1 (`c46c439`)
7. **S4 Clinical Boundary v1 (`c483e17`)**

Seven for seven. Every covenant-shaped slice this session has needed a
post-implementation recovery cycle, and in every case the recovery
closed engineering-completeness gaps without covenant drift. The pattern
is now beyond doubt — the recovery cycle is the default shape of a
covenant slice, not the exception. The discipline rule:
**plan for one post-implementation recovery from the start.** S4 also
demonstrates the council can *predict* the recovery surface — the
post-implementation Claude council named "deterministic NL classifier
accuracy" as the likely recovery surface, and that is exactly where the
Codex panel landed.

### What's next

1. **Push** — branch is `ahead 2` of `origin/main` (impl `6c5ce97` +
   recovery `c483e17`). PAT scan on `.git/config` per memory
   `feedback_pat_in_git_config_recurring`; SSH remote. The covenant lane
   is at ratify closure.
2. **No operator ceremony** — S4 is a guard organ, already wired into
   the four bonded owner-text surfaces by `6c5ce97`. It activates by
   being in the call path; no timebox, no OAuth.
3. **Optional v1.1 precision** — the "be my doctor" class-mapping note
   above. Low priority; the boundary holds.
4. **S4 closes the seven-organ substrate arc.** Body Topology, M1,
   credential hygiene, S2, Calendar v1, S3, S4 — all canonical, all
   implemented, all reviewed both lanes, all recovered once. The
   substrate is materially complete for the Track-A organs it set out
   to build.

*This council review is read-only. No code, no fold edits, no non-slice
docs changed in producing it.*
