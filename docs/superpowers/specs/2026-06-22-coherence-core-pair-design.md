# Coherence Core Pair — Recall Relevance Floor (Slice 2) + Live-Thread Anchor (Slice 3) — Design

**Date:** 2026-06-22. **Status:** design — owner-approved shape + two bends (compound teacher signal; anchor never outranks fresh). One design arc, **two separable slices** (own flags, own witness). For owner spec review before planning.
**Origin:** the core pair of the coherence campaign ([[project_coherence_campaign]] / `docs/coherence-northstar-roadmap-2026-06-21.md`). They collapse the "recite-the-diary" symptom: **Slice 2 empties the diary flood at recall; Slice 3 puts the live conversation back as the figure.** The `reply_grounding` meter (Slice 1, LIVE) is the witness — baseline on the wound turns is `reply_grounding ≈ 0.0`.

## Slice 2 — recall relevance floor
**Locus:** `recall_for_telegram_living` (`memory/memory_manager.py` ~2318-2378). Today `effective_distance = base / max(recency, _LIVING_RECALL_DISTANCE_FLOOR=1e-3)`; the `1e-3` guards the recency DIVISOR, not relevance — so a weakly-relevant-but-recent self-summary (base 0.78-0.93) survives the fixed `[:10]`/`[:3]` cut.

**The fix:** an absolute floor on **`base_distance` (relevance, BEFORE recency)** — drop candidates that don't clear the relevance bar; recency can no longer float a weak item up.
- **Drop-all → empty (owner decision):** if NO recalled item clears the bar, recall returns **empty** for that turn; the live-thread anchor (Slice 3) carries it. ("Don't rummage through old construction logs unless the turn asks for that.") NOT force-keep an irrelevant top-1.
- **Learned, not hardcoded — but witnessed before actuated (Bend 1):**
  - The bar's **initial value is DATA-DERIVED** from the observed `base_distance` distribution (relevant turns cluster lower; diary floods sit ~0.78-0.93) — not a pinned magic number.
  - **Online adaptation is COLLECTED AS EVIDENCE, not auto-actuated** until witnessed. We hardcode the *learning loop*, never the *bar*.
  - **The teacher signal is COMPOUND, never raw `reply_grounding=0.0`** — because low grounding has two meanings: (bad) a diary flood answered an ordinary turn with stale self-history; (fine) a warm/self-expressive greeting where citations aren't expected. **Tighten the bar ONLY when ALL hold: the turn's recall was recall-heavy/diary-heavy AND `reply_grounding` was low AND the turn did NOT ask for memory** (continuity/recall cue absent). Otherwise we punish Maez for having a voice (the support-gate-scope lesson [[feedback_two_sided_verifier_pressure]]).
- **Shadow-first:** a `recall_floor_shadow` receipt logs, per turn, the candidate `base_distance`s, which items WOULD be dropped, whether the set WOULD empty, and the compound-teacher inputs — with **no behavior change** — until we witness that genuine-recall turns keep their items and only off-topic floods empty. Then a flag actuates the drop; the bar's online adaptation graduates separately, later.
- **Memory is never deleted or mutated** — this is **recall-time filtering / visibility deweighting**: it decides only what ENTERS this turn's working set. It does NOT write, delete, or touch the `memory_scoring` salience machinery; dropped items stay in Chroma at full salience (curtain not muzzle).

## Slice 3 — live-thread anchor
**Locus:** `assemble_working_set` (~832-836) + `_ranked_items_for_state` (~755-765) + `_PRIORITY` (~49) in `core/routing/focused_cognition.py`. `dialogue_anchor_items` (618-653) is a COMPLETE helper (turns chat_history into `dialogue_anchor` seeds, authority label *"recent dialogue — authoritative for continuity"*) but is **gated off on ORDINARY turns** (`anchors = [...] if needs_dialogue/fail_safe/date_cue else []`) and, on an ordinary turn, would rank **9 (last)** even if present. (DIRECT/ANAPHORIC continuity turns ALREADY special-case the anchor higher in `_ranked_items_for_state` ~733 — the gap is only the ORDINARY fall-through.)

