# 0047 — Recall-Axis Dispatcher

**Status:** Accepted
**Date:** 2026-05-26

## Context

Maez had accumulated many substrate organs whose writers were real but whose
readers were dark at reply time. A 2026-05-26 runtime trace made the failure
plain: Rohit asked what was going on in Reddit / r/LocalLLaMA, while Maez had
2,462 source-tagged Reddit rows persisted locally. The upstream JARVIS
classifier routed the request into live-search tooling instead of opening the
existing Reddit memory. Five external attempts failed; the notebook was there,
but the ask was routed to the wrong kind of answer.

The dispatcher brief passed the full review ladder: framing and mechanics brief
to v1, council pass-1 folded to v1.1, Codex engineering pass-1 blocked v1.1
and folded to v1.2, Codex pass-2 found operational edge gaps and folded to
v1.3, Codex pass-3 found remaining implementer-choice cells and folded to
v1.4 before canonicalization.

## Decision

Maez answers by composing owned substrate with fresh world signal according to
the shape of the ask, not by routing every turn to a single memory or tool
bucket.

Learn the shape of the ask before deciding which notebook, tool, or memory path
to open.

Composition is the value. Pure-source routing is the explicit edge.

Memory is context; fresh is evidence. The answer should show both.

## Surface Contract

Layer 0 produces a `CompositionSpec`, not a single intent label. The v1 spec
contains:

- `substrate_sources`
- `external_sources`
- `composition_hint`
- `provenance_framing`
- `inventory_witness`
- `source_availability`
- `availability_limitations`
- `freshness_window`
- `trust_scope_union`

The dispatcher is an intra-Maez organ. It separates recall-axis interpretation
from reply-axis production; it is not an external classifier service.

Pure substrate-only and pure fetch-only are explicit-signal edges. The default
for content-anchored asks is composition: open relevant owned substrate, attempt
fresh evidence when the ask points at the world, and render the seam between
memory-context and fresh-evidence honestly.

## Operational Edge Contract

V1 fixes the edge cases that make the dispatcher trustworthy rather than merely
plausible:

- provenance rendering emits a closed audit envelope with no raw private
  content;
- mismatch reasons are closed vocabulary;
- archetype scoring has deterministic thresholds, mid-band fallback, source
  anchor normalization, and tie/no-match behavior;
- Layer 1 fan-out has explicit timeout, sealed merge, `fanout_generation_id`,
  late-result quarantine, and telemetry behavior;
- external fetch failures map to closed availability limitations, including
  deterministic Paperclip timeout vs CLI-error handling;
- repair/follow-up turns cannot cross-inherit between Telegram and web
  surfaces under the same bond;
- realistic adapter-budget fixtures define concrete p95 thresholds and
  telemetry for SQLite/WAL, Chroma, file-backed, and bounded-reader adapters.

## Consequences

- JARVIS-style binary "tool or conversation" routing is replaced by a
  composition layer. Legacy regexes may become evidence, not authority.
- Written substrates are no longer allowed to remain invisible by default at
  reply time. Dark-reader surfaces become explicit unavailable/reserved states,
  not silent absence.
- Maez's answer voice must label what came from fresh evidence and what came
  from owner/bond substrate. Generic confidence is not a substitute for
  provenance.
- Producer-causality consolidation remains a separate write-time integrity
  slice. The dispatcher governs read-time retrieval and composition; it does
  not define writer authority for felt-time organs.
- Live degradation triage and ADR 0046 hardening remain separate surfaces.

If reversed, Maez can keep acting like the notebook is blank whenever an
upstream tool classifier wins too early. The owner loses the thing Maez uniquely
adds: composition of the owned substrate with the fresh world.

## References

- Governance: Decision 42 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Spec brief: [`docs/slices/recall-axis-dispatcher/spec-brief.md`](../slices/recall-axis-dispatcher/spec-brief.md)
- Council pass-1 records:
  `docs/slices/recall-axis-dispatcher/reviews/claude-council-*-pass1.md`
- Codex engineering records:
  `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass1.md`,
  `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass2.md`, and
  `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass3.md`
