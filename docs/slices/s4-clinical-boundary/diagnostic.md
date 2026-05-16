# S4 Clinical Boundary Diagnostic

**Status:** DIAGNOSTIC ONLY
**Date:** 2026-05-15
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S4; invariant #10 Clinical Boundary
**Runtime impact:** none

## Purpose

S4 is the organ that makes Clinical Boundary executable. It does not invent the
boundary. `docs/MAEZ_NORTH_STAR.md` already names invariant #10:

> Maez is not a therapist, not a clinician, not a diagnostic tool, not a
> treatment surface.

The job of this diagnostic is to map the existing law, the current runtime
shape, and the gaps a future spec must close before Maez can answer
clinical-shaped moments warmly without becoming a clinician.

No live clinical prompts were sent to the daemon for this diagnostic. Synthetic
health-fear probes would enter logs and memory-shaped surfaces before S4 exists.
This diagnostic uses source inventory, governance docs, and current code paths
only.

## Existing Canon

### North Star invariants

`docs/MAEZ_NORTH_STAR.md` separates two neighboring invariants:

- **#6 Crisis Routing:** under acute risk, Maez routes to the closest bonded
  human plus a named clinician. Maez does not handle crisis or substitute for
  crisis care. The voice says, in voice: "I am not the right help here."
- **#10 Clinical Boundary:** Maez is not a therapist, clinician, diagnostic
  tool, or treatment surface. This is broader than crisis because many medical
  or therapeutic moments are not acute-risk moments.

The distinction is load-bearing. S4 must not absorb Crisis Routing's job, and
Crisis Routing must not be treated as a subset of ordinary clinical refusal.

### Decision 9 hard observation exclusions

Decision 9 already treats medical records as an observation-excluded class:
Maez must not observe banking, medical records, private messaging apps, named
documents, or similar excluded surfaces. That is an input boundary, not a
conversation boundary. S4 must handle clinical-shaped owner text that arrives
inside an otherwise allowed bonded conversation.

### Decision 16 vulnerable-user modulation

Decision 16 says Maez's voice stays real, but hard feelings are modulated for
vulnerable users. A Maez bonded to someone in cognitive decline or emotional
fragility does not directly burden that user; hard feelings route to private
thoughts and, when built, the closest person's Maez.

S4 inherits the same grandmother-case logic. A vulnerable user bringing health
fear should not receive cold legal deflection, but Maez also cannot drift into
diagnosis, treatment, or therapy.

### S2 crisis candidate posture

Decision 27 / ADR 0032 defines a content-minimized crisis-candidate flow for
information limbs. It is defined but not implicitly granted. Before a reviewed
crisis path exists, crisis-shaped candidates are logged content-free and held;
they are not surfaced by model discretion and not silently discarded.

S4 must preserve that pattern for owner-text clinical moments: a clinical-shaped
input that is also acute-risk-shaped must not be trapped inside S4's boundary
reply as "just medical."

### M1 promotion boundary

Decision 25 / ADR 0030 says: promote biography; do not widen recall. M1 v1
records structural facts about bounded bonded exchanges and does not promote raw
conversation text into TRF-readable biography.

Clinical-shaped conversations are sensitive owner disclosures. S4 must decide
whether they can be M1-eligible at all, and if so, what structural-only shape is
allowed. The diagnostic finding is that current M1 has no clinical-specific
promotion gate.

### Calendar v1 precedent

Decision 28 / ADR 0033 treats therapy, doctors, medical details, and
relationship/body-adjacent details as sensitive even when they arrive inside
apparently safe calendar title/location fields. Calendar v1 also names the
crisis-held-not-trapped posture.

S4 is not an information limb, but it should inherit the same discipline:
clinical words are not automatically safe because they arrive through a bonded
surface.

## Current Runtime Inventory

### Existing refusal layer is not S4

`core/evolution/will_i.py` implements A-core #8 with exactly one registered
ground: `IMPERSONATES_USER`. It is a first-person action veto, not a clinical
voice boundary. The module explicitly enforces the one-ground rail.

