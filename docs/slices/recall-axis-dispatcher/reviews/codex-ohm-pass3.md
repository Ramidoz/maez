# Ohm Review — Recall-Axis Dispatcher Pass-3

**Verdict: STILL OPEN**

v1.3 closes most of the operational edge surface. The audit envelope, tie/no-match rules, fan-out cancellation, and repair isolation are now implementable enough for my lane.

Two Ohm-surface gaps remain material:

1. External error mapping still contains an implementer choice.
2. Realistic p95 budget fixtures still lack concrete thresholds and source-count fixtures.

No covenant escalation.

## Per-Batch Closure Table

| Batch | v1.3 Change Cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Audit metadata payload | Audit envelope field list and consumer split | CLOSED | Lines 214-235 define a closed no-raw-private-content envelope, required fields, and split between `audit_assistant_text` and `self_claim_audit.py`; R#30a at line 762 anchors behavior. |
| Tie / no-match source selection | Thresholds, multi-match, stable order, no-match per inventory state | CLOSED | Lines 262-277 define thresholds, contributor rule, stable A-K tie order, and no-match behavior for `PRESENT`, `UNKNOWN`, `ABSENT`, and reserved sources; R#28a at line 759 anchors behavior. |
| Fan-out cancellation / late results | Timeout, global deadline, sealed merge, generation-id ignore, bounded cleanup | CLOSED | Lines 351-357 define timeout behavior, sealed merge set, late-result ignore by generation id, 25ms cleanup grace, quarantine, and telemetry; D12 at lines 669-671 and R#32a at line 765 anchor behavior. |
| External error mapping / stop conditions | Error class table | STILL OPEN | Lines 399-416 mostly close the table, but line 412 maps `ARXIV_OR_PAPERCLIP` timeout / CLI error to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, leaving an implementation-local choice. |
| Cross-surface repair isolation / post-repair validation | Cache key, freshness identity, cross-surface isolation, refusal before Layer 1 | CLOSED | Lines 427-436 define FSM, cache key, freshness identity with digest/timestamp/TTL, surface+conversation isolation, post-repair validation, and `REPAIR_PRIOR_SPEC_INVALID`; R#36/R#37 at lines 770-771 anchor behavior. |
| Realistic p95 adapter budgets / telemetry | R#38/R#39 and RED split | STILL OPEN | Lines 772-775 require realistic fixtures but do not name p95 thresholds per adapter or realistic source counts; D13 line 675 gives Layer 0 budget, not per-adapter fixture budgets. |

## Findings

### STILL OPEN — External Error Mapping Still Has an `or`

Batch: External-source error-class mapping and stop conditions

v1.3 line 412 says:

`ARXIV_OR_PAPERCLIP | timeout / CLI error | SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED | stop after first failure`

That is exactly the kind of implementer choice pass-3 is supposed to remove. Timeout and CLI error are different resource/cost surfaces. One is deadline exhaustion; the other is execution failure. The spec must not leave the implementer to decide which closed limitation applies.

Closure criteria:

- Split line 412 into separate rows.
- `timeout` should map deterministically to `SOURCE_TIMEOUT`.
- `CLI error` should map deterministically to one existing closed limitation, likely `FRESH_ATTEMPT_FAILED`, unless the vocabulary is amended.
- R#33a should explicitly include both Paperclip timeout and Paperclip CLI-error cases.

### STILL OPEN — Realistic p95 Budget Fixtures Lack Concrete Budgets

Batch: Realistic-store p95 adapter-budget requirements and telemetry anchors

v1.3 lines 772-775 require representative SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures, but they do not define the p95 assertion thresholds or realistic source counts per fixture. Line 675 defines Layer 0’s total warm/cold budget, but Batch 6 asks for adapter-budget fixtures under realistic source counts. Without per-fixture numbers, implementers still have to invent the measurement contract.

Closure criteria:

- Add a small table naming each realistic fixture: SQLite/WAL, Chroma, file-backed, bounded-reader.
- For each fixture, specify source-count / row-count shape and p95 ceiling.
- State whether the p95 ceiling is per adapter call, per branch, or total fixture run.
- R#38 should assert those exact ceilings, not merely “within budget.”
- R#39 should require telemetry to include fixture id, sample count, p50/p95, cold/warm marker, and timeout/cancellation counts.

## NITs

None. The remaining issues are material, not typographical.

## Final Summary

**STILL OPEN.**

v1.3 is close. Four of six pass-2 batches are closed. The v1.4 fold can be narrow: remove the `or` from Paperclip error mapping, and add concrete p95 adapter-budget fixture thresholds/source-counts.
