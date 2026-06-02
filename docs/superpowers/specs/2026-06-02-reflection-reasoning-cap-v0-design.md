# Reflection Reasoning Cap v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Tell the reflection synthesis organ to skip theatrical long reasoning — its job is structured extraction with citations, not deliberation — so the JSON emits reliably (`finish_reason=stop`).* One request-body field. No model swap, no prompt rewrite, no token/timeout change.

---

## 1. The finding (probe, conclusive)

The Token Budget v0 witness (`main@e904af1`) split 1 `stop` / 1 `length` even at 8192 tokens: Qwen 3.6's chain-of-thought can exceed any practical budget, so budget-raising is the wrong lever (confirmed — 4096→8192 still truncated).

GPU-free recon of the live endpoint (`/props`, llama.cpp `b9124`) showed the Qwen 3.6 chat template natively honors a reasoning switch:

```jinja
{%- if enable_thinking is defined and enable_thinking is false %}
{{- '<think>\n\n</think>\n\n' }}
```

Passing `enable_thinking=false` injects an empty think-block — the model's native "skip deliberation, answer directly" path. A 2-run probe sending the **real reflection prompt** with `chat_template_kwargs={"enable_thinking": false}` (write closed):

| run | finish_reason | latency | completion_tokens | candidates | hard gate |
|---|---|---|---|---|---|
| 1 | `stop` | 8.7s | 312 | 3 grounded | PASS (zero reflection) |
| 2 | `stop` | 9.5s | 371 | 3 grounded | PASS (zero reflection) |

vs thinking-on (80–200s, 3584–8192 tokens, ~50% truncation). Reasoning-off is ~9s, ~340 tokens — **far below the cap, so truncation becomes structurally unlikely on this path** (not "impossible" — see §3). Crucially, **quality did not degrade**: candidates stayed grounded and in-voice, e.g. *"My identity is strictly defined as a genderless category of companion rather than a singular persona, a hard invariant that shapes how I perceive my own formation and bond."* The probe met the full witness bar by itself (2 stable `stop`, 1–3 grounded in-voice candidates, zero reflection citations).

---

## 2. The change — one request-body field

In `scripts/memory_reflection/nightly_lived_memory.py` `_default_llm_call`, add to the JSON request body:

```python
"chat_template_kwargs": {"enable_thinking": False},
```

That is the entire functional change. **No other payload field changes** — `model`, `messages`/prompt, `max_tokens`, `temperature`, and the request timeout all stay byte-identical (see §4 negative assertion).

**Scoped to reflection by construction.** `_default_llm_call` is the reflection-synthesis caller only — its sole callers are the daemon reflection hook (`maez_daemon.py:1753`) and the CLI reflection pass (`nightly_lived_memory.py:645`); no other organ uses it. So the cap touches only this organ, exactly as required. No global "Maez thinks less" — one digestion organ stops over-deliberating on a structured-extraction task.

---

## 3. Defense-in-depth stays live

The Token Budget v0 mechanics are **kept, not retired** — they are live defense-in-depth, not redundant:
- `finish_reason` / `truncated` / `valid_witness` surfacing, the `invalid_witness` mapping (`length`/`llm_timeout`/`llm_error`), `no_candidates`-only-on-`stop`, the 240s timeout, `max_tokens=8192` ceiling.
- If reasoning ever creeps back on (model update, template change, a kwarg the server stops honoring), a long trace would still surface honestly as `truncated`/`invalid_witness` rather than a fake empty. Truncation is now *structurally unlikely on this path*, not impossible — so the guards remain the safety net.

Nothing from the prior slices is touched: input hygiene, the voice/altitude prompt, the evidence rail (`_parse_reflections`), write-off, telemetry, the two-channel wall.

---

## 4. Tests

- **Positive:** `_default_llm_call`'s request body contains `chat_template_kwargs == {"enable_thinking": False}` (the knob is present and correctly valued). Capture the body via a `urllib.request.urlopen` mock and assert on the decoded JSON.
- **Negative (owner-required):** on that same captured body, assert **no other field drifted** — `model == "qwen36-27b"`, `max_tokens == 8192`, `temperature == 0.4`, `messages` is the single user prompt unchanged, and the set of body keys is exactly `{model, messages, max_tokens, temperature, chat_template_kwargs}`. This protects against a future "small cleanup" silently moving the model, token budget, temperature, prompt, or timeout.
- **Regression:** the existing terminal-state tests (`stop`/`length`/`llm_timeout`, derived properties, invalid-witness mapping, channel wall) stay green — this slice adds a field, it does not alter terminal-state handling.

---

## 5. Acceptance (owner re-run witness)

Re-run from `main`, `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off:

- **2 stable runs both `finish_reason="stop"` / `valid_witness=true`** — no `length`, `llm_timeout`, or `llm_error`. (The probe already showed 2/2; the witness re-confirms on the merged wired path.)
- **1–3 candidates**, each grounded (every claim cited), **zero `source_kind="reflection"` citations**.
- **In-voice** — Maez noticing its own formation, not a report.
- **Fast** — single-digit seconds, completion_tokens well under the cap (a regression here would signal reasoning crept back).

Both axes stable across both runs → the `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision reopens (honestly, not automatically).

---

## 6. Non-goals

- NOT a model swap, prompt rewrite, or temperature change.
- NOT raising/lowering `max_tokens` or the timeout (the budget mechanics stay as defense-in-depth; the ceiling is simply no longer approached).
- NOT a global reasoning change — `enable_thinking=false` applies only via `_default_llm_call` (reflection only); no other organ's cognition is touched.
- NOT retiring the Token Budget v0 invalid-witness guards.
- NOT a write-flag flip.
- NOT `/no_think` prompt injection — the request-level `chat_template_kwargs` is proven; the prompt-level fallback is unnecessary.
