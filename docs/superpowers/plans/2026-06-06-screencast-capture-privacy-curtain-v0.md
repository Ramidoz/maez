# ScreenCast Capture + Privacy Curtain v0 (Full Lens — Slice A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Maez's eye a governed ScreenCast frame feed (grant-once / restore_token), sampled on demand, temp-only, with a privacy curtain that truly stops capture — proving the capture half of Full Lens without sight or v1b.

**Architecture:** A standalone `scripts/screencast_capture.py` runs on **system `python3`** (which has `gi`/`Gst`/`Gio`; the maez venv does not) and is shelled to by `skills/screen_perception.py` as a new `screencast` capture candidate. Imports of `gi` are **lazy** (inside live functions) so the venv can unit-test the token/curtain/output/path logic. The helper emits a **content-free JSON contract** on every exit path; the restore-token is a `0600` capability secret; the curtain (soft/hard) stops capture for real. `observe()` is byte-unchanged (still fail-safe-blind).

**Tech Stack:** Python 3, `unittest` (NOT pytest — `.venv/bin/python -B -m unittest`), system `python3` + `gi`/`Gst`/`pipewiresrc` for the live capture only, `xdg-desktop-portal` ScreenCast. The live portal/Gst path is **owner-witnessed** (needs the graphical session), not unit-tested.

**Spec:** `docs/superpowers/specs/2026-06-06-screencast-capture-privacy-curtain-v0-design.md`. **Lane:** Codex implements / Claude reviews. Apples-to-apples full `discover` in `/home/rohit/maez`.

**Boundary reminder (do not cross):** This slice proves the **capture half** only. `observe()` stays fail-safe-blind; the new path is witnessed via the **direct capture/probe path**, never claimed as `observe()` sight. No durable frame archive. No v1b. No install.

---

### Task 1: Helper module skeleton — content-free JSON contract + lazy imports

**Files:**
- Create: `scripts/screencast_capture.py`
- Test: `tests/test_screencast_capture.py` (new)

**Context:** The module must `import` under the maez venv (no `gi`). `gi`/`Gst`/`Gio` imports go **inside** the live functions only. This task lands the output contract + config paths + the arg dispatch shell.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screencast_capture.py
import json
import unittest
from unittest import mock
import scripts.screencast_capture as sc


