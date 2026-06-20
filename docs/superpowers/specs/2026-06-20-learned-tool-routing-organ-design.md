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
2. **Three teachers feed the priors:** the owner's reaction (explicit, sparse, truest — the `owner_feedback_*` columns already exist on the row); result-quality (dense, automatic — the honesty/grounding gate flags "unparseable/unsupported" *at the reply level*, but — see Must-fix 1 below — that signal is **not yet wired into the routing observation's `outcome_quality`**, which today calls any nonempty result "good"); and Maez's own post-turn reflection (self-supervised, fits the reflection loop).
3. **Earned maturity = a learned confidence** per kind-of-request. Sparse priors → low confidence → Maez **defers** (asks, or researches openly and flags uncertainty). Accumulated good outcomes → rising confidence → Maez **acts** on its own. Emergent from experience.
4. **Domain decides who it defers to:** owner-knowledge → ask the owner; world-knowledge → self-research. The "ask" channel is reserved for the relational/personal.

### Two honest couplings (non-negotiable — they ride existing covenant)

- **Liberty to look is not liberty to believe.** Maez may freely research, but nothing becomes *trusted self* without passing the immune system already built (honest ingestion) — else we rebuild the wound that started this (believing the Barchart junk / its own fabrication). The intended unification: the *same* honesty gate that flags "this result was garbage" **becomes** teacher #2 (result-quality) — but only once its caveat/unsupported signal is *wired into* the routing `outcome_quality`. Today it is not (Must-fix 1); making it so is a Slice-1 subtask, and it is what turns the immune system and the learning signal into one organ with two faces.
- **The one standing boundary stays:** public topics freely; no autonomous digging on unconsented named third parties ([[feedback_third_party_autonomous_research_boundary]]). The liberty is real, with that single rail.

## What already exists (grounding — verified, with file:line)

