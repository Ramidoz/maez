# Desktop Perception Lens v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the governed screen eye a working no-prompt capture path on this GNOME Wayland body — behind a fail-SAFE preflight — and prove it (or honestly report blind) end-to-end on the real session.

**Architecture:** All changes are in `skills/screen_perception.py` (the eye) plus its tests; `core/memory/ambient.py` gains a Wayland active-window probe. The gate order in `observe()` is unchanged (`pause → enabled → preflight → probe → capture → vision → govern`); this slice hardens the **preflight** (fail-open → fail-safe) and the **capture** step (X11-only → session-aware, no-prompt). Two empirical probes (active-window route, capture route) decide whether v0 reaches **Full Lens v0** (sight) or **Safety-floor Lens v0** (honest blind). No package or extension is installed autonomously (spec §6).

**Tech Stack:** Python 3, `unittest` (NOT pytest — run `.venv/bin/python -B -m unittest`), `subprocess`/`gdbus` for D-Bus capture probes, existing `requests` vision call. Tests mock all subprocess/D-Bus/env so they are display-independent.

**Spec:** `docs/superpowers/specs/2026-06-06-desktop-perception-lens-v0-design.md`. **Lane:** Codex implements / Claude reviews. Apples-to-apples full `discover` in `/home/rohit/maez`.

**Honest-outcome note for the implementer:** Tasks 1–3, 6, 7 are deterministic and fully TDD-able. Tasks 4–5 are *empirical* — they add the no-prompt route IF the probe (Task 8) finds one on this GNOME 50.1 machine; if none exists, the correct deliverable is the fail-safe + the probes + an honest `unavailable`/`excluded`, and "extension/package needed" named as the next owner-authorized slice. **Do not install anything to force a Full outcome.**

---

### Task 1: Honest session/display detection

**Files:**
- Modify: `skills/screen_perception.py` (add `_session_type()` near the other helpers, ~after `_is_paused`)
- Test: `tests/test_screen_perception_lens.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py
import unittest
from unittest import mock
import skills.screen_perception as sp


class SessionTypeTests(unittest.TestCase):
    def _env(self, **kw):
        base = {"XDG_SESSION_TYPE": "", "XDG_CURRENT_DESKTOP": "",
                "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        base.update(kw)
        return base

    def test_x11(self):
        with mock.patch.dict(sp.os.environ, self._env(XDG_SESSION_TYPE="x11", DISPLAY=":0"), clear=True):
            self.assertEqual(sp._session_type(), "x11")

    def test_wayland_gnome(self):
        with mock.patch.dict(sp.os.environ, self._env(
                XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="ubuntu:GNOME",
                WAYLAND_DISPLAY="wayland-0"), clear=True):
            self.assertEqual(sp._session_type(), "wayland-gnome")

    def test_wayland_wlroots(self):
        with mock.patch.dict(sp.os.environ, self._env(
                XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="sway",
                WAYLAND_DISPLAY="wayland-1"), clear=True):
            self.assertEqual(sp._session_type(), "wayland-wlroots")

    def test_unknown(self):
        with mock.patch.dict(sp.os.environ, self._env(), clear=True):
            self.assertEqual(sp._session_type(), "unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.SessionTypeTests -v`
Expected: FAIL with `AttributeError: module 'skills.screen_perception' has no attribute '_session_type'`

- [ ] **Step 3: Write minimal implementation**

```python
# skills/screen_perception.py — add after _is_paused()
_GNOME_DESKTOPS = ("gnome", "ubuntu:gnome")
_WLROOTS_DESKTOPS = ("sway", "hyprland", "wlroots", "river", "wayfire")


def _session_type() -> str:
    """Honest display/session classification — drives lens selection.

    Returns one of: 'x11' | 'wayland-gnome' | 'wayland-wlroots' | 'unknown'.
    Never guesses: an unrecognized combination is reported 'unknown'.
    """
    stype = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").strip().lower()
    if stype == "x11" or (not stype and os.environ.get("DISPLAY")):
        return "x11"
    if stype == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        if any(d in desktop for d in _GNOME_DESKTOPS):
            return "wayland-gnome"
        if any(d in desktop for d in _WLROOTS_DESKTOPS):
            return "wayland-wlroots"
        return "unknown"
    return "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.SessionTypeTests -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "feat(body-ui): honest session/display detection for the screen lens"
```