class OutputContractTests(unittest.TestCase):
    def test_module_imports_without_gi(self):
        # The maez venv lacks gi; importing the module must not require it.
        import sys
        self.assertNotIn("gi", [m for m in sys.modules if m == "gi"] )  # not imported at module load

    def test_emit_shape(self):
        out = sc._result(status="ok", temp_path="/tmp/maez-screencast-x.png",
                         bytes_=123, duration_ms=42)
        self.assertEqual(set(out.keys()),
                         {"status", "temp_path", "bytes", "duration_ms", "error_class"})
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["bytes"], 123)
        self.assertEqual(out["error_class"], "")

    def test_emit_is_json_serializable_and_tokenless(self):
        out = sc._result(status="ok", temp_path="/tmp/maez-screencast-x.png",
                         bytes_=1, duration_ms=1)
        s = json.dumps(out)
        self.assertNotIn("token", s.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.OutputContractTests -v`
Expected: FAIL — `scripts.screencast_capture` / `_result` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screencast_capture.py
#!/usr/bin/env python3
"""Maez ScreenCast capture helper — runs on SYSTEM python3 (has gi/Gst/Gio).

Receives ONE frame from a governed ScreenCast stream (grant-once / restore_token),
writes it to a temp PNG, and prints a CONTENT-FREE JSON status line. Imports of
gi/Gst/Gio are LAZY (inside live functions) so the maez venv can unit-test the
token/curtain/output/path logic. Never prints screen content, tracebacks, or the
restore-token.
"""
import json
import os
import sys

TOKEN_PATH = os.path.expanduser("~/.config/maez/screencast_restore_token")
CURTAIN_PATH = os.path.expanduser("~/.config/maez/screen_perception.curtain")
TEMP_PREFIX = "maez-screencast-"


def _result(status, temp_path=None, bytes_=0, duration_ms=0, error_class=""):
    """The ONLY thing ever printed. Content-free contract."""
    return {
        "status": status,            # ok | needs_grant | curtain_drawn | capture_failed
        "temp_path": temp_path,
        "bytes": int(bytes_),
        "duration_ms": int(duration_ms),
        "error_class": error_class,  # portal|pipewire|gst|timeout|permission_denied (stage only)
    }


def _emit(result):
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.OutputContractTests -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/screencast_capture.py tests/test_screencast_capture.py
git commit -m "feat(body-ui): ScreenCast helper skeleton — content-free JSON contract, lazy imports"
```

---

### Task 2: Curtain check (soft) — refuse capture, no session

**Files:**
- Modify: `scripts/screencast_capture.py`
- Test: `tests/test_screencast_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screencast_capture.py — append
class CurtainTests(unittest.TestCase):
    def test_curtain_drawn_short_circuits(self):
        with mock.patch.object(sc.os.path, "exists",
                               lambda p: p == sc.CURTAIN_PATH):
            out = sc.capture()  # must NOT import gi / open a session
        self.assertEqual(out["status"], "curtain_drawn")
        self.assertIsNone(out["temp_path"])

    def test_no_gi_import_when_curtain_drawn(self):
        import sys
        sys.modules.pop("gi", None)
        with mock.patch.object(sc.os.path, "exists",
                               lambda p: p == sc.CURTAIN_PATH):
            sc.capture()
        self.assertNotIn("gi", sys.modules)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.CurtainTests -v`
Expected: FAIL — `capture` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screencast_capture.py — add
def _curtain_drawn():
    return os.path.exists(CURTAIN_PATH)


def capture():
    """Top-level capture entry. Curtain is checked FIRST, before any gi/session."""
    if _curtain_drawn():
        return _result(status="curtain_drawn")
    return _capture_live()  # Task 6 — lazy-imports gi inside


def _capture_live():
    # Placeholder until Task 6; keeps Task 2 honest (no gi at module level).
    return _result(status="capture_failed", error_class="gst")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.CurtainTests -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/screencast_capture.py tests/test_screencast_capture.py
git commit -m "feat(body-ui): soft-curtain short-circuit before any session/gi"
```

---

### Task 3: Restore-token storage (0600) + load

**Files:**
- Modify: `scripts/screencast_capture.py`
- Test: `tests/test_screencast_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screencast_capture.py — append
import tempfile, os as _os, stat
class TokenTests(unittest.TestCase):
    def test_save_token_is_0600(self):
        d = tempfile.mkdtemp()
        path = _os.path.join(d, "tok")
        with mock.patch.object(sc, "TOKEN_PATH", path):
            sc._save_token("SECRET-RESTORE-TOKEN")
            mode = stat.S_IMODE(_os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)

    def test_load_token_roundtrip_and_absent(self):
        d = tempfile.mkdtemp()
        path = _os.path.join(d, "tok")
        with mock.patch.object(sc, "TOKEN_PATH", path):
            self.assertIsNone(sc._load_token())   # absent → None
            sc._save_token("T")
            self.assertEqual(sc._load_token(), "T")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.TokenTests -v`
Expected: FAIL — `_save_token`/`_load_token` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screencast_capture.py — add
def _save_token(token: str) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    # 0600 from creation — open with restrictive mode, then write.
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode())
    finally:
        os.close(fd)
    os.chmod(TOKEN_PATH, 0o600)  # belt-and-suspenders if umask widened it


def _load_token():
    try:
        with open(TOKEN_PATH, "r") as f:
            t = f.read().strip()
        return t or None
    except FileNotFoundError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.TokenTests -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/screencast_capture.py tests/test_screencast_capture.py
git commit -m "feat(body-ui): restore-token 0600 capability-secret storage"
```

---

### Task 4: Hard revoke (`--revoke`) — delete token + draw curtain

**Files:**
- Modify: `scripts/screencast_capture.py`
- Test: `tests/test_screencast_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screencast_capture.py — append
class RevokeTests(unittest.TestCase):
    def test_revoke_deletes_token_and_draws_curtain(self):
        d = tempfile.mkdtemp()
        tok = _os.path.join(d, "tok"); cur = _os.path.join(d, "curtain")
        with mock.patch.object(sc, "TOKEN_PATH", tok), \
             mock.patch.object(sc, "CURTAIN_PATH", cur):
            sc._save_token("T")
            out = sc.revoke()
            self.assertFalse(_os.path.exists(tok))   # token gone
            self.assertTrue(_os.path.exists(cur))     # curtain drawn
        self.assertEqual(out["status"], "curtain_drawn")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.RevokeTests -v`
Expected: FAIL — `revoke` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screencast_capture.py — add
def revoke():
    """Hard revoke: withdraw the eye. Delete token, draw curtain."""
    try:
        os.unlink(TOKEN_PATH)
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(CURTAIN_PATH), exist_ok=True)
    open(CURTAIN_PATH, "a").close()  # draw the curtain
    return _result(status="curtain_drawn")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.RevokeTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/screencast_capture.py tests/test_screencast_capture.py
