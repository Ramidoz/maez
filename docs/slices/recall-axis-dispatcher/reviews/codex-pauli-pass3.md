# Pauli Review — Codex Engineering Pass-3 Closure Audit

**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.3
**Controlling brief:** `reviews/codex-engineering-pass3-brief.md`
**Lens:** boundary conditions, impossible states, closed vocabularies, product-table legality, deterministic tie behavior, reserved/unavailable states, invariant contradictions.

## Verdict Summary

**STILL OPEN**

v1.3 closes several pass-2 operational gaps materially, but three of the six closure batches still leave implementer-choice surfaces:

- Batch 1 audit metadata payload: mostly closed, but the “closed envelope” still contains an unconstrained `mismatch_reason`.
- Batch 2 tie/no-match source selection: score band between `no_match_below` and `min_accept` is undefined; reserved class tie behavior is also under-specified.
- Batch 4 external error mapping: `ARXIV_OR_PAPERCLIP` uses `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, which is not a deterministic closed mapping.
- Batch 6 realistic p95 adapter budgets: fixture classes are named, but concrete p95 thresholds/source counts/measurement protocol remain unspecified.

Batches 3 and 5 are closed.

## Per-Batch Closure Table

| Batch | v1.3 Change Cited | Verdict | Evidence |
| --- | --- | --- | --- |
| 1. Audit metadata payload | `Audit metadata contract`, lines 214-235; refusal enum lines 547-560; R#30a lines 761-762 | STILL OPEN | Closed field list exists and no-raw-private-content is stated, but `mismatch_reason` has no closed vocabulary. |
| 2. Tie / no-match source selection | Scoring constants lines 260-267; tie/no-match rules lines 268-277; R#28a lines 758-759 | STILL OPEN | `top_score` band between `no_match_below=0.50` and `min_accept=0.62` is not specified; reserved class handling is only stated for no-match fallback. |
| 3. Fan-out cancellation / late results | Cancellation semantics lines 351-357; D12 lines 669-671; R#32a lines 764-765 | CLOSED | Per-branch timeout, global seal, generation-id ignore, bounded grace/quarantine, and telemetry are specified. |
| 4. External error mapping / stop conditions | Error table lines 399-416; R#33a lines 766-767 | STILL OPEN | `ARXIV_OR_PAPERCLIP` timeout / CLI error maps to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, leaving implementer choice. |
| 5. Cross-surface repair isolation / post-repair validation | Repair FSM lines 427-436; R#36-R#37 lines 770-771 | CLOSED | Keying, freshness identity, TTL, cross-surface isolation, and post-repair validation refusal are specified. |
| 6. Realistic p95 adapter budgets / telemetry | R#38-R#39 lines 772-773; RED split line 775; D13 lines 673-675 | STILL OPEN | Realistic fixture categories are named, but p95 thresholds, realistic source counts, and measurement protocol are not concrete enough for reproducible tests. |

## Findings

### STILL OPEN — Batch 1: `mismatch_reason` Breaks the Closed Audit Envelope

**Lines:** `spec-brief.md:214-235`, `spec-brief.md:547-560`

v1.3 requires `core/dispatcher/provenance_renderer.py` to emit a “closed audit envelope” with no raw private content and a required field list. That closes most of Batch 1. The boundary problem is that `mismatch_reason` is required at lines 232 and 235, but no closed vocabulary for mismatch reasons is defined. `DispatcherRefusalReason` is closed at lines 547-560, but `mismatch_reason` is separate and unconstrained.

Why this fails closure: a closed envelope with an open-ended reason string is not fully closed. Different implementers could emit `template_mismatch`, `bad template`, `wrong_role`, or free-form prose, and audit consumers would have to guess.

Closure criteria: v1.3 should define a closed `ProvenanceAuditMismatchReason` vocabulary or state that `mismatch_reason` must be one of a named closed enum. It should also say when `mismatch_reason` is null/absent versus populated.

### STILL OPEN — Batch 2: Mid-Band Scores Are Undefined

**Lines:** `spec-brief.md:260-277`, `spec-brief.md:758-759`

The scoring constants define:

- `min_accept = 0.62`
- `multi_match_delta = 0.04`
- `no_match_below = 0.50`

The no-match rule only triggers when `top_score < no_match_below` at line 273. The outright-win rule only triggers when score is at least `min_accept` at line 270. That leaves `0.50 <= top_score < 0.62` undefined.

Why this fails closure: this is exactly the kind of impossible-state gap Pauli should catch. A real query can land at `0.55`; v1.3 does not say whether that is low-confidence no-match, fallback hybrid, ask-for-clarification, or stable-order class selection.

There is a second boundary issue: line 271 says if multi-match cannot be represented by the legal product table, explicit-edge lexemes win, then stable manifest order breaks the tie. But reserved class `K_GRAPH_ASSISTED_RELATIONAL` is part of manifest order at lines 563-579, and reserved-source behavior is specified for no-match fallback at line 277, not for accepted-score ties.

Closure criteria: v1.3 should define:

- exact behavior for `no_match_below <= top_score < min_accept`;
- whether that band sets `inventory_witness=UNKNOWN`, asks clarification, or falls back deterministically;
- reserved-class/source handling during tie-break, not only during no-match fallback.

### CLOSED — Batch 3: Fan-Out Cancellation / Late Results

**Lines:** `spec-brief.md:351-357`, `spec-brief.md:669-671`, `spec-brief.md:764-765`

This is closed. v1.3 defines per-branch timeout behavior, global deadline behavior, merge-set sealing, generation-id ignore for late returns, bounded cleanup grace, quarantine, and telemetry fields. R#32a directly tests that late results cannot mutate prompt output.

No material closure gap from Pauli’s lens.

### STILL OPEN — Batch 4: `ARXIV_OR_PAPERCLIP` Error Mapping Is Not Closed

**Lines:** `spec-brief.md:399-416`, especially line 412

Most of the external-source table is deterministic. The exception is:

`ARXIV_OR_PAPERCLIP | timeout / CLI error | SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`

Why this fails closure: the pass-3 brief requires no implementer-local choice about retry/continue/mapping for v1 cases. An `or` in the availability limitation column is exactly implementer-local choice. Timeout and CLI error should be split into separate rows with one limitation each.

Closure criteria: v1.3 should split line 412 into deterministic rows, for example:

- timeout → `SOURCE_TIMEOUT`
- CLI/runtime error → `FRESH_ATTEMPT_FAILED`

If some CLI errors are timeout-like, that needs its own closed failure class.

### CLOSED — Batch 5: Cross-Surface Repair Isolation / Post-Repair Validation

**Lines:** `spec-brief.md:427-436`, `spec-brief.md:770-771`

This is closed. v1.3 keys prior specs by bond, surface, conversation, and turn; adds digest/timestamp/TTL freshness identity; names simultaneous Telegram/web isolation; and requires post-repair `CompositionSpec` validation before Layer 1. R#36 and R#37 directly test the two required behaviors.

No material closure gap from Pauli’s lens.

### STILL OPEN — Batch 6: Realistic p95 Budgets Are Still Not Reproducible

**Lines:** `spec-brief.md:673-675`, `spec-brief.md:772-775`

v1.3 improves the test surface by naming realistic fixture categories: SQLite/WAL, Chroma, file-backed, and bounded-reader. It also adds budget telemetry in R#39. But it still does not give reproducible p95 budget criteria for adapter fixtures.

Why this fails closure: “p95 adapter budgets under realistic source counts” is not mechanically testable unless the spec defines at least the threshold and the fixture scale. D13 gives Layer 0 total budget numbers, but R#38 is about representative local adapter fixtures. A test writer still has to invent source counts, iteration count, warmup behavior, and per-adapter p95 thresholds.

Closure criteria: v1.3 should name:

- fixture scale for each adapter class, e.g. row counts / collection size / file count / bounded-reader corpus size;
- p95 threshold per adapter or one explicit shared threshold;
- number of samples and warmup/prewarm assumptions;
- whether CI may mark these as perf-smoke versus release-gating.

## Final Summary

**STILL OPEN**

Required v1.4 fold:

1. Define closed `mismatch_reason` vocabulary or bind it to an existing closed enum.
2. Specify mid-band scoring behavior between `no_match_below` and `min_accept`, plus reserved-class handling during tie-breaks.
3. Split `ARXIV_OR_PAPERCLIP` timeout vs CLI error into deterministic error mappings.
4. Make realistic p95 adapter-budget fixtures reproducible with concrete scale, thresholds, sampling, and warmup rules.

Plain English: v1.3 got the right edge-case categories onto the page. The remaining problem is that a few cells still say “you decide” in places where production code needs a rule.
