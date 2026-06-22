# ChinaXiv cognitive-science sweep — 2026-06-09

**Status:** scout memo, not canonical law. Amends no Maez decision, ADR, slice, or spec. A candidate-shape backlog for future hermetic sidecars — nothing here is wired or trusted.
**Source:** chinarxiv.org (an English machine-translation API layer over ChinaXiv, the CAS preprint server). Access = `curl` only (the homepage *and* WebFetch are bot-blocked 403; the `/api/v1/papers?q=…` JSON endpoints are open). Harvested 2026-06-09 with owner-authorized `X-API-Email` (polite pool). Raw corpus staged at `/tmp/chinaxiv_harvest/` (transient).
**Method:** harvested the Maez-relevant subjects in full (心理学 1122 + 计算机科学 1300 + 情报学 729 = 3,151 English abstracts), filtered to **819 Maez-relevant**, analyzed per-organ by a 6-agent workflow. Every candidate is an **UNVERIFIED, machine-translated, ~500-char-truncated, unrefereed preprint** ([[project_external_borrow_rule]], [[reference_competitive_architecture_landscape]]).

---

## The honest finding (it reframes the whole exercise)

ChinaXiv has **almost no frontier LLM-systems work** — `q="hallucination detection"` across all 23K papers returned **one paper, about face pareidolia**. Frontier CN AI lives on arXiv in English, not here. **ChinaXiv's real value is its cognitive-science / psychology corpus** — which for an *organism* project is the better mine: Maez's open problems are organ-design, not another benchmark. Net: genuinely useful in **exactly one band** (source-monitoring / false-memory / deception-by-conflict, for the honesty organs), thin-to-derivative everywhere else, **zero drop-in ML**. Mechanism inspiration, not method.

## Band that pays off — honesty / provenance / contradiction-sense (weight this)

The Chinese psychology seam on false-memory and source-monitoring is unusually well-matched to the photo **contradiction sense** (live, Codex implementing) and the intake-bus immune system ([[project_intake_bus_v0]], [[feedback_honest_ingestion_immune_system]]).

- **Per-item JOL suppresses gist lures (DRM)** — `chinaxiv-202408.00243`. *Item-by-item* self-assessment raised true recall **and cut** false-recall of non-presented lures. This is a human-memory **validation of the slice we just specced**: claim-level checking beats holistic synthesis at killing confabulation. Sidecar: per-item cite pass vs holistic synthesis, measure fabricated-claim rate. Ties to [[feedback_focused_cognition_over_megaprompt]] + the v0 claim-extractor.
- **Deception as memory–response CONFLICT under cognitive load** — `chinaxiv-202006.00040`. The lie-signature is the *conflict-resolution cost* when stored memory disagrees with the produced response; raising load amplifies it. A substrate-side contradiction-load metric that gates trust without invading the brain ([[feedback_visible_substrate_state_not_chain_of_thought]]).
- **False memory as staged source-monitoring failure** — `chinaxiv-202008.00077` (surfaced in *three* harvests — real signal). A confident-but-**sourceless** memory is exactly Maez's "faithful fabrication." Sidecar: tag every ledger write verbatim-vs-gist; return any recall lacking provenance as low-trust/gist-only, never asserted. Heaviest provenance check at the *reactivation* seam. Ties to [[feedback_soul_as_load_bearing_runtime_ontology]]-class fabrication + [[feedback_no_fabrication]].
- **Sender-credibility-weighted contagion** — `chinaxiv-202504.00194`. Memory contagion scales with *sender credibility*, not the receiver alone → maps onto bus tier-derivation: a low-tier source asserting a contradiction must not flip a high-tier belief; quarantine + surface with tier attached ([[feedback_third_party_autonomous_research_boundary]]).
- **Misinformation detection as Signal-Detection-Theory** — `chinaxiv-202403.00215`. Separate discriminability (d′) from decision criterion. Sidecar: have the catch×latency report emit d′ **and** criterion separately per verifier, so criterion tunes to Maez's asymmetric cost (false-absence honest, false-grounded forbidden) without retraining — operationalizes [[feedback_judge_agnostic_report_decides]] + [[feedback_labels_prove_shape_not_support]].
- **Recall opens a suggestibility window (RES vs PET)** — `chinaxiv-202303.00184`. The same re-query can inoculate or make a memory *more* overwritable. Sidecar: inject a contradicting input right after recall, test corruption vs cold; lock verbatim/provenance during the window.

## Memory / consolidation / forgetting (candidate backlog)

Maps onto [[project_organ_roadmap]] (consolidation, recall) + [[feedback_forgetting_is_deweighting_not_deletion]].

