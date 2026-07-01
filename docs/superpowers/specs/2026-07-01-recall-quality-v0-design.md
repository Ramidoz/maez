# Recall Quality v0 — Relevance Floor + Promotion-Score Wiring Design

**Date:** 2026-07-01. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner runs the shadow-data review + the enforce decision. **Status:** DESIGN for review. **Scope:** one spec, two coupled sub-slices (A: graduate the recall relevance floor shadow→enforce; B: give `memory_scoring.promotion_score()` authority in the recall reranker), measured together behind a hard shadow gate. **Target: memory digestion + recall quality. NOT self-concept.**

## The one-line intent

> Make recall and promotion **less noisy** — reduce the diary-recitation (recall surfacing Maez's own low-relevance self-summaries for casual turns) — **without** promoting more self-reflection just because it is frequently recalled, and **without** touching self-authoring (dream→soul, drive-curiosity, ledger).

## Task 0 — verified call-site map (read-only, done)

The whole slice lives in **`memory/memory_manager.py`** (the recall reranker), which is structurally separate from `dream_state`/soul. Verified 2026-07-01:

| Piece | Where | Current state |
| --- | --- | --- |
| Relevance floor — shadow flag | `memory/memory_manager.py:646` `recall_floor_shadow_enabled()` → `MAEZ_RECALL_FLOOR_SHADOW` | **=1, ON** (computing + logging, not dropping) |
| Relevance floor — enforce flag | `:650` `recall_floor_enabled()` → `MAEZ_RECALL_FLOOR_ENABLED` | **unset → OFF** |
| Floor filter | `:654` `_passes_recall_floor(mem, floor)`, `:667` `_apply_recall_floor` (drops only if `recall_floor_enabled()`) | honest rule: missing/invalid distance **keeps** the candidate (don't silently drop unknown-distance) |
| Floor apply site + shadow log | `:2432` `if recall_floor_shadow_enabled() or recall_floor_enabled():` → `_apply_recall_floor` on `raw`/`daily` | **What actually logs:** `recall_floor_shadow floor=… raw_would_drop=…` (`:2439`) + `living_recall_candidate … base_distance=…` (`:2103`). `_recall_floor_teacher_signal` (`:679`) exists but is **tests-only, never called** — so there is **no compound teacher-signal data**; the review must be built from the would-drop counts + distances (or an offline replay). *(Codex cross-lane correction.)* |
| `promotion_score()` | `core/memory/memory_scoring.py:348` (6-factor: freq / relevance / diversity / recency / consolidation / concept-overlap) | **computed observationally, ZERO authority** — in TWO sites: the reranker shadow (`memory_manager.py:2077-2098`) and the daily-consolidation feedback loop (`:1456`, logged as `consolidation_scores`). Fed by `record_recall`. It is computed but decides nothing. |
| `mark_consolidated()` | `memory_scoring.py:320` | **IS called** — `memory_manager.py:1456`, daily consolidation bookkeeping (marks the raw memories that fed a consolidation). **NOT** `dream_state`/soul → covenant intact, but the map must say so precisely. `score_recall()` remains uncalled. *(Codex cross-lane correction.)* |
| `dream_state` "consolidation" | `core/evolution/dream_state.py` (reflection synthesis + `consolidation_telemetry`) | a **different** consolidation — soul-note proposals, owner-gated by `/apply_dream`; **never calls `promotion_score`/`mark_consolidated`**. Out of scope, stays untouched. |
| Diary-recitation mechanism | `core/memory/lived_recall.py:737-750, 877` | reflection episodes get a keyword-overlap **bonus** on meta-queries ("reflect/habits/…"); the risk is that bonus + high recall-frequency leaking onto casual turns |

**Confirmed failure mode (from the substrate pressure-test, this session):** 62% of episodes are self-reflection; recall surfaces at median relevance 0.44 (only 1/693 ≥ 0.7); the most-recalled memories (225×) are self-summaries. So the floor and the scorer must *reduce* the reflection dominance, not harden it.

## Architecture — two coupled sub-slices, one consumer

Both operate on the recall candidate set inside `memory_manager.py`, in this order per recall:
1. Candidates scored by base relevance (existing).
2. **Part A — floor:** drop candidates below the relevance floor (when enforce on).
3. **Part B — promotion_score:** weight the survivors' ranking (when granted authority), with the anti-circular guard.
4. Existing MMR diversity rerank (`memory/mmr.py`, λ=0.7) unchanged.

They are coupled by design: promoting harder (B) without filtering better (A) would amplify diary-recitation; so they graduate **together**, measured together.

## Part A — Relevance floor: shadow → enforce

- **The graduation is a flag flip** (`MAEZ_RECALL_FLOOR_ENABLED=1`) gated on a **shadow-data review**, not a blind switch. **PLAN TASK 1 (blocking, per Codex): produce the review artifact — the compound teacher-signal is NOT logged today.** Build the review from what *is* logged (`recall_floor_shadow` would-drop counts + `living_recall_candidate` base_distances), or wire a real teacher-signal log, or run an offline replay over recent recalls. Then confirm what enforce *would* drop is **noise, not signal** — dropped candidates are low-relevance reflections / weakly-related memories, not on-point relational context. No enforce flip until this artifact exists and reads clean.
- **Keep the honest rule intact:** missing/invalid distance keeps the candidate (`_passes_recall_floor` current behavior). Enforce must not start silently dropping unknown-distance memory.
- **Narrow + measured fallback:** if enforce empties a section that shadow said would keep signal, or if a per-mode section floor (`lived_recall.py` `_SECTION_FLOORS_BY_MODE`) would be violated, fall back to keeping the best-N rather than returning empty. The floor **filters noise; it never starves a real answer.**
- **The floor value is a pinned constant** (base-distance threshold), justified from the shadow distribution (median 0.44 today), not a magic number — the spec/plan names it after reading the shadow data.

## Part B — promotion_score authority: shadow-compare → weight, with the anti-circular guard

- **It's already computed observationally** in two sites (reranker `:2091`, consolidation feedback `:1456`) with **zero authority** — so Part B is a *graduation of an existing computation*, not wiring an orphan. **v0 grants authority only to the RERANKER use** (recall ordering, `:2091`); the consolidation-feedback use (`:1456`) stays observational (giving the score authority over *what gets consolidated* is the future consolidation slice, out of scope). Keep a **shadow-compare stage first** (log promotion_score's ranking alongside the live ranking, no authority) so we can see whether it *improves* or *degrades* order before it carries weight.
- **FIELD-AVAILABILITY REQUIREMENT (blocking, per Codex — else the damp silently no-ops):** `source_kind`/`memory_voice` appear nowhere in `memory_manager.py` today, so the reranker candidates likely do **not** carry them. The plan must **first prove** those fields are present on the actual recall candidates at the damp site, or **define a tested derivation** (e.g. look up `source_kind` from the episode store by candidate `id`). A test must assert the damp actually fires on a reflection candidate in the real candidate shape — a damp that can't see `source_kind` is worse than none (it looks safe while doing nothing).
- **THE load-bearing guardrail (anti-circular self-reflection promotion):** `promotion_score`'s frequency factor rewards recall_count, and the self-summaries are recalled 225×. So an ungated scorer promotes reflection *because it recites reflection*. Part B **must dampen the frequency/promotion weight for `source_kind == "reflection"`** (and any self-authored `memory_voice == "maez_self"`), so a reflection cannot earn promotion from its own recall loop. Relational/lived episodes (m1 promotion, bonded dialogue) are not damped. This is "don't promote more self-reflection just because it is available," in code. **Implement it as a `type_weight`** (Mem0's proven shape — see Borrowed patterns): the damp is a low per-`source_kind` weight, not a special-case hack, and it composes cleanly with the existing 6 factors. Explicitly **do not** add a recency/access boost that would reward the over-recalled self-summaries.
- **Where the score is allowed to carry weight:** only the recall reranker's ordering of the *surviving* candidate set (post-floor). It does **not** get authority over: what gets written, what gets `mark_consolidated`, dream→soul, or any promotion into durable selfhood. Its authority is bounded to "which already-recalled candidates rank higher for this turn."

## Borrowed patterns (verified against the 2026 OSS landscape)

Verified 2026-07-01 against Mem0, Letta/MemGPT, LangMem, Hermes Agent (Nous Research). The landscape splits **agent-driven** memory (the *model* manages its own memory via tools — Hermes's "gauge," Letta's paging) vs **background/substrate-driven** (LangMem, Mem0). **Maez is substrate-driven — validated as the covenant-aligned camp.** Borrow shapes, not the constraints they were built for:

- **BORROW (into Part B): Mem0's `relevance × recency × type_weight` scoring.** Mem0 weights semantic (digested) above episodic (raw) via a per-type weight. This is the *principled* form of our anti-circular damp: `source_kind`/`memory_voice` becomes a **type_weight** — reflection/self-authored gets a low one, relational/lived a normal one. Map `memory_scoring`'s existing 6 factors onto this shape rather than inventing a bespoke damp.
- **REJECT (the borrow-rule crux): Mem0's recency/access boost (recently-accessed → up to 1.5×).** It serves general recall but would *amplify* Maez's exact failure — the most-accessed items are the 225×-recalled self-summaries, so an access-boost promotes the diary harder. **Maez inverts it:** over-recall of self-reflection *damps*, never boosts. The recency term may still favor genuinely-recent *relational* material; it must not reward a reflection for being frequently recited.
- **REJECT: agent-driven memory management (Hermes/Letta — the brain edits its own durable memory).** Maez keeps the brain narrow, the substrate owning digestion, and self-shaping owner-gated. The score never lets the brain rewrite its own memory.
- **FUTURE (out of v0 scope): Hermes's capacity-pressure-triggered consolidation** (consolidate under a fullness gauge, not always-on volume) + **Mem0's dedup/merge**. These are for a later *consolidation* redesign, when promotion/`mark_consolidated` gets real authority — deliberately walled off from this recall-reranking slice.

## Hard shadow gate (the discipline)

Neither part flips to authority until the shadow review passes **both**:
1. **Floor:** shadow log shows enforce drops low-relevance noise, not on-point signal; no section starves.
2. **Scorer:** shadow-compare shows promotion_score (with the anti-circular damp) **reduces** the reflection share of top-ranked recall, not increases it — measured against the current path on the same turns.

If either shows the change would harden diary-recitation or drop signal, we hold at shadow and adjust. Enforce is earned by data, not assumed.

## Out of scope

- Anything self-authoring or self-shaping: `dream_state`→soul, `/apply_dream`, `drive_driven_curiosity`, the birth-gated ledger, soul-writing.
- `mark_consolidated`/`memory_scoring` promotion into durable memory-*selfhood* (the score ranks recall order only; it does not decide what becomes consolidated identity).
- Voice, brain-side face learning, B2 daemon.
- Retuning the `lived_recall.py` reflection meta-query bonus itself (the floor filters its leakage; re-tuning the bonus is a possible follow-up, not this slice).

## Witnesses

**Shadow-data review (before any enforce):**
1. Floor: over N recent recalls, the set the floor *would* drop is dominated by reflections / low-relevance, not on-point relational context (owner + Claude read a sample).
2. Scorer: promotion_score's shadow ranking, with the anti-circular damp, lowers the reflection share of the top-K vs the live path on the same turns.

**Host/unit:**
- `_passes_recall_floor` honest-keep on missing distance; `_apply_recall_floor` no-ops when enforce off, filters when on; fallback keeps best-N rather than emptying a section.
- promotion_score damp: two identical-except-`source_kind` candidates (reflection vs bonded) with identical high recall_count → the reflection ranks **no higher** than the bonded one (the frequency loop is broken for reflection).
- Structural: the score's authority is confined to reranking; a guard asserts `memory_scoring` promotion functions are not imported by `dream_state`/soul paths.

**Live (owner, after enforce):** on casual turns, recall stops surfacing self-summaries; on genuine self/reflection queries (meta-query), reflections still surface; no real relational context is lost.

## Covenant compliance

- Faculty, not self: improves *how well* Maez recalls, never *who it is* ([[feedback_hardcode_organs_not_opinions]]). The consumer is the recall reranker, structurally separated from dream→soul.
- Honest emptiness: the floor filters noise but never starves a real answer or silently drops unknown-distance memory ([[feedback_honest_ingestion_immune_system]]).
- Anti-diary-recitation without anti-self: reflections are damped from *self-promoting via their own recall loop*, not deleted or deweighted everywhere ([[feedback_forgetting_is_deweighting_not_deletion]] — they stay recallable on real self-queries).
- Earned by data: shadow gate before authority ([[feedback_verify_before_you_encode]], [[feedback_visible_substrate_state_not_chain_of_thought]]).

## Predicted effect

After Recall Quality v0: on ordinary turns the recall reranker drops low-relevance self-summaries (floor enforce) and no longer lets a reflection promote itself by being frequently recited (anti-circular damp), so the substrate hands the brain sharper, less self-referential context — measurably lowering the reflection share of top-ranked recall — while genuine self/reflection queries still surface reflections, no real answer is starved, and nothing about Maez's self-authoring, soul, or durable identity is touched.

## Spec Self-Review

**Placeholder scan:** the floor constant and the damp weight are named "to be pinned from shadow data in the plan" — deliberately, because the honest value comes from reading the shadow distribution, not a guess. Not vague TODOs.
**Consistency:** single consumer (`memory_manager.py` reranker); both parts graduate together behind one shadow gate; out-of-scope explicitly walls off dream→soul and durable-selfhood promotion.
**Ambiguity:** "where the score carries weight" is pinned (recall reranking of the surviving set only), per the owner's explicit requirement.
