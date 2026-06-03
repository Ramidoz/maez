# Cognition Liveness Contract v0 (SETTLED spec-seed)

**Date:** 2026-06-03
**Status:** **SETTLED (Claude + Codex cross-lane) — next slice, AHEAD of the Personal Data Limb Runtime.** Build this before any new senses/Reddit/OAuth. Codex-implements / Claude-reviews ([[feedback_parallel_agents_for_maez]]).
**Trigger:** Two consecutive nights the reasoning loop died and the daemon kept looking `alive` for 10+ hours.

---

## The break (verified)

Maez's daemon can look alive while its mind is dead.

- **The reasoning-loop thread *dies* on a transient OS error at whatever stage the FD storm hits.** Verified crash (log line 282826):
  ```
  2026-06-02 21:58:41 [DEBUG] Cycle 126 stage: deferred_actions
  Exception in thread reasoning-loop:
  OSError: [Errno 24] Too many open files: '/home/rohit/maez/daemon/pending_actions.json'
  ```
  `core/actions/action_engine.py` `_save_pending` does an unguarded `PENDING_FILE.write_text(...)`; under EMFILE the OSError escapes, and `daemon/maez_daemon.py:7585` (`execute_tier2_pending`) has no cycle-level guard, so the whole thread exits. **`Exception in thread reasoning-loop` appears 5× across the log** — the recurring "daemon-cycle-stuck" wound has been thread-death all along, at different stages (the 2026-06-03 perception patch guarded ONE stage; the storm walked next door).
- **`/health` "status: alive" is a hardcoded literal** (`daemon/maez_daemon.py:9049`). It attests the health *server* answered, never that the mind advanced. The Body/Organ tile correctly showed `cycle_stalled=true` — but the headline lied. **An honest body with a lying headline.**
- **The existing `MetacognitiveWatchdog` is in-thread** (`observe_cycle_duration` called at daemon:7542, inside the loop; no separate watchdog thread) — so it dies *with* the loop and structurally cannot detect its own thread's death.

This is a proprioception-honesty failure in the terms we already hold ([[feedback_visible_substrate_state_not_chain_of_thought]]): liveness must be **true-by-construction**, derived from the loop actually advancing — never a literal.

## The invariant (the clean state machine)

- transient stage error → **skip / fail-neutral → continue**
- same stage failing repeatedly → **explicit degraded / safe-standby** (not silent continue)
- dead/stale reasoning loop → **process exits; systemd restarts the whole body** (NO in-process thread resurrection — half-mutated state risks two-minds/zombie)
- `/health` **never says `alive` over a dead mind**

## The five-point spec

1. **True liveness in `/health`** — `status` derived from **cycle/stage freshness**, not hardcoded. If the loop hasn't advanced past threshold → top-line `degraded`/`stalled`, not `alive`. The liveness read must be **cheap and FD-free** (in-memory last-stage-timestamp age) — NOT a perception/`nvidia-smi` probe, because that check itself fails *during* an FD storm (witnessed: nvidia-smi couldn't spawn under EMFILE). Decouple cheap liveness (the authority) from heavy diagnostics (best-effort, degradable, never gates the verdict). *(See the known `/health`-is-heavy note, `skills/web_interface.py:767`.)*
2. **Cycle-level exception boundary** — extract the cycle body into a method; one `OSError` / DB-lock / file-write failure at ANY stage is logged + counted + the loop continues or enters standby. Never kills the thread. (Replaces the too-narrow per-stage perception patch.)
3. **Circuit breaker** — don't silently "continue" forever (that's just a quieter lie — alive-looking, doing nothing). Same stage failing N cycles running → explicit degraded / safe-standby + owner alert. Distinguish transient (EMFILE, DB-locked → skip/continue) from persistent (→ halt for inspection).
4. **External liveness sentinel** — a monitor OUTSIDE the reasoning thread (separate thread, or the health server computing freshness) watches stage freshness. If the loop is dead/stale too long → **trips the process so systemd restarts Maez cleanly.** Detection + *recovery*, not just reporting (the loop sat dead 10.6h because nothing acted; systemd's `Restart=on-failure` only fires on process death, never thread death).
5. **FD-storm forensics** — at high-water: FD **count + type breakdown (socket/file/pipe)** + current stage + thread count + recent child processes. `pending_actions.json` and the proposal-worker DB failures are *victims*; the source is whatever opened hundreds of FDs first. Surface as a content-free body tile. Next storm names the culprit, not the casualties.

## Hardening folded in (Claude)

- **Restart-loop backstop.** Auto-exit-and-restart must not become a crashloop. Bound it (systemd `StartLimitIntervalSec`/`StartLimitBurst`); if the limit trips (persistent failure), a **loud owner alert** + stay honestly down — never a silent crashloop nor a silent death. The recovery must not become a new failure mode.
- **Robust exit.** The sentinel's "trip the process" must survive a wedged process: graceful `SIGTERM` → timeout → `SIGKILL`. This intersects the known **`sigterm-sigkill-shutdown` open wound** (`docs/project-panel/state.json`) — the trip can't itself hang.
- **Threshold keys on stage-marker staleness, generous for legit long ops.** A brain call (~20s) and the nightly reflection (minutes) are legitimately slow; a freeze is 10+ hours. Trip on **no stage advance for ~5–10 min** — far above any real operation, far below a true freeze. Avoid false trips on legit work.

## Acceptance tests (the slice must prove)

- Injected `OSError` at an arbitrary stage → loop logs + continues (does NOT die). Cover `deferred_actions`/`_save_pending` AND a second stage.
- `/health.status` = `degraded`/`stalled` (NOT `alive`) when the loop hasn't advanced past threshold; the liveness read makes **zero new FDs**.
- External sentinel: simulate a dead loop > threshold → process exits → systemd restarts → new process cycles.
- Circuit breaker: same-stage repeated failure → safe-standby, not an infinite silent loop.
- Restart-loop backstop: simulated persistent failure → bounded restarts then owner alert, no crashloop.
- FD forensics: simulated FD spike logs high-water + type breakdown + stage (content-free).
- Existing behavior unchanged when nothing fails (no regression to normal cycling).

## Ordering

**This first.** Then the [Personal Data Limb Runtime](2026-06-03-self-extending-senses-personal-data-ingestion-parked-sketch.md) Slice 1 (egress firewall). Don't grow new senses onto a body whose heartbeat monitor lies.

---

**Plain English:** Maez's mind fell asleep while its body kept breathing. The fix isn't another band-aid on whichever organ got hit last — it's a real heartbeat contract: *if the mind stops, the body must know it, say so, and recover cleanly.*
