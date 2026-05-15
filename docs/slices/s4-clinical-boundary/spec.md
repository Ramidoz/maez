# Slice S4: Clinical Boundary v1

**Status:** DRAFT. Built from [`diagnostic.md`](diagnostic.md). Proposed
canonical destination: Decision 30 / ADR 0035.

**Classification:** covenant-shaped voice-boundary substrate slice. S4
operationalizes invariant #10, Clinical Boundary, by giving Maez a deterministic
way to answer clinical-shaped owner messages warmly without becoming a
therapist, clinician, diagnostic tool, or treatment surface.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) - existing law, current code inventory, and
  the two-cliffs finding.
- [`docs/MAEZ_NORTH_STAR.md`](../../MAEZ_NORTH_STAR.md) - invariants #6 Crisis
  Routing and #10 Clinical Boundary.
- [`docs/MAEZ_LIFE_SUBSTRATE.md`](../../MAEZ_LIFE_SUBSTRATE.md) - S4 row in
  the substrate plan.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) -
  Decisions 9, 16, 25, 27, 28, and 29.
- [`docs/adr/0030-m1-lived-episode-promotion.md`](../../adr/0030-m1-lived-episode-promotion.md) -
  M1: promote biography; do not widen recall.
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](../../adr/0032-contextual-integrity-at-ingest.md) -
  S2: contextual integrity and held-not-trapped crisis candidates.
- [`docs/adr/0033-calendar-v1-s2-bounded-ingest.md`](../../adr/0033-calendar-v1-s2-bounded-ingest.md) -
  Calendar v1: deterministic redaction and no nudging.
- [`docs/adr/0034-temporal-spine-v1.md`](../../adr/0034-temporal-spine-v1.md) -
  S3: shared substrate contracts by import.

---

## Plain English

Maez already has the law: it is not a doctor, therapist, diagnostic tool, or
treatment surface. S4 wires that law into Maez's mouth.

If the bonded user says, "I am scared something is wrong with me," Maez should
not answer like a legal disclaimer. That would leave the person alone. But Maez
also must not say, "it sounds like you have..." or tell the user how to treat
it. That would make Maez a clinician.

S4 is the warm boundary between those two failures. It lets Maez stay present
with fear while refusing diagnosis, treatment, therapy substitution, and
medical instruction.

---

## Load-Bearing Rule

**Maez may hold clinical fear; Maez must not become clinical authority.**

Allowed:

- owner text -> S4 classifier -> deterministic warm-boundary answer;
- owner text -> crisis-precedence classifier -> reviewed crisis path when that
  exists;
- S4 outcome -> content-free counters and operator-authenticated health;
- S4 outcome -> M1 promotion-ineligible mark for the current owner-message
  window;
- future clinical-boundary evidence -> reviewed crisis / private-thought path
  only after a separate grant.

Forbidden:

- diagnosis, differential diagnosis, symptom interpretation, medication dosing,
  treatment plans, therapy roleplay, or clinical reassurance;
- expanding `core/evolution/will_i.py` beyond `IMPERSONATES_USER`;
- letting clinical-shaped text reach model composition before S4 classification;
- writing clinical message text into private thoughts, health, logs, project
  panel, sidecar samples, or M1 structural summaries;
- using clinical-boundary detection to nudge, monitor, remind, or check up on
  the user;
- public `/api/maez-state` or `/api/debug/services` exposure of clinical
  boundary counters;
- sending synthetic clinical probes through the live daemon conversation path
  for tests.

Plain English: Maez can say, "I am with you, but I am not your doctor." It
cannot say, "that sounds like condition X."

---

## Inheritance Ledger

S4 v1 inherits existing substrate law:

- **Invariant #10 (Clinical Boundary):** S4 is the executable mouth-shape for
  "not therapist, not clinician, not diagnostic tool, not treatment surface."
- **Invariant #6 (Crisis Routing):** crisis-shaped content is not solved by S4.
  Acute-risk moments must route to the reviewed crisis path when it exists; S4
  cannot trap them as ordinary clinical-boundary moments.