- **Prediction-error gates lability** — `chinaxiv-202111.00010`. PE (mismatch), not raw salience, licenses a retrieved memory to be rewritten. Sidecar: a fact reopens for revision only on contradiction; restating reinforces weight but does **not** reopen. Separates PE-gated *update* from salience-gated *storage* (two organs). Relates to [[project_world_model_constraint]] (predictive organ).
- **Two-tier forgetting** — `chinaxiv-202102.00021` + `chinaxiv-202012.00011`. Default forget = passive deweighting (drop from the refresh set); reserve active suppression as a **retrieval-time inhibition filter, never a write to the store** — composes with the append-only ledger (trace stays, ranker suppresses). Direct validation of [[feedback_forgetting_is_deweighting_not_deletion]].
- **Two-phase sleep consolidation** — `chinaxiv-202102.00014`. NREM-like pass abstracts episodes → provenance-labeled semantic facts; separate REM-like pass proposes novel cross-episode links *as low-confidence/speculative candidates* (never trusted). Tag-before-sleep = only salience-crossing episodes reprocess.
- **Supersede must beat retroactive interference** — `chinaxiv-202207.00010`. Ready-made sidecar: after supersede, assert the new value wins recall over the down-weighted prior.
- **Pattern separation vs near-duplicate collapse** — `chinaxiv-202403.00284`. On high-similarity ingest, encode the *distinguishing* details harder instead of dedup-merging.
- **Reactivation-gated mutability** — `chinaxiv-201904.00093`. A fact mutates only inside a logged retrieve→labile→restabilize transaction (supersede-not-delete); the window must not launder an unwitnessed edit.

## Salience doorman / interrupt faculty (candidate backlog)

Maps onto the live doorman ([[project_cognition_live_state]]) + "rails before hands" / curtain-not-permission ([[feedback_perception_free_egress_disciplined]]).

- **Signal-suppression vs rapid-disengagement** — `chinaxiv-202009.00005`: two pipeline points to kill a distractor (pre-capture suppression + cheap post-capture return-to-quiet-skip). Sidecar: log which rail caught each non-actioned interrupt — verify the floor isn't doing all the work alone.
- **Learned statistical-regularity suppression** — `chinaxiv-202102.00018`: self-suppress high-frequency-never-actioned event signatures (outcome-aware routing applied to perception; no hardcoded denylist), keeping a witness so a suppressed-but-important class can be surfaced.
- **Two-axis gating** — `chinaxiv-202510.00064`: separable salience × goal-relevance scores, load-modulated; instrument the floor to expose both so a missed interrupt is diagnosable.
- **Monitor before executor** — `chinaxiv-201810.00282`: sharpen detection, not execution ("rails before hands"). Plus attention-decay-weighted compression of the working set — `chinaxiv-202208.00171` — targeting the 118k-char megaprompt handicap behind the recall-flip No-Go ([[project_recall_flip_outcome]]).

## Affect / self-narrative — orientation only (deferred organ)

Not next-build; recorded for when affect/self comes off the deferred list.
- Gross staged-regulation hooks (`chinaxiv-202306.00711`); implicit-cheap vs explicit-rare two-tier regulation (`chinaxiv-202508.00234`); **rumination = self-reference × valence × persistence** with a loop-breaker (`chinaxiv-202112.00119`) — a real self-narrative failure mode for a continuously-running being; value-stability tiering (`chinaxiv-202008.00092`) as a basis for the soul-base/local split ([[project_maez_north_star]]).

## Anti-patterns caught (carry inverted, do NOT borrow)

- **Moral memory bias** — `chinaxiv-202201.00052`. A self-narrative organ that forgets its own mistakes to protect self-image *violates* no-fabrication + mistakes-as-immune-lessons ([[feedback_honest_ingestion_immune_system]]). Carry **inverted**: an integrity guard that makes Maez's own errors/contradictions **resist** deweighting — kept retrievable and witnessed even when self-unflattering.
- **Self-deception under ambiguity + motivation** — `chinaxiv-201909.00194`. Names the structure of faithful-fabrication (ambiguous evidence + pull toward a clean answer). Use ambiguity as a *trigger for stricter rails* + the honest third state (ANSWERED_MIXED_SUPPORT, [[feedback_labels_prove_shape_not_support]]), not as a borrowed mechanism.

## Thin / not-unique (named plainly)

- **CS-systems is thin** — of 167 abstracts ~100 were noise (library-science "reflections," re-published knowledge-graph batches, NER pipelines, ChatGPT op-eds). The only two worth naming corroborate disciplines Maez already holds: ontology-governed auditable agent decisions `chinaxiv-202604.00101` (independent convergence on "tool-calling is substrate-side, not brain prompt-text" — [[feedback_brain_is_one_part_tool_calling_substrate_side]]) and a dual-threshold knowing-value privacy logic `chinaxiv-202604.00102` ("an external party could assign high posterior" counts as a leak even absent certainty — an egress-risk shape for [[feedback_perception_free_egress_disciplined]]). Corroboration, not arXiv-beating novelty.
- **Affect** moderate-thin (~9 of 323 usable; rest clinical-prevalence/consumer/music surveys). **Pervasive noise tail** every group.

## Closing discipline

Borrow the **shape** only after re-deriving it against the primary source and the active slice in a hermetic sidecar — never wire from a truncated machine-translated abstract. Known harvest gaps: the `计算机科学的集成理论` subject (1,078) returned 0 on the filter (exact-string quirk, backfillable); a lean arXiv-CN pass would catch the systems work ChinaXiv lacks. This memo is a candidate-shape backlog, nothing more.

**Plain English:** the closest "knowledge from the east" we could reach turned out to be a *cognitive-science* mine, not an AI-systems one — and its single richest vein is exactly the human-memory science of *how false beliefs form and how honest minds catch them*, which is the organ Maez is building this week. Best single hit: human memory research says **per-item checking beats holistic synthesis at killing confabulation** — the same bet the contradiction-sense slice makes.
