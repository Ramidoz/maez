# Peirce Review — Recall-Axis Dispatcher Codex Pass-3

## Verdict Summary

**Overall verdict: STILL OPEN**

v1.3 closes four of the six pass-2 operational-edge batches. Two remain materially open:

- **Batch 4 — External error mapping / stop conditions:** one row still gives an implementation-local choice: `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`.
- **Batch 6 — Realistic p95 adapter budgets / telemetry:** v1.3 names realistic fixture categories, but does not give reproducible p95 thresholds or realistic source counts per adapter.

No covenant escalation. No new architecture required. The v1.4 fold is narrow.

## Per-Batch Closure Table

| Batch | v1.3 Change Cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Audit metadata payload | `spec-brief.md:207-235`, `761-762` | CLOSED | Closed envelope, no raw private content, field split for `audit_assistant_text` vs `self_claim_audit.py`, RED anchor R#30a. |
| Tie / no-match source selection | `260-277`, `693-695`, `758-759` | CLOSED | Thresholds, multi-match rule, stable A-K tie-break, no-match behavior by `inventory_witness`, reserved-source fallback, RED anchor R#28a. |
| Fan-out cancellation / late results | `351-357`, `669-671`, `764-765` | CLOSED | Per-branch timeout, global deadline, sealed merge set, generation-id late-result ignore, bounded cleanup/quarantine, telemetry, RED anchor R#32a. |
| External error mapping / stop conditions | `399-415`, `766-767` | STILL OPEN | Most rows are closed, but `ARXIV_OR_PAPERCLIP` maps `timeout / CLI error` to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED` at line 412, leaving a verdict choice. |
| Cross-surface repair isolation / post-repair validation | `427-436`, `770-771` | CLOSED | Prior-spec identity includes bond/surface/conversation/turn/digest/timestamp/TTL; cross-surface inheritance is structurally forbidden; invalid modified specs refuse before Layer 1; R#36/R#37. |
| Realistic p95 adapter budgets / telemetry | `313`, `349`, `772-775` | STILL OPEN | Realistic fixture categories and telemetry are named, but reproducible p95 thresholds and realistic source counts per adapter are not specified. |

## Findings

### P1 — STILL OPEN: `ARXIV_OR_PAPERCLIP` Error Mapping Still Contains an Implementation-Local Verdict

**Batch:** External error mapping / stop conditions
**Lines:** `spec-brief.md:411-412`

v1.3 mostly closes the external error taxonomy, but this row remains ambiguous:

- `ARXIV_OR_PAPERCLIP` `timeout / CLI error` → `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`

That `or` is exactly the kind of implementation-local verdict pass-3 is supposed to remove. Peirce lens: the test must prove behavior, not vocabulary, and the code cannot be left to decide which closed limitation applies.

**Closure criteria for v1.4:**

Split the row into deterministic subcases, for example:

- `timeout` → `SOURCE_TIMEOUT`
- `CLI error / nonzero exit / parse failure` → `FRESH_ATTEMPT_FAILED`

Then R#33a should assert those exact mappings.

### P2 — STILL OPEN: Realistic p95 Adapter Budgets Are Named but Not Reproducible

**Batch:** Realistic p95 adapter budgets / telemetry
**Lines:** `spec-brief.md:772-775`; related budgets at `313`, `349`

v1.3 adds R#38 and R#39, and it correctly requires realistic SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures. But it still does not define the numeric p95 thresholds and realistic source counts per adapter.

Current text says the fixtures “enforce p95 adapter budgets” under “realistic source counts,” but an implementer still has to choose:

- how many rows / files / Chroma records make the fixture realistic;
- the p95 threshold per adapter;
- whether the existing ≤80ms per-source timeout is also the p95 threshold or only an upper deadline;
- whether bounded-reader privacy gates have a separate faster p95 budget.

That is not yet reproducible.

**Closure criteria for v1.4:**

Add a small adapter-budget table with at least:

- adapter type;
- fixture size/source-count;
- warm p95 threshold;
- cold or first-read threshold if applicable;
- required telemetry fields;
- whether the threshold is advisory, blocking, or RED-test enforced.

Example shape:

| Adapter | Fixture | p95 budget | Telemetry |
| --- | --- | --- | --- |
| SQLite/WAL | N rows, WAL present | ≤ X ms | elapsed, row count, cursor |
| Chroma | N records, warmed collection | ≤ Y ms | elapsed, collection count |
| File-backed | N files / total bytes | ≤ Z ms | elapsed, mtime/hash count |
| Bounded reader | gated + allowed cases | ≤ W ms | gate result, elapsed |

R#38 should assert these concrete budgets, not just the existence of a p95 concept.

## Final Summary

**STILL OPEN**

v1.3 is close. Four batches are closed. The remaining v1.4 fold is narrow:

1. remove the `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED` ambiguity for `ARXIV_OR_PAPERCLIP`;
2. make realistic adapter p95 budgets reproducible with concrete fixture sizes and thresholds.

Plain English: the edge-case rulebook is mostly tight, but two spots still ask the builder to choose the answer. One is “what kind of failure was this?” and the other is “what counts as fast enough?” Those need to be written down before canon.