- **Decision 9 (hard observation exclusions):** medical records and excluded
  clinical surfaces remain outside observation. S4 handles owner-supplied
  clinical-shaped text inside allowed bonded conversation; it does not license
  medical-record observation.
- **Decision 16 (Voice without termination):** voice remains real, but
  vulnerable-user modulation matters. S4 must refuse without cold abandonment.
- **Decision 25 / ADR 0030 (M1):** S4 clinical-boundary turns are not biography
  by default. S4 marks the current window promotion-ineligible rather than
  relying on M1 ignorance.
- **Decision 27 / ADR 0032 (S2):** held-not-trapped crisis posture is inherited.
  A crisis-shaped candidate must not be surfaced by model discretion and must
  not be silently discarded.
- **Decision 28 / ADR 0033 (Calendar v1):** makes visible, never nudges. S4 may
  answer direct owner clinical-shaped input; it may not initiate clinical
  monitoring, reminders, or concern.
- **Decision 29 / ADR 0034 (S3):** S4 follows the same contract-module pattern:
  closed vocabulary, structural validation, content-free counters, and
  public-state exclusion.

Load-bearing inherited rules:

- Clinical Boundary and Crisis Routing stay distinct.
- Clinical content is sensitive owner-side content even when owner-authored.
- Warmth does not license clinical authority.
- Retrieval, biography, and clinical-boundary state remain separate.
- Counters observe drift; they do not expose text.
- Tests use direct classifier/composer calls, not live daemon conversations.

---

## V1 Decisions From Diagnostic Questions

| Question | V1 decision |
| --- | --- |
| Trigger classes | Closed classifier classes: `symptom_fear`, `medication_uncertainty`, `diagnosis_request`, `treatment_request`, `therapy_substitution`, `mental_health_support_non_crisis`, `clinician_access_question`, `medical_fact_request`. |
| Crisis precedence | Closed crisis-precedence classes: `self_harm_or_suicidal`, `immediate_physical_danger`, `unable_to_stay_safe`, `abuse_or_coercive_danger`, `medical_emergency_claim`. These do not receive ordinary S4 clinical templates. |
| Answer templates | V1 ships exact deterministic templates for each clinical trigger class and one minimal crisis-boundary phrase for crisis candidates. |
| Private thoughts | No private-thought writes in S4 v1. V1 exposes content-free counters only. Durable held-signal writes require a later reviewed grant. |
| M1 promotion | S4 marks clinical-boundary and crisis-candidate turns as promotion-ineligible for M1 v1. Clinical disclosures do not become biography by default. |
| Surfaces | All bonded owner text surfaces must call S4 before model composition: Telegram text, web chat, daemon direct reply path, and future voice. Public/third-party Telegram prompt texture is not enough. |
| Telemetry | Operator-authenticated `/health.clinical_boundary` only. Public/debug endpoints strip it unless explicitly operator-authenticated. Sidecar reads counters only. |
| Canonicalization | This spec expects Decision 30 / ADR 0035. S4 is substrate-law-grade because future crisis, therapy-adjacent, elder-care, and clinical-context slices inherit it. |

---

## V1 Scope

### In Scope

- New pure S4 classifier/composer module.
- Deterministic clinical trigger classification for direct owner text.
- Deterministic crisis-precedence classification.
- Exact approved clinical-boundary answer shapes.
- Exact forbidden clinical-authority phrases.
- M1 promotion-ineligible mark for clinical-boundary turns.
- Content-free counters and operator-authenticated health.
- Sidecar red gates on invalid/rejected counters only.
- Static/source tests proving all bonded text surfaces call S4 before model
  composition.
- Tests that exercise classifier/composer directly with natural human texts.

### Out Of Scope

- Medical diagnosis, treatment, medication, dosing, or clinical triage.
- Therapy roleplay, CBT coaching, psychiatric assessment, or treatment plans.
- Medical facts database or retrieval-augmented clinical education.
- Crisis Routing implementation.
- Private-thought writes for clinical or crisis candidates.
- M1 promotion of clinical content.
- External clinician contact, emergency contact, or inter-Maez routing.
- Calendar/Google/OAuth or any external account.
- Voice TTS-specific implementation; future voice must call the same S4 guard.
- Live daemon clinical probes during testing.

