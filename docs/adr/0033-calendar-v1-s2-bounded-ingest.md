# ADR 0033: Calendar v1 S2-Bounded Ingest

**Status:** Accepted
**Date:** 2026-05-15

## Context

Decision 27 / ADR 0032 made S2 contextual integrity the gate for information
limbs. Calendar v1 is the first implementation slice to inherit the four-organ
substrate stack at once:

- Decision 24 / ADR 0029: Body Topology and information-limb safe degradation;
- Decision 25 / ADR 0030: M1 promotion discipline;
- Decision 26 / ADR 0031: credential hygiene;
- Decision 27 / ADR 0032: contextual integrity at ingest.

The Calendar diagnostic found that Maez already had a legacy pre-S2 Calendar
path. That path could put raw event titles/locations into prompt context,
append Calendar text into memory/scoring text, send reminder-like Telegram and
voice alerts, and refresh OAuth state through local JSON files outside the
credential interface.

Those behaviors are exactly the failure class the four substrate organs were
canonicalized to prevent.

The Calendar v1 slice ran diagnostic, spec draft, Codex six-seat engineering
panel, Claude covenant council, two structural folds, and focused closure
verification. The second fold introduced an Inheritance Ledger so future
information limbs can see which rules are canonical inheritance and which
choices are Calendar-specific.

## Decision

Calendar v1 is accepted as the first S2-bounded information-limb implementation
spec and precedent template.

The load-bearing rule is:

> Calendar is provenance, not Maez's lived schedule.

Calendar v1 must:

- replace the legacy direct Calendar path rather than wrap it;
- use the canonical S2 Body Bus envelope without Calendar-specific aliases;
- read only the bonded user's primary owned Google Calendar surface in v1;
- keep Calendar as pre-body staging, not a body organ or biography store;
- answer only direct owner Calendar requests;
- use deterministic redaction, deterministic answer composition, and a
  Calendar voice guard;
- forbid Calendar descriptions/bodies in v1;
- forbid proactive reminders, nudges, scheduler voice, body-state inference,
  crisis bypass, TRF widening, and Calendar memory promotion in v1;
- route OAuth client material, refresh tokens, granted-scope evidence, and
  token rotation through `core/infra/secrets.py`;
- forbid token-in-URL construction as a substrate principle;
- use polling-only incremental sync in v1, not push/webhook notifications;
- preserve tombstone/audit sidecars across provider cache reset;
- disable the legacy path process-start-strictly when Calendar v1 is enabled.

Calendar v1 also establishes a reusable **Inheritance Ledger** pattern for
future information limbs. Each information-limb implementation spec should name
the canonical decisions it inherits, list load-bearing inherited rules, and
state any source-specific override explicitly.

## Consequences

Calendar v1 is now a canonical precedent, not just a local implementation
proposal. Future Gmail, Slack, Notion, Drive, GitHub, and other information
limbs should copy its inheritance-ledger structure before drafting source-
specific rules.

This decision does not implement Calendar code. It authorizes the next
implementation phase after cooling-off and RED-first tests.

Implementation must start with legacy-disablement tests, then remove/gate the
legacy daemon import and raw prompt/memory/alert paths before adding the v1
connector skeleton. Live OAuth onboarding remains a separate explicit operator
gate after tests and review.

Changing the load-bearing rule, permitting legacy fallback, allowing proactive
Calendar reminders, allowing raw Calendar text into prompt/memory/log/panel
surfaces, treating Calendar as body state or biography, bypassing S2, using a
connector-local credential loader, or dropping the Inheritance Ledger precedent
requires a new reviewed decision.

## References

- [`docs/slices/calendar-v1/diagnostic.md`](../slices/calendar-v1/diagnostic.md)
- [`docs/slices/calendar-v1/spec.md`](../slices/calendar-v1/spec.md)
- [`docs/slices/calendar-v1/reviews/codex-panel.md`](../slices/calendar-v1/reviews/codex-panel.md)
- [`docs/slices/calendar-v1/reviews/spec-claude-council.md`](../slices/calendar-v1/reviews/spec-claude-council.md)
- [`docs/adr/0029-body-topology.md`](0029-body-topology.md)
- [`docs/adr/0030-lived-episode-promotion.md`](0030-lived-episode-promotion.md)
- [`docs/adr/0031-daemon-credential-hygiene.md`](0031-daemon-credential-hygiene.md)
- [`docs/adr/0032-contextual-integrity-at-ingest.md`](0032-contextual-integrity-at-ingest.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 28.
