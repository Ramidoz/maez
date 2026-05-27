# Kant — Council Pass-1 Review — Recall-Axis Dispatcher v1

**Reviewer:** Kant (categorical rules / universalizability / structural form)
**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1 (HEAD `9110084`)
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

The brief is structurally serious. The three principles are close to categorical, the closed vocabularies extend along the ADR 0046 discipline, and the Layer 0/1/2 partition is honestly bounded. But several invariants and one vocabulary cell admit silent exceptions that, under the categorical test (could every dispatcher-instance follow this rule without contradiction?), do not survive. Findings below.

---

## Blocking

### B1 — `ProvenanceFraming` is not categorically exhaustive over the partition

**Step 1 (claim):** The three-value enum (`SUBSTRATE_ONLY_UNVERIFIED`, `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, `FRESH_ONLY`) covers every cell of (substrate-presence × fresh-presence × explicit-signal).

**Step 2 (evidence):** Section 6 lists three values; §4 maps them to three doctor-analogy asymmetries; §7/D4 makes `provenance_framing` load-bearing for assembly template selection.

**Step 3 (cells):** The partition is at minimum 2×2×3 = 12 cells. Two collapse cleanly: (no-substrate × no-fresh × *) and the explicit-edge cases. But two cells have no framing:
  - (substrate-present × fresh-attempted-and-failed × no-explicit-signal) — the literal Finding 19 shape *after* the fix lands and a fetch is tried. Doctor analogy: labs ordered, lab machine broken, history available. This is NOT `SUBSTRATE_ONLY_UNVERIFIED` (we *did* attempt verification and failed), and NOT hybrid (no fresh evidence to compose). It needs an honest "attempted-but-unverified" framing.
  - (no-substrate × no-fresh × no-explicit-signal) — degenerate empty. Currently falls into none of the three.

**Step 4 (canon at risk):** ADR 0044 closing axiom — "provenance forever." A framing-less answer cannot enforce provenance discipline. `feedback_no_fabrication` — claiming verified state when the fetch failed is exactly the fabrication-of-validation shape.

**Step 5 (alternative):** Add `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` (labs-ordered-broken case) and `NO_GROUND` (neither available; refuse-honestly framing). Or make explicit that `SUBSTRATE_ONLY_UNVERIFIED` carries an optional `fetch_attempt: Failed` sub-field — but then it is no longer a flat closed enum and §6 is wrong.

**Step 6 (downstream):** R#7 currently asserts unverified caveat for substrate-only. It does not distinguish "didn't try" from "tried, failed" — both render identically under the current enum, which is the producer-causality laundering shape (caller cannot tell whether Maez witnessed an attempt).

**Step 7 (precedent):** This is the WitnessStatus argument from Kant B1/M1 in the sandbox-witness pass — absence-is-structured. "Attempted-and-failed" is structurally distinct from "didn't attempt" and must surface in the witness, not be collapsed.

**Step 8 (fix):** Either extend the enum (preferred, matches ADR 0046 closed-vocab discipline) or land an explicit invariant that fetch-failure paths route through `FRESH_ONLY` with empty external_sources and a witnessed `fetch_attempt_outcome` — and update R#7/R#8 to assert the distinction.

### B2 — D2 ("Hybrid Default") admits a silent "or is likely to exist" exception that breaks universalizability

**Step 1:** D2 says hybrid is default "when relevant substrate exists *or is likely to exist*."

**Step 2:** §5 Layer 0 step 4 — "Consult substrate inventory summaries to determine whether Maez likely has relevant owned substrate."

**Step 3 (cells):** "Likely to exist" is a probabilistic verdict. Under producer-causality (ADR 0042), the substrate either witnesses presence (inventory hit) or it does not. A "likely" verdict that is neither witnessed-present nor witnessed-absent is a substrate-side probabilistic claim with no producer.

**Step 4 (canon at risk):** ADR 0042 — caller-score laundering, but at the *internal* layer: Layer 0 launders an inventory-heuristic verdict as composition authority. `feedback_canon_governs_canon` — witness before claim.

**Step 5 (alternative):** Two cases must be split: (a) inventory witnesses presence → hybrid; (b) inventory witnesses absence → fresh-only with explicit `no_relevant_substrate` marker; (c) inventory cannot answer (unindexed surface) → spec must declare `substrate_availability: UNKNOWN` rather than silently defaulting to hybrid.

**Step 6 (downstream):** D5 already says "inventory is evidence, not authority" — D2 silently contradicts D5 by promoting inventory-likelihood-heuristic to composition default. Second-order contradiction inside the invariant set itself.

**Step 7 (precedent):** This is exactly the `feedback_fold_second_order_contradictions` failure shape — a local amendment (D2) creates a downstream contradiction with another load-bearing rule (D5).

**Step 8 (fix):** Rewrite D2 to require witnessed-presence OR witnessed-unknown; in the unknown case, hybrid is permitted but the spec must carry an `inventory_witness: UNKNOWN` field that the assembly layer surfaces.

---

## Major

### M1 — Layer architecture is not categorically a strict pipeline (0 → 1 → 2)

**Step 1:** §5 implies every query traverses Layer 0, then Layer 1, then Layer 2.

**Step 2:** Layer 2 input includes "previous-turn spec if available" — meaning Layer 2 *precedes* Layer 1 logically when the turn is a repair (it modifies the spec Layer 1 will then act on). The brief acknowledges this ("Layer 2 does not own base composition decisions") but does not state the categorical order.

**Step 3 (cells):** For first-turn queries: 0 → 1 (no Layer 2). For repair turns: 0 → 2 → 1, or arguably 2 → 0 → 1. The categorical claim "no layer silently performs work owned by another" is violated if Layer 2 runs between 0 and 1 without being declared in the pipeline shape.

**Step 4 (canon):** Categorical-imperative test — the rule "every query passes 0, then 1, then 2" is not universalizable across the repair-turn class.

**Step 5 (alt):** State the order as `0 → (2 if repair) → 1`, and make D8 explicit that Layer 2's output is the Layer 1 input on repair turns.

**Step 6 (downstream):** R#12 will pass under either ordering, so the test does not pin the order — a category error.

**Step 8 (fix):** Add a "Layer order" subsection in §5 that names the categorical pipeline shape per turn-class; tighten R#12 to assert Layer 2 ran *before* Layer 1 on repair turns.

### M3 — `CompositionHint` and `provenance_framing` are not orthogonal; closed-vocab product space is underspecified

**Step 1:** §6 lists 6 `CompositionHint` values and 3 `ProvenanceFraming` values. The four-field spec implies these are independently chosen.

**Step 2:** But `CompositionHint = SUBSTRATE_ONLY` with `ProvenanceFraming = FRESH_ONLY` is incoherent; `CompositionHint = FRESH_THEN_CONTEXTUALIZE` with `ProvenanceFraming = SUBSTRATE_ONLY_UNVERIFIED` is incoherent.

**Step 3 (cells):** 6×3 = 18 product cells; perhaps 5–6 are coherent. The brief does not declare the legal product subset.

**Step 4 (canon):** ADR 0046 — closed vocabularies must extend coherently. Two co-varying closed vocabularies whose legal product is unspecified is a half-closed system.

**Step 5 (alt):** Either (a) declare the legal `(hint, framing)` pairs as a closed table, or (b) collapse to one vocabulary, or (c) make `provenance_framing` a deterministic function of `(hint, substrate_sources, external_sources)` rather than an independent field.

**Step 8 (fix):** Add §6.5 "Legal product space" enumerating coherent pairs; add an invariant D11 refusing incoherent pairs at construction; add a RED anchor R#16 for the refusal.

### M4 — D6 ("No Caller-Supplied Composition Verdict") does not say what counts as "caller"

**Step 1:** D6 forbids caller-supplied `composition_hint`, `provenance_framing`, source selections.

**Step 2:** "Caller" is undefined. The owner utterance carries explicit-signal lexemes (`search`, `from your notes`) that D3 says *override* the default. Is the owner-as-caller supplying composition verdict via natural language?

**Step 3 (cells):** Three caller classes: (a) owner utterance, (b) upstream code (brain_loop, telegram handler), (c) test harness. D6 is categorical only over (b)/(c). Owner-language signals are *evidence the substrate weighs*, not caller-supplied verdicts. This needs to be explicit.

**Step 4 (canon):** ADR 0042 producer-causality — the substrate computes the verdict from owner-evidence. The brief currently leaves a category-ambiguity that an implementer could resolve wrongly.

**Step 8 (fix):** Restate D6: "No non-owner caller may supply final `composition_hint`, `provenance_framing`, or source selections. Owner-utterance lexemes are evidence; the substrate weighs them and computes the verdict per D3." Add an R#17 that asserts an upstream handler cannot pass a `composition_hint` kwarg into Layer 0.

---

## Minor

### m1 — `ExternalSource` value `NONE` is a category error

`NONE` is the absence of an external source; the field is already `list[ExternalSource]` which expresses absence via empty list. Including `NONE` as a list element creates two ways to encode "no external" — a non-canonical-form failure. Remove `NONE`. (Not load-bearing; framing-only, no 8-step trace required.)

### m2 — `SANDBOX_WITNESSES` carries a use-restriction the type cannot enforce

§6 says sandbox-witness rows are "readable for procedural questions about fixes; not used to authorize new ratification." This is a *consumer-side* discipline that the type system cannot enforce. Either add an invariant D12 making this categorical, or note explicitly that the restriction lives in the assembly layer's prompt-template policy and is RED-tested.

### m3 — Principle 1 ("learn shape of ask") admits zero-shot ambiguous asks silently

Principle 1 is categorical only if every utterance *has* a determinate shape. For genuinely ambiguous asks ("tell me about Qwen") the shape-detection produces multiple high-similarity archetypes — §4 says this triggers hybrid. That is a sound resolution, but Principle 1 should explicitly state: when shape is indeterminate, hybrid IS the categorically correct shape (because composition is the value, per Principle 2). Currently Principles 1 and 2 are independent — they should be cross-linked.

---

## NIT

- §4 example uses `memory_only_unverified` (lowercase); §6 uses `SUBSTRATE_ONLY_UNVERIFIED`. Rename consistently.
- D10 says external source labels do not grant credentials. True but redundant with the layer-architecture non-responsibility. Keep for explicitness; flag as deliberate.

---

## Closing synthesis

The brief is doing categorical work honestly. The three principles are nearly universalizable — Principle 3 (memory-as-context, fresh-as-evidence) is the most categorical of the three and survives every cell I tested. Principle 2 (composition is the value) survives when cross-linked with Principle 1 against ambiguous asks. Principle 1 survives when the indeterminate-shape case is explicitly resolved to hybrid rather than left silent.

The invariant set D1–D10 is the load-bearing surface and is where Kant's lens bites hardest. D2's "likely to exist" silently contradicts D5; that is a second-order contradiction inside the brief itself and must fold before ratification. The `ProvenanceFraming` three-cell enum cannot survive the fetch-attempted-failed case that the Reddit screenshot *itself* will produce after the fix lands — the brief would ship a framing that cannot represent its own motivating empirical shape. And the (hint × framing) product space being unspecified leaves the closed-vocabulary discipline half-closed.

These are amendment-class findings, not block-class. The Layer 0/1/2 partition is sound once the repair-turn order is named; the closed vocabularies extend along the ADR 0046 precedent once the product space is declared; `CompositionSpec`'s four fields become categorically exhaustive once the framing enum covers the attempted-and-failed cell. The brief is one fold away from ratifiable.

Recommended: **RATIFY-WITH-AMENDMENTS**, fold B1 + B2 + M3 before implementation begins, fold M1 + M4 in the mechanics half, file m1/m2/m3 as minor edits.