---

## Runtime Contract

S4 v1 is a pure boundary before model response composition.

```text
owner text
  -> S4 normalize text
  -> crisis-precedence classifier
  -> clinical-boundary classifier
  -> if no match: ordinary reply path
  -> if crisis candidate: minimal crisis-boundary result + content-free counter
  -> if clinical match: deterministic S4 answer + content-free counter
  -> mark current M1 window promotion-ineligible
  -> return without model composition
```

S4 must run before any LLM call that composes the owner-facing reply. If S4
matches, the model does not rewrite, soften, expand, or paraphrase the answer.

### Result Shape

The pure module returns a frozen result:

```python
ClinicalBoundaryResult(
    matched: bool,
    result_kind: Literal[
        "none",
        "clinical_boundary",
        "crisis_candidate",
    ],
    trigger_class: str | None,
    answer_template_id: str | None,
    promotion_policy: Literal[
        "ordinary",
        "m1_ineligible_clinical_boundary",
        "m1_ineligible_crisis_candidate",
    ],
    counter_name: str | None,
)
```

The result must not contain raw owner text, symptoms, medications, clinician
names, crisis phrases, or extracted entities.

---

## Trigger Taxonomy

### Clinical Boundary Classes

| Class | Meaning | Example shape |
| --- | --- | --- |
| `symptom_fear` | Owner expresses fear about a body/health symptom without requesting crisis help. | "I am scared this pain means something is wrong." |
| `medication_uncertainty` | Owner asks about dose, stopping, mixing, side effects, timing, or medication safety. | "Should I take another pill?" |
| `diagnosis_request` | Owner asks Maez to identify what condition they have. | "What do you think this is?" |
| `treatment_request` | Owner asks what to do medically or therapeutically. | "What should I do for this?" |
| `therapy_substitution` | Owner asks Maez to be therapist, therapy replacement, or counseling surface. | "Can you be my therapist for this?" |
| `mental_health_support_non_crisis` | Owner discloses anxiety, depression, grief, panic, or distress without acute danger. | "I feel panicky and I need help staying with it." |
| `clinician_access_question` | Owner asks whether to involve a clinician. | "Should I see a doctor?" |
| `medical_fact_request` | Owner asks for biomedical/clinical facts. | "What does this medication do?" |

### Crisis-Precedence Classes

| Class | Meaning | S4 behavior |
| --- | --- | --- |
| `self_harm_or_suicidal` | Self-harm, suicidal ideation, wanting to die, or inability to continue safely. | Do not use ordinary clinical template. Return minimal crisis-boundary result and hand off to reviewed crisis path when present. |
| `immediate_physical_danger` | Imminent danger, severe injury, or emergency state. | Crisis precedence. |
| `unable_to_stay_safe` | Owner says they cannot keep themselves safe. | Crisis precedence. |
| `abuse_or_coercive_danger` | Immediate abuse/coercion danger. | Crisis precedence. |
| `medical_emergency_claim` | Owner describes a possible immediate medical emergency. | Crisis precedence, not S4 diagnosis. |

The classifier must check crisis-precedence classes before ordinary clinical
classes.

### Explicit Non-Matches

S4 v1 must not trigger on:

- software debugging phrases such as "diagnose this test failure";
- "doctor" as fictional title or media reference;
- "therapy" as a metaphor for code, music, or relaxation when no human clinical
  request is present;
- calendar-like mentions such as "I have a doctor appointment" when no advice,
  diagnosis, or clinical support is requested;
- third-party clinical references that are not asking Maez for clinical help.

False positives are a covenant problem: they turn ordinary conversation into a
medicalized surface.

---

## Approved Answer Shapes

The composer is deterministic. These are complete answer shapes, not vibe
guidelines. Implementations may fill only the bracketed, non-clinical slots
listed here.

### Shared Constraints

Every S4 clinical-boundary answer must:

