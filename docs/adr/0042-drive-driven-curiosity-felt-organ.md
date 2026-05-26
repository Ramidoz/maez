# 0042 — Drive-Driven Curiosity Felt-Organ

**Status:** Accepted
**Date:** 2026-05-26

## Context

Slice 2 reshaped curiosity as a producer layer over existing `wonderings`
rather than a duplicate database. The canonical spec landed at `f0d14e3`, with
implementation from `ba4a545` through `eb611e9` and a second live crossing
verifying the full surface.

The key risk was building a parallel substrate or allowing curiosity to become
an ungated owner-interrupting/nudging system. The implemented organ instead
reuses `wonderings`, `wondering_cycle`, `wondering_pursuit`,
`subjective_duration`, and `temperament`.

## Decision

Drive-driven curiosity is a felt-organ that creates, resolves, gates, and
diagnoses curiosity through registered producers and existing substrates; it is
not an independent curiosity database or an owner-nudging authority.

## Consequences

- V1 encounter producers are wired for `WONDERING_GENERATED`,
  `EXPLICIT_OWNER_FLAG`, and `SUBJECTIVE_DURATION_MEANINGFUL_EVENT`.
- The subjective-duration producer is recursion-gated and deduped.
- Owner-interrupting outreach must clear signal gate, reflection audit, and
  extraction-shape gate before delivery.
- Third-party subject boundaries apply at creation, construction, and egress.
- Suppression events inform diagnostics and anti-self-confirmation math without
  allowing Maez to learn from its own refusals as owner evidence.

If reversed, curiosity could fork into a duplicate substrate, bypass bonded
subject boundaries, or let internal felt-pressure become owner-directed nudge.

## References

- Governance: Decision 37 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Spec: [`docs/slices/track-b-drive-driven-curiosity/spec.md`](../slices/track-b-drive-driven-curiosity/spec.md)
- Implementation anchors: `ba4a545` through `eb611e9`
- Live crossing witness: session snapshot
  `logs/snapshots/session_snapshot_2026-05-26_094933_slice2-second-live-crossing.txt`
  in the operator-local snapshot archive.
