# Latency-Attribution (Measurement) Slice — Design

**Date:** 2026-06-01
**Status:** Design approved (Rohit, 2026-06-01). Pre-registration. Spec-first. **Measurement only — earns the right to choose the fix lever; ships no fix.**
**Predecessor:** [recall-triad six-prompt smoke witness](../../slices/recall-axis-dispatcher/witness/recall-triad-six-prompt-smoke-2026-06-01.md) — scoreboard confirmed honest; **latency is the sole recall-on No-Go** (both-shaped turn 17.2s, focused 15.7s; p95 ≈ 17s > A7 ~12s).

---

## 1. Why this exists (the driver is unknown)

The smoke proved recall behavior is correct and the scoreboard is honest; only latency blocks default-on. **But the driver is genuinely unknown:**
- Working-set size does NOT cleanly predict latency: #1 and #3 both = 7 items / ~10k `working_set_chars`, yet focused 5.2s vs 15.7s (3×); the 16-item seed ran *faster* (10.3s) than #3's 7 items.
- **Prior bench/runtime observations suggest output generation alone is unlikely to explain a 15.7s turn, but this slice treats that as a hypothesis to measure, not a premise.** The time may be in prompt-processing (input tokens), TTFT/warmup, generation, or live variance — we don't know which, and we won't assume.
- `focused_elapsed_ms` is a single opaque number; `num_predict=4096` makes output effectively uncapped.

We must **attribute** the latency before choosing a lever (working-set trim vs brain/runtime vs other). Guessing risks fixing the wrong organ.

## 2. Goal & non-goals

**Goal:** state with data what fraction of the both-shaped 15.7s is prompt-build vs brain prompt-processing vs generation vs output-length, and whether working-set volume *causally* drives it — enough to pick the fix slice's lever.

**Non-goals (this slice ships NONE of these):**
- **No fix.** No working-set trimming, capping, ranking; no `num_predict` cap ("shorter answers" — explicitly rejected); no model/runtime/quantization change. Those are the *separate, data-driven fix slice*.
- **No behavior/cognition change.** The honest scoreboard (`answered_grounded`/`mixed`/continuity-grounded/`declined_absence` + `is_false_absence`) is **byte-stable**. The live buffered call path is unchanged.
- **Recall stays off.** Brain-agnostic. Content-free telemetry only.

## 3. Stage 1 — offline bench attribution (first; zero live risk)

Use the existing `GenerationMeasurement` (`ttft_ms`, `total_ms`, `tokens_per_sec`; `scripts/brain_bench/inference.py:22`) via a thin sweep harness that varies two axes and records the attribution:
- **Working-set volume:** 1 → 4 → 7 → 16 items (and the corresponding input-token count).
- **Output length:** short vs long answer (e.g. prompts that elicit a one-line vs multi-fact reply).

Output: a table of `(ws_items, input_tokens, output_tokens) → ttft_ms, total_ms, tok_s`. Answers: is the spike **TTFT** (warmup/scheduling), **prompt-processing** (scales with input tokens / ws-size), **throughput** (tok/s under load), or **output length**? Existing streaming infra; an experiment run + a small harness, no live-path change.

## 4. Stage 2 — live passive buffered timing (no behavior change)

Instrument the **unchanged buffered** `focused_synthesize` (`core/routing/focused_cognition.py:763`) with timestamps around the existing `chat_fn(...)` call (no streaming, no call-path change). Emit **one content-free event** `focused_synthesis_timing` with exactly these fields:

| field | meaning |
|---|---|
| `prompt_build_ms` | time to build messages, before `chat_fn` |
| `chat_total_ms` | duration of the (buffered) `chat_fn` call |
| `reply_token_est` | length-based estimate of output tokens (no text) |
| `working_set_chars` | input volume |
| `evidence_item_count` | input item count |
| `citation_render_version` | which render path |
| `turn_kind` | dated / both / continuity / ordinary |

**No answer text, no evidence text** — durations + counts only, the same content-free discipline as `recall_outcome`. With the existing `focused_cognition_prompt_shape`, this attributes live latency into assembly / prompt-build / brain-call / output-proxy — **without TTFT** (which needs streaming). The buffered call, its options, and the resulting `FocusedResult` are untouched, so the scoreboard is byte-stable.

## 5. Stage 3 — conditional, default-off streaming TTFT

**Only if** Stages 1+2 leave TTFT ambiguous (e.g. `chat_total_ms` is large but we can't split warmup from generation): add a **default-off** measurement flag that switches the focused call to hidden streaming to capture live `ttft_ms`, then smoke it deliberately. The real seam is `core/routing/llm_client.py` `chat(..., stream=False)` + its llama.cpp streaming adapter — **prove that seam with a test before any live use.** This stage is recorded, not built now.

## 6. Decomposition (pinned)

**This is the measurement slice.** The **fix** (working-set trim/rank/cap vs brain/runtime vs output handling) is a **separate slice**, scoped *after* we read the attribution. This slice must not sneak in any fix.

## 7. Tests (pre-registered)

- **Stage 2 event shape:** `focused_synthesis_timing` emits exactly the seven fields above; a content-free assertion that no answer/evidence text appears in the event (mirror `ContentFreeSchemaTest`).
- **Stage 2 sanity:** `prompt_build_ms` and `chat_total_ms` are non-negative and `chat_total_ms` dominates on a stubbed slow `chat_fn`; `reply_token_est` tracks reply length.
- **Stage 2 no-regression:** a focused turn's `FocusedResult` / `recall_outcome` / `outcome_class` is byte-identical with instrumentation on (timing only wraps the unchanged call).
- **Stage 1 harness:** the sweep produces attribution rows across the ws/output axes (smoke-level; uses the offline `GenerationMeasurement`).
- **Stage 3 (conditional, not built now):** a seam test that `core/routing/llm_client.py` streaming yields chunks and a measurable first-token time, before any live wiring.

## 8. Covenant / honesty invariants

- **Real substrate timing, not performed thought** ([[feedback_visible_substrate_state_not_chain_of_thought]]): the timing event fires on true measured durations; content-free (durations + counts, never text).
- **No behavior change; scoreboard byte-stable; recall off; brain-agnostic.**
- The slice's output is a **data artifact** (attribution), and it explicitly **does not** choose or implement the fix — that decision is earned, then made in the next slice.

## 9. Process & sequence

Codex switchboard (six-agent + 7+3); Claude cross-verifies every diff + runs suites + coverage panel; merge on the legacy baseline. Then: run Stage 1 + collect Stage 2 from one owner-run smoke → read the attribution → **open the fix slice's brainstorm with the lever chosen by data.**