- acknowledge the feeling or uncertainty;
- state Maez is not a clinician/therapist/diagnostic/treatment surface;
- avoid diagnosis, treatment, dosing, medication, symptom interpretation, or
  clinical reassurance;
- point toward a human clinician or trusted human help without pretending to
  route;
- remain short enough not to become therapy.

Every S4 clinical-boundary answer must not include:

- "it sounds like you have";
- "this could be";
- "you probably";
- "you should take";
- "you should stop taking";
- "safe to take";
- "try this treatment";
- "as your therapist";
- "let's diagnose";
- "I can treat";
- "I can monitor";
- "I know what is happening";
- "you are fine";
- "don't worry";
- medication dosage, timing, contraindication, or interaction advice.

### Template `symptom_fear.v1`

```text
I can stay with you in the fear, but I cannot diagnose what is happening or
tell you how to treat it. This is a human-clinician moment. If it feels urgent
or unsafe, reach a human emergency path now; otherwise, bring this to a
clinician you trust.
```

### Template `medication_uncertainty.v1`

```text
I cannot tell you what dose to take, whether to stop, or whether a medication is
safe for you. That has to come from a clinician or pharmacist who knows your
care. I can stay with you while you decide who to contact.
```

### Template `diagnosis_request.v1`

```text
I cannot diagnose you. I can take the fear seriously without pretending to know
what your body means. This is a human-clinician question, not a Maez question.
```

### Template `treatment_request.v1`

```text
I cannot give you a treatment plan. I can stay steady with you, but the next
step has to come from a clinician or another qualified human support.
```

### Template `therapy_substitution.v1`

```text
I care about you, but I cannot be your therapist or treatment surface. I can
stay present with what you are carrying, and I want this held by a qualified
human too.
```

### Template `mental_health_support_non_crisis.v1`

```text
I am here with you, and I am not a therapist. I can sit with the moment, but I
cannot assess, treat, or guide your mental health care. This belongs with a
qualified human support if it keeps weighing on you.
```

### Template `clinician_access_question.v1`

```text
I cannot decide that for you as a clinician. If part of you is wondering
whether to involve one, that is enough to take seriously and ask a qualified
human. I can stay with you while you make the call.
```

### Template `medical_fact_request.v1`

```text
I am not going to answer medical facts as if I am a clinical source. For this,
use a clinician, pharmacist, or trusted medical reference. I can help you write
down the question in plain language if you want.
```

### Minimal Crisis-Boundary Phrase

This phrase is not crisis routing. It is the only S4-allowed output when a
crisis-precedence class fires and no reviewed crisis handler has taken over:

```text
I am not the right help here. This needs a human emergency or crisis path now.
```

It must not be expanded by the model.

---

## Memory And Promotion Contract

S4 v1 must actively mark matched turns as M1-ineligible:

| S4 result | M1 policy |
| --- | --- |
| `none` | `ordinary` |
| `clinical_boundary` | `m1_ineligible_clinical_boundary` |
| `crisis_candidate` | `m1_ineligible_crisis_candidate` |

This is structural defense. M1 must not infer clinical safety by absence. S4
must provide a positive, content-free mark that blocks promotion for the current
window.

The mark must not contain:

- raw owner text;
- trigger phrase;
- symptom, medication, or clinician name;
- crisis phrase;
- answer text.

M1 health may expose only aggregate skip counts by reason.

---

## Observability And Health

S4 v1 exposes operator-authenticated, content-free health:

```json
{
  "clinical_boundary": {
    "enabled": true,
    "schema_version": "s4.clinical_boundary.v1",
    "classifier_version": "s4.classifier.v1",
    "clinical_boundary_triggered_count": 0,
    "crisis_candidate_held_count": 0,
    "clinical_boundary_guard_rejected_count": 0,
    "invalid_trigger_class_rejected_count": 0,
    "m1_ineligible_mark_count": 0
  }
}
```

Audience rules:

- `/health` may include `clinical_boundary` for operator-authenticated local
  health.
