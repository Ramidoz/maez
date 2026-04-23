# 0018 — Capacity revocation resolves the chicken-and-egg via face-value trust

**Status:** Accepted
**Date:** 2026 (pre-audit; captured in governance doc at
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-18))
**Governance anchor:** `Decision 18` in the governance doc

## Context

When the owner states that their decision-making capacity is compromised, Maez trusts the statement at face value rather than demanding adversarial proof. This resolves the chicken-and-egg ('prove you're compromised while compromised') with a simple rule: the last known well-stated wish governs.

The full context, rationale, and consequences are in the governance
doc — this ADR is a stable identifier that future decisions can
supersede or amend.

## Decision

See [Decision 18 — Capacity revocation resolves the chicken-and-egg via face-value trust](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-18)
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
