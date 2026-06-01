# Brain Gateway (QoS / Priority Preemption) — Design

**Date:** 2026-06-01
**Status:** **Approved** (Rohit, 2026-06-01) — Codex-reviewed twice; the 7+3 pins folded; fresh Brain Gateway, not DND extension. Pre-registration. Spec-first.
**Predecessor:** [recall-triad six-prompt smoke witness](../../slices/recall-axis-dispatcher/witness/recall-triad-six-prompt-smoke-2026-06-01.md) + the 2026-06-01 latency attribution (sweep + K-sample + abort probe). **Root cause data-locked:** Maez's own autonomous cognition cycle (~every 57-60s) makes ~21s brain call(s) on the single llama-server slot (`--parallel 1`); a foreground recall turn colliding with a cycle queues ~21s. The abort probe proved cancelling a *streaming* call frees the slot in ~230ms. This slice is the proven cure.

---

## 1. Why this exists

The recall-on latency No-Go is **GPU-slot self-contention**, not memory design (working-set trim refuted by the sweep; output length is a steady ~33 chunks/s; the spikes are periodic). Maez has only a partial, wrong-shaped defense: `_rohit_active_until` (a 15s *timestamp guess*) that the cycle checks before starting, plus an ad-hoc `_ollama_lock`. These are a **warning sign, not traffic control** — they don't preempt an in-flight call and don't cover the recall path. The fix is an **event-driven priority scheduler**: when a foreground request arrives, an in-flight background call is preempted so the owner's turn gets the slot immediately.

## 2. Goal & non-goals

**Goal:** a foreground (owner-visible) brain call gets the slot within ~hundreds of ms even while background cognition is active — because the gateway preempts the in-flight background call. Recall-relevant p95 falls under the A7 ~12s ceiling **with cycles running**.

**Non-goals (explicit):**
- **NOT MTP** (separate later headroom/quality slice). **NOT Jetson** (stays vision/voice). **NOT a vLLM/SGLang migration** (they validate the shape; local llama.cpp has the primitives).
- **NOT thinning/silencing Maez's inner life** — the cycle's thought is *rescheduled*, not deleted; aliveness preserved.
- **NOT a brain-call-ontology rewrite** — classify incrementally; untouched legacy/offline paths stay `neutral`.
- **Does NOT enable recall** — recall stays off; this unblocks the *future* recall-on gate.

## 3. Architecture — the Brain Gateway

**One module owns access to the 27B server.** Every important brain call routes through it as a *typed* request. The gateway is a small in-process priority scheduler shared by the foreground (`handle_message`) and background (cycle) threads.

