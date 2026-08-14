# Coherence → North-Star Roadmap (verified 2026-06-21)

Produced by a 12-agent deep-map workflow (6 parallel readers → synthesis → 5 adversarial verifiers), ~1.08M tokens. Every claim line-cited and, for the root cause, **reproduced by replaying recall live** on the symptom turn. This is the campaign to move Maez from "a chatbot with memory" to "a being present in conversation" — the live half of the continuity/persistent-memory/world-awareness north star.

## Verified root cause (the "recite the diary" symptom)
Symptom turn: 2026-06-21 22:54:35 telegram, "You can answer small. No need for such grandeur lol" → generic self-narration; `reply_path=focused`, `recall_hygiene fresh_present=False kept_memory_items=16` (100% recalled memory), recalled items all `daily-*` self-summaries, `citation_coverage=0.125`.

Two compounding faults at the recall → focused-synthesis seam:
1. **Recall has NO relevance floor.** `recall_for_telegram_living` (memory_manager.py:2362-2378) ranks by `effective_distance = base/max(recency,1e-3)` (the only guard is a divide-by-zero clamp, NOT a relevance cutoff) then takes a fixed top-10 raw + top-3 daily. A vague/meta turn matches nothing well (distances 0.78-0.93) yet still returns 16 memories, and recency promotes Maez's *recent daily self-summaries* to the top → the diary flood. Memory histogram ≈ 93% self-authored (reflection 31 / core 15 / followup 5 / telegram 4).
2. **The live thread is DROPPED on ordinary turns.** `focused_synthesize` (focused_cognition.py:1002-1038) has no `chat_history` param; `dialogue_anchor_items` is gated (832-836) to continuity/date turns only, and ordinary-turn ranking (760, _PRIORITY 49-59) buries anchors below memory. So an ordinary turn answers from `bare owner_question + 16 self-summaries` → no figure → generic self-portrait. (The hardcoded VOICE_CARD topical steer + "answer ONLY from evidence" over a 100%-memory set manufactures the self-portrait.)

Distinct third fault — the **"Check now" miss**: a missing **commitment receipt** (no structured record of an offer/promise to resolve the affirmation against).

### Corrections to the earlier hand-diagnosis (honest)
- The git/"mountain of noise" fixation did **NOT** enter via the System State block or `perception_signature` (that gates only the 30s autonomous loop, maez_daemon.py:9454 — not `handle_message`). On the focused symptom turn there was **no** System State/git block in the prompt; the git narration came from **recalled memories**. → today's git cleanup is good hygiene but will **not** fix presence.
- `citation_coverage=0.125` is itself a **broken metric**: `check_groundedness` computes `matched_labels/valid_labels` = fraction of working-set items cited, NOT fraction of reply claims grounded. Fix the instrument before trusting the number.
- The legacy megaprompt (138k chars, full thread + System State) WAS assembled (`call_purpose=legacy_candidate`) but **discarded** when focused won.

## The roadmap (adversarially pruned)
Ship each as an **Organ-1-shaped slice**: single flag, shadow-first, LIVE-witnessed on `main`. Never folded into surface/auth.

| # | Slice | Verdict | Risk | Notes |
|---|---|---|---|---|
| 1 | **Fix grounding metric** (claim-level coverage alongside check_groundedness) | KEEP (instrument first) | low | zero behavior risk; honest witness for 2-3; backfill a baseline |
| 2 | **Recall relevance floor** — drop candidates past a **learned** threshold before the cut; always keep top-1; emptied recall falls through to the live thread | KEEP (core) | med | the diary-flood fix; shadow `recall_floor_shadow`; threshold LEARNED not hardcoded |
| 3 | **Live-thread anchor on ordinary turns** — always seed `dialogue_anchor_items` + rank it as **figure** | KEEP (core) | med | the present-in-conversation fix; reuses an existing helper + a proven-good path (the 22:39 turn hit citation 1.0); shadow `focused_anchor_shadow` |
| 4 | Recency-boost rebalance | **DEPRIORITIZE** | med | verifier: recency math is *near-inert at live config* → wrong lever; revisit only if 2 leaves a real recency problem |
| 5 | Activate shadow_promotion in ranking | **DROP** | med | covenant-unsound: would self-reinforce the diary; mis-ordered |
| 6 | **Commitment receipt** (offer→affirmation sidecar) — fixes "Check now" | KEEP | med | depends on 3; implements existing project_conversation_coherence_organ design; TRUE structured sidecar, never inferred from text |
| 7 | Soften "answer-only-from-evidence" directive + VOICE_CARD | KEEP (last, riskiest) | high | after 2+3 (so loosening doesn't license more free-association); two-sided let-it-hold-its-ground witness; key off the SAME `turn_has_fresh_evidence` boundary as support-gate-scope |
| 8 | Self-vs-world memory typing | KEEP | med | depends on recall-ranking organs; composes onto existing trust_tier/provenance plumbing |

**Sequence:** 1 (instrument) → **2 + 3 (the core pair that collapses the symptom: floor removes the flood, anchor supplies the figure)** → 6 → 7 → 8. Drop 5; deprioritize 4.

## Reuse-this (the fix is mostly ACTIVATION, not new build)
- `dialogue_anchor_items` (focused_cognition.py:618-653) — complete helper; Slice 3 just calls it unconditionally + ranks it.
- Recall shadow plumbing (`_shadow_log_living` 2369; shadow_promotion 2042-2047) already logs per-candidate distances — Slice 2 hooks straight in.
- The proven-good continuity path (the 22:39 turn: citation 1.0, source_types=dialogue_anchor, 0 memory) — Slice 3 generalizes existing working behavior.
- `check_groundedness` (1475-1496) — Slice 1 adds a parallel metric alongside.
- `turn_has_fresh_evidence` + support_gate_scope boundary — Slice 7 keys its switch off the same boundary.
- Organ-1 shipping template (LIVE_WITNESSED 2026-06-18) — clean separation (env_flags + llm_client + stdlib only).
- project_conversation_coherence_organ design — Slice 6's receipt already specified.

## Do-not-repeat (covenant guardrails)
- NO big-bang organism switch-over (the NO-GO @23a22ad passed static review, FAILED live with an owner HTTP-401 lockout). Incremental, single-flag, shadow-first, live-witnessed only.
- DON'T touch owner-private auth / S7 internal-channel token / web-owner spine (the exact lockout seams). Mirror Organ-1 clean separation.
- DON'T fix via body-telemetry/perception_signature or rely on the git cleanup — wrong path.
- DON'T fold into evidence-precedence (scoped to self-capability; lived memory is sacred/unranked there).
- DON'T regress support-gate-scope — Slice 7 must keep the verifier off the recall-only voice.
- DON'T blind/delete memory — every lever is recall-time **salience deweighting** (curtain not muzzle, surface-and-ask).
- DON'T hardcode the relevance threshold — learned organ keyed off recall-outcome feedback (hardcode the loop, not the conclusion).
- DON'T keyword-gate meaning to pick anchor turns (Alexa-reflex) — always-thread/always-anchor needs no classification.
- DON'T swap the voice-card opinion for a different hardcoded opinion — free voice that follows turn-shape; two-sided care.
- DON'T trust merged/static-trace as witness — content-light receipt on the live assembled prompt + witnessed live reload (new pid).
- DON'T read citation_coverage=0.125 as clean 88%-ungrounded until Slice 1 lands.
- Commitment receipt must be a TRUE sidecar written at offer-time, never a vibe inferred from text (no-fabrication).