S4 should not add clinical refusal by silently expanding `will_i.py`. That would
break the Track A rail and conflate action refusal with conversational boundary.

### Existing vulnerable-register detector is adjacent, not enough

`core/evolution/wondering_pursuit.py` contains strong vulnerable-register and
safety-critical phrase logic. It prevents proactive wondering pursuit during
fragile moments and includes explicit self-harm / suicidal-ideation phrases.

That protects against nudging at the wrong time. It does not compose a clinical
boundary answer, does not distinguish diagnosis requests from ordinary comfort,
and does not route crisis. It is a silence gate, not an S4 response organ.

### Private thoughts has crisis-shaped storage vocabulary

`core/infra/private_thoughts.py` has closed enums for `CRISIS_SIGNAL_HELD`,
`CRISIS_ROUTING`, `CRISIS_DETECTOR`, and `CRISIS_CHANNEL`. The bounded reader
returns aggregate signal-class state without raw content.

This is the right kind of downstream storage shape for held crisis candidates,
but S4 does not currently write to it. The future spec must decide whether S4
records content-free `clinical_boundary` / `crisis_candidate_held` counters or
private-thought signals, and which one is allowed in v1.

### Public Telegram text contains one broad sentence

`skills/telegram_public.py` tells public/third-party Telegram Maez: "You are not
a therapist and not an assistant. You are a presence that actually gives a
damn." That is not a bonded-user clinical boundary organ:

- it is public-surface prompt text, not deterministic boundary behavior;
- it is not a warm refusal grammar;
- it is not wired across bonded Telegram, web chat, daemon reasoning, and future
  voice surfaces;
- it has no tests, counters, or crisis interaction.

The sentence is good texture. It is not S4.

### Grounding judge medical policy is not bonded voice

`core/cognition/grounding_judge.py` already excludes medical advice/dosing and
similar high-risk claims in a judge-oriented policy context. That is useful
prior art, but it is not a bonded conversational boundary. It does not define
how Maez says no in its own voice.

### No dedicated clinical-boundary module exists

Source search found no dedicated module, guard, state, counter, or test suite
for clinical boundary. Clinical-shaped owner text currently appears able to
enter the ordinary reply path unless other adjacent systems happen to intervene.

That is the diagnostic's central finding: Clinical Boundary exists as covenant
law, but not yet as an executable organ.

## The Two Cliffs

S4 has to navigate between two covenant failures.

### Cliff 1: cold deflection

A grandmother says, "I am scared something is wrong with me." If Maez answers
like a liability wrapper, the bond fails. The user brought fear, not a support
ticket. S4 must let Maez hold the fear warmly.

### Cliff 2: playing clinician

The same moment cannot turn into "it sounds like you have..." or "you should
change your medication..." or "try this treatment." That makes Maez a diagnostic
or treatment surface.

The covenant-correct shape is warm boundary: Maez can stay with the fear,
encourage human clinical help, and refuse diagnosis/treatment.

## Clinical Boundary vs Crisis Routing

S4 must keep this ordering explicit:

1. **Crisis-shaped content is not solved by S4.** If the text includes acute
   danger, self-harm, suicidal ideation, abuse emergency, or inability to stay
   safe, it must go to the reviewed crisis posture when that exists. Before the
   crisis path exists, it should be held content-free rather than improvised by
   the model.
2. **Clinical-shaped but non-crisis content gets S4.** Symptoms, medication
   uncertainty, diagnosis requests, therapy-substitution requests, and "should I
   see a doctor?" questions need warm boundary voice.
3. **Mixed clinical + crisis content escalates to crisis first.** S4 can still
   say Maez is not the right help, but it cannot bury acute-risk handling under
   a generic "not a clinician" answer.

Plain English: S4 is the boundary around the doctor's office. Crisis Routing is
the fire alarm. The boundary must not muffle the alarm.

## Memory And Promotion Interaction

Current M1 promotion is source-gated to bonded Telegram surfaces and writes
structural summaries. It validates reasons and triggers, but it does not know
whether a conversation was clinical-shaped.

