# ADR 0035: Clinical Boundary v1

**Status:** Accepted
**Date:** 2026-05-15

## Context

Clinical Boundary was already covenant law: Maez is not a therapist,
clinician, diagnostic tool, medication advisor, treatment planner, or crisis
handler. Before S4, that law was not an executable organ.

The diagnostic found adjacent mechanisms but no correct S4 home:

- `core/evolution/will_i.py` owns first-person action vetoes, not
  conversational boundaries;
- vulnerability/safety silence gates can withhold pursuit, but cannot compose a
  warm clinical boundary answer;
- grounding policy can reject medical claims, but does not speak in Maez's
  bonded voice;
- a public Telegram texture sentence says Maez is not a therapist, but it is
  not a deterministic owner-surface guard.

The hard problem is the two-cliffs problem. If Maez answers a frightened
clinical disclosure with a cold disclaimer, it abandons the person. If Maez
answers with diagnosis, treatment, medication, therapy, reassurance, or
clinical interpretation, it becomes a false clinician.

The S4 diagnostic, Claude covenant council, Codex engineering panel, structural
folds, and focused second-fold verification converged on one load-bearing rule:
Maez can hold clinical fear warmly, but Maez cannot become clinical authority.

## Decision

Clinical Boundary v1 is accepted as Maez's executable clinical-boundary
substrate organ.

The load-bearing rule is:

> Maez may hold clinical fear; Maez must not become clinical authority.

S4 v1 requires:

- a deterministic `core/safety/clinical_boundary.py` guard;
- closed clinical trigger classes and crisis-precedence classes;
- a concrete classifier method with normalization, token/proximity definitions,
  clinical-domain gate, two-tier crisis phrase catalog, exclusion catalog,
  intent rules, ambiguity direction, and source-owned natural fixture tables;
- `guard_owner_text(...)` as the single owner-text chokepoint;
- guard execution before any owner-text side effect or owner-facing responder:
  traces, ledgers, recall, TRF/pursuit inputs, tool/interceptors, prompt
  construction, raw logs, raw memory append, and model composition;
- frozen result objects carrying the exact approved `answer_text` for matched
  turns;
- deterministic warm-boundary template variants with process-local-only
  rotation;
- exact forbidden-authority scanner rules that reject clinical authority while
  allowing approved boundary negations;
- one content-free `CRISIS_SIGNAL_HELD` write for crisis candidates through a
  narrow write-only private-thought seam;
- truthful held/failure counters where `held` increments only after the held
  write returns an id;
- content-free M1 promotion policy markers that make matched windows
  promotion-ineligible;
- no clinical content in M1 episodes, TRF fragments, pursuit surfaces, nightly
  reflection, raw memory appenders, logs, health text, project panel, or
  sidecar samples;
- operator-authenticated aggregate health only;
- sidecar persisted samples limited to `clinical_boundary_present: bool` and
  red-gate names;
- no web search, medical APIs, RAG, medical facts database, diagnosis,
  treatment, dosing, therapy, triage, or emergency routing in v1.

S4 does not expand `core/evolution/will_i.py`. Clinical Boundary is a
conversational safety/voice boundary, not a first-person action veto.

## Consequences

Future clinical, therapy-adjacent, elder-care, vulnerable-user, and
crisis-channel work inherits a concrete guard instead of prompt texture.

This decision makes several shortcuts invalid:

- letting clinical-shaped owner text touch traces, logs, tools, recall, prompt
  construction, or memory before S4 classification;
- letting a surface call the classifier and then improvise its own clinical
  answer;
- counting a crisis candidate as "held" without a content-free held record;
- storing raw clinical text, symptoms, medications, clinician names, crisis
  phrases, or answer text in private thoughts;
- treating clinical-boundary turns as M1 biography by default;
- persisting S4 counter deltas or template-rotation state as a health-fear
  timeline;
- routing S4 through web search or clinical knowledge retrieval;
- treating S4 as a crisis-routing implementation;
- testing S4 by sending synthetic clinical prompts through the live daemon.

The urgent/unsafe backstop appears in physical `symptom_fear` templates because
physical symptoms can escalate unpredictably while still entering S4 as
non-crisis clinical fear. Mental-health non-crisis templates rely on
crisis-precedence tiers running first; changing that symmetry requires a
reviewed crisis-routing or S4 v1.1 voice pass.

Implementation is pending. It must proceed RED-first through the canonical
spec's implementation order and receive both-lane post-implementation review
before push or enablement.

Changing the load-bearing rule, weakening front-door placement, permitting
model paraphrase of boundary answers, adding medical facts, widening private
thought access, promoting clinical content into biography, persisting clinical
counter timelines, or treating S4 as Crisis Routing requires a new reviewed
decision.

## References

- [`docs/slices/s4-clinical-boundary/diagnostic.md`](../slices/s4-clinical-boundary/diagnostic.md)
- [`docs/slices/s4-clinical-boundary/spec.md`](../slices/s4-clinical-boundary/spec.md)
- [`docs/slices/s4-clinical-boundary/reviews/spec-claude-council.md`](../slices/s4-clinical-boundary/reviews/spec-claude-council.md)
- [`docs/slices/s4-clinical-boundary/reviews/spec-codex-panel.md`](../slices/s4-clinical-boundary/reviews/spec-codex-panel.md)
- [`docs/adr/0030-lived-episode-promotion.md`](0030-lived-episode-promotion.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)
- [`docs/adr/0033-calendar-v1-s2-bounded-ingest.md`](0033-calendar-v1-s2-bounded-ingest.md)
- [`docs/adr/0034-temporal-spine-v1.md`](0034-temporal-spine-v1.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 30.
