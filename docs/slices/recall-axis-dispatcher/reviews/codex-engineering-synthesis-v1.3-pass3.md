# Recall-Axis Dispatcher — Codex Engineering Pass-3 Synthesis

**Prepared:** 2026-05-26
**Artifact reviewed:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.3
**Base commit:** `e3b01e3 docs(dispatcher): fold pass-2 findings into v1.3`
**Dispatch brief:** `docs/slices/recall-axis-dispatcher/reviews/codex-engineering-pass3-brief.md`
**Review records:** `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass3.md`

This document is derivative reconstruction. The six `codex-*-pass3.md` files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Peirce | STILL OPEN |
| Arendt | STILL OPEN |
| Huygens | STILL OPEN |
| Pauli | STILL OPEN |
| Ohm | STILL OPEN |
| Lovelace / Bernoulli | STILL OPEN |

Engineering pass-3 result: **STILL OPEN.**

v1.3 closed the broad operational-edge shape, but pass-3 found a small set of remaining implementer-choice surfaces. No reviewer raised a covenant-axis escalation.

---

## Per-Batch Closure Summary

| Batch | Closure Verdict | Seat Pattern |
| --- | --- | --- |
| 1. Audit metadata payload | STILL OPEN / narrow | 5 CLOSED, 1 STILL OPEN |
| 2. Tie and no-match source selection | STILL OPEN / split | 4 CLOSED, 2 STILL OPEN |
| 3. Fan-out cancellation / late results | STILL OPEN / narrow | 5 CLOSED, 1 STILL OPEN |
| 4. External error mapping / stop conditions | STILL OPEN | 6 STILL OPEN |
| 5. Cross-surface repair isolation / post-repair validation | CLOSED | 6 CLOSED |
| 6. Realistic p95 adapter budgets / telemetry | STILL OPEN | 6 STILL OPEN |

Material outcome: v1.3 should not proceed to canonicalization. The v1.4 fold is narrow and operational.

---

## Convergent Material Findings

### Batch 6 — Realistic p95 Adapter Budgets Are Not Reproducible

Seats: Peirce, Arendt, Huygens, Pauli, Ohm, Lovelace / Bernoulli.

All six reviewers agreed that v1.3 still does not close the realistic adapter-budget batch. v1.3 correctly names the required fixture families and adds R#38/R#39, but it does not specify concrete fixture sizes, per-adapter p95 thresholds, sampling rules, or warm/cold conditions.

Current v1.3 evidence cited:

- `spec-brief.md:673-675`: Layer 0 warm/cold budget.
- `spec-brief.md:772-775`: R#38/R#39 and RED-suite split.
- `spec-brief.md:338-349`: Layer 1 timeout/deadline budget, cited as useful but insufficient for adapter fixture reproducibility.

Required v1.4 fold:

- Add a realistic adapter-budget table covering SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures.
- For each fixture, name fixture scale/source count, warm/cold condition, sample count or repetition rule, p95 threshold, and telemetry fields.
- State whether the p95 ceiling is per adapter call, per branch, or aggregate fixture run.
- Tie R#38 to those exact thresholds and R#39 to matching telemetry labels.

### Batch 4 — `ARXIV_OR_PAPERCLIP` Error Mapping Contains an `or`

Seats: Peirce, Arendt, Huygens, Pauli, Ohm, Lovelace / Bernoulli.

All six reviewers independently found the same remaining implementer-choice cell: the external error table maps `ARXIV_OR_PAPERCLIP` `timeout / CLI error` to `SOURCE_TIMEOUT or FRESH_ATTEMPT_FAILED`. That `or` violates the pass-3 closure rule: the implementation may not choose between closed availability limitations.

Current v1.3 evidence cited:

- `spec-brief.md:399-416`: external error taxonomy.
- `spec-brief.md:411-412`: ambiguous `ARXIV_OR_PAPERCLIP` row.
- `spec-brief.md:766-767`: R#33a.

Required v1.4 fold:

- Split the row into deterministic subcases:
  - `timeout` → `SOURCE_TIMEOUT`.
  - `CLI error` / nonzero exit / invocation error → `FRESH_ATTEMPT_FAILED` unless a new closed limitation is introduced.
  - empty/no match remains `FRESH_ATTEMPT_FAILED`.
- Update R#33a so Paperclip timeout and Paperclip CLI-error cases are asserted separately.

---

## Split / Narrow Material Findings

### Batch 2 — Tie / No-Match Source Selection Still Has Edge Ambiguity

Seats STILL OPEN: Pauli, Lovelace / Bernoulli.
Seats CLOSED: Peirce, Arendt, Huygens, Ohm.

v1.3 defines thresholds, outright win, multi-match, stable manifest order, and no-match behavior by `inventory_witness`. Two reviewers still found deterministic gaps:

- The score band `no_match_below <= top_score < min_accept` is undefined.
- No-match fallback with “explicit source-anchor sources if any” does not define normalization/order when multiple anchors appear, when anchors map to executable and reserved labels, or when utterance order conflicts with source priority.
- Reserved-class handling is stated for no-match fallback, but not clearly for accepted-score ties.

