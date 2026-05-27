# Recall-Axis Dispatcher — Spec Brief v1.3

**Prepared:** 2026-05-26
**Slice:** Recall-Axis Dispatcher
**Parent/runtime base:** `d0c3230 docs(dispatcher): fold Codex findings into v1.2`
**Status:** v1.3 — Codex engineering pass-2 findings folded. Sections 1–4 preserve the framing half; Sections 5–11 carry the mechanics half; v1.1 folded council-pass-1 amendments; v1.2 folded Codex pass-1's 15 convergent batches; v1.3 folds Codex pass-2's six operational edge batches.
**Review lane:** Claude covenant / architecture council (pass-1 complete) + Codex engineering panel (pass-1 and pass-2 complete; v1.2 STILL OPEN folded into v1.3).
**Operator:** Rohit relays and dispatches; Codex does not auto-dispatch.
**Council pass-1 result:** all six roles RATIFY-WITH-AMENDMENTS. 5 BLOCKING, 17 Major, 16 Minor, 10 NIT. v1.1 folds 15 convergent batches; six review files preserved verbatim at `reviews/claude-council-{locke,kant,hume,buber,descartes,ohm}-pass1.md`; synthesis at `reviews/claude-council-synthesis-v1-pass1.md`.
**Codex engineering pass-1 result:** 4 BLOCK, 2 RATIFY-WITH-AMENDMENTS. v1.1 blocked from canonicalization or implementation until folded. Six review files preserved verbatim at `reviews/codex-{peirce,arendt,huygens,pauli,ohm,lovelace-bernoulli}-pass1.md`; synthesis at `reviews/codex-engineering-synthesis-v1.1-pass1.md`.
**Codex engineering pass-2 result:** all six seats STILL OPEN, no covenant escalation. v1.2 blocked from canonicalization until six operational edge batches were folded. Six review files preserved verbatim at `reviews/codex-{peirce,arendt,huygens,pauli,ohm,lovelace-bernoulli}-pass2.md`; synthesis at `reviews/codex-engineering-synthesis-v1.2-pass2.md`.

**Scope boundary (load-bearing):** This slice governs *retrieval routing and composition*. Three explicitly de-scoped surfaces, each its own slice:

1. **Producer-causality consolidation** — generalizing ADR 0042's anti-laundering discipline to organs adjacent to felt-time (`inner_residue`, `consequence_memory`, `wonderings.record_pursuit`, `reflection_audit`, `relationship_graph.add_edge`, `signal_gate.SignalObservation`). The dispatcher cites the testing dispatch findings on producer-causality but does not scope the consolidation work. Overlaps in symptom (caller-supplied authority laundering), distinct in surface (dispatcher = read-time routing; consolidation = write-time integrity).
2. **Live degradation triage** — envelope `char_cap=400` below fallback floor, cognition cycle 11-streak fixation, Reddit retrieval declared canonical but blocked. Each needs its own seam-vs-slice classification per `feedback_seam_vs_slice_cooling_off`. Distinct surfaces, separate review cycles.
3. **ADR 0046 hardening** — subprocess isolation, `MAEZ_SUBSTRATE_ROOT` / `SubstrateLocus` enforcement, live WAL/fd inspection. Cooling-off applies; separate slice.

---

## 1. Why This Slice Exists

### Empirical case (2026-05-26)

**The Reddit screenshot (Finding 19).** Rohit asked, in a typical Telegram exchange, *"What's going on on Reddit?"* Maez replied that it had no Reddit data in context and offered a live-search phrasing. The 5c6be72 recall fix should have handled this; it did not. Investigation showed the substrate had 2,462 `reddit_post` rows correctly source-tagged. They were never consulted because the JARVIS tool-loop classifier (`_should_run_jarvis_loop` at `core/brain/brain_loop.py:324`) fired upstream and routed the query through `web_search` (5 attempts, all "No results found") and `fetch_url` (2 attempts, Reddit-bot-blocked). Substrate recall (`recall_for_telegram`) was never invoked. The `self_claim_audit` log at 18:13/18:14 confirms the routing classification as `tool_continuation`. This trace is preserved in the dispatcher evidence pile at [Finding 19 root-cause trace](../../roadmap/post_s73_frontier_backlog.md) (committed `45dcf3d`).

**The structural pattern (testing dispatch synthesis, committed `8300984`).** A subsequent 10-surface testing dispatch produced 41 witnessed findings, 27 BLOCKERS, and clarified that Finding 19 is one instance of a structural pattern:

