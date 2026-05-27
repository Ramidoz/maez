# Recall-Axis Dispatcher — Spec Brief v0.1 (framing half)

**Prepared:** 2026-05-26
**Slice:** Recall-Axis Dispatcher
**Parent/runtime base:** `5bcb15e docs(backlog): record hybrid-default dispatcher refinement`
**Status:** v0.1 — **framing half only.** Sections 1–4 (Why This Slice Exists, Three Design Principles, Doctor Analogy, Composition Specification). Mechanics half (layered architecture, closed vocabularies, invariants, RED tests, dependency map, council questions, predicted effect) deferred to a subsequent draft session.
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
ComposionSpec = {
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

### What the brief does NOT specify (v1 mechanics half)

This v0.1 framing-half draft intentionally stops here. v1 mechanics half will specify:
- Layered architecture: Layer 0 (substrate-vs-tool + spec construction), Layer 1 (substrate-axis routing), Layer 2 (repair/follow-up modifiers)
- Closed vocabularies: `SubstrateSource`, `ExternalSource`, `CompositionHint`, `ProvenanceFraming`, and the intent classes A–K from the v0 archetype set
- Invariants: substrate consultation before tool dispatch, seam visibility in composed output, role labeling per source, refuse-at-construction caller-supplied authority
- RED test anchors: per invariant, per closed-vocabulary refusal, per provenance framing
- Cross-canon dependency map: producer-causality, canon-governs-canon, sandbox-witness, interpretive humility, plus the 10-agent + testing dispatch evidence pile
- Council questions: deliberately-undecided judgment calls for council pass-1
- Predicted effect: what the dispatcher does when it lands

---

*Spec brief v0.1 (framing half) — 2026-05-26. Author: Claude under Rohit dispatch. Mechanics half deferred to a subsequent draft session per the hard-stop discipline. Producer-causality consolidation explicitly de-scoped as a separate slice with a separate contract. Live-degradation triage and ADR 0046 hardening also de-scoped: distinct surfaces, separate review cycles.*