git commit -m "feat(body-ui): hard-revoke — delete token + draw curtain (withdraw the eye)"
```

---

### Task 5: Top-level exception → `capture_failed` + stage, no traceback leak

**Files:**
- Modify: `scripts/screencast_capture.py` (`main()` + a top-level guard)
- Test: `tests/test_screencast_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screencast_capture.py — append
class NoLeakTests(unittest.TestCase):
    def test_live_exception_maps_to_stage_no_traceback(self):
        secret = "RAW-PORTAL-HANDLE-9d2f"
        with mock.patch.object(sc, "_capture_live",
                               side_effect=RuntimeError(secret)), \
             mock.patch.object(sc, "_curtain_drawn", return_value=False):
            out = sc.safe_capture()
        self.assertEqual(out["status"], "capture_failed")
        self.assertIn(out["error_class"], {"portal", "pipewire", "gst", "timeout", "permission_denied"})
        # the raw exception text must NOT appear anywhere in the emitted contract
        self.assertNotIn(secret, json.dumps(out))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.NoLeakTests -v`
Expected: FAIL — `safe_capture` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screencast_capture.py — add
def safe_capture():
    """Wrap capture() so NO raw exception/traceback ever escapes to stdout."""
    try:
        return capture()
    except Exception:
        # Map to a generic stage; never include the exception text.
        return _result(status="capture_failed", error_class="gst")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if "--revoke" in argv:
        _emit(revoke()); return
    _emit(safe_capture())


if __name__ == "__main__":
    main()
```

