# Jetson Presence B0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the B0 edge-app skeleton on the Jetson — capture + curtain + structural no-frame-write + honest-`unknown` labels POSTed through the already-witnessed Slice-A doorway. No recognition, no enrollment, no model, no biometric.

**Architecture:** A small importable package `devices/jetson_presence/jetson_presence/` (source in the Maez repo, backed up). Pure logic (label rule, orchestration) is host-unit-tested with `cv2`/`requests` injected; the only hardware/network I/O lives in thin `capture.py`/`emitter.py` adapters witnessed on-device. B0 emits `owner_present="unknown"`, fixed `confidence="low"`, always — never `present`/`absent`.

**Tech Stack:** Python 3.10 (host venv + Jetson system python), stdlib + `cv2` (Jetson) + `requests` (Jetson). Host tests: `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). cv2/requests are **injected** in host tests, so the host venv does not need them.

**Spec:** `docs/superpowers/specs/2026-06-30-real-presence-jetson-slice-b-design.md` (@9eb5122). This plan is **B0 only**; B1 (recognition/enrollment) and B2 (daemon) are separate plans.

**Covenant invariants this slice must hold:**
- `owner_present` is **always `unknown`** in B0; `confidence` is **always fixed `low`**; never `present`/`absent`.
- **No frame-write path anywhere** (no `imwrite`/`VideoWriter`/`write_bytes`/`tofile`/`Image.save`/`open(...,'wb')`); frames RAM-only.
- The curtain **releases `/dev/video0`** (real teardown), not a masked frame.
- The edge contract (schema_version, keys, enums) **must not drift** from `core.body.jetson_presence`.
- `deploy.sh` copies **source only** — never the token or a runtime secret file.
- `run.py` is **bounded** (`--once`/`--loops N`); no daemon/systemd/infinite loop (that's B2).

---

## File Structure

```
devices/jetson_presence/
  jetson_presence/
    __init__.py          # package marker (empty)
    labels.py            # pure: build_label(sensor_state, ts) -> 5-field dict; self-contained constants
    config.py            # runtime config: host url, token (from env), sentinel path, cadence, device index
    capture.py           # thin cv2 adapter: Camera(open/read_frame/release); cv2 lazy/injected; NO write path
    emitter.py           # thin requests adapter: post_label(...); requests lazy/injected
    presence_loop.py     # orchestration: run_once(...) state map; capture+emitter+curtain injected
    run.py               # bounded entry: --once / --loops N
  deploy.sh              # rsync the inner package to the Jetson; SOURCE ONLY
tests/
  _jetson_edge_path.py               # shared: put devices/jetson_presence on sys.path for host imports
  test_jetson_edge_labels.py         # label rule + contract-drift vs core.body.jetson_presence
  test_jetson_edge_capture.py        # injected-cv2 adapter behavior + no write call
  test_jetson_edge_emitter.py        # injected-requests POST shape
  test_jetson_edge_loop.py           # the exact B0 state map
  test_jetson_edge_no_frame_write.py # broad static + dynamic no-write guard
  test_jetson_edge_run.py            # bounded run
```

---

## Task 1: Package skeleton + the label rule + contract-drift test

**Files:**
- Create: `devices/jetson_presence/jetson_presence/__init__.py` (empty), `devices/jetson_presence/jetson_presence/labels.py`
- Create: `tests/_jetson_edge_path.py`, `tests/test_jetson_edge_labels.py`

- [ ] **Step 1: Create the host-import path helper**

```python
# tests/_jetson_edge_path.py
"""Put the Jetson edge package on sys.path for host-side unit tests.

The package lives at devices/jetson_presence/jetson_presence/ so the Jetson can
deploy + run `python -m jetson_presence.run`. Host tests import it the same way.
"""
import os
import sys

_PKG_PARENT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices", "jetson_presence")
)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_jetson_edge_labels.py
import unittest
import tests._jetson_edge_path  # noqa: F401  (path side-effect)
from jetson_presence import labels