Current v1.3 evidence cited:

- `spec-brief.md:260-277`: scoring constants and tie/no-match rules.
- `spec-brief.md:563-579`: archetype class list, including reserved `K_GRAPH_ASSISTED_RELATIONAL`.
- `spec-brief.md:758-759`: R#28/R#28a.

Required v1.4 fold:

- Define exact behavior for `0.50 <= top_score < 0.62`.
- Define explicit source-anchor normalization through closed `SubstrateSource` / `ExternalSource` vocabularies.
- Define ordering for multiple explicit executable anchors: utterance span order plus stable source-label tie-breaker, or a declared fixed priority list.
- State reserved anchors/classes become availability limitations only and do not become executable sources during tie/no-match resolution.
- Update R#28a to assert mid-band and multi-anchor no-match behavior.

### Batch 1 — Audit Metadata `mismatch_reason` Is Not Closed

Seat STILL OPEN: Pauli.
Seats CLOSED: Peirce, Arendt, Huygens, Ohm, Lovelace / Bernoulli.

v1.3 defines a closed audit envelope and consumer split, but Pauli found that `mismatch_reason` is required without a closed vocabulary. A closed envelope with an open-ended reason string still leaves audit consumers guessing.

Current v1.3 evidence cited:

- `spec-brief.md:214-235`: audit metadata contract.
- `spec-brief.md:547-560`: closed `DispatcherRefusalReason`, which does not cover `mismatch_reason`.
- `spec-brief.md:761-762`: R#30a.

Required v1.4 fold:

- Define a closed `ProvenanceAuditMismatchReason` vocabulary or explicitly bind `mismatch_reason` to an existing closed enum.
- State when `mismatch_reason` is null/absent versus populated.
- Update R#30a to assert closed mismatch reasons.

### Batch 3 — Fan-Out Seal Identity Is Not Mechanically Bound

Seat STILL OPEN: Huygens.
Seats CLOSED: Peirce, Arendt, Pauli, Ohm, Lovelace / Bernoulli.

v1.3 defines per-branch timeout, global deadline, sealed merge set, generation-id late-result ignore, bounded cleanup, quarantine, and telemetry. Huygens found one remaining schema/replayability gap: `generation_id` is load-bearing but not defined as a minting/binding identity.

Current v1.3 evidence cited:

- `spec-brief.md:351-357`: cancellation / late-result semantics.
- `spec-brief.md:669-672`: D12.
- `spec-brief.md:764-765`: R#32a.

Required v1.4 fold:

- Define `fanout_generation_id` as minted at Layer 1 fan-out start.
- Require every branch future and `RecallBranchResult` to carry that id.
- Require sealed merge state to record `fanout_generation_id`, `sealed_at`, and accepted branch ids.
- State any result with mismatched generation id or arrival after `sealed_at` is telemetry-only and cannot mutate recall, prompt blocks, or `CompositionSpec`.
- Update R#32a to assert this identity binding.

---

## Closed Batch

### Batch 5 — Cross-Surface Repair Isolation / Post-Repair Validation

Seats: 6 CLOSED.

All reviewers agreed v1.3 closes this batch. The brief now binds prior-spec lookup to bond/surface/conversation/turn and validates freshness through digest/timestamp/TTL. Simultaneous Telegram/web turns under the same bond cannot cross-inherit, and invalid modified specs refuse with `REPAIR_PRIOR_SPEC_INVALID` before Layer 1. R#36 and R#37 are the correct behavioral anchors.

No v1.4 fold needed for this batch.

---

## Material Outcome

v1.3 should not proceed to canonicalization yet.

The v1.4 fold is narrow:

1. Add concrete realistic adapter-budget fixture sizes, p95 thresholds, sampling/warmup rules, and telemetry labels.
2. Split `ARXIV_OR_PAPERCLIP` timeout vs CLI error into deterministic external error mappings.
3. Close tie/no-match edge cases: mid-band scores, multi-anchor ordering, and reserved-class handling.
4. Close the audit envelope by defining `ProvenanceAuditMismatchReason` or binding `mismatch_reason` to an existing closed enum.
5. Bind fan-out seal identity with `fanout_generation_id`, `sealed_at`, and accepted branch ids.

No council pass-2 is indicated. No covenant-axis escalation surfaced.

---

## Recommended Next Step

Fold `spec-brief.md` from v1.3 to v1.4 using the five operational amendments above.

Because every remaining finding is a small, explicit closure criterion, a full pass-4 is optional if v1.4 is limited to those amendments. A lightweight Codex receipt check may still be prudent before canonicalization as Decision 42 / ADR 0047, especially if the p95 table introduces new numeric commitments.

Plain English: v1.3 wrote the edge-case rulebook, but five cells still say “you decide” where production code needs a rule. v1.4 should turn those cells into fixed answers.
