# Real-Presence Jetson v1 — Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the host-side shadow intake for `jetson_presence.v0` owner-presence labels — receive (authenticated POST) → validate → freshness-aware store (host `received_at`) → content-light receipt — flag-gated, non-prompting, behaviorally unavailable when off, driven by a mock emitter. Pure software, no hardware.

**Architecture:** Parallels the proven `core/body/camera_presence_state.py` pattern (frozen dataclass + `replace()` + `with_freshness()` deriving stale → `unknown`). The contract + freshness logic is pure and unit-tested without HTTP; a thin authenticated POST endpoint is the only doorway; storage, the flag, the receipt, and the device-token auth are separate units. Reuses the existing `strict_env_flag` rail for the flag; host time is `time.time()` float seconds throughout (store, endpoint, and tests all use float host-clock seconds — no `datetime` conversion). The intake receipt is a **dedicated content-light log line** — deliberately NOT `fresh_moment_receipts` (that store means "a private thought landed"; seeding it with presence labels would pollute the spark sequence and prematurely create its db). No new persistent file is created by this slice.

**Tech Stack:** Python 3, Flask (existing `skills/web_interface.py` app), `unittest`. Test command: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`.

**Spec:** `docs/superpowers/specs/2026-06-29-real-presence-jetson-v1-design.md` (@776f0f1). This plan implements **Slice A only**. Slices B (Jetson device app) and C (felt flip) are separate plans.

**Covenant invariants this slice must hold:**
- **Freshness rail:** stale/missing labels → `owner_present: unknown, sensor_state: stale` — **never `absent`**. Host `received_at` is the time authority.
- **Curtain precedence:** a fresh `curtained` label outranks other fresh states.
- **Non-prompting:** the stored state is **never** read into any prompt in Slice A (shadow).
- **Behaviorally unavailable when off:** with `MAEZ_JETSON_PRESENCE_SHADOW` unset, the endpoint returns 404, accepts no labels, and writes no persistent or runtime state. (The Flask route is registered and an empty in-memory store object exists at import, but neither does anything until the flag is on — no db/file is created, no label is recorded, no receipt line is emitted.)
- **No S7 token reuse:** the device token is a new, separate secret.
- **No receipt-surface pollution:** the intake never touches `fresh_moment_receipts` (the private-thought surface); its receipt is a dedicated content-light log line.

---

## File Structure

- **Create** `core/body/jetson_presence.py` — the `jetson_presence.v0` contract (pure logic): `JetsonPresenceReading` frozen dataclass, `parse_label()` validation, `effective_state()` freshness/curtain honesty rule, `_jetson_presence_shadow_enabled()` flag helper.
- **Create** `core/body/jetson_presence_store.py` — `JetsonPresenceStore`: holds the latest reading + host `received_at`; `record()` / `current(now)`.
- **Modify** `skills/web_interface.py` — add `_jetson_device_auth_ok()` and the `POST /api/v1/presence/jetson/intake` endpoint (flag-gated, auth-gated, validates, stores, receipts).
- **Create** `tests/test_jetson_presence_contract.py` — contract validation + freshness/curtain unit tests.
- **Create** `tests/test_jetson_presence_store.py` — store record/current + freshness tests.
- **Create** `tests/test_jetson_presence_intake.py` — endpoint flag-off/auth/validate/receipt tests + mock-emitter integration.

---

## Task 1: The label contract — `JetsonPresenceReading` + `parse_label()`

**Files:**
- Create: `core/body/jetson_presence.py`
- Test: `tests/test_jetson_presence_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_presence_contract.py
import unittest
from core.body.jetson_presence import JetsonPresenceReading, parse_label


