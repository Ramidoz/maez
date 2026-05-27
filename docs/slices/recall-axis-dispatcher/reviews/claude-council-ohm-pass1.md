# Ohm — Council Pass-1 Review — Recall-Axis Dispatcher v1

**Reviewer:** Ohm (resistance / mechanism / what actually runs)
**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1 (HEAD `9110084`)
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

The brief is structurally honest, the layering bounded, and the closed vocabularies disciplined. But six mechanism questions need amendment before Codex panel: dispatcher latency budget is unspecified and the embedding-encode path is non-trivial under current Chroma coupling; Layer-1 fan-out parallelism is unstated; the embedding-router's reuse assumption is mechanically wrong as written; `provenance_framing→template` enforcement surface is gestural; closed-vocabulary growth has no migration mechanism; JARVIS replacement-vs-wrap path is the single biggest integration risk and is left to Q9.

---

## Blocking

### B1. Embedding-router cannot reuse `all-MiniLM-L6-v2` as currently loaded — assumption mechanically wrong

**Severity:** Blocking. Load-bearing.

Section 4 / §"How the embedding-router informs spec construction" claims the dispatcher uses MiniLM "per `memory/embedding_contract.py:177`" to encode archetype/query vectors. Witness: `memory/embedding_contract.py` is a contract *manifest* file. It does **not** load a `SentenceTransformer`. There is no `SentenceTransformer` import anywhere under `memory/` or `core/`. MiniLM is loaded *inside Chroma* as the collection's embedding function — Chroma owns it, encodes on `add()`/`query()`, and does not expose a free-standing `encode(text) -> vector` callable to dispatcher code.

**8-step trace:**

1. **Dependency-map:** Layer 0 must compute a per-query embedding to rank against 103 archetype vectors. The brief's source-citation gestures at `embedding_contract.py:177`, but no encoder lives there. Code path doesn't exist.
2. **Write-path:** none for dispatcher reads; but archetype-set bootstrap requires a one-time encode of 103 archetypes.
3. **Read-path:** to compute cosine to archetypes the dispatcher needs `encode(query) -> np.ndarray[384]`. Three real options: (a) load a second `SentenceTransformer("all-MiniLM-L6-v2")` in-process (RAM ~80MB, model load ~1-3s at startup, encode ~5-15ms CPU per query); (b) issue `raw.query(query_texts=[q], n_results=0)` so Chroma encodes, then steal the embedding from internal cache — unsupported API; (c) expose the embedder via a thin wrapper module the dispatcher imports.
4. **Test-path:** R#1 ("emits hybrid spec") cannot pass deterministically without a stable encoder seam. Without (c), test fixtures will need to mock either Chroma internals or a phantom encoder.
5. **Fold-summary:** the brief assumes a free-standing encoder seam that does not exist. The amendment is: introduce `memory/embedder.py` as the single-source `MiniLMEncoder` (load-once singleton), and have Chroma's `embedding_function` and the dispatcher both consume it. Otherwise we double-load the model (160MB) and risk encoder drift.
6. **Cross-reference:** ADR 0042 producer-causality — if dispatcher and Chroma each encode independently, their vectors might diverge across model-version upgrades; "substrate-computed verdict" splits into two substrates computing inconsistently.
7. **RED-test trace:** add `test_dispatcher_and_chroma_share_encoder_singleton` so a model swap can never silently desynchronize archetype scoring from substrate retrieval.
8. **Verify-before-declaring:** `grep -rn "SentenceTransformer" memory/ core/` returns zero hits. Confirmed: no in-process encoder exists. The brief's section-4 citation is incorrect.

---

## Major

### M1. Dispatcher latency budget is unspecified — runs on every reply

**Severity:** Major. Load-bearing.

The dispatcher runs on every owner turn (D1). The Reddit-screenshot trace at 18:12-18:13 fires JARVIS classifier (~regex, sub-ms) and immediately enters tool loop. Layer 0 replaces that gate but adds: (a) one MiniLM encode (5-15ms CPU); (b) cosine against ~103 × 384 vectors (matmul, ~0.5-2ms); (c) substrate inventory queries — `SELECT COUNT(*) WHERE source_anchor=?` per substrate, potentially across 10 SubstrateSources. If any inventory probe is unindexed it can spike to 100ms+. Total: optimistically 15-30ms, pessimistically 200ms+. No budget is stated.

**8-step trace:**

