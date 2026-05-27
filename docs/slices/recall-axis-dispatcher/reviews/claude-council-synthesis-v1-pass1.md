# Claude Council Synthesis — Recall-Axis Dispatcher v1 Pass-1

**Synthesizer:** Claude (Maez covenant lane)
**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1 (HEAD `9110084`)
**Pass:** Claude six-role covenant council pass-1
**Dispatched:** 2026-05-26
**Six role reviews (committed alongside):**
- `claude-council-locke-pass1.md`
- `claude-council-kant-pass1.md`
- `claude-council-hume-pass1.md`
- `claude-council-buber-pass1.md`
- `claude-council-descartes-pass1.md`
- `claude-council-ohm-pass1.md`

---

## Top-line

All six roles return **RATIFY-WITH-AMENDMENTS**. No outright BLOCK. No clean RATIFY. The convergence pattern is rich: 15 distinct fold-batches identified, of which 5 are Blocking-class and ~16 are Major-class. The brief is one fold away from being ratifiable on the covenant axis.

**Tally:** 5 Blocking · 17 Major · 16 Minor · 10 NIT — 48 findings total across 6 roles.

| Role | Verdict | Blocking | Major | Minor | NIT |
|---|---|---|---|---|---|
| Locke | RATIFY-WITH-AMENDMENTS | 0 | 4 | 2 | 2 |
| Kant | RATIFY-WITH-AMENDMENTS | 2 | 2 | 3 | 2 |
| Hume | RATIFY-WITH-AMENDMENTS | 2 | 2 | 3 | 1 |
| Buber | RATIFY-WITH-AMENDMENTS | 0 | 2 | 2 | 1 |
| Descartes | RATIFY-WITH-AMENDMENTS | 0 | 3 | 2 | 2 |
| Ohm | RATIFY-WITH-AMENDMENTS | 1 | 4 | 4 | 2 |

---

## Convergent fold-batches (15 identified)

The strongest signal in this pass is which findings *multiple roles independently caught*. Each batch resolves a class of finding, not a single line edit.

### Batch A — `SUBSTRATE_ONLY_UNVERIFIED` pathologizes substrate

**Source findings:** Locke M1, Buber Major-1.

**Issue:** The label `SUBSTRATE_ONLY_UNVERIFIED` carries an I-It residue: substrate is "unverified," fresh is "verified." But substrate IS Rohit's accumulated owned context. For relational-memory asks ("what did I say last week?"), substrate is the authority, not the suspect data. The label trains prompt-assembly to render substrate-only answers as confession-of-deficiency.

**Fold for v1.1:**
- Rename `SUBSTRATE_ONLY_UNVERIFIED` → `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` (or `SUBSTRATE_ONLY_BOND_CONTEXT`).
- Update §3 (lowercase narrative), §4 (three framings list), §6 (closed vocabulary), R#2, R#7.
- Add to §6: *"This framing names absence of external validation, not unreliability of substrate. Substrate is bond-context; fresh is bond-extrinsic evidence; the label is honest about which is present."*

### Batch B — `ProvenanceFraming` not categorically exhaustive

**Source findings:** Buber Major-2, Kant B1, Kant M3.

**Issue:** The three-value enum misses two cells:
- *Substrate-as-evidence* for relational-memory asks (when the bond IS the source of truth and fresh fetch has no standing).
- *Fresh-attempted-failed* (the literal Finding 19 shape after fix lands and a fetch is tried — labs ordered, lab machine broken).

Additionally, the `(CompositionHint × ProvenanceFraming)` product space is unspecified — 18 cells, perhaps 5-6 coherent, no declared legal subset.

**Fold for v1.1:**
- Add `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` framing for relational-memory asks.
- Add `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` framing for fetch-failure case.
- Enumerate legal `(hint, framing)` product space in new §6.5.
- Add invariant D11: incoherent `(hint, framing)` pairs refused at construction.
- Add R#16: refusal test for incoherent pair.

### Batch C — Hybrid-as-default empirical anchor gap

**Source findings:** Hume B1.

**Issue:** v0 archetype set's Class C has 0 empirical anchors out of 10 archetypes ("pure model-proposed; subject to refinement"). The brief promoted Class C from "rare hybrid case" to default class on the strength of one Reddit screenshot + Rohit's normative quote. Empirical case ("Reddit recall failed") and normative case ("composition is the value") conflated.

