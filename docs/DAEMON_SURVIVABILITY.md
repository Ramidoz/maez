# Daemon Survivability Knobs

Operational notes for background paths that must fail boundedly instead of
wedging the daemon.

## Proposal intent timeout

`MAEZ_PROPOSAL_INTENT_TIMEOUT_S` controls the LLM call used by the background
proposal worker when it asks for a structured patch intent.

- Default: `45`
- Scope: proposal-intent generation only
- Failure behavior: timeout marks the proposal job `failed`; it does not retry
  immediately
- Reason: proposal generation is background self-improvement work, so daemon
  responsiveness wins over completing a proposal

Example:

```bash
MAEZ_PROPOSAL_INTENT_TIMEOUT_S=30 python daemon/maez_daemon.py
```

Inspect recent proposal-intent failures:

```bash
sqlite3 memory/evolution_track.db \
  "SELECT id, weakness_description, last_error FROM proposal_jobs \
   WHERE state='failed' ORDER BY finished_at DESC LIMIT 10"
```

## Grounding judge circuit breaker

The grounding judge endpoint (default port 8081) is wrapped by a process-
local circuit breaker. After `MAEZ_JUDGE_BREAKER_THRESHOLD` transport
failures within `MAEZ_JUDGE_BREAKER_WINDOW_S` seconds, the breaker opens
and subsequent calls short-circuit as
`JudgeUnavailable(error_class='circuit_open')` without touching the
network. After `MAEZ_JUDGE_BREAKER_COOLDOWN_S`, the next call is admitted
as a single probe; success closes the breaker, failure reopens it.

| Env var | Default | Notes |
|---|---|---|
| `MAEZ_JUDGE_BREAKER_THRESHOLD` | `3` | Transport failures to open |
| `MAEZ_JUDGE_BREAKER_WINDOW_S`  | `300` | Window over which failures count |
| `MAEZ_JUDGE_BREAKER_COOLDOWN_S` | `30` | Time before HALF_OPEN probe allowed |

Invalid or non-positive values fall back to the defaults with a WARNING
on `core.cognition.grounding_judge`. A typo will not crash daemon import.

- Scope: dedicated judge HTTP path only (`_call_dedicated_judge`). The
  fallback `_llm_client.chat` path is intentionally not wrapped — it
  shares an endpoint with the proposal worker and gets its own breaker
  policy in a future slice.
- Failure classification: only `refused`, `timeout`, and `http_5xx`
  count toward the threshold. `bad_response` (judge alive, body
  malformed) is surfaced normally as `JudgeUnavailable` but does NOT
  trip the breaker — otherwise a single bad prompt-template deploy
  would deterministically open the circuit forever.
- State transitions log at WARNING on `core.cognition.grounding_judge`.
- Per-process state. Restart resets to CLOSED.

Inspect breaker state from a Python REPL:

```python
from core.cognition.grounding_judge import _JUDGE_BREAKER
print(_JUDGE_BREAKER)  # → CircuitBreaker(name='grounding_judge', state=..., ...)
```

## Dream-cycle worker bounding

The dream cycle (background AFK-triggered self-reflection) runs in a
daemon thread. Previously each idle trigger spawned a fresh
`threading.Thread(daemon=True)` with no concurrency guard — when a
cycle exceeded `DREAM_COOLDOWN_S`, multiple cycles could run
concurrently, leaking ~40-50 threads per 43-min window in observed
runs.

Slice 1.3 wraps the spawn in a `BoundedSingletonWorker`
(`core/health/bounded_worker.py`) that enforces at-most-one in flight
and supports bounded shutdown.

- **Concurrency:** at most one dream cycle in flight. Trigger-while-
  busy is logged at DEBUG and skipped.
- **Cadence:** unchanged — `dream_state.py:_last_dream_at` is still
  the primary cadence gate, updated at the start of `run_dream_cycle`.
  The worker is defense-in-depth against the cooldown failing under
  long cycles.
- **Shutdown:** `MaezDaemon.stop()` calls `worker.shutdown(timeout=5.0)`
  before exit; an in-flight cycle gets up to 5 seconds to finish
  writing to `memory.db`. After shutdown is signaled, no new cycles
  can spawn (eliminates the half-write-on-exit hazard).
- **Inspect from REPL:**
  ```python
  print(daemon._dream_worker)
  # → BoundedSingletonWorker(name='dream-cycle', in_flight=..., shutdown=...)
  ```

## Wake-word reader (pw-record) bounded read

The wake-word listener spawns `pw-record` (PipeWire microphone capture)
as a subprocess and reads its stdout in a daemon thread. Previously the
read was a blocking `proc.stdout.read(chunk_bytes)` with no timeout —
if PipeWire hung or the audio device went away mid-read, the reader
thread blocked in kernel-space (D-state). On 2026-05-07 this thread
held file descriptors through `kill -9` of the daemon and required a
machine reboot to release.

Slice 1.4 wraps the read in `select()` polling with a silence
watchdog. Both the WAV header read and the chunk reads go through
the same path; if pw-record produces no data for
`MAEZ_PW_READER_WATCHDOG_S` seconds, the helper kills the process to
unblock the pipe.

| Env var | Default | Notes |
|---|---|---|
| `MAEZ_PW_READER_WATCHDOG_S` | `5.0` | Continuous-silence threshold before proc.kill() |

- **Polling cadence:** `select()` timeout of 0.5s — the upper bound
  on how long stop_event takes to propagate to a quiet reader.
- **Cleanup ladder in `wake_word.stop()`:** terminate → bounded join
  (2s) → close stdout → kill → bounded join (2s) → log error if still
  alive. Module-level `_pw_proc` and `_pw_reader_thread` globals let
  `stop()` reach the proc and thread directly without depending on
  `_audio_loop_inner`'s finally block running (which it might not, if
  the audio loop itself is wedged).
