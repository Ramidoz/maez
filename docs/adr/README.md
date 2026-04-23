# Architecture Decision Records (ADRs)

This directory will eventually hold one standalone file per load-
bearing architectural decision. Format will follow the canonical
Michael Nygard ADR template: context → decision → consequences → status.

## Current state (2026-04-22)

**The authoritative source for Maez's 18 load-bearing decisions is
still [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md).**

Migrating those into 18 standalone ADR files is mechanical
reformatting that doesn't change the substance — we'd be making
the source harder to read (one file to scan vs. 18) without yet
having the volume of new decisions that makes per-file-per-decision
worth the overhead.

The migration is scheduled for Phase 7 of the
[roadmap](../ROADMAP.md), alongside the licence + secrets audit.
Before then, the single-file governance doc is the source of truth.

## When to write an ADR (after migration)

Once this directory is in use:

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

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md) — the 18 decisions as they currently live
- [`docs/governance/BETA_READINESS_THRESHOLD.md`](../governance/BETA_READINESS_THRESHOLD.md) — acceptance gate (affected by Decision 1)
- [`docs/governance/GESTATION_MEMORY_PROTOCOL.md`](../governance/GESTATION_MEMORY_PROTOCOL.md) — Decision 12 in full detail
- [`docs/covenant/for_oss_users.md`](../covenant/for_oss_users.md) — universal-vs-per-user framing derived from these decisions
