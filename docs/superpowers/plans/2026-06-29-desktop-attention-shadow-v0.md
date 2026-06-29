# Desktop Attention-Shadow v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Spec: [2026-06-29-desktop-attention-shadow-v0-design.md](../specs/2026-06-29-desktop-attention-shadow-v0-design.md).

**Goal:** Feed Maez's lean idle heartbeat a content-light desktop attention shadow: "Rohit's active surface changed," never the app, category, direction, screen, presence, camera, or voice.

**Architecture:** First fix the existing desktop sensor wrapper so Wayland can use the already-working active-window path without requiring `xdotool`. Then add a dedicated `desktop_attention_shadow` projector with its own runtime cache and schema, and wire it into the lean idle prompt through a distinct fact key and `DESKTOP ATTENTION SHADOW` block behind `MAEZ_DESKTOP_ATTENTION_SHADOW`. The slice is read-only, flag-off invisible, cold-start baseline-only, and separate from body-state.

**Tech Stack:** Python 3 stdlib, unittest, existing daemon/heartbeat modules. Test runner: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest ...`.

**Covenant rails:** Desktop attention only. No presence, idle, camera, mic, raw screen, app name, app category, git, connector, search, tool, action, soul, private-thought, salience, want, or lived-memory write. Raw `app_class` may be sampled locally but must never enter Maez prompt, Maez memory stores, private stores, or Maez-facing receipts/logs. Only a salted signature may live in `~/.local/state/maez/desktop_attention_shadow_signatures.json`.

---

## File Structure

- Modify `core/body/desktop_presence_state.py`
  - Make the existing availability wrapper Wayland-aware without enabling broader desktop perception globally.
- Modify `tests/test_desktop_presence_state.py`
  - Add hermetic tests for Wayland availability and no `xdotool` hard-gate.
- Create `core/cognition/desktop_attention_shadow.py`
  - Dedicated attention-shadow projection, runtime cache, receipt payload, and no downstream imports.
- Create `tests/test_desktop_attention_shadow.py`
  - Load-bearing privacy/cold-start/cache/import tests.
- Modify `core/cognition/lean_idle_heartbeat.py`
  - Add `desktop_attention_shadow` facts and a separate `DESKTOP ATTENTION SHADOW` prompt block.
- Modify `tests/test_lean_idle_heartbeat.py`
  - Assert distinct block/fact key, directionless rendering, and raw absence.
- Modify `daemon/maez_daemon.py`
  - Wire the shadow behind `MAEZ_DESKTOP_ATTENTION_SHADOW` without touching `MAEZ_DESKTOP_PERCEPTION`.
- Modify `tests/test_lean_idle_daemon.py`
  - Assert flag-off byte-identical/no cache and flag-on isolated wiring.
- Create `docs/handoffs/2026-06-29-desktop-attention-shadow-v0-handoff.md`
  - Evidence, predicted effect, witness steps, and interpretation guard.

---

### Task 0: Pin the Sensor Seam and Write RED Tests

**Files:**
- Modify: `tests/test_desktop_presence_state.py`
- Modify later: `core/body/desktop_presence_state.py`

- [ ] **Step 1: Add failing hermetic Wayland availability tests**

Add these tests to `tests/test_desktop_presence_state.py`:

```python
from unittest import mock


class DesktopPresenceStateTests(unittest.TestCase):
    # keep existing tests

    def test_wayland_availability_uses_gdbus_not_xdotool(self):
        from core.body import desktop_presence_state as dps

        def has_binary(name: str) -> bool:
            return name == "gdbus"

        with mock.patch.dict(
            "os.environ",
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            clear=True,
        ), mock.patch.object(dps.body_capabilities, "has_binary", has_binary):
            self.assertEqual(dps._desktop_availability(), ("available", ""))

    def test_wayland_availability_reports_tools_missing_without_gdbus(self):
        from core.body import desktop_presence_state as dps

        with mock.patch.dict(
            "os.environ",
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            clear=True,
        ), mock.patch.object(dps.body_capabilities, "has_binary", return_value=False):
            self.assertEqual(dps._desktop_availability(), ("unavailable", "tools_missing"))

    def test_x11_availability_still_requires_xdotool_and_session(self):
        from core.body import desktop_presence_state as dps

        with mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True), \
            mock.patch.object(dps.body_capabilities, "has_binary", return_value=True), \
            mock.patch.object(dps.body_capabilities, "desktop_session_reachable", return_value=True):
            self.assertEqual(dps._desktop_availability(), ("available", ""))
