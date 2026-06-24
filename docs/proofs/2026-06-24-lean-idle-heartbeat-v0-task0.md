# Lean Idle Heartbeat v0 Task 0 Proof

Status: GO.

## Loop Seam

- `daemon/maez_daemon.py:9097` defines the live `_loop()`.
- `_loop()` computes `_cycle_doorman_gate` at `daemon/maez_daemon.py:9522`.
- `_CycleDoormanGateDecision.floor_wake` exists at `daemon/maez_daemon.py:1822`.
- `_cycle_doorman_gate_decision()` sets `floor_wake` from `ReasonCode.WAKE_MIN_FLOOR` at `daemon/maez_daemon.py:2322`.
- `_reason()` is the existing deep-cycle generation method at `daemon/maez_daemon.py:4992`.
- Non-empty cycle output reaches lived memory at `daemon/maez_daemon.py:9841` via `self.memory.store(...)` and the websocket `cycle_end` broadcast at `daemon/maez_daemon.py:9853`.
- Returning `HEARTBEAT_OK` follows the existing silent-cycle branch at `daemon/maez_daemon.py:9588`, which skips audit, storage, and broadcast.

## Private Thought Seam

- `PrivateThoughts.record_signal()` exists at `core/infra/private_thoughts.py:591`.
- `SignalKind.SELF_WONDERING` exists at `core/infra/private_thoughts.py:200`.
- `ProducerId.SELF_WONDERING` exists at `core/infra/private_thoughts.py:188`.
- The registry maps `self_wondering` to producer `self_wondering` and class `self_observation` at `core/infra/private_thoughts.py:248-250`.
- `derived_signals()` is content-light and behavior-facing at `core/infra/private_thoughts.py:766-815`.

## Reuse / Non-Reuse

- No existing `lean_idle_heartbeat` or idle heartbeat private-thought producer exists in `daemon/`, `core/`, or `tests/`.
- Existing `record_signal()` production use is clinical-boundary holding, not an idle heartbeat.
- `core/brain/developmental_heartbeat.py` writes core memory through `memory.store_core(...)` at line 164, so it is not the private notebook seam.
- `core/evolution/dream_state.py` stores dream proposals and contains explicit soul-adjacent apply paths (`/apply_dream`, `write_soul_note`, `edit_soul_section`), so it is not the private notebook seam.

## Stop Conditions Checked

- No new scheduler is required.
- No soul writer is required.
- No web/search/tool path is required.
- No foreground reply path is required.
- The narrow insertion point is before `_reason()` only when the existing doorman wakes for `wake_min_floor`.
