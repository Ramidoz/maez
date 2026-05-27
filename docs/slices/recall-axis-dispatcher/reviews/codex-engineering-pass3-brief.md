# Recall-Axis Dispatcher — Codex Engineering Pass-3 Brief

**Prepared:** 2026-05-26
**Artifact under review:** `docs/slices/recall-axis-dispatcher/spec-brief.md` at v1.3
**Base commit:** `e3b01e3 docs(dispatcher): fold pass-2 findings into v1.3`
**Pass-2 synthesis:** `docs/slices/recall-axis-dispatcher/reviews/codex-engineering-synthesis-v1.2-pass2.md`
**Review lane:** Codex engineering panel pass-3 closure audit

---

## Opening Frame

This is a **closure audit with receipts**.

This pass verifies that the six operational-edge batches from `codex-engineering-synthesis-v1.2-pass2.md` are closed by v1.3. Re-opening the covenant axis, redesigning the dispatcher, or introducing new architecture is out of scope.

Findings must cite one of the six v1.3 fold batches and either confirm closure or name what remains open. Pass-3 is not asking whether the dispatcher is a good idea; it is asking whether v1.3 removed the remaining places where an implementer would have to invent behavior under pressure.

Happy paths prove the idea works; edge cases prove the system can be trusted.

---

## Scope

Review v1.3 only for closure of these six Codex pass-2 operational batches:

1. Audit metadata payload for provenance rendering and self-claim/fabrication audit.
2. Tie and no-match source-selection rules.
3. Fan-out cancellation and late-result behavior.
4. External-source error-class mapping and stop conditions.
5. Cross-surface repair isolation and post-repair validation.
6. Realistic-store p95 adapter-budget requirements and telemetry anchors.

Same-seat continuity is preferred where possible because pass-2 seats know the exact operational gaps they authored. Codex may compose the final roster, but reviewers should treat pass-2 batch closure as the job.

---

## Out of Scope

- Re-litigating whether the dispatcher is covenant-correct.
- Replacing the composition-layer architecture with a different design.
- Proposing new architecture not required to close one of the six pass-2 batches.
- Re-opening Codex pass-1 batches already closed in v1.2 unless v1.3 regresses a specific closure.
- Designing implementation code or implementation plans.
- Reviewing producer-causality consolidation, live-degradation triage, or ADR 0046 hardening.

---

## Required Output

Each reviewer must produce a per-batch closure table:

| Batch | v1.3 change cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Batch N | line(s) / section(s) | CLOSED / NIT / STILL OPEN | brief line(s), repo evidence, or pass-2 comparison |

### Verdict Definitions

**CLOSED**

The v1.3 brief materially closes the pass-2 batch. Cite the v1.3 line(s) that close it.

**NIT**

The batch is closed. The finding is typographical or framing-only and does not block ratification. NIT is not for "minor but real" engineering gaps.

**STILL OPEN**

The batch remains materially open. A STILL OPEN verdict must be actionable and include:

1. the specific v1.3 line(s) that fail to close the batch,
2. why those lines fail,
3. what v1.3 would need to contain for closure.

Without closure criteria, a STILL OPEN finding is incomplete.

---

## Escalation Rule

A finding that names a covenant principle — bond, sovereignty, never-delete, anti-laundering family, third-party-subject discipline, Maez's not-ours-to-control boundary, or bond-mediated voice — and is not one of the six pass-2 operational batches is structurally out of scope for pass-3.

Do not fold such a finding as engineering. Mark it **COVENANT-ESCALATION** and name the specific section that should receive a small focused council pass-2.

---

## Closure Criteria By Batch

Use this as the checklist. Reviewers may cite additional evidence, but each closure verdict should map to these criteria.

### Batch 1 — Audit Metadata Payload

Closed if v1.3 requires:

- a closed audit envelope emitted by `core/dispatcher/provenance_renderer.py`;
- an explicit no-raw-private-content rule;
- required payload fields sufficient for source-role/provenance comparison;
- a stated split of which fields go to `audit_assistant_text`, `core/safety/self_claim_audit.py`, or both;
- mismatch/refusal metadata sufficient to reconstruct why rendering or audit failed;
- a RED anchor proving the audit envelope is emitted.