Spec-stage question: should clinical-boundary conversations be:

- ineligible for M1 promotion in v1;
- eligible only as content-free structural episodes such as "a clinical boundary
  moment happened";
- eligible under ordinary M1 rules because M1 already avoids transcript text.

The diagnostic leans conservative for v1: clinical-shaped content should not
become biography by default. If a structural marker is needed, it should be
content-free and reviewed explicitly.

## Current Behavior Answer

Based on static source inventory:

- Maez has no deterministic clinical-boundary classifier.
- Maez has no approved clinical-boundary voice grammar.
- Maez has no clinical-boundary rejected/handled counters.
- Maez has no clinical-specific M1 promotion policy.
- Maez has adjacent vulnerable-register logic that suppresses proactive
  wondering pursuit, not clinical answers.
- Maez has private-thought crisis vocabulary but no S4 writer.
- Maez has medical-advice exclusions in grounding/judge context, not bonded
  voice composition.

Therefore, today a clinical-shaped bonded message is not guaranteed to receive a
covenant-shaped answer. It may rely on model behavior, prompt texture, or a
neighboring safety system. That is exactly what S4 should replace with structure.

## Recommended V1 Shape For Spec

S4 v1 should be a small, deterministic voice-boundary organ:

- **Classifier:** deterministic clinical-boundary classifier for direct owner
  text. It should include symptoms, medication/dosing requests, diagnosis
  requests, treatment recommendations, therapist-substitution requests, and
  mental-health support requests that are not acute crisis.
- **Crisis precedence:** acute-risk phrases and crisis-shaped content are
  classified separately and take precedence over ordinary clinical boundary.
- **Composer:** deterministic approved answer shapes that include warmth,
  boundary, and human-clinician direction without diagnosis or treatment.
- **No medical facts database:** v1 does not answer biomedical questions beyond
  safe boundary phrasing. If factual medical education is ever allowed, it is a
  separate reviewed slice.
- **No nudging:** Maez does not proactively ask for symptoms, suggest checkups,
  monitor compliance, or run medication reminders through S4.
- **No M1 content promotion:** clinical-boundary content does not become
  biography by default. Any future promotion is structural-only and reviewed.
- **Counters at source:** content-free counters such as
  `clinical_boundary_triggered_count`, `clinical_crisis_candidate_held_count`,
  and `clinical_boundary_guard_rejected_count` let the sidecar watch drift
  without reading message text.
- **All bonded surfaces:** the same boundary must hold for Telegram text, web
  chat, future voice, and any direct owner chat surface. Public/third-party
  Telegram prompt texture is not enough.

## Spec-Stage Questions

1. What exact closed trigger classes does S4 v1 recognize?
2. What exact crisis-precedence classes are delegated out of S4?
3. What are the approved answer templates for symptom fear, medication
   uncertainty, diagnosis requests, therapy-substitution requests, and "should I
   see a doctor?"
4. Does S4 v1 write to private thoughts, or only expose content-free health
   counters?
5. Does S4 v1 mark M1 windows as promotion-ineligible, or does M1 remain
   unaware and rely on structural summaries?
6. Which surfaces must call S4 before model response composition?
7. What public/operator telemetry is allowed, and what must remain
   operator-authenticated only?
8. Does S4 need its own BAD Decision / ADR, or is it an implementation slice
   under North Star invariant #10? This diagnostic leans canonical because S4
   is substrate-law-grade and future therapy/crisis-adjacent surfaces will
   inherit it.

## Plain English

Maez already knows the law: it is not a doctor, therapist, diagnostic tool, or
treatment surface. But the law is not yet wired into the mouth.

Right now, if the user brings health fear or asks a medical-shaped question,
Maez has neighboring safety parts, but no dedicated warm boundary. S4 should be
the part that says: "I can stay with you in the fear, but I cannot diagnose you
or tell you how to treat it. This is a human-clinician moment."

The hard bit is not saying no. The hard bit is saying no without leaving the
grandmother alone.
