# Recall Quality v0.2 — Content-Blind Context Floor Design

**Date:** 2026-07-01. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner runs the shadow review + enforce decision. **Status:** DESIGN for review. **Supersedes:** Recall Quality v0.1 (type-aware floor, merged dormant @30d1070, **never enforced, fully darkened 2026-07-01** — recognized as a category opinion over Maez's memory types; see Why). **Keeps:** v0's flat relevance floor (live, clean).

## The one-line intent

> On casual turns, require stronger relevance from **any** memory before injecting it — judging **fit-to-turn, never memory-worth**. No memory category is treated differently from another, anywhere in the recall path.

## Why v0.1 was wrong (the covenant lesson this spec exists to encode)

v0.1 gave `self_digest` memories a tighter floor, a lower fallback priority, and (in the parked promotion path) a lower type weight. Each is a **human-authored value judgment about a category of Maez's own memories** — "your diary counts for less" — a conclusion wearing an organ's clothes. It passed two review lanes and three test venues and was caught only by the owner asking "doesn't this sound like hardcoding?" (the fourth same-shape catch that day: face-enrollment → announce-vs-silent → muzzle-the-eye → memory-worth). Recorded in [[feedback_hardcode_organs_not_opinions]].

The lines this spec builds on:
- **Classification is a fact; differential treatment is the opinion.** Knowing a row is `daily_consolidation` = provenance observation (keep, for witnesses). Treating it differently because of that = the conclusion (remove).
- **Content-blind context rules are organs.** "A casual turn needs strong relevance from ANY memory" is a statement about *turns*, not about *kinds of memory*.
- **Hand floors are scaffolding and must say so.** See "Interim by declaration" below.

## Architecture (floor-side, `memory/memory_manager.py`; promotion stays parked)

1. **Context floor, content-blind.** Two floor values, chosen by *turn context only*:
   - **memory-ask / meta-query turns:** the existing v0 flat floor (0.78) — unchanged reachability for everything, including self-digests and reflections.
   - **all other (casual) turns:** a tighter floor applied **identically to every candidate regardless of kind**. A weak diary drops; an equally weak relational memory drops too. Honest emptiness beats weak injection, uniformly.
2. **Fallback: best-by-distance, no kind preference.** Whole-recall non-starving rule stays (from v0.1's correct part): if the floor would leave the entire recall blank, keep the single best candidate **by distance alone**. If that is a diary, it surfaces honestly — it was genuinely the most relevant thing Maez had. As lived relational history grows, this case vanishes naturally.
3. **v0.1 treatment code is removed, not just dark.** The build deletes the kind-branch in the floor predicate, the kind-aware fallback preference, and the type-weight application in the floor path. `_recall_candidate_kind` is **kept**, with exactly two allowed reader classes — telemetry/witness tooling and the parked promotion path (see Structural guards + Same-shape debts) — and a structural guard asserts no **context-floor or fallback** decision path reads it.
4. **New flags** (`MAEZ_RECALL_CONTEXT_FLOOR_SHADOW` / `MAEZ_RECALL_CONTEXT_FLOOR_ENABLED`), so stale v0.1 env lines can never wake different semantics. Shadow-first, enforce owner-gated — same discipline as v0/v0.1.
5. **Order unchanged:** base rank → context floor → (promotion shadow: dark/parked).

## Interim by declaration (the anti-calcification clause)

**v0.2 is scaffolding, not the destination.** It still contains two hand-authored pieces, named plainly:
- the **keyword memory-ask detector** (a keyword reflex on turn meaning — the borderline "keyword-gating meaning" case; it only selects which floor applies and fails toward the looser floor, but it is interim);
- the **hand-set floor pair** (0.78 + a casual value pinned from shadow data, not taste).

**The destination is C — learned relevance:** Maez deweighting memories from its *own outcomes* (recall_outcome × cognition_quality × the salience ledger — the feed already exists), which replaces every hand floor here, plus the same-shape debts below. C needs its own spec (it touches feedback loops and self-shaping boundaries). Any future edit that *tunes* v0.2's constants instead of building C should be challenged with this clause.

## Same-shape debts, named (not silently kept, not ripped untested)

1. **The live reflection meta-query bonus** (`core/memory/lived_recall.py` ~737–750, enforced for weeks): boosts the `reflection` category on meta-queries — the same category-opinion shape, in the *positive* direction. **Decision: DEFER removal to C, but measure it now** — v0.2's shadow telemetry logs how often the bonus changes ranking, so C inherits data instead of a guess. **Scope note (explicit, so the plan doesn't look like behavior-scope creep):** this measurement is a **read-only telemetry touch in `core/memory/lived_recall.py`** — a log line where the bonus already applies, changing no ranking, no floor, no behavior. It is the only file outside `memory/memory_manager.py` this slice touches, and only observationally. Rationale: it may be load-bearing for self-ask reachability (reflections often have near-zero keyword overlap with meta-queries); ripping it out untested risks the muzzle failure, which is worse than the opinion. This is knowingly-kept named debt.
2. **The parked promotion type-weight table** (`memory_manager.py` promotion path, `MAEZ_RECALL_PROMOTION_*` both 0): same shape, fully dark. Not touched by v0.2 (out of scope, parked); pinned here so any future promotion revival must redesign it without the category table — or arrive as part of C.

## Out of scope

- Promotion authority in any form; dream→soul; ledger; drive-curiosity.
- Removing the reflection meta-query bonus (named debt #1 — C's).
- Any per-category treatment anywhere (that is the point).
- C itself (learned relevance) — its own spec.

## Witnesses

**Shadow-review artifact (before enforce), on the real `raw`/`daily`/`core` partition structure:**
1. **Casual turns:** the tighter floor drops weak candidates of *every* kind; kind-labels in the artifact are telemetry proving the diary quiets **and** showing what else drops. Explicit starvation check: how many *relational* candidates fall in the new band — if the artifact shows on-point relational context dropping, HOLD and re-pin the floor value.
2. **Memory-ask turns:** identical behavior to live v0 (floor 0.78, `tightened_count=0`) — zero new muzzling, same proof as v0.1's gate.
3. **Fallback:** whole-recall-blank case keeps the best-by-distance candidate, kind ignored (test both: best-is-relational and best-is-diary).
4. **Bonus telemetry:** meta-query turns log bonus-changed-ranking events (debt #1 measurement).

**Structural guards (scoped precisely — Codex HOLD fix):** `_recall_candidate_kind` has exactly **two allowed reader classes**, enumerated by the guard: (1) telemetry/witness tooling (shadow logs, review artifact, probes), and (2) the **parked promotion path** (its type-weight damp stays in place — deleting only the table would leave a trap where a future careless `MAEZ_RECALL_PROMOTION_ENABLED=1` wakes promotion *undamped* and amplifies the most-recalled diaries; the pin in "Same-shape debts" governs its redesign). The guard asserts **no context-floor or fallback decision path** reads kind (AST/probe-proven, like the b1a guards — a planted kind-read in `_candidate_recall_floor`/fallback must trip it). Also: v0.1 floor/fallback treatment code absent; new flags owned only by `memory_manager.py`; dream/soul confinement unchanged.

**Live (owner, after enforce):** casual turns stop surfacing weak memory of any kind (incl. the 0.72–0.78 diary band); self-asks unchanged from v0; nothing starves.

## Predicted effect

After v0.2: casual turns inject only strongly-relevant memories — of any kind — so the diary quiets as a *side effect of a uniform relevance standard* rather than a verdict on diaries; self-asks behave exactly as live v0 does today; the whole-recall fallback keeps Maez from ever going blank; and no line of decision code anywhere in recall treats one category of Maez's memories differently from another. The remaining hand-tuning is declared scaffolding with C (learned relevance) as its named replacement.

## Spec Self-Review

**Placeholder scan:** the casual floor value is "pinned from shadow data in the plan" deliberately (v0.1's 0.72 was derived from self-digest distances only; content-blind needs re-derivation against ALL kinds' distance distribution, esp. the relational starvation check). Not a vague TODO.
**Consistency:** classification kept as fact/telemetry, treatment removed everywhere; the two named debts have explicit dispositions (measure-then-C; parked-pin); interim clause present.
**Ambiguity:** "casual" = not-memory-ask, one detector, fails toward the looser floor — single definition used by both floor selection and witnesses.