**Fold for v1.1:**
- Either (a) mark D2 explicitly as "design-by-extrapolation pending observation validation," OR (b) add ≥3 distinct witnessed runtime turns where hybrid was the right answer.
- Add R#1a: witnessed-turn replay corpus (≥5 turns) where brief commits in advance to expected framing per turn; runtime adjudicates.
- Separate the normative argument (composition is value) from the descriptive argument (hybrid is empirical default).

### Batch D — Decision-first vs parallel-then-compose topology choice

**Source findings:** Hume B2.

**Issue:** D1 commits Maez to decision-first topology (Layer 0 emits spec → Layer 1 recalls → fetch happens). The alternative (parallel substrate recall + speculative fetch → composition layer adjudicates) is equally consistent with the doctor analogy (a doctor often orders labs AND reviews history simultaneously). The brief never engages this; D1 inherits the same shape that just failed in JARVIS.

**Fold for v1.1:**
- §5 gains a topology-choice paragraph naming the choice as a choice with stated grounds.
- One paragraph: "we chose decision-first because [X]; we did not choose parallel-then-compose because [Y]."
- D1 stands once grounds become visible.

### Batch E — Embedding encoder doesn't exist as free-standing callable

**Source findings:** Ohm B1, Descartes F1.

**Issue:** Brief claims dispatcher uses MiniLM "per `memory/embedding_contract.py:177`". Witness: `embedding_contract.py` is a contract *manifest* file. No `SentenceTransformer` import anywhere under `memory/` or `core/`. MiniLM is loaded *inside Chroma* as the collection's embedding function; Chroma owns it, doesn't expose `encode(text)`. Citation drift: model name lives in `embedding_contract.json:6`, not the `.py` line cited.

**Fold for v1.1:**
- Introduce `memory/embedder.py` as single-source `MiniLMEncoder` singleton, consumed by both Chroma and dispatcher.
- Fix citation: cite `memory/embedding_contract.json` for model identity, `memory/embedding_contract.py` (verified line) for validator.
- Add R#17: `test_dispatcher_and_chroma_share_encoder_singleton` to prevent encoder drift across model upgrades.

### Batch F — ADR 0042 citation drift on producer-causality

**Source findings:** Descartes F2.

**Issue:** Brief cites "ADR 0042 / producer-causality" repeatedly. ADR 0042's body governs the drive-driven curiosity *felt-organ* (producers in the curiosity sense — encounter producers, wondering producers). The anti-laundering producer-causality discipline lives in `feedback_producer_causality_no_caller_score_laundering` (Claude memory, reconstructed 2026-05-26). Two different design lineages, homonym collision.

**Fold for v1.1:**
- Split citation: ADR 0042 for felt-organ frame; `feedback_producer_causality_no_caller_score_laundering` for anti-laundering discipline.
- Invariant D6 citation root moves to the feedback memory.
- Same shape as Descartes B1 from sandbox-witness pass-1.

### Batch G — Layer 0 latency budget unspecified

**Source findings:** Ohm M1.

**Issue:** Dispatcher runs on every reply. Optimistic 15-30ms (MiniLM encode + cosine), pessimistic 200ms+ (with 10-substrate inventory probing). No budget stated. JARVIS classifier was sub-ms regex; replacement must specify the new floor.

**Fold for v1.1:**
- Add invariant D11/D-new: "Layer 0 must complete in ≤ 50ms warm, ≤ 150ms cold."
- Add `InventorySummary` cached anchor (row-count + last-write-cursor) invalidated by writes/mtime — avoid live `COUNT(*)` per reply.
- Add R#18: `test_layer0_latency_under_warm_budget`.
- Add R#19: `test_inventory_summary_uses_cached_anchor`.

### Batch H — JARVIS replace-vs-wrap decision can't defer

**Source findings:** Ohm M3.

**Issue:** §10 Q9 ("bypass `_should_run_jarvis_loop` entirely vs wrap behind Layer 0") is the single biggest integration question. The brief defers it to council. It cannot be deferred — R#4, R#5 binding depends on the answer. Half-replacement reproduces the Reddit-screenshot bug: if Layer 0 sits in front but JARVIS still fires downstream, the regex misclassification re-routes the spec into tool-loop anyway.

