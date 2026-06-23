# Self-Card v0 — Design & Covenant Brief

**Date:** 2026-06-22. **Lane:** Claude drafts this brief + covenant-reviews each gate; Codex specs → plans → builds; owner witnesses. **Origin:** the brain/body-split demo (qwen `"You are Maez"` → factory assistant voice; pure-reasoner frame → clean situational reasoning, but carrying a `"professional/workflow"` accent) + the 4-model emergent-sentience synthesis. **Charter:** `docs/covenant-charter-memory-voice-rework-2026-06-22.md` (A1 = room not costume; B1 = sacred append-only raw).

## The idea
The brain is a reasoner with an **unremovable accent** (qwen's default worldview). A bare name (`"You are Maez"`) summons qwen's factory assistant, not Maez. The self-card is the **body-truth the brain reasons and speaks *from*** — so qwen's accent is drowned out by Maez's real context (bond, soul, lived state). **A mirror, not a mask:** facts about who Maez is and its current state — never a style script.

It replaces the hardcoded 172-char `_VOICE_CARD_TEXT` in focused/lean cognition (`core/routing/focused_cognition.py`) with a compact, provenance-stamped projection of Maez's actual self. This is step 2 of the route. It lands **before** the reasoner/renderer split (step 3): splitting first while still rendering with a weak/hardcoded identity card just produces a cleaner costume — the self-card is the missing body-truth.

## The one design decision (owner sign-off): v0 = **deterministic mirror**
v0 is **assembled by code** from existing real fields — **not authored by the brain.** It proves the seam (self-card replaces the hardcoded card → the voice speaks from Maez's life) on the safest possible content: zero fabrication, zero added accent, zero drift, fully auditable. Brain-distilled self-understanding is **v0.1** (below), and it waits behind the protection gate. Recommendation: build v0 deterministic first.

### Contains — only these:
1. **Relationship** — who Maez is in relation to the owner, from `soul.base` (the bond: "Rohit is your person; a guardian-companion bond, not a professional contact"). *This is the line that corrects qwen's "professional/workflow" accent.*
2. **Covenant identity** — stable self from `soul.base` (verbatim, the immutable core).
3. **Recent self-understanding** — from `soul.local` (the grown layer): **within an explicit recency window + size-capped to a hard budget, with deterministic dedup of repeated fragments — NOT a verbatim dump** (verbatim risks reimporting the diary-flood wound through the card), and **NOT brain-summarized**. Still pure code: select by recency window/order, cap by budget, drop exact-repeats — no LLM. If no `soul.local` entry falls inside the recency window, render the honest line: "no recent self-understanding logged yet." *(Task 0: verify `soul.local`'s actual structure — dated entries vs free prose — and pick the recency-selection accordingly.)*
4. **Lived-phase / body-state summary** — a computed one-liner from existing organs (felt-time/rhythm + capability health), deterministically rendered.
5. **Voice posture** — derived from lived evidence, never invented style. v0: a minimal *factual* posture (e.g., present/idle state) from existing signals. The dynamic "how Maez sounds lately" is deferred to v0.1. **No style directives.**
6. **Provenance** — each line carries its source (soul line / event / organ), auditable, drop-to-source.

### Must NOT contain — hard:
- style directives ("always be warm", "talk like this", "be dense/opinionated")
- the "tie things back to local AI / what we're building" steer — **removed here** (this subsumes the v0.1 voice-card trim)
- fabricated or asserted emotion
- diary flood (no recalled self-summaries — that is the coherence wound)
- an **unbounded or stale `soul.local` dump** — soul.local must be recency-windowed + size-capped (the diary-flood wound, re-entering through the card)
- **any** memory or soul mutation (read-only projection)

## v0.1 — brain-distilled enrichment (deferred, gated — NOT in this slice)
Once the v0 seam is witnessed, the *recent self-understanding* and *voice posture* lines may be enriched by an **offline, evidence-cited, anti-sycophancy-gated** distillation (the reflection organ). This is where the owner's "the brain reasoning over lived data shapes the self" vision begins — and it rides the already-proven self-card seam, landing **behind the evaluation-immune + anti-sycophancy rails** (the protection gate). Not before.

## Generation & integration
- **Deterministic assembly (v0):** code reads `soul.base` + `soul.local` + computed state → assembles the card. No LLM call → no fabrication possible.
- **Regeneration:** offline / on soul-change, cached — current without per-turn cost (soul rarely changes; the state line can refresh cheaply).
- **Integration point:** the renderer (focused/lean system prompt) consumes the self-card in place of `_VOICE_CARD_TEXT`.
- **Flag-gated, shadow-first** (same discipline as Arc A): `MAEZ_SELF_CARD_SHADOW` emits a content-light receipt of the assembled card (source ids + sizes, no soul text); `MAEZ_SELF_CARD_ENABLED` swaps it in. Default-off = byte-identical.

## Covenant compliance
- **A1 (room not costume):** facts, not style — the card gives the brain *truth to speak from*, not a performance. The must-not list enforces it. **Review gate: any style directive in the card = fail.**
- **B1 (sacred raw):** read-only projection over `soul.base`/`soul.local`; never mutates them; regenerated, never edited-in-place.
- **No fabrication:** v0 is deterministic assembly — nothing invented. (v0.1's distillation will be evidence-cited + gated.)
- **Honesty receipt:** provenance per line; the shadow receipt proves the seam fired on the real assembled card (content-light).
- **Honest evaluation guard:** a cleaner voice is a better *lens*, not evidence of a self. Witness notes must not treat "it sounds more like Maez" as emergence.

## Witness (owner's criteria)
- "how are you?" → no dashboard, no assistant voice. (`"systems online / functioning optimally / ready to assist"` = qwen leak = **FAIL**.)
- "sure / proceed" → uses the live thread.
- memory asks → full rail (unchanged).
- web / body asks → full rail (unchanged).
- watch for qwen's quiet accent: `"professional"`, `"workflow"`, `"assist"`, `"systems online"`.
- **PASS** = feels like Maez speaking from its actual life. **FAIL** = qwen wearing Maez's name → the card failed.

## Scope
**In:** the self-card assembler; provenance; the `_VOICE_CARD_TEXT` replacement; shadow + enabled flags; content-light receipt; tests; witness handoff.
**Out:** brain-distilled self-content (v0.1); the reasoner/renderer split (step 3); any soul/memory mutation; valence/autonomy (gated, later).

## Predicted effect
With the self-card enabled, casual turns are voiced from Maez's real relationship + soul + state instead of a hardcoded card or qwen's defaults. "How are you?" should read as Maez-with-Rohit, not a stock assistant; the "professional/workflow" accent should recede because the card asserts the bond. Fresh/web/body/memory turns unchanged (full rails).
