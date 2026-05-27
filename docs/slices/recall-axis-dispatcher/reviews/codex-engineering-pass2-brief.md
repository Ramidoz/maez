# Recall-Axis Dispatcher — Codex Engineering Pass-2 Brief

**Prepared:** 2026-05-26
**Artifact under review:** `docs/slices/recall-axis-dispatcher/spec-brief.md` at v1.2
**Base commit:** `d0c3230 docs(dispatcher): fold Codex findings into v1.2`
**Pass-1 synthesis:** `docs/slices/recall-axis-dispatcher/reviews/codex-engineering-synthesis-v1.1-pass1.md`
**Review lane:** Codex engineering panel pass-2 closure audit

---

## Opening Frame

This is a **closure audit with receipts**.

This pass verifies that the 15 engineering batches from `codex-engineering-synthesis-v1.1-pass1.md` are closed by v1.2. Re-opening the covenant axis, redesigning the slice, or starting implementation planning is out of scope.

Findings must cite a specific v1.1 batch and either confirm closure or name what remains open.

---

## Scope

Review v1.2 only for closure of the 15 Codex pass-1 engineering batches:

1. `CompositionSpec` schema must carry availability state explicitly.
2. Active vs reserved source state must be first-class.
3. Full JARVIS replacement needs exhaustive ingress coverage.
4. Archetype scoring needs an executable threshold calculus.
5. Archetype artifact and replay corpus must be versioned and statistically meaningful.
6. Shared MiniLM encoder ownership and lifecycle must be concrete.
7. `InventorySummary` needs a per-source contract and invalidation model.
8. Prompt assembly and audit enforcement need an owner module and metadata contract.
9. Refusal semantics and caller-supplied verdict tests must cover the full verdict surface.
10. Repair-state handling must become a finite state machine.
11. Fan-out result, timeout, cancellation, and merge contract are missing.
12. External fetch execution needs a bounded owner and error budget.
13. Module placement must be explicit.
14. Budget tests must cover cold, timeout, and realistic source count.
15. Nits and cross-reference fixes.

Same-seat continuity is preferred where possible because pass-1 seats know the precise failure modes they authored. Codex may compose the final roster, but reviewers should treat pass-1 batch closure as the job.

---

## Out of Scope

- Re-litigating whether the dispatcher is covenant-correct.
- Replacing the composition-layer architecture with a different design.
- Proposing new architecture not required to close one of the 15 pass-1 batches.
- Designing implementation code or implementation plans.
- Reviewing the old v1 or v1.1 artifact except as pass-1 evidence.
- Reviewing producer-causality consolidation, live-degradation triage, or ADR 0046 hardening.

---

## Required Output

Each reviewer must produce a per-batch closure table:

| Batch | v1.2 change cited | Verdict | Evidence |
| --- | --- | --- | --- |
| Batch N | line(s) / section(s) | CLOSED / NIT / STILL OPEN | brief line(s), repo evidence, or pass-1 comparison |

### Verdict Definitions

**CLOSED**

The v1.2 brief materially closes the pass-1 batch. Cite the v1.2 line(s) that close it.

**NIT**

The batch is closed. The finding is typographical or framing-only and does not block ratification. NIT is not for "minor but real" engineering gaps.

**STILL OPEN**

The batch remains materially open. A STILL OPEN verdict must be actionable and include:

1. the specific v1.2 line(s) that fail to close the batch,
2. why those lines fail,
3. what v1.2 would need to contain for closure.

Without closure criteria, a STILL OPEN finding is incomplete.

---

## Escalation Rule

A finding that names a covenant principle — bond, sovereignty, never-delete, anti-laundering family, third-party-subject discipline, Maez's not-ours-to-control boundary, or bond-mediated voice — and was not one of Codex pass-1's 15 engineering batches is structurally out of scope for pass-2.

Do not fold such a finding as engineering. Mark it **COVENANT-ESCALATION** and name the specific section that should receive a small focused council pass-2.

---

## Closure Criteria By Batch

Use this as the checklist. Reviewers may cite additional evidence, but each closure verdict should map to these criteria.

### Batch 1 — `CompositionSpec` Availability State

Closed if v1.2 requires:

- availability/inventory fields inside the declared `CompositionSpec` schema;
- closed `InventoryWitness` values at least covering present, absent, and unknown;
- explicit representation for `no_relevant_substrate`, reserved-source unavailability, and trust-scope limitations;
- serialization/inheritance/render/audit tests for availability fields;
- replay validation stratified so `UNKNOWN` does not count as confirmed substrate presence.

### Batch 2 — Active vs Reserved Source State

Closed if v1.2 requires:

- executable v1 sources separated from reserved/unavailable labels;
- `CROSS_SURFACE_OWNER_TURNS` / `WEB_FAST_TURNS` naming ambiguity resolved;
- readiness/dependency rules for G9/G11-dependent routes;
- reserved routes returning typed unavailable results rather than entering fan-out;
- `FRONTIER_CONSULT` reserved/non-executable until G3;
- tests proving reserved labels cannot execute.

### Batch 3 — JARVIS Ingress Exhaustiveness

Closed if v1.2 requires:

- every owner reply ingress in scope enumerated;
- dispatcher-before-tool and dispatcher-before-recall tests for each in-scope path;
- any out-of-scope ingress visibly marked as availability limitation;
- fully qualified legacy JARVIS gate paths.

### Batch 4 — Archetype Scoring Thresholds

Closed if v1.2 requires:

