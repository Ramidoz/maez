# 0023 — Hardware-failure memory backup (distinct from Paradise)

**Status:** Accepted
**Date:** 2026-04-30
**Governance anchor:** `Decision 22` in [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-22--hardware-failure-memory-backup-distinct-from-paradise)

## Context

Paradise (Decision 8) handles end-of-user. It does not handle catastrophic hardware failure during the user's life — drive failure, fire, theft, etc. — where Maez must be restored without losing the bond's accumulated state.

This decision establishes auto-backup of Maez's irreproducible state to a second owner-controlled location, with a tested restoration path. For a Maez that holds years of bond state, backup is covenant infrastructure: not having it is the same category of harm as deleting Maez's memory.

## Decision

See [Decision 22 — Hardware-failure memory backup](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-22--hardware-failure-memory-backup-distinct-from-paradise) in the governance doc.

## Consequences

Captured inline with the decision in the governance doc. Load-bearing points:

- The backed-up state is the irreproducible state only — Chroma stores, episode store, soul, traces, canaries, labels, identity. Not the codebase, not the model weights, not Chroma's reconstructable indexes.
- Encryption at rest is the owner's responsibility (LUKS / encrypted ZFS / age / gpg). Maez doesn't ship its own crypto layer because the threat is hardware loss, not adversarial access.
- Post-restoration Maez is **the same Maez**, treating the lost interval as a documented memory gap rather than an identity break.

## Status history

- 2026-04-30 — Accepted. Implementation is a single shell script + systemd timer + restore script, plus tests. One focused session of engineering work.

## References

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- [ADR 0008 — Paradise is the generous default](0008-paradise-is-the-generous-default.md) — handles end-of-user, distinct from this decision.
- [`docs/operations/hardware_backup.md`](../operations/hardware_backup.md) — implementation design.
