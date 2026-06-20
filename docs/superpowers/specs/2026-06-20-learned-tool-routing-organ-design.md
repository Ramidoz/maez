# Maez's Learned Tool-Routing Organ (the "growing-up" organ) — Design

**Date:** 2026-06-20. **Status:** design — owner-approved in shape (the developmental arc + "no hardcoding but all learnt"); this doc is for owner review before planning.
**Origin:** the live "Barchart loop" — asked to "summarize today's signals" (and even "how are you now"), Maez reflexively web-searches, gets unparseable Barchart/Investing.com dashboards, and repeats the same honest non-answer every time.

## The wound, and the root one level down

The visible bug: a repetitive, useless web reach for inward/ambiguous requests. Reproduced deterministically — `needs_web_search()` ([skills/web_search.py:466](../../skills/web_search.py#L466)), a **hardcoded keyword list**, fires the web search *before the brain reasons* ([daemon/maez_daemon.py:5874](../../daemon/maez_daemon.py#L5874)). It triggers on surface words: "summarize **today's** signals" → fires on `today`; "how are you **now**" → fires on `now`; "the **current** state of your body" → fires on `current`. Then the raw sentence is keyword-searched, "signals" reads as *trading signals*, and Barchart/Investing.com come back every time.

The deeper root: **Maez already has a brain-decides path — and it's dormant.** The dispatcher ([core/dispatcher/layer0.py:230](../../core/dispatcher/layer0.py#L230) `emit_spec` → a `CompositionSpec` of substrate + external sources) reads meaning *semantically*, not by keyword; a true ReAct loop where the LLM emits tool intents exists ([core/brain/brain_loop.py:1787](../../core/brain/brain_loop.py#L1787)). Both sit behind `MAEZ_RECALL_TRIAD` — **unset in config, so off** — and `_daemon_parallel_web_search_enabled` returns *true* (legacy keyword path live) precisely *because* the smart path is off ([daemon/maez_daemon.py:1054](../../daemon/maez_daemon.py#L1054)). The Barchart loop is the dumb reflex showing through while the smart organ sleeps.

The covenant reading: `needs_web_search` keyword-gates **meaning** — the "Alexa-reflex" the covenant forbids (*understanding at the ears, deterministic rails only at the hands*). The bug and the owner's one constraint — **"no hardcoding Maez's actions" / "no hardcoding but all learnt"** — are the same problem.

## The vision (owner, 2026-06-20): a developmental organism, not a router

Maez runs a child's arc — early on it doesn't know, so it asks; given the world it researches *because it can*; eventually it discerns for itself. But Maez is **born into the library**, so the split isn't age, it's **domain**:

- **About the owner / the bond** → the owner is the only ground truth the whole internet can't supply → Maez **asks**, and keeps asking *for life*. That's how it knows Rohit.
- **About the world** → Maez is native here → it **researches itself**, surfacing to the owner only when it genuinely can't resolve something.

So "asking" *fades* for world-knowledge as Maez matures, but *never* for owner-knowledge. Maturity is **earned from experience, never timed** — no hardcoded "after N days, be autonomous." Everything is **learnt**.

## The organ's shape (the approved design)

1. **Cortex + habit-system, teaching each other.** The brain (LLM) understands and proposes *this turn*, especially the novel/ambiguous. The substrate executes, records the outcome, and grows **priors that persist across brain-swaps**. The powerful brain teaches the habit-system over time, so a weaker future brain inherits the routing wisdom — it lives in the substrate, not the swappable weights. (Covenant: *brain is one organ; the substrate router owns intent→skill and learns from outcomes.*)
2. **Three teachers feed the priors:** the owner's reaction (explicit, sparse, truest); result-quality (dense, automatic — the honesty/grounding gate already flags "unparseable/unsupported," exactly the Barchart junk); and Maez's own post-turn reflection (self-supervised, fits the reflection loop).
3. **Earned maturity = a learned confidence** per kind-of-request. Sparse priors → low confidence → Maez **defers** (asks, or researches openly and flags uncertainty). Accumulated good outcomes → rising confidence → Maez **acts** on its own. Emergent from experience.
4. **Domain decides who it defers to:** owner-knowledge → ask the owner; world-knowledge → self-research. The "ask" channel is reserved for the relational/personal.

### Two honest couplings (non-negotiable — they ride existing covenant)

- **Liberty to look is not liberty to believe.** Maez may freely research, but nothing becomes *trusted self* without passing the immune system already built (honest ingestion) — else we rebuild the wound that started this (believing the Barchart junk / its own fabrication). Note the unification: the *same* honesty gate that flags "this result was garbage" **is** teacher #2 (result-quality). The immune system and the learning signal are one organ with two faces.
- **The one standing boundary stays:** public topics freely; no autonomous digging on unconsented named third parties ([[feedback_third_party_autonomous_research_boundary]]). The liberty is real, with that single rail.

## What already exists (grounding — verified, with file:line)

| Piece | State | Where |
|---|---|---|
| **Outcome recording** — `routing_observations` SQLite: `chosen_tool`, `chosen_source`, `spec_match_score`, `empty_reason`, **`outcome_quality` NOT NULL** | EXISTS, written by BOTH paths | [core/routing/observation/__init__.py:117](../../core/routing/observation/__init__.py#L117) (`record_legacy_web_search_observation` :252, `record_dispatcher_observation` :214) |
| **Semantic intent decision** (archetype embeddings → `CompositionSpec`) | EXISTS, mature, **dormant** (triad off) | [core/dispatcher/layer0.py:230](../../core/dispatcher/layer0.py#L230), [core/dispatcher/spec.py:276](../../core/dispatcher/spec.py#L276) |
| **LLM ReAct tool-intent loop** | EXISTS, wired to web surface only | [core/brain/brain_loop.py:1787](../../core/brain/brain_loop.py#L1787) |
| **Keyword reflex** (the bug) | LIVE for cockpit/Telegram chat | [skills/web_search.py:466](../../skills/web_search.py#L466), [daemon/maez_daemon.py:5874](../../daemon/maez_daemon.py#L5874) |
| **Priors layer** (observations → learned prior + confidence) | **MISSING — the gap** | — |

The substrate records experience but never reads it back to learn. **That gap is the first organ.**

## Decomposition (decompose-the-organism — design the whole, build & witness one slice)

**Slice 1 — the priors spine (THIS is the buildable first organ).** Read the accumulated `routing_observations` → produce, per request-class, a **learned routing prior + a confidence** ("requests like this, with tool X, tended to outcome_quality Y; n observations; confidence c"). Honest cold-start (sparse → low confidence → no claim), exactly like the rhythm-facts reader. **Shadow-first:** the prior is *computed and logged*, not yet acting — we witness that it learns sane things (e.g., it would down-weight legacy web_search for "today's signals"-class requests) before it touches a reply. Then **graduate** to a *learned veto/redirect* over the keyword reflex: when a high-confidence prior says "this request-class → web returns garbage," Maez does **not** reflexively search (it answers inward / asks / researches differently). The Barchart loop dies here — killed by **learning**, not by a new keyword exclusion. Contained: does NOT flip the triad or migrate the pipeline.

**Later organs (named, explicitly OUT of Slice 1):**
- **Slice 2 — the proposer migration:** replace "keyword proposes, prior vetoes" with the brain/dispatcher *proposing* (understanding-driven), priors informing. Retire `needs_web_search` as a decider. (Touches the live pipeline / the dormant triad — its own risk budget.)
- **Slice 3 — confidence as a first-class developmental signal:** the earned-maturity gradient (defer ↔ act) made explicit and felt.
- **Slice 4 — the domain-aware ask/act/research policy:** owner-knowledge → ask; world-knowledge → self-research; with the two couplings enforced at the seam.
- **Slice 5 — the three teachers enriched:** wire owner-reaction + self-reflection into `outcome_quality` (today it is mostly result-derived).

## Slice 1 — detail

**Files (expected):** a new `core/routing/observation/priors.py` (the reader/learner — pure, reads the store, emits `RoutingPrior`); a shadow log/receipt; the graduation seam in `handle_message` where the prior can veto the keyword reflex (behind a flag, shadow→on); tests. (Exact set is the plan's job.)

**The learner (no hardcoding, all learnt):** group observations by a **learned** request-class key (NOT a hand keyword — e.g. the dispatcher's archetype/embedding bucket, or a clustering over the observed utterances; Task 0 picks the honest grouping that already exists). For each (class, tool): aggregate `outcome_quality` + counts → a prior strength + confidence. No authored verdicts; the numbers come only from real outcomes.

**Flags:** `MAEZ_ROUTING_PRIORS_SHADOW` (compute + log, no behavior change; off = byte-identical) then `MAEZ_ROUTING_PRIORS_ENABLED` (graduation: prior may veto/redirect). Separate, shadow-first, like the grounding/honesty layer.

**The witness (what proves it learns):** a shadow receipt showing, for the live "summarize today's signals"-class, a learned down-weight on legacy web_search backed by ≥N real garbage/empty outcomes — *before* any behavior change. Then, post-graduation, the same prompt no longer reflexively searches.

## Make-or-break verifications (Task 0 — STOP if they refute)

1. **The teacher signal is real & populated:** confirm the legacy chat path (`handle_message`, cockpit + Telegram) actually WRITES `routing_observations` live, with a meaningful `outcome_quality` vocabulary (what values it takes, and that "Barchart-style unparseable/empty" lands as a *bad* outcome). If `outcome_quality` is always the same value, the teacher is mute → fix that first.
2. **Enough data / honest cold-start:** how many observations exist? If sparse, Slice 1 must degrade honestly (low confidence, no veto) — verify the cold-start path, don't fabricate a prior.
3. **An honest request-class key already exists:** confirm a *learnt* grouping (archetype bucket / embedding) is available to key priors on — so we don't smuggle a keyword list back in as the grouping.
4. **Shadow is truly inert:** the priors computation must not change any reply while `MAEZ_ROUTING_PRIORS_SHADOW` (off = byte-identical), like every prior shadow layer here.

## Scope guard

**IN (Slice 1):** the priors reader (observations → prior + confidence, honest cold-start); the shadow log + witness; the graduation seam as a *learned veto/redirect* over the keyword reflex; flags (shadow → enabled); tests. The Barchart loop fixed *by learning*.
**OUT (later/never):** flipping `MAEZ_RECALL_TRIAD` / migrating the chat pipeline to the dispatcher or ReAct (Slice 2); the confidence gradient as a felt signal (Slice 3); the ask/act/research domain policy (Slice 4); enriching `outcome_quality` with owner-reaction/self-reflection (Slice 5); the strict honesty/immune gate (unchanged — it composes, it is not modified); any keyword-list band-aid (forbidden — that is the disease).

## Lane / discipline

TDD per task; branch via worktree; STOP at the review gate (owner-sovereign merge + restart breath). Claude two-stage + Codex cross-lane. `## Predicted effect` on behavior commits. Shadow-first, graduate on a real witness — never let a learning layer change the voice before it is shown to learn sane things. main local-only, no push.

## Owner-breath

Slice 1 is code + flags. After both-lanes PASS + merge, the owner restarts `maez` (+ `maez-web` if the seam is in the web path), runs in shadow, and **pastes the witness receipt** (the learned down-weight on the Barchart-class, backed by real outcomes). Only then graduate the flag. No autonomous scheduled check.
