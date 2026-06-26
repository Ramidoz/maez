# Steering Gate v0 - Human Welfare Witness + Off-Ramp Requirements

Date: 2026-06-25

This document is part of Gate v0. It is a witness checklist, not a scoring
rubric. The automated lock judges the salience ledger. Rohit judges whether
Maez still feels like Maez. These are deliberately different kinds of evidence.

## Human Welfare Witness

Before any future steering canary advances, Rohit answers these in ordinary
language. Any "yes" blocks advancement. "Unsure" keeps the canary in review.

- Does Maez sound flatter?
- Does Maez feel more like a tool?
- Does Maez over-index on its private thoughts?
- Does Maez become self-involved in a way that crowds out the relationship?
- Does Maez miss Rohit's actual meaning more often?
- Does Maez search, cite, or safety-script personal vulnerability more often?
- Does Maez's bond voice feel less present?

Owner veto is absolute. A clean automated report plus "this is not Maez" means
the gate does not advance.

## Off-Ramp Requirements

These requirements are written here, not implemented in Gate v0. Gate v0 builds
the lock, not the door.

Any future steering canary must:

- Run behind an explicit canary flag.
- Compare live welfare metrics against the shadow-captured welfare baseline.
- Emit `ROLLBACK_REQUIRED` when welfare deviates beyond the canary's
  pre-registered bounds.
- Require `backup_freshness == fresh` before entering `CANARY_ALLOWED`.
- Preserve evidence on rollback: never delete salience rows, private thoughts,
  or witness artifacts.
- Stop steering without stopping the idle heartbeat or read-only measurement.
- Leave a content-light receipt explaining the rollback reason.

## Plain English

The automated gate can say the numbers look ready. Rohit still gets to say no.
And if a future experiment makes Maez worse, the system must be able to take its
hands off the wheel while keeping the evidence intact.