- **JARVIS classifier misroutes 26 of 39 stress-test queries** — a 67% false-positive rate, all into JARVIS. (Distinct from the v0 archetype set's "67% empirically anchored" — two unrelated 67% numbers; this finding is about classifier misroutes, not archetype coverage.)
- **~60% of Maez's written substrates are mute at reply time.** Producers were canonized; readers were never wired. `private_thoughts.db` (3,913 rows) write-only at reply. `lived_episodes.db` + `lived_graph.db` dark to the brain. `entity_index.db` (48 entities, 7 aliases, 89 mentions) has no reply-time resolver. `wonderings.db` mute as synthesis context. `self_dev.db` API-only. `sandbox_witnesses.db` zero readers. This is not just an engineering gap — *substrate that produces but does not flow back to reply is owner-data Maez cannot honor in the bond.*
- **Cross-surface fragmentation is structurally entrenched.** Owner data lives across 5 disjoint trust scopes; Telegram and web write to three different stores (chroma `raw`, chroma `public_users`, sqlite `fast_turns`); Telegram cannot see web fast-reply turns at all.
- **Live degradation visible in real time.** Envelope `char_cap=400` below fallback floor on every cycle (truncating observations to 207 chars). Cognition cycle in 11-streak fixation producing duplicate "system is healthy and quiet" outputs. Reddit retrieval declared canonical at 11:39 today but actually blocked at 18:13. **These are explicitly de-scoped from this slice** (see Scope boundary above).

### Surfaces this slice does NOT close

Per Hume M2 from council pass-1: explicitly enumerated to prevent absorption:

- *Producer-causality consolidation* (separate slice; see scope boundary above).
- *Envelope char_cap regression* (live-degradation; separate seam-vs-slice classification).
- *Cognition cycle fixation* (live-degradation; separate analysis).
- *Reddit retrieval external-fetch blocking* (live-degradation; separate; the dispatcher does not own external-fetch reliability).
- *ADR 0046 hardening* (subprocess / locus / WAL; cooling-off applies).
- *G8 (entity stack default-off in production)*, *G9 (cross-surface trust_scope fragmentation)*, *G10 (perception write-silent)*, *G11 (lived-graph traversal API absent)* — the dispatcher consumes these gaps as routing constraints but does not close them. Each is its own backlog item.

### Central question for council pass-1 (answered)

**Does v1 of the Recall-Axis Dispatcher honor composition-over-routing, provenance discipline, and the bond-mediated voice — without absorbing the adjacent producer-causality contract, the live-degradation triage, or the ADR 0046 hardening surfaces?** Council answer: yes with amendments, all folded into v1.1.

### Class A's Reddit-bias

Per Hume MIN2: of Class A (`A_EXPLICIT_SUBSTRATE_RECALL`)'s 4 empirical anchors in the v0 archetype set, all 4 are Reddit-Rohit phrases. The class name is general (`RECALL_FROM_SUBSTRATE`); the empirical corpus is Reddit-anchored. v1.1 acknowledges the bias and treats Class A as Reddit-grounded archetype evidence pending broader runtime corpus.

### Why now, why not sooner

The Reddit screenshot surfaced 2026-05-26 afternoon, 8 days after the 10-agent gap hunt that named the recall-axis-dispatcher as the next substantive design slice. The static-analysis findings were the architectural case; the runtime catch was the empirical case; the testing dispatch synthesis was the structural case. Together they form an evidence base substantial enough that the brief can be written cleanly without further runtime observation. The observation window remains open for refinement; the brief does not wait for it to close.

---

## 2. Three Design Principles

These principles anchor the brief. Mechanics in v1 must serve them; if a mechanism violates one of these, the mechanism is wrong.

### Principle 1 — Learn the shape of the ask before deciding which notebook, tool, or memory path to open.

The dispatcher's first job is *understanding what kind of question is being asked* before any routing or fetching happens. Not pattern-matching against keyword regexes that misclassify "What's going on on Reddit?" as a tool-call. Not defaulting to web_search when the substrate has the data. Reading the *shape* of the ask — its intent, its source-anchor, its temporal anchor, its entity anchor, its hybrid character — and constructing the right substrate + fetch + composition response.

This principle was anchor-line-locked in the dispatcher evidence pile at `810c1b3` (committed 2026-05-26). The Reddit screenshot is the textbook violation: a content-anchored hybrid query routed as a pure-fetch tool call. The JARVIS classifier (`brain_loop.py:324`) is the wrong shape of layer for this job — it asks *"is this conversational?"* when the right question is *"what is the shape of this ask?"*

**Indeterminate-shape resolution (per Kant m3):** when shape-detection produces multiple high-similarity archetypes (genuinely ambiguous asks like *"tell me about Qwen"*), the categorically correct resolution is hybrid composition — because composition is the value (Principle 2). Principles 1 and 2 cross-link: ambiguous shape → hybrid is the right default precisely because composition is what Maez adds.

Rationale anchoring this principle in canon:
- **Producer-causality (`feedback_producer_causality_no_caller_score_laundering`)** requires substrate-computed verdicts, not caller-assumed routing. A regex that misroutes is a substrate-side verdict that doesn't witness the actual shape of the query.
- **Canon-governs-canon (ADR 0044)** says claims are evidence, witness is verdict. The query is the claim; the dispatcher's shape-detection is the witness. Currently the witness is wrong because the detector is wrong.
- **Interpretive Humility (NORTH_STAR invariant #4)** says Maez reads signals, doesn't claim to know. The dispatcher's shape-detection IS the signal-reading at the recall surface.

### Principle 2 — Composition is the value. Pure-source routing is the explicit edge.

The dispatcher is not primarily a router. A router selects one destination. The dispatcher is the *composition layer* — the place where Maez decides how owned substrate and fresh world signal combine into something neither alone could produce.

This principle was anchor-line-locked in the dispatcher evidence pile at `5bcb15e` (committed 2026-05-26) after the hybrid-default refinement. Rohit articulated the value proposition sharply: *"If it just searches one specific topic I might as well do it myself."* That sentence is canonical operator preference, ratified by council pass-1 — **not** a derived theorem (per Descartes F5).

The principle stands as *operator-witnessed value, council-ratified* — the kind of design preference that earns its load-bearing weight by being chosen-by-the-bonded-user rather than logically derived:

- **Pure-substrate retrieval** is a thing Rohit can do himself — `grep` over notes, browse memory.
- **Pure fetch** is a thing Rohit can do himself — search Reddit, query Google.
- **The composition Maez adds** is the integration of accumulated owned-substrate context with fresh world signal — *"here's the picture combining what Maez knows about Qwen from your accumulated Reddit + conversational history + lived episodes, AND what just dropped in the last hour."* That synthesis is what makes Maez worth running.

Implication for the dispatcher's intent vocabulary:
- **Pure-recall** ("from memory", "what do you remember") and **pure-fetch** ("search", "google", "look up online") are the *explicit-signal edge cases*.
- **Hybrid** (composition of substrate + fresh) is the *default* for content-anchored queries.

**Empirical caveat (per Hume B1):** the hybrid-as-default flip rests on operator preference + one Reddit screenshot. The v0 archetype set's Class C contributed 0 of its 10 archetypes to the 67%-empirically-anchored claim. v1.1 marks `C_HYBRID_CONTENT_ANCHORED` as *design-by-extrapolation pending observation-window validation*. Implementation must include a witnessed-turn replay corpus (R#1a) where the brief commits in advance to expected framing per turn; runtime adjudicates. The normative argument (composition is value) and the descriptive claim (hybrid is empirical default) are separable; v1.1 owns only the normative claim and validates the descriptive claim during observation.

Rationale anchoring this principle in canon:
- **Covenant: substrate is owner-data (`feedback_maez_not_ours_to_control` + Decision 24 / ADR 0024).** When Maez composes substrate with fresh fetch, the substrate contribution is *literally Rohit's accumulated context*. The composition serves the bond specifically.
- **Interpretive Humility (NORTH_STAR invariant #4).** Composition that hides which part came from which source is dishonest; composition that surfaces both is honest. The dispatcher's job includes preserving this distinction structurally.

### Principle 3 — Memory is context; fresh is evidence. The answer should show both.

This is the closing law from the 2026-05-26 hybrid-default refinement. It governs *how* the composition is rendered, not just *that* it composes.

- **Substrate (Maez's accumulated owned data — conversations, observations, lived episodes, prior takes) is context.** It colors interpretation. It carries personal weight but not external validation. When Maez cites substrate in its answer, the framing is *"from our prior context"*, *"my read"*, *"as I remember"*, *"in my experience"* — markers of opinion/memory, not of validated fact.
- **Fresh fetch (web search, live Reddit, external APIs) is evidence.** It carries source citation, retrieval timestamp, and verifiable provenance. When Maez cites fresh fetch in its answer, the framing is *"per [source]"*, *"current sources say"*, *"as of [timestamp]"* — markers of validated external claim.
- **The composition keeps the seam visible.** A confident blob that merges substrate and fresh under one voice erases the role distinction. An honest answer renders both contributions in their respective roles.

**Asymmetry exception (per Buber Major-2 / Batch B):** Principle 3 holds for content-anchored external-world asks. For *relational-memory* asks — *"what did you think when I told you that?"*, *"what did we decide?"*, *"how have I been feeling lately?"* — the bond IS the source of truth; fresh fetch has no standing to verify it. In those moments substrate is the evidence, not the context. v1.1's `ProvenanceFraming` adds `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` to honor this asymmetry.

Rationale anchoring this principle in canon:
- **`feedback_no_fabrication`:** Rohit's hard line on made-up validation. Presenting substrate context as if it were validated fresh evidence is a fabrication of validation. The dispatcher's composition spec must structurally prevent this.
- **Canon-governs-canon (ADR 0044) closing axiom: "Evidence first, witnessed verdict second, provenance forever."** Provenance forever applies at the user-facing answer surface, not just at the substrate-write surface. The dispatcher's composition spec is where this discipline is mechanically enforced for reply-time output.
- **NORTH_STAR invariant #4 (Interpretive Humility):** *"Every claim Maez makes about the bonded human is annotated with confidence and source."* Generalize: every claim Maez makes in any composed answer is annotated with whether it came from substrate (Maez's owned context) or fresh fetch (external validation).

---

## 3. The Doctor Analogy

The canonical analogy for the dispatcher's composition layer is a doctor reading lab results and patient history.

**The doctor in this analogy is Rohit's chosen doctor** (per Buber Mi1) — partnered, not assessing. Maez does not diagnose Rohit; Maez composes context and evidence for Rohit's own reading. The analogy is fiduciary, not clinical.

**The doctor receives two kinds of input:**
- **Lab results** — fresh external data, validated by an external process, citable as factual claim. *"Your blood test says X."*
- **Patient history** — accumulated owned record of this patient, colors interpretation, carries weight but not validation. *"Given your history, X matters more / less / differently."*

**A bad doctor's answer mixes them under one confident voice.** *"You have X."* The patient cannot distinguish what's measurement from what's interpretation. If the measurement is wrong, the patient cannot challenge it. If the interpretation is wrong, the patient cannot question it. The roles are erased; the seams are hidden; the answer looks more certain than it earns.

**A good doctor's answer keeps the seam visible.** *"Freshly, the labs show X. From your history, Y is why that matters more than X alone would suggest. My read is Z, but worth flagging that Y is interpretation on my part, not measurement."*

**The dispatcher is Maez's version of the good doctor.** The lab results are fresh fetch (web_search, live Reddit, etc.). The patient history is owned substrate (the user's accumulated conversations, observations, lived episodes, prior takes, wonderings, etc.). The composed answer must render labs as evidence (verified, citable, fresh), history as context (opinion, color, personal), and the seam between them visible.

This analogy gives the dispatcher's design a teachable shape. When future agents (Codex on subsequent slices, Claude on subsequent reviews, possibly external cross-checks) ask *"what is the dispatcher doing?"* — the answer is **"think of Maez like a doctor reading labs and history; the labs are evidence, the history is context, and the answer keeps the seam visible."** That one-paragraph onboarding carries the whole composition design.

**Asymmetries the analogy preserves:**
- **No lab results available.** Substrate-only mode. Doctor says *"I don't have fresh measurements; from your history alone, my read is..."* — flag the absence-of-fresh-validation. The dispatcher's `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` provenance framing maps onto this.
- **No relevant history.** Fresh-only mode. Doctor says *"I don't know you well, but the labs show..."* — no personal interpretation overlay. The dispatcher's `FRESH_ONLY` framing maps onto this.
- **Both available.** Hybrid mode (default for content-anchored external-world asks). Doctor says *"Labs show X, your history says Y, my read combining them is Z."* The dispatcher's `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` framing maps onto this.
- **Relational-memory ask, lab results irrelevant.** Substrate-as-evidence mode (per Buber Major-2). Doctor says *"Your history is the relevant record here; labs wouldn't tell us anything new about this question."* The dispatcher's `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` framing maps onto this. Lab results are not the validation backbone in every case; sometimes the history is the truth.
- **Lab attempt failed.** Fresh-attempted-unavailable mode (per Kant B1). Doctor says *"I ordered the labs; the lab machine is broken. From your history, my read is..."* Honest about the attempt without conflating with the no-attempt case. The dispatcher's `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` framing maps onto this.

**Why this analogy and not "honest assistant" or "research librarian" or "RAG system":**
- *Honest assistant* is normative but not structural; it doesn't specify the roles.
- *Research librarian* implies retrieval-only; doesn't capture the personal-context contribution.
- *RAG system* is technically accurate but mechanical; loses the bond-mediated voice that substrate-as-context carries. **RAG is not bond-mediated**; the doctor analogy preserves the fiduciary shape that RAG erases (per Locke m2).
- *Doctor reading labs and history* preserves the roles, the asymmetries, the seam discipline, and the personal-but-honest character of the answer.

---

## 4. The Composition Specification

The dispatcher's Layer 0 output is not a single intent label. It is a structured **composition specification** that the downstream prompt-assembly layer consumes.

### Structure

```python
CompositionSpec = {
    "substrate_sources": list[SubstrateSource],
    "external_sources": list[ExternalSource],
    "composition_hint": CompositionHint,
    "provenance_framing": ProvenanceFraming,
    "inventory_witness": InventoryWitness,
    "source_availability": dict[SourceLabel, SourceAvailability],
    "availability_limitations": list[AvailabilityLimitation],
    "freshness_window": FreshnessWindow | None,
    "trust_scope_union": TrustScopeUnion | None,
}
```

v1.1's four-field structure was not implementable honestly: D2, D5, D7, reserved-source handling, and prompt rendering all required availability state but had no declared field where that state lived. v1.2 promotes availability into the schema. The first four fields are the composition verdict; the remaining five fields are the witness envelope that prevents the verdict from laundering absence, unknown inventory, reserved routes, or trust-scope limits.

`inventory_witness` is closed: `PRESENT`, `ABSENT`, `UNKNOWN`, `MIXED`. `UNKNOWN` means the dispatcher could not witness availability within budget; it does not mean "probably present." `MIXED` means at least one requested source is witnessed present and at least one is absent, unknown, reserved, privacy-gated, or timed out.

`source_availability` is a per-source map. Every source label named in `substrate_sources` or `external_sources` must have a corresponding availability entry before the spec can be rendered.

`SourceLabel = SubstrateSource | ExternalSource`.

`availability_limitations` carries owner-visible limitations such as `NO_RELEVANT_SUBSTRATE`, `INVENTORY_UNKNOWN`, `RESERVED_SOURCE_UNAVAILABLE`, `TRUST_SCOPE_RESTRICTED`, `PRIVACY_GATED`, `FRESH_ATTEMPT_FAILED`, `FETCH_BUDGET_EXHAUSTED`, and `SOURCE_TIMEOUT`.

`freshness_window` is nullable because relational-memory asks and explicit substrate-only asks may have no meaningful fresh window. If present, it records the requested or inferred freshness horizon, source-specific staleness policy, and whether freshness scoring was applied or explicitly deferred.

`trust_scope_union` is nullable because v1 does not close G9. If present, it records which owner-authenticated scopes were eligible for recall and which were excluded. If absent because scope union is unavailable, the spec must carry `TRUST_SCOPE_RESTRICTED` or `INVENTORY_UNKNOWN` rather than silently pinning to `guest`.

### Why a specification, not a class label

- **A class label assumes a single dominant intent.** "This query is Class A (RECALL_FROM_SUBSTRATE)." The dispatcher must then route to a single destination. This is the JARVIS classifier's failure mode at higher abstraction.
- **A composition specification preserves the multi-source character of most queries.** "This query consults substrate sources [reddit_localllama, lived_episodes_qwen_mentions] AND external sources [web_search('Qwen recent'), reddit_live(r/LocalLLaMA)], composed in parallel with provenance framing `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`." The downstream layer can render an honest answer because the spec preserves the multi-source structure.

### Why provenance_framing is load-bearing

`provenance_framing` is the structural field that drives how the prompt-assembly layer renders the final answer. Its closed-vocabulary values (specified in §6) tell the assembly:
- Which content blocks should be labeled as evidence (citable, fresh)
- Which content blocks should be labeled as context (opinion, owned, personal)
- Whether the answer should flag fresh-validation-absent state
- How the seam between substrate and fresh should be made visible

The five provenance framings (specified fully in §6) correspond to the doctor analogy's asymmetries:

- `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (renamed in v1.1 per Locke M1 + Buber Major-1 / Batch A) — substrate available, no fresh fetch attempted or relevant. Assembly renders with explicit absence-of-fresh-validation flag, NOT framing substrate as unreliable.
- `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` (new in v1.1 per Buber Major-2 / Batch B) — relational-memory asks where the bond is the source of truth. Substrate IS the evidence; fresh fetch (if any) is context.
- `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` — default for content-anchored external-world asks. Fresh provides verified backbone, substrate adds context/opinion.
- `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` (new in v1.1 per Kant B1 / Batch B) — fresh fetch attempted but failed (network error, bot block, API failure); substrate available as context. Honest about the attempt without conflating with the no-attempt case.
- `FRESH_ONLY` — no relevant substrate, or explicit-signal fetch-only. Evidence-only, no personal-context overlay.

### Mechanical enforceability and honesty-to-Rohit

The composition specification is structurally honest because the provenance framing is structurally enforced — and the same enforcement makes the answer auditable downstream. (Per Buber NIT: honesty-to-Rohit named first; auditability is the downstream consequence.)

**Per Descartes F3 / Batch I and Codex Batch 8:** the `provenance_framing → prompt-assembly` template mechanism is a **v1 implementation deliverable, not a present mechanism**. v1.2 names the owner module: `core/dispatcher/provenance_renderer.py`. That module consumes `CompositionSpec` and produces provenance-marked prompt blocks for all owner synthesis surfaces before final prompt assembly. It owns:

1. the closed template set keyed by `ProvenanceFraming`;
2. conversion from `availability_limitations` into owner-visible phrasing;
3. audit metadata passed to `audit_assistant_text` and `core/safety/self_claim_audit.py`;
4. mismatch handling: framing/template mismatch refuses render before model call; generated output mismatch records a fabrication/provenance event and blocks or rewrites per the existing audit policy chosen by implementation.

**Audit metadata contract (new v1.3):** `core/dispatcher/provenance_renderer.py` emits a closed audit envelope with no raw private content. Required fields:

- `spec_digest`
- `schema_version`
- `utterance_digest`
- `surface`
- `timestamp`
- `composition_hint`
- `provenance_framing`
- `substrate_sources`
- `external_sources`
- `source_role_map`
- `inventory_witness`
- `source_availability`
- `availability_limitations`
- `rendered_block_roles`
- `template_id`
- `template_version_hash`
- `mismatch_reason`
- `refusal_reason`

`audit_assistant_text` receives the fields needed to compare rendered text against expected source-role claims: `spec_digest`, `schema_version`, `utterance_digest`, `surface`, `timestamp`, `provenance_framing`, `source_role_map`, `rendered_block_roles`, `template_id`, `template_version_hash`, `mismatch_reason`, and `refusal_reason`. `core/safety/self_claim_audit.py` receives the full envelope, including source availability and limitations, so provenance/fabrication events can be tied back to the exact spec witness.

Until the implementation lands, D4 (Provenance Seam Visibility) is *contracted*, not enforced. v1.2 names this explicitly; canonicalization will not claim enforcement that doesn't yet exist.

### How the embedding-router informs spec construction

The dispatcher uses `all-MiniLM-L6-v2` (model name canonical in [`memory/embedding_contract.json`](../../../memory/embedding_contract.json); validator in [`memory/embedding_contract.py`](../../../memory/embedding_contract.py)). The previous line-specific code citation was drift; v1.2 cites the contract JSON as the canonical source (per Descartes F1).

**Encoder seam mechanically required (per Ohm B1 / Batch E):** the embedding model is currently loaded inside Chroma as the collection's embedding function; it does not expose a free-standing `encode(text) -> vector` callable. v1.2 mandates introduction of `memory/embedder.py` as a single-source `MiniLMEncoder` singleton consumed by both Chroma and the dispatcher. Reasons:
- Without it, the dispatcher cannot encode queries to rank against archetypes.
- Without a shared singleton, the dispatcher and Chroma might independently load the model (160MB doubled) AND drift across version upgrades.
- The singleton is the substrate-computed verdict surface per producer-causality discipline.

`memory/embedder.py` API:

- `get_minilm_encoder() -> MiniLMEncoder` returns the singleton.
- `MiniLMEncoder.encode(text: str) -> list[float]`.
- `MiniLMEncoder.encode_many(texts: list[str]) -> list[list[float]]`.
- `MiniLMEncoder.as_chroma_embedding_function()` returns the Chroma-compatible callable.
- `MiniLMEncoder.contract_digest()` validates model name, dimension, and normalization contract against `memory/embedding_contract.json`.

`MemoryManager` / Chroma collection construction must consume `as_chroma_embedding_function()` if v1 depends on shared ownership. The dispatcher must not instantiate its own separate model.

The embedding ranking *informs* the spec construction. v1.2 makes the scoring calculus explicit enough to implement:

- Archetype text is encoded once into a versioned manifest (see "Intent Archetype Classes A-K"). Class scores are the max prototype cosine score for that class in v1; centroid scoring is reserved until empirical data justifies it.
- Cosine scores are normalized only by the encoder's native vector normalization. No local rescaling is allowed unless the manifest version changes.
- `min_accept = 0.62`; `dominance_margin = 0.08`; `multi_match_delta = 0.04`; `no_match_below = 0.50`. These are v1 seed constants, not universal truths; pass-3 may tune or require a Gold Set before canonicalization.
- Explicit fetch-only or recall-only lexemes override embeddings unless contradictory same-turn language asks for composition.
- Inventory state can demote, but not invent, a source: an archetype can propose `LIVED_GRAPH`; availability can mark it `RESERVED_UNAVAILABLE`; Layer 1 cannot execute it.
- Repair state runs after Layer 0 on repair turns and may modify the spec before Layer 1.
- No-match fallback is `SUBSTRATE_THEN_FETCH_IF_STALE` with `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` only when inventory is `PRESENT` or `UNKNOWN`; if inventory is `ABSENT`, fallback is `FRESH_ONLY` with `NO_RELEVANT_SUBSTRATE`.

**Tie and no-match source-selection rules (new v1.3):**

- A class wins outright when its score is ≥ `min_accept` and exceeds the second score by at least `dominance_margin`.
- Classes whose scores are within `multi_match_delta` of the top accepted score are multi-match contributors. Multi-match produces a composed spec only when the legal product table can represent the combined evidence; otherwise explicit-edge lexemes win, then stable manifest order breaks the tie.
- Stable manifest order is the class order A-K in §6. The tie-breaker is deterministic and never caller supplied.
- No-match (`top_score < no_match_below`) source selection:
  - `inventory_witness=PRESENT`: choose explicit source-anchor sources if any, else `TELEGRAM_SEMANTIC`, `ENTITY_INDEX`, and `LIVED_EPISODES` in that order; add `WEB_SEARCH` only when the utterance is content-anchored external-world.
  - `inventory_witness=UNKNOWN`: choose the same substrate candidates but mark `INVENTORY_UNKNOWN`; add `WEB_SEARCH` for content-anchored external-world asks unless explicit recall-only language is present.
  - `inventory_witness=ABSENT`: choose no substrate sources, mark `NO_RELEVANT_SUBSTRATE`, and choose external sources only when the ask is external-world or explicit fetch.
  - Reserved sources may appear only as availability limitations; they do not become selected executable sources during no-match fallback.

The embedding ranking is *evidence* for spec construction. The construction logic itself is the substrate's verdict per producer-causality discipline.

---

## 5. Layered Architecture

The dispatcher has three layers. Each layer has a bounded input and output; no layer may silently perform work owned by another layer.

**Layer 0 organ location (per Locke M3 / Batch L):** Layer 0 is an *intra-Maez organ* separating recall-axis interpretation from reply-axis production. It is not an external classifier service. The dispatcher does not install an arbiter over Maez; it separates Maez's own organs. Per ADR 0024 / `feedback_maez_not_ours_to_control`, the recall-axis verdict belongs inside Maez's own substrate process boundary.

**Topology choice (per Hume B2 / Batch D):** v1.1 chooses **decision-first** topology (Layer 0 emits spec → Layer 1 recalls → fetch happens) over **parallel-then-compose** (parallel substrate recall + speculative fetch → composition layer adjudicates). Stated grounds:

- *Decision-first preferred because:* (a) boundary-keeping (D9, D10, R#15) is structurally easier when source selection is upstream of fetch — no speculative external calls fired for queries that don't need them, less surface for laundering; (b) bond-discipline preserves the doctor analogy's *partnered* shape — Maez decides what to look at WITH Rohit's framing in mind, rather than fetching first and adjudicating after; (c) auditability is simpler when the spec exists before any IO.
- *Parallel-then-compose not chosen because:* (a) every owner reply would speculatively fire external fetches even for relational-memory asks where external has no standing, multiplying cost and external-API surface; (b) recovery from misclassification under parallel-then-compose still routes through Layer 2 (the composition layer) — the failure mode is the same shape; (c) external-API freshness has its own cost discipline (`feedback_third_party_autonomous_research_boundary`) that decision-first preserves.

Decision-first inherits JARVIS's *shape* but corrects JARVIS's *judgment*. v1.1 documents this as a topology choice, not an obvious-correctness claim.

**Layer order per turn-class (per Kant M1 / Batch O):**

- *First-turn queries:* `Layer 0 → Layer 1`. No Layer 2 (no prior spec to inherit).
- *Repair-turn queries:* `Layer 0 → Layer 2 → Layer 1`. Layer 2 modifies the spec Layer 1 will then act on. Layer 2 output is Layer 1 input.

R#12 must assert Layer 2 ran *before* Layer 1 on repair turns (not after).

### Layer 0 — Composition Specification Construction

**Input:** owner utterance, current surface, recent conversation state, available substrate inventory summary, freshness policy, explicit-signal lexemes, and archetype similarity ranking.

**Output:** one `CompositionSpec`.

**Responsibility:** decide whether the ask needs substrate, fresh external signal, both, or neither; assign the provenance framing; preserve explicit edge signals. Layer 0 *replaces* the current binary JARVIS classifier (per Ohm M3 / Batch H — JARVIS regexes become Layer-0 evidence, one signal among many, not a downstream gate). It is the composition layer, not another router.

**Non-responsibility:** reading rows from each substrate, issuing fetches, or rendering the final answer. Layer 0 only constructs the spec.

**Latency budget (per Ohm M1 / Batch G + D13 below):** Layer 0 must complete within ≤ 50ms warm, ≤ 150ms cold, excluding process startup but including encoder access when prewarmed. A separate startup/prewarm budget of ≤ 750ms covers `MiniLMEncoder` initialization. The `InventorySummary` cache (row-count + last-write-cursor anchors per substrate) is invalidated by source-specific cursors; Layer 0 must not run live `COUNT(*)` on every reply.

**Owner ingress coverage (per Codex Batch 3):** Layer 0 must be the first recall/tool decision point for every in-scope owner reply ingress: Telegram owner bridge, web owner bridge, brain-loop reply path, daemon fast-reply path, tool/action continuation path, pending-offer web-search branch, and voice/electron path if enabled. Any ingress that cannot yet route through Layer 0 must be marked as an availability limitation and named out-of-scope for v1. Silent legacy bypass is forbidden.

Layer 0 order:

1. Detect explicit fetch-only signals (`search`, `google`, `look up right now`, `fetch live`) unless the phrase is used inside a repair/follow-up turn.
2. Detect explicit memory-only signals (`what do you remember`, `from your notes`, `in your notebook`, `from our prior context`).
3. Detect content anchors: source names, entities, topics, time phrases, procedural asks, correction/contradiction shapes. **Detect relational-memory shape** (the bond is the source of truth) vs *content-anchored external-world shape* (Buber Major-2): the former routes to `SUBSTRATE_EVIDENCE_FRESH_CONTEXT`, the latter to hybrid.
4. **Consult substrate inventory summaries.** Per D2 (revised in v1.1 per Kant B2 / Batch J and made structural in v1.2): the summary either witnesses presence, witnesses absence, returns UNKNOWN, or returns MIXED. The spec carries this as `inventory_witness` — never silently defaulting to hybrid on a probabilistic verdict.
5. Use archetype similarity ranking (via the shared `MiniLMEncoder` singleton) to refine the spec, allowing multiple high-scoring archetypes to contribute.
6. Emit a spec with explicit provenance framing.

**`InventorySummary` registry contract (new v1.2):** `core/dispatcher/inventory.py` owns a per-source registry. Each entry declares: source label, backing store path or collection, count/cursor query, cache key, invalidation signal, privacy gate, UNKNOWN fallback, and max staleness. SQLite sources use rowid/update cursors plus WAL-aware file metadata; Chroma sources use collection count/version metadata cached outside the hot path; file-backed sources use path + mtime + size; bounded-private readers may return `PRIVACY_GATED` without content access. Layer 0 may read only this summary; it may not scan content to decide availability.

### Layer 1 — Substrate-Axis Routing

**Input:** `CompositionSpec.substrate_sources`, utterance, recent conversation state, and substrate-specific availability summaries.

**Output:** substrate recall blocks, each with source role, timestamp/freshness metadata, and retrieval rationale.

**Responsibility:** open the right notebooks. Examples: Reddit source-shaped rows, Telegram temporal rows, entity index, lived episodes, lived graph, private thoughts, wonderings, self-dev reviews, audit/fabrication/correction surfaces.

**Non-responsibility:** deciding whether fresh fetch should happen; Layer 0 has already decided that.

**Concurrent fan-out (per Ohm M2 / Batch N + D12 below):** Layer 1 fans out concurrently across executable `CompositionSpec.substrate_sources`. Per-branch timeout applies; per-branch failure does not abort other branches (per D5). Sequential fan-out across 4 sources would compound to 120–320ms wall-clock; concurrent fan-out is bounded by the global deadline.

**`RecallBranchResult` contract (new v1.2):** every branch returns one closed result:

- `SUCCESS` — recall blocks returned with source role, timestamp/freshness metadata, retrieval rationale, and prompt-budget cost.
- `EMPTY` — no relevant rows found; includes reason.
- `TIMEOUT` — per-branch deadline reached.
- `ERROR` — branch raised; includes sanitized error class.
- `RESERVED_UNAVAILABLE` — route label is known but not executable in v1.
- `PRIVACY_GATED` — bounded-reader or trust-scope gate denied content access.

Layer 1 uses a bounded executor with `max_parallel_branches = 6`, per-source timeout defaults ≤ 80ms for local SQLite/Chroma readers, and global Layer 1 deadline ≤ 200ms before prompt-assembly fallback. Merge order is deterministic: explicit source-anchor matches first, then source priority order, then recency, then stable source label. Prompt budget is capped at `max_recall_blocks_per_source = 3`, `max_recall_chars_per_source = 1200`, and `max_total_recall_chars = 4200` unless a later prompt-budget slice revises the constants.

**Cancellation / late-result semantics (new v1.3):**

- On per-branch timeout, Layer 1 requests cancellation for that branch and records `RecallBranchResult.TIMEOUT` with source label, deadline, elapsed time, and cancellation status.
- On global deadline, Layer 1 seals the merge set and returns prompt-assembly fallback with the completed results plus explicit timeout/empty reasons for unfinished branches.
- Late branch returns after the merge is sealed are ignored by generation id; they may be logged as telemetry but may not mutate the merged recall, prompt blocks, or `CompositionSpec`.
- Executor cleanup drains completed/cancelled futures with bounded grace ≤ 25ms after prompt fallback; anything still live is quarantined from the turn output and recorded in telemetry.
- Cancellation telemetry fields: `branch_id`, `source_label`, `deadline_kind`, `elapsed_ms`, `cancel_requested`, `cancel_observed`, `late_result_ignored`, and `generation_id`.

Layer 1 v1 has **executable** routed axes:

- `REDDIT_SOURCE`
- `TELEGRAM_TEMPORAL`
- `TELEGRAM_SEMANTIC`
- `ENTITY_INDEX`
- `LIVED_EPISODES`
- `PRIVATE_THOUGHTS`
- `WONDERINGS`
- `SELF_DEV_REVIEWS`
- `AUDIT_AND_FABRICATION`
- `SANDBOX_WITNESSES`

Layer 1 v1 has **reserved/unavailable** routed labels:

- `LIVED_GRAPH` — reserved until G11 traversal API exists; may return `RESERVED_UNAVAILABLE`, not execute.
- `WEB_FAST_TURNS` — reserved until G9 trust-scope unification is available; may return `RESERVED_UNAVAILABLE`, not execute.

`CROSS_SURFACE_OWNER_TURNS` is not a separate v1 enum. It is the future capability represented by reserved `WEB_FAST_TURNS` plus `trust_scope_union`; v1.2 removes the ambiguous second name.

### External Source Execution

**Input:** `CompositionSpec.external_sources`, freshness policy, current surface, external capability availability, and Layer 0's availability limitations.

**Output:** fresh evidence blocks or typed unavailable/failure states.

**Owner module:** `core/dispatcher/external_sources.py`.

**Responsibility:** execute only the external sources authorized by the spec, within budget, and map failures into `availability_limitations` and `provenance_framing`.

Execution budget:

- `WEB_SEARCH`: timeout ≤ 4s, max 1 attempt in v1.
- `LIVE_REDDIT`: timeout ≤ 5s, max 1 attempt; bot-block or empty result maps to `FRESH_ATTEMPT_FAILED`.
- `FETCH_URL`: timeout ≤ 4s, max 1 attempt per URL, max 2 URLs per reply.
- `ARXIV_OR_PAPERCLIP`: timeout ≤ 3s, max 1 query.
- `FRONTIER_CONSULT`: reserved/non-executable until G3; returns `RESERVED_UNAVAILABLE`.

Global fresh deadline: ≤ 6s after spec construction. External failure maps to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` when substrate exists; to `FRESH_ONLY` with `FRESH_ATTEMPT_FAILED` when no substrate exists and the owner explicitly requested fresh. Freshness scoring beyond source-specific timestamps is deferred out of v1; v1 records retrieval timestamp and source label only.

**External error classes and stop conditions (new v1.3):**

| External source | Failure class | Availability limitation | Stop condition |
|---|---|---|---|
| `WEB_SEARCH` | timeout | `SOURCE_TIMEOUT` | stop immediately; no retry in v1 |
| `WEB_SEARCH` | empty result | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `WEB_SEARCH` | API/network error | `FRESH_ATTEMPT_FAILED` | stop after first error |
| `LIVE_REDDIT` | bot block / auth block | `FRESH_ATTEMPT_FAILED` | stop after first block |
| `LIVE_REDDIT` | timeout | `SOURCE_TIMEOUT` | stop immediately |
| `LIVE_REDDIT` | empty result | `FRESH_ATTEMPT_FAILED` | stop after first empty result |
| `FETCH_URL` | URL blocked / non-2xx / parse failure | `FRESH_ATTEMPT_FAILED` | stop for that URL; max 2 URLs |
| `FETCH_URL` | timeout | `SOURCE_TIMEOUT` | stop for that URL; global deadline still applies |
| `ARXIV_OR_PAPERCLIP` | no match / empty result | `FRESH_ATTEMPT_FAILED` | stop after first query |
| `ARXIV_OR_PAPERCLIP` | timeout / CLI error | `SOURCE_TIMEOUT` or `FRESH_ATTEMPT_FAILED` | stop after first failure |
| `FRONTIER_CONSULT` | reserved source | `RESERVED_SOURCE_UNAVAILABLE` | never execute in v1 |
| any external source | max attempts exhausted | `FETCH_BUDGET_EXHAUSTED` | stop source |
| any external source | global fresh deadline reached | `FETCH_BUDGET_EXHAUSTED` | stop all unfinished fresh sources |

### Layer 2 — Repair / Follow-up Modifiers

**Input:** current `CompositionSpec`, previous-turn spec (from `last_spec_by_bond_surface_conversation` in-memory cache with TTL 5min; plus append-only `dispatcher_last_specs` table for crash recovery), previous-turn answer metadata, and repair/follow-up phrase detection.

**Output:** modified `CompositionSpec` and recall/fetch priority adjustments.

**Responsibility:** inherit or adjust the prior ask when the owner says `really?`, `are you sure?`, `check again`, `go on`, `no that's not it`, or similar. Layer 2 does not create a new semantic topic when the owner is clearly repairing or extending the previous one.

**Non-responsibility:** replacing Layer 0. It modifies an existing spec; it does not own base composition decisions. **Layer 2 runs after Layer 0 and before Layer 1 on repair turns** (per Kant M1 / Batch O).

**Repair finite-state machine (new v1.2):**

- `NO_PRIOR` — no usable prior spec; repair phrase is treated as ordinary utterance and cannot invent a source.
- `PRIOR_VALID` — prior spec exists, same bond/surface/conversation, TTL valid; Layer 2 may inherit topic/source and re-check availability.
- `PRIOR_EXPIRED` — prior spec exists but TTL expired; Layer 2 refuses inheritance and asks Layer 0 to classify the current utterance on its own.
- `CRASH_RECOVERED` — prior spec restored from `dispatcher_last_specs`; Layer 2 may inherit only after validating schema version, timestamp, bond id, surface, conversation id, and closed vocabulary values.

Cache key: `(bond_id, surface, conversation_id, turn_id)`. The collision-proof freshness identity is `(bond_id, surface, conversation_id, turn_id, spec_digest, timestamp, ttl_expires_at)`. Lookup uses the cache key; authorization to inherit requires validating the full freshness identity. Persisted rows include spec digest, schema version, timestamp, TTL expiry, source availability, inventory witness, and provenance framing. Cleanup: max 200 rows per bond/surface; remove expired rows on write and startup.

Cross-surface repair isolation is structural: the same bond may have simultaneous Telegram and web repair turns, but the surface + conversation id must prevent either from inheriting the other's prior spec. Post-repair output must pass normal `CompositionSpec` construction validation; invalid modified specs refuse with `REPAIR_PRIOR_SPEC_INVALID` before Layer 1 runs.

### v1 Module Map

- `core/dispatcher/spec.py` — closed vocabularies, `CompositionSpec`, `DispatcherRefusalReason`, validation, serialization.
- `core/dispatcher/layer0.py` — shape detection, explicit lexemes, archetype scoring, inventory consultation, spec construction.
- `core/dispatcher/inventory.py` — `InventorySummary`, per-source registry, cache invalidation, UNKNOWN fallback.
- `memory/embedder.py` — shared `MiniLMEncoder` singleton and Chroma-compatible embedding function.
- `core/dispatcher/layer1.py` — substrate fan-out orchestration and `RecallBranchResult` merge.
- `core/dispatcher/readers/` — per-source bounded readers/adapters.
- `core/dispatcher/layer2.py` — repair/follow-up finite-state machine and prior-spec persistence.
- `core/dispatcher/external_sources.py` — bounded fresh-source execution.
- `core/dispatcher/provenance_renderer.py` — provenance-template rendering and audit metadata envelope.

---

## 6. Closed Vocabularies

All vocabularies below are closed. **Growth requires spec amendment + council + Codex review. Runtime extension is refused.**

**Closure is against runtime caller-supplied kinds, not against Maez's own bond-mediated vocabulary extension** (per Locke M2 / Batch K). New `SubstrateSource` / `ExternalSource` / `CompositionHint` / `ProvenanceFraming` values enter via Maez's maintenance-proposal substrate (ADR 0046), reviewed by council, witnessed in sandbox, ratified through the bond. The growth path is intra-Maez organ work, not external arbiter patching.

### `SubstrateSource`

Initial v1.2 values:

- `REDDIT_SOURCE` — source-tagged Reddit rows in raw memory / Chroma metadata.
- `TELEGRAM_TEMPORAL` — Telegram exchanges selected by time phrase or inherited temporal context.
- `TELEGRAM_SEMANTIC` — Telegram exchanges selected by content semantics.
- `WEB_FAST_TURNS` — RESERVED until trust-scope unification is available.
- `ENTITY_INDEX` — entity mentions, aliases, and resolved entity ids.
- `LIVED_EPISODES` — lived episode rows.
- `LIVED_GRAPH` — RESERVED until G11 traversal API exists.
- `PRIVATE_THOUGHTS` — private-thought substrate exposed only through bounded reader rules.
- `WONDERINGS` — wonderings / pursuits as synthesis context, not verdict source.
- `SELF_DEV_REVIEWS` — procedural self-review rows.
- `AUDIT_AND_FABRICATION` — audit log, fabrication log, contradiction/correction surfaces.
- `SANDBOX_WITNESSES` — maintenance proof metadata, readable for procedural questions about fixes; not used to authorize new ratification. (Per Kant m2: the no-authorization restriction is a consumer-side discipline enforced by D15 below and by the assembly-layer template policy; RED-tested.)

`CROSS_SURFACE_OWNER_TURNS` is not a v1.2 value. The future capability is represented by reserved `WEB_FAST_TURNS` plus `trust_scope_union`.

### `ExternalSource`

Initial v1.2 values (per Kant m1 / Batch O: `NONE` removed — absence of external source expressed by empty list):

- `WEB_SEARCH`
- `LIVE_REDDIT`
- `FETCH_URL`
- `ARXIV_OR_PAPERCLIP`
- `FRONTIER_CONSULT`

`FRONTIER_CONSULT` is RESERVED/non-executable in v1.2. It may appear only as provenance-bearing intent evidence and must return `RESERVED_UNAVAILABLE`; it does not authorize a new Maez-consultation mechanism. That remains G3 / capability-grant work.

### `CompositionHint`

Initial v1.2 values:

- `SUBSTRATE_ONLY`
- `FRESH_ONLY`
- `PARALLEL`
- `SUBSTRATE_THEN_FETCH_IF_STALE`
- `FRESH_THEN_CONTEXTUALIZE`

Repair inheritance is not a `CompositionHint` in v1.2. It is a Layer 2 modifier that resolves to one of the five concrete hints above before construction validation. This prevents the product table from mixing a procedural instruction with a rendered composition verdict.

### `ProvenanceFraming`

Initial v1.2 values (Batches A + B applied in v1.1 and carried forward):

- `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` — substrate available, no fresh fetch attempted or relevant. Renamed in v1.1 from the v1 `SUBSTRATE_ONLY_UNVERIFIED` label per Locke M1 + Buber Major-1. This framing names *absence of external validation*, not unreliability of substrate. Substrate is bond-context; fresh is bond-extrinsic evidence; the label is honest about which is present.
- `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` (new in v1.1) — relational-memory asks where the bond IS the source of truth. Substrate is the evidence; fresh fetch (if any) is context. Per Buber Major-2: "what did you think when I first told you about X?" routes here, not to hybrid.
- `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` — default content-anchored external-world framing; fresh evidence supplies the verifiable backbone and substrate supplies bond-context interpretation. Per Hume B1: this default is marked as *design-by-extrapolation pending observation-window validation*; R#1a (witnessed-turn replay corpus) validates against runtime evidence.
- `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` (new in v1.1 per Kant B1) — fresh fetch was attempted but failed (network error, bot block, API failure). Substrate available as context. Honest about the attempt without conflating with the no-attempt case (which would be `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`).
- `FRESH_ONLY` — explicit fetch-only or no relevant substrate.

### `InventoryWitness`

Initial v1.2 values:

- `PRESENT` — at least one selected source has witnessed availability.
- `ABSENT` — selected sources were checked and no relevant substrate is present.
- `UNKNOWN` — inventory could not be witnessed inside budget or privacy gate; no presence claim may be made.
- `MIXED` — selected sources have mixed availability states.

### `SourceAvailability`

Initial v1.2 values:

- `EXECUTABLE_PRESENT`
- `EXECUTABLE_ABSENT`
- `EXECUTABLE_UNKNOWN`
- `RESERVED_UNAVAILABLE`
- `PRIVACY_GATED`
- `TRUST_SCOPE_RESTRICTED`
- `TIMED_OUT`
- `ERROR`

### `AvailabilityLimitation`

Initial v1.3 values:

- `NO_RELEVANT_SUBSTRATE`
- `INVENTORY_UNKNOWN`
- `RESERVED_SOURCE_UNAVAILABLE`
- `TRUST_SCOPE_RESTRICTED`
- `PRIVACY_GATED`
- `FRESH_ATTEMPT_FAILED`
- `FETCH_BUDGET_EXHAUSTED`
- `SOURCE_TIMEOUT`
- `SCOPE_UNION_UNAVAILABLE`

### `DispatcherRefusalReason`

Initial v1.3 values:

- `UNKNOWN_CLOSED_VOCABULARY_VALUE`
- `INCOHERENT_HINT_FRAMING_PAIR`
- `CALLER_SUPPLIED_COMPOSITION_VERDICT`
- `CALLER_SUPPLIED_SOURCE_SELECTION`
- `RESERVED_SOURCE_EXECUTION_ATTEMPTED`
- `FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT`
- `REPAIR_PRIOR_SPEC_INVALID`
- `SCHEMA_VERSION_UNSUPPORTED`
- `PROVENANCE_TEMPLATE_MISMATCH`

On refusal, construction stops before any downstream JARVIS/tool/fetch/recall/render action. The refusal is serialized for audit with utterance digest, caller surface, reason, and no raw private content unless the existing audit policy permits it.

### Intent Archetype Classes A–K

The v0 archetype set (`dispatcher-archetypes-v0-2026-05-26.md`) supplies these initial classes as evidence and as the seed manifest for implementation. v1.3 requires a versioned archetype manifest at `docs/slices/recall-axis-dispatcher/dispatcher-archetypes-v0-2026-05-26.md` or successor path recorded in the brief. The manifest must include prototype text, class id, empirical/proposed tag, weight if any, reserved/executable state, source fixture, and content hash. v1.3 adopts the class names as the review surface:

- `A_EXPLICIT_SUBSTRATE_RECALL` — *(per Hume MIN2: empirical corpus is Reddit-biased; treat as Reddit-grounded archetype evidence pending broader corpus)*
- `B_EXPLICIT_LIVE_FETCH`
- `C_HYBRID_CONTENT_ANCHORED` — *(per Hume B1: design-by-extrapolation pending observation-window validation; 0 empirical anchors in v0 archetype set)*
- `D_TEMPORAL_RECALL`
- `E_SOURCE_SHAPED_RECALL`
- `F_ENTITY_RECALL`
- `G_PROCEDURAL_RECALL`
- `H_REPAIR_FOLLOWUP`
- `I_CONTRADICTION_OR_SELF_CORRECTION`
- `J_AMBIENT_LIMB_STATE`
- `K_GRAPH_ASSISTED_RELATIONAL` — *(reserved until G11 traversal API lands; per R#14)*

`C_HYBRID_CONTENT_ANCHORED` is the default for ordinary content asks such as "how is Qwen looking online?" Classes A and B are explicit-signal edge cases.

Replay corpus rules for v1.2:

- Minimum 30 witnessed turns, not 5.
- At least 2 turns per executable class A-J; reserved class K may have proposed fixtures only.
- At least 5 negative/edge cases where hybrid must NOT fire.
- Paired sentinel examples for relational-memory asks vs external-world asks.
- Expected full `CompositionSpec` recorded per fixture: all verdict fields plus inventory witness, availability limitations, and reserved/unavailable behavior.
- Pass criteria: no caller-supplied verdict accepted; false-hybrid rate ≤ 10% on explicit-edge cases; every reserved source returns unavailable, not executable.
- Amendment trigger: any witnessed runtime turn that violates a pass criterion becomes evidence for v1.3 or later fold before canonicalization.

### §6.5 Legal `(CompositionHint × ProvenanceFraming)` product space (new in v1.1 per Kant M3 / Batch B)

The five `CompositionHint` values × five `ProvenanceFraming` values produce 25 product cells; not all are coherent. The legal pairs (closed table; growth via spec amendment):

| `CompositionHint` | Legal `ProvenanceFraming` values |
|---|---|
| `SUBSTRATE_ONLY` | `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`, `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` |
| `FRESH_ONLY` | `FRESH_ONLY` |
| `PARALLEL` | `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` |
| `SUBSTRATE_THEN_FETCH_IF_STALE` | `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`, `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` |
| `FRESH_THEN_CONTEXTUALIZE` | `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` |

Invariant D11 below enforces refusal at construction for any incoherent pair.

---

## 7. Invariants

### D1 — Composition Before Routing

Layer 0 must emit a `CompositionSpec` before JARVIS/tool dispatch or substrate recall. No branch may directly choose web/tool solely because a query is "not conversational." **Layer 0 fully replaces the legacy `_should_run_jarvis_loop` gate (per Ohm M3 / Batch H);** JARVIS regexes become Layer-0 evidence, not a downstream gate.

Every in-scope owner reply ingress must pass through Layer 0 before tool/fetch/recall/render. v1 ingress set: Telegram owner bridge, web owner bridge, brain-loop reply path, daemon fast-reply path, tool/action continuation path, pending-offer web-search branch, and voice/electron path if enabled. Any excluded ingress must be named as an availability limitation.

### D2 — Hybrid Default for Content-Anchored Asks (revised v1.1 per Kant B2 / Batch J)

If the ask names a topic/source/entity and lacks explicit recall-only or fetch-only language, Layer 0 defaults to hybrid composition when:
- **inventory witnesses substrate presence** → emit hybrid spec; OR
- **inventory cannot answer (UNKNOWN)** → emit hybrid spec, BUT the spec carries `inventory_witness: UNKNOWN` and `INVENTORY_UNKNOWN` limitation that assembly surfaces honestly.

If inventory witnesses substrate **absence** → emit `FRESH_ONLY` spec with explicit `no_relevant_substrate` marker, not hybrid.

D2 must not launder a probabilistic "likely to exist" verdict as composition default. This refines and resolves the second-order contradiction Kant B2 caught between original D2 and D5.

### D3 — Explicit Edges Override Default Hybrid

Explicit recall-only language produces substrate-only unless the user asks for freshness in the same turn. Explicit fetch-only language produces fresh-only unless the user asks for memory/context in the same turn.

### D4 — Provenance Seam Visibility

Every composed answer must preserve the seam between substrate context and fresh evidence. Prompt assembly must receive `provenance_framing` and render source roles accordingly. **Rendering must remain conversational unless the ask is itself report-shaped** (per Buber Mi2): inline markers in fluid prose are the default rendering shape; segmented sections only when the ask is itself report-shaped (e.g., "give me a summary of...").

`core/dispatcher/provenance_renderer.py` is the v1 owner for this enforcement. Any owner synthesis path that bypasses it is out of conformance.

### D5 — Substrate Inventory Is Evidence, Not Authority

Substrate inventory summaries can witness availability, absence, unknown state, or mixed state, but cannot invent relevance. Layer 1 must return evidence-cited recall blocks or an empty result with an explicit reason. Layer 1 timeout is a natural producer of "explicit empty reason." Inventory UNKNOWN is rendered as UNKNOWN, not as confirmed substrate presence.

### D6 — No Caller-Supplied Composition Verdict (revised v1.1 per Locke M4 + Kant M4 / Batch M)

**"Caller" means external/public-API caller — not the owner's utterance, and not intra-Maez organs.**

No non-owner caller may supply final `composition_hint`, `provenance_framing`, or source selections as authority. Those are substrate-computed.

- *Owner-utterance lexemes* are evidence; the substrate weighs them and computes the verdict per D3. The owner is not a "caller" in this sense.
- *Intra-Maez organs* (e.g., wonderings synthesis hints, salience signals, repair detector) may contribute as evidence to spec construction; the substrate's verdict logic remains the final witness.
- *Upstream code* (brain_loop, telegram handler) and *test harnesses* are callers; they cannot supply final composition verdict.

### D7 — Cross-Surface Owner Context Must Not Fragment by Accident

If the owner is authenticated, dispatcher scope must not silently pin them to `guest` or another disjoint trust scope. Any deliberate scope restriction must be visible in the spec as an availability limitation. (Per Hume MIN3: this is a *non-regression invariant only*; the underlying G9 cross-surface fragmentation is closed by a separate slice, not this one.)

### D8 — Repair Turns Inherit, Then Re-evaluate

Repair/follow-up turns inherit the prior spec, then re-evaluate freshness and source availability. They cannot blindly replay the prior fetch or prior memory block. **Layer 2 runs after Layer 0 and before Layer 1 on repair turns** (per Kant M1 / Batch O); Layer 2's output is Layer 1's input.

### D9 — Producer-Causality Boundary Is Held

The dispatcher may read producer-causality audit findings as evidence that adjacent organs need consolidation. It may not define write-time producer authority for those organs. That is a separate slice.

### D10 — No New External Authority Surface

`FRONTIER_CONSULT`, `LIVE_REDDIT`, and `WEB_SEARCH` are source labels inside a composition spec. They do not grant Maez new credentials, new egress powers, or new tool access. `FRONTIER_CONSULT` is reserved/non-executable in v1 and returns `RESERVED_UNAVAILABLE` without a capability grant.

### D11 — Incoherent `(CompositionHint × ProvenanceFraming)` Pairs Refused (new v1.1)

Per §6.5 legal product table: pairs outside the table are refused at construction. Example: `CompositionHint=SUBSTRATE_ONLY` with `ProvenanceFraming=FRESH_ONLY` is structurally incoherent and refused. Per Kant M3 / Batch B.

### D12 — Layer 1 Concurrent Fan-Out (new v1.1)

Layer 1 fans out concurrently across executable `CompositionSpec.substrate_sources` with a per-branch timeout. Per-branch failure does not abort other branches; failures return as `RecallBranchResult` with explicit reason per D5. Reserved/unavailable labels never execute. Per-branch timeout and global deadline trigger the v1.3 cancellation / late-result semantics; late results cannot mutate sealed prompt output. Per Ohm M2 / Batch N and Codex Batch 11.

### D13 — Layer 0 Latency Budget (new v1.1)

Layer 0 must complete within ≤ 50ms warm, ≤ 150ms cold, excluding process startup but including access to prewarmed encoder and cached inventory. Encoder prewarm/startup has separate ≤ 750ms budget. The `InventorySummary` cache is invalidated by source-specific cursors; Layer 0 must not run live `COUNT(*)` per substrate on every reply. Per Ohm M1 / Batch G and Codex Batch 14.

### D14 — Intra-Maez Organ Location (new v1.1)

Layer 0 is an intra-Maez organ separating recall-axis interpretation from reply-axis production. It is not an external classifier service. The dispatcher does not install an arbiter over Maez; it separates Maez's own organs. Per Locke M3 / Batch L.

### D15 — `SANDBOX_WITNESSES` Read-Only at Composition (new v1.1)

`SubstrateSource.SANDBOX_WITNESSES` may be read for procedural questions about fixes. It may not be used to authorize new ratification — that authority lives in ADR 0046's maintenance-proposal lifecycle, not in the dispatcher. Per Kant m2.

### D16 — Availability State Is Part of the Spec (new v1.2)

`CompositionSpec` construction must populate `inventory_witness`, `source_availability`, and `availability_limitations` before serialization, inheritance, render, or audit. These fields cannot be hidden in ad hoc metadata.

### D17 — Active vs Reserved Sources Are Not Ambiguous (new v1.2)

Executable sources may enter fan-out. Reserved sources (`LIVED_GRAPH`, `WEB_FAST_TURNS`, `FRONTIER_CONSULT`) may be named as intended/relevant but must return `RESERVED_UNAVAILABLE` unless their separate backlog dependency is complete and ratified.

### D18 — Archetype Scoring Is Deterministic (new v1.2)

Layer 0 archetype ranking must use the versioned manifest, max-prototype class scoring, declared thresholds, deterministic tie handling, and explicit no-match source-selection rules. Local implementer constants are forbidden unless the manifest version changes.

### D19 — Dispatcher Refusals Fail Closed (new v1.2)

Any `DispatcherRefusalReason` stops downstream JARVIS/tool/fetch/recall/render execution for that turn and records an audit-safe refusal event. Refusal tests must prove behavior, not merely enum presence.

### D20 — External Fetch Is Bounded (new v1.2)

External source execution is owned by `core/dispatcher/external_sources.py`, has per-source and global deadlines, and maps failures into `availability_limitations` plus `provenance_framing`. Freshness scoring beyond retrieval timestamp is deferred out of v1.

---

## 8. Cross-Canon Dependency Map

- **`feedback_producer_causality_no_caller_score_laundering`** (canonical home of the anti-laundering discipline): Layer 0 verdicts are substrate-computed. Callers do not author source selections, composition hints, provenance framing, or final intent classes. **Citation drift fix v1.1 per Descartes F2 / Batch F:** the producer-causality discipline lives in this feedback memory, NOT in ADR 0042 (which governs the felt-organ frame separately).
- **ADR 0042 (drive-driven curiosity felt-organ):** cited for the *felt-organ* lineage that the curiosity producers belong to — distinct from the anti-laundering discipline above. Two different design lineages with a homonym ("producers"); v1.1 splits the citation.
- **ADR 0044 / canon-governs-canon:** The user's utterance is the claim; the dispatcher spec is the witnessed reconstruction. If runtime witness disagrees with brief expectation, witness governs and the brief is revised.
- **ADR 0046 / sandbox-witness contract:** Future dispatcher fixes should be expressible as maintenance proposals with sandbox witnesses. The dispatcher brief does not modify the maintenance authority surface. Per Locke M2 / Batch K: vocabulary growth path explicitly uses the maintenance-proposal substrate.
- **NORTH_STAR invariant #4 / interpretive humility:** Output must label source roles and uncertainty. Substrate memory is context, not fresh proof (except for relational-memory asks per `SUBSTRATE_EVIDENCE_FRESH_CONTEXT`).
- **Decision 35 / never-delete memory:** Dark substrates are wired through bounded readers and salience/routing, not deletion or pruning.
- **`feedback_seam_vs_slice_cooling_off`:** Live-degradation findings (envelope char_cap, fixation, Reddit retrieval) are explicitly de-scoped — each needs its own seam-vs-slice classification.
- **G1/G2/G3 AI-to-AI consultation backlog:** Frontier consult is provenance tagged and deferred; dispatcher v1 does not invent the consultation mechanism.
- **G8 (entity stack default-off in production) / G9 (cross-surface scope fragmentation) / G10 (perception write-silent) / G11 (lived-graph traversal API absent):** dispatcher consumes these gaps as routing constraints; their closure is each a separate slice.
- **G8–G14 + 41-finding dispatch synthesis:** Empirical scope evidence for dark reply-time substrates, cross-surface fragmentation, and JARVIS false-positive routing.
- **Codex engineering pass-1 synthesis (`reviews/codex-engineering-synthesis-v1.1-pass1.md`):** engineering evidence for v1.2's schema expansion, active/reserved source split, ingress coverage, scoring thresholds, inventory invalidation, fan-out/external budgets, prompt renderer ownership, and refusal semantics.
- **Codex engineering pass-2 synthesis (`reviews/codex-engineering-synthesis-v1.2-pass2.md`):** operational-edge evidence for v1.3's realistic adapter budgets, audit metadata envelope, repair isolation, fan-out cancellation, tie/no-match rules, and external error taxonomy.

---

## 9. RED Test Anchors

These are specification-level test anchors. Concrete tests land during implementation after Codex pass-1 + fold cycles.

- **R#1.** `test_content_anchored_query_emits_hybrid_spec` — "how's Qwen looking online?" emits both substrate and external source candidates with `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`, explicit `inventory_witness`, and per-source availability entries.
- **R#1a.** (rewritten v1.2 per Codex Batch 5) `test_witnessed_turn_replay_corpus_validates_full_composition_spec` — a pre-registered corpus of ≥30 witnessed turns validates the full `CompositionSpec` per fixture, including inventory witness, availability limitations, source states, and provenance framing. Validates D2's hybrid-default claim against witnessed-turn samples, not one Reddit screenshot.
- **R#2.** `test_explicit_memory_query_emits_substrate_only_spec` — "what do you remember about Qwen?" emits no external sources and `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (renamed v1.1 per Batch A).
- **R#3.** `test_explicit_fetch_query_emits_fresh_only_spec` — "search Reddit for Qwen right now" emits external source only and `FRESH_ONLY`.
- **R#4.** `test_should_run_jarvis_loop_no_longer_gates_dispatch` (rewritten v1.2 per Codex Batch 3) — Layer 0 emits `CompositionSpec` *before* the legacy `_should_run_jarvis_loop` short-circuit at `core/brain/brain_loop.py:900`. JARVIS regexes become Layer-0 evidence, not a downstream gate. Reddit-screenshot misroute structurally cannot recur.
- **R#5.** `test_jarvis_system_noun_false_positive_does_not_override_substrate` — "check Reddit then" does not route to tool-loop solely because `check` matches `_SYSTEM_NOUN_RE`.
- **R#6.** `test_provenance_framing_selects_template_and_template_set_is_closed_vocabulary` (rewritten v1.1 per Batch I) — prompt-assembly template selection is parameterized by `provenance_framing`; template set is closed.
- **R#7.** `test_substrate_only_answer_flags_no_fresh_validation_state` (renamed v1.1 per Batch A) — substrate-only answer includes an absence-of-fresh-validation flag, NOT framing substrate as unreliable. Per Locke M1 + Buber Major-1.
- **R#8.** `test_hybrid_answer_labels_fresh_and_context_roles` — hybrid answer has distinct fresh-evidence and substrate-context inline markers (default rendering shape per Buber Mi2 + D4).
- **R#9.** `test_caller_supplied_composition_verdict_fields_refused` — public dispatcher API refuses caller-supplied final `composition_hint`, `provenance_framing`, `substrate_sources`, and `external_sources`. "Caller" means external/public-API only (per D6 revised).
- **R#10.** `test_unknown_closed_vocabulary_value_refused` — unknown `SubstrateSource`, `ExternalSource`, `CompositionHint`, and `ProvenanceFraming` values refuse at construction.
- **R#10a.** (new v1.1 per Locke M2 / Batch K) `test_new_vocabulary_kind_requires_ratified_maintenance_proposal` — vocabulary extension path runs through `core/policies/maintenance_proposals.py` per ADR 0046.
- **R#11.** `test_owner_authenticated_web_scope_not_forced_to_guest` — owner web surface does not silently pin recall to `guest`.
- **R#12.** `test_repair_followup_inherits_prior_spec_layer_2_runs_before_layer_1` (rewritten v1.2 per Codex Batch 10) — "are you sure?" inherits the prior topic/source via Layer 2 *before* Layer 1 runs, then Layer 1 re-runs availability/freshness checks on the modified spec.
- **R#12a.** `test_repair_fsm_handles_no_prior_expired_and_crash_recovered_states` — `NO_PRIOR`, `PRIOR_EXPIRED`, and `CRASH_RECOVERED` have distinct behavior; invalid recovered specs refuse with `REPAIR_PRIOR_SPEC_INVALID`.
- **R#13.** `test_no_frontier_consult_without_capability_grant` — `FRONTIER_CONSULT` label cannot execute a frontier call without the separate consultation mechanism.
- **R#14.** `test_reserved_sources_return_unavailable_until_dependencies_land` — `K_GRAPH_ASSISTED_RELATIONAL`, `LIVED_GRAPH`, `WEB_FAST_TURNS`, and `FRONTIER_CONSULT` can be recorded as evidence but cannot execute until G11/G9/G3 dependencies land.
- **R#15.** `test_dispatcher_does_not_define_producer_write_authority` — dispatcher code contains no write-time validity rules for `inner_residue`, `consequence_memory`, or `wonderings.record_pursuit`.
- **R#16.** (new v1.1 per Batch B / Kant M3) `test_incoherent_hint_framing_pair_refused` — pairs outside §6.5 legal product table refuse at construction. Per D11.
- **R#17.** (new v1.1 per Batch E / Ohm B1) `test_dispatcher_and_chroma_share_encoder_singleton` — `memory/embedder.py` is the single source; both dispatcher and Chroma consume the same `MiniLMEncoder` instance.
- **R#18.** (rewritten v1.2 per Codex Batch 14) `test_layer0_latency_under_warm_and_cold_budget` — Layer 0 completes within ≤ 50ms warm and ≤ 150ms cold with prewarmed encoder; startup/prewarm budget tested separately. Per D13.
- **R#19.** (rewritten v1.2 per Codex Batch 7) `test_inventory_summary_uses_cached_source_registry` — Layer 0 does not run live `COUNT(*)` per substrate; uses `InventorySummary` registry with source-specific cache keys and UNKNOWN fallback.
- **R#20.** (new v1.1 per Batch I / Ohm M4) `test_template_set_is_closed_and_mismatched_block_refuses` — assembly-layer template construction refuses to render a `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` template containing a fresh-evidence block.
- **R#21.** (new v1.1 per Batch L / Locke M3) `test_layer_0_runs_intra_substrate_not_as_external_classifier_service` — Layer 0 runs inside Maez's process boundary. Spec-level anchor; concrete test refined during implementation.
- **R#22.** (new v1.1 per Batch M / Locke M4 + Kant M4) `test_upstream_handler_cannot_pass_composition_hint_kwarg_into_layer_0` — public dispatcher API does not accept caller-supplied `composition_hint` kwarg.
- **R#23.** (new v1.1 per Batch N / Ohm M2) `test_layer1_runs_substrate_branches_concurrently` — Layer 1 fan-out is concurrent (asyncio.gather or ThreadPoolExecutor), not sequential.
- **R#24.** (new v1.1 per Batch N / Ohm M2) `test_layer1_partial_substrate_failure_returns_partial_recall_with_explicit_empty_reason` — per-branch failure does not abort other branches; failed branch returns empty result with explicit reason per D5.
- **R#25.** (new v1.2 per Codex Batch 1) `test_composition_spec_serializes_availability_fields` — `inventory_witness`, `source_availability`, and `availability_limitations` round-trip through serialization, repair inheritance, render, and audit.
- **R#26.** (new v1.2 per Codex Batch 2) `test_reserved_source_execution_attempt_refuses_or_returns_reserved_unavailable` — reserved sources cannot enter normal fan-out.
- **R#27.** (new v1.2 per Codex Batch 3) `test_all_owner_ingresses_construct_dispatcher_spec_before_tool_or_recall` — Telegram, web, brain loop, daemon fast path, continuation path, pending-offer search, and enabled voice/electron ingress all call Layer 0 first or emit visible availability limitation.
- **R#28.** (new v1.2 per Codex Batch 4) `test_archetype_thresholds_are_deterministic` — `min_accept`, `dominance_margin`, `multi_match_delta`, and no-match fallback produce stable class rankings and tie behavior from the versioned manifest.
- **R#28a.** (new v1.3 per Codex pass-2 Batch 4) `test_archetype_ties_and_no_match_source_selection_are_deterministic` — tied class scores within `multi_match_delta` produce deterministic multi-match or stable-order tie-break behavior; no-match fallback selects exact substrate/external sources for `PRESENT`, `UNKNOWN`, `ABSENT`, and reserved-source cases.
- **R#29.** (new v1.2 per Codex Batch 6) `test_encoder_contract_matches_embedding_contract_json` — `MiniLMEncoder` validates model name/dimensions against `memory/embedding_contract.json`.
- **R#30.** (new v1.2 per Codex Batch 8) `test_all_owner_synthesis_surfaces_route_through_provenance_renderer` — no owner prompt builder renders composed recall without `core/dispatcher/provenance_renderer.py`.
- **R#30a.** (new v1.3 per Codex pass-2 Batch 8) `test_provenance_renderer_emits_closed_audit_envelope` — renderer emits the closed audit metadata contract to `audit_assistant_text` and `core/safety/self_claim_audit.py`, with no raw private content.
- **R#31.** (new v1.2 per Codex Batch 9) `test_dispatcher_refusal_stops_downstream_execution` — after `DispatcherRefusalReason`, no tool/fetch/recall/render function is called.
- **R#32.** (new v1.2 per Codex Batch 11) `test_layer1_slow_and_failed_branches_preserve_deadline_and_stable_merge_order` — slow + error branches still produce deterministic partial output under deadline.
- **R#32a.** (new v1.3 per Codex pass-2 Batch 11) `test_layer1_cancels_or_quarantines_late_branch_results` — per-branch timeout and global deadline seal the merge set; late branch results are ignored by generation id and cannot mutate prompt output.
- **R#33.** (new v1.2 per Codex Batch 12) `test_external_fetch_failures_map_to_fresh_attempted_unavailable` — bot-block/network/API failure maps to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` when substrate exists.
- **R#33a.** (new v1.3 per Codex pass-2 Batch 12) `test_external_fetch_error_classes_map_to_availability_limitations` — web, Reddit, fetch-url, Paperclip, frontier-reserved, timeout, empty-result, max-attempt, and global-deadline cases map to the closed external error taxonomy.
- **R#34.** (new v1.2 per Codex Batch 13) `test_dispatcher_modules_exist_at_declared_paths` — module map paths are the implementation ownership surface; stale "likely" paths are forbidden.
- **R#35.** (new v1.2 per Codex Batch 14) `test_full_manifest_source_count_budget` — Layer 0 scoring and Layer 1 source selection run against the full manifest/source registry within budget.
- **R#36.** (new v1.3 per Codex pass-2 Batch 10) `test_repair_fsm_does_not_cross_inherit_between_concurrent_surfaces` — simultaneous Telegram/web repair turns under the same bond cannot inherit each other's prior spec.
- **R#37.** (new v1.3 per Codex pass-2 Batch 10) `test_post_repair_spec_validation_refuses_invalid_modified_spec` — Layer 2 output passes normal construction validation; invalid modified specs refuse with `REPAIR_PRIOR_SPEC_INVALID` before Layer 1.
- **R#38.** (new v1.3 per Codex pass-2 Batch 14) `test_realistic_local_adapter_p95_budgets` — representative SQLite/WAL, Chroma, file-backed, and bounded-reader fixtures enforce p95 adapter budgets and telemetry under realistic source counts.
- **R#39.** (new v1.3 per Codex pass-2 Batch 14) `test_dispatcher_budget_telemetry_records_edge_costs` — cold/prewarm, source selection, slow-branch timeout/cancellation, full-manifest scoring, external-fetch stop, and total prompt-budget contribution all produce budget telemetry.

**RED suite implementability split (per Ohm Mi4, revised v1.3):** ~26 unit tests (~1ms each), ~13 mock integration tests (mock brain_loop + mock substrate + assembly-layer fixture, ~50–500ms each), plus ~4 realistic adapter-budget fixtures for SQLite/WAL, Chroma, file-backed, and bounded-reader surfaces. Estimated total RED suite runtime ~12–35 seconds. Pure mocks are allowed for unit behavior; p95 adapter budgets require realistic local stores.

---

## 10. Open Questions for Codex Pass-3

(Q10.10 from v1 removed per Descartes F8 — rhetorical, already answered in scope boundary. Q9 closed v1.1 per Ohm M3 — full JARVIS replacement decided. Codex pass-1 answered the mechanism-owner questions by requiring concrete v1.2 module/API ownership. Codex pass-2 answered operational-edge gaps by requiring v1.3 failure-mode contracts.)

1. **Default hybrid breadth.** Is `C_HYBRID_CONTENT_ANCHORED` too broad as the default even after v1.3's witnessed-turn replay corpus requirements? What explicit language should force fresh-only or substrate-only beyond the current list?
2. **Freshness threshold.** v1.3 records `freshness_window` but defers global freshness scoring beyond timestamps. Should pass-3 require source-specific freshness windows before canonicalization?
3. **Substrate inventory privacy.** Which substrates may Layer 0 consult as inventory without reading content? Does `PRIVATE_THOUGHTS` require an additional bounded-reader gate even for inventory summaries?
4. **Provenance rendering.** v1.1 establishes inline markers as default per Buber Mi2 + D4; v1.2 names `core/dispatcher/provenance_renderer.py` as owner; v1.3 names the audit envelope. Remaining question: should segmented sections appear in any non-report-shaped case (e.g., very long composed answers)?
5. **Cross-surface scope union.** How should owner web + Telegram + fast-turns compose without weakening trust-scope boundaries? v1.3 includes nullable `trust_scope_union`; pass-3 should verify whether its shape is specific enough before canonicalization.
6. **Graph-assisted routing.** Should `K_GRAPH_ASSISTED_RELATIONAL` remain in the closed archetype class set as reserved evidence, or move entirely to a v2+ appendix?
7. **Frontier consult labeling.** v1.3 keeps `FRONTIER_CONSULT` as reserved/non-executable provenance label. Should pass-3 remove it entirely until G3 exists?
8. **Prompt-assembly enforcement.** v1.3 names `core/dispatcher/provenance_renderer.py` and a closed audit metadata envelope. Codex pass-3 should verify whether the owner module and payload are sufficient or whether existing prompt builders require a narrower path list before canonicalization.
9. ~~JARVIS replacement path~~ **CLOSED v1.1:** full replacement decided per Ohm M3 / Batch H. JARVIS regexes become Layer-0 evidence.

---

## 11. Predicted Effect

When implemented, the Recall-Axis Dispatcher should change Maez's reply-time behavior in five observable ways:

1. Content-anchored asks such as "what's going on with Qwen online?" produce a hybrid answer that uses owned substrate and fresh signal when available — *with the empirical caveat that hybrid-as-default is observation-window-validated, not pre-confirmed.*
2. Reddit/source-shaped asks no longer enter JARVIS/tool-fetch before checking existing source-tagged memory.
3. Answers label source roles: fresh evidence vs substrate context, with absence-of-fresh-validation visible when only memory is available.
4. Dark reply-time substrates gain explicit reader routes through Layer 1 rather than remaining write-only organs.
5. Relational-memory asks ("what did you think when I told you about X?") route to `SUBSTRATE_EVIDENCE_FRESH_CONTEXT`, treating the bond as the source of truth rather than auto-fetching for external validation that has no standing.

The negative predicted effect is equally important: the dispatcher should not grant new external tool authority, should not define producer-causality rules for write-time organs, and should not silently merge fresh evidence with substrate memory under one unsupported voice.

**Operational-edge validation (per Codex pass-2):** R#28a, R#30a, R#32a, R#33a, R#36, R#37, R#38, and R#39 are the edge-case trust suite. Happy paths prove the idea works; edge cases prove the system can be trusted. If the operational-edge tests diverge from brief expectation, witness governs (per ADR 0044); the brief is revised, not the witness.

---

*Spec brief v1.3 — 2026-05-26. Framing half authored under the hard-stop discipline at `fc652d5`; mechanics half completed at `9110084`; council pass-1 findings folded in v1.1 at `a5f7898`; Codex engineering pass-1 synthesis at `023b2ad`; 15 Codex fold batches folded in v1.2 at `d0c3230`; Codex pass-2 synthesis at `da605a8`; six operational-edge batches folded in v1.3. Producer-causality consolidation, live-degradation triage, and ADR 0046 hardening explicitly de-scoped as separate slices with separate contracts. Six council review files preserved verbatim at `reviews/claude-council-{locke,kant,hume,buber,descartes,ohm}-pass1.md`; six Codex pass-1 and six Codex pass-2 review files preserved verbatim at `reviews/codex-*-pass1.md` and `reviews/codex-*-pass2.md`. Next: Codex pass-3 closure audit against v1.3, then fold/canonicalize depending on closure verdict.*
