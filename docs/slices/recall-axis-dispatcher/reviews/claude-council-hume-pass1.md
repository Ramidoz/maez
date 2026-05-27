# Hume — Council Pass-1 Review — Recall-Axis Dispatcher v1

**Reviewer:** Hume (empirical scrutiny / inductive reasoning / cause-and-effect)
**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1 (HEAD `9110084`)
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

The brief is honestly scoped, the doctor analogy is teachable, and Sections 5–10 supply the closed-vocabulary discipline that a v1 mechanics half owes. But three load-bearing claims extrapolate beyond their witness base, and one (D1's primacy) is asserted as the right primary axis without the brief showing the alternative was considered. I cannot block — the framing is sound and the de-scoping is clean — but I require amendments before the brief enters Codex implementation lane.

---

## Blocking findings

### B1. Principle 2 / D2 / `C_HYBRID_CONTENT_ANCHORED`-as-default is built on a class with **zero empirical anchors**

**Severity:** Blocking.

The v0 archetype set (`docs/roadmap/dispatcher-archetypes-v0-2026-05-26.md` line 268) shows **Class C — MEMORY_THEN_FRESHNESS: 10 Total / 0 Empirical / 5 Proposed**. The author's own table says "No runtime examples yet; pure model-proposed; subject to refinement." The brief then promotes this exact class (renamed `C_HYBRID_CONTENT_ANCHORED`) from "zero empirical anchors / rare hybrid case" to **default** for ordinary content asks (§2 Principle 2, §6 closing line, §7 D2, §11 prediction #1).

This is precisely the inferential leap I am positioned to flag. The flip is justified in the brief by one Reddit screenshot (Finding 19) + one Rohit quote (*"if it just searches one specific topic I might as well do it myself"*) — a normative argument about value, not a witnessed runtime distribution. The 67% empirical anchor rate the brief leans on for credibility is the **Class A–B–D–E–F–H–I–J–K** number; Class C contributes **0** to that 67%.

The two arguments — "hybrid is the value Maez adds" (normative) and "hybrid is the empirical default" (descriptive) — are conflated. They can both be true, but only the first is witnessed by the current evidence base.

**8-step trace:**

1. **Dependency-map:** D2 ("Hybrid default for content-anchored asks") binds Layer 0's emission distribution to a class whose archetype examples were author-generated; R#1 RED-tests the default behavior; §11 predicts behavioral change in production.
2. **Write-path:** Layer 0 emits `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` for any content-anchored ask lacking explicit edge language — a structurally broad emission.
3. **Read-path:** prompt-assembly receives hybrid framing and issues both substrate recall AND external fetch on every such ask, doubling cost and surface area.
4. **Test-path:** R#1 uses one canonical phrase ("how's Qwen looking online?"). No RED test demonstrates that the *population* of content-anchored owner asks is hybrid-shaped, only that this one is.
5. **Fold-summary:** the brief must either (a) cite ≥3 distinct witnessed runtime turns where hybrid was the right answer and pure-recall/pure-fetch was wrong, OR (b) mark D2 explicitly as **"design-by-extrapolation; not corpus-witnessed; to be validated by observation window N."** Either is acceptable; conflating them is not.
6. **Cross-reference:** Mirrors my M1 from the sandbox-witness review — "the precedent corpus is invoked as ground truth but never mapped to invariants." Same failure mode, different slice.
7. **RED-test trace:** add R#1a — a witnessed-turn replay corpus (≥5 turns) where the brief commits in advance to whether each is hybrid/substrate-only/fresh-only, then runtime adjudicates. Without this, R#1 is a tautology.
8. **Verify-before-declaring:** static check fails. D2's evidentiary basis is one Reddit screenshot generalized via design intuition. Per `feedback_canon_governs_canon_witness_before_claim`, claim ≠ verdict.

**Required amendment:** Class C is renamed in v1 to flag its synthetic origin, OR D2 is marked "design-by-extrapolation pending observation," OR a witnessed-turn corpus is added. Brief does not enter Codex lane until one of these is chosen.

### B2. D1 (composition-before-routing) is asserted as the right *primary axis* without showing the alternative was considered

**Severity:** Blocking.

The user's prompt names the alternative explicitly: "always run substrate AND tool, compose afterward." The brief never engages this. D1 commits Maez to a **decision-then-act** topology (Layer 0 emits spec → Layer 1 recalls → fetch happens) when a **act-then-compose** topology (parallel substrate recall + speculative fetch → composition layer adjudicates) is at least equally consistent with the doctor analogy. A doctor often orders labs *and* reviews history simultaneously, then composes.

The decision-first topology is also the one that *failed* in the JARVIS classifier case. JARVIS's bug is not that it decided before acting — it is that it decided **wrong**. The brief inherits the same topology and proposes to make the decision smarter. That may be correct, but the brief presents D1 as load-bearing invariant rather than as a topology choice with tradeoffs.

This matters because R#15 / D9 / D10 boundary-keeping is easier in the decision-first model; cost and latency are easier in the act-then-compose model. Either is defensible; asserting the choice without showing the trade is what I flag.

**8-step trace:**

1. **Dependency-map:** D1 binds every reply-time path to "spec first." Layers 1 and 2 inherit this; R#4 enforces it.
2. **Write-path:** Layer 0 becomes a critical-path latency hop and a single point of misclassification.
3. **Read-path:** if Layer 0 misclassifies (as JARVIS did), recovery requires Layer 2 repair; the design pushes errors downstream rather than letting parallel evidence cancel them.
4. **Test-path:** no RED test compares decision-first vs parallel-then-compose latency, cost, or recovery characteristics.
5. **Fold-summary:** §5 must explicitly name the topology choice as a choice. One paragraph: "we chose decision-first because [X]; we did not choose parallel-then-compose because [Y]." Then D1 stands on stated grounds.
6. **Cross-reference:** `project_external_borrow_rule` — the brief borrows the "router with smarter detector" shape from JARVIS without showing that shape was built for the constraint Maez actually has (which is **honest composition**, not **fast routing**).
7. **RED-test trace:** none required if the topology choice is documented; the trace lives in §5 prose.
8. **Verify-before-declaring:** D1 currently reads as "obviously right." It is not obviously right. It is reasonable, but it inherits the same shape that just failed in production.

**Required amendment:** §5 gains a topology-choice paragraph. D1 stands; its grounds become visible.

---

## Major findings

### M1. `provenance_framing` driving prompt-assembly templates is asserted, not witnessed

**Severity:** Major.

§4 ("Mechanical enforceability") claims `provenance_framing` "drives template selection in prompt assembly" and "can be audited by post-generation `self_claim_audit`." Neither end of this contract is witnessed in the brief. The prompt-assembly layer is not cited at any file path. `self_claim_audit` is cited in §1 (the Finding 19 trace) but never shown to currently audit *template-shaped* claims. The audit at 18:13/18:14 logged a routing classification, not a provenance-framing breach.

This is a clean instance of the "shapes vs constraints" rule. The shape (templates labeled with provenance) is borrowed from RAG-with-citations systems; the constraint those shapes serve (verifiable provenance at generation time) is asserted as already present in Maez's stack.

**8-step trace:**

1. **Dependency-map:** D4 + R#6 + R#7 + R#8 all bind to `provenance_framing` reaching and shaping prompt assembly. R#6 is the load-bearing RED.
2. **Write-path:** Layer 0 emits the framing; assembly must consume it. No code path is named.
3. **Read-path:** `self_claim_audit` must detect framing-vs-output mismatches. No current audit rule is cited.
4. **Test-path:** R#6 says "prompt assembly receives `provenance_framing`." This tests presence at an API boundary, not structural enforcement.
5. **Fold-summary:** brief must cite the prompt-assembly module(s) and current audit rules; if they do not yet support framing-driven templates, this becomes scoped implementation work in this slice (not "already enforceable").
6. **Cross-reference:** mirrors my B2 from sandbox-witness pass-1 — `observed_effect` cannot be load-bearing unless its computation function is named.
7. **RED-test trace:** R#6 needs sibling R#6a — `test_provenance_framing_actually_changes_rendered_output_shape` — to distinguish API plumbing from enforcement.
8. **Verify-before-declaring:** without prompt-assembly file paths, this is asserted enforceability.

### M2. The 41-finding → 27-blocker → 19-unique-surface gap is not addressed

**Severity:** Major.

The user's prompt names this explicitly and they are right to flag it. The brief cites the testing dispatch in §1 and §8 but never enumerates **which architectural surfaces this slice closes vs which it cites without scoping.** §1 names live-degradation symptoms (envelope `char_cap=400`, cognition-cycle fixation, 11-streak duplicate outputs) that the dispatcher contract does not close. The closing paragraph de-scopes producer-causality and ADR 0046 hardening — good — but does not de-scope live-degradation triage with the same precision.

This is a framing finding, not a mechanics one. It does not require the 8-step trace per `feedback_fold_second_order_contradictions` — it is honesty-about-scope. **(Framing-only finding; no 8-step trace required.)**

**Required amendment:** §1 closing paragraph or §8 gains a "surfaces this slice does NOT close" enumeration, naming live-degradation triage, envelope-cap regression, and the cognition-cycle fixation as separate slices.

---

## Minor findings

### MIN1. "67% empirically anchored" is load-bearing but the user's prompt and the brief use the number for different things

The brief's "67% false-positive rate" (§1) is the JARVIS misroute rate; the archetype set's "67% empirically anchored" (anchored file, line 277) is the archetype-coverage rate. Two different 67% numbers in adjacent canon. Either is fine alone; together they invite confusion. **(Framing/citation-only; no trace required.)** Recommend the brief cite the archetype-anchor rate explicitly when leaning on the v0 set.

### MIN2. "All four Rohit-witnessed Reddit phrases anchored" for Class A is a 4-phrase corpus

Class A's 4 empirical anchors are all Reddit-Rohit phrases. The class is named `RECALL_FROM_SUBSTRATE` (general). Brief should either narrow Class A's name or acknowledge the corpus is Reddit-biased.

### MIN3. D7 (cross-surface scope) cites a problem the dispatcher does not own

The 5-disjoint-trust-scopes finding is a write-time / authentication issue. D7 says the dispatcher must not silently pin owner to `guest`. That is correct as a non-regression invariant, but the underlying fragmentation is not closed by this slice and the brief should say so.

### NIT1. Section 4's `CompositionSpec` Python type is shown but `SubstrateSource` / `ExternalSource` / `CompositionHint` / `ProvenanceFraming` are described as "specified in v1 mechanics half" in §4 and then *are* specified in §6. The "(specified in v1's mechanics half; framing-half draft does not enumerate them.)" parenthetical is now stale. Strike it. **(Typographical; no trace required.)**

---

## Closing synthesis

**What is witnessed:** Finding 19 is a single, well-traced runtime catch. The 41-finding testing dispatch produced 27 BLOCKERS across structural surfaces. The JARVIS classifier's 67% false-positive rate on 39 stress-test queries is a real measurement. Classes B, E, F, I, J of the v0 archetype set have ≥7/10 empirical anchors each. The Reddit-substrate-mute-at-reply phenomenon is structurally entrenched in the code (`brain_loop.py:324`, `recall_for_telegram` non-invocation).

**What is inferred:** that hybrid composition is the *default* shape of owner content-asks (Class C: 0 empirical anchors); that decision-first topology beats parallel-then-compose (never compared); that prompt-assembly templates can structurally enforce the labs/history seam (no module cited, no audit rule named); that the doctor analogy's role distinction maps cleanly onto Maez's substrate (analogy is teachable, mapping is asserted).

**Where the brief over-extends:** in promoting Class C from "rare hybrid case / zero anchors" to default class on the strength of one screenshot + one normative quote. The flip may be right — Rohit's value argument is the kind of argument that should drive design — but the brief presents it as if the empirical base demanded the flip. It does not. The empirical base demanded that JARVIS stop misrouting source-anchored queries; that is Class E, which has 8/10 anchors. Hybrid-as-default is a separate move and deserves separate witness.

**What is honestly scoped:** the producer-causality de-scoping (§ scope boundary) is clean and load-bearing. D9 holds the line. D10 holds the no-new-authority line. R#13–R#15 enforce these. This is the brief's strongest discipline.

**Verdict reasoning:** the amendments are bounded — three labels added, one corpus citation, one topology paragraph, one "surfaces not closed" enumeration. None require re-architecting. The framing layer is sound. RATIFY-WITH-AMENDMENTS, not RECONSIDER, because the brief is honest about its de-scopings even where it over-reaches on its claims.