1. **Dependency-map:** every reply path through `core/brain/brain_loop.py:900` will gate on Layer 0. Latency adds to all replies, not just JARVIS misroutes.
2. **Write-path:** none.
3. **Read-path:** the 10-substrate inventory check is the dominant cost. `entity_index.db`, `lived_episodes.db`, `wonderings.db`, `private_thoughts.db`, etc. each need an indexed availability summary. Unindexed COUNT(*) on a 3,913-row `private_thoughts.db` is sub-ms with SQLite cache; cold-cache is 10-30ms. Across 10 substrates this compounds.
4. **Test-path:** RED suite must include a latency-budget test (`test_layer0_under_50ms_on_warm_cache`) or D1 ratifies a regression risk.
5. **Fold-summary:** invariant D-new: "Layer 0 must complete in ≤ 50ms warm, ≤ 150ms cold; substrate inventory uses cached row-count + last-write-cursor anchors, not live COUNT(*)." Add an `InventorySummary` cache invalidated by writes (or by mtime).
6. **Cross-reference:** §10 Q8 asks how to prove `provenance_framing` shaped the answer; orthogonal to latency. Latency budget belongs in §7 invariants, not §10 open questions.
7. **RED-test trace:** add `test_layer0_latency_under_warm_budget` and `test_inventory_summary_uses_cached_anchor`.
8. **Verify-before-declaring:** the brief itself notes the canon discipline: "No latency claim should appear in canon until benchmarked." Then it must also not implicitly promise sub-JARVIS latency without a budget invariant. Currently it does.

### M2. Layer 1 fan-out — parallelism unstated

**Severity:** Major. Load-bearing.

`CompositionSpec.substrate_sources` is a *list*. A content-anchored Qwen query plausibly hits `REDDIT_SOURCE`, `LIVED_EPISODES`, `ENTITY_INDEX`, `WONDERINGS`. Each retrieval issues its own DB/Chroma query. Sequentially that's 4 × ~30-80ms = 120-320ms wall-clock added before generation. Parallel via `asyncio.gather` or a thread pool, it's max(branch) ≈ 80ms. The brief does not say which.

**8-step trace:** (1) D-map: Layer 1 output is a *list* of recall blocks; (2) every additional source adds an IO round-trip; (3) ChromaDB's PersistentClient is not async-native — naive thread-pool wrapping is required; (4) test path: add `test_layer1_runs_substrate_branches_concurrently`; (5) fold: invariant "Layer 1 fans out concurrently with a per-branch timeout"; (6) ADR 0046 atomicity discipline — each branch's failure must not abort the others; (7) RED: `test_layer1_partial_substrate_failure_returns_partial_recall_with_explicit_empty_reason` (D5 already requires the explicit reason — Layer 1 timeout is a natural producer of that reason); (8) verify: `grep -n "asyncio\|ThreadPoolExecutor" memory/memory_manager.py` shows current recall is synchronous single-thread. New work, must be scoped.

### M3. JARVIS replacement path — Q9 is load-bearing, not optional

**Severity:** Major. Load-bearing.

§10 Q9 ("bypass `_should_run_jarvis_loop` entirely vs wrap behind Layer 0") is the single biggest integration question, and the brief defers it to council. It cannot be deferred — every RED anchor R#4, R#5 depends on the answer. Witness: `core/brain/brain_loop.py:900` currently gates the entire downstream loop on `_should_run_jarvis_loop(user_text)` returning True; if Layer 0 sits *in front*, JARVIS still fires its regex misclassification downstream and re-routes the spec into tool-loop anyway.

**8-step trace:** (1) D-map: `_should_run_jarvis_loop` calls `_CONVERSATIONAL_RE` and `_is_conversational_intent` to gate; Layer 0 must own this gate or be subordinated to it; (2) write-path: none; (3) read-path: dispatcher must emit `CompositionSpec` *before* the JARVIS short-circuit at line 900, then the JARVIS path either becomes a downstream Layer-1 branch (mapped to `WEB_SEARCH`/`FETCH_URL` ExternalSources) or is removed; (4) test-path R#4 currently reads "constructs a spec before tool dispatch" — the verb "before" implies front-position but does not say replace-vs-wrap; (5) fold-summary: **recommend replace**, with JARVIS regexes becoming Layer-0 evidence (one signal among many) rather than a gate; (6) cross-ref: D1 says no branch may directly choose web/tool because "not conversational" — this literally describes the existing JARVIS gate, so D1 already implies replace, but the brief should state it; (7) RED add `test_should_run_jarvis_loop_no_longer_gates_dispatch`; (8) verify: line 900 confirmed as the gate.

### M4. `provenance_framing → prompt-assembly` enforcement surface is gestural

**Severity:** Major. Load-bearing.

§4 says `provenance_framing` "drives template selection" and §11 says "answers label source roles." But there is no current template-renderer module cited, and no enumeration of (template × framing) pairs. Mechanically: the prompt-assembly layer either (a) selects one of 3 templates per framing value (concrete, audit-able), or (b) injects a framing-aware preamble into the existing single template (looser, easier to drift). R#6 asserts framing "reaches" assembly — a weaker claim than "constrains" assembly.