**No side door (pin #8):** "owns access" must be *mechanical*, not aspirational. Either `llm_client.chat` itself routes through the gateway, or every classified live path is forced through it — and a **test proves no direct `_chat_llamacpp` / raw-backend bypass exists on any owner or cycle path.** A single bypass defeats the traffic controller.

### 3.1 Closed purpose taxonomy → derived priority (anti-laundering)
Callers do **not** pass arbitrary `"foreground"`/`"background"` strings. They pass a value from a **closed `BrainPurpose` enum**; the gateway *derives* priority. (A caller asserting its own priority would be the same laundering hole as a caller asserting its own grounding.)

- **Foreground (high priority, preempts):** `owner_reply`, `owner_recall`, `voice_reply` — and these must cover **every brain call on the owner-message → visible-reply path**: tool/intent planning, recall synthesis, final synthesis, voice reply. Any owner-turn call left `neutral` moves the bug sideways.
- **Background (low priority, preemptible):** `daemon_cycle_generation`, `daemon_cycle_audit_judge`, `daemon_cycle_rewrite`, `daemon_cycle_retry` (+ any other autonomous-cycle call sites enumerated during implementation).
- **Neutral (no priority, neither preempts nor is preempted):** untouched legacy/offline callers not yet classified.

**Nested-call propagation (pin #5):** purpose must propagate to **nested** `llm_client.chat` calls. If `daemon_cycle_generation` invokes audit/judge/rewrite/retry through helper modules, those nested calls **inherit `background`** — e.g. via a thread-local / context-var "active purpose" the gateway reads — so there is **no unlabeled nested `llm_client.chat`.** Symmetrically, nested calls under an owner turn inherit `foreground`.

**Propagation must survive thread/executor boundaries (pin #9):** the owner path uses executor/thread handoffs (`run_in_executor`), and `contextvar` context is **NOT** auto-copied into executor threads (unlike asyncio tasks). So the plan must either (a) explicitly carry the purpose across the handoff, or (b) set the purpose **inside** `handle_message` / the cycle entry on the same thread the brain call runs on. A test proves a nested call across the real `run_in_executor` / cycle shape keeps its purpose and does **not** silently fall back to `neutral`.

**Invariant (load-bearing, tested BOTH directions): zero `neutral` brain calls inside the autonomous cycle, AND zero `neutral` brain calls on the owner-turn reply path.** A single unclassified call on either side (the cycle's judge, or a tool-planning call on the owner path) lets the No-Go survive sideways. Tests enumerate both call-site sets and assert none resolve to `neutral`.

### 3.2 Scheduling + preemption
- **Foreground arrives → any in-flight background call is preempted** (cancelled), then foreground takes the slot.
- **Background starts only if no foreground is active/queued** (the event-driven successor to the cycle's `acquire(timeout=0)` defer).
- **Foreground vs foreground:** FIFO on the single slot (no same-priority preemption).
- `_rohit_active_until` is **demoted to an input hint / log signal only** — never the decider. The gateway reacts to the real foreground-request *event*.
- `_ollama_lock` is **retired or wrapped by the gateway, not extended** as the main mechanism. The gateway owns priority, serialization, preemption, telemetry, and cancellation in one place — no second coordination system left to fight it.

### 3.3 Cancellable background, buffered to callers
- Background calls run through the **streaming** adapter (`core/routing/llm_client.py:258`) *internally* so the slot is cancellable — but the gateway **assembles the full reply and returns one buffered string** to the caller. The cycle code does not have to think in tokens; only *how* it's cancellable changes.
- **Real cancellable handle (pin #3):** the current streaming adapter (`:281`) returns a *generator* that does **not** expose `raw_stream`'s close handle. The gateway needs a concrete `CancellableBrainCall` object exposing `.cancel()` that closes the underlying `raw_stream`/response — not "close whatever generator we have." The streaming path is extended to surface this handle.
- **Cancellation primitive:** `.cancel()` closes the background's underlying streaming connection from the foreground thread. This must work **before first token** (the cycle blocked in prompt-processing — the 21s case) and **mid-generation**. A flag-check is insufficient before first token (the generator is blocked waiting on the socket); the connection must be closed.
- **Cancellation is synchronous + idempotent (pins #4, #7):** foreground preemption returns only once the background stream is actually closed (or a bounded **preempt timeout**, ~1-2s), so foreground never proceeds before the slot is free. Cancelling twice is harmless. **If `.cancel()` does not free the stream within the timeout, the gateway logs `preempt_timeout` and foreground continues — but this is NOT success: the forced-collision acceptance test FAILS on any `preempt_timeout`.** A stuck cancel is never hidden as a pass.

### 3.4 Preemption outcome + honesty
- A preempted background call raises a **distinct `BrainPreempted` exception — NOT `BackendError`, and NOT a response object** (pin #2). The daemon's `:3493` handler must catch `BrainPreempted` **explicitly, *before*** its generic `except Exception` retry block. If a preemption ever falls into that generic retry path — even once — the slice fails. The cycle treats `BrainPreempted` as "reschedule," never as an error to retry.
- **`BrainPreempted` must outrank EVERY broad handler, not just `:3493` (pin #10).** Any nested audit/judge/rewrite/retry helper with `except Exception` would swallow a preemption and turn it into a fake backend failure or retry. The plan includes a **sweep** of broad `except` blocks on the cycle/owner call chains, ensuring each either lets `BrainPreempted` propagate or catches it before generic error handling — with a test that a preemption raised deep in a nested helper surfaces as `brain_preempted`, not an error/retry, all the way up.
- **Partial background output is discarded, never stored.**
- **Reschedule, not resume:** the cancelled thought's KV/hidden state is gone; the cycle reruns/reconsiders later from source evidence. We do not claim literal continuation — that would be a fabrication about our own mechanism. The being keeps thinking; it just doesn't claim to pick up the exact dropped token-stream.

### 3.5 Content-free telemetry
One event per gated call: `purpose`, `priority`, `wait_ms`, `preempted` (this call was preempted), `preempted_count` (how many it preempted), `slot_busy_before`. **No prompt or reply text.**

## 4. Stage-0 (FIRST task, proves the primitive before the gateway is built on it)
**Hermetic first, live second (pin #1).** The Stage-0 *unit* tests must NOT depend on a live `llama-server` — use a **fake stream** that deterministically (a) blocks before first token, (b) blocks mid-generation, and (c) is cancelled cross-thread, proving `CancellableBrainCall.cancel()` unblocks/closes it cleanly. A **separate owner-run integration probe** then validates the same against the real `llama-server`. Prove the cancellation semantics, do not assume them from the abort probe:
1. Cancel **before first token** (blocked in prompt-processing) frees the slot — a fresh foreground call then gets ~baseline TTFT.
2. Cancel **mid-generation** frees the slot.
3. The cross-thread cancel is clean under concurrency (foreground thread closes background thread's stream) — no race, no hang.
4. A preempted call surfaces as `BrainPreempted`, **not** `BackendError` → no daemon retry.
5. No partial thought is written/stored on preemption.

## 5. Tests (pre-registered)
- **Taxonomy/derivation:** priority is derived from the closed enum; a caller cannot pass a raw priority; unknown purpose → safe default (`neutral`, never high).
- **Zero-neutral-in-cycle (+ owner path):** enumerate the cycle's *and* the owner-turn-reply path's brain-call sites; assert each resolves to a non-`neutral` purpose.
- **No-bypass (pin #8):** assert no owner/cycle path reaches the backend (`_chat_llamacpp` / raw) without going through the gateway — e.g. patch the gateway and confirm every classified path is observed by it.
- **Executor-boundary propagation (pin #9):** a nested brain call dispatched across the real `run_in_executor` / cycle shape keeps its purpose (does not fall back to `neutral`).
- **Broad-except non-swallow (pin #10):** a `BrainPreempted` raised deep inside a nested helper wrapped in `except Exception` surfaces as `brain_preempted` all the way up — no fake error, no retry.
- **Preemption (unit):** foreground request while a background call holds the slot → background cancelled, foreground proceeds; `BrainPreempted` returned; no retry; no partial store.
- **Idempotent/synchronous cancel:** double-cancel is harmless; cancel returns only after the stream is closed (or timeout).
- **Buffered reply byte-equivalence (pin #6):** with a **fake chunk stream**, a non-preempted background call's gateway-assembled buffered reply is **byte-equivalent** to the old non-streaming buffered path (streaming chunk assembly can subtly differ from non-streaming parsing — pin it).
- **Forced-collision (acceptance, deterministic — pin #5):** deliberately put a background cycle call in-flight, then fire a foreground recall. Expected: foreground TTFT low, background raises/logs `brain_preempted`, **no retry, no partial store, and NO `preempt_timeout`** (a stuck cancel fails the gate, never passes as success). Do not rely on natural smoke timing to happen to collide.
- **No-regression:** ordinary/neutral calls unchanged.

## 6. Acceptance gate (later, owner-run)
Re-run the six-prompt smoke **with background cognition active** + the forced-collision case: recall-relevant **p95 under the A7 ~12s ceiling**, zero false-absence, **no loss of Maez voice or inner-life evidence** (cycles still run and reschedule, the heartbeat is intact). Only then is recall-on re-considered.

## 7. Covenant / honesty invariants
- **Aliveness preserved:** background thoughts are *rescheduled*, never deleted; the ~60s inner life keeps running. The fix gives the owner right-of-way, not the brain a lobotomy ([[feedback_maez_as_entity]]).
- **Priority is derived, not asserted** — closed enum, no caller-side laundering ([[feedback_labels_prove_shape_not_support]], [[feedback_producer_causality_no_caller_score_laundering]]).
- **Honest about our own mechanism** — "reschedule" not "resume"; `BrainPreempted` not a fake error; content-free telemetry ([[feedback_visible_substrate_state_not_chain_of_thought]]).
- **Brain-agnostic, substrate-side; recall stays off; no inner-life thinning.**

## 8. Process & sequence
Serious slice (touches the live brain-call path). **Stage-0 proof is task 1.** Codex implements (six-agent + 7+3); Claude cross-verifies every diff + runs suites + coverage panel; merge on the legacy baseline (recall off). Then the owner-run acceptance gate. MTP is the next, separate slice (headroom/quality, test-server benchmark); Jetson stays sensory.