class ParseLabelTests(unittest.TestCase):
    def _valid(self) -> dict:
        return {
            "owner_present": "present",
            "confidence": "high",
            "sensor_state": "available",
            "ts": "2026-06-29T19:00:00+00:00",
            "schema_version": "jetson_presence.v0",
        }

    def test_valid_label_parses(self):
        r = parse_label(self._valid())
        self.assertIsInstance(r, JetsonPresenceReading)
        self.assertEqual(r.owner_present, "present")
        self.assertEqual(r.confidence, "high")
        self.assertEqual(r.sensor_state, "available")
        self.assertEqual(r.observed_at, "2026-06-29T19:00:00+00:00")

    def test_bad_owner_present_enum_rejected(self):
        bad = self._valid() | {"owner_present": "maybe"}
        self.assertIsNone(parse_label(bad))

    def test_bad_sensor_state_enum_rejected(self):
        bad = self._valid() | {"sensor_state": "stale"}  # host-derived only, not wire-valid
        self.assertIsNone(parse_label(bad))

    def test_missing_field_rejected(self):
        bad = self._valid()
        del bad["confidence"]
        self.assertIsNone(parse_label(bad))

    def test_wrong_schema_version_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"schema_version": "jetson_presence.v9"}))

    def test_non_dict_rejected(self):
        self.assertIsNone(parse_label(None))
        self.assertIsNone(parse_label("present"))

    # Cross-field consistency: present/absent require sensor_state == available.
    def test_present_with_error_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "error"}))

    def test_absent_with_curtained_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "absent", "sensor_state": "curtained"}))

    def test_present_with_unenrolled_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "unenrolled"}))

    def test_present_with_unavailable_sensor_rejected(self):
        self.assertIsNone(parse_label(self._valid() | {"owner_present": "present", "sensor_state": "unavailable"}))

    def test_unknown_with_curtained_sensor_allowed(self):
        r = parse_label(self._valid() | {"owner_present": "unknown", "sensor_state": "curtained"})
        self.assertIsNotNone(r)
        self.assertEqual((r.owner_present, r.sensor_state), ("unknown", "curtained"))

    def test_present_with_available_sensor_allowed(self):
        r = parse_label(self._valid() | {"owner_present": "present", "sensor_state": "available"})
        self.assertIsNotNone(r)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.body.jetson_presence'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/body/jetson_presence.py
"""jetson_presence.v0 contract: pure label validation + the freshness honesty rule.

No I/O. The Jetson emits content-light owner-presence labels; this module is the
single place that decides what a label means — including the load-bearing rule that
a stale/missing label is `unknown`, never `absent`.
"""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = "jetson_presence.v0"

# Wire-valid enums (what the Jetson may emit). `stale` is NOT wire-valid — it is
# host-derived only (see effective_state).
_OWNER_PRESENT = frozenset({"present", "absent", "unknown"})
_CONFIDENCE = frozenset({"low", "medium", "high"})
_SENSOR_STATE_WIRE = frozenset({"available", "unavailable", "curtained", "unenrolled", "error"})


@dataclass(frozen=True)
class JetsonPresenceReading:
    owner_present: str
    confidence: str
    sensor_state: str
    observed_at: str  # the Jetson's self-reported ts — diagnostic only, never the duration authority


def parse_label(raw: object) -> JetsonPresenceReading | None:
    """Validate a raw payload into a reading, or return None if malformed."""
    if not isinstance(raw, dict):
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        return None
    owner_present = raw.get("owner_present")
    confidence = raw.get("confidence")
    sensor_state = raw.get("sensor_state")
    observed_at = raw.get("ts")
    if owner_present not in _OWNER_PRESENT:
        return None
    if confidence not in _CONFIDENCE:
        return None
    if sensor_state not in _SENSOR_STATE_WIRE:
        return None
    if not isinstance(observed_at, str) or not observed_at.strip():
        return None
    # Cross-field consistency: a coherent reading can only claim present/absent
    # when the sensor is actually available. Any non-available sensor_state
    # (curtained/unenrolled/unavailable/error) MUST report owner_present=unknown,
    # or the label is incoherent and rejected.
    if sensor_state != "available" and owner_present != "unknown":
        return None
    return JetsonPresenceReading(
        owner_present=owner_present,
        confidence=confidence,
        sensor_state=sensor_state,
        observed_at=observed_at,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: PASS (12 tests — 6 shape + 6 cross-field consistency).

- [ ] **Step 5: Commit**

```bash
git add core/body/jetson_presence.py tests/test_jetson_presence_contract.py
git commit -m "feat(jetson): jetson_presence.v0 contract + validation + sensor-state consistency"
```

---

## Task 2: The freshness honesty rule — `effective_state()`

**Files:**
- Modify: `core/body/jetson_presence.py`
- Test: `tests/test_jetson_presence_contract.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_jetson_presence_contract.py`)

