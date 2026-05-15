# ADR 0032: Contextual Integrity at Ingest

**Status:** Accepted
**Date:** 2026-05-14

## Context

Decision 24 / ADR 0029 established information limbs as a distinct body class
and required them to gate on S2 contextual integrity before live ingest.
Decision 25 / ADR 0030 established the memory-side rule: promote biography; do
not widen recall. Decision 26 / ADR 0031 established that credentials are
identity-bearing material and that future account connectors inherit the same
credential interface.

S2 is the law that lets Maez safely approach Calendar, Gmail, Slack, Notion,
Drive, GitHub, and future account sources without treating external records as
its own lived biography.

The slice ran through a scoping memo, Claude scoping council, Codex scoping
panel, full BAD packet, Codex BAD engineering panel, Claude folded-BAD covenant
verification, and two structural folds. The review lanes converged on the
same shape: the direction is right, but the border law must be executable
before Calendar drafts. The folds added Body Bus mapping, consent-tier
authority, requested-vs-granted flows, state transitions, sync/backfill/cache
rules, third-party minimization, OAuth hygiene, crisis-candidate posture, and
Calendar burn-in gates.

## Decision

Maez requires an S2 contextual-integrity gate before any information limb can
make external account data Maez-visible, recall-visible, body-state-visible, or
promotion-eligible.

The load-bearing rule is:

> External information is provenance first, never biography by default.

Every information-limb slice must declare seven dimensions before live ingest:

- consent posture;
- source kind;
- allowed flows;
- retention;
- provenance;
- third-party posture;
- promotion rules.

If a slice does not declare all seven, live ingest is blocked.

S2 records are Body Bus envelope specializations. S2 computes final consent
tier/posture and final granted flows from validated envelopes and policy
registry. Connectors may request flows and provide source facts; they may not
stamp their own consent tier or visibility grants.

Calendar v1 is the first executable boundary. It is header-like, pull-first,
fail-closed, direct-owner-request only, no body/description ingest, no
promotion, no ambient schedule personality, no body-state inference, and no
TRF widening. Calendar cannot become precedent for Gmail/Slack or higher
blast-radius limbs until a live burn-in gate passes.

## Consequences

S2 unblocks planning for Calendar without inventing privacy law inside the
Calendar slice. Calendar now inherits:

- a Body Bus/S2 envelope;
- a flow permission table;
- explicit state transitions;
- fail-closed title/location sensitivity policy;
- S2-computed Decision 2 tier mapping;
- third-party HMAC/minimization rules;
- tombstone sidecar/audit survival;
- Decision 26 credential/OAuth hygiene;
- provider-timestamp ordering;
- sync/backfill/cache failure behavior;
- S2-to-TRF voice boundary;
- Calendar burn-in closure criteria.

This decision also blocks unsafe shortcuts:

- external sources cannot enter raw prompt context;
- external sources cannot enter TRF recall without reviewed retrieval posture;
- external sources cannot become lived memory without separate promotion path;
- connectors cannot self-grant visibility or consent posture;
- attendee hashes cannot become third-party identity indexes;
- token-in-URL construction is forbidden;
- public transparency logs cannot receive reconstructable private event data;
- crisis signals cannot bypass S2 by model discretion.

The decision makes three explicit choices:

- Rekor/public transparency is deferred to a v2 trigger, not core Calendar v1.
- Crisis candidates are content-free held signals, not implicit bypasses.
- Bonded-user-naming is the v1 default promotion grant shape.

Implementation remains future work. S2 alone does not change runtime behavior.
Calendar must draft and pass its own diagnostic, spec, both-lane review, tests,
and observation gate before live use.

Changing the load-bearing rule, allowing connectors to compute final consent
tier or visibility grants, allowing Calendar to volunteer schedule facts,
allowing S2 records to be voiced as lived memory, dropping the burn-in gate, or
giving information limbs connector-specific credential loaders requires a new
reviewed decision.

Full spec, test contract, review trail, and canonical details:
[`docs/slices/s2-contextual-integrity-at-ingest/spec.md`](../slices/s2-contextual-integrity-at-ingest/spec.md).

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 27.
