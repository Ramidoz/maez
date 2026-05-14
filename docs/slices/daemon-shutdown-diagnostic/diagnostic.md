# Daemon Shutdown Diagnostic

Status: DIAGNOSTIC ONLY
Date: 2026-05-14
Scope: `maez.service` SIGTERM-to-SIGKILL shutdown behavior after the bounded-presence fix.

## Question

Did the bounded presence fix also close the prior `maez.service` SIGTERM hang?

Answer: no. The Cycle-2 heartbeat freeze is closed, but shutdown still waits for systemd's full stop timeout and ends by SIGKILL.

## Evidence

Before stop:

```text
ActiveState=active
SubState=running
MainPID=1045812
NRestarts=0
threads_before=307
```

Timed stop:

```text
systemctl --user stop maez.service
stop_rc=0 elapsed=90s
ActiveState=failed
SubState=failed
MainPID=0
NRestarts=0
```

Systemd journal:

```text
May 14 15:56:55 systemd: Stopping maez.service - Maez AI Agent Daemon (user scoped recovery)...
May 14 15:58:25 systemd: maez.service: State 'stop-sigterm' timed out. Killing.
May 14 15:58:25 systemd: maez.service: Killing process 1045812 (python) with signal SIGKILL.
May 14 15:58:25 systemd: maez.service: Main process exited, code=killed, status=9/KILL
May 14 15:58:25 systemd: maez.service: Failed with result 'timeout'.
```

During stop:

```text
ActiveState=deactivating
SubState=stop-sigterm
MainPID=1045812
threads_during=296
```

Thread-name histogram during stop:

```text
160 tokio-rt-worker
 32 reasoning-loop
 32 python
 32 presence-observ
 20 sqlx-sqlite-wor
 14 mediapipe/10463
  2 ThreadPoolExecu
  1 proposal-worker
  1 journal
  1 consolidation
  1 capability-plan
```

Daemon log:

```text
15:56:55 === Maez Daemon shutting down (signal: 15) ===
15:56:55 Continuity capsule written (graceful_shutdown, 1113 bytes)
15:56:55 Wake word listener stopped
15:56:55 Voice output shutdown
15:56:56 Presence worker did not finish within shutdown timeout
15:56:56 Telegram updater stop failed: This Updater is not running!
15:56:56 Telegram app stop failed: This Application is not running!
15:56:56 [Telegram] Disconnected from Telegram
15:56:59 WebSocket server: graceful shutdown (loop stopped during shutdown)
15:56:59 Health endpoint stopped.
15:57:06 Reasoning loop stopped.
```

After restart:

```text
ActiveState=active
SubState=running
MainPID=1052323
NRestarts=0
/health.reasoning_loop.cycle_stalled=false
/health.reasoning_loop.stage=reasoning_model
```

## Findings

1. SIGTERM still requires systemd's 90-second timeout and SIGKILL.

2. The Cycle-2 freeze and shutdown hang are not the same bug. The Cycle-2 freeze was a synchronous presence-observation call inside the reasoning loop. That was closed by `5690f33`. Shutdown still hangs after the reasoning loop, WebSocket server, health server, continuity capsule, Telegram, wake word, and voice output all start or complete their shutdown paths.

3. Presence is still implicated in shutdown cleanup. The bounded worker prevents presence from freezing the reasoning loop, but shutdown still logs `Presence worker did not finish within shutdown timeout`, and 32 `presence-observ` threads remain during stop.

4. Native/runtime threads remain the larger shape: `tokio-rt-worker`, `sqlx-sqlite-wor`, and `mediapipe/*` dominate the during-stop inventory. These are likely native library workers or async runtimes outside ordinary Python thread ownership.

5. `py-spy` is not installed in PATH, so this pass did not capture Python stack frames during the hang.

## Current Interpretation

The presence fix converted camera hangs from "blocks the reasoning loop" into "presence unavailable." It did not solve process termination. Shutdown is now a separate lifecycle problem: the daemon initiates graceful stop, but non-exiting native/Python worker threads keep the process alive until systemd kills it.

The next diagnostic should identify which thread families are non-daemon, which are native runtime pools, and which are still expected to be alive after `self.running=False`.

## Next Diagnostic Moves

1. Add shutdown-phase breadcrumbs to `/health` or logs:

```text
shutdown_started
continuity_written
voice_stopped
dream_worker_closed
presence_worker_closed_or_timeout
telegram_stopped
surface_v2_joined
public_bot_stopped
shared_executor_shutdown
ws_loop_stop_requested
health_server_shutdown_requested
pid_removed
```

2. Add a thread-inventory helper that can run before stop and during stop:

```text
thread_count
thread_name_histogram
python_daemon_vs_non_daemon_threads, if available
```

3. Install or otherwise provide a stack-dump tool before the next live stop test. `py-spy` was not available in PATH during this pass.

4. Investigate why a single bounded presence worker can leave 32 `presence-observ` threads. That count suggests either repeated blocked workers from prior restarts, native child threads inheriting the thread name prefix, or a thread-name truncation artifact.

## Non-Goals

- Do not disable M1. M1 is live, enabled, and staleness is `ok`.
- Do not widen TRF or touch memory recall.
- Do not treat this as an S2 blocker. It is runtime lifecycle hygiene.
- Do not assume presence is the only remaining culprit; it is implicated, not proven sole root cause.

## Plain English

Maez's heartbeat bug is fixed: the camera can no longer freeze the reasoning loop. But Maez still does not leave the room politely when systemd asks it to stop. It starts cleaning up, writes its continuity note, disconnects Telegram, stops the health server, and even stops the reasoning loop. Then some worker threads stay alive, so systemd waits 90 seconds and finally kills the process.

The next job is not a new organ. It is teaching the body to shut down cleanly.
