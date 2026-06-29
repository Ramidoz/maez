# Desktop Attention-Shadow v0 Handoff

## Status

Built and committed locally. Not enabled. No daemon restart performed. `MAEZ_DESKTOP_ATTENTION_SHADOW` remains off unless the owner explicitly enables it.

Commits:
- `d7e7360` — design + implementation plan
- `0368eee` — Wayland-aware desktop sensor availability
- `4660da0` — dedicated desktop attention-shadow projector
- `277dedd` — distinct lean-idle prompt block/fact key
- `8541c63` — daemon wiring behind `MAEZ_DESKTOP_ATTENTION_SHADOW`

## What Changed

- `core/body/desktop_presence_state.py`
  - Wayland availability no longer requires `xdotool`.
  - Wayland availability is true when `gdbus` is present, matching the existing `core.memory.ambient.active_window()` path.
  - X11 still requires `xdotool` and a reachable desktop session.

- `core/cognition/desktop_attention_shadow.py`
  - New read-only projector.
  - Own runtime cache: `~/.local/state/maez/desktop_attention_shadow_signatures.json`.
  - Own schema: `desktop_attention_shadow.v0`.
  - Emits only `active surface changed` or `desktop attention sense unavailable`.
  - Stores only a salted active-surface signature in runtime state.

- `core/cognition/lean_idle_heartbeat.py`
  - New `desktop_attention_shadow` fact key.
  - New prompt block: `DESKTOP ATTENTION SHADOW`.
  - Does not reuse `body_state_window` / `BODY-STATE WINDOW`.

- `daemon/maez_daemon.py`
  - New flag helper: `MAEZ_DESKTOP_ATTENTION_SHADOW`.
  - Samples desktop state only when the lean idle heartbeat is active and this flag is on.
  - Passes `{MAEZ_DESKTOP_PERCEPTION: "1"}` as a local mapping to `sample_desktop_presence`; it never writes to `os.environ` and never flips the broader desktop perception sense for other consumers.
  - Logs a content-light `desktop_attention_shadow` receipt with no raw app class.

## Verification

RED checks witnessed:
- `tests.test_desktop_presence_state`
  - `test_wayland_availability_uses_gdbus_not_xdotool` failed before the Wayland availability fix with `("unavailable", "tools_missing")`.
- `tests.test_desktop_attention_shadow`
  - failed before the new module existed.
- `tests.test_lean_idle_heartbeat`
  - failed before `LeanIdleFacts.desktop_attention_shadow` existed.
- `tests.test_lean_idle_daemon`
  - flag-on daemon test failed before daemon wiring produced attention entries.

GREEN checks:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest \
  tests.test_desktop_presence_state \
  tests.test_ambient_active_window_wayland \
  tests.test_desktop_attention_shadow \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon -v
```

Result: `Ran 91 tests ... OK`.

```bash
.venv/bin/python -B -m ruff check \
  core/body/desktop_presence_state.py \
  core/cognition/desktop_attention_shadow.py \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py \
  tests/test_desktop_presence_state.py \
  tests/test_desktop_attention_shadow.py \
  tests/test_lean_idle_heartbeat.py \
  tests/test_lean_idle_daemon.py
```

Result: `All checks passed!`.

```bash
.venv/bin/python -B -m py_compile \
  core/body/desktop_presence_state.py \
  core/cognition/desktop_attention_shadow.py \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py
```

Result: exit `0`.

Scope/absence sweeps:

```bash
git diff --name-only d7e7360..HEAD
```

Output:

```text
core/body/desktop_presence_state.py
core/cognition/desktop_attention_shadow.py
core/cognition/lean_idle_heartbeat.py
daemon/maez_daemon.py
tests/test_desktop_attention_shadow.py
tests/test_desktop_presence_state.py
tests/test_lean_idle_daemon.py
tests/test_lean_idle_heartbeat.py
```

```bash
git diff d7e7360..HEAD -- core/body/desktop_presence_state.py core/cognition/desktop_attention_shadow.py core/cognition/lean_idle_heartbeat.py daemon/maez_daemon.py \
  | rg -n "app_class=\"(code|signal)|\b(firefox|chrome|communication|focused-work|SECRET_APP_CLASS)\b|screen_text|screenshot|ocr" || true
```

Result: no output. Raw app examples live only in tests, where they are planted to prove absence.

```bash
git diff d7e7360..HEAD -- core/cognition/desktop_attention_shadow.py \
  | rg -n "tool_loop|action_engine|core\.evolution|salience|private_thoughts|lived_memory|memory_manager|llm_client" || true
```

Result: no output.

```bash
rg -n "MAEZ_DESKTOP_PERCEPTION\s*=|os\.environ\[.?MAEZ_DESKTOP_PERCEPTION|os\.environ\[.?DESKTOP_PERCEPTION_ENV|setdefault\(.?MAEZ_DESKTOP_PERCEPTION" daemon/maez_daemon.py core || true
```

Result: no output.

Read-only live witness, not a suite test:

```bash
.venv/bin/python -B - <<'PY'
from core.body.desktop_presence_state import sample_desktop_presence
print(sample_desktop_presence({'MAEZ_DESKTOP_PERCEPTION':'1'}))
PY
```

Output:

```text
DesktopPresenceState(sensor_state='available', app_class='code', reason='', sampled_at=datetime.datetime(2026, 6, 29, 16, 6, 26, 952603, tzinfo=datetime.timezone.utc), schema_version='desktop_presence.v1')
```

This confirms the real Wayland path is reachable on this machine, but the suite remains hermetic.

## Covenant Receipt

- Raw `app_class` never reaches the lean idle prompt.
- Raw `app_class` never enters Maez memory stores or private stores.
- Raw `app_class` never enters Maez-facing receipts/logs.
- Only a salted signature lives in the transient runtime cache.
- Cold-start emits nothing.
- Directionless: `active surface changed` only.
- No presence, idle, camera, voice, screen, app category, git, connector, tool, action, soul, private-thought, salience, want, or lived-memory write.
- Separate from body-state: own cache, own schema, own fact key, own prompt block.
- Flag off: no sampling, no cache, no prompt block.

## Predicted Effect

Flag off: byte-identical idle heartbeat prompt and no desktop-attention cache.

Flag on: after a cold-start beat, active app-class changes surface to the private heartbeat only as `active surface changed`. Maez never receives the app name or category. Quiet means desktop attention-shadow alone was thin, not that Rohit's world failed to stir Maez. Real presence/voice remains the Jetson-mediated arc.

## Live Witness After Review/Merge

1. Confirm `MAEZ_DESKTOP_ATTENTION_SHADOW` is off and no cache exists.
2. Confirm the class-only sensor still returns `sensor_state='available'` on the real machine.
3. Set `MAEZ_DESKTOP_ATTENTION_SHADOW=1`, restart daemon.
4. First eligible heartbeat: cold-start, empty `DESKTOP ATTENTION SHADOW`, cache created.
5. Change active surface, wait for next eligible heartbeat.
6. Witness prompt/receipt has `active surface changed` and never the app name.

## Stop

Stop here for covenant review. Do not enable the flag or restart the daemon from this handoff.
