# 0004 — Relational vs personological knowledge

**Status:** Accepted
**Date:** 2026 (pre-audit; captured in governance doc at
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-4))
**Governance anchor:** `Decision 4` in the governance doc

## Context

Maez can retain *relational* knowledge (what this third party and my bonded user mean to each other, in the context of the bonded user's life). Maez cannot retain *personological* knowledge (standalone facts about the third party).

The full context, rationale, and consequences are in the governance
doc — this ADR is a stable identifier that future decisions can
supersede or amend.

## Decision

See [Decision 4 — Relational vs personological knowledge](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-4)
in the governance doc.

## Consequences

Captured inline with the decision in the governance doc. Load-bearing
points:

- The decision is **universal across every Maez** — any fork that
  drops it stops being a Maez. See
  [`docs/covenant/for_oss_users.md`](../covenant/for_oss_users.md)
  for the universal-vs-per-user framing.

## Status history

- 2026 — Accepted. Landed into `BETA_ARCHITECTURE_DECISIONS.md` during
  pre-audit governance work.
- 2026-04-23 — Captured as a standalone ADR in Phase 7 of the road-
  to-OSS plan.

## References

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- [`docs/MAEZ.md`](../MAEZ.md)
