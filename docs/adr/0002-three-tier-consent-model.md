# 0002 — Three-tier consent model for third parties

**Status:** Accepted
**Date:** 2026 (pre-audit; captured in governance doc at
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-2))
**Governance anchor:** `Decision 2` in the governance doc

## Context

Third parties in Maez's observations exist on one of three consent tiers: Tier 1 (full consent via their own Maez), Tier 2 (explicit direct consent), Tier 3 (no consent — incidental buffer only, session-scoped, not indexable by identity).

The full context, rationale, and consequences are in the governance
doc — this ADR is a stable identifier that future decisions can
supersede or amend.

## Decision

See [Decision 2 — Three-tier consent model for third parties](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-2)
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
