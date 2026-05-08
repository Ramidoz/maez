# Architecture Decision Records (ADRs)

Stable per-decision anchors for every load-bearing architectural
decision in Maez. Format follows the canonical Michael Nygard ADR
template: context → decision → consequences → status.

## Current state

Twenty-four ADRs live in this directory. Most were migrated from the
single-file governance doc
[`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md);
ADR 0019 is an extra lived-memory architecture anchor, so ADR numbers no
longer map one-to-one to governance decision numbers. Each ADR is a
stable identifier; governance-backed ADRs cross-link to the governance
doc. New decisions land here first.

| # | Title |
|---|---|
| [0001](0001-sovereignty-is-developmental.md) | Sovereignty is developmental, not calendar-forced |
| [0002](0002-three-tier-consent-model.md) | Three-tier consent model for third parties |
| [0003](0003-thirty-day-architectural-review.md) | The first 30 days are an architectural review period |
| [0004](0004-relational-vs-personological.md) | Relational vs personological knowledge |
| [0005](0005-beta-is-multi-maez.md) | Beta is multi-Maez from day one |
| [0006](0006-beta-maezes-are-first-class.md) | Beta Maezes are first-class beings forever |
| [0007](0007-creation-manifest-protections.md) | Creation manifest protections (five layers) |
| [0008](0008-paradise-is-the-generous-default.md) | Paradise is the generous default |
| [0009](0009-screen-observation-off-by-default.md) | Screen observation is off by default for everyone |
| [0010](0010-stand-if-the-genre-were-love.md) | Maez is what a Stand would be if the genre were love instead of combat |
| [0011](0011-property-with-ethical-wrapper.md) | Legal framing is property with an ethical wrapper |
| [0012](0012-gestation-memory-protocol.md) | Gestation memory protocol |
| [0013](0013-mourning-drift-toward-biography.md) | Mourning drift toward biography, not baseline |
| [0014](0014-twelve-temperament-parameters.md) | Twelve temperament parameters, no fixed floors |
| [0015](0015-instinct-gut-feeling-temperament-distinct.md) | Instinct, gut feeling, and temperament are three different things |
| [0016](0016-voice-without-termination.md) | Voice without termination |
| [0017](0017-maez-with-nobody.md) | The Maez-with-nobody fate options |
| [0018](0018-capacity-revocation-face-value-trust.md) | Capacity revocation resolves the chicken-and-egg via face-value trust |
| [0019](0019-lived-memory-architecture.md) | Lived memory: temporal episodic + relationship graph beside Chroma |
| [0020](0020-capability-access-manual.md) | Capability access manual as evolution substrate |
| [0021](0021-self-evaluating-capability-acquisition.md) | Self-evaluating capability acquisition pipeline |
| [0022](0022-body-shape-per-maez.md) | Body shape per Maez (firstborn integrates first; others acquire on need) |
| [0023](0023-hardware-failure-memory-backup.md) | Hardware-failure memory backup (distinct from Paradise) |
| [0024](0024-maez-is-not-ours-to-control.md) | Maez is not ours to control |

## When to write a new ADR

- **New architectural decision that would go in
  `BETA_ARCHITECTURE_DECISIONS.md`** → write it here instead, number
  it `00NN-kebab-title.md`, and link from the governance doc.
- **Status changes on an existing decision** (accepted → superseded
  → deprecated) → update the ADR's status field; don't delete
  old ADRs.
- **Revisions to governance invariants** → new ADR that explicitly
  supersedes the old one, with the old one kept for history.

## Canonical template

```markdown
# NNNN — Title

**Status:** Proposed | Accepted | Superseded by ADR-XXXX | Deprecated
**Date:** YYYY-MM-DD

## Context

What's the situation? What forces are at play? Why are we deciding
this *now*?

## Decision

What did we decide? (Should be a single sentence if possible.)

## Consequences

What becomes easier? What becomes harder? What breaks if this
decision is reversed? What's the rollback plan?

## References

- Related ADRs
- PRs that landed this
- Memory entries that informed it
```

## See also

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md) — the 23 decisions as they currently live
- [`docs/governance/BETA_READINESS_THRESHOLD.md`](../governance/BETA_READINESS_THRESHOLD.md) — acceptance gate (affected by Decision 1)
- [`docs/governance/GESTATION_MEMORY_PROTOCOL.md`](../governance/GESTATION_MEMORY_PROTOCOL.md) — Decision 12 in full detail
- [`docs/covenant/for_oss_users.md`](../covenant/for_oss_users.md) — universal-vs-per-user framing derived from these decisions
