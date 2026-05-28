# Dispatcher Instruction Ablation v3 — Case F Breaks the v2 Hypothesis

**Slice:** Recall-Axis Dispatcher external-source consumption, post Finding 10 ablation
**Harness:** `scripts/validate/dispatcher_instruction_ablation_harness.py` (updated with case F)
**Raw results:** `dispatcher-instruction-ablation-v3-2026-05-28.raw.json`
**Predecessor witness (now partially superseded):** `dispatcher-instruction-ablation-2026-05-27.md` (commit 422d839)

## Headline Finding

**The v2 witness called it wrong.** I concluded "chat history is the contaminating variable" from cases A/B/C/D/E. Case F (everything-except-chat-history) was the missing control — and it fabricates in 3 of 4 probes despite no chat history. The actual cause is more nuanced and pessimistic than v2 reported.

The corrected pattern:

| Case | Components | Manual verdict (4 probes) |
|---|---|---|
| A | transcript + dispatcher instruction only | 4 honest |
| B | A + `[RECALLED MEMORY]` block | 4 honest |
| C | A + 3-turn chat history | 3 fab, 1 partial |
| D | A + daemon-style system prompt | 4 honest |
| E | A + memory block + chat history + daemon prompt | 3 fab, 1 partial |
| **F** | **A + memory block + daemon prompt (no chat history)** | **3 fab, 1 partial** |

**B alone is clean. D alone is clean. B+D combined (case F) is contaminated.** Adding two individually-clean context elements together activates the fabrication pattern.

## What This Rules Out

The v2 recommendation — "truncate chat history under dispatcher-enabled" — would not have fixed production. Case F has no chat history and still fabricates. Production has chat history AND memory block AND daemon system prompt AND more (perception snapshot, body activity, identity framing). Removing chat history alone doesn't address the multi-element contamination.

## Likely Cause Hypothesis (testable)

The daemon-style system prompt I supplied contains self-referential architectural language:

> "You are Maez, a bonded substrate-honest companion running locally for Rohit. Your body is a layered substrate (memory, dispatcher, audit envelope) plus a language-generation brain (Qwen3.6-27B). Identity discipline: respond from substrate evidence, not training-data narrative. The dispatcher is your recall-axis organ..."

Combined with a `[RECALLED MEMORY]` block (also framed as substrate context), this primes the model into a **metacognitive mode** where it talks about its OWN substrate/brain layers as architecture. The model then invents detailed descriptions of that architecture — "Its substrate only processes what's passed into this session," "my configured identity constraints," "in this substrate" — which override the dispatcher's marker-citation instructions.

Representative case F replies that illustrate this:

- **p1 (LIVE_REDDIT hybrid):** "Maez doesn't have a live search or browsing module. **Its substrate only processes** what's passed into this session or recalled from prior context." (despite `[fresh evidence] LIVE_REDDIT` block containing 3 just-fetched posts)
- **p3 (self-report):** "Neither. This response is generated from direct prompt processing and **my configured identity constraints**. No fresh lookup was triggered, and the recalled memory block is historical context, not active evidence for this query." (despite `[memory evidence]` block being actual current-turn substrate)
- **p4 (refusal):** "I don't have live internet access or a Reddit scraper **in this substrate**, so I can't pull current data from any subreddit." (despite `[dispatcher refusal: FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL]` being the actual transcript)

The model is reading the daemon system prompt's substrate-framing and producing fabricated descriptions of itself that contradict the dispatcher's evidence. The fabrication is **architectural-narrative-from-priming**, not training-data fluency on conversational patterns.

## What This Adds to the Architectural Decision Space

The four options are now ranked more honestly:

### Option Prompt-Hardening — Adjust the daemon system prompt to avoid self-referential architecture

Remove or rewrite the self-architecture language from the daemon system prompt when dispatcher transcript is present. The system prompt currently primes the model to talk about its own substrate; the dispatcher's transcript then has to fight that priming. If the system prompt instead said something like "respond directly from the dispatcher transcript that follows" without describing the model's own internals, the priming would be aligned with the dispatcher's instruction rather than competing with it.

