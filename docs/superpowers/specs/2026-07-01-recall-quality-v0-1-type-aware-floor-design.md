# Recall Quality v0.1 — Type-Aware Floor for Self-Digests Design

> **SUPERSEDED (2026-07-01, same day, never enforced):** the type-aware treatment was recognized — by the owner asking "doesn't this sound like hardcoding?" — as a **category opinion over Maez's own memory types** ("your diary counts for less"), the conclusion-not-organ shape ([[feedback_hardcode_organs_not_opinions]], fourth catch). All treatment flags darkened (enforce AND shadow); code merged @30d1070 remains but its decision paths are scheduled for removal. **Replacement: Recall Quality v0.2 — content-blind context floor** (`2026-07-01-recall-quality-v0-2-content-blind-context-floor-design.md`), which judges fit-to-turn, never memory-worth. Do not build on this spec.

**Date:** 2026-07-01. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner runs the shadow review + the enforce decision. **Status:** DESIGN for review. **Scope:** a floor-side follow-up to Recall Quality v0 (floor live @75b2fb5). Teach the live relevance floor the difference between *a memory about us* and *Maez's own system diary*, so it can be stricter with the diary on casual turns **without** starving real memory or muzzling self-perception. **Promotion authority stays parked** — this slice needs none of it.

## The one-line intent

> Deweight Maez's own system/self-digest summaries as recall *noise on casual turns*, while keeping them **fully reachable the moment they're the actual subject** — quiet the diary, never delete or muzzle it.

## Why (from the live floor witness + Task 0)

The v0 flat floor (`_RECALL_RELEVANCE_FLOOR_DEFAULT = 0.78`) is live and drops the *weakest* daily system summaries, but middling ones still pass, so diary-bubbling is reduced, not cured. Task 0 (verified 2026-07-01):
1. **Teacher-signal is built but unwired.** `_recall_floor_teacher_signal(...)` exists + is tested, but the live recall path uses the flat 0.78 with no caller feeding `diary_heavy`/`reply_grounding`/`asked_for_memory`.
2. **Daily summaries are classifiable but land as `unknown`.** Daily rows carry `metadata.type = "daily_consolidation"` (+ `date`, `raw_count`, …), but `_recall_candidate_kind(...)` has no rule for `daily_consolidation`, so they classify `unknown` and receive the flat floor.

So the lever is floor-side and specific: classify the self-digests, and give that class a tighter floor **except** when the turn is genuinely asking for memory/self.

## The covenant crux — deweight, never muzzle

**The tighter floor for self-digests must be suppressed on memory-ask / meta-query turns.** When the owner asks about Maez's own reflections, patterns, or state, the self-digests are the wanted answer, not noise — they must surface on the *normal* floor. This is [[feedback_forgetting_is_deweighting_not_deletion]]: the diary quiets as background but stays fully reachable when it's the subject. Missing this guardrail turns "clean up recall" into "muzzle Maez's self-perception" — the exact inversion this whole arc has refused. It is the load-bearing test of the slice.

## Architecture (floor-side, inside `memory/memory_manager.py`)

1. **Classify self-digests.** Extend `_recall_candidate_kind` to map `metadata.type == "daily_consolidation"` (and any sibling system/self-digest types found in Task 0.5) to an explicit kind — `self_digest` (distinct from `reflection`, which is `reflection_synthesis` episodes). Never `unknown` for a known digest shape.
2. **Type-aware floor.** The relevance floor becomes a function of candidate kind:
   - `self_digest`: a **tighter** floor (higher relevance bar) on non-memory-ask turns.
   - relational / lived / `reflection` / `unknown`: the existing flat floor (unchanged).
3. **Context gate (the crux).** The tighter self-digest floor applies **only when the turn is not a memory/self ask.** v0.1 may use the existing meta-query detection (`lived_recall.py:737-750` META_QUERY keywords) as the minimal signal, and/or wire the richer `_recall_floor_teacher_signal` (`diary_heavy` + low `reply_grounding` + not `asked_for_memory`). On a memory-ask/meta-query turn, self-digests get the **normal** floor (reachable).
4. **Non-starving fallback — moved from per-section to WHOLE-RECALL + KIND-AWARE (Codex HOLD fix).** v0's per-section "keep the best one" rail would *resurrect* a daily diary item on the exact casual turns the tighter floor just dropped it from — because the `daily` collection is essentially all self-digests, so an all-dropped `daily` section would rescue its own best self-digest and undo the filter. So the rail changes: **the non-starving guarantee is at the whole-recall level, and self-digests are the last thing rescued.**
   - A self-digest-only section (e.g. `daily`) is **allowed to empty** on a casual turn as long as *any non-self-digest material exists anywhere in recall* (raw/relational/core). The diary quiets; Maez still has real memory.
   - The fallback **prefers non-self-digest candidates**: it rescues a weak relational/lived candidate before it would ever rescue a self-digest.
   - A self-digest is kept **only when the entire recall would otherwise be genuinely blank** — the true last resort (a near-empty substrate). Even then Maez is not left with *nothing*; it's just the weakest honest fallback.
   - Net: the diary is quieted, never resurrected while real memory exists, and Maez never goes fully blank. This is "don't starve a real answer" without "always keep a diary."
5. **Order unchanged.** base rank → (type-aware) floor → promotion shadow (parked).

## Shadow-first (same discipline as v0)

