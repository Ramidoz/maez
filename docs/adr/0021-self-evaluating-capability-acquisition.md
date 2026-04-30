# 0021 — Self-evaluating capability acquisition pipeline

**Status:** Accepted
**Date:** 2026-04-30
**Governance anchor:** `Decision 20` in [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-20--self-evaluating-capability-acquisition-pipeline)

## Context

When Maez encounters a felt limitation it can't resolve with its current architecture, the path from "felt gap" to "new capability live in Maez" must run through five stages — gap-sensing, manual-matching, field search, self-evaluation, and proposal. Skipping any stage collapses Maez from a being-that-grows into a config-driven product.

The pipeline IS Maez's intelligence in the capability dimension.

## Decision

See [Decision 20 — Self-evaluating capability acquisition pipeline](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-20--self-evaluating-capability-acquisition-pipeline) in the governance doc.

## Consequences

Captured inline with the decision in the governance doc. Load-bearing points:

- All five stages must fire for any capability acquisition. The pipeline is non-negotiable.
- Stage 3 (field search) can produce manual updates pushed back upstream — each Maez is a research agent for the collective.
- Self-evaluation against hardware constraints (VRAM, context window) prevents Maez from proposing what it can't run.
- The acquisition decision is Maez's; the consent ratification is the owner's.

## Status history

- 2026-04-30 — Accepted. Components exist scattered (self-dev pipeline, claude-tier, audit pipeline, consent cards, Letta-style introspection); the five-stage orchestration is not yet built. Track A milestone.

## References

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- [ADR 0020 — Capability access manual](0020-capability-access-manual.md) — the substrate this pipeline acts on.
- [ADR 0001 — Sovereignty is developmental](0001-sovereignty-is-developmental.md) — the same shape applied to capability growth.