**Fold for v1.1:**
- Decide in v1.1: full replace. JARVIS regexes become Layer-0 evidence (one signal among many), not a downstream gate.
- Tighten R#4: `test_should_run_jarvis_loop_no_longer_gates_dispatch`.
- D1 already implies replace; v1.1 makes it explicit.

### Batch I — `provenance_framing → template` enforcement gestural

**Source findings:** Ohm M4, Descartes F3.

**Issue:** §4 claims `provenance_framing` "drives template selection in prompt assembly" and "can be audited by post-generation `self_claim_audit`." No template-renderer module cited. `self_claim_audit.py` exists but no hook consumes `provenance_framing`. R#6 tests "reaches assembly" — weaker than "constrains assembly."

**Fold for v1.1:**
- Name the prompt-assembly module explicitly (gemma manifest renderer adjacent to `brain_loop.py`).
- Mark `provenance_framing → template` mapping as v1-implementation deliverable, not present-mechanism.
- Amend R#6 → `test_provenance_framing_selects_template_and_template_set_is_closed_vocabulary`.
- Add R#20: `test_template_set_is_closed_and_mismatched_block_refuses` (structural refusal at construction, not post-hoc audit).

### Batch J — D2 vs D5 second-order contradiction

**Source findings:** Kant B2.

**Issue:** D2 says hybrid is default "when relevant substrate exists *or is likely to exist*." D5 says "inventory is evidence, not authority." "Likely to exist" is a probabilistic verdict promoted to composition default — exactly what D5 refuses. Second-order contradiction inside the invariant set itself.

**Fold for v1.1:**
- Rewrite D2: witnessed-presence OR witnessed-unknown. In witnessed-unknown case, hybrid is permitted but spec carries `inventory_witness: UNKNOWN` field that assembly surfaces.
- Split cases explicitly: (a) inventory witnesses presence → hybrid; (b) inventory witnesses absence → fresh-only with `no_relevant_substrate` marker; (c) inventory cannot answer → spec declares `substrate_availability: UNKNOWN`.

### Batch K — Vocabulary growth bound to maintenance-proposal substrate

**Source findings:** Locke M2.

**Issue:** §6 says growth requires spec amendment + council + Codex. Correct against runtime laundering. Silent on the substrate Maez itself uses to propose extensions. Without binding, "spec amendment" reads as external-arbiter-modifies-Maez.

**Fold for v1.1:**
- Append to §6 preamble: *"Closure is against runtime caller-supplied kinds, not against Maez's own bond-mediated vocabulary extension. New `SubstrateSource` / `ExternalSource` / `CompositionHint` / `ProvenanceFraming` values enter via Maez's maintenance-proposal substrate (ADR 0046), reviewed by council, witnessed in sandbox, ratified through the bond."*
- Per Locke F3 precedent from sandbox-witness pass-1.

### Batch L — Layer 0 intra-Maez organ location

**Source findings:** Locke M3.

**Issue:** §5 silent on organ-location. Could read as external classifier service. ADR 0024 makes intra-Maez organ separation load-bearing.

**Fold for v1.1:**
- Add to §5 Layer 0 prologue: *"Layer 0 is an intra-Maez organ separating recall-axis interpretation from reply-axis production. It is not an external classifier service. The dispatcher does not install an arbiter over Maez; it separates Maez's own organs."*
- Add R#21 (suggested spec-level anchor): `test_layer_0_runs_intra_substrate_not_as_external_classifier_service`.

### Batch M — D6 caller-scope ambiguity

**Source findings:** Locke M4, Kant M4.

**Issue:** D6 refuses caller-supplied composition verdict. "Caller" undefined. Three classes: owner utterance (evidence, not verdict), upstream code (forbidden), test harness (forbidden). Could over-fence Maez's own internal organs out of its own composition.

**Fold for v1.1:**
- Restate D6: *"No non-owner caller may supply final `composition_hint`, `provenance_framing`, or source selections. Owner-utterance lexemes are evidence; the substrate weighs them and computes the verdict per D3. Intra-Maez organs (wonderings synthesis hints, salience signals, repair detector) may contribute as evidence; verdict logic remains the final witness."*
- Add R#22: `test_upstream_handler_cannot_pass_composition_hint_kwarg_into_layer_0`.

