# Cognition Liveness Contract v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maez's health contract truthful when the reasoning loop dies or stalls, and recover by exiting non-zero so systemd restarts the whole process.

**Architecture:** Keep recovery outside the reasoning loop. The historical loop body runs under a supervising thread target with a circuit breaker for repeated same-stage failures; a completed cycle resets the failure counter so only consecutive failures escalate. `/health.status` derives from the cheap in-memory heartbeat/thread-liveness fields, while heavy perception remains diagnostic data. FD-storm forensics are captured only on failure/stall, content-free.

**Tech Stack:** Python 3.14, `unittest`, Flask health route, user-systemd `Restart=on-failure`.

---

### Task 1: Heartbeat Truth Helpers

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_cognition_liveness_contract.py`

- [x] Write failing tests for `_cycle_heartbeat_health()` and a new `_health_status_from_reasoning_loop()` helper:
  - fresh loop -> `alive`
  - stale loop -> `stalled`
  - dead reasoning thread with a fresh timestamp -> `stalled`
  - safe-standby watchdog -> `safe_standby`
- [x] Implement `_cycle_liveness_stale_after_seconds()` with default `600` and env override `MAEZ_COGNITION_STALE_AFTER_SECONDS`, falling back to `600` on invalid/low values.
- [x] Implement `_health_status_from_reasoning_loop()` and wire `/health["status"]` through it instead of the hardcoded literal.
- [x] Run `tests/test_cognition_liveness_contract.py`.

### Task 2: Cycle Exception Boundary + Circuit Breaker

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_cognition_liveness_contract.py`

- [x] Write failing tests for `_handle_cycle_exception()`:
  - first `OSError(24, "Too many open files")` returns `False`, keeps `running=True`, stores failure summary, and marks `cycle_error_recovered`.
  - repeated same-stage failures hit threshold, return `True`, set `watchdog_state="safe_standby"`, `operator_resume_required=True`, and stop the loop.
  - a completed clean cycle resets the counter, so non-consecutive same-stage failures do not accumulate into safe-standby.
- [x] Add initialization fields: consecutive failure stage/count, last exception summary, last FD forensics, liveness threshold values.
- [x] Add `_handle_cycle_exception()` and `_enter_cycle_exception_safe_standby()`.
- [x] Run the historical `_loop()` body under `_run_reasoning_loop_supervised()` so an escaping exception cannot kill the reasoning thread silently; reset the failure counter at cycle completion.
- [x] Run `tests/test_cognition_liveness_contract.py` and existing perception/watchdog tests.

### Task 3: External Sentinel + Process Trip

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_cognition_liveness_contract.py`

- [x] Write failing tests for `_trip_process_for_liveness_failure()` using injected stop and exit functions; assert graceful stop is attempted before non-zero exit.
- [x] Store `self._reasoning_loop_thread` in `start()`.
- [x] Add `_start_cognition_liveness_sentinel()` thread that checks heartbeat age and thread liveness outside the reasoning thread.
- [x] On stale/dead loop, capture FD forensics, log content-free error, call `_trip_process_for_liveness_failure(reason="reasoning_loop_stalled")`.
- [x] Start the sentinel after the reasoning thread starts.
- [x] Run liveness tests.

### Task 4: FD Forensics

**Files:**
- Create: `core/health/fd_forensics.py`
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_cognition_liveness_contract.py`

- [x] Write failing test for `fd_forensics_snapshot()` returning only content-free keys: `fd_count`, `by_type`, `thread_count`, `state`.
- [x] Implement `/proc/<pid>/fd` classification with no target paths in the returned payload.
- [x] Store the latest snapshot in `self._last_fd_forensics` on EMFILE or sentinel trip.
- [x] Expose the latest snapshot under `/health["resource_forensics"]` and `body["heartbeat"]["last_fd_forensics_state"]`.
- [x] Run liveness/body tests.

### Task 5: Verification and Commit

**Files:**
- Modify: `docs/project-panel/state.json` only if the open wound text needs to point at the new health contract.

- [x] Run focused suites:
  - `.venv/bin/python -m unittest tests.test_cognition_liveness_contract tests.test_perception_resilience tests.test_metacognitive_watchdog tests.test_project_panel tests.test_maez_body_organ_view`
- [x] Run a floor command and name unrelated failures if present.
- [ ] Commit with predicted effect:
  - `fix(cognition): make daemon liveness truthful and recoverable`
  - Predicted effect: a future reasoning-loop EMFILE no longer leaves `/health.status=alive` over a dead mind; repeated/stale failure exits non-zero so user-systemd restarts Maez.