class LabelRuleTests(unittest.TestCase):
    def test_available_is_unknown_low(self):
        lab = labels.build_label("available", "2026-06-30T12:00:00+00:00")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")
        self.assertEqual(lab["sensor_state"], "available")
        self.assertEqual(lab["ts"], "2026-06-30T12:00:00+00:00")
        self.assertEqual(lab["schema_version"], "jetson_presence.v0")

    def test_curtained_and_unavailable_still_unknown_low(self):
        for state in ("curtained", "unavailable", "error"):
            lab = labels.build_label(state, "t")
            self.assertEqual(lab["owner_present"], "unknown")
            self.assertEqual(lab["confidence"], "low")
            self.assertEqual(lab["sensor_state"], state)

    def test_b0_never_emits_present_or_absent(self):
        # B0 has no path to present/absent: build_label fixes owner_present.
        for state in ("available", "curtained", "unavailable", "error", "unenrolled"):
            self.assertEqual(labels.build_label(state, "t")["owner_present"], "unknown")

    def test_rejects_unknown_sensor_state(self):
        with self.assertRaises(ValueError):
            labels.build_label("teleporting", "t")

    def test_exact_five_keys(self):
        self.assertEqual(
            set(labels.build_label("available", "t").keys()),
            {"owner_present", "confidence", "sensor_state", "ts", "schema_version"},
        )