- Invalid `MAEZ_PW_READER_WATCHDOG_S` values fall back to the default
  with a WARNING — daemon import must not fail on a typo.
- Per-process state. Restart resets.

## Telegram batch / session dict eviction (slice 1.5)

The Telegram surface has four dicts that grow O(unique_senders) and
self-evict on the happy path but leak residue on exception/race
paths: `_pending_text_batches`, `_pending_photo_batches`,
`_media_group_events` (telegram_adapter), and `_active_sessions`
(platform_base). Slice 1.5 adds periodic sweep tasks that prune
entries past their TTL.

| Env var | Default | Notes |
|---|---|---|
| `MAEZ_TELEGRAM_SWEEP_INTERVAL_S` | `60` | Telegram batch sweep cadence (seconds) |
| `MAEZ_TELEGRAM_BATCH_TTL_S` | `300` | Telegram batch entry TTL (5 min) |
| `MAEZ_SESSION_SWEEP_INTERVAL_S` | `600` | Session sweep cadence (seconds) |
| `MAEZ_SESSION_TTL_S` | `86400` | Session idle horizon (24h) |

- **Telegram batch eviction:** entries past TTL are removed; if the
  associated flush task is `done()`, INFO log; if NOT done (silently-
  crashed flush signal), the task is cancelled and a WARNING is
  logged. `_batch_last_touched` is refreshed on every append site.
- **Session eviction** requires ALL THREE: TTL elapsed, interrupt
  event NOT set, and NO live `_background_tasks` referencing the
  session_key. Tasks are tagged with `task.session_key` at spawn.
  Wedged-but-stale entries log WARNING (operator signal); clean
  evictions log INFO.
- **Lifecycle:** `_batch_sweep_task` is created via the idempotent
  `_ensure_batch_sweep_started()` helper. `__init__` calls it
  best-effort (succeeds in test contexts that already have a running
  loop; silently defers in production where adapters are constructed
  synchronously before the loop exists). `connect()` is the
  load-bearing call site — it invokes both `super().start()` (for the
  base-class `_session_sweep_task`) AND
  `_ensure_batch_sweep_started()` (for the Telegram batch sweep).
  `disconnect() → self.stop() → super().stop()` cancels both in
  lockstep.
- Invalid env values fall back to defaults with a WARNING (slice
  1.2/1.3/1.4 posture).

Inspect counts from a Python REPL:

```python
print(len(adapter._pending_text_batches),
      len(adapter._media_group_events),
      len(adapter._active_sessions))
```

## Shared executor for sync work (slice 1.6)

The 12 `run_in_executor(None, ...)` call sites in
`skills/surface/maez_adapter.py` and `skills/telegram_voice.py` used
Python's default thread pool (`min(32, cpu+4)`). Under sustained
load the pool fills with idle workers that never reap — the audit
attributed ~150-200 of the 330 leaked-threads-per-43-min hang to
this class.

Slice 1.6 routes all 12 sites through a process-wide bounded
`ThreadPoolExecutor` in `core/health/shared_executor.py`.

| Env var | Default | Notes |
|---|---|---|
| `MAEZ_SHARED_EXECUTOR_MAX_WORKERS` | `8` | Bound on concurrent sync work |
| `MAEZ_LLM_CALL_TIMEOUT_S` | `120` | asyncio-side timeout for LLM call sites |

**Integration pattern (production):**

All 12 call sites use plain `loop.run_in_executor(get_shared_executor(), fn)`.
Pool-bounded; no asyncio awaiter timeout. The original slice 1.6
attempt added an awaiter-side timeout via `run_llm_in_executor` —
that helper still exists in the module but is **NOT wired into
production**. Reason:

  * The worker thread cannot be cancelled (Python sync code runs
    to completion).
  * Several call sites (run_brain_loop, jarvis_loop, pipe.handle_reply,
    daemon.handle_message) write durable state — memory rows,
    approval cards, intermediate sends — after the surface has
    already given up.
  * Result of an awaiter-only timeout: ghost turns. User sees
    "internal error" at T=120s, then a stale follow-up appears at
    T=300s when the abandoned worker writes its card / sends its
    intermediate message.

The proper fix is either (a) per-call deadlines INSIDE the LLM
client — the pattern slice 1.1 used for proposal_intent and slice
1.2 for the grounding judge — extended to brain_loop and
jarvis_loop, OR (b) turn-generation tokens that workers check
before writing side effects. Either way, that's a future slice.

**Shutdown:** `MaezDaemon.stop()` calls
`shutdown_shared_executor(wait=False, cancel_futures=True)` AFTER
all surfaces (telegram, surface_v2, public_bot) have stopped
submitting.

  * `wait=False`: a sync LLM call wedged on a dead llama.cpp
    would block stop() forever with `wait=True`. With `wait=False`,
    the daemon proceeds; stuck workers remain in the process
    until either they complete naturally or systemd's
    `TimeoutStopSec` sends SIGKILL.
  * `cancel_futures=True`: queued (not-yet-running) work is dropped
    immediately. Running sync work cannot be cancelled.

**Pool exhaustion under wedged backend:** N hung LLM calls fill
the pool with N stuck workers; the corresponding awaiters block
forever (no asyncio-side timeout in production today). Daemon's
reply path stalls. The proper fix is the per-call deadline pattern
described above. This slice closes the *thread leak* but not the
*caller-blocking-on-wedged-backend* shape — that requires the
deferred LLM-client-internal timeouts.

Inspect:
```python
from core.health.shared_executor import get_shared_executor, is_initialized
print(is_initialized(), get_shared_executor()._max_workers)
```