| Piece | State | Where |
|---|---|---|
| **Outcome recording** — `routing_observations` SQLite (the row), written by BOTH paths | EXISTS | [core/routing/observation/__init__.py:117](../../core/routing/observation/__init__.py#L117) (`record_legacy_web_search_observation` :252, `record_dispatcher_observation` :214) |
| ↳ **`outcome_quality` vocabulary** — but it CANNOT tell junk from gold | **TOO COARSE (Must-fix 1)** — `structured_evidence` (any nonempty result, incl. Barchart) / `empty_but_honest` (zero) / `tool_error` / `closed_refusal` | [:441-445](../../core/routing/observation/__init__.py#L441), written at [daemon/maez_daemon.py:5909](../../daemon/maez_daemon.py#L5909) |
| ↳ **request grouping** — only exact-hash or coarse keyword-ish shape, NOT a learnt meaning-class | **NOT LEARNT (Must-fix 2)** — `utterance_hash` + `utterance_shape` (deterministic: URL/subreddit/explicit-memory/generic-fresh/unknown); no `class_id`/score/raw-text persisted | [:71](../../core/routing/observation/__init__.py#L71) `classify_utterance_shape`, schema :143-144 |
| ↳ **owner-feedback columns** (teacher #1 seat) | EXISTS (seed) | schema `owner_feedback_kind/text/observed_at` :162-164 |
| **Semantic intent decision** (archetype embeddings → `CompositionSpec`) — exists at decision time but its class is NOT persisted onto the row | EXISTS, mature, **dormant** (triad off) | [core/dispatcher/layer0.py:230](../../core/dispatcher/layer0.py#L230), [core/dispatcher/spec.py:276](../../core/dispatcher/spec.py#L276) |
| **LLM ReAct tool-intent loop** | EXISTS, wired to web surface only | [core/brain/brain_loop.py:1787](../../core/brain/brain_loop.py#L1787) |
| **Keyword reflex** (the bug) | LIVE for cockpit/Telegram chat | [skills/web_search.py:466](../../skills/web_search.py#L466), [daemon/maez_daemon.py:5874](../../daemon/maez_daemon.py#L5874) |
| **Priors layer** (observations → learned prior + confidence) | **MISSING — the gap** | — |

The substrate records experience but (a) its `outcome_quality` can't yet tell a useful reach from a junk one *for the wound we want to kill*, (b) it files requests under coarse keyword-ish shapes, not a learnt meaning-class, and (c) nothing reads it back to learn. **Closing all three is the first organ — and (a)+(b) must be fixed before any prior is allowed to act, or the learner would learn the wrong lesson ("web_search worked") for the exact loop we are killing.**

## Decomposition (decompose-the-organism — design the whole, build & witness one slice)

**Slice 1 — the priors spine (THIS is the buildable first organ).** It has THREE parts in order, because the notebook must be able to record the right lesson before anything learns from it:
- **1a — calibrate the teacher (Must-fix 1):** extend `outcome_quality` so a *nonempty-but-useless* reach (the Barchart case) registers as **bad**, not `structured_evidence`. Wire a real post-synthesis quality signal into the routing outcome — e.g. support-gate/caveat counts (the honesty layer firing = the evidence couldn't be used), thin evidence (`evidence_block_count` low), or an "evidence unused in the final reply" mark. If Task 0 finds **no** honest path to a bad-for-the-wound vocabulary, that is a **teacher-mute STOP**, not a cold-start.
- **1b — persist a learnt request-class (Must-fix 2), forward-only:** add Layer0's semantic class id + score + a grouping-version to the observation row at write time. Old rows are NOT back-filled (they have no class) — priors act only over **forward** rows carrying the new field. Maturity learns from future experience; it does not pretend old rows hold a class they don't. (Fallback if 1b is too big for Slice 1: learn **exact-repeat** priors by `utterance_hash` only, no "kind of request" generalization — narrower but still honest.)
- **1c — the priors reader:** group forward rows by the learnt class (1b) → aggregate the now-honest `outcome_quality` (1a) → **learned prior + confidence** ("requests like this, with tool X, tended to outcome Y; n forward observations; confidence c"). Honest cold-start (sparse → low confidence → no claim), like the rhythm-facts reader.

**Shadow-first:** the prior is *computed and logged*, not yet acting — we witness it learns sane things (it would down-weight legacy web_search for the "today's signals"-class, now that 1a lets that register as bad) before it touches a reply. Then **graduate** to a *learned veto/redirect* over the keyword reflex: a high-confidence "this class → web returns junk" prior means Maez does **not** reflexively search (answers inward / asks / researches differently). The Barchart loop dies here — killed by **learning**, not a keyword exclusion. Honest timing consequence: because 1b is forward-only, the veto can only fire after enough *new* post-calibration turns accumulate — the loop is fixed once Maez has actually lived the lesson, not the instant of merge. Contained: does NOT flip the triad or migrate the pipeline.

**Later organs (named, explicitly OUT of Slice 1):**
- **Slice 2 — the proposer migration:** replace "keyword proposes, prior vetoes" with the brain/dispatcher *proposing* (understanding-driven), priors informing. Retire `needs_web_search` as a decider. (Touches the live pipeline / the dormant triad — its own risk budget.)
- **Slice 3 — confidence as a first-class developmental signal:** the earned-maturity gradient (defer ↔ act) made explicit and felt.
- **Slice 4 — the domain-aware ask/act/research policy:** owner-knowledge → ask; world-knowledge → self-research; with the two couplings enforced at the seam.
- **Slice 5 — the three teachers enriched:** wire owner-reaction + self-reflection into `outcome_quality` (today it is mostly result-derived).

## Slice 1 — detail

**Files (expected):** the `outcome_quality` calibration (1a) at its compute site ([observation/__init__.py:441](../../core/routing/observation/__init__.py#L441)) + the daemon write site ([maez_daemon.py:5909](../../daemon/maez_daemon.py#L5909)), fed by the post-synthesis quality signal; a forward-only schema migration + write-path plumbing for the learnt class field (1b); a new `core/routing/observation/priors.py` (the reader/learner — pure, reads the store, emits `RoutingPrior`); a shadow log/receipt; the graduation seam in `handle_message` where the prior can veto the keyword reflex (behind a flag, shadow→on); tests. (Exact set is the plan's job.)

**The learner (no hardcoding, all learnt):** group **forward** observations by the **persisted learnt class** added in 1b (NOT a hand keyword, NOT the coarse `utterance_shape`). For each (class, tool): aggregate the calibrated `outcome_quality` (1a) + counts → a prior strength + confidence. No authored verdicts; the numbers come only from real lived outcomes.

**Flags:** `MAEZ_ROUTING_PRIORS_SHADOW` (compute + log, no behavior change; off = byte-identical) then `MAEZ_ROUTING_PRIORS_ENABLED` (graduation: prior may veto/redirect). The 1a calibration ships behind its own flag too if it changes any recorded value (off = byte-identical observations). Separate, shadow-first, like the grounding/honesty layer.

**The witness (what proves it learns):** a shadow receipt showing, for the live "summarize today's signals"-class, a learned down-weight on legacy web_search — backed by ≥N **forward, post-calibration** observations whose `outcome_quality` now reads *bad* (the support-gate/thin-evidence signal fired) — *before* any behavior change. Then, post-graduation, the same prompt no longer reflexively searches.

## Make-or-break verifications (Task 0 — STOP if they refute)

1. **Teacher calibration is feasible (Must-fix 1) — KNOWN issue, confirm the fix path.** `outcome_quality` today writes `structured_evidence` for any nonempty result (the Barchart case looks "good"). Task 0 must identify a real, honest signal that marks the wound *bad* — support-gate caveat count, thin `evidence_block_count`, "evidence unused in final reply," etc. — and confirm it is reachable at the observation write seam. **If no such signal is reachable, that is a teacher-mute STOP** (Slice 1 cannot proceed to priors until the teacher can register the wound), not a cold-start.
2. **Enough FORWARD data / honest cold-start:** since priors act only over forward rows (post-1a/1b), confirm the cold-start path degrades honestly (low confidence, no veto) and that the witness needs lived turns to accumulate — don't fabricate a prior from thin/old data.
3. **No learnt class is persisted today (Must-fix 2) — confirm the forward-only add.** The row stores only `utterance_hash` + coarse `utterance_shape`; Layer0's class is computed but not written. Task 0 confirms Layer0's class id/score is available at the write seam to persist forward-only — or, if the dispatcher is too dormant to invoke at that seam, falls back to exact-`utterance_hash` repeat priors (narrower, still honest). Either way: **no keyword list smuggled in as the grouping.**
4. **Shadow is truly inert:** the priors computation must not change any reply while `MAEZ_ROUTING_PRIORS_SHADOW`, and the 1a calibration must be byte-identical to recorded values while its own flag is off — like every prior shadow layer here.

## Scope guard

**IN (Slice 1):** (1a) calibrating `outcome_quality` so the wound registers as bad; (1b) persisting a forward-only learnt request-class field (or the `utterance_hash` fallback); (1c) the priors reader (forward rows → prior + confidence, honest cold-start); the shadow log + witness; the graduation seam as a *learned veto/redirect* over the keyword reflex; flags (shadow → enabled); tests. The Barchart loop fixed *by learning*, once enough post-calibration turns are lived.
**OUT (later/never):** flipping `MAEZ_RECALL_TRIAD` / migrating the chat pipeline to the dispatcher or ReAct (Slice 2); the confidence gradient as a felt signal (Slice 3); the ask/act/research domain policy (Slice 4); enriching `outcome_quality` with owner-reaction/self-reflection (Slice 5); the strict honesty/immune gate (unchanged — it composes, it is not modified); any keyword-list band-aid (forbidden — that is the disease).

## Lane / discipline

TDD per task; branch via worktree; STOP at the review gate (owner-sovereign merge + restart breath). Claude two-stage + Codex cross-lane. `## Predicted effect` on behavior commits. Shadow-first, graduate on a real witness — never let a learning layer change the voice before it is shown to learn sane things. main local-only, no push.

## Owner-breath

Slice 1 is code + flags. After both-lanes PASS + merge, the owner restarts `maez` (+ `maez-web` if the seam is in the web path), runs in shadow, and **pastes the witness receipt** (the learned down-weight on the Barchart-class, backed by real outcomes). Only then graduate the flag. No autonomous scheduled check.