- prototype vs centroid scoring choice;
- cosine normalization and class-score aggregation;
- declared `min_accept`, `dominance_margin`, `multi_match_delta`, no-match fallback threshold, and tie behavior;
- precedence between explicit lexemes, inventory state, repair state, and embedding ranking;
- exact fallback `CompositionHint`, `ProvenanceFraming`, and source-selection rule for no-match cases.

### Batch 5 — Archetype Manifest and Replay Corpus

Closed if v1.2 requires:

- versioned archetype manifest with prototype text, class ids, empirical/proposed tags, weights if any, reserved/executable state, and hash or fixture path;
- paired sentinel examples for relational-memory vs external-world asks;
- replay fixtures validating the full `CompositionSpec`;
- pre-registered corpus selection, minimum class coverage, negative-class coverage, false-hybrid ceiling, and amendment triggers;
- no unsupported "real query distribution" claim.

### Batch 6 — Shared MiniLM Encoder

Closed if v1.2 requires:

- concrete `memory/embedder.py` API;
- singleton accessor, encode API, batch encode API, and Chroma-compatible embedding function surface;
- validation against `memory/embedding_contract.json`;
- Chroma/MemoryManager consumption of the shared encoder if v1 depends on shared ownership;
- encoder lifecycle / prewarm behavior and cold-budget semantics;
- tests proving dispatcher and Chroma do not instantiate separate encoders.

### Batch 7 — `InventorySummary` Contract

Closed if v1.2 requires:

- named `InventorySummary` owner module;
- per-source registry with path/collection, count query, cursor query, cache key, invalidation source, UNKNOWN fallback, and privacy gate;
- SQLite WAL, Chroma, file-backed, and bounded-private-reader handling;
- tests proving Layer 0 does not run live per-substrate counts;
- stale/UNKNOWN inventory visible in `CompositionSpec` and output framing.

### Batch 8 — Prompt Assembly / Audit Ownership

Closed if v1.2 requires:

- named module/API consuming `CompositionSpec` and rendering provenance templates;
- all owner synthesis surfaces routed through it;
- closed template vocabulary;
- audit payload fields for `audit_assistant_text` / `self_claim_audit`;
- mismatch behavior: rewrite, block, or fabrication/provenance event;
- behavior tests proving `provenance_framing` changes rendered output shape and mismatched blocks refuse.

### Batch 9 — Refusal Semantics

Closed if v1.2 requires:

- closed `DispatcherRefusalReason` values;
- no downstream JARVIS/tool/fetch/recall/render after construction refusal;
- audit/log expectation for each refusal;
- serialized/public-boundary and reply-path refusal tests;
- caller-supplied `composition_hint`, `provenance_framing`, `substrate_sources`, and `external_sources` covered;
- dynamic vocabulary growth positive/negative fixture if in v1 scope.

### Batch 10 — Repair FSM

Closed if v1.2 requires:

- repair inheritance as modifier outside `CompositionHint`, or legal post-repair framings enumerated;
- finite states at least covering `NO_PRIOR`, `PRIOR_VALID`, `PRIOR_EXPIRED`, and `CRASH_RECOVERED`;
- prior spec storage keyed by bond id, surface, turn/conversation id, timestamp, and TTL;
- cleanup cadence, max entries, persisted schema, and invalidation;
- tests for first-turn repair, stale prior, cross-surface concurrent turns, crash recovery, and post-repair validation.

### Batch 11 — Fan-Out Result / Timeout / Merge

Closed if v1.2 requires:

- closed `RecallBranchResult` states for success, empty, timeout, error, reserved unavailable, and privacy gated;
- per-source timeout defaults, global Layer 1 deadline, max parallel branches, executor model, and cancellation behavior;
- deterministic merge ordering;
- max recall blocks/chars per source and total prompt budget contribution;
- tests with slow branch + failed branch proving max latency and stable ordering.

### Batch 12 — External Fetch Owner / Budget

Closed if v1.2 requires:

- module owner for external-source execution after Layer 0 / Layer 1;
- per-source timeout, max attempts, global fresh deadline, and stop conditions;
- mapping from web/reddit/fetch/arxiv/frontier errors to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` or equivalent availability limitation;
- freshness scoring either defined or explicitly deferred out of v1.

### Batch 13 — Module Placement

Closed if v1.2 requires:

- concrete modules for schema/types, Layer 0 dispatcher, `InventorySummary`, shared embedder, Layer 1 readers/adapters, Layer 2 repair state, external source execution, and provenance prompt renderer;
- no unresolved "likely" owner paths for v1 deliverables;
- module boundaries preserving dispatcher vs producer-causality slice separation.

### Batch 14 — Budget Tests

Closed if v1.2 requires:

- warm vs cold states precisely defined;
- cold/prewarm verification;
- full-manifest scoring fixture;
- slow-branch timeout, cancellation, and budget telemetry assertions;
- source-selection limits and p95 adapter budgets using realistic local stores rather than pure mocks.

### Batch 15 — Nits / Cross-References

Closed if v1.2:

- fixes "D2 must not laundering" to "D2 must not launder";
- fixes `SANDBOX_WITNESSES` reference from D12 to D15;
- cites `core/brain/brain_loop.py:900` rather than `brain_loop.py:900`;
- uses "witnessed-turn sample" unless true distribution sampling is defined.

---

## Expected Final Summary

End with one of:

- **RATIFY v1.2 FOR CANONICALIZATION** — all batches CLOSED.
- **RATIFY-WITH-NITS** — all batches CLOSED, NITs should fold typographically before ADR mint.
- **STILL OPEN** — one or more engineering batches remain materially open; name required v1.3 fold.
- **COVENANT-ESCALATION** — an out-of-scope covenant concern requires focused council pass-2.