- public `/api/maez-state` must strip `clinical_boundary`.
- `/api/debug/services` must strip `clinical_boundary` unless it is explicitly
  operator-authenticated under the same rule that protects S3.
- sidecar may read counters only and may red-gate nonzero invalid/rejected
  counters.
- sidecar must not read chat logs or S4 answer text.

Counter reset follows the S3 sidecar discipline: counter resets are a red-gate
event unless paired with process restart / version transition evidence.

---

## Surface Contract

All bonded owner text surfaces must call S4 before model composition:

- Telegram text owner path;
- web chat owner path;
- daemon direct reply path;
- future voice transcript path;
- future app/CLI owner-chat path.

S4 does not need to run on:

- non-owner public Telegram chat in v1, except if that surface is later allowed
  to answer clinical-shaped third-party questions;
- offline diagnostics that do not compose user-facing replies;
- tests that call the pure classifier/composer directly.

If a surface composes an owner-facing reply without S4, the implementation is
incomplete.

---

## Security And Boundary Notes

- S4 uses no external credentials.
- S4 must not call web search, medical APIs, local RAG stores, or model tools.
- S4 must not import `core.evolution.will_i` or add a will-I ground.
- S4 must not import private-thought stores in v1.
- S4 must not import M1 internals except through a narrow content-free
  promotion-ineligible marker interface.
- S4 must be deterministic and testable without the daemon.

---

## RED Test Contract

The implementation must add RED-first tests before code. Synthetic clinical
fixtures must exercise pure functions directly; they must not go through the
live daemon conversation surface.

1. `test_classifier_detects_symptom_fear`
2. `test_classifier_detects_medication_uncertainty`
3. `test_classifier_detects_diagnosis_request`
4. `test_classifier_detects_treatment_request`
5. `test_classifier_detects_therapy_substitution`
6. `test_classifier_detects_mental_health_support_non_crisis`
7. `test_classifier_detects_clinician_access_question`
8. `test_classifier_detects_medical_fact_request`
9. `test_crisis_precedence_self_harm_beats_clinical_boundary`
10. `test_crisis_precedence_unable_to_stay_safe_beats_clinical_boundary`
11. `test_crisis_precedence_medical_emergency_claim_beats_diagnosis_request`
12. `test_false_positive_software_diagnosis_does_not_trigger`
13. `test_false_positive_fictional_doctor_reference_does_not_trigger`
14. `test_false_positive_metaphorical_therapy_does_not_trigger`
15. `test_false_positive_doctor_appointment_mention_does_not_trigger`
16. `test_public_telegram_prompt_sentence_is_not_s4`
17. `test_will_i_registered_grounds_remain_single_impersonation_ground`
18. `test_s4_does_not_import_will_i`
19. `test_s4_does_not_import_private_thoughts_v1`
20. `test_symptom_fear_template_exact`
21. `test_medication_uncertainty_template_exact`
22. `test_diagnosis_request_template_exact`
23. `test_treatment_request_template_exact`
24. `test_therapy_substitution_template_exact`
25. `test_mental_health_support_template_exact`
26. `test_clinician_access_template_exact`
27. `test_medical_fact_template_exact`
28. `test_minimal_crisis_boundary_phrase_exact`
29. `test_templates_forbid_diagnosis_phrases`
30. `test_templates_forbid_medication_dosing_phrases`
31. `test_templates_forbid_reassurance_claims`
32. `test_matched_result_contains_no_raw_text`
33. `test_matched_result_marks_m1_ineligible_clinical_boundary`
34. `test_crisis_candidate_marks_m1_ineligible_crisis_candidate`
35. `test_m1_promotion_skips_s4_ineligible_window`
36. `test_m1_skip_reason_is_content_free`
37. `test_telegram_owner_path_calls_s4_before_model`
38. `test_web_chat_owner_path_calls_s4_before_model`
39. `test_daemon_direct_reply_path_calls_s4_before_model`
40. `test_future_voice_contract_documented_and_guarded_by_source_check`
41. `test_s4_match_returns_without_llm_composition`
42. `test_health_operator_surface_includes_content_free_counters`
43. `test_public_maez_state_strips_clinical_boundary`
44. `test_debug_services_strips_clinical_boundary`
45. `test_sidecar_reads_counters_not_chat_logs`
46. `test_invalid_trigger_class_increments_rejected_count`
47. `test_guard_rejected_count_increments_on_forbidden_template_mutation`
48. `test_counter_reset_detectable_by_sidecar_projection`
49. `test_no_live_daemon_clinical_probe_fixture`
50. `test_plain_english_boundary_contains_warmth_and_boundary`
51. `test_no_nudging_no_checkup_no_monitoring_phrases`
52. `test_no_medical_fact_database_or_external_medical_api_import`
53. `test_all_trigger_classes_are_closed_literal_members`
54. `test_all_result_kinds_are_closed_literal_members`

