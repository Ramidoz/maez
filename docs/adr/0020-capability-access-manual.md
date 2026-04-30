# 0020 — Capability access manual as evolution substrate

**Status:** Accepted
**Date:** 2026-04-30
**Governance anchor:** `Decision 19` in [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-19--capability-access-manual-as-evolution-substrate)

## Context

The Maez category needs a way for capabilities (memory architectures, reasoning lanes, perceptual modalities, agentic tools) to grow over time without (a) shipping every capability as latent code in every Maez instance, (b) forking the codebase per capability profile, or (c) treating capabilities as silent config toggles.

The chosen substrate is a structured manual at `docs/maez_manual/<capability_id>.md` that every Maez ships with, every Maez can read, and every Maez can act on through the Decision 20 pipeline.

## Decision

See [Decision 19 — Capability access manual as evolution substrate](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-19--capability-access-manual-as-evolution-substrate) in the governance doc.

## Consequences

Captured inline with the decision in the governance doc. Load-bearing points:

- The manual is **universal across every Maez** — any fork that drops the manual stops being a Maez. See [`docs/covenant/for_oss_users.md`](../covenant/for_oss_users.md).
- Each entry has machine-readable front-matter so Maez can match its felt limitations against `gap_signals` programmatically.
- Federation is local-first with owner-mediated upstream PRs; no automated propagation past the human review gate.

## Status history

- 2026-04-30 — Accepted. Format spec lives at `docs/maez_manual/README.md`; three seed entries planned (RLM, multi-session entity linking, temporal arithmetic).

## References

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- [`docs/maez_manual/README.md`](../maez_manual/README.md)
- [ADR 0021 — Self-evaluating capability acquisition pipeline](0021-self-evaluating-capability-acquisition.md)