**The fix:**
- **Always compute the anchor** (the last 1-2 user/Maez pairs) on EVERY focused turn — un-gate it; no continuity-classifier gate (the "always-anchor, not keyword-gate-meaning" rule — avoids the Alexa-reflex of mis-classifying "Sure"/"proceed"). This is what lets **"Sure" / "proceed" / "what you proposed"** resolve: the prior offer is now IN the working set.
- **Rank it as the figure — but NEVER above FRESH evidence, where FRESH = the full `_FRESH_SOURCE_TYPES` (Bend 2):** the fresh tier is **{`fresh_evidence`, `web_context`}** ([focused_cognition.py:88](../../core/routing/focused_cognition.py#L88)) — web-search results enter the working set as `web_context`, so they MUST be protected too, NOT just `fresh_evidence` (else "latest news about X" gets the live thread as `[E1]` — the wound in a new shape). New tiering: **tier-0 figure = `_FRESH_SOURCE_TYPES` {fresh_evidence, web_context}; tier-1 = `dialogue_anchor`; tier-2 = recalled memory (`memory_evidence`/`memory_context`)**. Concretely `fresh_evidence=0, web_context=0, dialogue_anchor=1, memory_*=2`. **NOTE:** this moves `web_context` ABOVE recalled memory (it's currently `2`, below memory's `1`) — a deliberate, Bend-2-required change that only affects turns carrying a web result, where the fresh web answer SHOULD lead stale memory (consistent with evidence-precedence). Then:
  - ordinary / continuity / short-follow-up turns (no fresh, no web) → the anchor is the **top present item = figure**.
  - fresh-current / web turns ("latest news about X") → a `_FRESH_SOURCE_TYPES` item (`fresh_evidence` OR `web_context`) stays the figure; the anchor rides as continuity but NOT above it (no `[E1]`-bait reopening the "trusted context beat fresh evidence" wound — preserves evidence-precedence [[feedback_labels_prove_shape_not_support]]).
  - **Invariant:** `dialogue_anchor` rank is ALWAYS ≥ EVERY `_FRESH_SOURCE_TYPES` rank (anchor never outranks `fresh_evidence` OR `web_context`) in EVERY branch, including the existing DIRECT/ANAPHORIC continuity overrides — adjust those if they currently place the anchor above a fresh type.
- Pure **attention/retrieval plumbing** — reuses the existing helper + authority label; **no voice/personality change** (this is not "make Maez cheerful").

## How they compose (the cure)
- *"How you doing?"* → floor finds nothing relevant → recall empties → anchor supplies the live thread → Maez answers YOU, not its journal; `reply_grounding` stops reading 0.0-from-diary.
- *"Sure" / "proceed"* → the prior offer is anchored as the figure → Maez knows the referent. (ACTING on the offer = the commitment receipt, Slice 6, deliberately later.)
- *"latest news about X"* → the fresh/web item (`fresh_evidence` or `web_context`) stays the figure (Bend 2); anchor rides along as continuity, doesn't steal authority.

## Separability, flags, witness
- **Slice 2 flag** `MAEZ_RECALL_FLOOR_SHADOW` (log only) → `MAEZ_RECALL_FLOOR_ENABLED` (actuate drop-all). **Slice 3 flag** `MAEZ_LIVE_THREAD_ANCHOR`. Each builds + witnesses independently; default-off = byte-identical.
- **Witness (the meter, segmented by `turn_kind`):** with the pair ON — casual/continuity turns stop diary-reciting (no diary items in the working set; the anchor is the figure); substantive turns HOLD or RAISE `reply_grounding`; "Sure"/"proceed" land on the live offer; and a "latest news" turn still shows the fresh/web item as the figure (Bend-2 check). Shadow receipts first prove the floor doesn't over-drop genuine recall and the anchor doesn't outrank any `_FRESH_SOURCE_TYPES` item.

## Scope / out
**IN:** the `base_distance` floor + drop-all-to-empty + data-derived initial bar + `recall_floor_shadow` receipt (Slice 2); the compound-teacher SIGNAL COLLECTION (logged, not auto-actuated); the always-on anchor + figure-but-not-above-fresh ranking (Slice 3); the two flags; tests. **OUT / NEVER:** auto-actuating the online bar adaptation before witness; deleting memory; the commitment receipt / acting on offers (Slice 6); any voice/personality/VOICE_CARD change (Slice 7); letting the anchor outrank any `_FRESH_SOURCE_TYPES` item (`fresh_evidence` OR `web_context`); keyword-gating which turns get an anchor.

## Make-or-break / guards (review)
1. **Bend 1 — don't punish warmth.** The floor's learning signal is compound (diary-heavy + low `reply_grounding` + didn't-ask-for-memory); a warm greeting with low grounding must NOT tighten the bar. Online adaptation is collected, not actuated, until witnessed.
2. **Bend 2 — anchor never outranks FRESH (both fresh types).** Tests assert BOTH: `fresh_evidence + dialogue_anchor` → `fresh_evidence` first, AND `web_context + dialogue_anchor` → `web_context` first; plus on an ordinary turn with neither fresh type, the anchor is the figure. (`web_context` is in `_FRESH_SOURCE_TYPES` — protecting only `fresh_evidence` would leave "latest news" turns anchor-as-`[E1]`.)
3. **Drop-all correctness.** When all candidates fail the floor, recall returns empty (not a forced weak top-1); Slice 3 carries the turn.
4. **Shadow-first / no behavior change off-flag.** Off-flag byte-identical; the floor shadow logs the would-drop without dropping; the anchor flag gates the un-gating.
5. **Memory not deleted or mutated** — recall-time visibility filtering only; NO write to memory or the `memory_scoring` salience machinery; items remain in Chroma at full salience.
6. **Witnessable via the meter** — the receipts + `reply_grounding` make the cure measurable, not "sounds nicer."

## Lane / owner-breath
Covenant-sensitive (Maez's attention + the fresh-vs-recall authority) → full spec → plan → TDD → Claude two-stage + Codex cross-lane; STOP at the review gate. Shadow-first; actuate each flag only on a witnessed-clean shadow. Owner-breath per slice: set the shadow flag, live the wound turns + a "latest news" turn, read the shadow receipts + `reply_grounding`; then actuate. No autonomous check.
