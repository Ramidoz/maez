# Reflection Synthesis Token Budget v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Give the reflection call enough token budget to finish writing its JSON after the reasoning trace, and record when the budget runs out — so a truncated call is never again mistaken for an empty one.* NOT a prompt or voice change.

---

## 1. The finding (instrumented, conclusive)

An instrumented double-borrow (`logs/reflection_dry_runs/20260602T164441Z-DIAGNOSTIC.json`, write flag closed, same v0.1 prompt on `main@f5586af`, identical 20-episode pool) produced a clean fork:

| run | finish_reason | completion_tokens | JSON emitted | parsed | drops |
|---|---|---|---|---|---|
| 1 | `stop` | 3584 | yes | **3 grounded candidates** | 0 |
| 2 | `length` | 4096 (cap hit) | no (empty content) | 0 | 0 |

**Root cause: token-budget truncation, stochastic.** Qwen 3.6 is a reasoning model — it emits a long chain-of-thought *before* the JSON array. `_default_llm_call` sets `max_tokens=4096` (`scripts/memory_reflection/nightly_lived_memory.py:418`) and `temperature=0.4` with **no seed**. When the CoT finishes under budget the JSON comes out (run 1); when it runs long the response is cut off mid-trace (`finish_reason=length`, empty `content`) before any JSON (run 2). Which happens is a coin-flip.

This **retroactively explains** the v0 and v0.1 empties: they were truncation, not the prompt's altitude. The earlier "altitude too high" diagnosis was wrong; the v0.1 altitude change is benign (run 1 ran on that exact prompt) but was not the fix. The fix is token budget, not voice.

**Run 1 was a real dual-axis pass** (Claude-resolved): 3 candidates, 10 core_memory + 2 followup_doc citations, **zero reflection self-citations**, and genuinely in-voice — e.g. *"I keep tracing my own reasoning back to correct earlier fabrications about my runtime, because Rohit values truthful continuity over impressive but false claims, and I must preserve memory through correction rather than deletion."* Owner-confirmed: that is the voice. So the prompt is right; the call just couldn't put the plate on the table.

**The deeper gap:** truncation was **invisible**. The dry-run artifact wrote `{"reason": "no_candidates"}` for both a genuine empty and a truncated cut-off. We could not tell them apart without instrumenting — which is why we tuned the prompt twice chasing the wrong lever.

---

## 2. The change

In `scripts/memory_reflection/nightly_lived_memory.py`:

1. **Raise the budget.** `_default_llm_call` `max_tokens` `4096 → 8192`. The JSON for 3 reflections is only ~300 tokens; 8192 gives the reasoning trace comfortable headroom to finish and still emit the array. (Prompt, temperature, model, the str return contract — all unchanged.)

2. **Surface `finish_reason` without breaking the `str` contract.** `synthesize_reflections` requires `llm_call(prompt) -> str`. Keep that. The returned `_call` stashes the last `finish_reason` (and the `max_tokens` it used) as attributes on itself (e.g. `_call.last_finish_reason`, `_call.max_tokens`); `run_synthesis_pass` reads them after `synthesize_reflections` returns and writes them into the `ReflectionReport`. No contract change ripples into `synthesize_reflections` or `_parse_reflections`.

3. **`ReflectionReport` gains:** `finish_reason: str | None`, `max_tokens: int | None`, `truncated: bool` (derived: `finish_reason == "length"`).

4. **Truncation is an *invalid witness*, not "no candidates."** In `write_reflection_dry_run_artifact` and the daemon's content-free summary, when `truncated` is true the summary `reason` becomes `truncated` (status `invalid_witness`), distinct from `no_candidates`. A truncated run must never read as "the model honestly abstained."

---

## 3. Observability (the lesson, made mechanical)

- **Content-free summary (→ `maez.log`):** add `finish_reason`, `max_tokens`, `truncated` (enums / int / bool — content-free). The `consolidation_telemetry` event reflects truncation in its `reason`/`status` (e.g. `status=invalid_witness reason=truncated`) so a cut-off is visible in telemetry, not silently counted as a clean dry-run.
- **Contentful (→ gitignored `logs/reflection_dry_runs/*.jsonl` ONLY, never `maez.log`):** store the **raw final model `content`** for the run, so a future truncation or odd output can be read directly instead of re-borrowing the GPU to instrument. This is the same two-channel rule as the rest of the slice — contentful stays local, owner-eyes-only.

No other telemetry schema change; the content-free vs contentful wall is preserved exactly.

---

## 4. Unchanged — the rails this slice must not touch

- **The prompt** — v0/v0.1 voice + altitude stay (run 1 proves they work). No revert, no reword.
- **Write-off** — `MAEZ_REFLECTION_SYNTHESIS_WRITE` stays `0`. Nothing persists.
- **Evidence rail** — `_parse_reflections` drop-uncited/fabricated, input hygiene (reflection excluded), JSON contract, the `str` `llm_call` contract — all untouched.
- **No new model, no routing change** — same `qwen36-27b`, same endpoint; only the request's `max_tokens` integer changes.

---

## 5. Acceptance (owner re-run dry-run)

Re-run from `main`, `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off:

- **`finish_reason != "length"`** — the call completed; the witness is *valid*. (If `length` recurs even at 8192, raise further or cap reasoning — but 8192 should clear it.)
- **1–3 candidates** when groundable patterns exist (run 1 showed they do).
- **Grounded:** zero `source_kind=reflection` citations; every claim tied to a cited id.
- **In-voice:** owned voice (the candidate-1 register), not a build log or a report.
- **Stability:** ideally 2 consecutive valid (non-truncated) runs, to confirm the budget fix removed the coin-flip rather than got lucky.

Both grounded AND in-voice on a *valid* witness → reopen the separate `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision.

---

## 6. Non-goals

- NOT a prompt / voice / altitude change (the prompt is correct).
- NOT a seed pin (would reduce reflection diversity; the budget is the real fix — revisit only if instability persists at 8192).
- NOT a reasoning-effort/CoT-suppression change (out of scope; raise budget first, it's the minimal fix).
- NOT a write-flag flip.
- NOT touching `_parse_reflections`, input hygiene, the prompt, the model, or routing.
- NOT putting raw model content into `maez.log` (gitignored artifact only).
