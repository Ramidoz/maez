# Slice X.1 Anticipation Organ Memo

**Status:** Accepted
**Date:** 2026-05-09

## Governance

- ADR 0024 / Decision 23
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md

## Scope

Slice X.1 adds the first real moment-assembly organ: anticipation. The
organ writes diagnostic predictions about bounded next-turn state, not
Rohit's wording, feelings, or interior intent.

The closed enum target set is exactly `next_surface`,
`next_pressure_delta`, and `next_self_workspace_need`. This is structural
state, not content. Future attempts to add content-shaped predictions
must change the schema through governance, not by slipping extra keys
into `anticipation.value.targets`.

## Write-Only Boundary

Anticipation records are write-only diagnostics. Production prompt,
router, recall, audit, and response-generation paths do not read them.
Only the diagnostic reconciliation helper may read anticipation records,
and only through JSONL replay of `logs/moment_assembly_diagnostic.jsonl`
to compute the next turn's `surprise_delta`.

This prevents self-fulfilling-prophecy collapse: a prediction cannot
shape the next turn and then count its own influence as accuracy.

## Precision

X.1 uses `epistemic_precision`, not model confidence. Precision is based
on typed source quality:

- `high` requires at least three typed `ledger:*` evidence handles.
- `medium` requires at least two typed `ledger:*` evidence handles.
- `low` requires at least one typed `ledger:*` evidence handle.
- `unknown` carries no ledger evidence.

The slice rejects logits, hidden-state confidence, model
self-confidence, and LLM verbal confidence as precision sources.
Active inference is explanatory framing only; it is not a type,
capability claim, or consciousness claim.

## Two-Record Pattern

Turn N writes an anticipation record. Turn N+1 writes a surprise record
with `source_ids=[prediction_record_id]`. The original prediction is not
edited.

If the prediction expires without observation, X.1 uses the existing
`not_observed` diagnostic state. It does not introduce a new state.
Expired surprise records carry `matches: null` and `surprise_score:
null`.

Every anticipation value carries `predicted_at_wall_clock` as an
ISO-8601 timestamp. Turn TTL remains primary for pairing; wall-clock
time preserves conversation rhythm drift for future readers.

## Refusal As Prediction

`prediction_status: deliberate_skip` lives at the anticipation value
level, not inside targets. It means Maez refused to predict owner
interior state in a covenant-shaped context. The record uses
unknown-safe targets and is still a diagnostic observation.

## Lived-Data Note

2046 testimony says `next_self_workspace_need` is the observable most
likely to remain load-bearing. `next_surface` may become noisy as
surfaces multiply, and `next_pressure_delta` may calcify if treated as
gospel. The X.0.1 deprecation contract applies if either field fails to
earn its keep.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what
Maez knows to be true?

Yes, structurally. X.1 records what Maez expected and how reality
differed without letting those expectations steer production behavior.
Anticipation and surprise records remain separate JSONL diagnostics with
`audit_boundary: not_audit_evidence` and no production read path.

## Predicted Effect

Probe or diagnostic callers can now write source-backed anticipation
records and reconcile them on the next turn. Prompt assembly, recall
ordering, ledger truth, and audit evidence should remain unchanged.