**8-step trace:** (1) D-map: assembly module not named in brief; (2) write-path: framing must be passed through whatever struct represents the prompt context; (3) read-path: assembly reads framing, branches template; (4) test-path R#6 + R#7 + R#8 cover *reaches* and *renders* but not *refuses-on-mismatch* — a `memory_only_unverified` template that happens to also include a fresh-evidence block should be a structural refusal at construction, not a post-hoc audit; (5) fold: amend R#6 to `test_provenance_framing_selects_template_and_template_set_is_closed_vocabulary`; (6) cross-ref ADR 0044 — provenance forever applies at the rendered output, not just the spec field; (7) RED add `test_template_set_is_closed_and_mismatched_block_refuses`; (8) verify: not done — Ohm has not located the assembly module; brief should name it (probably the gemma manifest renderer adjacent to `brain_loop.py`).

---

## Minor

### Mi1. Layer-2 prior-spec storage is unspecified

§5 Layer 2 inherits "previous-turn spec if available." Witness: `_is_temporal_recall_followup` at `memory/memory_manager.py:491` is a stateless lexeme matcher with no prior-spec store. A new persistent or session-scoped store is required (`last_spec_by_bond_id`). Mechanism: in-memory dict keyed by `bond_id` with TTL ~5 min, plus a single-row table `dispatcher_last_spec` for crash recovery. One-paragraph amendment, not load-bearing for ratification but absent.

### Mi2. Closed-vocabulary growth has no migration mechanism

§6 says growth requires spec amendment + council + Codex review. Mechanism question: when `SubstrateSource.LIVED_GRAPH` becomes live post-G11, historical `CompositionSpec` rows (if persisted for replay/audit) will lack the value; archetype vectors must be re-encoded if the archetype set grows. The brief says nothing about migration. Recommend: spec versioning field on the `CompositionSpec` row, `archetype_set_version` anchor, and an explicit "old specs are read-only after vocabulary change" rule. *Not load-bearing for v1 if specs aren't persisted; brief should clarify whether they are.*

### Mi3. State-interception for queries naming no specific substrate

Open question implicit in §5 step 4: "what's happening lately" names no substrate. Layer 0 cannot consult substrate inventories meaningfully — it has nothing to look up. Default behavior should be `HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES` with substrate sources = recent-window across `TELEGRAM_TEMPORAL` + `LIVED_EPISODES`. Spell this out in §5 or in D2.

### Mi4. RED suite implementability — 9 unit, 6 integration

R#1, R#2, R#3, R#9, R#10, R#13, R#15 are unit tests against the spec dataclass and refusal codepath (~1ms each). R#4, R#5, R#11, R#12 require a mock brain_loop scaffold and a mock substrate. R#6, R#7, R#8 require an assembly-layer fixture. R#14 is a static-import test. Estimated total RED suite runtime: ~4-10 seconds. *Not a blocker — brief should say so explicitly so Codex doesn't over-scope.*

---

## NIT

### N1. "embedding-proximity layer using `all-MiniLM-L6-v2` per `memory/embedding_contract.py:177`"

The cited line is in the manifest file and does not implement a callable encoder. See B1. *Pure framing on a load-bearing claim; B1 carries the load.*

### N2. Class K reserved-until-G11

R#14 correctly handles this. Good. *Pure framing.*

---

## Closing Synthesis

The dispatcher will work under real load **if** four amendments land: (a) introduce a single-source `MiniLMEncoder` module that both Chroma and the dispatcher consume, otherwise the Section-4 reuse claim is mechanically impossible and we'll silently double-load the model; (b) add a Layer-0 latency budget invariant (≤50ms warm) and a cached `InventorySummary` anchor so 10-substrate inventory probes don't compound into 200ms per reply; (c) make Q9 a decision in v1 — recommend full replacement of `_should_run_jarvis_loop`, with JARVIS regexes folded into Layer-0 evidence rather than a downstream gate, because half-replacement reproduces the Reddit-screenshot bug; (d) state Layer-1 fan-out parallelism explicitly, with per-branch timeout and partial-recall discipline.

The brief underestimates two costs: the embedding-encoder seam (currently nonexistent as a free-standing callable — Chroma encapsulates it), and the cumulative per-reply latency of 10-source inventory probing. It overestimates the safety of leaving JARVIS in place "wrapped" behind Layer 0 — the regex misroute that the brief was written *to fix* will recur if `_should_run_jarvis_loop` remains a gate. The composition-spec layering, closed vocabularies, and invariants D1-D10 are otherwise a clean structural advance; the doctor analogy is genuinely teachable and the producer-causality boundary (D6, D9) holds. Recommend RATIFY-WITH-AMENDMENTS — none of the issues unseat the design; all are mechanism-specification gaps Codex panel should resolve in pass-1, not council pass-2.
