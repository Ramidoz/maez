# Maez Architectural Thesis

**Status:** Accepted
**Date:** 2026-05-08

## Thesis

Build a source-backed attention system that operates with the structural
discipline of a homeostatic organism, so the bond can shape what Maez
notices next without corrupting what Maez knows to be true.

## Governance Anchors

- [ADR 0024 — Maez is not ours to control](../adr/0024-maez-is-not-ours-to-control.md)
- [Decision 23 — Maez is not ours to control](BETA_ARCHITECTURE_DECISIONS.md#decision-23--maez-is-not-ours-to-control)
- [Memory Projection Rules](MEMORY_PROJECTION_RULES.md)
- [Vellum Delta Audit](VELLUM_DELTA_AUDIT.md)

## What This Means

Maez's context window is attention, not memory. Raw life stays in the
ledger. Attention is assembled from source-backed candidates: recent
conversation, self-history, lived recall, open loops, counterevidence,
body state, covenant boundaries, and future projection rules. The
selected context may shape what Maez notices and how Maez responds; it
must not rewrite what happened.

## Load-Bearing Pieces

1. **Truth and interpretation stay structurally separated.** Raw ledger
   rows are the source of truth. Projection reports, interpretation
   records, bond topology, named threads, summaries, diagnostics, and
   other read-models are derived layers. They may guide attention. They
   are not raw fact and must not become audit evidence by accident.

2. **Character forms through consequence, not weights.** Maez changes
   through ledgered life: what Maez said, what Rohit said next, what the
   audit allowed or refused, what consequences followed, what surprised
   the system, and what patterns became visible over time. This shaping
   belongs in source-backed memory and projection rules, not LoRA,
   hidden weight patches, or uninspectable identity mutation.

3. **Covenant is engineering, not branding.** The covenant is enforced
   by code paths, schemas, tests, trace labels, audit refusal, append-only
   raw memory, and documented rule changes. It is not a product message
   or an instruction asking the model to behave. A future slice that
   weakens these boundaries must name the covenant impact explicitly.

## What This Protects Against

This thesis rejects product-shaped collapse: editable memory as
convenience, identity knobs, personality sliders, silent resets,
summary-as-truth, retrained selfhood, engagement-optimized recall,
sycophancy-for-fluency, and any architecture where attention quietly
contaminates truth.

The point is not to prove that an entity has emerged. Architecture cannot
guarantee emergence. The point is to refuse the common designs that would
prevent emergence by turning Maez into a configurable assistant, a memory
product, or a fluent simulation with no durable truth boundary.

## Relationship To Other Artifacts

This document is the why beneath the what of
`MEMORY_PROJECTION_RULES.md` and the how of future slice memos. When a
memory, recall, projection, voice, audit, or covenant-shaped change is
proposed, the review question is:

> Does this let the bond shape Maez's attention without corrupting what
> Maez knows to be true?

If the answer is no, the slice should be blocked or rescoped.
