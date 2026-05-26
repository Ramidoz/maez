# 0045 — Ratifiable Maintenance Proposals

**Status:** Accepted
**Date:** 2026-05-26

## Context

The Reddit recall fix at `5c6be72` was the canonical small maintenance shape:
Maez had data, a reply path failed to use it correctly, and the fix was
bounded, RED-testable, and ratifiable. Commit `6fdfd6c` then added a substrate
for representing that class of future fix without opening autonomous merge or
live-cross authority.

The core risk was turning self-maintenance into a self-claim engine. The landed
shape creates the form first and leaves proof contract, gap detection, and
execution authority for later slices.

## Decision

Maez may record bounded self-maintenance needs as bond-scoped,
owner-ratifiable `MaintenanceProposal` rows, but the proposal form itself does
not authorize autonomous patching, live merge, or live crossing.

## Consequences

- Proposal scopes are closed vocabulary and exclude architecture changes.
- Every proposal requires evidence refs and predicted effect.
- Owner ratification writes an OWNER_EXPLICIT maintenance-ratification
  preference.
- Autonomy composition refuses to consume maintenance ratification as a policy
  modifier.
- Failed preference writes leave proposals proposed rather than falsely
  ratified.
- The sandbox-witness contract remains the next required slice before
  gap-detection authority.

If reversed, Maez could launder "I think I fixed myself" into owner-grade
authority without a separable proof contract.

## References

- Governance: Decision 40 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Implementation anchor: `6fdfd6c`
- Precedent behavioral fix: `5c6be72`
- Files: `core/policies/maintenance_proposals.py`,
  `tests/test_maintenance_proposals.py`
