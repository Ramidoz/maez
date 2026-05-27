# Arendt — Codex Engineering Pass-3 Closure Audit

**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.3
**Controlling brief:** `reviews/codex-engineering-pass3-brief.md`
**Lens:** state integrity, concurrency, repair isolation, sealed merge-set behavior, authority-transition integrity
**Verdict:** **STILL OPEN**

v1.3 materially closes four of the six operational-edge batches. Two remain open: external error mapping still contains one implementation-choice fork, and realistic p95 adapter budgets still lack reproducible numeric/load criteria.

## Verdict Summary

| Batch | Verdict |
| --- | --- |
| 1. Audit metadata payload | CLOSED |
| 2. Tie / no-match source selection | CLOSED |
| 3. Fan-out cancellation / late results | CLOSED |
| 4. External error mapping / stop conditions | STILL OPEN |
| 5. Cross-surface repair isolation / post-repair validation | CLOSED |
| 6. Realistic p95 adapter budgets / telemetry | STILL OPEN |

## Per-Batch Closure Table

| Batch | v1.3 Change Cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Audit metadata payload | Lines 214-235, R#30a at 762 | CLOSED | Closed envelope, no raw private content, field list, consumer split, mismatch/refusal fields, RED anchor all present. |
| Tie / no-match source selection | Lines 258-277, R#28a at 759 | CLOSED | Outright-win threshold, multi-match rule, legal-product fallback, stable A-K tie-break, no-match behavior for PRESENT/UNKNOWN/ABSENT, reserved-source handling all specified. |
| Fan-out cancellation / late results | Lines 351-357, D12 at 669-671, R#32a at 765 | CLOSED | Per-branch timeout, global deadline, sealed merge set, generation-id late-result ignore, bounded cleanup grace, quarantine, telemetry, and RED anchor present. |
| External error mapping / stop conditions | Lines 399-416, R#33a at 767 | STILL OPEN | Most mapping is closed, but line 412 uses `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, leaving implementer choice for `ARXIV_OR_PAPERCLIP` timeout / CLI error. |
| Cross-surface repair isolation / post-repair validation | Lines 427-436, R#36-R#37 at 770-771 | CLOSED | Key includes bond/surface/conversation/turn; freshness identity adds digest/timestamp/TTL; cross-surface inheritance forbidden; invalid modified specs refuse before Layer 1; tests named. |
| Realistic p95 adapter budgets / telemetry | Lines 772-775, D13 at 673-675 | STILL OPEN | Realistic fixture classes and telemetry categories are named, but concrete p95 thresholds and realistic source-count/load fixtures are not specified. |

## Findings

### STILL OPEN — External Error Mapping Leaves One Open Fork

**Batch:** External-source error-class mapping and stop conditions
**Lines:** `spec-brief.md:411-412`, with table context at `399-416`

v1.3 mostly closes this batch, but line 412 says:

`ARXIV_OR_PAPERCLIP | timeout / CLI error | SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED | stop after first failure`

That `or` is the remaining state-integrity gap. The pass-3 brief requires closed failure classes and no implementer-local choice about retry/continue or classification. A timeout and a CLI error are different failure states; collapsing them into a row with two possible availability limitations leaves the implementation to decide which one applies.

**Closure criteria for v1.4:**

- Split the row into closed cases, for example:
  - `timeout` → `SOURCE_TIMEOUT` → stop after first timeout.
  - `CLI error` → `FRESH_ATTEMPT_FAILED` or a named closed limitation → stop after first CLI error.
- If CLI error itself has subtypes, either defer subtyping or enumerate it, but do not leave `A or B` in the availability limitation cell.
- Ensure R#33a asserts the exact mapping, not only that “some” closed limitation is emitted.

### STILL OPEN — Realistic p95 Adapter Budgets Are Named, Not Reproducible

**Batch:** Realistic-store p95 adapter-budget requirements and telemetry anchors
**Lines:** `spec-brief.md:772-775`, with D13 at `673-675`

v1.3 adds the right test surfaces: R#38 names SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures; R#39 names telemetry categories. That closes the “pure mocks only” problem. It does not yet make the p95 requirement reproducible.

The phrase “under realistic source counts” at line 772 does not define source counts, row counts, collection sizes, file counts, or p95 thresholds per adapter. D13 defines a Layer 0 total budget, but Batch 6 asked for adapter-budget fixtures, not only a global Layer 0 latency ceiling. Without fixture load sizes and numeric p95 pass criteria, two implementers could write incompatible tests and both claim conformance.

**Closure criteria for v1.4:**

- Define realistic fixture loads for each adapter class, such as row-count / WAL-state for SQLite, collection size for Chroma, file count / byte size for file-backed readers, and gated/allowed cases for bounded readers.
- Define numeric p95 thresholds per adapter class or a clearly allocated budget slice under the D13 / Layer 1 budgets.
- State the sample size / repetition rule for p95 measurement, or at least a minimum run count sufficient for deterministic CI interpretation.
- Ensure R#38 asserts those values, not merely fixture type presence.
- Keep R#39 as telemetry coverage, but tie telemetry assertions to the same budget labels used by R#38.

## NITs

None. The two open items are material, not typographical.

## Final Summary

**STILL OPEN.**

v1.3 closes the state-shape issues that mattered most to Arendt’s lane: audit envelope state, deterministic tie behavior, sealed merge-set behavior, and cross-surface repair isolation are now specified tightly enough to implement without improvising. Two operational receipts still need v1.4: remove the `ARXIV_OR_PAPERCLIP` error-mapping fork, and make realistic p95 adapter-budget tests numerically reproducible.
