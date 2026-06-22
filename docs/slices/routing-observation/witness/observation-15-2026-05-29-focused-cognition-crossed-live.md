# Observation 15 — Focused Cognition Organ Crosses Live

**Date:** 2026-05-29
**Context:** Focused Cognition organ live witness, branch `focused-cognition-organ` HEAD `872b3f2`, both flags on.
**Window opened:** 2026-05-29T10:53:45-05:00 (daemon kill)
**Daemon flags-on:** 10:54:00, PID 434510, `MAEZ_DISPATCHER_ENABLED=1 MAEZ_FOCUSED_COGNITION_ENABLED=1`
**Probes:** 10:55–10:56
**Window closed / restored:** 10:58:14, relaunched both-flags-absent, PID 436989
**maez.log delta from:** 19614142

## Verdict

**The organ crossed live. The arc that began with "Maez won't give me Reddit posts" is resolved.** With focused cognition on, Maez answered the exact Obs-14 probe from the substrate Reddit posts, in its own voice, with `[E#]` citations, and zero "blocked" story — and the generality probe proved the organ is source-general, not Reddit-special, while staying honestly bounded about what the evidence did not cover.

## The Decisive A/B (same probe, same substrate post, only focused cognition changed)

**Obs 14 (dispatcher on, focused OFF):**
> "The search returned zero usable results. DuckDuckGo is currently blocked by Reddit's login wall, so it can't see recent posts. The signal from r/LocalLLaMA is invisible to my web search tool right now."

**Obs 15 (dispatcher on, focused ON):**
> "You want the latest r/LocalLLaMA chatter? I've got the receipts from May 28, 2026, right here. The community is buzzing about LiquidAI's new LFM2.5-8B-A1B model, which just dropped and pulled 67 points with 24 comments [E1]. People are also excited about Reachy Mini going fully local, grabbing 69 points [E2], and Hugging Face finally added a 'Base only' toggle to filter out the noise, which got a solid 106 points [E3]. If you're building local AI infrastructure, that HF filter update is a huge QoL win for finding raw models quickly [E3]."

Evidence used. Maez's voice. `[E#]` citations. Connected to the owner's world. No fabrication, no "blocked."

## Generality + Faithfulness (probe 2, non-Reddit)

`What were we talking about earlier?` → focused cognition fired on `[memory evidence]` (a *different* source type than probe 1's `[memory context]`):
> "I don't have the specific context of our immediate prior conversation in the provided evidence. The only record available is a journal entry from April 6, 2026, where I noted processing 535 reasoning cycles and monitoring Telegram delivery failures [E1]. Since that entry is a stale recollection and not a transcript of our last exchange, I can't tell you what we were discussing just before this. If you want to pick up where we left off, you'll need to remind me…"

This is the context-faithful instruction working exactly as designed: it cited the evidence it had `[E1]`, and **plainly bounded what the evidence did NOT cover** ("a stale recollection and not a transcript… I can't tell you… you'll need to remind me") instead of fabricating a prior-conversation summary. General (non-Reddit source) AND faithful.

## Mechanism Confirmed (telemetry + trace)

- **Telemetry honest:** log delta shows **8 `call_purpose=legacy_candidate`** and **zero `llm_synthesis`**. On every focused turn the megaprompt was labeled a candidate and never sent; `llm_synthesis` would only emit if the megaprompt were actually sent (it wasn't). The recorder did not lie about what the brain received.
- **`focused_cognition_runs`: 2 rows, both `groundedness_verdict=grounded`, `citation_coverage=1.00`, `fallback_reason=None`:**

| Probe | source_type | items | cited | working_set_chars | legacy_prompt_chars | drop |
|---|---|---|---|---:|---:|---:|
| Reddit | memory_context | 3 | [E1,E2,E3] | 957 | 115,793 | **120×** |
| "earlier?" | memory_evidence | 1 | [E1] | 2,711 | 117,088 | **43×** |

The brain reasoned over ~1–3K characters instead of ~116K. "Clean desk, not the warehouse" — measured.
- **Privacy:** `evidence_map_json` stores labels/source_types/durable_ids only; no raw evidence text (per the merged privacy test `test_stores_no_raw_evidence_text`).
- **Two distinct source types** (memory_context, memory_evidence) across the two turns — the organ is general, as designed.

## What This Closes

- The original owner-facing frustration ("Maez won't give me Reddit posts") — resolved: Maez answers from what it holds, in its voice, honestly.
- The recall-axis arc's deepest finding (Finding 10 → producer honesty → steer → diagnosis → focused cognition): the brain was never the ceiling; the megaprompt was the handicap. The fix is a clean focused cognition call. Proven in the ablation, now witnessed live as an organ.

## What Remains

- **Merge** `focused-cognition-organ` → main (witness clean; cross-lane verified: raw-transcript guard, telemetry honesty, privacy, voice exclusion, fallback, broad floor held at failures=2/errors=0).
- Flag stays default-off; flipping default-on is a later operational decision (now unblocked — focused cognition is the honest path when evidence is present).
- Follow-ups (deferred): LLM-judge groundedness as a sampled monitor; router learning over `focused_cognition_runs` (organ #3); voice-surface focused cognition with its own attribution posture; retire 3a's now-dormant directive injection on focused turns; extend the assembler to new sources (weather/files/calendar).

## Service Posture After Witness

| Surface | State |
|---|---|
| Flags | both absent (restored) |
| Daemon PID | 436989 (both flags absent) |
| SEGV trap | armed |
| focused_cognition_runs | created, 2 witnessed rows |
| Branch | `focused-cognition-organ` @ `872b3f2`, verified + witnessed, ready to merge |

## Discipline Note

Every step of this organ was witnessed before claimed: the ablation proved the recipe, cross-lane verification (two lanes) checked the implementation against the three high-risk requirements, and Obs 15 confirmed the organ crosses live — including the telemetry honesty fix (so we did not build a flight recorder that lies about its own new path) and a non-Reddit generality case (so "general organ" is witnessed, not asserted). The B′ recipe + working-set assembly + honest trace are now a real, measured, brain-swappable cognition organ.