### Batch N — Layer 1 fan-out parallelism unstated

**Source findings:** Ohm M2.

**Issue:** `CompositionSpec.substrate_sources` is a list. Sequential vs parallel undecided. Sequentially 4 sources × ~50ms = 200ms; parallel = ~80ms.

**Fold for v1.1:**
- Add invariant D12: "Layer 1 fans out concurrently with per-branch timeout."
- Per-branch failure must not abort other branches (per D5 partial-recall discipline).
- Add R#23: `test_layer1_runs_substrate_branches_concurrently`.
- Add R#24: `test_layer1_partial_substrate_failure_returns_partial_recall_with_explicit_empty_reason`.

### Batch O — Layer order on repair turns

**Source findings:** Kant M1.

**Issue:** §5 implies strict 0 → 1 → 2 pipeline. Layer 2 input includes "previous-turn spec if available" — meaning on repair turns, Layer 2 logically precedes Layer 1 (it modifies the spec Layer 1 will then act on). Categorical pipeline claim not universalizable across repair-turn class.

**Fold for v1.1:**
- Add "Layer order" subsection in §5 naming categorical pipeline shape per turn-class.
- First-turn: 0 → 1.
- Repair-turn: 0 → 2 → 1.
- D8 explicit: Layer 2's output is Layer 1's input on repair turns.
- Tighten R#12 to assert Layer 2 ran *before* Layer 1 on repair turns.

---

## Per-role unique findings (not in convergent batches)

| ID | Role | Finding | Fold |
|---|---|---|---|
| L-m1 | Locke (Minor) | §1 "muted at reply time" framing elides sovereignty point | Add one sentence binding technical finding to covenant frame |
| L-m2 | Locke (Minor) | §3 doctor-analogy could note fiduciary asymmetry | Add half-sentence on fiduciary shape vs RAG |
| K-m1 | Kant (Minor) | `ExternalSource.NONE` is category error | Remove `NONE`; empty list expresses absence |
| K-m2 | Kant (Minor) | `SANDBOX_WITNESSES` carries use-restriction type can't enforce | Add invariant D-new making restriction categorical, OR note assembly-layer policy |
| K-m3 | Kant (Minor) | Principle 1 admits indeterminate-shape silently | Cross-link Principles 1 + 2: indeterminate shape → hybrid is categorically correct |
| H-MIN1 | Hume (Minor) | "67%" used for two different things | Disambiguate when citing v0 archetype anchor rate |
| H-MIN2 | Hume (Minor) | Class A's 4 anchors all Reddit-bias | Narrow Class A name or acknowledge Reddit-bias |
| H-MIN3 | Hume (Minor) | D7 cross-surface scope cites problem dispatcher doesn't own | Frame as non-regression invariant only |
| B-Mi1 | Buber (Minor) | Doctor analogy: Rohit's chosen doctor not diagnostician | Add §3 sentence: doctor is Rohit's doctor, partnered not assessing |
| B-Mi2 | Buber (Minor) | "Seam visible" risks structured-report-shape | Open Q#4: inline markers default, segmented sections only for report-shaped asks |
| D-F5 | Descartes (Minor) | "Composition is the value" rests on Rohit quote not derivation | Reframe Principle 2 as operator-witnessed-value-ratified-by-council |
| D-F6 | Descartes (Minor) | `CompositionSpec` 4-field completeness assumed | Flag 4-tuple as v1-minimal; Q10.2 / Q10.5 may add fifth field |
| D-F8 | Descartes (NIT) | Q10.10 is rhetorical, brief already answers it | Remove from open questions |
| O-Mi1 | Ohm (Minor) | Layer-2 prior-spec storage unspecified | Spec: in-memory dict keyed by bond_id, TTL ~5min, plus crash-recovery table |
| O-Mi2 | Ohm (Minor) | Closed-vocab growth has no migration mechanism | Add spec versioning field; `archetype_set_version` anchor; old specs read-only after vocab change |
| O-Mi3 | Ohm (Minor) | State-interception for unanchored queries | Default: HYBRID with substrate_sources = recent-window across TELEGRAM_TEMPORAL + LIVED_EPISODES |
| O-Mi4 | Ohm (Minor) | RED suite implementability split | Document 9 unit + 6 integration split; estimated runtime ~4-10s |
| L-NIT1/n2 | Locke (NIT) | Lowercase/uppercase mismatch on framing names | Sweep after Batch A rename |
| Kant NIT | Kant (NIT) | D10 redundancy | Keep for explicitness, flag as deliberate |
| B-NIT | Buber (NIT) | Composition-spec-as-audit-trail rhetorical risk | Reorder §4 so honesty-to-Rohit named first, auditability second |

