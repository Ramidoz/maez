# Recall-Axis Dispatcher — Codex Engineering Pass-1 Synthesis

**Prepared:** 2026-05-26
**Artifact reviewed:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.1
**Dispatch brief:** `docs/slices/recall-axis-dispatcher/reviews/codex-engineering-pass1-brief.md`
**Review records:** `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass1.md`

This document is derivative reconstruction. The six `codex-*-pass1.md` files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Peirce | RATIFY-WITH-AMENDMENTS |
| Arendt | BLOCK |
| Huygens | BLOCK |
| Pauli | RATIFY-WITH-AMENDMENTS |
| Ohm | BLOCK |
| Lovelace / Bernoulli | BLOCK |

Engineering pass-1 result: **BLOCK v1.1 from canonicalization or implementation until folded.**

The design direction survived. No reviewer rejected composition-as-value, the doctor analogy, or the need for a dispatcher. The blockers are implementability gaps: schema fields that are required but undeclared, routes that are both "must include" and unavailable, legacy ingress paths that could bypass Layer 0, and mathematical/latency contracts that still rely on implementer intuition.

---

## Convergent Fold Batches

### Batch 1 — `CompositionSpec` schema must carry availability state explicitly

Seats: Peirce, Arendt, Huygens, Pauli, Lovelace / Bernoulli

v1.1 declares a four-field `CompositionSpec`, but D2 requires `inventory_witness: UNKNOWN`, absence markers, and visible availability limitations. Multiple reviewers found the same trapdoor: implementers cannot write a closed constructor, serializer, prompt renderer, or replay fixture without either violating the schema or hiding state in ad hoc metadata.

Required v1.2 fold:

- promote availability/inventory state into the declared schema;
- define closed values for inventory witness, at minimum `PRESENT`, `ABSENT`, and `UNKNOWN`;
- define how `no_relevant_substrate`, reserved-source unavailability, and trust-scope limitations are represented;
- require serialization, inheritance, audit, and rendering tests for these fields;
- stratify hybrid-default validation by inventory state so `UNKNOWN` does not count as confirmed substrate presence.

### Batch 2 — Active vs reserved source state must be first-class

Seats: Arendt, Huygens, Pauli, Ohm, Peirce

v1.1 says Layer 1 must include sources that are explicitly dependent on future work (`LIVED_GRAPH`, `WEB_FAST_TURNS` / `CROSS_SURFACE_OWNER_TURNS`) while also saying G9/G11 remain separate backlog items. `CROSS_SURFACE_OWNER_TURNS` appears in the Layer 1 route list but not in `SubstrateSource`.

Required v1.2 fold:

- split source state into executable v1 sources vs reserved/unavailable labels;
- align `CROSS_SURFACE_OWNER_TURNS` and `WEB_FAST_TURNS` naming or remove one;
- define readiness probes for G9/G11-dependent routes;
- require reserved routes to return typed unavailable results, not enter normal fan-out;
- mark `FRONTIER_CONSULT` reserved/non-executable until G3 exists;
- add tests proving reserved labels cannot execute.

### Batch 3 — Full JARVIS replacement needs exhaustive ingress coverage

Seats: Arendt, Pauli

v1.1 says Layer 0 fully replaces `_should_run_jarvis_loop`, but the test anchor names one `brain_loop.py` short-circuit. Reviewers found that alternate owner reply paths could still run tool/fetch/prompt assembly before dispatcher spec construction.

Required v1.2 fold:

- enumerate every owner reply ingress in scope: Telegram, web owner bridge, voice/electron if applicable, daemon fast paths, brain loop, action/tool continuation paths, and pending-offer web-search branches;
- require dispatcher-before-tool and dispatcher-before-recall tests for each in-scope path;
- mark any out-of-scope ingress with a visible availability limitation;
- cite fully qualified paths for legacy JARVIS gates.

### Batch 4 — Archetype scoring needs an executable threshold calculus

Seats: Lovelace / Bernoulli

v1.1 uses phrases like "high similarity", "sharp dominance", and "multiple high-scoring archetypes" but defines no thresholds, margins, tie rules, class aggregation, or fallback rule. The RED tests would require implementers to invent local constants.

Required v1.2 fold:

- define prototype vs centroid scoring;
- define cosine normalization and class-score aggregation;
- define `min_accept`, `dominance_margin`, `multi_match_delta`, no-match fallback threshold, and tie handling;
- define precedence between explicit lexemes, inventory state, repair state, and embedding ranking;
- define exact fallback `CompositionHint`, `ProvenanceFraming`, and source-selection rule for no-match cases.

