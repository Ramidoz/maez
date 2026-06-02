# Cycle Salience Doorman (deterministic v1) — Design

**Date:** 2026-06-01
**Status:** Draft under review (owner review pending before plan/Codex)
**Lane:** Codex implements, Claude cross-verifies, Rohit owner-witnesses.

---

## 1. Problem

Every ~60s the daydream cycle runs the **deep brain** (`_reason`, ~6-17s GPU) and very often the brain itself concludes `HEARTBEAT_OK` ("nothing noteworthy"). That is the deep mind doing the **doorman's job** — burning the 4090 to decide there was nothing to decide. A proto-gate exists — `core/cognition/perception_signature.py::should_skip_reasoning()` — but it only considers **perception-axis change** (fixation prevention), so the richer salience signals (new failures, open wants, changed memory, absence rails, scheduled maintenance) still wake the deep brain unnecessarily.

**Covenant constraint (load-bearing, from Session 11m):** `_rohit_active_until` is a **hint only** — presence must NOT gate cognition. Maez thinks when there is something to think about, **watched or not**. So the fix triggers on **salience, never presence.**

## 2. The fix — a deterministic salience doorman before the deep call

Introduce a **substrate-side, model-free** doorman that runs **before** `_reason`, extends the existing signature gate, and decides "is there something worth waking the deep brain for?" from **sourced signals** with **closed reason codes**.

