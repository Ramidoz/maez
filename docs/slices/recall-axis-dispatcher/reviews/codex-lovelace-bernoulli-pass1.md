# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Lovelace/Bernoulli

## Verdict

BLOCK

## Findings

### Blocking

- **B1. Archetype ranking has no executable threshold calculus**
  - Evidence: v1.1 says “High similarity,” “Sharp dominance,” and “No high similarity” drive spec construction, but defines no numeric thresholds, margins, score aggregation, or tie rules (`spec-brief.md:205-211`). Layer 0 later “use[s] archetype similarity ranking” while “allowing multiple high-scoring archetypes to contribute” (`spec-brief.md:247-254`).
  - Engineering consequence: implementers must invent magic numbers. R#1/R#2/R#3/R#12 cannot be deterministic RED tests because the spec does not say what score is “high,” what margin is “dominant,” or when ambiguity becomes hybrid.
  - Closure criterion: v1.2 must define a scoring contract: prototype/centroid method, cosine normalization, class-score aggregation, `min_accept`, `dominance_margin`, `multi_match_delta`, fallback threshold, and precedence between explicit lexemes, inventory, repair state, and embeddings.

- **B2. Witnessed-turn replay corpus is too small and underspecified to validate hybrid default**
  - Evidence: v1.1 marks hybrid default as “design-by-extrapolation pending observation-window validation” (`spec-brief.md:90`, `spec-brief.md:345`) but R#1a requires only “a corpus of ≥5 witnessed runtime turns” to validate “real query distribution” (`spec-brief.md:480`). Predicted effect says runtime divergence revises the brief (`spec-brief.md:538`).
  - Engineering consequence: `n>=5` with no sampling rule, confusion matrix, acceptance threshold, or negative-class coverage is ceremonial validation. A cherry-picked corpus could ratify an over-broad hybrid default while missing fresh-only, recall-only, relational-memory, and repair false positives.
  - Closure criterion: v1.2 must pre-register corpus construction and pass/fail criteria: consecutive or explicitly sampled witnessed turns, minimum class coverage, full expected `CompositionSpec`, adjudication process, hybrid precision/recall or false-hybrid ceiling, and amendment triggers when runtime disagrees.

### Major

- **M1. Archetype artifact is not versioned as an implementation input**
  - Evidence: v1.1 says the v0 archetype set “supplies these initial classes as evidence, not canon” while adopting class names as the review surface (`spec-brief.md:349-365`).
  - Engineering consequence: the dispatcher has no canonical prototype list to encode. Engineers can disagree on which archetype strings count, how proposed vs empirical examples are weighted, and whether reserved classes participate in scoring.
  - Closure criterion: v1.2 must include or reference a versioned archetype manifest with prototype texts, class ids, empirical/proposed tags, weights if any, reserved/executable status, and a hash or fixture path used by tests.

- **M2. Relational-memory versus content-anchored external-world split lacks paired negative examples**
  - Evidence: Layer 0 must distinguish relational-memory shape from content-anchored external-world shape (`spec-brief.md:251`), and routes “what did you think when I first told you about X?” away from hybrid (`spec-brief.md:344`).
  - Engineering consequence: semantically adjacent turns like “what did you think when I told you about Qwen?” versus “what do people think about Qwen?” are likely embedding-near but operationally opposite. Without sentinel pairs, the model can silently over-fetch private relational asks or under-fetch external-world asks.
  - Closure criterion: v1.2 must require paired replay fixtures for relational/content contrasts and define which detector has priority when embedding similarity conflicts with relational-shape evidence.

- **M3. `UNKNOWN` inventory is counted as hybrid without separating statistical cases**
  - Evidence: D2 emits hybrid when inventory witnesses presence, and also when inventory is `UNKNOWN`, with `inventory_witness: UNKNOWN` surfaced (`spec-brief.md:390-396`).
  - Engineering consequence: replay metrics will conflate “hybrid because substrate exists” with “hybrid because inventory could not answer.” That can inflate hybrid-default success while hiding inventory failure or absence.
  - Closure criterion: v1.2 must require validation stratified by inventory witness state: `PRESENT`, `ABSENT`, `UNKNOWN`. Hybrid-default empirical claims should only count `PRESENT` separately from `UNKNOWN`.

- **M4. Freshness scoring is referenced but not specified**
  - Evidence: Layer 0 input includes “freshness policy” (`spec-brief.md:237`), the vocabulary includes `SUBSTRATE_THEN_FETCH_IF_STALE` (`spec-brief.md:335`), and Q10.2 leaves freshness threshold open (`spec-brief.md:515`).
  - Engineering consequence: stale-vs-fresh decisions become ad hoc per implementer, especially for Reddit, web search, Telegram temporal recall, and lived episodes. Tests can assert vocabulary but not correct behavior.
  - Closure criterion: v1.2 must define either source-specific freshness policies or an explicit v1 rule that freshness scoring is out of scope and cannot affect Layer 0 decisions yet.

### Minor

- **m1. R#1a validates only framing, not the full dispatcher decision**
  - Evidence: R#1a commits to expected `provenance_framing` per turn (`spec-brief.md:480`).
  - Engineering consequence: a replay can pass with the right framing but wrong `substrate_sources`, `external_sources`, or `composition_hint`.
  - Closure criterion: Validate the full `CompositionSpec`, not only framing.

- **m2. No-match fallback is underspecified**
  - Evidence: “No high similarity” falls back to “broader heuristic / safer default (substrate-first with optional fetch)” (`spec-brief.md:209`).
  - Engineering consequence: “optional fetch” can mean different legal product pairs, producing non-repeatable behavior.
  - Closure criterion: Define the exact fallback `CompositionHint`, `ProvenanceFraming`, and source-selection rule.

- **m3. Latency test does not cover scoring worst case**
  - Evidence: D13 gives warm/cold Layer 0 budgets (`spec-brief.md:446-448`), but R#18 only names warm budget (`spec-brief.md:498`).
  - Engineering consequence: archetype ranking over the full manifest could pass warm-only tests while cold encoder load or worst-case scoring violates the contract.
  - Closure criterion: Add cold-budget and full-manifest scoring fixtures, or explicitly scope cold encoder initialization outside Layer 0.

### Nit

- **n1. Grammar typo in D2**
  - Evidence: “D2 must not laundering…” (`spec-brief.md:398`).
  - Engineering consequence: None.
  - Closure criterion: Change to “must not launder.”

- **n2. “Hybrid default” should avoid calling R#1a validation of real distribution unless sampling is defined**
  - Evidence: R#1a says it validates against “real query distribution” (`spec-brief.md:480`).
  - Engineering consequence: Wording overclaims the statistical strength of the replay corpus.
  - Closure criterion: Say “witnessed-turn sample” unless v1.2 defines distribution sampling.

## Summary

The architecture is pointing in the right direction, but the Lovelace/Bernoulli lane cannot ratify v1.1 as an implementation contract yet. The current brief names the right mathematical surfaces but leaves the actual decision calculus, replay validation, and failure metrics undefined. Without those, the dispatcher will be buildable only by local engineer intuition, and its hybrid-default claim can pass tests without earning empirical trust.