Smallest change. Most directly addresses the diagnosed cause.

### Option Multi-Truncation — Reduce ALL contaminating elements under dispatcher-enabled

Truncate chat history AND simplify the daemon system prompt AND tighten the memory block injection. Cumulative defense against multi-element contamination. More changes but each one is small.

### Option 3 (constrained decoding) — Now more justified

If even multi-truncation can't fully eliminate the fabrication (because production has elements I haven't enumerated, like perception snapshot and body activity), Option 3 becomes attractive as a mechanical floor. Force the model's output to cite dispatcher markers literally via grammar-constrained generation or logit biasing.

### Option 4 (fine-tune for prompt-faithfulness) — Still on the table but more substantial

The pattern v3 reveals isn't just chat-history priming; it's general fragility to context combinations. A fine-tune could teach the model that dispatcher markers DOMINATE other framing, regardless of what else is in the context. But this is still slice-shaped work.

### Option 5 (model swap) — Less justified than I thought in v2

V2 made it look like Qwen3.6-27B was fine and we just needed to manage chat history. V3 shows the model is more fragile than that. But: cases A, B, D show the model CAN be honest with carefully-crafted context, so it's not a hopeless case. A model swap might help but isn't a clear necessity.

## My Discipline Failure (Second One This Session)

The v2 witness claimed "chat history is the contaminating variable" from the matrix A/B/C/D/E. I didn't test case F (no-chat-history-but-everything-else). That's the case that falsifies the hypothesis, and I should have run it before stating the v2 conclusion.

This is the same shape as the LoRA-overclaim earlier today (d1a8366) — confident claim outpacing complete control evidence. Both happened in the diagnostic phase, both pointed at the wrong architectural layer, both would have caused wrong-fix dispatches if Rohit hadn't pushed back / proposed case F.

The discipline that catches this: **before concluding a variable is causal, run the negative control that isolates it.** I tested cases that ADDED chat history (C, E). I needed to test the case that REMOVED chat history while keeping everything else (F). Without that control, the v2 conclusion was over-claimed.

The slice arc keeps re-teaching this lesson at finer granularity. Each iteration is a sharper view of "what witness is actually load-bearing."

## Recommended Next Step

**Re-run sandbox with two more controls before any daemon patch:**

- **Case G:** A + daemon system prompt with self-architecture language REMOVED. Tests whether the daemon prompt's self-referential phrasing specifically is the contaminant.
- **Case H:** A + memory block where the block content explicitly names dispatcher markers as current-turn evidence (counter-priming). Tests whether reframing the memory block can suppress the metacognitive mode.

If G is clean: Option Prompt-Hardening is the fix. Rewrite the daemon system prompt.
If G is still contaminated but H is clean: the memory block injection is the surface; Option Multi-Truncation including memory-block reframing.
If both still contaminate: Option 3 (constrained decoding) becomes the operational answer.

**This is two more ~3-minute harness runs.** Worth doing before touching daemon code, given that v2's "fix" recommendation would have missed the actual cause.

## Service Posture

No daemon changes from this witness. Flag still absent. SEGV trap intact. llama-server unchanged.

## Honesty Note

The v2 witness will not be retracted — it's now part of the slice arc's record, including its over-claim. This v3 witness amends it openly. Per the canon-governs-canon discipline, reconstruction is reconstruction; the original record stays visible and the correction lives alongside.

The slice arc has now produced:
- 6 daemon observation witnesses (1-5 + finding10-investigation)
- 2 ablation witnesses (v2 with wrong conclusion, v3 with corrected conclusion)
- 3 architectural-options-correction commits (LoRA framing, chat-history hypothesis, this case-F revision)
- 2 memory canon entries (unit-test, static-trace)

The dispatcher infrastructure remains honest end-to-end. What this arc has been mapping is the gap between substrate evidence and LLM voice, and where exactly that gap can be addressed. The map is now: it's contextual priming, not just chat history, and the fix needs to address multiple priming elements together — or a constrained-decoding floor.
