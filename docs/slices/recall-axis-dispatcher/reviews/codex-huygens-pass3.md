# Huygens Review — Recall-Axis Dispatcher Codex Pass-3

**Artifact reviewed:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.3
**Controlling brief:** `reviews/codex-engineering-pass3-brief.md`
**Lens:** schema mechanics, storage identity, deterministic replayability, exact payload fields, fixture concreteness, edge-case reproducibility.

## Verdict Summary

**STILL OPEN**

v1.3 closes three of the six operational-edge batches cleanly, but three remain materially open:

- Batch 3: fan-out cancellation uses `generation_id` as the seal mechanism but does not define its creation/binding identity.
- Batch 4: external error mapping contains an implementation-choice `or` for `ARXIV_OR_PAPERCLIP`.
- Batch 6: realistic p95 adapter-budget fixtures are named but do not specify concrete fixture sizes or per-adapter p95 thresholds.

No covenant escalation.

## Per-Batch Closure Table

| Batch | v1.3 Change Cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Audit metadata payload | `spec-brief.md:214-235`, `R#30a` at `762` | CLOSED | Closed envelope, no raw private content, required fields, split between `audit_assistant_text` and `self_claim_audit.py` are all explicit. |
| Tie / no-match source selection | `spec-brief.md:268-277`, `R#28a` at `759` | CLOSED | Outright win, multi-match, tie-break, no-match behavior, reserved-source fallback are deterministic enough for implementation. |
| Fan-out cancellation / late results | `spec-brief.md:351-357`, `D12` at `669-672`, `R#32a` at `765` | STILL OPEN | The spec says late results are ignored by `generation_id`, but does not define how that generation id is created, bound, and compared. |
| External error mapping / stop conditions | `spec-brief.md:399-416`, `R#33a` at `767` | STILL OPEN | `ARXIV_OR_PAPERCLIP` maps `timeout / CLI error` to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, leaving implementer choice. |
| Cross-surface repair isolation / post-repair validation | `spec-brief.md:419-436`, `R#36-R#37` at `770-771` | CLOSED | Cache key, freshness identity, TTL, surface/conversation separation, and post-repair validation/refusal are specified. |
| Realistic p95 adapter budgets / telemetry | `spec-brief.md:772-775`, `D13` at `673-676`, `R#38-R#39` at `772-773` | STILL OPEN | The fixture classes are named, but concrete realistic source counts and per-adapter p95 thresholds are absent. |

## Findings

### STILL OPEN 1 — Fan-Out Seal Identity Is Named But Not Mechanically Defined

**Batch:** Fan-out cancellation / late results
**Lines:** `spec-brief.md:351-357`, `669-672`, `765`

v1.3 improves the cancellation contract: per-branch timeout requests cancellation, global deadline seals the merge set, late results are ignored by `generation_id`, and telemetry records late-result status.

The remaining gap is identity mechanics. `generation_id` is the load-bearing replay/seal key, but the brief does not define:

- when the `generation_id` is minted,
- whether it is per Layer 1 invocation, per branch, or per `CompositionSpec`,
- whether branch futures/results must carry it,
- what sealed state stores the accepted generation,
- how a late result proves it belongs to the stale generation before being ignored.

**Closure criteria:** v1.4 should add a short seal identity contract, for example:

- Layer 1 mints `fanout_generation_id` at fan-out start.
- Every branch future and `RecallBranchResult` carries that id.
- The sealed merge set records `fanout_generation_id`, `sealed_at`, and accepted branch ids.
- Any result whose generation id does not match the sealed id, or arrives after `sealed_at`, is telemetry-only and cannot mutate recall, prompt blocks, or `CompositionSpec`.

### STILL OPEN 2 — External Error Mapping Contains An Implementation-Choice `or`

**Batch:** External error mapping / stop conditions
**Lines:** `spec-brief.md:399-416`, especially `412`

The table is mostly closed and implementable. The exception is:

`ARXIV_OR_PAPERCLIP | timeout / CLI error | SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`

That `or` violates the pass-3 closure criterion: no implementer-local choice about mapping failure classes to availability limitations.

**Closure criteria:** split the ambiguous row into deterministic rows:

- `timeout` → `SOURCE_TIMEOUT`
- `CLI nonzero / invocation error` → `FRESH_ATTEMPT_FAILED` or a single chosen limitation
- `no match / empty result` → `FRESH_ATTEMPT_FAILED`

If `CLI error` has subtypes, name the subtypes in the table rather than leaving a choice in implementation.

### STILL OPEN 3 — Realistic Adapter-Budget Fixtures Lack Concrete Fixture Sizes And p95 Thresholds

**Batch:** Realistic p95 adapter budgets / telemetry
**Lines:** `spec-brief.md:673-676`, `772-775`

v1.3 names the right fixture families: SQLite/WAL, Chroma, file-backed, and bounded-reader. It also requires telemetry for cold/prewarm, source selection, cancellation, full-manifest scoring, external-fetch stop, and total prompt-budget contribution.

But the pass-2 closure criterion asked for reproducible p95 adapter-budget tests under realistic source counts. v1.3 does not yet specify:

- representative row/vector/file counts,
- per-adapter p95 thresholds,
- warm vs cold/prewarm fixture conditions per adapter,
- whether the p95 sample count is fixed,
- what counts as realistic for each substrate class.

Without those, two implementers can both satisfy `R#38` while benchmarking different workloads.

**Closure criteria:** v1.4 should add a small adapter-budget table, for example:

| Adapter class | Fixture shape | Sample count | p95 threshold | Telemetry required |
| --- | --- | --- | --- | --- |
| SQLite/WAL | N rows, indexed query, WAL enabled | N runs | ≤ X ms | elapsed, rows scanned/returned |
| Chroma | N vectors, 384-dim, top-k query | N runs | ≤ X ms | encode excluded/included stated |
| File-backed | N files / total bytes | N runs | ≤ X ms | files opened, bytes read |
| Bounded-reader | N candidate records + gate outcome | N runs | ≤ X ms | gate reason, returned chars |

Exact numbers can be conservative seed values, but they must be in the brief so the test is replayable.

## NITs

None. The open items are material engineering gaps, not typographical/framing observations.

## Final Summary

**STILL OPEN**

v1.3 materially closes the audit envelope, tie/no-match selection, and repair isolation batches. It still needs a narrow v1.4 fold for:

1. fan-out generation/seal identity,
2. deterministic `ARXIV_OR_PAPERCLIP` error mapping,
3. concrete realistic adapter-budget fixture sizes and p95 thresholds.

Plain English: v1.3 mostly wrote the weird-case rulebook. Huygens still sees three places where the builder would have to invent exact machinery: what counts as the sealed fan-out generation, how one external error row maps, and what “realistic p95 budget” concretely measures.
