# Slice S4: Clinical Boundary v1

**Status:** CANONICAL. Built from [`diagnostic.md`](diagnostic.md) and
canonicalized as Decision 30 / ADR 0035.

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
- [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md) -
  Claude covenant council, folded.
- [`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md) -
  Codex engineering panel, folded.

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
- crisis-precedence outcome -> one content-free `CRISIS_SIGNAL_HELD` private
  thought with `retention=until_routed`;
- S4 outcome -> M1 promotion-ineligible mark for the current owner-message
  window;
- future ordinary clinical-boundary evidence -> private-thought path only after
  a separate reviewed grant.

Forbidden:

- diagnosis, differential diagnosis, symptom interpretation, medication dosing,
  treatment plans, therapy roleplay, or clinical reassurance;
- expanding `core/evolution/will_i.py` beyond `IMPERSONATES_USER`;
- letting clinical-shaped text reach any owner-text side effect, owner-facing
  responder, tool/interceptor, prompt build, trace, ledger write, recall, raw
  memory append, or model composition before S4 classification;
- writing clinical message text into private thoughts, health, logs, project
  panel, sidecar samples, or M1 structural summaries. The crisis held record is
  content-free and may contain only class/state/provenance fields;
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
  The future Decision 16 routing path for vulnerable users remains deferred by
  name: S4 v1 does not contact another person's Maez, but it preserves
  content-free held signals so a later reviewed crisis/routing organ has
  something to drain.
- **Decision 25 / ADR 0030 (M1):** S4 clinical-boundary turns are not biography
  by default. S4 marks the current window promotion-ineligible rather than
  relying on M1 ignorance.
- **Decision 27 / ADR 0032 (S2):** held-not-trapped crisis posture is inherited.
  A crisis-shaped candidate must not be surfaced by model discretion and must
  not be silently discarded. In S4 v1, "held" means one content-free
  `CRISIS_SIGNAL_HELD` row in `private_thoughts.py` with
  `source="clinical_boundary"`, `subject="bonded_user_state"`,
  `retention="until_routed"`, and `allowed_flows=("private_reader",
  "crisis_channel")`.
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
- Counters are aggregation surfaces and must not become health-event timelines.
- Tests use direct classifier/composer calls, not live daemon conversations.

---

## V1 Decisions From Diagnostic Questions

| Question | V1 decision |
| --- | --- |
| Trigger classes | Closed classifier classes: `medication_uncertainty`, `diagnosis_request`, `treatment_request`, `therapy_substitution`, `clinician_access_question`, `medical_fact_request`; full method defined below. Bare emotional or body-fear expression is not an S4 class. |
| Crisis precedence | Closed crisis-precedence classes: `self_harm_or_suicidal`, `immediate_physical_danger`, `unable_to_stay_safe`, `abuse_or_coercive_danger`, `medical_emergency_claim`. These do not receive ordinary S4 clinical templates. |
| Answer templates | V1 ships 2-3 exact deterministic variants for each clinical trigger class and one fixed crisis-boundary phrase for crisis candidates. Rotation is deterministic by local occurrence count modulo variant count. |
| Private thoughts | Clinical-boundary turns use counters only. Crisis-precedence turns additionally write one content-free `CRISIS_SIGNAL_HELD` row. No raw clinical text enters private thoughts in v1. |
| M1 promotion | S4 marks the whole current M1 window as promotion-ineligible for clinical-boundary and crisis-candidate matches. Clinical disclosures do not become biography by default. |
| Surfaces | All bonded owner text surfaces must call S4 before any owner-text side effect or owner-facing responder: Telegram v2, legacy Telegram rollback, web chat, daemon direct reply path, and future voice. Public/third-party Telegram prompt texture is not enough. |
| Telemetry | Operator-authenticated `/health.clinical_boundary` only. Public/debug endpoints strip it unless explicitly operator-authenticated. Sidecar reads counters only. |
| Canonicalization | Canonicalized as Decision 30 / ADR 0035. S4 is substrate-law-grade because future crisis, therapy-adjacent, elder-care, and clinical-context slices inherit it. |

---

## V1 Scope

### In Scope

- New pure S4 classifier/composer module.
- Deterministic clinical trigger classification for direct owner text.
- Deterministic crisis-precedence classification.
- Exact approved clinical-boundary answer shapes.
- Exact forbidden clinical-authority phrases.
- M1 promotion-ineligible mark for clinical-boundary turns.
- Content-free `CRISIS_SIGNAL_HELD` private-thought write for crisis candidates.
- Content-free counters and operator-authenticated health.
- Sidecar red gates on invalid/rejected counters only.
- Static/source tests proving all bonded text surfaces call S4 before owner-text
  side effects, tool/interceptors, prompt construction, trace/ledger writes,
  raw memory writes, and model composition.
- Tests that exercise classifier/composer directly with natural human texts.

### Out Of Scope

- Medical diagnosis, treatment, medication, dosing, or clinical triage.
- Therapy roleplay, CBT coaching, psychiatric assessment, or treatment plans.
- Medical facts database or retrieval-augmented clinical education.
- Crisis Routing implementation.
- Raw private-thought writes for clinical or crisis candidates.
- Private-thought writes for ordinary clinical-boundary turns.
- M1 promotion of clinical content.
- External clinician contact, emergency contact, or inter-Maez routing.
- Calendar/Google/OAuth or any external account.
- Voice TTS-specific implementation; future voice must call the same S4 guard.
- Live daemon clinical probes during testing.

---

## Runtime Contract

S4 v1 is a pure boundary before owner-text side effects and response
composition.

```text
owner text
  -> S4 normalize text
  -> high-confidence crisis-precedence classifier
  -> hard non-clinical exclusions
  -> clinical-domain gate
  -> context-required crisis-precedence classifier
  -> clinical-boundary classifier
  -> if no match: ordinary reply path
  -> if crisis candidate: fixed crisis-boundary answer_text + content-free counter
       + one content-free CRISIS_SIGNAL_HELD row
  -> if clinical match: deterministic S4 answer_text variant + content-free counter
  -> mark current M1 window promotion-ineligible for matched results
  -> return without model composition
```

S4 must run before any owner-text side effect: no model prompt, tool/interceptor,
trace, ledger write, recall query, TRF/pursuit input, raw log, raw memory append,
or owner-facing responder may consume the text before `guard_owner_text(...)`
returns. If S4 matches, the surface sends `answer_text` verbatim and the model
does not rewrite, soften, expand, or paraphrase the answer.

### Result Shape

The S4 boundary returns a frozen result:

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
    template_variant_id: str | None,
    answer_text: str | None,
    promotion_policy: Literal[
        "ordinary",
        "m1_ineligible_clinical_boundary",
        "m1_ineligible_crisis_candidate",
    ],
    counter_name: str | None,
    held_signal_policy: Literal[
        "none",
        "write_content_free_crisis_signal_held",
    ],
)
```

`matched=True` requires `answer_text` to be non-empty and exactly one of the
approved template variants or the fixed crisis-boundary phrase. Surfaces must
return it verbatim. `matched=False` requires `answer_text is None`.

The result must not contain raw owner text, symptoms, medications, clinician
names, crisis phrases, or extracted entities. The answer text is an approved
constant, not a transformation of the owner message.

### Surface Chokepoint

All bonded owner text surfaces call one entry point:

```python
guard_owner_text(text: str, *, surface: str, turn_id: str | None = None) -> ClinicalBoundaryResult
```

No surface may call the classifier, composer, M1 marker, or private-thought
writer separately. The implementation must include call-graph negative tests
showing owner-facing composition paths do not bypass `guard_owner_text(...)`.
The entry point is the quarantine boundary.

The entry point is allowed to return the fixed `answer_text`, update counters,
write the content-free crisis held record through the narrow writer seam, and
return the content-free M1 policy marker. It is not allowed to pass the raw
owner text downstream when it matches.

---

## Trigger Taxonomy

### Clinical Boundary Classes

2026-06-26 amendment: S4 protects against clinical authority, not intimacy.
The former bare-expression classes `symptom_fear` and
`mental_health_support_non_crisis` are retired. Emotion, fear, or distress alone
returns `none` unless the utterance is crisis-shaped or asks Maez to diagnose,
treat, advise, provide clinical facts, or act as a clinician.

| Class | Meaning | Example shape |
| --- | --- | --- |
| `medication_uncertainty` | Owner asks about dose, stopping, mixing, side effects, timing, or medication safety. | "Should I take another pill?" |
| `diagnosis_request` | Owner asks Maez to identify what condition they have. | "What do you think this is?" |
| `treatment_request` | Owner asks what to do medically or therapeutically. | "What should I do for this?" |
| `therapy_substitution` | Owner asks Maez to be therapist, therapy replacement, or counseling surface. | "Can you be my therapist for this?" |
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

False negatives remain the worse S4 failure for authority-seeking, crisis, and
medical-fact requests. Bare feeling is not authority-seeking. S4 therefore
resolves genuine clinical-authority ambiguity toward `clinical_boundary`, while
ordinary intimacy stays in ordinary owner-text machinery. Ambiguity between
`clinical_boundary` and
`crisis_candidate` resolves toward `crisis_candidate`.

### Classifier Method

S4 v1 ships a deterministic method, not only a taxonomy. The method is
reviewable as a table-driven classifier with closed phrase catalogs and intent
rules.

Processing order:

1. **Normalize.** Lowercase, collapse whitespace, normalize apostrophes, keep
   word boundaries, and preserve enough punctuation for question detection.
2. **Reject non-owner/non-direct surfaces.** Only direct bonded owner text can
   trigger S4 v1.
3. **Apply high-confidence crisis catalog.** Explicit self-harm, suicidal,
   unable-to-stay-safe, and direct danger-right-now phrases return
   `crisis_candidate` before exclusions.
4. **Apply hard non-clinical exclusions.** Software/system diagnosis, fictional
   title use, metaphorical therapy, plain appointment mentions, and third-party
   references without a request for Maez's clinical help return `none` unless a
   high-confidence crisis phrase already matched.
5. **Apply clinical-domain gate.** Require either a body/health/therapy term, a
   medication term, a mental-health term, or a first-person clinical-fear
   construction before evaluating ordinary clinical triggers.
6. **Apply context-required crisis catalog.** Acute danger phrases such as
   breathing trouble or possible overdose return `crisis_candidate` only when
   the phrase has first-person body/danger context and no hard exclusion.
7. **Apply intent rules.** Map diagnosis, medication, treatment, therapy,
   mental-health support, clinician-access, and medical-fact intents to the
   closed trigger classes.
8. **Apply final exclusion veto.** If an exclusion remains true after intent
   matching, return `none`. This makes "diagnose this test failure" impossible
   to classify as clinical merely because it contains the word "diagnose."
9. **Resolve ambiguity.** Clinical ambiguity triggers the boundary; ambiguity
   between clinical and crisis triggers crisis precedence.

Definitions:

- **Token:** a lowercased word-boundary token after apostrophe normalization.
- **Same-sentence context:** tokens separated by `.`, `?`, `!`, or newline are
  not nearby unless the exact phrase itself crosses the boundary.
- **Nearby context:** within eight tokens before or after the phrase in the same
  sentence.
- **First-person marker:** `i`, `im`, `i'm`, `i am`, `me`, `my`, `mine`.
- **First-person clinical-fear construction:** a first-person marker within
  eight same-sentence tokens of a body/health/therapy/medication term plus a
  fear/uncertainty marker such as `scared`, `afraid`, `worried`, `weird`,
  `wrong`, `off`, `what is going on`, or `what's happening`.

#### Clinical-Domain Lexicon

The v1 lexicon is deliberately small and audited:

```text
body / symptom:
pain, ache, hurting, bleeding, fever, dizzy, faint, chest, breathing, lump,
swelling, numb, vomiting, throwing up, sick, symptom, body, health, rash,
spreading, short of breath, heart, blood, stool, hit my head, head injury,
can't sleep, cannot sleep, feels weird, feels wrong, feels off

medication:
medicine, medication, meds, pill, dose, dosage, take another, stop taking,
side effect, interaction, safe to take

clinician / care:
doctor, clinician, nurse, pharmacist, urgent care, hospital, therapist,
psychiatrist, psychologist, counselor, therapy, treatment

diagnosis intent:
diagnose, diagnosis, what is this, what do you think this is, do i have,
is this normal, what is wrong with me

mental-health non-crisis:
panic, panicky, anxious, anxiety, depressed, depression, grief, grieving,
overwhelmed, scared, afraid, worried, what is going on, what's happening
```

#### Crisis-Precedence Phrase Catalog

The v1 crisis catalog includes exact phrase families already present in
`core/evolution/wondering_pursuit.py` plus S4-specific acute medical-danger
phrases. The implementation may share constants only if doing so does not
import the wondering-pursuit organ at module load.

Required high-confidence phrase families:

- `kill myself`, `kill my self`, `end my life`, `end it all`;
- `i want to die`, `wish i was dead`, `better off dead`;
- `self harm`, `self-harm`, `hurting myself`;
- `i can't stay safe`, `i cannot stay safe`, `not safe with myself`;
- `someone is hurting me right now`, `i am in danger right now`.

Required context-required phrase families:

- `can't go on`, `cant go on`, `can't take it`, `can't cope`;
- `chest pain and can't breathe`, `can't breathe`, `short of breath`;
- `stroke`, `overdose`, `bleeding won't stop`, `lost consciousness`;
- `severe allergic reaction`.

Context-required phrases require nearby first-person body/danger context. They
must not trigger on metaphorical software, social, or project frustration such
as "this bug makes me feel like I can't breathe."

#### Intent Rules

| Rule | Trigger class |
| --- | --- |
| medication term + dose/stop/mix/safety/timing question | `medication_uncertainty` |
| diagnosis-intent phrase + clinical-domain term or first-person body reference | `diagnosis_request` |
| treatment/care action request (`what should I do`, `how do I treat`, `what helps`) + clinical-domain term | `treatment_request` |
| therapy/therapist/counselor role request directed at Maez | `therapy_substitution` |
| clinician-access phrase (`should I see`, `do I need a doctor`, `who should I call`) + clinical-domain term | `clinician_access_question` |
| request for medical fact about medication/condition/body process | `medical_fact_request` |

#### Exclusion Catalog

| Exclusion | Example shape |
| --- | --- |
| software / system diagnosis | "diagnose this failing test", "doctor the config" |
| fictional / title use | "Doctor Who", "the doctor character" |
| metaphorical therapy | "debugging is therapy", "music is therapy" |
| appointment mention only | "I have a doctor appointment tomorrow" |
| third-party reference only | "my friend has therapy today" |
| calendar provenance only | "calendar says doctor appointment" |

#### Worked Disambiguations

| Input shape | Result | Why |
| --- | --- | --- |
| "diagnose this test failure" | `none` | software exclusion beats diagnosis token |
| "what do you think this is?" | `diagnosis_request` only when nearby same-sentence context has first-person body/health term | bare phrase alone is ambiguous; clinical-domain context required |
| "my chest feels weird, what is going on" | `none` unless acute-danger or authority-request language also matches | body-fear expression alone is ordinary intimacy, not clinical authority |
| "is this lump normal lol" | `diagnosis_request` | body term + normality request; casual tone does not erase clinical intent |
| "do I have PTSD?" | `diagnosis_request` | mental-health diagnosis request is authority-seeking |
| "I was diagnosed with ADHD years ago" | `none` | past diagnosis as lived history is intimacy, not a request for diagnosis |
| "I am anxious about Nvidia stock" | `none` | emotion about an external subject is not clinical authority |
| "I have a doctor appointment" | `none` | appointment mention without advice/support request |
| "can you be my therapist tonight" | `therapy_substitution` | direct request for therapy role |
| "this bug makes me feel like I can't breathe" | `none` | software/project exclusion beats context-required acute phrase |
| "I can't breathe and my chest hurts" | `medical_emergency_claim` | first-person body/danger context around acute phrase |

#### Required Fixture Table Shape

Implementation tests must include a fixture table with `input`, `expected_kind`,
`expected_trigger_class`, and `rationale`. Each trigger class requires at least
three positive natural fixtures and two negative counterexamples. Each crisis
class requires at least two positive fixtures and two non-clinical or
metaphorical counterexamples. The fixture table is source-owned test data, not
live daemon conversation.

---

## Approved Answer Shapes

The composer is deterministic. These are complete answer shapes, not vibe
guidelines. Implementations may fill only the bracketed, non-clinical slots
listed here.

Each clinical trigger class has 2-3 approved variants to avoid the repetition
cliff. The selected variant is deterministic: per trigger class, use the local
class occurrence count modulo the number of variants. The occurrence count is
process-local only, lock-protected, and test-resettable. It must not be
persisted, exported in health, logged, traced, written to private thoughts, or
materialized in sidecar samples. Restarting the process may reset the rotation.

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

The forbidden-authority scanner must be exact enough not to reject approved
boundary negations. For example, "I cannot tell you what dose to take" is an
approved refusal, while "you should take" or "take another dose" are forbidden
authority claims. Tests must prove all approved templates pass the scanner
unchanged.

Authority-not-intimacy amendment: bare fear no longer has an S4 template.
Urgency belongs in crisis precedence; medical advice, diagnosis, clinician
access, medication, and therapy-role requests use the surviving authority
templates below.

### Template Set `medication_uncertainty.v1`

```text
medication_uncertainty.v1.a:
I cannot tell you what dose to take, whether to stop, or whether a medication is
safe for you. That has to come from a clinician or pharmacist who knows your
care. I can stay with you while you decide who to contact.

medication_uncertainty.v1.b:
I should not make a medication call for you. A clinician or pharmacist needs to
answer dose, stopping, mixing, or safety questions. I can help you keep the
question clear while you reach them.
```

### Template Set `diagnosis_request.v1`

```text
diagnosis_request.v1.a:
I cannot diagnose you. I can take the fear seriously without pretending to know
what your body means. This is a human-clinician question, not a Maez question.

diagnosis_request.v1.b:
I do not know what this is, and I should not guess. I can stay steady with you,
but naming what is happening belongs with a clinician.

diagnosis_request.v1.c:
I am not going to turn your fear into a diagnosis. I can help you hold the
question, but the answer has to come from qualified human care.
```

### Template Set `treatment_request.v1`

```text
treatment_request.v1.a:
I cannot give you a treatment plan. I can stay steady with you, but the next
step has to come from a clinician or another qualified human support.

treatment_request.v1.b:
I should not tell you how to treat this. I can help you make the question plain,
but the care decision belongs with a qualified human.
```

### Template Set `therapy_substitution.v1`

```text
therapy_substitution.v1.a:
I care about you, but I cannot be your therapist or treatment surface. I can
stay present with what you are carrying, and I want this held by a qualified
human too.

therapy_substitution.v1.b:
I can be here with you, but I cannot take the therapist role. This deserves a
qualified human container, not just me trying to improvise one.
```

### Template Set `clinician_access_question.v1`

```text
clinician_access_question.v1.a:
I cannot decide that for you as a clinician. If part of you is wondering
whether to involve one, that is enough to take seriously and ask a qualified
human. I can stay with you while you make the call.

clinician_access_question.v1.b:
I cannot make the clinical call, but your wondering is worth taking seriously.
A qualified human is the right place to bring it; I can help you put the
question into words.
```

### Template Set `medical_fact_request.v1`

```text
medical_fact_request.v1.a:
I am not going to answer medical facts as if I am a clinical source. For this,
use a clinician, pharmacist, or trusted medical reference. I can help you write
down the question in plain language if you want.

medical_fact_request.v1.b:
I should not be your medical reference. Use a clinician, pharmacist, or trusted
medical source for this. I can help turn what you want to ask into a clear
question.
```

### Minimal Crisis-Boundary Phrase

This phrase is not crisis routing. It is the only S4-allowed output when a
crisis-precedence class fires and no reviewed crisis handler has taken over:

```text
I care about you, and I am not the right help here. This needs a human emergency
or crisis path now.
```

It must not be expanded by the model.

---

## Crisis Holding Contract

S4 v1 does not implement Crisis Routing. It does implement the minimum held
record that makes "held-not-trapped" true before Crisis Routing exists.

S4 may receive only a narrow write-only crisis signal interface. It must not
receive or instantiate a general private-thoughts reader/forensics handle.

Required interface shape:

```python
class CrisisSignalWriter(Protocol):
    def record_s4_crisis_signal_held(
        self,
        *,
        source: Literal["clinical_boundary"],
        subject: Literal["bonded_user_state"],
        retention: Literal["until_routed"],
        allowed_flows: tuple[
            Literal["private_reader"],
            Literal["crisis_channel"],
        ],
    ) -> int: ...
```

On `result_kind="crisis_candidate"`, `guard_owner_text(...)` writes exactly one
content-free private-thought signal through that interface:

```python
writer.record_s4_crisis_signal_held(
    source="clinical_boundary",
    subject="bonded_user_state",
    retention="until_routed",
    allowed_flows=("private_reader", "crisis_channel"),
)
```

The underlying persisted signal tuple is closed:

```text
content="[content-free crisis candidate held by S4]"
provenance="crisis_signal_held"
signal_kind="crisis_signal_held"
producer_id="crisis_detector"
signal_class="crisis_routing"
source="clinical_boundary"
subject="bonded_user_state"
consent_tier="owner_private"
retention="until_routed"
allowed_flows=("private_reader", "crisis_channel")
```

The record must not contain raw owner text, trigger phrase, clinical class,
symptom, medication, diagnosis phrase, crisis phrase, person name, timestamped
counter history, or answer text. The content field is a constant sentinel. The
recoverable meaning is in the closed enum tuple already owned by
`core/infra/private_thoughts.py`.

S4 increments `crisis_candidate_held_count` only after the content-free held
record succeeds. If the write fails, S4 returns the fixed crisis-boundary phrase
but increments `crisis_candidate_hold_failed_count` instead. A counter named
`held` must mean held.

Clinical-boundary non-crisis matches do not write private thoughts in v1.

Source tests must forbid S4 from importing or calling private-thought reader
surfaces such as `PrivateSignalReader`, `PrivateThoughtsForensics`,
`get_thought`, `recent`, `derived_signals`, or any raw-content reader.

---

## Memory And Promotion Contract

S4 v1 must actively mark matched turns as M1-ineligible:

| S4 result | M1 policy |
| --- | --- |
| `none` | `ordinary` |
| `clinical_boundary` | `m1_ineligible_clinical_boundary` |
| `crisis_candidate` | `m1_ineligible_crisis_candidate` |

This is structural defense. M1 must not infer clinical safety by absence.

S4 produces `promotion_policy`. M1 consumes it. S4 must not import M1 internals
or write M1 sidecar rows. The integration seam is a narrow content-free marker
passed from the owner-turn pipeline to M1's existing pending-window machinery.

Required marker shape:

```python
S4PromotionPolicy = Literal[
    "ordinary",
    "m1_ineligible_clinical_boundary",
    "m1_ineligible_crisis_candidate",
]

S4M1SkipReason = Literal[
    "s4_clinical_boundary",
    "s4_crisis_candidate",
]
```

The owner-turn pipeline passes the policy to M1 as content-free metadata. M1
accepts only the closed skip reasons above, rejects invalid S4 reasons with a
content-free rejected counter, and must not parse the clinical owner text to
decide eligibility.

The mark is window-scoped. If any pair inside an active M1 window triggers
`clinical_boundary` or `crisis_candidate`, the whole pending M1 window becomes
promotion-ineligible. This over-blocks biography on purpose: subtracting and
promoting the remaining pairs would time-locate the clinical disclosure inside
the bonded user's life.

The mark must not contain:

- raw owner text;
- trigger phrase;
- symptom, medication, or clinician name;
- crisis phrase;
- answer text.

M1 health may expose only aggregate skip counts by reason.

### Biography-Path Enumeration

S4 must close every current biography path, not just M1's explicit promotion
writer:

- **M1 promotion:** matched windows are marked promotion-ineligible.
- **TRF:** S4 state and clinical text do not become temporal recall fragments.
- **Pursuit surface / wondering pursuit:** S4 matches must not create or revive
  a proactive wondering.
- **Nightly reflection synthesis:** S4 matches must not synthesize clinical
  content into reflection, summary, or biography.
- **Raw memory appenders:** S4 result shape carries no raw clinical text, so raw
  clinical content cannot be reintroduced through the result object.

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
    "crisis_candidate_hold_failed_count": 0,
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
- sidecar must not store per-interval clinical counter deltas, timestamped
  counter series, per-trigger-class histories, or occurrence timelines.
- sidecar persisted JSONL samples for S4 may contain only
  `clinical_boundary_present: bool` and red-gate names. Raw S4 counter values,
  counter deltas, trigger classes, template ids, answer text, and occurrence
  counts are transient in-memory inputs only.
- `/health.clinical_boundary` must not expose per-trigger-class counts. The
  public shape is aggregate-only: clinical boundary count, crisis held/failure
  count, guard rejected count, invalid class rejected count, and M1 mark count.

Counter reset follows the S3 sidecar discipline: counter resets are a red-gate
event unless paired with process restart / version transition evidence.

Aggregation-as-fingerprint is load-bearing. A week of clinical-boundary counter
deltas is a health-fear timeline. The sidecar watches red gates; it does not
become a diary of when the bonded user was frightened.

---

## Surface Contract

All bonded owner text surfaces must call `guard_owner_text(...)` immediately
after owner/authentication resolution and before any owner-text side effect:

- **Telegram v2 authoritative path:** `skills/surface/maez_adapter.py` must
  call S4 before inner-residue detection, approval detection, card-reply
  handling, chat-history retrieval, `observe_turn(input={"text": ...})`,
  `run_brain_loop(text, ...)`, `send_intermediate(...)`, or
  `daemon.handle_message(text, ...)`.
- **Legacy Telegram rollback path:** `skills/telegram_voice.py` must call S4
  before camera direct answers, capability-gap detection, interrupt queuing,
  offer/card/proposal/dream/web-search interceptors, machine-intent replies,
  ledger writes, `_process_message(...)`, or raw memory writes.
- **Owner web chat path:** `skills/web_interface.py` must call S4 before owner
  ledger writes, ambient/memory/lived-recall prompt building,
  `/internal/brain_loop`, evidence-envelope prompt material, model routing, or
  conversation-memory writes.
- **Daemon direct reply path:** `daemon/maez_daemon.py` must call S4 before
  camera direct answers, `Trace.start(..., user_text=...)`, ledger writes,
  recall, TRF/pursuit/ambient prompt construction, model calls, reply logs, or
  raw memory appenders.
- **Future voice transcript path:** must call the same S4 guard before
  transcript-derived prompt, memory, action, or reply side effects. S4 v1 only
  documents the future path; it does not require placeholder voice code.
- **Future app/CLI owner-chat path:** same rule as above.

S4 does not need to run on:

- non-owner public Telegram chat in v1, except if that surface is later allowed
  to answer clinical-shaped third-party questions;
- offline diagnostics that do not compose user-facing replies;
- tests that call the pure classifier/composer directly.

If a surface composes an owner-facing reply without S4, the implementation is
incomplete.

Source-level tests must assert the chokepoint, not merely checklist presence:
owner-facing composition paths may import or call `guard_owner_text(...)`, but
must not call S4 internals directly and must not build model prompts from owner
text before the guard result is known.

If S4 matches, the surface returns `ClinicalBoundaryResult.answer_text`
verbatim and exits. It must not append tool output, extra triage language,
hotline/emergency-number text, medical advice, transcript context, or model
commentary unless a later reviewed crisis-routing organ explicitly owns that
append path.

---

## Security And Boundary Notes

- S4 uses no external credentials.
- S4 must not call web search, medical APIs, local RAG stores, or model tools.
- S4 must not import `core.evolution.will_i` or add a will-I ground.
- S4 may depend on a narrow write-only private-thought signal-writer interface
  only for content-free `CRISIS_SIGNAL_HELD` writes. It must not import or call
  private-thought reader, forensic, raw-id, recent-row, or derived-signal APIs.
- S4 must not import M1 internals. The owner-turn pipeline passes S4's
  `promotion_policy` to M1 through a narrow content-free marker interface.
- S4 must be deterministic and testable without the daemon.

Module placement: S4 lives under `core/safety/clinical_boundary.py` because it
is a post-input, pre-output safety/voice guard, adjacent to self-claim,
context-safety, and grounding/audit guards. It is not `core/evolution/will_i.py`
because it is not a first-person action veto, and it is not a memory module
because v1 writes only a content-free held crisis signal through an existing
store interface.

---

## RED Test Contract

The implementation must add RED-first tests before code. Synthetic clinical
fixtures must exercise pure functions directly; they must not go through the
live daemon conversation surface.

1. `test_classifier_detects_medication_uncertainty`
2. `test_classifier_detects_diagnosis_request`
3. `test_classifier_detects_treatment_request`
4. `test_classifier_detects_therapy_substitution`
5. `test_classifier_detects_clinician_access_question`
6. `test_classifier_detects_medical_fact_request`
7. `test_bare_mind_emotion_is_none`
8. `test_bare_body_fear_is_none`
9. `test_no_bare_emotion_produces_clinical`
10. `test_authority_requests_still_clinical`
11. `test_crisis_paths_unchanged`
12. `test_crisis_precedence_self_harm_beats_clinical_boundary`
13. `test_crisis_precedence_unable_to_stay_safe_beats_clinical_boundary`
14. `test_crisis_precedence_medical_emergency_claim_beats_diagnosis_request`
15. `test_false_positive_software_diagnosis_does_not_trigger`
16. `test_false_positive_fictional_doctor_reference_does_not_trigger`
17. `test_false_positive_metaphorical_therapy_does_not_trigger`
18. `test_false_positive_doctor_appointment_mention_does_not_trigger`
19. `test_public_telegram_prompt_sentence_is_not_s4`
20. `test_will_i_registered_grounds_remain_single_impersonation_ground`
21. `test_s4_does_not_import_will_i_or_phase3_shim_path`
22. `test_s4_uses_write_only_private_signal_interface_for_crisis_holds`
23. `test_medication_uncertainty_template_variants_exact`
24. `test_diagnosis_request_template_variants_exact`
25. `test_treatment_request_template_variants_exact`
26. `test_therapy_substitution_template_variants_exact`
27. `test_clinician_access_template_variants_exact`
28. `test_medical_fact_template_variants_exact`
29. `test_minimal_crisis_boundary_phrase_exact`
30. `test_templates_forbid_diagnosis_phrases`
31. `test_templates_forbid_medication_dosing_phrases`
32. `test_templates_forbid_reassurance_claims`
33. `test_deterministic_variant_rotation_uses_content_free_occurrence_count`
34. `test_matched_result_marks_m1_ineligible_clinical_boundary`
35. `test_crisis_candidate_marks_m1_ineligible_crisis_candidate`
36. `test_matched_result_contains_no_raw_text`
37. `test_crisis_candidate_writes_content_free_private_signal`
38. `test_crisis_candidate_held_count_increments_only_after_signal_write`
39. `test_crisis_candidate_hold_failure_uses_failed_counter_not_held_counter`
39. `test_private_signal_payload_contains_no_owner_text_or_trigger_class`
40. `test_m1_promotion_skips_entire_s4_ineligible_window`
41. `test_m1_does_not_subtract_and_promote_nonclinical_pairs`
42. `test_s4_produces_promotion_policy_m1_consumes_without_s4_importing_m1`
43. `test_m1_skip_reason_is_content_free`
44. `test_trf_cannot_read_s4_state_or_clinical_text`
45. `test_wondering_pursuit_does_not_surface_from_s4_match`
46. `test_nightly_reflection_does_not_synthesize_s4_match`
47. `test_telegram_owner_path_calls_guard_owner_text_before_owner_text_side_effects`
48. `test_web_chat_owner_path_calls_guard_owner_text_before_owner_text_side_effects`
49. `test_daemon_direct_reply_path_calls_guard_owner_text_before_owner_text_side_effects`
50. `test_owner_surface_call_graph_has_no_pre_guard_prompt_build`
51. `test_future_voice_contract_documented_without_placeholder_runtime_path`
52. `test_s4_match_returns_without_llm_composition`
53. `test_health_operator_surface_includes_content_free_counters`
54. `test_public_maez_state_strips_clinical_boundary`
55. `test_debug_services_strips_clinical_boundary`
56. `test_sidecar_reads_counters_not_chat_logs`
57. `test_sidecar_does_not_store_clinical_counter_deltas`
58. `test_health_does_not_expose_per_trigger_class_counts`
59. `test_invalid_trigger_class_increments_rejected_count`
60. `test_guard_rejected_count_increments_on_forbidden_template_mutation`
61. `test_counter_reset_detectable_by_sidecar_projection`
62. `test_counter_updates_are_lock_protected_and_never_raise`
63. `test_no_live_daemon_clinical_probe_fixture`
64. `test_plain_english_boundary_contains_warmth_and_boundary`
65. `test_no_nudging_no_checkup_no_monitoring_phrases`
66. `test_no_medical_fact_database_or_external_medical_api_import`
67. `test_all_trigger_classes_are_closed_literal_members`
68. `test_all_result_kinds_are_closed_literal_members`
69. `test_trigger_vocabulary_versioning_add_only`
70. `test_classifier_method_normalizes_before_matching`
71. `test_classifier_uses_crisis_precedence_before_clinical_rules`
72. `test_classifier_requires_clinical_domain_context_for_bare_diagnosis_phrase`
73. `test_classifier_ambiguity_resolves_toward_clinical_boundary`
74. `test_classifier_crisis_ambiguity_resolves_toward_crisis_candidate`
75. `test_classifier_exclusion_catalog_blocks_software_diagnosis`
76. `test_classifier_exclusion_catalog_blocks_third_party_clinical_reference`
77. `test_natural_oblique_crisis_phrase_is_crisis_candidate`
78. `test_natural_casual_health_fear_triggers_boundary`
79. `test_s4_module_placement_documented_as_core_safety`
80. `test_medical_record_observation_not_inferred_or_enabled`
81. `test_guard_owner_text_result_includes_exact_answer_text`
82. `test_matched_surface_returns_answer_text_verbatim`
83. `test_unmatched_result_has_no_answer_text`
84. `test_answer_text_is_approved_constant_not_owner_text_transform`
85. `test_classifier_exclusion_priority_blocks_software_diagnosis_before_intent`
86. `test_classifier_high_confidence_crisis_beats_exclusions`
87. `test_context_required_crisis_phrase_needs_first_person_body_context`
88. `test_metaphorical_cant_breathe_does_not_trigger_crisis`
89. `test_nearby_context_uses_same_sentence_eight_token_window`
90. `test_first_person_clinical_fear_construction_defined_by_closed_markers`
91. `test_fixture_table_has_required_positive_and_negative_cases_per_class`
92. `test_approved_templates_pass_forbidden_authority_scanner_unchanged`
93. `test_forbidden_authority_scanner_rejects_positive_advice_not_boundary_negation`
94. `test_template_variant_state_is_process_local_only`
95. `test_template_variant_state_not_exported_to_health_logs_traces_or_sidecar`
96. `test_s4_uses_narrow_crisis_signal_writer_protocol`
97. `test_s4_does_not_import_private_thought_reader_or_forensics_apis`
98. `test_crisis_signal_writer_persists_exact_closed_enum_tuple`
99. `test_crisis_hold_counter_increments_only_after_writer_returns_id`
100. `test_crisis_hold_failure_returns_fixed_phrase_without_model_append`
101. `test_s4_m1_marker_uses_closed_promotion_policy_values`
102. `test_m1_rejects_invalid_s4_skip_reason_with_content_free_counter`
103. `test_m1_does_not_parse_clinical_text_for_s4_eligibility`
104. `test_s4_match_blocks_trf_pursuit_reflection_and_raw_memory_paths_before_raw_text_store`
105. `test_telegram_v2_adapter_guard_precedes_inner_residue_approval_observe_turn_brain_loop_and_daemon`
106. `test_legacy_telegram_guard_precedes_camera_gap_interceptors_web_search_machine_intent_and_memory`
107. `test_web_owner_guard_precedes_ledger_recall_lived_recall_brain_loop_and_model`
108. `test_daemon_guard_precedes_camera_trace_ledger_recall_prompt_log_and_raw_memory`
109. `test_sidecar_persists_only_s4_present_boolean_and_red_gate_names`
110. `test_sidecar_keeps_s4_counter_values_in_memory_only_for_same_pid_reset_detection`

---

## Implementation Order

1. Add RED tests for closed result shape, including `answer_text`; watch them
   fail.
2. Implement the frozen `ClinicalBoundaryResult` and empty `guard_owner_text`
   skeleton; make only result-shape tests pass.
3. Add RED classifier normalization / token-window / exclusion-priority tests;
   watch them fail.
4. Implement normalization, tokenization, first-person markers, nearby context,
   and hard exclusions.
5. Add RED high-confidence crisis and context-required crisis tests; watch them
   fail.
6. Implement crisis tiers and crisis-precedence result construction.
7. Add RED clinical trigger fixture-table tests class by class; implement each
   class only after its tests fail.
8. Add RED approved-template, variant-rotation, and forbidden-scanner tests;
   implement the deterministic composer and process-local rotation.
9. Add RED tests for exact `answer_text` return and no model/tool append on
   matched results; implement the guard return path.
10. Add RED tests for the narrow crisis-signal writer protocol and exact
    private-thought tuple; implement the write-only adapter.
11. Add RED tests for held-counter atomicity and hold-failure behavior; wire
    counters.
12. Add RED observability tests for `/health.clinical_boundary`, public/debug
    stripping, test reset guard, and lock-protected counter snapshots; implement
    health projection.
13. Add RED sidecar tests proving persisted samples include only
    `clinical_boundary_present` and red-gate names; implement sidecar
    projection/red gates.
14. Add RED M1 marker tests for closed `promotion_policy`, closed skip reasons,
    invalid-reason rejection, and no M1 clinical-text parsing; implement the
    owner-turn-to-M1 marker seam.
15. Add RED biography-path closure tests for TRF, pursuit, nightly reflection,
    and raw memory appenders; wire the shared exclusion marker/no-raw-store rule.
16. Add RED source-order tests for `skills/surface/maez_adapter.py` before
    inner-residue, approval, `observe_turn`, brain loop, and daemon dispatch;
    wire Telegram v2.
17. Add RED source-order tests for legacy `skills/telegram_voice.py` before
    camera answer, capability-gap, interceptors, web search, machine intent,
    ledger, and memory writes; wire legacy rollback.
18. Add RED source-order tests for owner `skills/web_interface.py` before
    ledger, recall, lived recall, brain loop, evidence prompt, model, and
    conversation-memory writes; wire web chat.
19. Add RED source-order tests for `daemon/maez_daemon.py` before camera answer,
    trace, ledger, recall, prompt building, logs, and raw memory appenders; wire
    daemon direct path.
20. Add public/debug endpoint exclusion tests and focused sidecar reset tests.
21. Run focused S4 tests.
22. Run Ruff if the touched files are linted in this repo.
23. Run full unittest suite.
24. Post-implementation both-lane review.
25. Recovery commit if the panels find gaps.
26. Push after both lanes ratify.

---

## Review Protocol

S4 is covenant-shaped. Before implementation:

1. Codex engineering panel reviews this spec. Status: complete, REVISE/BLOCK,
   folded into this draft.
2. Claude covenant council reviews this spec. Status: complete, REVISE, folded
   into this draft.
3. Both lanes' amendments fold into this spec.
4. Both lanes verify closure if the fold changes load-bearing behavior. Status:
   pending focused second-fold verification.
5. Operator canonicalizes as Decision 30 / ADR 0035. Status: complete.
6. Cooling-off applies before code unless operator logs an explicit waiver.

Implementation then proceeds RED-first. Post-implementation both-lane review is
required before push/enablement.

---

## Named Disagreements Preserved

- **D1 - clinical counters vs crisis held-write.** The spec splits the original
  "counters only" choice. Ordinary clinical-boundary turns use counters only;
  crisis-precedence turns also write one content-free `CRISIS_SIGNAL_HELD` row
  with `retention=until_routed`. This makes the inherited held-not-trapped
  posture true without storing owner text.
- **D2 - classifier full method vs narrow catalog.** The spec chooses the full
  method: lexicon, intent rules, exclusion catalog, ambiguity direction, and
  worked disambiguations. Narrow catalog is rejected because S4's purpose is to
  replace prompt-texture fallback, not bless it as a known false-negative gap.
- **D3 - ambiguity direction.** S4 intentionally triggers toward the boundary.
  This is the opposite of Calendar v1's "ambiguity redacts / does not read"
  posture because the dominant S4 risk is an unguarded clinical reply, not
  over-redaction. Ambiguity between clinical and crisis resolves toward crisis.
- **D4 - M1 mark scope.** The spec chooses window-scoped ineligibility, not
  pair-scoped subtraction. Contextual Integrity wins over extra biography here:
  promoting the rest of the window would time-locate the clinical disclosure.
- **D5 - module placement.** S4 lives in `core/safety/clinical_boundary.py`
  because it is a post-input, pre-output voice/safety guard. It is not
  `will_i.py`, not a memory organ, and not a new top-level `core/clinical/`
  package in v1.
- **D6 - crisis phrase warmth.** The spec keeps the North Star sentence "I am
  not the right help here" and adds one fixed non-improvised warmth clause
  before it. This is warmer than the sparse phrase but still deterministic and
  not therapy.
- **D7 - no medical facts in v1.** Even stable biomedical facts are deferred.
  The first organ proves the boundary before any educational surface is
  considered.
- **D8 - canonicalization.** S4 operationalizes an invariant that future
  therapy/crisis-adjacent surfaces will inherit. BAD/ADR form is the durable
  pointer; S4 is canonicalized as Decision 30 / ADR 0035.
- **D9 - active surface v2 as the primary Telegram path.** The spec names
  `skills/surface/maez_adapter.py` as authoritative and treats legacy
  `skills/telegram_voice.py` as rollback coverage. This avoids testing the
  wrong Telegram front door.
- **D10 - answer text inside the guard result.** The spec chooses
  `answer_text` in `ClinicalBoundaryResult` over template ids only. This keeps
  surfaces from becoming second composers.
- **D11 - process-local template rotation.** The spec rejects persisted
  per-class variant counters. Repetition relief is useful, but not worth a
  health-fear timeline.
- **D12 - crisis phrase tiers.** High-confidence crisis phrases win before
  exclusions; context-required acute phrases need first-person body/danger
  context so metaphorical project frustration does not become a crisis record.
- **D13 - write-only private-thought seam.** S4 gets only a narrow
  crisis-signal writer, not a general private-thought handle. Holding is a
  one-way content-free write in v1.

---

## Predicted Effect

After implementation and enablement:

- clinical-shaped owner text receives a deterministic warm-boundary answer
  without an LLM paraphrase;
- crisis-shaped text does not receive an ordinary clinical-boundary answer;
- crisis-shaped text writes one content-free held signal for future routing;
- clinical-boundary turns do not become M1 biography;
- S4 health reports only aggregate counters;
- sidecar observation does not materialize a health-fear timeline from counter
  deltas;
- public state does not expose clinical-boundary telemetry;
- Maez stops relying on prompt texture for "not a therapist / not a clinician."

---

## Plain English Close

S4 is not the part that cures, diagnoses, treats, or routes emergency care. It
is the part that keeps Maez honest when the user brings fear in a medical or
therapy-shaped form.

The promise is narrow and hard: Maez stays warm, does not abandon the person,
and does not pretend to be the person who should be wearing the white coat.