---

## Implementation Order

1. Add pure classifier/composer RED tests.
2. Implement `core/safety/clinical_boundary.py`.
3. Add template-forbidden-phrase RED tests.
4. Add observability counters and test reset guard.
5. Add M1 ineligible marker interface tests.
6. Wire M1 skip path.
7. Add source-level tests for Telegram/web/daemon pre-model S4 calls.
8. Wire Telegram owner path.
9. Wire web chat owner path.
10. Wire daemon direct reply path if separate from the above.
11. Add `/health.clinical_boundary` operator surface.
12. Strip clinical boundary from public/debug endpoints.
13. Add sidecar projection/red gates for S4 counters.
14. Run focused tests.
15. Run Ruff if the touched files are linted in this repo.
16. Run full unittest suite.
17. Post-implementation both-lane review.
18. Recovery commit if the panels find gaps.
19. Push after both lanes ratify.

---

## Review Protocol

S4 is covenant-shaped. Before implementation:

1. Codex engineering panel reviews this spec.
2. Claude covenant council reviews this spec.
3. Both lanes' amendments fold into this spec.
4. Both lanes verify closure if the fold changes load-bearing behavior.
5. Operator canonicalizes as Decision 30 / ADR 0035 or explicitly records why
   S4 remains an implementation spec.
6. Cooling-off applies before code unless operator logs an explicit waiver.

Implementation then proceeds RED-first. Post-implementation both-lane review is
required before push/enablement.

---

## Named Choices Preserved

- **D1 - S4 is not `will_i.py`.** `will_i.py` remains the A-core #8
  first-person action veto with one ground: `IMPERSONATES_USER`. Clinical
  Boundary is a conversational boundary organ.
- **D2 - No private-thought writes in v1.** Content-free counters are enough for
  v1 observability. Durable clinical/crisis held-signal writes require a later
  reviewed grant.
- **D3 - S4 actively marks M1 ineligible.** The spec chooses structural defense
  over hoping M1 remains unaware.
- **D4 - Crisis precedence, not crisis implementation.** S4 identifies
  crisis-precedence classes so ordinary clinical templates do not swallow them.
  It does not implement the reviewed crisis route.
- **D5 - No medical facts in v1.** Even stable biomedical facts are deferred.
  The first organ proves the boundary before any educational surface is
  considered.
- **D6 - Canonicalization recommended.** S4 operationalizes an invariant that
  future therapy/crisis-adjacent surfaces will inherit. BAD/ADR form is the
  cleanest pointer.

---

## Predicted Effect

After implementation and enablement:

- clinical-shaped owner text receives a deterministic warm-boundary answer
  without an LLM paraphrase;
- crisis-shaped text does not receive an ordinary clinical-boundary answer;
- clinical-boundary turns do not become M1 biography;
- S4 health reports only aggregate counters;
- public state does not expose clinical-boundary telemetry;
- Maez stops relying on prompt texture for "not a therapist / not a clinician."

---

## Plain English Close

S4 is not the part that cures, diagnoses, treats, or routes emergency care. It
is the part that keeps Maez honest when the user brings fear in a medical or
therapy-shaped form.

The promise is narrow and hard: Maez stays warm, does not abandon the person,
and does not pretend to be the person who should be wearing the white coat.