class ContractDriftTests(unittest.TestCase):
    """The edge producer and the host doorway must not drift silently."""

    def test_schema_version_matches_host(self):
        from core.body import jetson_presence as host
        self.assertEqual(labels.SCHEMA_VERSION, host.SCHEMA_VERSION)

    def test_sensor_states_subset_of_host_wire_enum(self):
        from core.body import jetson_presence as host
        # Every state the edge can emit must be a wire-valid host sensor_state.
        self.assertTrue(labels.SENSOR_STATES <= host._SENSOR_STATE_WIRE)

    def test_label_keys_match_host_allowed_keys(self):
        from core.body import jetson_presence as host
        self.assertEqual(
            set(labels.build_label("available", "t").keys()), host._ALLOWED_KEYS
        )

    def test_fixed_owner_present_and_confidence_are_host_valid(self):
        from core.body import jetson_presence as host
        self.assertIn(labels.FIXED_OWNER_PRESENT, host._OWNER_PRESENT)
        self.assertIn(labels.FIXED_CONFIDENCE, host._CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_labels -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence'`.

- [ ] **Step 4: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/__init__.py
```

```python
# devices/jetson_presence/jetson_presence/labels.py
"""Pure B0 label rule for the Jetson edge producer.

Self-contained (the Jetson deploys only this package), but a host test pins its
constants against core.body.jetson_presence so the edge cannot drift from the
doorway. B0 always emits owner_present=unknown, confidence=low.
"""
from __future__ import annotations

SCHEMA_VERSION = "jetson_presence.v0"
SENSOR_STATES = frozenset(
    {"available", "unavailable", "curtained", "unenrolled", "error"}
)
FIXED_OWNER_PRESENT = "unknown"   # B0: no recognition; never present/absent
FIXED_CONFIDENCE = "low"          # B0: fixed; never derived (no occupancy leak)


def build_label(sensor_state: str, ts: str) -> dict:
    """Return the five-field jetson_presence.v0 label for B0.

    owner_present and confidence are fixed; only sensor_state and ts vary.
    """
    if sensor_state not in SENSOR_STATES:
        raise ValueError(f"unknown sensor_state: {sensor_state!r}")
    return {
        "owner_present": FIXED_OWNER_PRESENT,
        "confidence": FIXED_CONFIDENCE,
        "sensor_state": sensor_state,
        "ts": ts,
        "schema_version": SCHEMA_VERSION,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_labels -v`
Expected: PASS (8 tests). If a `ContractDriftTests` test fails, the edge and host genuinely disagree — fix `labels.py` to match `core.body.jetson_presence`, do not weaken the test.

- [ ] **Step 6: Commit**

```bash
git add devices/jetson_presence/jetson_presence/__init__.py devices/jetson_presence/jetson_presence/labels.py tests/_jetson_edge_path.py tests/test_jetson_edge_labels.py
git commit -m "feat(jetson-edge): B0 pure label rule + host contract-drift test"
```

---

## Task 2: Runtime config

**Files:**
- Create: `devices/jetson_presence/jetson_presence/config.py`
- Create: `tests/test_jetson_edge_config.py` (added to the labels test run group)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_edge_config.py
import os
import unittest
from unittest import mock
import tests._jetson_edge_path  # noqa: F401
from jetson_presence import config


class ConfigTests(unittest.TestCase):
    def test_defaults_when_env_absent(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.load_config()
            self.assertEqual(cfg.host_url, "http://127.0.0.1:11437")
            self.assertEqual(cfg.intake_path, "/api/v1/presence/jetson/intake")
            self.assertEqual(cfg.device_index, 0)
            self.assertEqual(cfg.token, "")  # no token -> emitter will 401, fail-closed

    def test_env_overrides(self):
        env = {
            "MAEZ_JETSON_HOST_URL": "http://10.0.0.5:11437",
            "MAEZ_JETSON_DEVICE_TOKEN": "tok-abc",
            "MAEZ_JETSON_CURTAIN_SENTINEL": "/run/maez/curtain",
            "MAEZ_JETSON_DEVICE_INDEX": "1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = config.load_config()
            self.assertEqual(cfg.host_url, "http://10.0.0.5:11437")
            self.assertEqual(cfg.token, "tok-abc")
            self.assertEqual(cfg.curtain_sentinel, "/run/maez/curtain")
            self.assertEqual(cfg.device_index, 1)

    def test_token_is_never_a_literal_in_source(self):
        import inspect
        src = inspect.getsource(config)
        self.assertNotIn("MAEZ_JETSON_DEVICE_TOKEN=", src)  # read from env, not embedded


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence.config'`.

- [ ] **Step 3: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/config.py
"""Runtime config for the Jetson edge producer. Read from env; no secrets in source."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeConfig:
    host_url: str
    intake_path: str
    token: str
    curtain_sentinel: str
    device_index: int
    cadence_seconds: float


def load_config() -> EdgeConfig:
    return EdgeConfig(
        host_url=os.environ.get("MAEZ_JETSON_HOST_URL", "http://127.0.0.1:11437"),
        intake_path="/api/v1/presence/jetson/intake",
        token=os.environ.get("MAEZ_JETSON_DEVICE_TOKEN", ""),
        curtain_sentinel=os.environ.get(
            "MAEZ_JETSON_CURTAIN_SENTINEL", "/run/maez/jetson_curtain"
        ),
        device_index=int(os.environ.get("MAEZ_JETSON_DEVICE_INDEX", "0")),
        cadence_seconds=float(os.environ.get("MAEZ_JETSON_CADENCE_SECONDS", "5")),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_config -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/config.py tests/test_jetson_edge_config.py
git commit -m "feat(jetson-edge): B0 runtime config (env-only, no embedded secret)"
```

---

## Task 3: The capture adapter (lazy/injected cv2, no write path)

**Files:**
- Create: `devices/jetson_presence/jetson_presence/capture.py`
- Create: `tests/test_jetson_edge_capture.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_edge_capture.py
import unittest
from unittest import mock
import tests._jetson_edge_path  # noqa: F401
from jetson_presence import capture


class _FakeCap:
    def __init__(self, opened=True, read_ok=True):
        self._opened = opened
        self._read_ok = read_ok
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        return (self._read_ok, object() if self._read_ok else None)

    def release(self):
        self.released = True


class _FakeCV2:
    """Minimal injected cv2: VideoCapture only. No imwrite/VideoWriter exposed."""
    def __init__(self, cap):
        self._cap = cap

    def VideoCapture(self, index):
        return self._cap


class CaptureTests(unittest.TestCase):
    def test_open_read_release(self):
        cap = _FakeCap(opened=True, read_ok=True)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        self.assertTrue(cam.open())
        ok, frame = cam.read_frame()
        self.assertTrue(ok)
        self.assertIsNotNone(frame)  # frame in RAM, returned, never written
        cam.release()
        self.assertTrue(cap.released)

    def test_open_failure(self):
        cap = _FakeCap(opened=False)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        self.assertFalse(cam.open())

    def test_read_failure(self):
        cap = _FakeCap(opened=True, read_ok=False)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        cam.open()
        ok, frame = cam.read_frame()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_capture_module_calls_no_write(self):
        # The injected cv2 has no imwrite/VideoWriter; if capture.py tried to call
        # one, this would AttributeError. Exercise the full path.
        cap = _FakeCap(opened=True, read_ok=True)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        cam.open()
        cam.read_frame()
        cam.release()
        # _FakeCV2 exposes only VideoCapture -> any write attempt would have raised.


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_capture -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence.capture'`.

- [ ] **Step 3: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/capture.py
"""Thin cv2 capture adapter. The ONLY hardware I/O in B0.

cv2 is injected (tests) or imported lazily (device), so host tests need no
OpenCV. There is deliberately NO frame-write path here: frames are read into
RAM, returned, and dropped by the caller. No frame-write APIs, no file sink --
the no-frame-write guard test enforces this and names the forbidden calls.
"""
from __future__ import annotations


class Camera:
    def __init__(self, *, device_index: int, cv2_module=None):
        self._index = device_index
        self._cv2 = cv2_module  # injected for tests; None -> lazy import on open()
        self._cap = None

    def _cv2_mod(self):
        if self._cv2 is None:
            import cv2  # lazy: device-only dependency
            self._cv2 = cv2
        return self._cv2

    def open(self) -> bool:
        self._cap = self._cv2_mod().VideoCapture(self._index)
        return bool(self._cap.isOpened())

    def read_frame(self):
        """Return (ok, frame). frame lives in RAM; the caller discards it. Never written."""
        if self._cap is None:
            return (False, None)
        ok, frame = self._cap.read()
        return (bool(ok), frame if ok else None)

    def release(self) -> None:
        """Real teardown: release /dev/video0 (the curtain's mechanism)."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_capture -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/capture.py tests/test_jetson_edge_capture.py
git commit -m "feat(jetson-edge): B0 capture adapter (lazy/injected cv2, no write path)"
```

---

## Task 4: The emitter (lazy/injected requests)

**Files:**
- Create: `devices/jetson_presence/jetson_presence/emitter.py`
- Create: `tests/test_jetson_edge_emitter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_edge_emitter.py
import unittest
from unittest import mock
import tests._jetson_edge_path  # noqa: F401
from jetson_presence import emitter


class _FakeResp:
    def __init__(self, code):
        self.status_code = code


class _FakeRequests:
    def __init__(self, code=200):
        self.calls = []
        self._code = code

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _FakeResp(self._code)


class EmitterTests(unittest.TestCase):
    def test_post_shape(self):
        fake = _FakeRequests(code=200)
        label = {"owner_present": "unknown", "confidence": "low",
                 "sensor_state": "available", "ts": "t", "schema_version": "jetson_presence.v0"}
        code = emitter.post_label(
            "http://127.0.0.1:11437", "/api/v1/presence/jetson/intake",
            token="tok-abc", label=label, requests_module=fake,
        )
        self.assertEqual(code, 200)
        call = fake.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:11437/api/v1/presence/jetson/intake")
        self.assertEqual(call["headers"]["X-Maez-Jetson-Token"], "tok-abc")
        self.assertEqual(call["json"], label)
        self.assertIsNotNone(call["timeout"])

    def test_network_error_returns_none(self):
        class _Boom:
            def post(self, *a, **k):
                raise OSError("network down")
        code = emitter.post_label("http://h", "/p", token="t", label={}, requests_module=_Boom())
        self.assertIsNone(code)  # best-effort: never crash the loop on a transport error


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_emitter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence.emitter'`.

- [ ] **Step 3: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/emitter.py
"""Thin requests adapter: POST a label to the host doorway. The ONLY network I/O."""
from __future__ import annotations


def post_label(host_url, intake_path, *, token, label, requests_module=None, timeout=4.0):
    """POST the label with the device token. Returns status code, or None on transport error."""
    if requests_module is None:
        import requests  # lazy: device-only dependency
        requests_module = requests
    url = host_url.rstrip("/") + intake_path
    try:
        resp = requests_module.post(
            url, json=label, headers={"X-Maez-Jetson-Token": token}, timeout=timeout
        )
        return resp.status_code
    except Exception:
        return None  # best-effort; a dropped POST must not crash the loop
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_emitter -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/emitter.py tests/test_jetson_edge_emitter.py
git commit -m "feat(jetson-edge): B0 emitter (lazy/injected requests, best-effort POST)"
```

---

## Task 5: The orchestration loop (the exact B0 state map)

**Files:**
- Create: `devices/jetson_presence/jetson_presence/presence_loop.py`
- Create: `tests/test_jetson_edge_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_edge_loop.py
import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence import presence_loop


class _Cam:
    def __init__(self, open_ok=True, read_ok=True):
        self._open_ok = open_ok
        self._read_ok = read_ok
        self.opened = False
        self.released = False
        self.frames_read = 0

    def open(self):
        self.opened = True
        return self._open_ok

    def read_frame(self):
        self.frames_read += 1
        return (self._read_ok, object() if self._read_ok else None)

    def release(self):
        self.released = True


class LoopStateMapTests(unittest.TestCase):
    def _run(self, cam, curtained):
        emitted = []
        lab = presence_loop.run_once(
            camera=cam,
            emit=lambda label: emitted.append(label),
            is_curtained=lambda: curtained,
            now_ts=lambda: "T",
        )
        return lab, emitted

    def test_curtained_releases_camera_and_emits_curtained(self):
        cam = _Cam()
        lab, emitted = self._run(cam, curtained=True)
        self.assertTrue(cam.released)
        self.assertFalse(cam.opened)          # curtained never opens the camera
        self.assertEqual(lab["sensor_state"], "curtained")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")
        self.assertEqual(emitted, [lab])

    def test_open_and_read_ok_is_available_unknown_and_releases(self):
        cam = _Cam(open_ok=True, read_ok=True)
        lab, emitted = self._run(cam, curtained=False)
        self.assertTrue(cam.opened)
        self.assertEqual(cam.frames_read, 1)   # frame read (RAM) and discarded
        self.assertTrue(cam.released)          # blink: released every cycle
        self.assertEqual(lab["sensor_state"], "available")
        self.assertEqual(lab["owner_present"], "unknown")

    def test_open_fail_is_unavailable_unknown_and_releases(self):
        cam = _Cam(open_ok=False)
        lab, _ = self._run(cam, curtained=False)
        self.assertTrue(cam.released)          # released even when open fails
        self.assertEqual(lab["sensor_state"], "unavailable")
        self.assertEqual(lab["owner_present"], "unknown")

    def test_read_fail_is_error_unknown_and_releases(self):
        cam = _Cam(open_ok=True, read_ok=False)
        lab, _ = self._run(cam, curtained=False)
        self.assertTrue(cam.released)          # released even when read fails
        self.assertEqual(lab["sensor_state"], "error")
        self.assertEqual(lab["owner_present"], "unknown")

    def test_never_present_or_absent(self):
        for curtained, ook, rok in [(True, True, True), (False, True, True),
                                    (False, False, True), (False, True, False)]:
            lab, _ = self._run(_Cam(open_ok=ook, read_ok=rok), curtained=curtained)
            self.assertIn(lab["owner_present"], ("unknown",))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_loop -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence.presence_loop'`.

- [ ] **Step 3: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/presence_loop.py
"""B0 orchestration: one cycle of the exact B0 state map. No recognition.

State map (B0):
  curtained                  -> sensor_state=curtained
  camera opens + frame reads -> sensor_state=available
  camera will not open       -> sensor_state=unavailable
  opened but read fails      -> sensor_state=error
owner_present is always 'unknown', confidence always 'low' (in build_label).
Frames are read into RAM and DROPPED here -- never stored, never written.
"""
from __future__ import annotations

from jetson_presence.labels import build_label


def run_once(*, camera, emit, is_curtained, now_ts):
    """Run one cycle; build + emit the label; return it. All deps injected.

    B0 'blink' discipline: open the eye, read one frame (dropped), close it.
    The camera is released EVERY cycle (in a finally) -- B0 never holds
    /dev/video0 past one tiny cycle. Persistent ownership can wait for B2.
    """
    ts = now_ts()
    if is_curtained():
        camera.release()  # ensure released; curtained never opens
        label = build_label("curtained", ts)
    else:
        try:
            if not camera.open():
                label = build_label("unavailable", ts)
            else:
                ok, _frame = camera.read_frame()  # frame in RAM, dropped here
                label = build_label("available" if ok else "error", ts)
        finally:
            camera.release()  # blink: release /dev/video0 every cycle, even on failure
    emit(label)
    return label
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_loop -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/presence_loop.py tests/test_jetson_edge_loop.py
git commit -m "feat(jetson-edge): B0 orchestration state map (frames RAM-only, dropped)"
```

---

## Task 6: The broad no-frame-write guard

**Files:**
- Create: `tests/test_jetson_edge_no_frame_write.py` (test-only; proves the covenant, no production code)

- [ ] **Step 1: Write the test**

```python
# tests/test_jetson_edge_no_frame_write.py
import os
import unittest
import tests._jetson_edge_path  # noqa: F401

_PKG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices", "jetson_presence", "jetson_presence")
)

_FORBIDDEN_TOKENS = (
    "imwrite", "VideoWriter", "imencode",   # cv2 frame sinks
    "write_bytes", ".tofile(", ".save(",     # pathlib / numpy / PIL sinks
    "'wb'", '"wb"', "'ab'", '"ab"',          # binary file opens
)


class NoFrameWriteStaticTests(unittest.TestCase):
    def test_no_write_token_in_any_source_file(self):
        offenders = []
        for name in os.listdir(_PKG_DIR):
            if not name.endswith(".py"):
                continue
            src = open(os.path.join(_PKG_DIR, name), encoding="utf-8").read()
            for tok in _FORBIDDEN_TOKENS:
                if tok in src:
                    offenders.append(f"{name}: {tok}")
        self.assertEqual(offenders, [], f"forbidden frame-write tokens found: {offenders}")


class NoFrameWriteDynamicTests(unittest.TestCase):
    def test_running_a_cycle_writes_no_file(self):
        from unittest import mock
        import builtins
        import pathlib
        from jetson_presence import presence_loop

        class _Cam:
            def open(self): return True
            def read_frame(self): return (True, object())
            def release(self): pass

        writes = []
        real_open = builtins.open

        def _watch_open(path, mode="r", *a, **k):
            if any(c in mode for c in "wax"):   # any write/append/exclusive open
                writes.append((str(path), mode))
            return real_open(path, mode, *a, **k)

        with mock.patch("builtins.open", _watch_open), \
             mock.patch.object(pathlib.Path, "write_bytes",
                               lambda self, b: writes.append(("write_bytes", str(self)))):
            presence_loop.run_once(camera=_Cam(), emit=lambda l: None,
                                   is_curtained=lambda: False, now_ts=lambda: "t")
        self.assertEqual(writes, [], f"a file write happened during a B0 cycle: {writes}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it passes (characterizes existing clean code)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_no_frame_write -v`
Expected: PASS. If the static test FAILS, a forbidden sink was introduced — remove the write path, do not weaken the token list.

- [ ] **Step 3: Commit**

```bash
git add tests/test_jetson_edge_no_frame_write.py
git commit -m "test(jetson-edge): B0 structural no-frame-write guard (static + dynamic)"
```

---

## Task 7: The bounded entry point

**Files:**
- Create: `devices/jetson_presence/jetson_presence/run.py`
- Create: `tests/test_jetson_edge_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_edge_run.py
import unittest
from unittest import mock
import tests._jetson_edge_path  # noqa: F401
from jetson_presence import run


class RunBoundedTests(unittest.TestCase):
    def test_loops_n_times_then_exits(self):
        calls = {"n": 0}

        def _fake_cycle(**kwargs):
            calls["n"] += 1
            return {"sensor_state": "available", "owner_present": "unknown"}

        with mock.patch.object(run, "_run_one_cycle", _fake_cycle), \
             mock.patch.object(run.time, "sleep", lambda s: None):
            run.main(["--loops", "3"])
        self.assertEqual(calls["n"], 3)

    def test_once_runs_a_single_cycle(self):
        calls = {"n": 0}
        with mock.patch.object(run, "_run_one_cycle", lambda **k: calls.__setitem__("n", calls["n"] + 1)), \
             mock.patch.object(run.time, "sleep", lambda s: None):
            run.main(["--once"])
        self.assertEqual(calls["n"], 1)

    def test_no_infinite_default(self):
        # Default must be bounded (e.g. --loops 1), never an unbounded daemon in B0.
        calls = {"n": 0}
        with mock.patch.object(run, "_run_one_cycle", lambda **k: calls.__setitem__("n", calls["n"] + 1)), \
             mock.patch.object(run.time, "sleep", lambda s: None):
            run.main([])
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_run -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jetson_presence.run'`.

- [ ] **Step 3: Write minimal implementation**

```python
# devices/jetson_presence/jetson_presence/run.py
"""Bounded B0 runner. NO daemon, NO infinite loop -- that is B2.

Usage: python -m jetson_presence.run [--once | --loops N]
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from jetson_presence.capture import Camera
from jetson_presence.config import load_config
from jetson_presence.emitter import post_label
from jetson_presence.presence_loop import run_once


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_curtained(sentinel_path: str):
    return os.path.exists(sentinel_path)


def _run_one_cycle(*, cfg, camera):
    return run_once(
        camera=camera,
        emit=lambda label: post_label(cfg.host_url, cfg.intake_path, token=cfg.token, label=label),
        is_curtained=lambda: _is_curtained(cfg.curtain_sentinel),
        now_ts=_now_ts,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jetson presence B0 (bounded).")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="run a single cycle")
    g.add_argument("--loops", type=int, default=1, help="run N cycles then exit (default 1)")
    args = parser.parse_args(argv)
    loops = 1 if args.once else max(1, args.loops)

    cfg = load_config()
    camera = Camera(device_index=cfg.device_index)
    for i in range(loops):
        _run_one_cycle(cfg=cfg, camera=camera)
        if i + 1 < loops:
            time.sleep(cfg.cadence_seconds)
    camera.release()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_run -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/run.py tests/test_jetson_edge_run.py
git commit -m "feat(jetson-edge): B0 bounded runner (--once/--loops, no daemon)"
```

---

## Task 8: The deploy script (source only, no secrets)

**Files:**
- Create: `devices/jetson_presence/deploy.sh`, `devices/jetson_presence/.gitignore`

- [ ] **Step 1: Write the deploy script + gitignore**

```bash
# devices/jetson_presence/deploy.sh
#!/usr/bin/env bash
# Deploy the Jetson edge package SOURCE ONLY to the device. Never copies secrets.
set -euo pipefail

JETSON="${MAEZ_JETSON_SSH:-rohit@192.168.40.27}"
DEST="${MAEZ_JETSON_DEST:-/home/rohit/maez-jetson}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# rsync ONLY the package source. Exclude any local runtime/secret artifacts.
rsync -av --delete \
  --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '.env' --exclude 'secrets*' --exclude 'runtime*' --exclude '*.token' \
  "$HERE/jetson_presence/" "$JETSON:$DEST/jetson_presence/"

echo "Deployed source to $JETSON:$DEST/jetson_presence/"
echo "Token + flag are provisioned on the Jetson env, NOT copied from the repo."
echo "Run on device:  cd $DEST && MAEZ_JETSON_DEVICE_TOKEN=... python3 -m jetson_presence.run --once"
```

```gitignore
# devices/jetson_presence/.gitignore
# Runtime artifacts that must stay Jetson-local (never committed):
.env
secrets*
runtime*
*.token
__pycache__/
*.pyc
```

- [ ] **Step 2: Make it executable + sanity-check (no run on device yet)**

```bash
chmod +x devices/jetson_presence/deploy.sh
bash -n devices/jetson_presence/deploy.sh && echo "deploy.sh syntax OK"
```
Expected: `deploy.sh syntax OK`.

- [ ] **Step 3: Commit**

```bash
git add devices/jetson_presence/deploy.sh devices/jetson_presence/.gitignore
git commit -m "feat(jetson-edge): B0 deploy script (source only, secrets stay on device)"
```

---

## Task 9: Host regression + ruff + STOP at review gate

**Files:** none (verification).

- [ ] **Step 1: Run the full jetson-edge host suite**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_jetson_edge_labels tests.test_jetson_edge_config \
  tests.test_jetson_edge_capture tests.test_jetson_edge_emitter \
  tests.test_jetson_edge_loop tests.test_jetson_edge_no_frame_write \
  tests.test_jetson_edge_run -v
```
Expected: all PASS. **Contract-drift and no-frame-write tests must be green** — they are the covenant.

- [ ] **Step 2: Ruff on touched files**

Run: `/home/rohit/maez/.venv/bin/ruff check devices/jetson_presence/jetson_presence/ tests/test_jetson_edge_*.py tests/_jetson_edge_path.py`
Expected: `All checks passed!`

- [ ] **Step 3: git diff --check + scope**

Run: `git diff --check && git log --oneline -8`
Expected: clean; ~8 commits under `devices/jetson_presence/` + `tests/`. Nothing outside those paths.

- [ ] **Step 4: STOP at the review gate**

Do NOT deploy to the Jetson, do NOT run on-device, do NOT set any flag/token live. Report: branch/commit tip, the suite green (esp. contract-drift + no-frame-write), ruff clean, and the on-device witness plan below. Hand to **Codex for cross-lane covenant review**. The on-device live witnesses are the owner's, after review.

---

## On-device live witnesses (owner-run, after review/merge — NOT part of the build)

1. **Deploy:** `bash devices/jetson_presence/deploy.sh` (source only).
2. **Provision on the Jetson** (env, not from repo): `export MAEZ_JETSON_DEVICE_TOKEN=<the value in the host secrets.local.env>`; ensure the host `maez-web` has `MAEZ_JETSON_PRESENCE_SHADOW=1` (already set).
3. **No-frames witness:** snapshot the run dir, run `python3 -m jetson_presence.run --loops 3`, diff the dir → **zero new files**.
4. **Honest-unknown transport witness:** on the host, `grep jetson_presence_intake logs/maez-web.log | tail` → a real receipt with **`owner_present=unknown`** from the Jetson (never `present`).
5. **Curtain teardown witness:** `touch /run/maez/jetson_curtain`, run a cycle → emitter posts `sensor_state=curtained`; confirm `/dev/video0` is released (re-openable by another process). Remove the sentinel → `available` resumes.

---

## Self-Review

**Spec coverage (B0 portion):**
- Skeleton + package in repo: Tasks 1–7 (`devices/jetson_presence/jetson_presence/`). ✓
- Pure label rule, always unknown + fixed low: Task 1. ✓
- Contract no-drift vs host: Task 1 `ContractDriftTests`. ✓
- Exact B0 state map (curtained/available/unavailable/error → unknown/low; never present/absent): Task 5. ✓
- Lazy/injected cv2 (host tests need no OpenCV): Task 3. ✓
- Broad structural no-frame-write (imwrite/VideoWriter/write_bytes/tofile/save/'wb'): Task 6 (static + dynamic). ✓
- Curtain real teardown (release /dev/video0): Task 5 (release on curtain) + on-device witness 5. ✓
- Emitter to the Slice-A doorway with the device token: Task 4. ✓
- Deploy source-only, secrets stay on device: Task 8 + `.gitignore`. ✓
- Bounded run, no daemon: Task 7. ✓
- Real Jetson → host unknown receipt: on-device witness 4. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. (Task 6's import note is a clarifying aside, not a gap — the test code is complete.)

**Type consistency:** `build_label(sensor_state, ts)`, `Camera(device_index=, cv2_module=)` / `open()`/`read_frame()`/`release()`, `post_label(host_url, intake_path, *, token, label, requests_module=, timeout=)`, `run_once(*, camera, emit, is_curtained, now_ts)`, `load_config() -> EdgeConfig`, `run.main(argv)` / `run._run_one_cycle(*, cfg, camera)` — consistent across tasks.