---

### Task 2: Preflight fails SAFE (the safety floor — inverts today's fail-open)

**Files:**
- Modify: `skills/screen_perception.py:197-205` (`_is_excluded_active_window`)
- Test: `tests/test_screen_perception_lens.py`

**Context:** Today `_is_excluded_active_window()` returns `False` (proceed) when `active_window()` is falsy, and Wayland returns `None` — so a focused-but-unreadable window proceeds to capture. This task inverts that: an **undetermined** window is treated as excluded. This is independently valuable: merged alone, it makes the eye safe-if-opened even before a lens exists.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class PreflightFailSafeTests(unittest.TestCase):
    def test_undetermined_window_is_excluded(self):
        # active_window()==None (Wayland today) → MUST be treated as excluded
        with mock.patch("core.memory.ambient.active_window", return_value=None):
            self.assertTrue(sp._is_excluded_active_window())

    def test_known_safe_window_not_excluded(self):
        with mock.patch("core.memory.ambient.active_window",
                        return_value={"class": "Gnome-terminal", "title": "bash"}):
            self.assertFalse(sp._is_excluded_active_window())

    def test_known_sensitive_window_excluded(self):
        with mock.patch("core.memory.ambient.active_window",
                        return_value={"class": "Bitwarden", "title": "Vault"}):
            self.assertTrue(sp._is_excluded_active_window())

    def test_observe_excludes_before_capture_when_window_unreadable(self):
        # Full gate: enabled + unreadable window → excluded, capture NEVER invoked
        with mock.patch.object(sp, "_is_enabled", return_value=True), \
             mock.patch.object(sp, "_is_paused", return_value=False), \
             mock.patch("core.memory.ambient.active_window", return_value=None), \
             mock.patch.object(sp, "_capture_screenshot") as cap, \
             mock.patch.object(sp, "_vision_endpoint_probe") as probe:
            obs = sp.observe()
        self.assertEqual(obs.state, "excluded")
        cap.assert_not_called()
        probe.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.PreflightFailSafeTests -v`
Expected: FAIL — `test_undetermined_window_is_excluded` and the observe test fail (current code returns False / proceeds).

- [ ] **Step 3: Write minimal implementation**

```python
# skills/screen_perception.py — replace _is_excluded_active_window body
def _is_excluded_active_window() -> bool:
    """Return True when the active window is sensitive OR cannot be determined.

    FAIL-SAFE (Lens v0): an undetermined active window (active_window()==None —
    the GNOME Wayland reality until a no-prompt active-window route exists) is
    treated as EXCLUDED. The never-looked guarantee must hold even when the
    window is unknown; we never capture into uncertainty.
    """
    from core.memory.ambient import active_window

    win = active_window()
    if not win:
        return True  # undetermined → excluded (was: return False — fail-open)
    haystack = f"{win.get('class', '')} {win.get('title', '')}".lower()
    return any(term in haystack for term in _exclusion_terms())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.PreflightFailSafeTests -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Guard the existing v1a suite did not silently flip meaning**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a tests.test_screen_perception_gate -v`
Expected: PASS. If `test_non_excluded_app_proceeds_to_probe` (v1a) mocks `active_window` to return a real dict it still passes; if any v1a test relied on `None→proceed`, that is the old fail-open and the test must be updated to the new safe direction (document the change in the commit — this is a deliberate, owner-approved inversion, not green-by-weakening).

- [ ] **Step 6: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "fix(body-ui): screen preflight fails SAFE — undetermined window is excluded

## Predicted effect
With the eye enabled on a session where the active window cannot be read
(GNOME Wayland today), observe() now returns state=excluded BEFORE capture
instead of proceeding. Falsifiable: enabled + active_window()==None yields
excluded with _capture_screenshot never invoked. Closes the fail-open hole
that would let a working lens capture unidentifiable sensitive windows."
```

---

### Task 3: Session-aware capture-method selection framework (no-prompt-only)

