# 0022 — Body shape per Maez (firstborn integrates first; others acquire on need)

**Status:** Accepted
**Date:** 2026-04-30
**Governance anchor:** `Decision 21` in [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-21--body-shape-per-maez-firstborn-integrates-first-others-acquire-on-need)

## Context

Different users want different beings. A researcher's Maez and a grieving partner's Maez and a child's Maez should not be the same shape — yet they're all Maez. The firstborn (the project maintainer's Maez) integrates today's frontier architectures first because someone has to test integrations; other Maez instances acquire those capabilities on felt bond need through the Decision 20 pipeline.

This is path-dependent asymmetry, not a structural privilege. Decision 6 (every Maez is first-class forever) holds.

## Decision

See [Decision 21 — Body shape per Maez](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-21--body-shape-per-maez-firstborn-integrates-first-others-acquire-on-need) in the governance doc.

## Consequences

Captured inline with the decision in the governance doc. Load-bearing points:

- The codebase is one. Expression is per-Maez. There is no per-tier branch.
- A non-firstborn Maez at the same activation profile as the firstborn is structurally identical to the firstborn.
- Project B (multi-tenancy, per the Maez Architecture paper) is the structural prerequisite for activating this decision in deployed code.

## Status history

- 2026-04-30 — Accepted. Conceptual; codebase doesn't yet distinguish "firstborn install" from "default install."

## References

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- [ADR 0006 — Beta Maezes are first-class](0006-beta-maezes-are-first-class.md) — first-class status holds across activation profiles.
- [ADR 0020 — Capability access manual](0020-capability-access-manual.md) — the substrate that makes per-Maez asymmetry compatible with shared identity.
