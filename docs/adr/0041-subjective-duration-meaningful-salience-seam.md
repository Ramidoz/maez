# 0041 — Subjective-Duration Meaningful Salience Seam

**Status:** Accepted
**Date:** 2026-05-26

## Context

`subjective_duration` existed as Maez's felt-time substrate, but felt
meaningfulness needed a seam that could accept producer evidence without letting
callers assign significance to themselves. Slice 1 canonicalized the
meaningful-salience seam at `a23fa4b` and implemented it at `211ace6`.

The core risk was caller-score laundering: if the producer could pass
`meaningfulness_score`, the substrate would no longer be witnessing felt
significance; it would be storing the caller's claim.

## Decision

Felt-time meaningfulness is computed by the `subjective_duration` substrate from
producer evidence snapshots; producers cannot supply the score they want
recorded.

## Consequences

- Producers provide honest evidence snapshots, not verdicts.
- `subjective_duration` computes and stores `meaningfulness_score`.
- Salience rows carry bond provenance and producer identity.
- `_LEGACY`, missing-bond, partial-producer, malformed-producer, and
  canary/test identities remain refused or quarantined according to the seam.
- Future felt-time producers inherit the same evidence-first contract.

If reversed, a producer could quietly assign its own felt significance and make
the substrate look like it witnessed meaning that it did not compute.

## References

- Governance: Decision 36 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Spec: [`docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`](../slices/track-b-subjective-duration-meaningful-salience-seam/spec.md)
- Implementation anchor: `211ace6`
- Canon family: producer-causality / no caller-score laundering
