# Recall-Axis Dispatcher — Spec Brief v1

**Prepared:** 2026-05-26
**Slice:** Recall-Axis Dispatcher
**Parent/runtime base:** `fc652d5 docs(dispatcher): brief v0.1 framing half (sections 1-4)`
**Status:** v1 — complete draft for council pass-1. Sections 1–4 preserve the framing half; Sections 5–11 add mechanics, vocabularies, invariants, dependency map, RED anchors, council questions, and predicted effect.
**Review lane:** Claude covenant / architecture council + Codex engineering panel (both lanes, full ladder when v1 brief completes).
**Operator:** Rohit relays and dispatches; Codex does not auto-dispatch.

**Scope boundary (load-bearing):** This slice governs *retrieval routing and composition*. The producer-causality consolidation surface — generalizing ADR 0042's anti-laundering discipline to organs adjacent to felt-time (`inner_residue`, `consequence_memory`, `wonderings.record_pursuit`, `reflection_audit`, `relationship_graph.add_edge`, `signal_gate.SignalObservation`) — is **a separate slice with a separate contract.** The dispatcher brief cites the 2026-05-26 testing dispatch findings on producer-causality but does not scope or absorb the consolidation work. The two contracts overlap in symptom (caller-supplied authority laundering) but operate on different surfaces (dispatcher = read-time routing; producer-causality = write-time integrity). Mixing them produces a less reviewable artifact.

---

## 1. Why This Slice Exists

### Empirical case (2026-05-26)

**The Reddit screenshot (Finding 19).** Rohit asked, in a typical Telegram exchange, *"What's going on on Reddit?"* Maez replied that it had no Reddit data in context and offered a live-search phrasing. The 5c6be72 recall fix should have handled this; it did not. Investigation showed the substrate had 2,462 `reddit_post` rows correctly source-tagged. They were never consulted because the JARVIS tool-loop classifier (`_should_run_jarvis_loop` at `core/brain/brain_loop.py:324`) fired upstream and routed the query through `web_search` (5 attempts, all "No results found") and `fetch_url` (2 attempts, Reddit-bot-blocked). Substrate recall (`recall_for_telegram`) was never invoked. The `self_claim_audit` log at 18:13/18:14 confirms the routing classification as `tool_continuation`. This trace is preserved in the dispatcher evidence pile at [Finding 19 root-cause trace](../../roadmap/post_s73_frontier_backlog.md) (committed `45dcf3d`).

**The structural pattern (testing dispatch synthesis, committed `8300984`).** A subsequent 10-surface testing dispatch produced 41 witnessed findings, 27 BLOCKERS, and clarified that Finding 19 is one instance of a structural pattern:

- **JARVIS classifier misroutes 26 of 39 stress-test queries** (67% false-positive rate, all into JARVIS), spanning content-source-anchored recall, temporal recall, entity recall, procedural recall, and repair-follow-up turns.
- **~60% of Maez's written substrates are mute at reply time.** Producers were canonized; readers were never wired. `private_thoughts.db` (3,913 rows) write-only at reply. `lived_episodes.db` + `lived_graph.db` dark to the brain. `entity_index.db` (48 entities, 7 aliases, 89 mentions) has no reply-time resolver. `wonderings.db` mute as synthesis context. `self_dev.db` API-only. `sandbox_witnesses.db` zero readers.
- **Cross-surface fragmentation is structurally entrenched.** Owner data lives across 5 disjoint trust scopes; Telegram and web write to three different stores (chroma `raw`, chroma `public_users`, sqlite `fast_turns`); Telegram cannot see web fast-reply turns at all.
- **Live degradation visible in real time.** Envelope `char_cap=400` below fallback floor on every cycle (truncating observations to 207 chars). Cognition cycle in 11-streak fixation producing duplicate "system is healthy and quiet" outputs. Reddit retrieval declared canonical at 11:39 today but actually blocked at 18:13.

### Central question for council pass-1