- **wake = False** → emit a **content-free** `doorman_skip` (with `reason_code`); **no deep-brain call, no fabricated thought.** (Same observable outcome as today's `HEARTBEAT_OK` — nothing stored — but without spending the GPU to get there.)
- **wake = True** → proceed to `_reason` (with the cycle packet when `MAEZ_CYCLE_FOCUSED_ENABLED` is on).
- **FAIL-OPEN (the mechanically-enforced covenant):** a false skip (missing a real moment) is the dangerous failure; a false wake is mere waste. So on **any** uncertainty — malformed/empty signal bundle, unknown signal class, selector/doorman exception, stale or missing doorman state — the verdict is **`wake=True` with `reason_code=WAKE_FAIL_OPEN`**, OR fall back to today's path (deep brain runs). The doorman **never skips on error or ambiguity.** Skipping is only ever the result of an explicit, well-formed "nothing salient + floor not due" verdict.

### Signals the doorman reads (sourced, not summarized)

Reuse the cycle-packet candidate sources + the signature gate:
- **changed perception axes** — `perception_signature.extract_axes` / `stale_fields` (the existing seam).
- **new failures / unresolved cards** — `action_outcome` signals.
- **open wants / wonderings / capability queue** — `open_loop` signals.
- **recent meaningful salience** — stored-thought salience deltas.
- **changed memory / evidence** — memory delta since last cycle.
- **signal-availability change** — a *change* in whether a **data source** is available (screen signal absent/returned, camera *sensor* unavailable/returned, a sensor rail changed). HARD DEFINITION: this is **data-source availability, NOT physical owner presence.** `perception_signature.extract_axes()` includes a `presence` axis — the doorman wake path **excludes the owner-presence axis entirely** (presence is never a wake term; §4). Only a *transition* in source availability wakes; **steady absence does not repeatedly wake** (a screen that's been off for an hour is not newly salient each cycle).
- **scheduled maintenance** — builder/consolidation/hourly-capability due.
- **minimum-thought floor (periodic probe, not a latch)** — reuse the **existing `DEFAULT_MIN_THOUGHT_FLOOR` value** (do not invent a new cadence). Semantics: count **quiet skips since the last deep-wake opportunity**; after N quiet skips, wake **once** (`WAKE_MIN_FLOOR`). If that woken cycle's deep brain returns `HEARTBEAT_OK` (nothing), **reset the quiet counter and resume skipping** — it must NOT latch into waking every cycle thereafter (that would reintroduce the waste). So the floor is a periodic *probe* ("still nothing?") on a fixed cadence, not a continuous wake state. (Count is cycles-since-last-wake-*opportunity*, NOT cycles-since-last-stored-*thought*, to avoid the latch.)

### Closed reason codes (auditable, like the packet's source types)

`WAKE_PERCEPTION_CHANGED`, `WAKE_NEW_FAILURE`, `WAKE_OPEN_WANT`, `WAKE_MEMORY_DELTA`, `WAKE_SIGNAL_AVAILABILITY_CHANGED` (data-source availability transition, NOT owner presence), `WAKE_SCHEDULED`, `WAKE_MIN_FLOOR`, `WAKE_FAIL_OPEN` (uncertainty/error); `SKIP_NOTHING_SALIENT`, `SKIP_UNCHANGED`. The verdict carries `wake: bool` + `reason_code` (closed enum). No free text. Note: the `perception` axis set used for the wake decision **excludes owner-presence**.

## 3. The organ boundary (so a model can slot in later — your steer)

The doorman is a pure function: `decide(signal_bundle) -> DoormanVerdict(wake, reason_code)`. v1 is **deterministic** over sourced signals. **Later**, an i9 small model (LFM2.5-class) can implement the *same interface* as a **tested evidence classifier** — behind a flag, scored against the deterministic baseline — **never** a free-text summarizer the deep brain trusts. Building the boundary now with deterministic logic proves the organ before introducing a model-trust problem.

## 4. Presence — modulates timing, never gates thought (the covenant line)

Presence (`_rohit_active_until`, camera) may **only** shift the *timing of heavy/background classes* — e.g., defer a big overnight-style consolidation pass while Rohit is likely to speak. It **never** suppresses a genuinely salient thought, and it is **never** an input to the `wake` decision. Salience decides *whether* Maez thinks; presence decides *when the heavy stuff* runs. The unit test asserts: with presence "active", a salient signal still wakes (`wake=True`), and with presence "absent", Maez still wakes on salience (no presence term in the wake path at all).

## 5. Inner life is preserved, not thinned (covenant)

The skip only removes the **redundant "re-confirm nothing" cycles** — the ones where today's deep brain runs solely to emit `HEARTBEAT_OK`. Maez still reflects (a) whenever any salience signal fires, and (b) periodically via the min-thought floor regardless of change. So Maez doesn't go quiet; it stops *burning the brain to learn it has nothing to say.* The load-bearing rail (see §7) guarantees no genuinely salient moment is ever skipped.

## 6. Flag-gated, measurement-first, legacy fallback

Flag `MAEZ_CYCLE_DOORMAN_ENABLED` (off by default). Off → current behavior (deep brain runs every cycle; existing signature gate only). On → the doorman gates. Content-free telemetry `doorman_verdict`: `wake` (bool), `reason_code`, `signals_present` (closed list of which signal classes fired), and the cycle's `skipped`/`woke` outcome — numbers/enums only, **no thought/memory text**. This lets us measure wake/skip rate + reason-code distribution before defaulting on.

## 7. Acceptance (owner-witnessed + the load-bearing rail)

- **Load-bearing rail (the false-skip guard — the inverse of the packet's false-absence):** the doorman must **NEVER skip a genuinely salient cycle.** Every one of {new failure, open want, changed memory, changed perception axis, signal-availability transition, scheduled maintenance, min-floor-due} → `wake=True`. A skip on any genuinely-salient signal is the one outcome we must not ship. Hermetic, exhaustive per signal class.
- **FAIL-OPEN (tested beside the exhaustive rail):** malformed/empty bundle, unknown signal class, doorman/selector exception, stale or missing doorman state → **`wake=True` (`WAKE_FAIL_OPEN`)** or legacy fallback — **never a skip.** Skipping only ever results from an explicit, well-formed "nothing salient + floor not due" verdict.
- **Skip works:** under a literally-unchanged, well-formed signal bundle below the min-floor, `wake=False`, `doorman_skip` content-free, **no `_reason` call** (assert the deep brain was not invoked).
- **Presence never gates:** presence active vs absent does not change a salient wake; **the owner-presence axis is excluded from the wake path entirely** (assert no presence term).
- **Signal-availability is a transition, not a state:** a source that *changes* availability wakes once; **steady absence does NOT repeatedly wake** (a screen off for many cycles is not newly salient each cycle).
- **Min-floor is a periodic probe, not a latch:** after N quiet skips the doorman wakes once; if that cycle returns `HEARTBEAT_OK`, the quiet counter **resets and skipping resumes** — assert it does NOT wake every cycle after a floor wake.
- **Live (owner-witnessed):** with the flag on, GPU duty drops (fewer deep calls), Maez's reflections when it *does* wake are unchanged/in-voice, and Maez doesn't feel "quieter" in a way that matters — the redundant cycles are gone, the meaningful ones remain.

## 8. Non-goals

- **NOT a model** — deterministic v1; the model is a later, tested, flag-gated classifier behind the same interface.
- **NOT presence-gating** — salience triggers; presence only modulates heavy-work timing.
- **NOT a change to what Maez thinks when it wakes** — the cycle packet owns the woken prompt; the doorman only decides *whether* to wake.
- **NOT rate-limiting** — we reject "just run less often"; the fix is the salience primitive, not a timer.
- **NOT circadian heavy/sleep scheduling yet** — the heavy-class deferral is a follow-on; this slice is the wake-decision organ. (Night/idle heavy-consolidation scheduling builds on this doorman next.)