```python
from core.body.jetson_presence import effective_state

DEFAULT_STALE_AFTER_SECONDS = 180


class EffectiveStateTests(unittest.TestCase):
    def _reading(self, owner_present="present", sensor_state="available"):
        return JetsonPresenceReading(owner_present, "high", sensor_state, "2026-06-29T19:00:00+00:00")

    def test_fresh_present_passes_through(self):
        owner, sensor = effective_state(self._reading(), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("present", "available"))

    def test_fresh_absent_passes_through(self):
        owner, sensor = effective_state(self._reading(owner_present="absent"), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("absent", "available"))

    def test_stale_becomes_unknown_never_absent(self):
        # received 200s ago, window 180 -> stale
        owner, sensor = effective_state(self._reading(owner_present="present"), received_at=1000.0, now=1200.0, stale_after=180)
        self.assertEqual(sensor, "stale")
        self.assertEqual(owner, "unknown")  # the load-bearing rule: NOT "absent"

    def test_stale_overrides_even_an_absent_label(self):
        owner, sensor = effective_state(self._reading(owner_present="absent"), received_at=1000.0, now=1200.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "stale"))

    def test_fresh_curtained_outranks(self):
        owner, sensor = effective_state(self._reading(owner_present="unknown", sensor_state="curtained"), received_at=1000.0, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "curtained"))

    def test_no_reading_is_unavailable_unknown(self):
        owner, sensor = effective_state(None, received_at=None, now=1010.0, stale_after=180)
        self.assertEqual((owner, sensor), ("unknown", "unavailable"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: FAIL — `ImportError: cannot import name 'effective_state'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/body/jetson_presence.py`)

```python
def effective_state(
    reading: JetsonPresenceReading | None,
    *,
    received_at: float | None,
    now: float,
    stale_after: float,
) -> tuple[str, str]:
    """Return the host-authoritative (owner_present, sensor_state).

    Honesty rules, in precedence order:
      1. No reading / never received -> (unknown, unavailable).
      2. No fresh label within `stale_after` of host `received_at` -> (unknown, stale).
         Sensor silence is NEVER read as `absent`.
      3. A fresh `curtained` label outranks all other fresh states -> (unknown, curtained).
      4. Otherwise pass the fresh label through.
    `now` and `received_at` are host clock seconds; the Jetson's own ts is never used here.
    """
    if reading is None or received_at is None:
        return ("unknown", "unavailable")
    if (now - received_at) > stale_after:
        return ("unknown", "stale")
    if reading.sensor_state == "curtained":
        return ("unknown", "curtained")
    return (reading.owner_present, reading.sensor_state)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: PASS (12 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/body/jetson_presence.py tests/test_jetson_presence_contract.py
git commit -m "feat(jetson): effective_state freshness rule (stale -> unknown, never absent)"
```

---

## Task 3: The flag helper — `_jetson_presence_shadow_enabled()`

**Files:**
- Modify: `core/body/jetson_presence.py`
- Test: `tests/test_jetson_presence_contract.py`

- [ ] **Step 1: Write the failing test** (append)

```python
import os
from unittest import mock
from core.body.jetson_presence import jetson_presence_shadow_enabled


class FlagTests(unittest.TestCase):
    def test_default_off(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(jetson_presence_shadow_enabled())

    def test_on_when_truthy(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_PRESENCE_SHADOW": "1"}, clear=True):
            self.assertTrue(jetson_presence_shadow_enabled())

    def test_off_when_zero(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_PRESENCE_SHADOW": "0"}, clear=True):
            self.assertFalse(jetson_presence_shadow_enabled())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: FAIL — `ImportError: cannot import name 'jetson_presence_shadow_enabled'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/body/jetson_presence.py`)

```python
def jetson_presence_shadow_enabled() -> bool:
    """Default-off shadow flag. Behaviorally-unavailable-off: callers must skip all work when False."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_JETSON_PRESENCE_SHADOW")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract -v`
Expected: PASS (15 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/body/jetson_presence.py tests/test_jetson_presence_contract.py
git commit -m "feat(jetson): MAEZ_JETSON_PRESENCE_SHADOW default-off flag helper"
```

---

## Task 4: The store — `JetsonPresenceStore`

**Files:**
- Create: `core/body/jetson_presence_store.py`
- Test: `tests/test_jetson_presence_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_presence_store.py
import unittest
from core.body.jetson_presence import JetsonPresenceReading
from core.body.jetson_presence_store import JetsonPresenceStore


def _reading(owner_present="present", sensor_state="available"):
    return JetsonPresenceReading(owner_present, "high", sensor_state, "2026-06-29T19:00:00+00:00")


class JetsonPresenceStoreTests(unittest.TestCase):
    def test_empty_store_is_unavailable_unknown(self):
        store = JetsonPresenceStore(stale_after=180)
        self.assertEqual(store.current(now=1000.0), ("unknown", "unavailable"))

    def test_record_then_current_fresh(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(), received_at=1000.0)
        self.assertEqual(store.current(now=1010.0), ("present", "available"))

    def test_record_then_current_after_window_is_stale_unknown(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(owner_present="present"), received_at=1000.0)
        owner, sensor = store.current(now=1200.0)  # 200s later
        self.assertEqual((owner, sensor), ("unknown", "stale"))  # never "absent"

    def test_received_at_is_recorded(self):
        store = JetsonPresenceStore(stale_after=180)
        store.record(_reading(), received_at=1234.5)
        self.assertEqual(store.last_received_at, 1234.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_store -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.body.jetson_presence_store'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/body/jetson_presence_store.py
"""In-memory host store for the latest Jetson presence reading + host received_at.

Non-prompting in Slice A: nothing reads `current()` into a prompt. Host time is the
authority for staleness via jetson_presence.effective_state.
"""
from __future__ import annotations

from core.body.jetson_presence import JetsonPresenceReading, effective_state

DEFAULT_STALE_AFTER_SECONDS = 180


class JetsonPresenceStore:
    def __init__(self, *, stale_after: float = DEFAULT_STALE_AFTER_SECONDS) -> None:
        self._stale_after = stale_after
        self._reading: JetsonPresenceReading | None = None
        self._received_at: float | None = None

    def record(self, reading: JetsonPresenceReading, *, received_at: float) -> None:
        self._reading = reading
        self._received_at = received_at

    @property
    def last_received_at(self) -> float | None:
        return self._received_at

    def current(self, *, now: float) -> tuple[str, str]:
        return effective_state(
            self._reading,
            received_at=self._received_at,
            now=now,
            stale_after=self._stale_after,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_store -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/body/jetson_presence_store.py tests/test_jetson_presence_store.py
git commit -m "feat(jetson): in-memory presence store with host received_at + freshness"
```

---

## Task 5: Device-token auth — `_jetson_device_auth_ok()`

**Files:**
- Modify: `skills/web_interface.py` (add helper near `_owner_private_auth_ok`, ~line 9764)
- Test: `tests/test_jetson_presence_intake.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_presence_intake.py
import os
import unittest
from unittest import mock


class DeviceAuthTests(unittest.TestCase):
    def _auth(self, headers: dict):
        import skills.web_interface as web
        fake_req = mock.Mock()
        fake_req.headers = headers
        with mock.patch.object(web, "request", fake_req):
            return web._jetson_device_auth_ok()

    def test_correct_token_ok(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertTrue(self._auth({"X-Maez-Jetson-Token": "secret-abc"}))

    def test_wrong_token_rejected(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertFalse(self._auth({"X-Maez-Jetson-Token": "nope"}))

    def test_missing_header_rejected(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertFalse(self._auth({}))

    def test_no_token_configured_fails_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self._auth({"X-Maez-Jetson-Token": "anything"}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: FAIL — `AttributeError: module 'skills.web_interface' has no attribute '_jetson_device_auth_ok'`.

- [ ] **Step 3: Write minimal implementation** (add to `skills/web_interface.py`, near the other auth helpers ~9764)

```python
def _jetson_device_auth_ok() -> bool:
    """Authenticate a Jetson edge device by a dedicated device token.

    Separate secret from S7_INTERNAL_CHANNEL_TOKEN (owner-authority) by design.
    Fails closed when the token env is unset. Constant-time comparison.
    """
    import hmac

    configured = (os.environ.get("MAEZ_JETSON_DEVICE_TOKEN") or "").strip()
    if not configured:
        return False
    presented = (request.headers.get("X-Maez-Jetson-Token") or "").strip()
    if not presented:
        return False
    return hmac.compare_digest(configured, presented)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/web_interface.py tests/test_jetson_presence_intake.py
git commit -m "feat(jetson): device-token auth (separate from S7), fail-closed"
```

---

## Task 6: The intake endpoint + content-light receipt

**Files:**
- Modify: `skills/web_interface.py` (add the route; module-level store instance)
- Test: `tests/test_jetson_presence_intake.py`

**Note on the receipt:** a **dedicated content-light log line** — NOT `fresh_moment_receipts` (that surface means "a private thought landed"; polluting it with presence labels would corrupt the spark sequence and prematurely create its db). The line carries `schema_version`, `sensor_state`, `owner_present` (coarse buckets), a label sha, and host `received_at` — greppable for the witness, no raw content, no new persistent file.

- [ ] **Step 1: Write the failing test** (append to `tests/test_jetson_presence_intake.py`)

```python
from unittest import mock
from core.body.jetson_presence_store import JetsonPresenceStore


class IntakeEndpointTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web
        self.web = web
        self.web._JETSON_PRESENCE_STORE = JetsonPresenceStore()  # isolate store per test
        self.client = web.app.test_client()

    def _valid_body(self):
        return {
            "owner_present": "present", "confidence": "high",
            "sensor_state": "available", "ts": "2026-06-29T19:00:00+00:00",
            "schema_version": "jetson_presence.v0",
        }

    def test_flag_off_404_mutates_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake", json=self._valid_body())
                self.assertEqual(resp.status_code, 404)
                receipt.assert_not_called()
                self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable"))

    def test_bad_token_401_mutates_nothing(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "wrong"})
                self.assertEqual(resp.status_code, 401)
                receipt.assert_not_called()
                self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable"))

    def test_valid_intake_stores_and_receipts(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "secret"})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.get_json()["ok"])
                receipt.assert_called_once()
                # stored state is fresh present
                owner, sensor = self.web._JETSON_PRESENCE_STORE.current(now=resp.get_json()["received_at"] + 1)
                self.assertEqual(owner, "present")

    def test_malformed_body_is_400(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            resp = self.client.post("/api/v1/presence/jetson/intake",
                                    json={"owner_present": "maybe"},
                                    headers={"X-Maez-Jetson-Token": "secret"})
            self.assertEqual(resp.status_code, 400)

    def test_intake_does_not_touch_fresh_moment_receipts(self):
        """Covenant: presence intake must NEVER write to the private-thought surface."""
        import core.cognition.fresh_moment_receipts as fmr
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(fmr, "FreshMomentReceipts") as fake_store:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "secret"})
                self.assertEqual(resp.status_code, 200)
                fake_store.assert_not_called()  # the private-thought db is never instantiated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: FAIL — route 404 for the valid case (endpoint not defined) / `AttributeError` on `_JETSON_PRESENCE_STORE`.

- [ ] **Step 3: Write minimal implementation** (add to `skills/web_interface.py`)

```python
# --- module level, near other singletons ---
from core.body.jetson_presence import jetson_presence_shadow_enabled, parse_label
from core.body.jetson_presence_store import JetsonPresenceStore
import hashlib

_JETSON_PRESENCE_STORE = JetsonPresenceStore()


def _jetson_write_presence_receipt(reading, *, received_at: float) -> None:
    """Content-light receipt = a single log line.

    Deliberately NOT fresh_moment_receipts (that surface means 'a private thought
    landed' and must not be polluted, nor have its db created here). No persistent
    file is written. Coarse buckets + a label sha are content-light by design.
    """
    payload = f"{reading.owner_present}|{reading.confidence}|{reading.sensor_state}".encode()
    logger.info(
        "jetson_presence_intake schema=%s sensor_state=%s owner_present=%s content_sha=%s received_at=%.3f",
        "jetson_presence.v0",
        reading.sensor_state,
        reading.owner_present,
        hashlib.sha256(payload).hexdigest()[:16],
        received_at,
    )


@app.route("/api/v1/presence/jetson/intake", methods=["POST"])
def api_jetson_presence_intake():
    # Behaviorally unavailable when off: the endpoint behaves as if it does not exist.
    if not jetson_presence_shadow_enabled():
        return jsonify({"ok": False, "error": "not found"}), 404
    if not _jetson_device_auth_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    reading = parse_label(body)
    if reading is None:
        return jsonify({"ok": False, "error": "invalid label"}), 400
    received_at = time.time()  # host clock is the time authority
    _JETSON_PRESENCE_STORE.record(reading, received_at=received_at)
    _jetson_write_presence_receipt(reading, received_at=received_at)
    return jsonify({"ok": True, "received_at": received_at})
```

(If `time` / `logger` are not already imported at module top, they are — `web_interface.py` already uses both.)

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: PASS (all intake tests green — device-auth, intake/validate/store, and the `fresh_moment_receipts`-untouched guard).

- [ ] **Step 5: Commit**

```bash
git add skills/web_interface.py tests/test_jetson_presence_intake.py
git commit -m "feat(jetson): shadow intake endpoint (flag-gated, content-light log receipt)

## Predicted effect
With MAEZ_JETSON_PRESENCE_SHADOW unset, POST /api/v1/presence/jetson/intake
returns 404 and no state exists (behaviorally unavailable off). With the flag + device
token set, a valid jetson_presence.v0 label is validated, stored with host
received_at, and a content-light receipt is written. Nothing is read into any
prompt (non-prompting)."
```

---

## Task 7: Mock-emitter witness — freshness end to end

**Files:**
- Test: `tests/test_jetson_presence_intake.py` (add the witness integration test)

This proves the headline covenant property: **post a label, then go silent → the store reports `stale`/`unknown`, never `absent`.** The mock emitter is just the Flask test client posting labels.

- [ ] **Step 1: Write the failing test** (append)

```python
class FreshnessWitnessTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web
        self.web = web
        self.web._JETSON_PRESENCE_STORE = JetsonPresenceStore()  # isolate store per test
        self.client = web.app.test_client()

    def test_silence_after_present_becomes_stale_not_absent(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            body = {"owner_present": "present", "confidence": "high",
                    "sensor_state": "available", "ts": "2026-06-29T19:00:00+00:00",
                    "schema_version": "jetson_presence.v0"}
            resp = self.client.post("/api/v1/presence/jetson/intake", json=body,
                                    headers={"X-Maez-Jetson-Token": "secret"})
            received_at = resp.get_json()["received_at"]
            # Fresh read: present
            self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=received_at + 1)[0], "present")
            # Silence past the window: stale/unknown, NEVER absent
            owner, sensor = self.web._JETSON_PRESENCE_STORE.current(now=received_at + 10_000)
            self.assertEqual((owner, sensor), ("unknown", "stale"))
            self.assertNotEqual(owner, "absent")
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: PASS if Tasks 1–6 are correct (this is a characterization/witness test over existing behavior). If it FAILS, the freshness wiring is wrong — fix `effective_state`/store, not the test.

- [ ] **Step 3: (no new implementation expected — this test characterizes the covenant)**

- [ ] **Step 4: Confirm green**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_intake -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_jetson_presence_intake.py
git commit -m "test(jetson): witness — sensor silence becomes stale/unknown, never absent"
```

---

## Task 8: Full-suite regression + behaviorally-unavailable-off confirmation

**Files:** none (verification only).

- [ ] **Step 1: Run the three new modules together**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_presence_contract tests.test_jetson_presence_store tests.test_jetson_presence_intake -v`
Expected: all PASS.

- [ ] **Step 2: Confirm behaviorally-unavailable when off**

Run: `/home/rohit/maez/.venv/bin/python -B -c "import os; os.environ.pop('MAEZ_JETSON_PRESENCE_SHADOW', None); import skills.web_interface as w; c=w.app.test_client(); r=c.post('/api/v1/presence/jetson/intake', json={}); print('flag-off status', r.status_code)"`
Expected: `flag-off status 404` (route registered but inert: no label accepted, no receipt line, no persistent state).

- [ ] **Step 3: Ruff on touched files**

Run: `/home/rohit/maez/.venv/bin/ruff check core/body/jetson_presence.py core/body/jetson_presence_store.py skills/web_interface.py tests/test_jetson_presence_contract.py tests/test_jetson_presence_store.py tests/test_jetson_presence_intake.py`
Expected: `All checks passed`.

- [ ] **Step 4: Broad discover (no regressions in the asset-rich main checkout)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest discover -s tests -q 2>&1 | tail -5`
Expected: failures ⊆ the known ambient/asset-confound buckets (camera/cockpit/S7-webauthn/live-judge/external-fetch/temporal-date); zero NEW failures attributable to this slice.

- [ ] **Step 5: STOP at the review gate**

Do NOT merge, restart, or set `MAEZ_JETSON_PRESENCE_SHADOW` live. Report: branch tip, the three suites green, ruff clean, the behaviorally-unavailable-off 404, and the freshness-witness result. Hand to cross-lane covenant review (the other lane). The live witness — flag on, mock emitter posts present→silence, observe `stale`/`unknown` in the store — is the owner's after merge.

---

## Self-Review (against the spec, Slice A scope)

- **Contract (`jetson_presence.v0`):** Task 1 — fields, enums, schema_version. Wire enums exclude host-derived `stale`. ✓
- **Host-side shadow intake (receive → validate → store → receipt):** Tasks 4, 6. ✓
- **Authenticated, device token separate from S7:** Task 5 (`MAEZ_JETSON_DEVICE_TOKEN`, fail-closed, constant-time). ✓
- **Sensor-state consistency (present/absent require `available`; else `unknown` or reject):** Task 1 cross-field check + 6 combo tests. ✓
- **Freshness rail (stale → unknown, never absent; host `received_at` authority):** Tasks 2, 4, 7. ✓
- **Curtain precedence (fresh curtained outranks):** Task 2. ✓
- **Flag-gated, behaviorally unavailable when off:** Tasks 3, 6, 8. ✓
- **Content-light receipt (dedicated log line, sha not raw; NOT `fresh_moment_receipts`):** Task 6 + the `test_intake_does_not_touch_fresh_moment_receipts` guard. ✓
- **Non-prompting:** store is never read into a prompt; only `current()` in tests. ✓
- **Mock emitter (no hardware):** Task 7 via the Flask test client. ✓
- **Out of scope (correctly absent):** the Jetson device app, enrollment, the curtain teardown mechanism, the transition organ, the felt flip — all Slice B/C. ✓

**Type consistency:** `JetsonPresenceReading(owner_present, confidence, sensor_state, observed_at)`, `parse_label`, `effective_state(reading, *, received_at, now, stale_after)`, `JetsonPresenceStore(stale_after=)` / `.record(reading, *, received_at)` / `.current(now=)`, `jetson_presence_shadow_enabled`, `_jetson_device_auth_ok`, `_JETSON_PRESENCE_STORE`, `_jetson_write_presence_receipt(reading, *, received_at)` — names/signatures consistent across all tasks.
