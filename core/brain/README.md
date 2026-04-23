# core/brain

The two top-level conductors of Maez's thinking loop.

| Module | Role |
|---|---|
| [`brain_loop.py`](brain_loop.py) | 30-second reasoning cycle. Pulls perception, memory, soul, residue; emits a thought; scores it via `core/cognition`; stores what survives. Entry point called by `daemon/maez_daemon.py`. |
| [`conversation_controller.py`](conversation_controller.py) | Chat-side controller. Wraps incoming user turns in the decision pipeline, manages reply assembly, coordinates card presentation. |

## Invariants

- The reasoning cycle never blocks on network. Any cloud route is
  gated by `core.routing` and times out aggressively.
- The cycle is idempotent on crash: any state that matters is
  persisted before the cycle returns. Abort mid-cycle and the next
  cycle re-derives from disk.
- `brain_loop.py` never writes to soul — only to memory. Soul changes
  flow through `core.evolution.soul_loader`.

## Public surface

- `run_brain_loop(...)` — the daemon's main loop entry.
- `ConversationController` — chat-surface facade.

## Legacy import paths

`core.brain_loop` and `core.conversation_controller` are Phase-3 shims
that resolve to this package via `sys.modules`. Both paths are valid.