```

- [ ] **Step 2: Run RED**

Run:

```bash
cd /home/rohit/maez
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_desktop_presence_state -v
```

Expected RED: `test_wayland_availability_uses_gdbus_not_xdotool` fails because current `_desktop_availability()` returns `("unavailable", "tools_missing")` when `xdotool` is absent.

- [ ] **Step 3: Implement the Wayland-aware availability fix**

In `core/body/desktop_presence_state.py`, replace `_desktop_availability()` with this shape:

```python
def _is_wayland_session() -> bool:
    return (
        os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def _desktop_availability() -> tuple[str, str]:
    """Return (sensor_state, reason) for honest desktop reachability."""
    if _is_wayland_session():
        if not body_capabilities.has_binary("gdbus"):
            return "unavailable", "tools_missing"
        return "available", ""
    if not body_capabilities.has_binary("xdotool"):
        return "unavailable", "tools_missing"
    if not os.environ.get("DISPLAY"):
        return "unavailable", "wayland"
    if not body_capabilities.desktop_session_reachable():
        return "unavailable", "session_unreachable"
    return "available", ""
```

Do not add new D-Bus code here. `sample_desktop_presence()` already calls `core.memory.ambient.active_window()`, and that function already routes Wayland through `gdbus`.

- [ ] **Step 4: Run GREEN**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_desktop_presence_state tests.test_ambient_active_window_wayland -v
```

Expected GREEN: existing class-only/no-title behavior still passes; new Wayland tests pass hermetically.

- [ ] **Step 5: Commit**

```bash
git add core/body/desktop_presence_state.py tests/test_desktop_presence_state.py
git commit -m "fix(body): allow Wayland desktop attention sampling"
```

Commit body must include:

```text
## Predicted effect
With desktop perception explicitly enabled by a caller, Wayland sessions can report a class-only active window through the existing ambient D-Bus path without requiring xdotool. With all flags off, no live Maez behavior changes.
```

---

### Task 1: Build the Dedicated Attention-Shadow Module

**Files:**
- Create: `core/cognition/desktop_attention_shadow.py`
- Create: `tests/test_desktop_attention_shadow.py`

- [ ] **Step 1: Write failing module tests**

Create `tests/test_desktop_attention_shadow.py`:

```python
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.body.desktop_presence_state import DesktopPresenceState

_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)


class DesktopAttentionShadowTests(unittest.TestCase):
    def _path(self, td: str) -> Path:
        return Path(td) / "desktop_attention_shadow_signatures.json"

    def test_default_signature_path_is_distinct_runtime_cache_not_memory(self):
        from core.cognition.desktop_attention_shadow import default_signature_path

        path = default_signature_path()
        self.assertIn(".local/state/maez", str(path))
        self.assertTrue(str(path).endswith("desktop_attention_shadow_signatures.json"))
        self.assertNotIn("world_window_signatures.json", str(path))
        self.assertNotIn("/memory/", str(path))

    def test_flag_off_returns_none_and_creates_no_cache(self):
        from core.cognition.desktop_attention_shadow import maybe_collect_desktop_attention_shadow

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(sensor_state="available", app_class="code", sampled_at=_NOW),
                enabled=False,
                signature_path=path,
            )
            self.assertIsNone(result)
            self.assertFalse(path.exists())

    def test_cold_start_records_signature_but_emits_no_entry(self):
        from core.cognition.desktop_attention_shadow import maybe_collect_desktop_attention_shadow

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(sensor_state="available", app_class="code", sampled_at=_NOW),
                enabled=True,
                signature_path=path,
            )
            self.assertIsNotNone(result)
            self.assertTrue(result.cold_start)
            self.assertEqual(result.entries, ())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "desktop_attention_shadow.v0")
            self.assertIn("active_surface", payload["signatures"])
            self.assertNotIn("code", path.read_text(encoding="utf-8"))

    def test_changed_app_class_emits_directionless_shadow_only(self):
        from core.cognition.desktop_attention_shadow import maybe_collect_desktop_attention_shadow

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(sensor_state="available", app_class="code", sampled_at=_NOW),
                enabled=True,
                signature_path=path,
            )
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(sensor_state="available", app_class="signal", sampled_at=_NOW),
                enabled=True,
                signature_path=path,
            )
            self.assertFalse(result.cold_start)
            self.assertEqual(len(result.entries), 1)
            entry = result.entries[0]
            self.assertEqual(entry.field, "active_surface")
            self.assertEqual(entry.phrase, "active surface changed")
            rendered = repr(result) + json.dumps(result.receipt_payload(), sort_keys=True)
            self.assertNotIn("code", rendered)
            self.assertNotIn("signal", rendered)
            self.assertNotIn("communication", rendered)
            self.assertNotIn("focused-work", rendered)
            self.assertNotIn("to ", rendered.lower())
            self.assertNotIn("from ", rendered.lower())

    def test_same_app_class_emits_no_shadow(self):
        from core.cognition.desktop_attention_shadow import maybe_collect_desktop_attention_shadow

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            state = DesktopPresenceState(sensor_state="available", app_class="code", sampled_at=_NOW)
            maybe_collect_desktop_attention_shadow(state, enabled=True, signature_path=path)
            result = maybe_collect_desktop_attention_shadow(state, enabled=True, signature_path=path)
            self.assertEqual(result.entries, ())

    def test_unavailable_sensor_returns_label_without_cache_or_delta(self):
        from core.cognition.desktop_attention_shadow import maybe_collect_desktop_attention_shadow

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(sensor_state="unavailable", reason="no_active_window", sampled_at=_NOW),
                enabled=True,
                signature_path=path,
            )
            self.assertFalse(result.cold_start)
            self.assertEqual(len(result.entries), 1)
            self.assertEqual(result.entries[0].phrase, "desktop attention sense unavailable")
            self.assertFalse(path.exists())

    def test_module_imports_no_command_or_downstream_writers(self):
        src = Path("core/cognition/desktop_attention_shadow.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        forbidden = {
            "core.actions.action_engine",
            "core.actions.tool_loop",
            "core.evolution.drive_driven_curiosity",
            "core.evolution.wonderings",
            "core.evolution.wants",
            "core.cognition.salience_ledger",
            "core.cognition.fresh_moment_receipts",
            "core.infra.private_thoughts",
            "core.memory.lived_memory",
            "core.memory.memory_manager",
            "core.llm_client",
        }
        self.assertTrue(forbidden.isdisjoint(imported), imported)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run RED**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_desktop_attention_shadow -v
```

Expected RED: import failure for `core.cognition.desktop_attention_shadow`.

- [ ] **Step 3: Implement the module**

Create `core/cognition/desktop_attention_shadow.py`:

```python
"""Content-light desktop attention shadow for the lean idle heartbeat.

This is a sense projector, not a command path. It compares a class-only active
surface signature across beats and emits only "active surface changed"; raw
app classes stay out of Maez prompt, memory stores, and receipts.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from core.body.desktop_presence_state import DesktopPresenceState

SCHEMA_VERSION = "desktop_attention_shadow.v0"
_HASH_SALT = "maez.desktop_attention_shadow.v0"
_FIELD = "active_surface"


@dataclass(frozen=True)
class DesktopAttentionEntry:
    field: str
    phrase: str
    provenance: str
    sensitivity: str


@dataclass(frozen=True)
class DesktopAttentionResult:
    entries: tuple[DesktopAttentionEntry, ...]
    cold_start: bool
    sensor_state: str
    reason: str = ""
    schema_version: str = SCHEMA_VERSION

    def receipt_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "cold_start": bool(self.cold_start),
            "sensor_state": self.sensor_state,
            "reason": self.reason,
            "entry_count": len(self.entries),
            "entries": [
                {
                    "field": entry.field,
                    "provenance": entry.provenance,
                    "sensitivity": entry.sensitivity,
                }
                for entry in self.entries
            ],
        }


def default_signature_path() -> Path:
    return Path.home() / ".local" / "state" / "maez" / "desktop_attention_shadow_signatures.json"


def maybe_collect_desktop_attention_shadow(
    state: DesktopPresenceState,
    *,
    enabled: bool,
    signature_path: Path | None = None,
) -> DesktopAttentionResult | None:
    if not enabled:
        return None
    return DesktopAttentionShadow(signature_path or default_signature_path()).entries_for(state)


class DesktopAttentionShadow:
    def __init__(self, signature_path: Path) -> None:
        self.signature_path = Path(signature_path)

    def entries_for(self, state: DesktopPresenceState) -> DesktopAttentionResult:
        if state.sensor_state != "available" or not state.app_class:
            return DesktopAttentionResult(
                entries=(
                    DesktopAttentionEntry(
                        field="desktop_sensor_state",
                        phrase="desktop attention sense unavailable",
                        provenance="desktop_presence_state.sensor_state",
                        sensitivity="safe_label",
                    ),
                ),
                cold_start=False,
                sensor_state=str(state.sensor_state),
                reason=str(state.reason or ""),
            )

        current = {_FIELD: _signature(str(state.app_class))}
        previous = self._read_signatures()
        self._write_signatures(current)
        if previous is None:
            return DesktopAttentionResult(entries=(), cold_start=True, sensor_state="available")
        if previous.get(_FIELD) == current[_FIELD]:
            return DesktopAttentionResult(entries=(), cold_start=False, sensor_state="available")
        return DesktopAttentionResult(
            entries=(
                DesktopAttentionEntry(
                    field=_FIELD,
                    phrase="active surface changed",
                    provenance="desktop_presence_state.app_class",
                    sensitivity="sensitive_delta",
                ),
            ),
            cold_start=False,
            sensor_state="available",
        )

    def _read_signatures(self) -> dict[str, str] | None:
        try:
            with self.signature_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return None
        except Exception:
            return None
        if not isinstance(data, Mapping):
            return None
        signatures = data.get("signatures")
        if not isinstance(signatures, Mapping):
            return None
        return {str(key): str(value) for key, value in signatures.items()}

    def _write_signatures(self, signatures: Mapping[str, str]) -> None:
        self.signature_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.signature_path.with_suffix(self.signature_path.suffix + ".tmp")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "signatures": dict(sorted((str(k), str(v)) for k, v in signatures.items())),
        }
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
        tmp.replace(self.signature_path)


def _signature(app_class: str) -> str:
    material = f"{_HASH_SALT}:{app_class.strip().lower()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_desktop_attention_shadow -v
```

Expected GREEN.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/desktop_attention_shadow.py tests/test_desktop_attention_shadow.py
git commit -m "feat(cognition): add desktop attention shadow projector"
```

Commit body must include:

```text
## Predicted effect
No live behavior changes while MAEZ_DESKTOP_ATTENTION_SHADOW remains unset. When called explicitly, the projector records only a salted active-surface signature in runtime state and emits either "active surface changed" or "desktop attention sense unavailable"; raw app classes never reach Maez-facing output.
```

---

### Task 2: Add the Dedicated Prompt Seam

**Files:**
- Modify: `core/cognition/lean_idle_heartbeat.py`
- Modify: `tests/test_lean_idle_heartbeat.py`

- [ ] **Step 1: Add failing prompt tests**

Add tests to `tests/test_lean_idle_heartbeat.py`:

```python
def test_prompt_renders_desktop_attention_shadow_as_own_block(self) -> None:
    prompt = build_lean_idle_prompt(
        LeanIdleFacts(
            cycle=7,
            doorman_reason="wake_min_floor",
            self_card_text="SELF",
            desktop_attention_shadow=(
                {
                    "field": "active_surface",
                    "phrase": "active surface changed",
                    "provenance": "desktop_presence_state.app_class",
                    "sensitivity": "sensitive_delta",
                    "signature": "raw-SECRET_APP_CLASS-secret",
                },
            ),
        )
    )

    self.assertIn("DESKTOP ATTENTION SHADOW", prompt.text)
    self.assertIn("active surface changed", prompt.text)
    self.assertIn("provenance: desktop_presence_state.app_class", prompt.text)
    self.assertIn("sensitivity: sensitive_delta", prompt.text)
    self.assertNotIn("BODY-STATE WINDOW", prompt.text)
    self.assertNotIn("SECRET_APP_CLASS", prompt.text)
    self.assertNotIn("raw-SECRET_APP_CLASS-secret", prompt.text)
    self.assertIn("desktop_attention_shadow", prompt.fact_keys)
    self.assertIn(
        f"If nothing is worth privately carrying, answer exactly {HEARTBEAT_OK}.",
        prompt.text,
    )


def test_prompt_omits_desktop_attention_shadow_when_empty(self) -> None:
    prompt = build_lean_idle_prompt(
        LeanIdleFacts(
            cycle=7,
            doorman_reason="wake_min_floor",
            self_card_text="SELF",
            desktop_attention_shadow=(),
        )
    )

    self.assertNotIn("DESKTOP ATTENTION SHADOW", prompt.text)
```

- [ ] **Step 2: Run RED**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -v
```

Expected RED: `LeanIdleFacts` does not accept `desktop_attention_shadow`.

- [ ] **Step 3: Implement the prompt seam**

In `core/cognition/lean_idle_heartbeat.py`:

1. Add a new field to `LeanIdleFacts`:

```python
desktop_attention_shadow: tuple[Mapping[str, object], ...] = ()
```

2. Add a block renderer:

```python
def _desktop_attention_shadow_block(entries: tuple[Mapping[str, object], ...]) -> str:
    if not entries:
        return ""
    lines: list[str] = []
    for entry in entries:
        phrase = _compact(entry.get("phrase"))
        if not phrase:
            continue
        provenance = _compact(entry.get("provenance"))
        sensitivity = _compact(entry.get("sensitivity"))
        parts = [phrase]
        if provenance:
            parts.append(f"provenance: {provenance}")
        if sensitivity:
            parts.append(f"sensitivity: {sensitivity}")
        lines.append("- " + "; ".join(parts))
    if not lines:
        return ""
    return "\nDESKTOP ATTENTION SHADOW (changes since last beat)\n" + "\n".join(lines) + "\n"
```

3. Add `"desktop_attention_shadow"` to `fact_keys`.

4. Render the new block after `_body_state_window_block(...)`:

```python
+ _desktop_attention_shadow_block(facts.desktop_attention_shadow)
```

Do not render `signature`, `sensor_state`, `reason`, or raw `app_class`.

- [ ] **Step 4: Run GREEN**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_lean_idle_heartbeat -v
```

Expected GREEN.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/lean_idle_heartbeat.py tests/test_lean_idle_heartbeat.py
git commit -m "feat(cognition): add desktop attention prompt block"
```

Commit body must include:

```text
## Predicted effect
No live behavior changes until a caller passes desktop_attention_shadow facts. When passed, the lean idle prompt renders a distinct DESKTOP ATTENTION SHADOW block, separate from BODY-STATE WINDOW, and omits signatures/raw app classes.
```

---

### Task 3: Wire the Daemon Behind `MAEZ_DESKTOP_ATTENTION_SHADOW`

**Files:**
- Modify: `daemon/maez_daemon.py`
- Modify: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Add failing daemon tests**

Add tests to `tests/test_lean_idle_daemon.py` near the existing body-window tests:

```python
def test_desktop_attention_shadow_flag_off_does_not_create_cache_or_sample(self):
    from daemon.maez_daemon import MaezDaemon
    import core.cognition.lean_idle_heartbeat as lih

    daemon = object.__new__(MaezDaemon)
    daemon.cycle_count = 7
    daemon.private_thoughts = None
    daemon._lean_idle_self_card_text = lambda: "SELF"
    daemon._lean_idle_private_signal_summary = lambda: {}
    daemon._lean_idle_time_facts = lambda: {}
    daemon._lean_idle_body_state = lambda: {}
    daemon._lean_idle_open_loops = lambda: {}
    daemon._lean_idle_recent_private_thoughts = lambda: ()
    captured = {}

    def capture(*, facts, **kwargs):
        captured["facts"] = facts
        return lih.LeanIdleResult(False, False, None, None, "shadow_only", {})

    with tempfile.TemporaryDirectory() as td:
        cache_path = Path(td) / "desktop_attention_shadow_signatures.json"
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1"},
            clear=True,
        ), mock.patch(
            "core.cognition.desktop_attention_shadow.default_signature_path",
            return_value=cache_path,
        ), mock.patch(
            "core.body.desktop_presence_state.sample_desktop_presence",
            side_effect=AssertionError("must not sample when flag off"),
        ), mock.patch.object(lih, "run_lean_idle_heartbeat", capture):
            daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertFalse(cache_path.exists())
        self.assertEqual(captured["facts"].desktop_attention_shadow, ())


def test_desktop_attention_shadow_flag_on_passes_directionless_entries(self):
    from daemon.maez_daemon import MaezDaemon
    import core.cognition.lean_idle_heartbeat as lih

    daemon = object.__new__(MaezDaemon)
    daemon.cycle_count = 7
    daemon.private_thoughts = None
    daemon._lean_idle_self_card_text = lambda: "SELF"
    daemon._lean_idle_private_signal_summary = lambda: {}
    daemon._lean_idle_time_facts = lambda: {}
    daemon._lean_idle_body_state = lambda: {}
    daemon._lean_idle_open_loops = lambda: {}
    daemon._lean_idle_recent_private_thoughts = lambda: ()
    captured = {}

    def capture(*, facts, **kwargs):
        captured["facts"] = facts
        return lih.LeanIdleResult(False, False, None, None, "shadow_only", {})

    states = [
        DesktopPresenceState(sensor_state="available", app_class="code"),
        DesktopPresenceState(sensor_state="available", app_class="signal"),
    ]

    with tempfile.TemporaryDirectory() as td:
        cache_path = Path(td) / "desktop_attention_shadow_signatures.json"
        with mock.patch.dict(
            "os.environ",
            {
                "MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1",
                "MAEZ_DESKTOP_ATTENTION_SHADOW": "1",
            },
            clear=True,
        ), mock.patch(
            "core.cognition.desktop_attention_shadow.default_signature_path",
            return_value=cache_path,
        ), mock.patch(
            "core.body.desktop_presence_state.sample_desktop_presence",
            side_effect=states,
        ), mock.patch.object(lih, "run_lean_idle_heartbeat", capture):
            daemon._maybe_run_lean_idle_heartbeat({}, _gate())
            daemon._maybe_run_lean_idle_heartbeat({}, _gate())

    entries = captured["facts"].desktop_attention_shadow
    self.assertEqual(len(entries), 1)
    self.assertEqual(entries[0]["field"], "active_surface")
    self.assertEqual(entries[0]["phrase"], "active surface changed")
    self.assertNotIn("code", repr(entries))
    self.assertNotIn("signal", repr(entries))
```

Make sure the test file imports these if absent:

```python
import tempfile
from pathlib import Path
from core.body.desktop_presence_state import DesktopPresenceState
```

- [ ] **Step 2: Run RED**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_lean_idle_daemon -v
```

Expected RED: no daemon flag helper/wiring yet.

- [ ] **Step 3: Implement the daemon flag and wiring**

In `daemon/maez_daemon.py`:

1. Add a flag helper near `_world_window_shadow_enabled()`:

```python
def _desktop_attention_shadow_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return _env_flag("MAEZ_DESKTOP_ATTENTION_SHADOW", environ=environ)
```

2. In `_maybe_run_lean_idle_heartbeat`, initialize:

```python
desktop_attention_shadow: tuple[dict[str, object], ...] = ()
```

3. After body-window collection and before broker signature calculation, add:

```python
if _desktop_attention_shadow_enabled():
    try:
        from core.body.desktop_presence_state import (
            PERCEPTION_ENV as DESKTOP_PERCEPTION_ENV,
            sample_desktop_presence,
        )
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        desktop_state = sample_desktop_presence({DESKTOP_PERCEPTION_ENV: "1"})
        attention_result = maybe_collect_desktop_attention_shadow(
            desktop_state,
            enabled=True,
        )
        if attention_result is not None:
            desktop_attention_shadow = tuple(
                {
                    "field": entry.field,
                    "phrase": entry.phrase,
                    "provenance": entry.provenance,
                    "sensitivity": entry.sensitivity,
                }
                for entry in attention_result.entries
            )
            logger.info(
                "desktop_attention_shadow receipt=%s",
                json.dumps(attention_result.receipt_payload(), sort_keys=True),
            )
    except Exception as exc:
        logger.info(
            "desktop_attention_shadow receipt=%s",
            json.dumps(
                {
                    "schema_version": "desktop_attention_shadow.v0",
                    "skip_reason": "error",
                    "error_class": exc.__class__.__name__,
                },
                sort_keys=True,
            ),
        )
```

This passes a local env mapping to `sample_desktop_presence`; it must not set `os.environ["MAEZ_DESKTOP_PERCEPTION"]` or flip the broader sense for other consumers.

4. Pass it to `LeanIdleFacts`:

```python
desktop_attention_shadow=desktop_attention_shadow,
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_lean_idle_daemon tests.test_lean_idle_heartbeat tests.test_desktop_attention_shadow tests.test_desktop_presence_state -v
```

Expected GREEN.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(daemon): wire desktop attention shadow into idle heartbeat"
```

Commit body must include:

```text
## Predicted effect
With MAEZ_DESKTOP_ATTENTION_SHADOW unset, the idle heartbeat prompt and daemon behavior remain unchanged and no desktop-attention cache is created. With the flag on, the daemon samples the desktop sense only for this shadow path, logs a content-light receipt, and passes a distinct desktop_attention_shadow block to the private heartbeat.
```

---

### Task 4: Absence Sweep, Static Guards, and Live-Witness Handoff

**Files:**
- Create: `docs/handoffs/2026-06-29-desktop-attention-shadow-v0-handoff.md`

- [ ] **Step 1: Run focused verification**

Run:

```bash
cd /home/rohit/maez
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest \
  tests.test_desktop_presence_state \
  tests.test_ambient_active_window_wayland \
  tests.test_desktop_attention_shadow \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon -v

.venv/bin/python -B -m ruff check \
  core/body/desktop_presence_state.py \
  core/cognition/desktop_attention_shadow.py \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py \
  tests/test_desktop_presence_state.py \
  tests/test_desktop_attention_shadow.py \
  tests/test_lean_idle_heartbeat.py \
  tests/test_lean_idle_daemon.py

.venv/bin/python -B -m py_compile \
  core/body/desktop_presence_state.py \
  core/cognition/desktop_attention_shadow.py \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py
```

Expected: tests pass, ruff clean, compile clean.

- [ ] **Step 2: Run absence and scope sweeps**

Run:

```bash
git diff --name-only HEAD~3..HEAD
git diff HEAD~3..HEAD -- core/cognition/desktop_attention_shadow.py core/cognition/lean_idle_heartbeat.py daemon/maez_daemon.py | rg -n "signal|code|firefox|chrome|communication|focused-work|idle bucket|screen_text|screenshot|ocr|search|tool_loop|action_engine|private_thoughts|salience|wonderings|wants|soul|lived_memory" || true
rg -n "MAEZ_DESKTOP_PERCEPTION\\s*=|os\\.environ\\[.?MAEZ_DESKTOP_PERCEPTION|body_state_window.*desktop|DESKTOP ATTENTION SHADOW|desktop_attention_shadow" core daemon tests
```

Expected:
- Raw planted app classes appear only in tests as planted forbidden strings.
- No production code writes `MAEZ_DESKTOP_PERCEPTION` into `os.environ`.
- `desktop_attention_shadow` appears as its own fact/block, not inside `body_state_window`.
- No command/downstream writer imports in `desktop_attention_shadow.py`.

- [ ] **Step 3: Write the handoff**

Create `docs/handoffs/2026-06-29-desktop-attention-shadow-v0-handoff.md` with:

```markdown
# Desktop Attention-Shadow v0 Handoff

## Status
Built, not enabled. No restart performed. `MAEZ_DESKTOP_ATTENTION_SHADOW` remains off unless the owner explicitly enables it.

## What changed
- Wayland desktop availability no longer requires `xdotool`; it uses the existing class-only active-window path when explicitly sampled.
- Added `core.cognition.desktop_attention_shadow` with its own runtime cache:
  `~/.local/state/maez/desktop_attention_shadow_signatures.json`
  schema `desktop_attention_shadow.v0`.
- Added distinct `desktop_attention_shadow` facts and `DESKTOP ATTENTION SHADOW` prompt block.
- Wired daemon collection behind `MAEZ_DESKTOP_ATTENTION_SHADOW` only.

## Verification
- [paste focused unittest command and result]
- [paste ruff command and result]
- [paste py_compile command and result]
- [paste absence/scope sweep result]

## Covenant receipt
- Raw `app_class` never reaches prompt, Maez memory stores/private stores, or Maez-facing receipts/logs.
- Only salted signature reaches runtime cache.
- Cold-start emits nothing.
- Directionless: "active surface changed" only.
- No presence, camera, voice, screen, app category, git, connector, tool, action, soul, private-thought, salience, want, or lived-memory write.
- Separate from body-state: own cache, own schema, own fact key, own prompt block.

## Predicted effect
Flag off: byte-identical idle heartbeat prompt and no cache.
Flag on: after a cold-start beat, app-class changes surface as "active surface changed" in the private heartbeat. Quiet means attention-shadow alone was thin, not that Rohit's world failed to stir Maez. Real presence/voice remains the Jetson arc.

## Live witness after merge
1. Confirm flag off and no cache exists.
2. Run one hermetic/manual sensor check on the real machine:
   `.venv/bin/python -B -c "from core.body.desktop_presence_state import sample_desktop_presence; print(sample_desktop_presence({'MAEZ_DESKTOP_PERCEPTION':'1'}))"`
   Expect `sensor_state='available'` and a class-only `app_class` if the Wayland path is currently reachable.
3. Set `MAEZ_DESKTOP_ATTENTION_SHADOW=1`, restart daemon.
4. First eligible heartbeat: cold-start, empty `DESKTOP ATTENTION SHADOW`, cache created.
5. Change active surface, wait for next eligible heartbeat.
6. Witness prompt/receipt has "active surface changed" and never app name.
```

- [ ] **Step 4: Commit and STOP for covenant review**

```bash
git add docs/handoffs/2026-06-29-desktop-attention-shadow-v0-handoff.md
git commit -m "docs(handoff): record desktop attention shadow v0 build"
```

Stop. Do not merge/restart/enable the flag before covenant review.

---

## Self-Review

**Spec coverage:** Wayland sensor fix is Task 0. Dedicated cache/schema is Task 1. Dedicated prompt fact/block is Task 2. Daemon flag/wiring is Task 3. Absence-test and raw-class exclusion are Tasks 1, 2, and 4. Hermetic Wayland tests are Task 0; live machine check is handoff/witness only. No presence/camera/voice/screen/git/connectors enter any task.

**Placeholder scan:** No placeholder fields or deferred implementation holes. The only live-machine check is explicitly a witness, not a suite dependency.

**Type consistency:** The plan consistently uses `DesktopPresenceState`, `DesktopAttentionEntry`, `DesktopAttentionResult.entries`, `receipt_payload()`, `desktop_attention_shadow`, and `MAEZ_DESKTOP_ATTENTION_SHADOW`.

**Interpretation guard:** The handoff requires the conclusion rule: quiet means desktop attention-shadow alone is thin, not that owner-world signal failed.