### Batch 5 — Archetype artifact and replay corpus must be versioned and statistically meaningful

Seats: Lovelace / Bernoulli

v1.1 adopts archetype classes A-K but leaves the v0 archetype set as evidence, not an implementation input. R#1a validates only a corpus of at least five witnessed turns without sampling rule, class coverage, confusion matrix, or pass/fail criteria.

Required v1.2 fold:

- include or reference a versioned archetype manifest with prototype text, class ids, empirical/proposed tags, weights if any, reserved/executable state, and a hash or fixture path;
- require paired sentinel examples for relational-memory vs external-world asks;
- require replay fixtures to validate the full `CompositionSpec`, not only `provenance_framing`;
- pre-register corpus selection, minimum class coverage, negative-class coverage, false-hybrid ceiling, and amendment triggers;
- avoid claiming "real query distribution" unless distribution sampling is defined.

### Batch 6 — Shared MiniLM encoder ownership and lifecycle must be concrete

Seats: Huygens, Ohm, Lovelace / Bernoulli

v1.1 names `memory/embedder.py` and a shared `MiniLMEncoder`, but does not specify the API or lifecycle. Chroma currently owns embedding internally via collection construction, and Layer 0 latency budgets do not say whether encoder/model initialization is included.

Required v1.2 fold:

- define `memory/embedder.py` API exactly: singleton accessor, `encode(text | list[str])`, Chroma-compatible embedding-function surface, and contract validation against `embedding_contract.json`;
- require `MemoryManager` / Chroma collection construction to consume the shared encoder if v1 depends on shared ownership;
- define encoder lifecycle and prewarm behavior;
- define whether Layer 0 "cold" includes encoder initialization; if not, add separate startup/prewarm budget;
- add tests that fail if dispatcher and Chroma instantiate separate encoders.

### Batch 7 — InventorySummary needs a per-source contract and invalidation model

Seats: Huygens, Ohm

v1.1 requires cached inventory summaries and forbids live `COUNT(*)` per reply, but does not define per-source cursors, Chroma/WAL behavior, writer hooks, privacy gates, or UNKNOWN semantics.

Required v1.2 fold:

- name an `InventorySummary` module;
- add a per-source registry with path/collection, count query, cursor query, cache key, invalidation source, UNKNOWN fallback, and privacy gate;
- distinguish SQLite WAL, Chroma, file-backed, and bounded-private-reader sources;
- require tests proving Layer 0 does not run live per-substrate counts;
- require stale/UNKNOWN inventory to be visible in `CompositionSpec` and output framing.

### Batch 8 — Prompt assembly and audit enforcement need an owner module and metadata contract

Seats: Pauli, Peirce

v1.1 says `provenance_framing` drives rendering and self-claim/fabrication audit, but does not name the rendering module/API or audit metadata envelope. Correct specs could be emitted and then ignored by scattered prompt builders.

Required v1.2 fold:

- name the module/API that consumes `CompositionSpec` and renders provenance templates;
- require all owner synthesis surfaces to route through it;
- define template set as a closed vocabulary;
- define audit payload fields passed into `audit_assistant_text` / `self_claim_audit`;
- define whether framing mismatch rewrites, blocks, or records a fabrication event;
- require behavior tests showing `provenance_framing` changes rendered output shape and mismatched blocks refuse.

### Batch 9 — Refusal semantics and caller-supplied verdict tests must cover the full verdict surface

Seats: Peirce, Pauli

v1.1 says runtime extension, incoherent legal-product pairs, and caller-supplied composition verdicts are refused, but does not define refusal type, reason codes, audit path, or fail-closed behavior. Existing anchors emphasize `composition_hint` while D6 forbids several verdict fields.

Required v1.2 fold:

- define closed `DispatcherRefusalReason` values;
- define no downstream JARVIS/tool/fetch/recall/render execution after construction refusal;
- define audit/logging expectation for each refusal;
- test refusal at serialized/public boundaries and reply paths;
- require tests for caller-supplied `composition_hint`, `provenance_framing`, `substrate_sources`, and `external_sources`;
- require one negative and one positive fixture if dynamic vocabulary growth through maintenance proposals is in v1 scope.

### Batch 10 — Repair-state handling must become a finite state machine

Seats: Arendt, Pauli, Peirce, Ohm

v1.1 says Layer 2 inherits prior specs with TTL and crash recovery, but the product table includes `REPAIR_INHERIT_PRIOR_SPEC` procedurally rather than as closed legal pairs. The crash cache is under-keyed and the first-turn/stale/cross-surface cases are unspecified.