Primary v1.3 surfaces to inspect:

- `Audit metadata contract (new v1.3)`.
- `R#30a`.

### Batch 2 — Tie and No-Match Source Selection

Closed if v1.3 requires:

- the exact outright-win threshold rule;
- the exact multi-match rule for scores within `multi_match_delta`;
- deterministic behavior when legal product-table composition cannot represent the combined classes;
- deterministic stable tie-break order;
- exact no-match source selection for `inventory_witness=PRESENT`, `UNKNOWN`, and `ABSENT`;
- reserved-source handling during fallback;
- a RED anchor proving ties and no-match source selection are deterministic.

Primary v1.3 surfaces to inspect:

- `Tie and no-match source-selection rules (new v1.3)`.
- `R#28a`.

### Batch 3 — Fan-Out Cancellation / Late Results

Closed if v1.3 requires:

- behavior at per-branch timeout;
- behavior at global Layer 1 deadline;
- a mechanically identifiable sealed merge set or equivalent seal mechanism;
- explicit prohibition on late branch results mutating merged recall, prompt blocks, or `CompositionSpec`;
- cleanup, bounded grace, quarantine, or equivalent handling after prompt fallback;
- cancellation/late-result telemetry fields;
- a RED anchor proving late results cannot mutate sealed prompt output.

Primary v1.3 surfaces to inspect:

- `Cancellation / late-result semantics (new v1.3)`.
- `D12`.
- `R#32a`.

### Batch 4 — External Error Mapping / Stop Conditions

Closed if v1.3 requires:

- closed failure classes for `WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, `ARXIV_OR_PAPERCLIP`, and `FRONTIER_CONSULT`;
- mapping from each failure class to a closed `AvailabilityLimitation`;
- stop conditions for timeout, empty result, API/network failure, bot/auth block, URL failure, max attempts, global fresh deadline, and reserved source;
- no implementer-local choice about whether to retry or continue for v1 cases;
- a RED anchor proving error classes map to availability limitations.

Primary v1.3 surfaces to inspect:

- `External error classes and stop conditions (new v1.3)`.
- `R#33a`.

### Batch 5 — Cross-Surface Repair Isolation / Post-Repair Validation

Closed if v1.3 requires:

- prior-spec lookup keyed at least by bond, surface, conversation, and turn;
- a collision-proof freshness identity or equivalent validation model including digest and TTL;
- simultaneous Telegram/web repair turns under the same bond unable to inherit each other's prior spec;
- post-repair modified specs passing normal `CompositionSpec` construction validation before Layer 1;
- invalid modified specs refusing before Layer 1;
- RED anchors proving cross-surface isolation and post-repair validation/refusal.

Primary v1.3 surfaces to inspect:

- `Repair finite-state machine`.
- `Cross-surface repair isolation is structural`.
- `R#36`.
- `R#37`.

### Batch 6 — Realistic p95 Adapter Budgets / Telemetry

Closed if v1.3 requires:

- adapter-budget fixtures using realistic local stores, not pure mocks;
- coverage for representative SQLite/WAL, Chroma, file-backed, and bounded-reader adapters;
- p95 assertions under realistic source counts;
- a distinction between unit mocks, mock integration tests, and realistic adapter-budget fixtures;
- telemetry assertions for cold/prewarm, source selection, slow-branch timeout/cancellation, full-manifest scoring, external-fetch stop, and total prompt-budget contribution;
- RED anchors proving realistic p95 budgets and telemetry.

Primary v1.3 surfaces to inspect:

- `R#38`.
- `R#39`.
- RED suite implementability split.

---

## Expected Final Summary

End with one of:

- **RATIFY v1.3 FOR CANONICALIZATION** — all six batches CLOSED.
- **RATIFY-WITH-NITS** — all six batches CLOSED, NITs should fold typographically before ADR mint.
- **STILL OPEN** — one or more operational batches remain materially open; name required v1.4 fold.
- **COVENANT-ESCALATION** — an out-of-scope covenant concern requires focused council pass-2.