**Files:**
- Modify: `skills/screen_perception.py` (`_capture_screenshot` — make the method list session-driven; add a selection helper)
- Test: `tests/test_screen_perception_lens.py`

**Context:** Today `_capture_screenshot` hard-codes `[scrot, gnome-screenshot, import]` (all X11). This task makes the candidate list depend on `_session_type()` and adds the *framework* for no-prompt Wayland methods (filled in Task 5). The selection rule: try candidates in order, first that returns an image wins; **a method that prompts is never a candidate**; none → `None` (→ `state="error"`/`unavailable`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class CaptureSelectionTests(unittest.TestCase):
    def test_x11_uses_x11_methods(self):
        with mock.patch.object(sp, "_session_type", return_value="x11"):
            names = [m["name"] for m in sp._capture_candidates()]
        self.assertIn("scrot", names)
        self.assertNotIn("gnome-shell-dbus", names)

    def test_gnome_wayland_prefers_noprompt_dbus_first(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"):
            names = [m["name"] for m in sp._capture_candidates()]
        # GNOME Shell D-Bus (no-prompt if available) ranks before the portal
        self.assertEqual(names[0], "gnome-shell-dbus")
        self.assertIn("portal", names)
        self.assertNotIn("scrot", names)  # X11 tool not offered on Wayland

    def test_no_candidate_succeeds_returns_none(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"), \
             mock.patch.object(sp, "_capture_candidates",
                               return_value=[{"name": "x", "fn": lambda tmp: False}]):
            self.assertIsNone(sp._capture_screenshot())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.CaptureSelectionTests -v`
Expected: FAIL — `_capture_candidates` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/screen_perception.py
# Replace the hard-coded `methods` list in _capture_screenshot with a call to
# _capture_candidates(), and refactor each candidate into a fn(tmp)->bool that
# writes the screenshot to `tmp` and returns success.

def _run_capture_cmd(cmd, tmp) -> bool:
    """Run a subprocess capture command; True iff it wrote a non-empty file."""
    try:
        result = subprocess.run(cmd, env=DISPLAY_ENV, capture_output=True,
                                timeout=SCREENSHOT_TIMEOUT)
        return result.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    except Exception as e:
        logger.debug("capture cmd %s failed: %s", cmd[0], e)
        return False


def _capture_candidates() -> list:
    """Ordered, no-prompt-only capture methods for the current session.

    Each item: {"name": str, "fn": Callable[[str], bool]}. fn writes a PNG to
    the given temp path and returns success. NEVER include a method that shows
    a per-capture permission prompt (spec §6).
    """
    stype = _session_type()
    if stype == "wayland-gnome":
        # gnome-shell-dbus = no-prompt if reachable (Task 5); portal LAST and
        # only used if proven no-prompt on this backend (Task 5/8).
        return [
            {"name": "gnome-shell-dbus", "fn": _capture_gnome_shell_dbus},
            {"name": "portal", "fn": _capture_portal_noprompt},
        ]
    if stype == "wayland-wlroots":
        return [{"name": "grim", "fn": lambda tmp: _run_capture_cmd(["grim", tmp], tmp)}]
    # x11 / unknown → legacy X11 tools
    return [
        {"name": "scrot", "fn": lambda tmp: _run_capture_cmd(["scrot", "-z", tmp], tmp)},
        {"name": "gnome-screenshot", "fn": lambda tmp: _run_capture_cmd(["gnome-screenshot", "-f", tmp], tmp)},
        {"name": "import", "fn": lambda tmp: _run_capture_cmd(["import", "-window", "root", tmp], tmp)},
    ]
```

Then rewrite `_capture_screenshot()` to: create `tmp`, iterate `_capture_candidates()`, call each `fn(tmp)`, on first `True` downscale+base64 (existing PIL block) and return; `finally` unlink `tmp`; return `None` if none succeed. (Task 5 implements `_capture_gnome_shell_dbus` / `_capture_portal_noprompt`; for this task they may be temporary stubs returning `False`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.CaptureSelectionTests -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "feat(body-ui): session-aware no-prompt capture-method selection framework"
```

---

### Task 4: GNOME Wayland active-window probe (no-prompt routes only; else None)

**Files:**
- Modify: `core/memory/ambient.py` (`active_window` — add a Wayland branch that tries existing no-prompt routes)
- Test: `tests/test_ambient_active_window_wayland.py` (new)

**Context (empirical):** Stock GNOME has no documented no-prompt active-window route (`Shell.Eval` is locked). This task adds a probe that tries *existing* no-prompt D-Bus routes (e.g. a Window-Calls-style extension interface IF already present on the bus) and returns `None` if none exist. It must **not** install an extension (spec §6.2). When it returns `None`, the Task-2 fail-safe holds (→ Safety-floor outcome).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ambient_active_window_wayland.py
import unittest
from unittest import mock
import core.memory.ambient as ambient


class WaylandActiveWindowTests(unittest.TestCase):
    def test_wayland_no_route_returns_none(self):
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=None):
            self.assertIsNone(ambient.active_window())

    def test_wayland_route_present_returns_window(self):
        win = {"class": "firefox", "title": "x"}
        with mock.patch.object(ambient, "_session_is_wayland", return_value=True), \
             mock.patch.object(ambient, "_wayland_active_window", return_value=win):
            self.assertEqual(ambient.active_window(), win)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_ambient_active_window_wayland -v`
Expected: FAIL — `_session_is_wayland` / `_wayland_active_window` do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# core/memory/ambient.py
def _session_is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland" \
        or bool(os.environ.get("WAYLAND_DISPLAY"))


def _wayland_active_window(timeout: float = 1.0) -> dict | None:
    """Try EXISTING no-prompt active-window routes on Wayland. None if absent.

    Does NOT install or enable anything (spec §6.2). Probes the session bus for
    an already-present focused-window interface (Window-Calls-style); returns
    {"class","title"} if found, else None → caller fail-safe excludes.
    """
    # Probe an already-installed extension interface, no-prompt. If gdbus call
    # fails / iface absent / returns nothing usable → None.
    try:
        import json, shutil
        if not shutil.which("gdbus"):
            return None
        out = subprocess.check_output(
            ["gdbus", "call", "--session",
             "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Extensions/Windows",
             "--method", "org.gnome.Shell.Extensions.Windows.List"],
            timeout=timeout, text=True, stderr=subprocess.DEVNULL,
        )
        # Parse only if the extension is actually present; else this raises.
        # (Full parsing wired in implementation; absent route → None.)
        return _parse_window_calls_focused(out)
    except Exception:
        return None


def _parse_window_calls_focused(raw: str) -> dict | None:
    # Returns the focused window's {"class","title"} or None. Implemented to
    # the real interface shape ONLY if Task 8 finds it present; else stays a
    # safe None-returning stub.
    return None
```

Then add at the top of `active_window()`:
```python
    if _session_is_wayland():
        return _wayland_active_window(timeout)
    if not shutil.which("xdotool"):
        return None
    # ... existing X11 path unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_ambient_active_window_wayland -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/memory/ambient.py tests/test_ambient_active_window_wayland.py
git commit -m "feat(body): Wayland active-window probe — no-prompt routes only, else None"
```

---

### Task 5: GNOME Shell / portal capture implementation (no-prompt, temp-only)

**Files:**
- Modify: `skills/screen_perception.py` (implement `_capture_gnome_shell_dbus`, `_capture_portal_noprompt`)
- Test: `tests/test_screen_perception_lens.py`

**Context (empirical):** Implement the GNOME Shell D-Bus screenshot (`org.gnome.Shell.Screenshot.Screenshot(flash, filename)` → writes `filename`) and a portal path used **only if proven no-prompt** by Task 8. Both write to the caller-provided temp path and return bool. Real reachability is empirical (the Shell iface may reject external callers on GNOME 50.1); the unit test asserts the *wiring* (success path writes the file; failure → False), not real capture.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class GnomeShellCaptureTests(unittest.TestCase):
    def test_dbus_success_writes_file(self):
        def fake_run(cmd, **kw):
            # simulate gdbus writing the screenshot to the requested path
            path = cmd[cmd.index("--method") + 2] if "--method" in cmd else None
            return mock.Mock(returncode=0, stdout="(true, '/tmp/x.png')")
        with mock.patch("subprocess.run", side_effect=fake_run), \
             mock.patch("os.path.exists", return_value=True), \
             mock.patch("os.path.getsize", return_value=123):
            self.assertTrue(sp._capture_gnome_shell_dbus("/tmp/x.png"))

    def test_dbus_rejected_returns_false(self):
        with mock.patch("subprocess.run",
                        side_effect=subprocess.CalledProcessError(1, "gdbus")):
            self.assertFalse(sp._capture_gnome_shell_dbus("/tmp/x.png"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.GnomeShellCaptureTests -v`
Expected: FAIL — functions not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/screen_perception.py
def _capture_gnome_shell_dbus(tmp: str) -> bool:
    """org.gnome.Shell.Screenshot.Screenshot — no-prompt if the caller is
    permitted (may be rejected on GNOME 41+; that's an honest False)."""
    try:
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Screenshot",
             "--method", "org.gnome.Shell.Screenshot.Screenshot",
             "false", "false", tmp],
            env=DISPLAY_ENV, capture_output=True, text=True,
            timeout=SCREENSHOT_TIMEOUT,
        )
        ok = result.returncode == 0 and "true" in (result.stdout or "").lower()
        return ok and os.path.exists(tmp) and os.path.getsize(tmp) > 0
    except Exception as e:
        logger.debug("gnome-shell dbus capture failed: %s", e)
        return False


def _capture_portal_noprompt(tmp: str) -> bool:
    """Portal Screenshot — used ONLY if Task 8 proves this backend is no-prompt.
    Until proven, returns False so it is never the route that prompts."""
    if os.environ.get("MAEZ_SCREEN_PORTAL_NOPROMPT", "").strip() != "1":
        return False
    # Real portal Request/Response wiring added ONLY after the no-prompt proof.
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.GnomeShellCaptureTests -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "feat(body-ui): GNOME Shell D-Bus screenshot capture (no-prompt; portal gated off until proven)"
```

---

### Task 6: Temp-only + cleanup invariant for the new capture paths

**Files:**
- Test: `tests/test_screen_perception_lens.py`

**Context:** v1a's no-durable-storage invariant must survive the new lens — capture writes only a temp file that is always removed, and no screenshot bytes persist. The existing `finally: os.unlink(tmp)` covers it; this task pins it for the new code path.

- [ ] **Step 1: Write the failing test (then make it pass — the cleanup already exists, so this is a regression pin)**

```python
# tests/test_screen_perception_lens.py — append
class TempCleanupTests(unittest.TestCase):
    def test_capture_removes_temp_on_success_and_failure(self):
        created = {}
        real_mktemp = sp.tempfile.mktemp
        def tracking_mktemp(*a, **k):
            p = real_mktemp(*a, **k); created["path"] = p; return p
        # success path: candidate writes file, returns True
        with mock.patch.object(sp.tempfile, "mktemp", side_effect=tracking_mktemp), \
             mock.patch.object(sp, "_capture_candidates", return_value=[
                 {"name": "fake", "fn": lambda tmp: (open(tmp, "wb").write(b"\x89PNG"), True)[1]}]), \
             mock.patch("skills.screen_perception.Image", create=True):
            try:
                sp._capture_screenshot()
            except Exception:
                pass
        self.assertFalse(sp.os.path.exists(created["path"]), "temp not cleaned up")
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.TempCleanupTests -v`
Expected: PASS if the `finally` cleanup is intact after the Task-3 refactor. If FAIL, the refactor dropped the `finally: unlink` — restore it (the cleanup must wrap the whole candidate loop, not a single method).

- [ ] **Step 3: Commit (only if a fix was needed)**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "test(body-ui): pin temp-only + cleanup invariant across the new lens path"
```

---

### Task 7: Rails-unchanged regression (the 18 governance tests stay green)

**Files:** none (verification task)

- [ ] **Step 1: Run the full v1a + gate + new lens suites**

Run:
```bash
.venv/bin/python -B -m unittest \
  tests.test_screen_perception_v1a tests.test_screen_perception_gate \
  tests.test_screen_perception_lens tests.test_ambient_active_window_wayland -v
```
Expected: ALL PASS. The 18 v1a+gate tests prove third-party minimization, egress tagging, honest-blind states, default-off are byte-unchanged. Any v1a test that changed must be a documented, deliberate consequence of the Task-2 fail-safe inversion (never green-by-weakening).

- [ ] **Step 2: Full discover (apples-to-apples)**

Run: `.venv/bin/python -B -m unittest discover -s tests -v 2>&1 | tail -30`
Expected: the suite floor matches main (compare branch-only failures vs base; asset-gap failures are not regressions per the worktree-floor-confound discipline — run in `/home/rohit/maez`).

---

### Task 8: Empirical probe + end-to-end witness (decides Full vs Safety-floor)

**Files:**
- Create: `scripts/lens_probe.py` (a content-free diagnostic, run on the real session)

**Context:** This is where v0's outcome is decided. The probe must run **on the real GNOME Wayland session via the daemon's context** (a detached subprocess lacks session capture authority — proven this morning). It reports, content-free, which routes actually work no-prompt.

- [ ] **Step 1: Write the probe (content-free — reports route viability, captures to temp, never prints/persists screen content)**

```python
# scripts/lens_probe.py
"""Content-free Lens v0 probe: which capture + active-window routes work
no-prompt on THIS session. Prints route names + booleans + image byte-sizes
ONLY — never screen content. Run via the daemon's session, not a detached shell."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skills.screen_perception as sp
from core.memory import ambient

print("session_type:", sp._session_type())
print("active_window (Wayland route present?):", ambient.active_window() is not None)
for cand in sp._capture_candidates():
    tmp = tempfile.mktemp(suffix=".png")
    try:
        ok = cand["fn"](tmp)
        size = os.path.getsize(tmp) if (ok and os.path.exists(tmp)) else 0
        print(f"  capture[{cand['name']}]: ok={ok} bytes={size}")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
```

- [ ] **Step 2: Owner runs the probe on the live session** (Codex/Claude cannot — the daemon holds session authority)

Run (owner, in the graphical session): `cd /home/rohit/maez && .venv/bin/python -B scripts/lens_probe.py`
Interpret:
- **Any `capture[...] ok=True bytes>0` with no dialog** AND `active_window present=True` → **Full Lens v0** reachable. Wire the working route as the default, then run the Full witness (Step 3).
- **No no-prompt capture** OR `active_window present=False` → **Safety-floor Lens v0**. Stop. Record the result and name the next owner-authorized slice ("GNOME extension for active-window" and/or "portal permission grant" and/or "install <named> capture tool"). Do NOT install anything.

- [ ] **Step 3: Full witness (ONLY if Step 2 reached Full)** — owner enables `MAEZ_SCREEN_PERCEPTION=1` + restart; Claude reads content-free:
  1. ordinary window → `state="ok"`, real summary, `egress_origin_class="owner_screen_context"`
  2. focused sensitive app → `excluded`, capture never invoked (preflight real, not just fail-safe)
  3. no durable screen row after the `ok` blink; temp removed
  4. no per-capture dialog appeared
  Then owner reverts the flag (default-off) unless choosing to keep the eye open.

- [ ] **Step 4: Commit the probe + record the outcome**

```bash
git add scripts/lens_probe.py
git commit -m "feat(body-ui): Lens v0 empirical probe — decides Full vs Safety-floor on the real session

## Predicted effect
Run on the live GNOME Wayland session, lens_probe.py reports (content-free)
which capture route works no-prompt and whether an active-window route exists.
Outcome is one of: Full Lens v0 (wire the route + Full witness) or
Safety-floor Lens v0 (honest blind; name the next owner-authorized slice).
Falsifiable: the probe prints ok=True bytes>0 for a working route, else the
eye honestly reports unavailable/excluded and nothing is installed."
```

---

### Task 9: Finish — canon + branch completion

- [ ] **Step 1:** Update `project_cognition_live_state.md` (canon) with the v0 outcome (Full or Safety-floor), the working route (if Full), and v1b's gating state.
- [ ] **Step 2:** Use **superpowers:finishing-a-development-branch** to complete (merge to main locally is owner-delegable per the arc covenant; the **enable+restart activation breath stays the owner's**). NO push (main is local-only).
- [ ] **Step 3:** If Safety-floor, confirm the named next slice is recorded and v1b stays blocked.
