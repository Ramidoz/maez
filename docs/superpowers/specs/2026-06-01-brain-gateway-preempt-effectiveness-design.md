# Brain Gateway — Preempt Effectiveness (Handle-Install Timing) Design

**Date:** 2026-06-01
**Status:** Draft under review (owner review pending before plan/Codex)
**Predecessor:** `docs/superpowers/specs/2026-06-01-brain-gateway-qos-design.md` (structure landed @ `ad6a2f8` + `fd22d86`)
**Lane:** Codex implements, Claude cross-verifies, Rohit orchestrates + owner-runs the live gate.
**Recall stays OFF through this slice.**

---

## 1. Problem (code-confirmed, not hypothesized)

The Brain Gateway's *structure* is proven live: a foreground `owner_recall` enters at `priority=100`, sees the in-flight background cycle, and the cycle yields (`preempted=True`). But the acceptance gate is a **No-Go on preempt EFFECTIVENESS**: under a forced collision, `owner_recall wait_ms` stays **10-15s** even though the brain generates in ~4-5s once it owns the slot.

Root cause is a **handle-install timing gap**, confirmed by reading current `main`:

- `BrainGateway.submit` runs the blocking stream-start `raw_stream = run_streaming_fn()` at [`brain_gateway.py:145`](../../../core/routing/brain_gateway.py#L145) **before** installing the cancellable handle `record.call = call` at [`:155`](../../../core/routing/brain_gateway.py#L155).
- `run_streaming_fn()` for the live path is `start_cancellable_chat()` → `_start_llamacpp_stream()` → `_get_openai_client().chat.completions.create(stream=True)` at [`llm_client.py:325`](../../../core/routing/llm_client.py#L325). If that `create()` blocks through prompt-eval, `record.call is None` for that entire window.
- `_reserve_slot` only cancels the in-flight call when a handle exists: [`:206-213`](../../../core/routing/brain_gateway.py#L206-L213) sets `cancel_requested=True`, grabs `call_to_cancel = current.call` (**`None`**), increments `preempted_count`, and the guard `if call_to_cancel is not None` skips the cancel. The foreground then spins on the 0.05s wait ([`:215-216`](../../../core/routing/brain_gateway.py#L215-L216)) until the background's `run_streaming_fn()` returns and the background self-cancels.

This explains both live symptoms exactly: the **10-15s wait** = the duration the foreground spins waiting for the background's blocking stream-start to return; the **hundreds of `preempted_count`** = ~one spin per 0.05s across that window.

The earlier `_LlamaCppStreamAdapter.close()`-is-broken hypothesis is **withdrawn** — that close ([`llm_client.py:300`](../../../core/routing/llm_client.py#L300)) correctly forwards to the raw stream. The flaw is the *timing of when a cancellable handle becomes available*, not the close itself.

**Right-of-way is achievable** (the deciding measurement): a real cancel-before-first-token probe against live llama-server, using raw `requests`, freed the slot in **~440-536ms** (3/4 trials; the 1 slow trial was an ambient daemon-cycle collision because the probe bypasses the gateway). So the server cooperates; the gateway just isn't holding a closeable handle during prompt-eval.

## 2. The slice is measurement-first

The fix is **gated on a live diagnostic**, not chosen up front. There are two non-exclusive candidate causes:

- **(C1) Gateway ordering gap** — even a fast stream-start leaves a window where `record.call is None`.
- **(C2) Transport opacity** — the openai SDK's `create(stream=True)` may not expose a closeable connection until the first SSE event (i.e. until prompt-eval ends), where raw `requests`/`httpx` exposes it after early-flushed headers (probe-proven).

We do **not** convict the SDK before the diagnostic proves the gap is real and load-bearing. `handle_state=missing` during the wait proves the gap without yet naming C1 vs C2.

## 3. Diagnostic (Task 1, load-bearing — gates the fix)

Emit a **content-free** event from `_reserve_slot`, sampled at each foreground preempt attempt:

```
brain_gateway_preempt_probe purpose=owner_recall current_purpose=daemon_cycle_generation handle_state=missing|present wait_ms=… preempt_attempts=…
```

- `handle_state = "missing" if current.call is None else "present"` — read off the in-flight record at [`brain_gateway.py:208`](../../../core/routing/brain_gateway.py#L208).
- `current_purpose` = the in-flight (background) record's `purpose` (the one being preempted).
- `preempt_attempts` = the existing `preempted_count` spin counter.
- No prompt, no reply, no token text — same content-free discipline as `brain_gateway_event`.

**Pass condition for the diagnosis:** under a forced collision (cycle in-flight + foreground recall), the probe reads `handle_state=missing` through the 10-15s wait. That proves the room-key-before-fire-alarm flaw live. (Owner-run for the live read; hermetic test asserts the event fires with the right shape.)

## 4. RED test (forces the fix shape)

A hermetic test (fake stream, no live server): a background `run_streaming_fn()` that **blocks before returning** (deterministically, cross-thread). A foreground preempt must still **acquire a cancellable handle and win sub-second** — i.e. the foreground must not depend on the background's `run_streaming_fn()` having returned.

The current gateway **fails** this (no handle exists to cancel while the background is blocked in stream-start). The test is RED first, then drives the fix. This test is what makes the fix verifiable without the live server.

## 5. Fix space (chosen by Task 1 + RED, not pre-baked)

The RED test encodes the real requirement: **a cancellable handle must exist before the network round-trip completes.** Two implementation routes, smallest first:

- **(F1) Reorder / early handle** — the smallest-surface fix **if the existing transport can expose an early close handle**: split stream-start into "start (returns a closeable connection fast)" + "consume (blocks)", and install `record.call` from the fast half. F1 is conditional on evidence, not on optimism — it is **not** a license for heroic SDK surgery to force `create(stream=True)` to do what it can't.
- **(F2) Transport swap** — replace the openai-SDK `create(stream=True)` stream-start in `_start_llamacpp_stream` with a raw `requests`/`httpx` streaming POST whose connection handle is available immediately. Justified because raw `requests` **already proved** the slot frees in ~440ms.

**Decision rule (evidence-gated, no ritual):**
- Try F1 **only if** Task 1 — or a tiny transport microprobe — shows the existing transport can produce a closeable handle *before* prompt-eval completes.
- **Otherwise F2 is the fix**, full stop: if `create(stream=True)` does not return until first SSE / post-prompt-eval, skip F1 and go straight to F2. No SDK heroics.
- If F1 alone makes the RED test pass and drops the forced-collision wait sub-second, we **do not touch transport**.

"Smallest first" is a principle, not a ritual: if the SDK can't hand us the emergency brake early, use the transport that can.

## 6. Invariants / covenant

- **No-bypass preserved** — every owner/cycle brain call still routes through the gateway; the fix changes *when the handle is installed*, not *whether* calls are gated. The existing no-bypass test must stay green.
- **Content-free telemetry** — the new probe event carries no prompt/reply/token text; assert it in tests.
- **Cancelled cognition reschedules, not deleted** — a preempted cycle still yields cleanly (`BrainPreempted`), writes no partial thought, triggers no false backend-error retry. Maez's inner life is interrupted, not thinned.
- **Brain-agnostic, substrate-side** — no change to the brain's function-call grammar; this is gateway/transport plumbing.
- **Recall stays OFF** — no flag flip in this slice. The slice ends at a proven sub-second forced-collision wait; the recall default-on re-gate is a separate owner-run step afterward.

## 7. Acceptance gate (owner-run, unchanged)

Forced collision: background cycle in-flight, foreground `owner_recall` fires →
- `owner_recall wait_ms` **sub-second**,
- background `preempted=True`, no retry, no partial store,
- **no `preempt_timeout`** (the cancel actually frees the slot; the timeout is not the escape hatch),
- A7 ~12s p95 ceiling holds with cognition active, Maez voice + inner-life evidence intact.

## 8. Testing & process

- **unittest runner** (`.venv/bin/python -m unittest`), **NO pytest**.
- **Hermetic Stage-0 first**: the RED test + the probe-event-shape test run against fake streams, no live llama-server.
- **Separate owner-run integration note** for the live forced-collision read (not a unit test).
- Floor both directions on a clean checkout (NOT git stash); the known-unrelated flaky trio (egress / web-slice / import-shim) is excluded by name.
- Serious slice (touches the live brain-call path) → Codex implements (6-agent + 7+3), Claude cross-verifies (reads every diff, runs the suite independently, fires the coverage panel). The plan is the Codex handoff.

## 9. Non-goals

- **No MTP** (later headroom, not the cure — it shortens the stuck call, doesn't create right-of-way).
- **No second slot / `--parallel 2`** (right-of-way is achievable on one slot).
- **No prompt/working-set trimming** (refuted earlier).
- **No transport swap if reorder suffices** (don't change more surface than the diagnostic licenses).