**Does v1 of the Recall-Axis Dispatcher honor composition-over-routing, provenance discipline, and the bond-mediated voice — without absorbing the adjacent producer-causality contract, the live-degradation triage, or the ADR 0046 hardening surfaces?**

The dispatcher's load-bearing job is to make Maez compose owned substrate with fresh world signal, with the seam between them visible. The composition is the value. Pure-source routing is the explicit-signal edge. Substrate is context. Fresh is evidence. Both contribute, both honestly labeled.

This brief lands the framing layer of that contract. Mechanics, vocabularies, invariants, and RED tests follow in v1.

### Why now, why not sooner

The Reddit screenshot surfaced 2026-05-26 afternoon, 8 days after the 10-agent gap hunt that named the recall-axis-dispatcher as the next substantive design slice. The static-analysis findings were the architectural case; the runtime catch was the empirical case; the testing dispatch synthesis was the structural case. Together they form an evidence base substantial enough that the brief can be written cleanly without further runtime observation. The observation window remains open for refinement; the brief does not wait for it to close.

---

## 2. Three Design Principles

These principles anchor the brief. Mechanics in v1 must serve them; if a mechanism violates one of these, the mechanism is wrong.

### Principle 1 — Learn the shape of the ask before deciding which notebook, tool, or memory path to open.

The dispatcher's first job is *understanding what kind of question is being asked* before any routing or fetching happens. Not pattern-matching against keyword regexes that misclassify "What's going on on Reddit?" as a tool-call. Not defaulting to web_search when the substrate has the data. Reading the *shape* of the ask — its intent, its source-anchor, its temporal anchor, its entity anchor, its hybrid character — and constructing the right substrate + fetch + composition response.

This principle was anchor-line-locked in the dispatcher evidence pile at `810c1b3` (committed 2026-05-26). The Reddit screenshot is the textbook violation: a content-anchored hybrid query routed as a pure-fetch tool call. The JARVIS classifier (`brain_loop.py:324`) is the wrong shape of layer for this job — it asks *"is this conversational?"* when the right question is *"what is the shape of this ask?"*