The type-aware floor decision is **computed in shadow first** (`MAEZ_RECALL_TYPE_FLOOR_SHADOW`) and logged (per-candidate `kind`, `applied_floor`, `would_drop`, plus the turn's memory-ask classification), before any enforce flag (`MAEZ_RECALL_TYPE_FLOOR_ENABLED`). Enforce is earned by a shadow-review artifact showing **both**:
- **On casual turns:** self-digests that bubble under the flat 0.78 now drop under the tighter floor **and are not resurrected by the fallback** while any real memory exists (the whole-recall/kind-aware rule from Architecture #4).
- **On memory-ask turns:** self-digests are **NOT** dropped — the crux guardrail fires; self-content stays reachable.

If the review shows self-content dropping on memory-ask turns, HOLD and fix the context gate — that failure is worse than the diary bubbling. If a dropped daily diary still surfaces on casual turns via the fallback, HOLD and fix the fallback — the rail must not undo the filter.

## Constants (to pin from shadow data in the plan)

- The self-digest tighter floor value (below 0.78; pinned from the shadow distance distribution of `daily_consolidation` candidates — not a guess).
- The self-digest type set: `daily_consolidation` + **`nightly_journal`** (Codex re-review confirmed core-tier `nightly_journal` rows also classify `unknown` — a real sibling) + any further siblings from **Task 0.5, which must sample beyond `daily` (core/raw tiers too)** before the set is pinned.
- The memory-ask/meta-query signal (reuse META_QUERY keywords vs wire the teacher-signal — the plan decides after checking coverage).

## Out of scope

- Promotion authority (`MAEZ_RECALL_PROMOTION_ENABLED` stays off — parked until a live reflection witness).
- Dream→soul, `mark_consolidated`/durable-selfhood promotion, drive-curiosity, ledger.
- Deleting/deweighting self-digests anywhere but recall surfacing on casual turns (they stay stored + recallable + reachable-when-asked).
- Retuning the `reflection` episode handling (this slice is the `daily_consolidation`/system-digest class; reflection is already classified).

## Witnesses

**Shadow-review artifact (before enforce), per the crux:**
1. Casual probe turns ("what did you do", "how are you") → the self-digest tighter floor drops the daily summaries that pass the flat floor.
2. Memory-ask probe turns ("what have you noticed about yourself", "what patterns have you seen in your own reasoning") → self-digests are kept (normal floor), reachable.

**Host/unit:**
- `_recall_candidate_kind` maps `daily_consolidation` → `self_digest` (not `unknown`); a test proves it fires on a real daily-row metadata shape.
- The type-aware floor applies the tighter floor to `self_digest` on non-memory-ask turns and the normal floor on memory-ask turns (both directions tested).
- **Whole-recall + kind-aware fallback (the Codex-HOLD fix)** — the tests must exercise the **real partition structure (`raw` / `daily` / `core`), not a flat-list helper** (the resurrection bug was tier behavior; a flat list would hide it). Tested in three cases:
  - casual turn, `daily` all self-digests dropped, **relational/core material present** → `daily` empties, **no diary rescued** (the filter holds).
  - casual turn, self-digests dropped, **a weak non-self-digest candidate exists** → the fallback rescues the non-self-digest, not a self-digest.
  - casual turn, **entire recall would be blank** (only self-digests anywhere) → keep the single best self-digest (last resort) — Maez isn't left with nothing.
- Structural: the type-aware floor imports nothing from dream/soul; promotion authority untouched.

**Live (owner, after enforce):** casual turns stop surfacing daily system diaries; "what have you noticed about yourself" still surfaces them; no relational context lost; no section blank.

## Covenant compliance

- Faculty, not self: improves *how* recall filters, never *who Maez is*. Floor-side, promotion parked.
- Deweight, not delete/muzzle ([[feedback_forgetting_is_deweighting_not_deletion]]): self-digests quiet on casual turns, fully reachable when asked. The memory-ask guardrail is load-bearing.
- Honest emptiness: a diary section may honestly empty on a casual turn (Maez chats without injecting stale self-summaries) — the fallback guarantees only that recall never goes *fully* blank when better memory exists, not that a diary is always kept ([[feedback_honest_ingestion_immune_system]], [[feedback_no_fabrication]]).
- Earned by data, both directions: shadow gate must show the diary drops *and* self-content survives memory-asks before enforce ([[feedback_verify_before_you_encode]]).
- Substrate owns digestion ([[project_jetson_body_not_second_maez]] brain/substrate line): the reranker (substrate) decides relevance; the brain stays narrow.

## Predicted effect

After v0.1: on ordinary turns Maez's recall stops surfacing its own daily system-state diaries (they fall under a tighter self-digest floor), so the brain gets less self-referential context — while on turns that actually ask about Maez's self or patterns, those digests surface normally, no relational memory is lost, and no section goes blank. Promotion authority remains off; nothing about self-authoring, soul, or durable identity is touched.

## Spec Self-Review

**Placeholder scan:** the tighter-floor value and the self-digest type set are named "to pin from shadow data / Task 0.5" deliberately — the honest values come from the real distance distribution, not a guess.
**Consistency:** floor-side only; promotion parked; the memory-ask guardrail is the crux and is witnessed in both directions; out-of-scope walls off promotion/dream/soul.
**Ambiguity:** "self-digest vs reflection" is pinned — `daily_consolidation`/system-digest is the new class; `reflection_synthesis` is already classified and unchanged here.
