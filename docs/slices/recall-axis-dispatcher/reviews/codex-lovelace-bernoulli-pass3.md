# Lovelace / Bernoulli Review — Codex Engineering Pass-3

## Verdict Summary

**Verdict: STILL OPEN**

v1.3 closes four of the six operational-edge batches cleanly. Two remain materially open from the Lovelace/Bernoulli lens:

1. **Tie / no-match source-selection** still has one nondeterministic source-anchor case.
2. **Realistic p95 adapter budgets** name fixture classes and telemetry, but do not define reproducible fixture sizes or p95 thresholds per adapter.

One additional material gap remains in **external error mapping**: `ARXIV_OR_PAPERCLIP` uses an `or` mapping for timeout / CLI error, leaving implementer choice.

No covenant escalation.

## Per-Batch Closure Table

| Batch | v1.3 change cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Audit metadata payload | `spec-brief.md:207-235`, `spec-brief.md:761-762` | CLOSED | Closed owner module, no-raw-private-content envelope, required fields, split between `audit_assistant_text` and `self_claim_audit.py`, and R#30a are explicit. |
| Tie / no-match source selection | `spec-brief.md:268-277`, `spec-brief.md:758-759` | STILL OPEN | Thresholds and tie-breaks are mostly deterministic, but no-match with “explicit source-anchor sources if any” lacks deterministic source-anchor normalization/order. |
| Fan-out cancellation / late results | `spec-brief.md:351-357`, `spec-brief.md:669-671`, `spec-brief.md:764-765` | CLOSED | Per-branch timeout, global deadline, sealed merge set, generation-id ignore rule, quarantine/grace, telemetry, and R#32a are specified. |
| External error mapping / stop conditions | `spec-brief.md:399-415`, `spec-brief.md:766-767` | STILL OPEN | Most mappings are closed, but `ARXIV_OR_PAPERCLIP` timeout / CLI error maps to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`, leaving implementer choice. |
| Cross-surface repair isolation / post-repair validation | `spec-brief.md:427-436`, `spec-brief.md:770-771` | CLOSED | Freshness identity includes digest + timestamp + TTL; surface/conversation prevent cross-inheritance; invalid modified specs refuse before Layer 1; R#36/R#37 cover both. |
| Realistic p95 adapter budgets / telemetry | `spec-brief.md:313`, `spec-brief.md:338-349`, `spec-brief.md:748-749`, `spec-brief.md:772-775` | STILL OPEN | Fixture classes and telemetry categories are named, but realistic source counts and per-adapter p95 thresholds are not reproducible enough for repeated-run verification. |

## Findings

### STILL OPEN 1 — No-match source-anchor fallback is not fully deterministic

**Batch:** Tie and no-match source-selection rules
**Lines:** `spec-brief.md:273-277`, especially `274`
**Severity:** STILL OPEN

v1.3 closes most of the scoring ambiguity. The numeric thresholds are explicit at `spec-brief.md:262`, outright-win and multi-match behavior are specified at `270-272`, and no-match behavior is split by `inventory_witness` at `273-277`.

The remaining nondeterminism is this clause:

`inventory_witness=PRESENT`: “choose explicit source-anchor sources if any”

That does not define the normalization rule when multiple explicit source anchors appear, when anchors map to both executable and reserved labels, or when utterance order conflicts with stable source priority. The later sentence at `277` handles reserved sources generally, but not ordering or selection among multiple explicit executable anchors.

**Closure criteria:** v1.3 should add one deterministic rule, for example:

- source anchors normalize through the closed `SubstrateSource` / `ExternalSource` vocabulary;
- reserved anchors become availability limitations only;
- executable anchored sources are ordered by utterance span order, then stable source-label order as tie-breaker; OR by a declared fixed source-priority list;
- R#28a must assert multi-anchor no-match behavior is stable across repeated runs.

Without that, two implementations can both satisfy the prose while emitting different source order or different selected source sets for the same no-match utterance.

### STILL OPEN 2 — External error mapping still contains an implementer-local `or`

**Batch:** External-source error-class mapping and stop conditions
**Lines:** `spec-brief.md:411-412`
**Severity:** STILL OPEN

Most of the table at `399-415` is clean and closed. The one open cell is:

`ARXIV_OR_PAPERCLIP` | `timeout / CLI error` | `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`

That `or` is exactly the kind of implementation-local choice pass-3 is supposed to eliminate. A timeout and a CLI error are different failure classes. If both are valid, they need separate rows.

**Closure criteria:** split the row into deterministic mappings, e.g.:

- `timeout` → `SOURCE_TIMEOUT` → stop after first query;
- `CLI error` → `FRESH_ATTEMPT_FAILED` or a newly declared closed limitation, if desired;
- R#33a must include both cases separately.

Until then, repeated implementations can classify the same Paperclip failure differently.

### STILL OPEN 3 — Realistic p95 adapter-budget fixtures lack reproducible thresholds and load sizes

**Batch:** Realistic p95 adapter-budget requirements and telemetry anchors
**Lines:** `spec-brief.md:313`, `338-349`, `772-775`
**Severity:** STILL OPEN

v1.3 correctly upgrades the test surface from mocks to realistic local fixtures. It names SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures at `772` and distinguishes unit/mock/realistic fixture layers at `775`.

The remaining gap is reproducibility. R#38 says “under realistic source counts,” but it does not define:

- the row count / collection count / file count / bounded-reader corpus size for each fixture;
- whether p95 is measured over N repetitions, N queries, or both;
- per-adapter p95 thresholds;
- whether thresholds are adapter-local or only checked against aggregate Layer 0 / Layer 1 budgets.

D13 gives a Layer 0 budget at `313`; Layer 1 gives timeout/deadline constants at `338-349`. Those are useful global budgets, but they are not the concrete adapter-budget fixture contract pass-2 requested.

**Closure criteria:** v1.3 should add a fixture table for R#38/R#39 with at least:

- adapter type;
- fixture size;
- warm/cold condition;
- repetition count or sample size;
- p95 threshold;
- telemetry fields asserted.

Example shape, not exact required numbers:

| Adapter | Fixture size | Condition | p95 threshold | Telemetry required |
| --- | --- | --- | --- | --- |
| SQLite/WAL | N rows, WAL enabled | warm | ≤ X ms | cursor, elapsed, row count |
| Chroma | N vectors / M collections | warm | ≤ Y ms | collection count, elapsed |
| File-backed | N files / total bytes | warm | ≤ Z ms | mtime/size scan count |
| Bounded reader | N entries behind gate | warm | ≤ W ms | gate result, elapsed |

Without concrete fixture sizes and thresholds, R#38 is directionally right but not reproducible under repeated runs.

## Closed Batches

### CLOSED — Audit metadata payload

The audit envelope is now sufficiently concrete. Lines `214-235` define a closed envelope, no raw private content, required fields, and the consumer split. R#30a at `761-762` proves emission to both audit consumers.

No further engineering closure required.

### CLOSED — Fan-out cancellation / late results

Lines `351-357` define per-branch timeout, global deadline, sealed merge set, generation-id ignore behavior, bounded grace, quarantine, and telemetry. D12 at `669-671` makes late mutation forbidden. R#32a at `764-765` tests the behavior.

No further engineering closure required.

### CLOSED — Cross-surface repair isolation / post-repair validation

Lines `434-436` bind inheritance to bond, surface, conversation, turn, digest, timestamp, and TTL. They also require validation of the modified spec before Layer 1 and refusal with `REPAIR_PRIOR_SPEC_INVALID`. R#36/R#37 at `770-771` are the right behavioral anchors.

No further engineering closure required.

## NITs

None.

## Final Summary

**STILL OPEN**

v1.3 substantially closes the edge-case rulebook, but three operational details still leave implementer choice:

1. deterministic ordering/selection for explicit source anchors during no-match fallback;
2. deterministic Paperclip timeout vs CLI-error mapping;
3. reproducible p95 adapter-budget fixture sizes and thresholds.

A narrow v1.4 fold should be enough. No covenant pass is indicated.