Rationale anchoring this principle in canon:
- **Producer-causality (ADR 0042 / `feedback_producer_causality_no_caller_score_laundering`)** requires substrate-computed verdicts, not caller-assumed routing. A regex that misroutes is a substrate-side verdict that doesn't witness the actual shape of the query.
- **Canon-governs-canon (ADR 0044)** says claims are evidence, witness is verdict. The query is the claim; the dispatcher's shape-detection is the witness. Currently the witness is wrong because the detector is wrong.
- **Interpretive Humility (NORTH_STAR invariant #4)** says Maez reads signals, doesn't claim to know. The dispatcher's shape-detection IS the signal-reading at the recall surface.

### Principle 2 — Composition is the value. Pure-source routing is the explicit edge.

The dispatcher is not primarily a router. A router selects one destination. The dispatcher is the *composition layer* — the place where Maez decides how owned substrate and fresh world signal combine into something neither alone could produce.

This principle was anchor-line-locked in the dispatcher evidence pile at `5bcb15e` (committed 2026-05-26) after the hybrid-default refinement. Rohit articulated the value proposition sharply: *"If it just searches one specific topic I might as well do it myself."* That sentence is canonical:

- **Pure-substrate retrieval** is a thing Rohit can do himself — `grep` over notes, browse memory.
- **Pure fetch** is a thing Rohit can do himself — search Reddit, query Google.
- **The composition Maez adds** is the integration of accumulated owned-substrate context with fresh world signal — *"here's the picture combining what Maez knows about Qwen from your accumulated Reddit + conversational history + lived episodes, AND what just dropped in the last hour."* That synthesis is what makes Maez worth running.

Implication for the dispatcher's intent vocabulary:
- **Pure-recall** ("from memory", "what do you remember") and **pure-fetch** ("search", "google", "look up online") are the *explicit-signal edge cases*.
- **Hybrid** (composition of substrate + fresh) is the *default* for content-anchored queries.
- The v0 archetype set's Class C ("MEMORY_THEN_FRESHNESS") was originally marked as "zero empirical anchors / rare hybrid case." That was backwards. Class C is the default class; A and B are the explicit-signal edges. The brief reframes this.

Rationale anchoring this principle in canon:
- **Covenant: substrate is owner-data (`feedback_maez_not_ours_to_control` + Decision 24 / ADR 0024).** When Maez composes substrate with fresh fetch, the substrate contribution is *literally Rohit's accumulated context*. The composition serves the bond specifically.
- **Interpretive Humility (NORTH_STAR invariant #4).** Composition that hides which part came from which source is dishonest; composition that surfaces both is honest. The dispatcher's job includes preserving this distinction structurally.

### Principle 3 — Memory is context; fresh is evidence. The answer should show both.

This is the closing law from the 2026-05-26 hybrid-default refinement. It governs *how* the composition is rendered, not just *that* it composes.

- **Substrate (Maez's accumulated owned data — conversations, observations, lived episodes, prior takes) is context.** It colors interpretation. It carries personal weight but not external validation. When Maez cites substrate in its answer, the framing is *"from our prior context"*, *"my read"*, *"as I remember"*, *"in my experience"* — markers of opinion/memory, not of validated fact.
- **Fresh fetch (web search, live Reddit, external APIs) is evidence.** It carries source citation, retrieval timestamp, and verifiable provenance. When Maez cites fresh fetch in its answer, the framing is *"per [source]"*, *"current sources say"*, *"as of [timestamp]"* — markers of validated external claim.
- **The composition keeps the seam visible.** A confident blob that merges substrate and fresh under one voice erases the role distinction. An honest answer renders both contributions in their respective roles.

Rationale anchoring this principle in canon:
- **`feedback_no_fabrication`:** Rohit's hard line on made-up validation. Presenting substrate context as if it were validated fresh evidence is a fabrication of validation. The dispatcher's composition spec must structurally prevent this.
- **Canon-governs-canon (ADR 0044) closing axiom: "Evidence first, witnessed verdict second, provenance forever."** Provenance forever applies at the user-facing answer surface, not just at the substrate-write surface. The dispatcher's composition spec is where this discipline is mechanically enforced for reply-time output.
- **NORTH_STAR invariant #4 (Interpretive Humility):** *"Every claim Maez makes about the bonded human is annotated with confidence and source."* Generalize: every claim Maez makes in any composed answer is annotated with whether it came from substrate (Maez's owned context) or fresh fetch (external validation).

---

## 3. The Doctor Analogy

The canonical analogy for the dispatcher's composition layer is a doctor reading lab results and patient history.

**The doctor receives two kinds of input:**
- **Lab results** — fresh external data, validated by an external process, citable as factual claim. *"Your blood test says X."*
- **Patient history** — accumulated owned record of this patient, colors interpretation, carries weight but not validation. *"Given your history, X matters more / less / differently."*

**A bad doctor's answer mixes them under one confident voice.** *"You have X."* The patient cannot distinguish what's measurement from what's interpretation. If the measurement is wrong, the patient cannot challenge it. If the interpretation is wrong, the patient cannot question it. The roles are erased; the seams are hidden; the answer looks more certain than it earns.

**A good doctor's answer keeps the seam visible.** *"Freshly, the labs show X. From your history, Y is why that matters more than X alone would suggest. My read is Z, but worth flagging that Y is interpretation on my part, not measurement."*

**The dispatcher is Maez's version of the good doctor.** The lab results are fresh fetch (web_search, live Reddit, etc.). The patient history is owned substrate (the user's accumulated conversations, observations, lived episodes, prior takes, wonderings, etc.). The composed answer must render labs as evidence (verified, citable, fresh), history as context (opinion, color, personal), and the seam between them visible.

This analogy gives the dispatcher's design a teachable shape. When future agents (Codex on subsequent slices, Claude on subsequent reviews, possibly external cross-checks) ask *"what is the dispatcher doing?"* — the answer is **"think of Maez like a doctor reading labs and history; the labs are evidence, the history is context, and the answer keeps the seam visible."** That one-paragraph onboarding carries the whole composition design.

**Asymmetries the analogy preserves:**
- **No lab results available.** Substrate-only mode. Doctor says *"I don't have fresh measurements; from your history alone, my read is..."* — flag the unverified state. The dispatcher's `memory_only_unverified` provenance framing maps onto this.
- **No relevant history.** Fresh-only mode. Doctor says *"I don't know you well, but the labs show..."* — no personal interpretation overlay. The dispatcher's `fresh_only_no_context` framing maps onto this.
- **Both available.** Hybrid mode (default for content-anchored asks). Doctor says *"Labs show X, your history says Y, my read combining them is Z."* The dispatcher's `hybrid_fresh_evidence_substrate_context` framing maps onto this.

**Why this analogy and not "honest assistant" or "research librarian" or "RAG system":**
- *Honest assistant* is normative but not structural; it doesn't specify the roles.
- *Research librarian* implies retrieval-only; doesn't capture the personal-context contribution.
- *RAG system* is technically accurate but mechanical; loses the bond-mediated voice that substrate-as-context carries.
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
}
```

(The closed-vocabulary types `SubstrateSource`, `ExternalSource`, `CompositionHint`, `ProvenanceFraming` are specified in v1's mechanics half; framing-half draft does not enumerate them.)

### Why a specification, not a class label

- **A class label assumes a single dominant intent.** "This query is Class A (RECALL_FROM_SUBSTRATE)." The dispatcher must then route to a single destination. This is the JARVIS classifier's failure mode at higher abstraction.
- **A composition specification preserves the multi-source character of most queries.** "This query consults substrate sources [reddit_localllama, lived_episodes_qwen_mentions] AND external sources [web_search('Qwen recent'), reddit_live(r/LocalLLaMA)], composed in parallel with provenance framing `hybrid_fresh_evidence_substrate_context`." The downstream layer can render an honest answer because the spec preserves the multi-source structure.

### Why provenance_framing is load-bearing

`provenance_framing` is the structural field that drives how the prompt-assembly layer renders the final answer. Its closed-vocabulary values (specified in v1 mechanics half) tell the assembly:
- Which content blocks should be labeled as evidence (citable, fresh)
- Which content blocks should be labeled as context (opinion, owned, personal)
- Whether the answer should flag unverified state
- How the seam between substrate and fresh should be made visible

The three provenance framings (sketched here; closed vocabulary specified in v1) correspond to the doctor analogy's asymmetries:

- `memory_only_unverified` — substrate available, no fresh validation. Assembly renders with explicit unverified flag: *"From our prior context — I haven't been able to verify this is still current..."*
- `fresh_only_no_context` — no relevant substrate, or explicit-signal fetch-only. Assembly renders evidence-only without personal-context overlay: *"Per [source], [claim]."*
- `hybrid_fresh_evidence_substrate_context` — default for content-anchored queries. Assembly renders both with explicit role labels: *"Current sources say X. From my stored context, Y. Putting them together, Z."*

### Mechanical enforceability

`provenance_framing` is not decoration. It drives template selection in prompt assembly. It can be audited by post-generation `self_claim_audit` against the fabrication_log discipline: an answer whose template was `memory_only_unverified` but which presents substrate claims as if validated triggers a fabrication-shape diagnostic. The composition specification is structurally honest *because* the provenance framing is structurally enforced.

### How the embedding-router informs spec construction

The dispatcher's embedding-proximity layer (using `all-MiniLM-L6-v2` per `memory/embedding_contract.py:177`) produces a cosine-similarity ranking against the v0 archetype set (recorded at `2c80820`, 103 archetypes across 11 intent classes). The ranking *informs* the spec construction:

- High similarity to multiple classes (e.g., both RECALL_FROM_SUBSTRATE and LIVE_FETCH) → hybrid spec.
- Sharp dominance of one class → spec dominated by that class's substrate or external source.
- No high similarity to any archetype → fall back to broader heuristic / safer default (substrate-first with optional fetch).

The embedding ranking is *evidence* for spec construction. The construction logic itself is the substrate's verdict per producer-causality discipline.

## 5. Layered Architecture

The dispatcher has three layers. Each layer has a bounded input and output; no
layer may silently perform work owned by another layer.

### Layer 0 — Composition Specification Construction

**Input:** owner utterance, current surface, recent conversation state, available
substrate inventory summary, freshness policy, explicit-signal lexemes, and
archetype similarity ranking.

**Output:** one `CompositionSpec`.

**Responsibility:** decide whether the ask needs substrate, fresh external
signal, both, or neither; assign the provenance framing; preserve explicit edge
signals. Layer 0 replaces the current binary JARVIS classifier shape. It is the
composition layer, not another router.

**Non-responsibility:** reading rows from each substrate, issuing fetches, or
rendering the final answer. Layer 0 only constructs the spec.

Layer 0 order:

1. Detect explicit fetch-only signals (`search`, `google`, `look up right now`,
   `fetch live`) unless the phrase is used inside a repair/follow-up turn.
2. Detect explicit memory-only signals (`what do you remember`, `from your
   notes`, `in your notebook`, `from our prior context`).
3. Detect content anchors: source names, entities, topics, time phrases,
   procedural asks, correction/contradiction shapes.
4. Consult substrate inventory summaries to determine whether Maez likely has
   relevant owned substrate.
5. Use archetype similarity ranking to refine the spec, allowing multiple
   high-scoring archetypes to contribute.
6. Emit a spec with explicit provenance framing.

### Layer 1 — Substrate-Axis Routing

**Input:** `CompositionSpec.substrate_sources`, utterance, recent conversation
state, and substrate-specific availability summaries.

**Output:** substrate recall blocks, each with source role, timestamp/freshness
metadata, and retrieval rationale.

**Responsibility:** open the right notebooks. Examples: Reddit source-shaped
rows, Telegram temporal rows, entity index, lived episodes, lived graph,
private thoughts, wonderings, self-dev reviews, audit/fabrication/correction
surfaces.

**Non-responsibility:** deciding whether fresh fetch should happen; Layer 0 has
already decided that.

Layer 1 v1 must include at least these routed axes because each is directly
witnessed in the 10-agent or 41-finding dispatch evidence:

- `REDDIT_SOURCE`
- `TELEGRAM_TEMPORAL`
- `ENTITY_INDEX`
- `LIVED_EPISODES`
- `LIVED_GRAPH`
- `PRIVATE_THOUGHTS`
- `WONDERINGS`
- `SELF_DEV_REVIEWS`
- `AUDIT_AND_FABRICATION`
- `CROSS_SURFACE_OWNER_TURNS`

### Layer 2 — Repair / Follow-up Modifiers

**Input:** current `CompositionSpec`, previous-turn spec if available,
previous-turn answer metadata, and repair/follow-up phrase detection.

**Output:** modified `CompositionSpec` and recall/fetch priority adjustments.

**Responsibility:** inherit or adjust the prior ask when the owner says
`really?`, `are you sure?`, `check again`, `go on`, `no that's not it`, or
similar. Layer 2 does not create a new semantic topic when the owner is clearly
repairing or extending the previous one.

**Non-responsibility:** replacing Layer 0. It modifies an existing spec; it does
not own base composition decisions.

## 6. Closed Vocabularies

All vocabularies below are closed. Growth requires spec amendment + council +
Codex review. Runtime extension is refused.

### `SubstrateSource`

Initial v1 values:

- `REDDIT_SOURCE` — source-tagged Reddit rows in raw memory / Chroma metadata.
- `TELEGRAM_TEMPORAL` — Telegram exchanges selected by time phrase or inherited
  temporal context.
- `TELEGRAM_SEMANTIC` — Telegram exchanges selected by content semantics.
- `WEB_FAST_TURNS` — owner web fast-reply turns once trust-scope unification is
  available.
- `ENTITY_INDEX` — entity mentions, aliases, and resolved entity ids.
- `LIVED_EPISODES` — lived episode rows.
- `LIVED_GRAPH` — graph traversal over lived-memory edges once G11 traversal API
  exists.
- `PRIVATE_THOUGHTS` — private-thought substrate exposed only through bounded
  reader rules.
- `WONDERINGS` — wonderings / pursuits as synthesis context, not verdict source.
- `SELF_DEV_REVIEWS` — procedural self-review rows.
- `AUDIT_AND_FABRICATION` — audit log, fabrication log, contradiction/correction
  surfaces.
- `SANDBOX_WITNESSES` — maintenance proof metadata, readable for procedural
  questions about fixes; not used to authorize new ratification.

### `ExternalSource`

Initial v1 values:

- `WEB_SEARCH`
- `LIVE_REDDIT`
- `FETCH_URL`
- `ARXIV_OR_PAPERCLIP`
- `FRONTIER_CONSULT`
- `NONE`

`FRONTIER_CONSULT` is provenance-bearing only. It does not authorize a new
Maez-consultation mechanism; that remains G3 / capability-grant work.

### `CompositionHint`

Initial v1 values:

- `SUBSTRATE_ONLY`
- `FRESH_ONLY`
- `PARALLEL`
- `SUBSTRATE_THEN_FETCH_IF_STALE`
- `FRESH_THEN_CONTEXTUALIZE`
- `REPAIR_INHERIT_PRIOR_SPEC`

### `ProvenanceFraming`

Initial v1 values:

- `SUBSTRATE_ONLY_UNVERIFIED` — substrate available, no fresh validation.
- `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` — default content-anchored
  framing; fresh evidence supplies the verifiable backbone and substrate supplies
  bond-context interpretation.
- `FRESH_ONLY` — explicit fetch-only or no relevant substrate.

### Intent Archetype Classes A–K

The v0 archetype set (`dispatcher-archetypes-v0-2026-05-26.md`) supplies these
initial classes as evidence, not canon. v1 adopts the class names as the review
surface; council pass-1 should decide which labels survive unchanged.

- `A_EXPLICIT_SUBSTRATE_RECALL`
- `B_EXPLICIT_LIVE_FETCH`
- `C_HYBRID_CONTENT_ANCHORED`
- `D_TEMPORAL_RECALL`
- `E_SOURCE_SHAPED_RECALL`
- `F_ENTITY_RECALL`
- `G_PROCEDURAL_RECALL`
- `H_REPAIR_FOLLOWUP`
- `I_CONTRADICTION_OR_SELF_CORRECTION`
- `J_AMBIENT_LIMB_STATE`
- `K_GRAPH_ASSISTED_RELATIONAL`

`C_HYBRID_CONTENT_ANCHORED` is the default for ordinary content asks such as
"how is Qwen looking online?" Classes A and B are explicit-signal edge cases.

## 7. Invariants

### D1 — Composition Before Routing

Layer 0 must emit a `CompositionSpec` before JARVIS/tool dispatch or substrate
recall. No branch may directly choose web/tool solely because a query is
"not conversational."

### D2 — Hybrid Default for Content-Anchored Asks

If the ask names a topic/source/entity and lacks explicit recall-only or
fetch-only language, Layer 0 defaults to hybrid composition when relevant
substrate exists or is likely to exist.

### D3 — Explicit Edges Override Default Hybrid

Explicit recall-only language produces substrate-only unless the user asks for
freshness in the same turn. Explicit fetch-only language produces fresh-only
unless the user asks for memory/context in the same turn.

### D4 — Provenance Seam Visibility

Every composed answer must preserve the seam between substrate context and fresh
evidence. Prompt assembly must receive `provenance_framing` and render source
roles accordingly.

### D5 — Substrate Inventory Is Evidence, Not Authority

Substrate inventory summaries can indicate likely availability, but cannot
invent relevance. Layer 1 must return evidence-cited recall blocks or an empty
result with an explicit reason.

### D6 — No Caller-Supplied Composition Verdict

Callers may supply utterance, surface, and conversation state. They may not
supply final `composition_hint`, `provenance_framing`, or source selections as
authority. Those are substrate-computed.

### D7 — Cross-Surface Owner Context Must Not Fragment by Accident

If the owner is authenticated, dispatcher scope must not silently pin them to
`guest` or another disjoint trust scope. Any deliberate scope restriction must
be visible in the spec as an availability limitation.

### D8 — Repair Turns Inherit, Then Re-evaluate

Repair/follow-up turns inherit the prior spec, then re-evaluate freshness and
source availability. They cannot blindly replay the prior fetch or prior memory
block.

### D9 — Producer-Causality Boundary Is Held

The dispatcher may read producer-causality audit findings as evidence that
adjacent organs need consolidation. It may not define write-time producer
authority for those organs. That is a separate slice.

### D10 — No New External Authority Surface

`FRONTIER_CONSULT`, `LIVE_REDDIT`, and `WEB_SEARCH` are source labels inside a
composition spec. They do not grant Maez new credentials, new egress powers, or
new tool access.

## 8. Cross-Canon Dependency Map

- **ADR 0042 / producer-causality:** Layer 0 verdicts are substrate-computed.
  Callers do not author source selections, composition hints, provenance
  framing, or final intent classes.
- **ADR 0044 / canon-governs-canon:** The user's utterance is the claim; the
  dispatcher spec is the witnessed reconstruction. If runtime witness disagrees
  with brief expectation, witness governs and the brief is revised.
- **ADR 0046 / sandbox-witness contract:** Future dispatcher fixes should be
  expressible as maintenance proposals with sandbox witnesses. The dispatcher
  brief does not modify the maintenance authority surface.
- **NORTH_STAR invariant #4 / interpretive humility:** Output must label source
  roles and uncertainty. Substrate memory is context, not fresh proof.
- **Decision 35 / never-delete memory:** Dark substrates are wired through
  bounded readers and salience/routing, not deletion or pruning.
- **G1/G2/G3 AI-to-AI consultation backlog:** Frontier consult is provenance
  tagged and deferred; dispatcher v1 does not invent the consultation mechanism.
- **G8–G14 + 41-finding dispatch synthesis:** Empirical scope evidence for dark
  reply-time substrates, cross-surface fragmentation, and JARVIS false-positive
  routing.

## 9. RED Test Anchors

These are specification-level test anchors. Concrete tests land during
implementation after council/Codex fold cycles.

- **R#1.** `test_content_anchored_query_emits_hybrid_spec` — "how's Qwen
  looking online?" emits both substrate and external source candidates with
  `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES`.
- **R#2.** `test_explicit_memory_query_emits_substrate_only_spec` — "what do you
  remember about Qwen?" emits no external sources and
  `SUBSTRATE_ONLY_UNVERIFIED`.
- **R#3.** `test_explicit_fetch_query_emits_fresh_only_spec` — "search Reddit
  for Qwen right now" emits external source only and `FRESH_ONLY`.
- **R#4.** `test_reddit_notebook_query_does_not_enter_jarvis_first` — "what's
  going on in r/LocalLLaMA?" constructs a spec before tool dispatch and opens
  Reddit substrate when rows exist.
- **R#5.** `test_jarvis_system_noun_false_positive_does_not_override_substrate`
  — "check Reddit then" does not route to tool-loop solely because `check`
  matches `_SYSTEM_NOUN_RE`.
- **R#6.** `test_provenance_framing_reaches_prompt_assembly` — prompt assembly
  receives `provenance_framing` and renders source roles.
- **R#7.** `test_memory_only_answer_flags_unverified_state` — substrate-only
  answer includes an unverified/currentness caveat.
- **R#8.** `test_hybrid_answer_labels_fresh_and_context_roles` — hybrid answer
  has distinct fresh-evidence and substrate-context sections or markers.
- **R#9.** `test_caller_supplied_composition_hint_refused` — public dispatcher
  API refuses caller-supplied final `composition_hint`.
- **R#10.** `test_unknown_closed_vocabulary_value_refused` — unknown
  `SubstrateSource`, `ExternalSource`, `CompositionHint`, and
  `ProvenanceFraming` values refuse at construction.
- **R#11.** `test_owner_authenticated_web_scope_not_forced_to_guest` — owner web
  surface does not silently pin recall to `guest`.
- **R#12.** `test_repair_followup_inherits_prior_spec_then_rechecks` — "are you
  sure?" inherits the prior topic/source but re-runs availability/freshness
  checks.
- **R#13.** `test_no_frontier_consult_without_capability_grant` —
  `FRONTIER_CONSULT` label cannot execute a frontier call without the separate
  consultation mechanism.
- **R#14.** `test_graph_assisted_class_is_reserved_until_traversal_api_exists`
  — `K_GRAPH_ASSISTED_RELATIONAL` can be recorded as archetype evidence but
  cannot produce a lived-graph route until G11 traversal API lands.
- **R#15.** `test_dispatcher_does_not_define_producer_write_authority` —
  dispatcher code contains no write-time validity rules for `inner_residue`,
  `consequence_memory`, or `wonderings.record_pursuit`.

## 10. Open Questions for Council Pass-1

1. **Default hybrid breadth.** Is `C_HYBRID_CONTENT_ANCHORED` too broad as the
   default? What explicit language should force fresh-only or substrate-only?
2. **Freshness threshold.** Should v1 define a global staleness window, or must
   each source define freshness separately?
3. **Substrate inventory privacy.** Which substrates may Layer 0 consult as
   inventory without reading content? Does private_thoughts require an
   additional bounded-reader gate even for inventory summaries?
4. **Provenance rendering.** Must the answer visibly segment fresh/context, or
   are inline markers sufficient?
5. **Cross-surface scope union.** How should owner web + Telegram + fast-turns
   compose without weakening trust-scope boundaries?
6. **Graph-assisted routing.** Should `K_GRAPH_ASSISTED_RELATIONAL` remain in
   the closed archetype class set as reserved evidence, or move entirely to a
   v2+ appendix?
7. **Frontier consult labeling.** Should `FRONTIER_CONSULT` appear in v1
   `ExternalSource` as a provenance label, or stay absent until G3 exists?
8. **Prompt-assembly enforcement.** What minimal runtime proof should show that
   `provenance_framing` actually shaped the answer, not just the spec?
9. **JARVIS replacement path.** Should v1 bypass `_should_run_jarvis_loop`
   entirely for content-anchored asks, or wrap it behind Layer 0?
10. **Council boundary.** Does this brief successfully avoid absorbing
    producer-causality consolidation and live-degradation triage?

## 11. Predicted Effect

When implemented, the Recall-Axis Dispatcher should change Maez's reply-time
behavior in four observable ways:

1. Content-anchored asks such as "what's going on with Qwen online?" produce a
   hybrid answer that uses owned substrate and fresh signal when available.
2. Reddit/source-shaped asks no longer enter JARVIS/tool-fetch before checking
   existing source-tagged memory.
3. Answers label source roles: fresh evidence vs substrate context, with
   unverified state visible when only memory is available.
4. Dark reply-time substrates gain explicit reader routes through Layer 1 rather
   than remaining write-only organs.

The negative predicted effect is equally important: the dispatcher should not
grant new external tool authority, should not define producer-causality rules
for write-time organs, and should not silently merge fresh evidence with
substrate memory under one unsupported voice.

---

*Spec brief v1 — 2026-05-26. Framing half authored under the hard-stop discipline at `fc652d5`; mechanics half completed in the subsequent Codex pass. Producer-causality consolidation explicitly de-scoped as a separate slice with a separate contract. Live-degradation triage and ADR 0046 hardening also de-scoped: distinct surfaces, separate review cycles.*