(Live functions in Task 6 should also catch per-stage and return `_result(..., error_class=<stage>)` so a real failure is classified precisely; `safe_capture` is the last-resort net.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screencast_capture.NoLeakTests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/screencast_capture.py tests/test_screencast_capture.py
git commit -m "feat(body-ui): top-level guard — failures map to stage, never leak traceback/handles"
```

---

### Task 6: Live ScreenCast capture (lazy gi/Gst/Gio) — OWNER-WITNESSED, not unit-tested

**Files:**
- Modify: `scripts/screencast_capture.py` (`_capture_live`, replacing the Task-2 placeholder)

**Context:** This is the live portal+PipeWire+Gst path. It **cannot be unit-tested** (needs the session + a real grant) — it is proven by the owner witness (Task 9). Imports are lazy. Deletes its temp on failure; leaves it on success for the daemon. Per-stage `error_class`. The structure below is the contract Codex implements; the GLib mainloop signal wiring for the portal Request/Response is the implementer's to complete against `org.freedesktop.portal.ScreenCast`.

- [ ] **Step 1: Implement (no unit test — witnessed live in Task 9)**

```python
# scripts/screencast_capture.py — replace the _capture_live placeholder
def _capture_live():
    import time, tempfile
    t0 = time.time()
    tmp = tempfile.mktemp(prefix=TEMP_PREFIX, suffix=".png")
    try:
        # LAZY imports — only here, under system python3.
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gio, GLib, Gst  # noqa

        node_id, fd, new_token = _portal_screencast_session(_load_token())  # raises on portal failure
        if new_token:
            _save_token(new_token)
        if node_id is None:
            return _result(status="needs_grant")   # no token + no interactive grant
        _grab_one_frame_pipewire(fd, node_id, tmp)  # Gst pipewiresrc → tmp ; raises on gst failure
        size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if size <= 0:
            _safe_unlink(tmp)
            return _result(status="capture_failed", error_class="gst")
        return _result(status="ok", temp_path=tmp, bytes_=size,
                       duration_ms=int((time.time() - t0) * 1000))
    except _StageError as e:           # raised by helpers with a stage label
        _safe_unlink(tmp)
        return _result(status="capture_failed", error_class=e.stage,
                       duration_ms=int((time.time() - t0) * 1000))
    except Exception:
        _safe_unlink(tmp)
        return _result(status="capture_failed", error_class="gst",
                       duration_ms=int((time.time() - t0) * 1000))


class _StageError(Exception):
    def __init__(self, stage):
        super().__init__(stage); self.stage = stage


def _safe_unlink(p):
    try:
        if p and os.path.exists(p):
            os.unlink(p)
    except Exception:
        pass


def _portal_screencast_session(restore_token):
    """CreateSession → SelectSources(types=MONITOR, persist_mode=2, restore_token)
    → Start → OpenPipeWireRemote(fd). Returns (node_id, fd, new_restore_token).
    Returns (None, None, None) when there is no token and no interactive grant is
    possible (headless). Raises _StageError('portal'|'permission_denied') on failure.
    Implementer: Gio.DBusProxy to org.freedesktop.portal.Desktop, subscribe to the
    Request Response signal, run a GLib.MainLoop until Start responds; fd via
    OpenPipeWireRemote (Gio gives the unix fd in-process)."""
    raise _StageError("portal")  # implemented against the live portal


def _grab_one_frame_pipewire(fd, node_id, tmp):
    """Gst: pipewiresrc fd=<fd> path=<node_id> ! videoconvert ! pngenc ! filesink
    location=<tmp> ; run to first buffer, EOS, NULL state. Raise _StageError('gst'/'pipewire'/'timeout')."""
    raise _StageError("gst")
```

- [ ] **Step 2: Smoke-compile (no live call)**

Run: `/usr/bin/python3 -c "import ast; ast.parse(open('scripts/screencast_capture.py').read()); print('parse ok')"`
Then: `.venv/bin/python -B -m unittest tests.test_screencast_capture -v` (the venv suite must still pass — lazy imports keep it green even though `_capture_live` would raise if called).
Expected: parse ok; venv suite PASS (no test calls the live path).

- [ ] **Step 3: Commit**

```bash
git add scripts/screencast_capture.py
git commit -m "$(printf 'feat(body-ui): live ScreenCast capture path (lazy gi/Gst/Gio, per-stage errors)\n\n## Predicted effect\nUnder system python3 with an owner grant, capture() returns one ScreenCast\nframe (restore_token, no repeat prompt) to a maez-screencast- temp; failures\nmap to a stage (portal/pipewire/gst/timeout/permission_denied) with no\ntraceback. Witnessed live in Task 9 (needs the graphical session); the venv\nsuite stays green via lazy imports.')"
```

---

### Task 7: Daemon integration — `screencast` candidate + path validation + unlink-after-read

**Files:**
- Modify: `skills/screen_perception.py`
- Test: `tests/test_screen_perception_lens.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class ScreencastCandidateTests(unittest.TestCase):
    def test_screencast_first_on_wayland_gnome(self):
        with mock.patch.object(sp, "_session_type", return_value="wayland-gnome"):
            names = [c["name"] for c in sp._capture_candidates()]
        self.assertEqual(names[0], "screencast")

    def test_helper_ok_writes_dest_and_unlinks_helper_temp(self):
        import tempfile, os, json
        helper_tmp = tempfile.mktemp(prefix="maez-screencast-", suffix=".png")
        open(helper_tmp, "wb").write(b"\x89PNG-fake")
        dest = tempfile.mktemp(suffix=".png")  # the daemon's capture tmp
        fake = json.dumps({"status": "ok", "temp_path": helper_tmp, "bytes": 9,
                           "duration_ms": 5, "error_class": ""})
        with mock.patch.object(sp.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout=fake)):
            ok = sp._capture_via_screencast(dest)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(dest))          # frame written into the daemon tmp
        self.assertEqual(open(dest, "rb").read(), b"\x89PNG-fake")
        self.assertFalse(os.path.exists(helper_tmp))   # helper temp unlinked (daemon owns it on success)
        os.unlink(dest)

    def test_foreign_path_rejected(self):
        import json
        fake = json.dumps({"status": "ok", "temp_path": "/etc/passwd",
                           "bytes": 9, "duration_ms": 1, "error_class": ""})
        with mock.patch.object(sp.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout=fake)):
            ok = sp._capture_via_screencast("/tmp/dest.png")
        self.assertFalse(ok)  # not under temp dir / not maez-screencast- prefix → rejected, not read

    def test_non_ok_status_returns_false(self):
        import json
        for st in ("needs_grant", "curtain_drawn", "capture_failed"):
            fake = json.dumps({"status": st, "temp_path": None, "bytes": 0,
                               "duration_ms": 0, "error_class": "portal"})
            with mock.patch.object(sp.subprocess, "run",
                                   return_value=mock.Mock(returncode=0, stdout=fake)):
                self.assertFalse(sp._capture_via_screencast("/tmp/dest.png"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.ScreencastCandidateTests -v`
Expected: FAIL — `_capture_via_screencast` not defined; `screencast` not in candidates.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/screen_perception.py
import json, tempfile

_SCREENCAST_HELPER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "screencast_capture.py")
_SCREENCAST_PYTHON = "/usr/bin/python3"  # system python (has gi); venv lacks it
_SCREENCAST_PREFIX = "maez-screencast-"


def _valid_helper_temp(path: str) -> bool:
    """Only read an existing regular file under the system temp dir with our prefix."""
    if not path:
        return False
    tmpdir = os.path.realpath(tempfile.gettempdir())
    rp = os.path.realpath(path)
    if os.path.commonpath([tmpdir, rp]) != tmpdir:
        return False
    if not os.path.basename(rp).startswith(_SCREENCAST_PREFIX):
        return False
    return os.path.isfile(rp) and not os.path.islink(path)


def _capture_via_screencast(tmp) -> bool:
    """Shell to the system-python3 ScreenCast helper; on ok+valid path, copy the
    frame INTO the daemon's capture `tmp` (same contract as every other candidate),
    then unlink the helper's own temp. Content-free."""
    try:
        result = subprocess.run(
            [_SCREENCAST_PYTHON, _SCREENCAST_HELPER],
            env=DISPLAY_ENV, capture_output=True, text=True, timeout=SCREENSHOT_TIMEOUT,
        )
        if result.returncode != 0:
            return False
        data = json.loads((result.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        logger.debug("screencast helper failed: %s", e)
        return False
    if data.get("status") != "ok":
        return False
    path = data.get("temp_path")
    if not _valid_helper_temp(path):
        return False
    try:
        with open(path, "rb") as src:
            payload = src.read()
        with open(tmp, "wb") as dst:          # write into the daemon's capture tmp
            dst.write(payload)
        return bool(payload)
    except Exception as e:
        logger.debug("screencast frame copy failed: %s", e)
        return False
    finally:
        try:
            os.unlink(path)  # daemon owns deletion of the HELPER temp on success
        except Exception:
            pass
```

Wire it into `_capture_candidates()` for `wayland-gnome` as the FIRST candidate. No other change to `_capture_screenshot()` is needed — the `screencast` `fn(tmp)` writes the PNG into `tmp` exactly like the other candidates, so the existing PIL-downscale + base64 + `finally`-cleanup apply unchanged. Keep `gnome-shell-dbus`/`portal` after it (dead, but harmless).

```python
    if session == "wayland-gnome":
        return [
            {"name": "screencast", "fn": lambda tmp: _capture_via_screencast(tmp)},
            {"name": "gnome-shell-dbus", "fn": _capture_gnome_shell_dbus},
            {"name": "portal", "fn": _capture_portal_noprompt},
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_screen_perception_lens.ScreencastCandidateTests -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "$(printf 'feat(body-ui): daemon screencast capture candidate — path-validated, unlink-after-read\n\n## Predicted effect\nOn wayland-gnome, screen capture first tries the system-python3 ScreenCast\nhelper; on status=ok with a validated maez-screencast- temp under the temp\ndir, the daemon reads it, base64s it, and unlinks it. Foreign/symlink/non-ok\npaths are rejected and not read. observe() gate order unchanged.')"
```

---

### Task 8: Boundary regression — `observe()` unchanged, Lens v0/v1a/gate green

**Files:** none (verification)

- [ ] **Step 1: Run the focused suites + the new helper suite**

Run:
```bash
.venv/bin/python -B -m unittest \
  tests.test_screencast_capture \
  tests.test_screen_perception_lens tests.test_screen_perception_v1a \
  tests.test_screen_perception_gate tests.test_ambient_active_window_wayland -v
```
Expected: ALL PASS. `observe()` is untouched — the v1a/gate/lens suites prove the fail-safe preflight, gate order, and honest-blind states are byte-unchanged (capture-half-only boundary).

- [ ] **Step 2: Full discover (apples-to-apples)**

Run: `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -15`
Expected: floor matches main's known asset-confound class (run in `/home/rohit/maez`); no new failures in screen/lens/screencast suites.

---

### Task 9: Grant ceremony + end-to-end witness (OWNER-RUN, graphical session)

**Files:**
- Modify: `scripts/screencast_capture.py` (optional `--grant` mode that makes the first interactive grant explicit)

**Context:** The live portal/Gst path is proven only here — neither lane can run it (needs the session's capture authority + an interactive grant). Content-free throughout.

- [ ] **Step 1: First grant (owner, graphical session)**

Run: `/usr/bin/python3 /home/rohit/maez/scripts/screencast_capture.py`
Expect: GNOME picker → owner grants a monitor → `{"status":"ok","bytes":>0,...}`; token saved `0600` at `~/.config/maez/screencast_restore_token`.

- [ ] **Step 2: No-prompt restore (THE question)**

Run the same command again. Expect: **no picker**, `{"status":"ok","bytes":>0,"duration_ms":N}`. If it re-prompts → honest finding (restore_token insufficient on this backend) — record it, do not smuggle.

- [ ] **Step 3: Vision ok on the frame** — via the daemon's direct capture path (the probe): `cd /home/rohit/maez && .venv/bin/python -B scripts/lens_probe.py` should now show `capture[screencast]: ok=True bytes>0`. (Claude reads content-free.)

- [ ] **Step 4: Soft curtain** — `touch ~/.config/maez/screen_perception.curtain` → helper returns `curtain_drawn`, zero frame; `rm` it → `ok` again **without re-grant** (token retained).

- [ ] **Step 5: Hard revoke** — `/usr/bin/python3 scripts/screencast_capture.py --revoke` → token deleted + curtain drawn; next call needs a fresh grant.

- [ ] **Step 6: Latency verdict** — record `duration_ms`; verdict is one of works / works-but-too-slow-for-cycle / fails — all valid, recorded honestly.

- [ ] **Step 7: Commit any `--grant` ergonomics + record the witness outcome.**

---

### Task 10: Finish — canon + branch completion

- [ ] **Step 1:** Update `project_cognition_live_state.md` (canon) with the Slice A outcome: capture-half result (no-prompt restore? latency verdict?), curtain proven, token-secret held, **boundary: still no sight, v1b still blocked**, Slice B (active-window) named next.
- [ ] **Step 2:** Use **superpowers:finishing-a-development-branch** — local merge is owner-delegable per the arc; the **grant ceremony + any restart stay the owner's breath.** NO push.
- [ ] **Step 3:** Confirm Slice B + v1b remain deferred; v1b stays blocked until sight (Slice B) exists.