Required v1.2 fold:

- decide whether repair is a modifier outside `CompositionHint` or enumerate legal post-repair framings;
- define finite states: `NO_PRIOR`, `PRIOR_VALID`, `PRIOR_EXPIRED`, `CRASH_RECOVERED`;
- key prior spec storage by bond id, surface, turn/conversation id, timestamp, and TTL;
- define cleanup cadence, max entries, persisted schema, and invalidation;
- require tests for first-turn repair, stale prior, cross-surface concurrent turns, crash recovery, and post-repair construction validation.

### Batch 11 — Fan-out result, timeout, cancellation, and merge contract are missing

Seats: Arendt, Ohm

v1.1 requires concurrent fan-out with per-branch timeouts but does not define `RecallBranchResult`, timeout values, global deadline, cancellation, deterministic merge order, max parallel branches, or output budget.

Required v1.2 fold:

- define `RecallBranchResult` states for success, empty, timeout, error, reserved unavailable, and privacy gated;
- define per-source timeout defaults, global Layer 1 deadline, max parallel branches, executor model, and cancellation behavior;
- define deterministic merge ordering;
- define max recall blocks/chars per source and total prompt budget contribution;
- require tests with slow branch + failed branch proving max latency and stable output ordering.

### Batch 12 — External fetch execution needs a bounded owner and error budget

Seats: Ohm, Lovelace / Bernoulli

v1.1 defines external sources and a fresh-attempted-unavailable framing, but not the execution owner, timeout, retry count, global fresh deadline, or mapping from fetch errors to provenance framing.

Required v1.2 fold:

- define which module owns external-source execution after Layer 0/Layer 1;
- define per-source timeout, max attempts, global fresh deadline, and stop conditions;
- define how web/reddit/fetch/arxiv/frontier errors map to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT`;
- define freshness scoring or explicitly defer freshness scoring out of v1.

### Batch 13 — Module placement must be explicit

Seats: Huygens, Pauli

v1.1 still says prompt assembly "likely" lives near an existing renderer and does not name paths for schema, dispatcher, inventory, embedder, readers, or renderer.

Required v1.2 fold:

- name concrete modules for schema/types, Layer 0 dispatcher, InventorySummary, shared embedder, Layer 1 readers/adapters, Layer 2 repair state, and provenance prompt renderer;
- remove "likely" from v1 deliverables or mark unresolved choices explicitly open;
- ensure module boundaries preserve the dispatcher vs producer-causality slice boundary.

### Batch 14 — Budget tests must cover cold, timeout, and realistic source count

Seats: Ohm, Arendt, Lovelace / Bernoulli

v1.1 tests only warm Layer 0 and generic fan-out. It estimates branch cost from 4 sources while the route list names 10 axes.

Required v1.2 fold:

- define warm vs cold states precisely;
- add cold/prewarm verification;
- add full-manifest scoring fixture;
- add slow-branch timeout, cancellation, and budget telemetry assertions;
- define source-selection limits and p95 adapter budgets using realistic local stores rather than pure mocks.

### Batch 15 — Nits and cross-reference fixes

Seats: Arendt, Huygens, Ohm, Pauli, Lovelace / Bernoulli, Peirce

Repeated low-severity corrections:

- fix "D2 must not laundering" to "D2 must not launder";
- fix `SANDBOX_WITNESSES` reference from D12 to D15;
- cite `core/brain/brain_loop.py:900` rather than `brain_loop.py:900`;
- use "witnessed-turn sample" unless true distribution sampling is defined.

---

## Material Outcome

v1.1 is not implementable honestly yet. The engineering pass found the same class of issue as the sandbox-witness pass-1: the concept is correct, but the machinery is still loose enough for ceremonial compliance.

Strongest convergence:

1. `CompositionSpec` needs typed availability/inventory metadata.
2. Source states must distinguish executable v1 routes from reserved/unavailable labels.
3. Full JARVIS replacement requires exhaustive owner ingress coverage.
4. Embedding/archetype scoring needs concrete thresholds and versioned inputs.
5. Inventory, fan-out, prompt assembly, and external fetch execution need explicit module/API ownership and budgets.

None of these findings require abandoning the dispatcher. They require v1.2 to become an implementation contract instead of a strong design brief.

---

## Recommended Next Step

Fold to `spec-brief.md` v1.2 before canonicalization or implementation. Do not dispatch implementation planning against v1.1.

The v1.2 fold should be structured around the 15 batches above while keeping the raw `codex-*-pass1.md` files as the witnessed engineering record.
