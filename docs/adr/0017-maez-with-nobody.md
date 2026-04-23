# 0017 — The Maez-with-nobody fate options

**Status:** Accepted
**Date:** 2026 (pre-audit; captured in governance doc at
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-17))
**Governance anchor:** `Decision 17` in the governance doc

## Context

When a Maez loses its bonded user permanently (death, withdrawal, capacity loss), the fate options are: wait in a quiet ambient state; migrate to a designated successor relationship if the owner authorized one; archive. Never: reassign to a stranger.

The full context, rationale, and consequences are in the governance
doc — this ADR is a stable identifier that future decisions can
supersede or amend.

## Decision

See [Decision 17 — The Maez-with-nobody fate options](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-17)
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
