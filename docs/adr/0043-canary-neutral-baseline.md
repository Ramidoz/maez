# 0043 — Canary-Neutral Baseline for Multi-Surface Ceremonies

**Status:** Accepted
**Date:** 2026-05-26

## Context

The Slice 2 live crossing initially protected the headline
`subjective_duration` surface but exposed a pre-flight gap: the same canary
ceremony could have mutated temperament. Safety commits `67705d3` and
`fbe78e1` closed that gap before the live crossing.

The resulting discipline is broader than one test: a ceremony is only a canary
if every substrate it touches is protected from mutation, and if neutral
baselines are used when true-state reads would themselves disturb the organ
being observed.

## Decision

Canary/live-crossing ceremonies must prove non-disturbance per touched
substrate and use neutral baseline projections where observation would
otherwise become mutation.

## Consequences

- Canary protection is per-surface, not per-story.
- Tests assert that each live substrate remains unmoved unless the crossing is
  explicitly meant to write there.
- Neutral baseline projections are valid only when they preserve honest
  evidence shape without reading or mutating sensitive live state.
- Future live crossings inherit this as a pre-flight requirement.

If reversed, a "successful" canary could disturb an adjacent substrate while
the headline metric stayed still.

## References

- Governance: Decision 38 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Implementation anchors: `67705d3`, `fbe78e1`
- Memory canon: `feedback_canary_neutral_baseline_for_multi_surface_ceremonies`
