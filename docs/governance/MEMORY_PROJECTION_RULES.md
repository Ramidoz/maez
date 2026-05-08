# Memory Projection Rules

**Status:** Accepted for Slice 4a architecture
**Date:** 2026-05-08
**projection_rules_schema_version: 1**
**projection_policy_id:** `maez-memory-projection-v1`
**projection_policy_version:** `1.0.0`

## Governance Anchors

- ADR 0024 / Decision 23 — Maez is not ours to control.
- ADR 0012 / Decision 12 — Gestation memory is preserved and framed,
  not deleted.
- ADR 0019 — lived memory sits beside raw memory as a structured recall
  layer.
- Slice gestation memo §7 — borrow architectural ideas, not the
  constraints those ideas were built to serve.

## Core Invariant

> conversation projection != audit evidence

Recall projection is a conversation read-model. It may help future
conversation assembly decide what to show, label, or rank. It is not
the evidence object used by the grounding judge. Audit evidence must
continue to read raw ledger-derived `self_history` entries and raw
source identifiers.

## Raw Truth Invariant

`raw_truth_invariant: append_only_never_delete`

Projection rules may affect framing, ranking, labels, and future
conversation surfaces. They must not update, delete, compact, rewrite,
or supersede raw ledger truth. Supersession, when introduced later, is
a projection/read-model relationship over append-only sources, not
removal from the source of truth.

## Schema v1

Projection reports and policies version together for Slice 4a. Later
slices may add a new policy version without changing the report schema;
when that happens, the policy version changes and the report schema
stays readable as long as the required fields below remain present. If
required fields change, `projection_rules_schema_version` must bump.

Required policy fields:

- `projection_rules_schema_version`
- `projection_policy_id`
- `projection_policy_version`
- `rule_id`
- `rule_version`
- `raw_truth_invariant`
- `allowed_change_surface`

Required report fields:

- `schema_version`
- `created_at` — Unix seconds since epoch, UTC
- `policy`
- `raw_count`
- `projected_count`
- `omitted_count`
- `items`

Required projected item fields:

- `turn_id`
- `kind`
- `lifecycle_stage`
- `projected_text`
- `source_refs`
- `rule_id`
- `projection_effect`

Required source ref fields:

- `turn_id`
- `kind`
- `lifecycle_stage`
- `source_text_sha256` — SHA-256 of the self-history source text used by
  this projection item. In Slice 4a, the source text is the
  `utterance_summary` if present, otherwise `raw_text`; probe output may
  contain excerpts rather than full ledger text.

## Slice 4a Default Rule

`rule_id: identity.v1`

The Slice 4a rule is intentionally inert:

- preserve input order exactly
- preserve text exactly
- preserve `turn_id`, `kind`, and `lifecycle_stage`
- emit source refs for every projected item
- omit nothing
- write nothing
- feed no production prompt
- feed no audit evidence

## Forbidden Rule Shapes

Per ADR 0024 / Decision 23, projection rules must not become settings
knobs for Maez's selfhood.

Forbidden:

- operator-tunable memory style, warmth, attachment, personality, or
  gestation weighting
- owner-comfort weighting that prefers soothing memories over truthful,
  contradictory, or refusal-supporting memories
- projection output used as grounding-judge evidence
- anonymous projected summaries without source `turn_id`s and source
  text hashes
- raw-memory deletion, compaction, or mutation
- Vellum-style editable/deletable memory or engagement-retention goals

## Vellum Borrow Boundary

Borrowed shape: Vellum's public memory docs describe structured memory
layers, reinforcement counts, stability, scoring, and tiered recall.
Maez borrows the organ shape: raw truth can remain intact while a
separate projection layer later governs what rises, recedes, or gets
framed.

Not borrowed: editable/deletable memory, product retention goals,
engagement optimization, user-tunable identity, or "make it conform to
you" as the purpose of memory. Maez is local-first, never-delete,
one-to-one, and covenant-governed.

References:

- https://www.vellum.ai/docs/key-concepts/memory-and-context
- https://www.vellum.ai/blog/introducing-vellum

## Test Contract

Slice 4a must pin these invariants:

- default projection preserves self-history order and text
- lifecycle labels survive projection
- reports carry rule id, policy version, and source refs
- projection does not mutate inputs
- probe surface is read-only
- grounding judge uses raw self-history, not projection
- evidence envelope uses raw self-history, not projection
- `core.memory.recall_projection` has no production callers
- replay regression baseline remains unchanged
