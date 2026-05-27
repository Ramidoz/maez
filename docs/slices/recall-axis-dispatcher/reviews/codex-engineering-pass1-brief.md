# Recall-Axis Dispatcher — Codex Engineering Pass-1 Brief

**Prepared:** 2026-05-26
**Artifact under review:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.1
**Council status:** Claude/council pass-1 folded into v1.1 at `a5f7898`.
**Review lane:** Codex engineering pass-1.

This pass reviews v1.1 for implementability. It does **not** re-litigate the
covenant/design axis already handled by the council fold.

---

## Scope

Review the v1.1 brief as an implementation contract. Ask whether an engineer
could build it without hidden trapdoors, ceremonial tests, unbounded latency,
ambiguous ownership, or paths that conflict with the current repo.

The expected output is an engineering review with:

- verdict: `RATIFY`, `RATIFY-WITH-AMENDMENTS`, or `BLOCK`
- Blocking / Major / Minor / Nit findings
- every Blocking or Major finding must cite v1.1 line(s) or section(s)
- every Blocking or Major finding must name the concrete implementation
  consequence and the closure criterion
- findings must stay in engineering lane unless a new covenant issue is
  inseparable from an implementation trapdoor

## Out of Scope

- Re-arguing the three anchor lines.
- Re-opening council pass-1 covenant findings unless v1.1 introduced a new
  engineering consequence while folding them.
- Scoping producer-causality consolidation.
- Scoping live-degradation triage.
- Scoping ADR 0046 hardening beyond references needed for dispatcher
  maintenance-proposal compatibility.

## Engineering Questions to Pressure

### 1. Layer 0 Ownership and JARVIS Replacement

v1.1 decides full replacement of `_should_run_jarvis_loop`. Is the replacement
mechanically well-scoped? Where should Layer 0 live, how does it intercept before
JARVIS, and what legacy code paths would still bypass it?

### 2. CompositionSpec Implementability

Are the four v1-minimal fields enough? Does the newly mentioned
`inventory_witness: UNKNOWN` imply a fifth field not declared in the structure?
Can callers be prevented from supplying composition verdicts while intra-Maez
organs still contribute evidence?

### 3. Closed Vocabulary and Legal Product Table

Can `SubstrateSource`, `ExternalSource`, `CompositionHint`,
`ProvenanceFraming`, and archetype classes A-K be implemented as closed enums
with refusal at construction? Are the legal `(CompositionHint ×
ProvenanceFraming)` pairs complete and testable?

### 4. InventorySummary and Latency Budget

D13 requires <=50ms warm / <=150ms cold and cached inventory. Does the repo have
the necessary invalidation hooks? Which stores can produce cheap row-count /
last-write-cursor summaries, and which would force slow reads?

### 5. Embedding Encoder Ownership

Council v1.1 expects `memory/embedder.py` as a shared MiniLM singleton consumed
by both Chroma and dispatcher. Does this align with the current embedding code?
What exact module/API should own the encoder without duplicating Chroma internals
or introducing dependency/resource drift?

### 6. Layer 1 Fan-Out and Dark Substrate Readers

D12 requires concurrent fan-out with per-branch timeouts. Are the named
substrate sources actually readable through stable APIs? Which sources need new
bounded readers before v1 can honestly route to them? Which should remain
reserved?

### 7. Prompt Assembly and Provenance Enforcement

v1.1 requires `provenance_framing` to select templates and change rendered
output shape. Which module owns that renderer? Can tests prove output shape
changes without brittle LLM text assertions? How does `self_claim_audit` or
fabrication logging consume provenance metadata?

### 8. Cross-Surface Scope and Owner Context

D7 is currently non-regression only. Does the dispatcher need a concrete
trust-scope union API to implement v1, or should web fast-turns stay reserved
until G9 closes? What is the least dangerous implementable boundary?

### 9. Frontier / External Source Labels

Does including `FRONTIER_CONSULT` as an `ExternalSource` create a misleading
implementation surface before G3 exists? Should it be a reserved enum value,
absent from v1, or present but non-executable?

### 10. RED Test Quality

Walk R#1-R#24. Do they test behavior or vocabulary existence? Which tests are
unit, integration, static, or observation-replay? Which anchors are too broad to
be meaningful in v1?

## Suggested Engineering Seats

Codex may compose its own roster. Suggested lanes:

- **Peirce:** refusal-path discipline, caller-supplied verdicts, tests that prove
  behavior rather than enum existence.
- **Arendt:** state transitions, cross-surface scope, concurrency/fan-out, legacy
  JARVIS replacement paths.
- **Huygens:** schema/API mechanics, embedder ownership, InventorySummary cache
  and invalidation.
- **Pauli:** module boundaries, prompt assembly enforcement, self-claim /
  fabrication integration, dynamic bypass paths.
- **Ohm:** latency, resource cost, timeout policy, operational feasibility.
- **Lovelace/Bernoulli:** recall-ranking math, archetype scoring, thresholding,
  empirical replay corpus and failure modes.

## Required Review Shape

Use this structure:

```markdown
# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: <Seat>

## Verdict

<RATIFY | RATIFY-WITH-AMENDMENTS | BLOCK>

## Findings

### Blocking

- **B1. <title>**
  - Evidence: <v1.1 section/line citation>
  - Engineering consequence: <what breaks or becomes unbuildable>
  - Closure criterion: <what v1.2 must say or require>

### Major

...

### Minor

...

### Nit

...

## Summary

<short engineering assessment>
```

If no findings of a severity exist, write `None`.