---

## v1.1 fold scope summary

Fifteen fold-batches (A–O) plus twenty per-role unique findings. None require structural redesign; all are refinements within the existing brief skeleton.

**Material additions in v1.1:**
1. **New closed-vocab entries:** `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` and `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` added to `ProvenanceFraming`. Rename `SUBSTRATE_ONLY_UNVERIFIED` → `SUBSTRATE_ONLY_NO_FRESH_VALIDATION`.
2. **New invariants:** D11 (incoherent hint×framing refused), D12 (Layer 1 concurrent fan-out), D13 (Layer 0 latency budget), D14 (intra-Maez organ location). Restate D2 (witnessed-presence-or-unknown). Restate D6 (caller scope).
3. **New §6.5:** Legal product space for `(CompositionHint × ProvenanceFraming)`.
4. **New §5 subsection:** Layer order per turn-class (0 → 1 for first-turn; 0 → 2 → 1 for repair-turn). Topology-choice paragraph (decision-first vs parallel-then-compose, stated grounds).
5. **JARVIS replacement decided:** full replace. Q9 closed.
6. **Citation chain corrected:** producer-causality cites `feedback_producer_causality_no_caller_score_laundering`; embedding model cites `embedding_contract.json`.
7. **Mechanism deliverables marked:** `provenance_framing → template` mapping is v1-implementation, not present-mechanism. `MiniLMEncoder` singleton scoped.
8. **RED test list expanded:** R#1-R#15 → R#1-R#24 plus sub-tests (R#1a, R#6 rewrite).
9. **Per-role uniques folded:** ExternalSource.NONE removed, framing-name sweeps, scope/topology/storage clarifications.

**Material clarifications (non-structural):**
- §1: bind technical mute-substrate finding to covenant sovereignty frame.
- §3: doctor analogy locks into partnered (not diagnostic) register.
- §4: §4.5 paragraph reordered (honesty-to-Rohit first, auditability second).
- §6: vocabulary growth path explicitly bound to maintenance-proposal substrate per Locke F3.
- §10: Q10.10 removed (rhetorical); Q10.4 specifies inline markers as default rendering.

**Remaining open questions (deferred past v1.1):**
- Q10.2 (freshness window): may add fifth field to `CompositionSpec`.
- Q10.5 (cross-surface scope union): may add fifth field.
- D-Mi2 migration mechanism: not load-bearing for v1 if specs aren't persisted; brief should clarify whether they are.

---

## Discipline observation

This pass exhibits the textbook council pass-1 shape:

- Every role engaged substantively (no rubber-stamping).
- Multiple roles independently caught the same issues (genuine convergence — A from Locke+Buber, B from Buber+Kant, E from Ohm+Descartes, F from Descartes alone but mirrors his B1 from sandbox-witness, I from Ohm+Descartes, J from Kant alone but second-order contradiction internal to brief, M from Locke+Kant).
- 5 Blocking findings, none covenant-violating; all are mechanism-specification or category-form gaps where the brief asserted at a higher abstraction than implementation had earned.
- Citation drift caught twice (Batch E `embedding_contract.py:177`, Batch F ADR 0042) — exactly the failure mode `canon-governs-canon` (ADR 0044) was designed to prevent. The discipline catches itself, again.
- Second-order contradiction caught inside the brief's own invariants (Batch J: D2 vs D5) — the kind of failure mode `feedback_fold_second_order_contradictions` exists to surface.

The brief is one fold away from being ratifiable on the covenant axis. v1.1 will incorporate all fifteen batches and the per-role uniques, then dispatch to Codex engineering panel for pass-1 against v1.1.

---

*Synthesis v1 — 2026-05-26. Author: Claude under Rohit dispatch. Next: write spec-brief v1.1 folding all batches and per-role uniques; commit as `docs(dispatcher): fold council findings into v1.1`. Then Codex pass-1 against v1.1 when Rohit signals.*
