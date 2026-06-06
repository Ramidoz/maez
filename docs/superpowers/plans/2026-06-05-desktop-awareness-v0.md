# Desktop Awareness v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A content-free, honestly-available desktop body sense — Maez perceives **which app class** the owner is in (never the window title), reports **blind** when it genuinely can't see, surfaced on `/health.body` + a dashboard tile, default-disabled and dormant.

**Architecture:** A pure sensor module `core/body/desktop_presence_state.py` (mirrors `core/body/camera_presence_state.py`) carries the entire honesty spine (content-free app-class-only, honest-availability, blind-beats-stale) and is fully unit-testable without the daemon. The daemon threads it exactly like camera-presence (`_desktop_presence_health` → `/health.body.desktop`); the dashboard adds a "Desktop" tile mirroring the "eyes" tile.

**Tech Stack:** Python 3.14, `unittest` (NOT pytest), `xdotool`/`xprop` (via the existing `ambient.active_window`), the body-capability probes.

**Spec:** `docs/superpowers/specs/2026-06-05-desktop-awareness-v0-design.md`

**Lands dormant** (default `MAEZ_DESKTOP_PERCEPTION=0` → no live change). The daemon-wiring commit (Task 2) carries the `## Predicted effect` (the when-enabled behavior). Test runner `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `core/body/desktop_presence_state.py` | The pure sensor: `DesktopPresenceState` + `sample_desktop_presence` + `_desktop_availability`. Content-free, honest, blind-beats-stale. The spine. |
| `tests/test_desktop_presence_state.py` | The spine tests (pure): default-disabled, honest-availability matrix, content-free/no-title, blind-beats-stale. |
| `daemon/maez_daemon.py` | `self._desktop_presence_state` + `_desktop_presence_health()` + the `desktop` key in `/health.body` (mirror camera-presence at 2477/2951/3036). |
| `tests/test_desktop_presence_health.py` | Daemon-level: `/health.body.desktop` present; default-disabled. |
| `ui/dashboard_local.html` | A "Desktop" tile in `ORGANS` (mirror the "eyes" tile at line 470). |

**Reused:** `core/memory/ambient.py` `active_window()`; `core/infra/body_capabilities.py` (`has_binary`/`env_present`); the camera-presence + eyes-tile patterns.

---

## Task 1: The pure sensor module (the honesty spine)

**Files:**
- Create: `core/body/desktop_presence_state.py`
- Test: `tests/test_desktop_presence_state.py`

- [ ] **Step 1: Write the sensor module**

```python
# core/body/desktop_presence_state.py
"""Desktop Awareness v0 -- content-free desktop body sensor.

Mirrors camera_presence_state.py: holds only content-free state -- the active
APP CLASS (which app), never the window TITLE (what's in it), never frames,
never durable history. "Which room of the house, not what paper on the desk."
Perceive honestly or report blind -- never fabricate / infer / show-stale-as-current.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

PERCEPTION_ENV = "MAEZ_DESKTOP_PERCEPTION"
SCHEMA_VERSION = "desktop_presence.v1"

VALID_SENSOR_STATES = frozenset({"disabled", "available", "unavailable"})
VALID_REASONS = frozenset(
    {"", "tools_missing", "wayland", "session_unreachable", "no_active_window"}
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DesktopPresenceState:
    sensor_state: str = "disabled"   # disabled | available | unavailable
    app_class: str | None = None     # content-free; set ONLY when available
    reason: str = ""                 # honest blind reason when unavailable
    sampled_at: datetime | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.sensor_state not in VALID_SENSOR_STATES:
            raise ValueError(f"invalid sensor_state: {self.sensor_state!r}")
        if self.reason not in VALID_REASONS:
            raise ValueError(f"invalid reason: {self.reason!r}")
        # Honesty invariant: an app class may exist ONLY when available.
        # Makes "blind carries a (stale/fabricated) app" un-constructable.
        if self.app_class is not None and self.sensor_state != "available":
            raise ValueError("app_class may only be set when sensor_state == 'available'")
        if self.sampled_at is not None and self.sampled_at.tzinfo is None:
            raise ValueError("sampled_at must include timezone")

    def to_health(self, *, now: datetime | None = None) -> dict[str, object]:
        current = (now or _utc_now()).astimezone(timezone.utc)
        age = None
        if self.sampled_at is not None:
            age = int((current - self.sampled_at.astimezone(timezone.utc)).total_seconds())
        return {
            "schema_version": self.schema_version,
            "sensor_state": self.sensor_state,
            "app_class": self.app_class,
            "reason": self.reason,
            "age_seconds": age,
        }


def _desktop_availability() -> tuple[str, str]:
    """Honest availability -> (sensor_state, reason). Mirrors
    body_capabilities.desktop_session_reachable, but returns the reason."""
    if not shutil.which("xdotool"):
        return "unavailable", "tools_missing"
    if not (os.environ.get("DISPLAY") or ""):
        return "unavailable", "wayland"  # no DISPLAY -> likely Wayland-only
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            capture_output=True, timeout=1.5, check=False,
        )
        if result.returncode != 0:
            return "unavailable", "session_unreachable"
    except (subprocess.TimeoutExpired, OSError):
        return "unavailable", "session_unreachable"
    return "available", ""


def sample_desktop_presence(
    env: Mapping[str, str],
    *,
    now: datetime | None = None,
    availability_fn: Callable[[], tuple[str, str]] = _desktop_availability,
    active_window_fn: Callable[[], dict | None] | None = None,
) -> DesktopPresenceState:
    """Sample the desktop sense, content-free. Returns a FRESH state each call
    -- blind beats stale: an unavailable sample never carries the prior app."""
    mode = (env.get(PERCEPTION_ENV) or "0").strip()
    if mode in {"", "0"}:
        return DesktopPresenceState(sensor_state="disabled")

    sampled = (now or _utc_now()).astimezone(timezone.utc)
    state, reason = availability_fn()
    if state == "unavailable":
        return DesktopPresenceState(
            sensor_state="unavailable", reason=reason, sampled_at=sampled
        )

    win_fn = active_window_fn
    if win_fn is None:
        from core.memory.ambient import active_window as win_fn
    window = win_fn()
    # CONTENT-FREE: only the class is read; the title is deliberately discarded.
    app_class = (window or {}).get("class") if window else None
    if not app_class:
        return DesktopPresenceState(
            sensor_state="unavailable", reason="no_active_window", sampled_at=sampled
        )
    return DesktopPresenceState(
        sensor_state="available", app_class=str(app_class), sampled_at=sampled
    )
```

- [ ] **Step 2: Write the failing spine tests**

```python
# tests/test_desktop_presence_state.py
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.body.desktop_presence_state import (
    DesktopPresenceState,
    sample_desktop_presence,
)

_NOW = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)


class DesktopPresenceStateTests(unittest.TestCase):
    def test_default_disabled_does_not_sample(self):
        called = {"window": False, "avail": False}

        def _avail():
            called["avail"] = True
            return ("available", "")

        def _win():
            called["window"] = True
            return {"class": "firefox", "title": "secret"}

        state = sample_desktop_presence(
            {}, now=_NOW, availability_fn=_avail, active_window_fn=_win
        )
        self.assertEqual(state.sensor_state, "disabled")
        self.assertIsNone(state.app_class)
        self.assertFalse(called["avail"], "disabled must not probe availability")
        self.assertFalse(called["window"], "disabled must not read the window")

    def test_available_is_app_class_only_no_title(self):
        # HEADLINE content-free test: the title must never appear anywhere.
        state = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: {
                "class": "firefox",
                "title": "Re: confidential salary discussion - Gmail",
            },
        )
        self.assertEqual(state.sensor_state, "available")
        self.assertEqual(state.app_class, "firefox")
        health = state.to_health(now=_NOW)
        blob = repr(state) + repr(health)
        self.assertNotIn("confidential", blob)
        self.assertNotIn("Gmail", blob)
        self.assertNotIn("salary", blob)

    def test_honest_availability_matrix_never_fabricates(self):
        for reason in ("tools_missing", "wayland", "session_unreachable"):
            state = sample_desktop_presence(
                {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
                availability_fn=lambda r=reason: ("unavailable", r),
                active_window_fn=lambda: {"class": "firefox", "title": "x"},
            )
            self.assertEqual(state.sensor_state, "unavailable")
            self.assertEqual(state.reason, reason)
            self.assertIsNone(state.app_class, "blind must never carry an app class")

    def test_reachable_but_no_active_window_is_blind_not_fabricated(self):
        state = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: None,
        )
        self.assertEqual(state.sensor_state, "unavailable")
        self.assertEqual(state.reason, "no_active_window")
        self.assertIsNone(state.app_class)

    def test_blind_beats_stale(self):
        # available -> then unavailable: the new sample must NOT carry the old app.
        avail = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("available", ""),
            active_window_fn=lambda: {"class": "code", "title": "x"},
        )
        self.assertEqual(avail.app_class, "code")
        blind = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"}, now=_NOW,
            availability_fn=lambda: ("unavailable", "session_unreachable"),
            active_window_fn=lambda: {"class": "code", "title": "x"},
        )
        self.assertEqual(blind.sensor_state, "unavailable")
        self.assertIsNone(blind.app_class)

    def test_invariant_app_class_only_when_available(self):
        # The dataclass itself refuses "blind with an app" -- un-constructable.
        with self.assertRaises(ValueError):
            DesktopPresenceState(sensor_state="unavailable", app_class="firefox")
```

- [ ] **Step 3: Run — verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_desktop_presence_state -v`
Expected: PASS — especially `test_available_is_app_class_only_no_title` (the content-free headline) and `test_honest_availability_matrix_never_fabricates` + `test_blind_beats_stale` (the Firefox-tabs scar).

- [ ] **Step 4: Commit**

```bash
git add core/body/desktop_presence_state.py tests/test_desktop_presence_state.py
git commit -m "feat(body): desktop presence sensor — content-free, honest, blind-beats-stale

App-class-only (title discarded); honest-availability matrix (tools_missing/
wayland/session_unreachable/no_active_window -> blind, never an app); the
dataclass invariant makes 'blind carries an app' un-constructable; default-
disabled does not sample. Pure module, no daemon. Lands dormant.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Wire into the daemon (`/health.body.desktop`)

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_desktop_presence_health.py`

Mirror the camera-presence integration. Anchors: the import block (~line 95), `__init__` (~2477), the body-dict builder (~2951, where `"eyes"` is built from `camera_presence`), and `_camera_presence_health` (~3036).

- [ ] **Step 1: Add the import + the health method + the body field**

Near the camera-presence import (daemon/maez_daemon.py ~95):

```python
from core.body.desktop_presence_state import (
    DesktopPresenceState,
    sample_desktop_presence,
)
```

In `__init__`, beside `self._camera_presence_state = resolve_camera_presence_state(os.environ)` (~2477):

```python
        self._desktop_presence_state = sample_desktop_presence(os.environ)
```

Add a health method beside `_camera_presence_health` (~3036):

```python
    def _desktop_presence_health(self) -> dict:
        try:
            self._desktop_presence_state = sample_desktop_presence(os.environ)
        except Exception:
            self._desktop_presence_state = DesktopPresenceState(
                sensor_state="unavailable", reason="session_unreachable"
            )
        return self._desktop_presence_state.to_health()
```

In the body-dict builder (the method around line 2951 that takes `camera_presence: dict` and builds `"eyes": {...}` at 2967), add a parameter `desktop_presence: dict` and a `"desktop"` key beside `"eyes"`:

```python
            "desktop": {
                "sensor_state": desktop_presence.get("sensor_state", "unknown"),
                "app_class": desktop_presence.get("app_class"),
                "reason": desktop_presence.get("reason", ""),
                "age_seconds": desktop_presence.get("age_seconds"),
                "schema_version": desktop_presence.get("schema_version", "desktop_presence.v1"),
            },
```

Find the single caller of that body-builder (grep: `git grep -n "camera_presence=" daemon/maez_daemon.py` or the call passing the eyes dict) and thread the desktop health in beside the camera one:

```python
            desktop_presence=self._desktop_presence_health(),
```

- [ ] **Step 2: Write the failing daemon-level test**

```python
# tests/test_desktop_presence_health.py
from __future__ import annotations

import unittest
from unittest import mock

from core.body.desktop_presence_state import sample_desktop_presence


class DesktopPresenceHealthTests(unittest.TestCase):
    def test_default_disabled_health_shape(self):
        # The sensor's health, as the daemon will surface it, is content-free
        # and disabled by default.
        health = sample_desktop_presence({}).to_health()
        self.assertEqual(health["sensor_state"], "disabled")
        self.assertIsNone(health["app_class"])
        self.assertEqual(set(health.keys()),
                         {"schema_version", "sensor_state", "app_class", "reason", "age_seconds"})

    def test_enabled_unavailable_is_content_free(self):
        health = sample_desktop_presence(
            {"MAEZ_DESKTOP_PERCEPTION": "1"},
            availability_fn=lambda: ("unavailable", "wayland"),
        ).to_health()
        self.assertEqual(health["sensor_state"], "unavailable")
        self.assertEqual(health["reason"], "wayland")
        self.assertIsNone(health["app_class"])
```

(Note: a full daemon-boot `/health.body` test is heavy; the sensor-shape test above is the content-free contract the daemon surfaces. If a `/health` integration test exists for camera-presence, mirror it; otherwise this contract test is sufficient — the daemon wiring is a thin pass-through of `to_health()`.)

- [ ] **Step 3: Run — verify pass + py_compile the daemon**

Run: `.venv/bin/python -B -m unittest tests.test_desktop_presence_health -v` then `.venv/bin/python -B -m py_compile daemon/maez_daemon.py`
Expected: PASS; daemon compiles. If the body-builder signature/caller doesn't line up, reconcile against the camera-presence threading (the exact same shape).

- [ ] **Step 4: Commit (carries `## Predicted effect`)**

```bash
git add daemon/maez_daemon.py tests/test_desktop_presence_health.py
git commit -m "feat(body): surface desktop sense on /health.body (default-disabled)

Threads the desktop presence sensor into the daemon like camera-presence:
_desktop_presence_health() -> /health.body.desktop. Default-disabled =
dormant; no cognition-injection, no storage.

## Predicted effect
Default MAEZ_DESKTOP_PERCEPTION=0 -> no live change (dormant). WHEN ENABLED
(=1): the daemon samples the active app CLASS (content-free, never the title)
on each /health.body read and exposes {sensor_state, app_class, reason,
age_seconds}; on Wayland/missing-tools/unreachable-session it reports a blind
reason, never a fabricated app. No prompt/cognition change, no memory written.
Falsifiable: enabled on this X11 box, /health.body.desktop.app_class is the
real active app's class and never its title; forced-unavailable -> blind.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: The dashboard "Desktop" tile

**Files:**
- Modify: `ui/dashboard_local.html`

- [ ] **Step 1: Add a "Desktop" tile to the `ORGANS` array (mirror the "eyes" tile at line 470)**

In the `ORGANS` array, add an entry mirroring the eyes-tile renderer shape (match the exact return shape the eyes fn uses — inspect line 470-479):

```javascript
  ['desktop','Desktop','focus', e=>{
    if(!e || e.sensor_state==='disabled') return {state:'off', detail:'disabled'};
    if(e.sensor_state==='unavailable') return {state:'warn', detail:'blind · '+(e.reason||'unknown')};
    const age = (e.age_seconds!=null) ? (' · '+e.age_seconds+'s ago') : '';
    return {state:'ok', detail:(e.app_class||'?')+age};
  }],
```

(Adjust the returned object keys to match the eyes tile's renderer contract exactly — read lines 470-479 first; the point is: disabled→off, unavailable→blind+reason, available→app_class+age. Never render a title — there is none in the data.)

- [ ] **Step 2: Verify the dashboard parses (no syntax error)**

Run: `node --check ui/dashboard_local.html 2>/dev/null || echo "node check skipped (html); visually confirm the ORGANS entry is well-formed JS"`
Expected: no JS syntax error in the added block (it's inline JS; a visual confirm + matching the eyes-tile shape is the check).

- [ ] **Step 3: Commit**

```bash
git add ui/dashboard_local.html
git commit -m "feat(body-ui): Desktop tile on the organ dashboard (mirrors eyes)

Content-free Desktop tile: app class + age when available, honest 'blind ·
<reason>' when unavailable, 'disabled' when off. Mirrors the eyes tile.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Full-suite green + apples-to-apples

**Files:** none

- [ ] **Step 1: Run the new modules**

Run: `.venv/bin/python -B -m unittest tests.test_desktop_presence_state tests.test_desktop_presence_health -v`
Expected: ALL PASS.

- [ ] **Step 2: Full discover**

Run: `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -6`
Expected: zero new failures attributable to this slice; run in `/home/rohit/maez`. (Live-judge flaky floor wobbles ±1-2.)

- [ ] **Step 3: Confirm dormant + read-only**

`git grep -n "MAEZ_DESKTOP_PERCEPTION" core/ daemon/` shows the env gate; confirm default (unset) → `disabled`. Confirm no action/write-side code was added (the slice only reads). Confirm `git status --porcelain memory/db` is empty.

---

## Self-Review (against the spec)

**Spec coverage:**
- §2 default-disabled → Task 1 `test_default_disabled_does_not_sample`. ✓
- §2 app-class-only, no title (even locally) → Task 1 `test_available_is_app_class_only_no_title` (headline). ✓
- §2 honest blind reason; never infer/fabricate → Task 1 honest-availability matrix + `no_active_window` + the dataclass invariant. ✓
- §2 never store / never inject → pure sensor (no persistence, no prompt path); Task 4 Step 3 confirms. ✓
- §2 blind-beats-stale → Task 1 `test_blind_beats_stale` (fresh state each sample). ✓
- §4 mirror camera-presence + the `/health.body.desktop` field → Task 2. ✓
- §4 dashboard tile mirror eyes → Task 3. ✓
- §5 the four states → Task 1 tests (disabled / available / unavailable+reason / no_active_window). ✓
- §8 dormant + `## Predicted effect` → Task 2 commit. ✓

**Placeholder scan:** none. Two bounded implementer-confirms (the daemon body-builder caller in Task 2; the eyes-tile renderer return shape in Task 3) are flagged with the exact grep/line to check — not placeholders.

**Type consistency:** `DesktopPresenceState(sensor_state, app_class, reason, sampled_at, schema_version)`, `sample_desktop_presence(env, *, now, availability_fn, active_window_fn)`, `_desktop_availability() -> (state, reason)`, `to_health(*, now) -> {schema_version, sensor_state, app_class, reason, age_seconds}`, `_desktop_presence_health()` — consistent across Tasks 1-2. The reason vocabulary (`tools_missing`/`wayland`/`session_unreachable`/`no_active_window`) matches between the sensor and the tests. ✓
