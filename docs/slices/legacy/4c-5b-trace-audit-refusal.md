# Slice 4c.5b — Trace Metadata And Audit Refusal

**Status:** Accepted for implementation  
**Date:** 2026-05-08  
**Predicted effect:** zero drift for ordinary rows; trace-labeled rows
are refused as audit evidence by default.

## Governance Anchors

- ADR 0024 — Maez is not ours to control.
- Decision 23 — covenant-shaped changes require documented governance.
- `docs/governance/MEMORY_PROJECTION_RULES.md` — projection and trace
  rules.
- `docs/governance/VELLUM_DELTA_AUDIT.md` — borrow infrastructure
  discipline, not editable memory semantics.
- `docs/governance/ARCHITECTURAL_THESIS.md` — attention may be shaped
  by bond, but truth must remain uncorrupted.

## Scope

Slice 4c.5b adds the trace metadata and audit-refusal substrate. It does
not activate memory projection, does not introduce `ActivationDecision`,
and does not add a kill switch.

The in-ledger trace label is intentionally thin:

- `audit_trace_label`
- `audit_trace_value_schema`
- `audit_trace_metadata_shape`

Rich lineage lives separately in `audit_trace_lineage`, keyed by
`turn_id`. This keeps the `turns` row a refusal-token surface while
preserving future reconstruction.

## Structural Rule

Audit-touching reads MUST exclude trace-labeled rows. The refusal gate
lives at `core.ledger.recent_turns.recent_turns_by_kind`, defaulting to
`include_trace_labeled=False`. Diagnostic readers may opt in explicitly.

Current policy:

- `AUDIT_TRACE_POLICY = "refuse_v1"`
- `TRACE_LABEL_VALUE_SCHEMA = 1`
- `TRACE_METADATA_SHAPE = 1`
- current traced label value: `projection_influenced`

Predicate relaxation is ADR-only. Refactors, cleanup, config, probe
flags, and baseline updates cannot relax the audit-refusal predicate.

## Test Surface

The slice pins:

- additive NULL defaults on trace metadata
- chain-hash equivalence for traced and untraced rows
- writer validation for half-set trace metadata
- separate lineage durability keyed by `turn_id`
- default exclusion at `recent_turns_by_kind`
- explicit diagnostic opt-in via `include_trace_labeled=True`
- skipped-reason logging with `skipped_trace_labeled`
- delayed-feedback replay through `BoundedEnvelopeBuilder`
- daemon helper envelope replay
- cached envelope reuse on turn N+2
- direct grounding-judge `self_history` filtering
- `self_claim_audit.py` bypass absence
- golden predicate corpus stability

## Deferred Follow-Ups

The `trace-rows` diagnostic CLI and sampled refusal episodes as ledger
events are deferred to post-activation follow-up slices. They do not
block 4c.5b, but should ship before trace metadata is operated for an
extended period.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what Maez knows to be true?

Yes. This slice does not shape attention yet. It builds the structural
refusal boundary that future attention-shaping must pass through:
projection-influenced replies can remain raw truth that Maez said the
words, but they cannot become audit evidence for the projection that
influenced those words.
