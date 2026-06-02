# Cycle Packet — Telemetry Fix + Merge Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** Make the cycle packet self-report its speed (fix `cycle_packet_shape.prefill_ms=null`), then merge the proven slice flag-off. This is the foundation for circadian/tiered-soul, so it must carry its own timing evidence — no more hand-reading llama.cpp logs.

**Lane:** Codex implements, Claude cross-verifies. Flag stays **off** by default; legacy cycle path is the resting state. Branch: `cycle-focused-cognition-packet`.

**Order (Rohit/Codex-locked):** 1) telemetry fix · 2) merge flag-off · 3) circadian (separate slice) · 4) tiered cycle-soul *only after* circadian shows whether 6s still matters.

---

## Task 1: Telemetry — make the cycle self-report timing

Two timings; do **1a first** (trivial, always works, alone fixes the complaint), then **1b** (precise, llama.cpp-only, graceful-null elsewhere).

### Task 1a: wall-clock `chat_total_ms` (always available)

**Files:** `daemon/maez_daemon.py` (`_reason`, the cycle `chat` call ~`:3720`; `_log_cycle_packet_shape` ~`:3680`); telemetry helper ~`:1505-1543`.

- [ ] **Step 1 (test):** assert `cycle_packet_shape` carries a numeric `chat_total_ms` after a (faked) cycle chat — content-free (number only).
- [ ] **Step 2:** wrap the cycle's `response = _llm_client.chat(...)` in a `time.monotonic()` timer; pass `chat_total_ms=int(elapsed*1000)` into `_log_cycle_packet_shape`. Add `chat_total_ms` to the shape dict (alongside the existing `prefill_ms`). Content-free.
- [ ] **Step 3:** Run → PASS. Commit `feat(cycle): self-report chat_total_ms in cycle_packet_shape`.

### Task 1b: server `prefill_ms` (precise; llama.cpp socket path)

The server's `timings.prompt_ms` (true prefill) rides in the final SSE chunk, which the socket parser currently parses-and-ignores.

**Files:** `core/routing/llm_client.py` (`_LlamaCppStreamParser`, `_LlamaCppSocketStream`, `_LlmResponse`, `chat`); `core/routing/cancellable_brain_call.py` (surface the captured timings); `daemon/maez_daemon.py` (`_reason`).

- [ ] **Step 1 (test):** feed `_LlamaCppStreamParser` a wire whose final `data:` chunk includes `"timings":{"prompt_ms":1234,...}`; assert the parser exposes `prompt_ms=1234` after iteration (and `None` when no timings present).
- [ ] **Step 2:** in `_LlamaCppStreamParser._drain_sse`, when a parsed `data` dict has a `timings` block, stash `self.server_prompt_ms = timings.get("prompt_ms")` (and optionally `predicted_ms`). Expose it on `_LlamaCppSocketStream` (read-through to the parser). `CancellableBrainCall.collect()` returns the buffered text as today; add a way to read the stream's `server_prompt_ms` after collect (e.g. a property).
- [ ] **Step 3:** add an **optional** `server_prompt_ms: int | None = None` field to `_LlmResponse` (additive; default None so every existing consumer is unaffected); populate it in `chat()` from the cancellable call when the llama.cpp socket path is used. Non-llamacpp / buffered / ollama paths leave it `None` (graceful).
- [ ] **Step 4:** in `_reason`, pass `getattr(response, "server_prompt_ms", None)` as `prefill_ms` to `_log_cycle_packet_shape`. Now `prefill_ms` is the real server prefill when available, `None` otherwise (and `chat_total_ms` always covers it).
- [ ] **Step 5:** Run parser + transport + cycle tests → PASS. Confirm `_LlmResponse`'s new field doesn't break the equivalence/byte tests. Commit `feat(transport): surface server prefill_ms through to cycle telemetry`.

---

## Task 2: Merge the cycle packet flag-off

- [ ] **Step 1:** Cross-verify (Claude lane): re-run the cycle_packet + transport + targeted suites; re-confirm the adversarial selector rails (signal_absence survives tight budget, no crowd-out) still hold after the telemetry changes; flag-off still a true no-op; fallback intact.
- [ ] **Step 2:** Floor both directions on a clean checkout (NOT git stash); known-unrelated trio excluded by name.
- [ ] **Step 3 (owner):** `git merge --ff-only cycle-focused-cognition-packet` → main. **Flag `MAEZ_CYCLE_FOCUSED_ENABLED` stays off by default** — merging lands the capability disabled; the live default-on remains a separate owner decision.
- [ ] **Step 4:** Optional re-witness: with the flag on for a short window, confirm `cycle_packet_shape` now self-reports `prefill_ms` + `chat_total_ms` (no more hand-reading llama.cpp logs). Revert flag off.

---

## Out of scope (separate, later slices)

- **Circadian scheduling** — its own spec/plan; built *on top of* the merged packet. Decides whether the ~6s cycle even matters by reducing frequency.
- **Tiered cycle-soul** — consider **only after** circadian shows 6s still matters; covenant-sensitive (touches Maez's static self), so it gets its own deliberate design, not a casual trim.
- **The Gemma brain bakeoff** — parked offline ceremony (`2026-06-01-maez-brain-bakeoff.md`); unrelated to this merge.

---

## Self-Review

- **Order honored:** telemetry (T1) before merge (T2); circadian/tiered-soul explicitly out of scope.
- **Cheapest-first:** 1a (wall-clock) alone fixes "Maez didn't self-report speed"; 1b adds precision, graceful-null where unavailable.
- **Additive + safe:** `_LlmResponse.server_prompt_ms` is additive/default-None; no existing consumer changes; flag stays off; every commit green.
- **Foundation carries its evidence:** post-merge, circadian/tiered-soul work reads `cycle_packet_shape` timing directly instead of llama.cpp logs.
