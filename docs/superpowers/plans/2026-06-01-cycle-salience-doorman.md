# Cycle Salience Doorman (deterministic v1) — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** A deterministic, model-free doorman that decides "wake the deep brain?" from sourced signals *before* `_reason`, replacing the perception-only gate. Salience triggers; presence never gates; fail-open on any uncertainty. Flag-off keeps today's behavior.

**Lane:** Codex implements, Claude cross-verifies, Rohit owner-witnesses. Flag `MAEZ_CYCLE_DOORMAN_ENABLED` off by default.

**Spec:** `docs/superpowers/specs/2026-06-01-cycle-salience-doorman-design.md`

---

## Seam (verified)

- `core/cognition/perception_signature.py`: `DEFAULT_MIN_THOUGHT_FLOOR = 10`; `extract_axes(snap, git_dirty_count=...)` (carries a `presence` axis — **exclude from wake**); `signature_from_axes`; `should_skip_reasoning(current_signature, last_thought_signature, cycles_since_last_thought, min_thought_floor=...)`; `stale_fields`.
- The live gate: `daemon/maez_daemon.py:7216-7252` (`perception_signature_gate` stage → `should_skip_reasoning` → skip sets `result=None` + `self._cycles_since_last_thought += 1`; else → `reasoning_model` / `_reason`).
- Cheap salience signals (booleans/counts, NOT full evidence): new failures (`action_outcome`), open wants (`open_loop`), memory delta, signal-availability transition, scheduled maintenance due. (The full evidence is the cycle packet's job *after* wake; the doorman reads cheap presence/count signals only.)

---

## Task 1: `core/cognition/cycle_doorman.py` — the deterministic decider

**Files:** create `core/cognition/cycle_doorman.py`; test `tests/test_cycle_doorman.py`.

- [ ] **Step 1: Write the load-bearing tests FIRST**

```python
# tests/test_cycle_doorman.py
import unittest
from core.cognition.cycle_doorman import decide, DoormanSignals, ReasonCode

def _quiet():  # well-formed, nothing salient, floor not due
    return DoormanSignals(
        perception_changed=False, new_failures=0, open_wants=0,
        memory_delta=False, signal_availability_changed=False,
        scheduled_due=False, quiet_skips=0, min_floor=10, presence="active")

class DoormanTest(unittest.TestCase):
    # --- LOAD-BEARING RAIL: never skip a genuinely salient cycle ---
    def test_every_salient_signal_wakes(self):
        for field, code in [
            ("perception_changed", ReasonCode.WAKE_PERCEPTION_CHANGED),
            ("memory_delta", ReasonCode.WAKE_MEMORY_DELTA),
            ("signal_availability_changed", ReasonCode.WAKE_SIGNAL_AVAILABILITY_CHANGED),
            ("scheduled_due", ReasonCode.WAKE_SCHEDULED),
        ]:
            s = _quiet(); object.__setattr__(s, field, True)
            v = decide(s)
            self.assertTrue(v.wake, f"{field} must wake")
        for field, code in [("new_failures", ReasonCode.WAKE_NEW_FAILURE),
                             ("open_wants", ReasonCode.WAKE_OPEN_WANT)]:
            s = _quiet(); object.__setattr__(s, field, 1)
            self.assertTrue(decide(s).wake, f"{field} must wake")

    # --- FAIL-OPEN: any uncertainty/error -> wake, never skip ---
    def test_fail_open_on_none_bundle(self):
        v = decide(None)
        self.assertTrue(v.wake); self.assertEqual(v.reason_code, ReasonCode.WAKE_FAIL_OPEN)
    def test_fail_open_on_malformed(self):
        v = decide(object())   # not a DoormanSignals
        self.assertTrue(v.wake); self.assertEqual(v.reason_code, ReasonCode.WAKE_FAIL_OPEN)

    # --- PRESENCE NEVER GATES ---
    def test_presence_absent_does_not_change_salient_wake(self):
        s = _quiet(); object.__setattr__(s, "new_failures", 1)
        s.presence = "active";  a = decide(s)
        s.presence = "absent";  b = decide(s)
        self.assertEqual((a.wake, a.reason_code), (b.wake, b.reason_code))
    def test_presence_alone_never_wakes(self):
        s = _quiet(); s.presence = "absent"     # only presence differs from active
        self.assertFalse(decide(s).wake)        # presence is not a wake term

    # --- SKIP only on explicit well-formed nothing ---
    def test_quiet_below_floor_skips(self):
        v = decide(_quiet())
        self.assertFalse(v.wake)
        self.assertIn(v.reason_code, (ReasonCode.SKIP_NOTHING_SALIENT, ReasonCode.SKIP_UNCHANGED))

    # --- FLOOR is a periodic probe, not a latch ---
    def test_floor_wakes_once_then_resets(self):
        s = _quiet(); object.__setattr__(s, "quiet_skips", 10)   # == min_floor
        v = decide(s)
        self.assertTrue(v.wake); self.assertEqual(v.reason_code, ReasonCode.WAKE_MIN_FLOOR)
        # caller resets quiet_skips to 0 after a floor wake; next quiet cycle skips again
        s2 = _quiet(); object.__setattr__(s2, "quiet_skips", 0)
        self.assertFalse(decide(s2).wake)

    # --- signal-availability is a TRANSITION, not steady state ---
    def test_steady_absence_does_not_repeat_wake(self):
        # availability_changed reflects a TRANSITION; steady (False) does not wake
        s = _quiet(); object.__setattr__(s, "signal_availability_changed", False)
        self.assertFalse(decide(s).wake)
```

- [ ] **Step 2:** Run → FAIL (module absent).
- [ ] **Step 3: Implement** `cycle_doorman.py`:
  - `class ReasonCode(str, Enum)`: the closed `WAKE_*` / `SKIP_*` set incl. `WAKE_FAIL_OPEN`, `WAKE_MIN_FLOOR`, `WAKE_SIGNAL_AVAILABILITY_CHANGED`, `SKIP_NOTHING_SALIENT`, `SKIP_UNCHANGED`.
  - `@dataclass class DoormanSignals`: the cheap fields above (presence is carried for *telemetry only*, **never read in the wake logic**).
  - `def decide(signals) -> DoormanVerdict(wake: bool, reason_code: ReasonCode, signals_present: tuple)`:
    - **Fail-open first:** `if not isinstance(signals, DoormanSignals): return DoormanVerdict(True, WAKE_FAIL_OPEN, ())`. Wrap the whole body in `try/except → WAKE_FAIL_OPEN`.
    - Evaluate salience terms **in priority order**, return the first wake; **presence is never read.** `new_failures>0 → WAKE_NEW_FAILURE`; `open_wants>0 → WAKE_OPEN_WANT`; `memory_delta → WAKE_MEMORY_DELTA`; `signal_availability_changed → WAKE_SIGNAL_AVAILABILITY_CHANGED`; `perception_changed → WAKE_PERCEPTION_CHANGED`; `scheduled_due → WAKE_SCHEDULED`; `quiet_skips >= min_floor → WAKE_MIN_FLOOR`.
    - Else `wake=False`, `SKIP_NOTHING_SALIENT` (or `SKIP_UNCHANGED` if only-perception-stable).
    - `signals_present` = the closed tuple of which classes fired (content-free).
- [ ] **Step 4:** Run → PASS (iterate until every rail green). Commit `feat(cycle): deterministic salience doorman (fail-open, presence-excluded)`.

---

## Task 2: Wire into the cycle gate behind the flag + fix the floor counter

**Files:** `daemon/maez_daemon.py` (`:7216-7252`); telemetry helper.

- [ ] **Step 1: Test (daemon seam):** flag off → existing `should_skip_reasoning` path unchanged; flag on → `decide()` drives the gate; `wake=False` → content-free `doorman_skip` + **`_reason` NOT called** (assert via a patched `_reason`); `wake=True` → `_reason` proceeds; `doorman_verdict` telemetry content-free.
- [ ] **Step 2: Implement** at the gate:
  - Read `MAEZ_CYCLE_DOORMAN_ENABLED`. **Off → unchanged** (`should_skip_reasoning` only).
  - **On →** assemble `DoormanSignals` from the cheap cycle signals (failures/wants/memory-delta/availability-transition/scheduled-due/`quiet_skips`=the floor counter/perception_changed from `current_sig != last_sig`/presence for telemetry). Call `decide(...)`.
    - `wake=False` → log content-free `doorman_skip` (`reason_code`) + `doorman_verdict` telemetry; `result=None`; **increment `quiet_skips`**.
    - `wake=True` → `doorman_verdict` telemetry; proceed to `reasoning_model`/`_reason`.
  - **Floor-counter fix (the latch bug):** track **`quiet_skips` = cycles since last *wake opportunity*** (not since last stored thought). On a **floor wake** whose `_reason` returns `HEARTBEAT_OK` (nothing), **reset `quiet_skips=0`** so it does NOT wake every subsequent cycle. On any real stored thought, also reset. (Keeps the periodic-probe semantics from spec §2.)
- [ ] **Step 3:** `doorman_verdict` telemetry helper — content-free: `wake` (bool), `reason_code`, `signals_present` (closed tuple), `quiet_skips` (int). No thought/memory text. Assert the field set in a test.
- [ ] **Step 4:** Run daemon-seam + doorman tests → PASS. Commit `feat(cycle): flag-gated doorman in cycle gate + periodic floor counter`.

---

## Task 3: Regression + owner-run acceptance

- [ ] **Step 1:** Full perception_signature + cycle suites green (no regression to the existing gate when flag off).
- [ ] **Step 2:** Floor both directions on a clean checkout (NOT git stash); known-unrelated trio excluded by name.
- [ ] **Step 3: Acceptance note (owner-run):** `docs/slices/cycle-doorman/acceptance.md` — with `MAEZ_CYCLE_DOORMAN_ENABLED=1`: read `doorman_verdict` over real cycles → **skip rate up** (fewer deep calls / GPU duty down), reason-code distribution sane, **every genuinely-salient moment still woke** (no missed failure/want/memory/availability), floor still probes periodically (Maez not gone silent), presence never suppressed a salient wake. Any miss → flag off (legacy gate is the resting state).

---

## Self-Review

- **Covenant mechanical, not just intended:** presence is carried for telemetry but **never read** in `decide()` (asserted by `test_presence_alone_never_wakes`); fail-open is the default on any error/malformed/unknown (asserted); the floor is a periodic probe with an explicit reset (asserted no-latch).
- **The dangerous failure is false-skip** — covered by the exhaustive per-signal wake test + fail-open; skip only on explicit well-formed nothing.
- **Extends, doesn't replace recklessly:** flag-off is the exact current `should_skip_reasoning` behavior; the doorman is purely additive behind the flag.
- **Organ boundary clean:** `decide(DoormanSignals) -> DoormanVerdict` is the interface a future i9/LFM2.5 evidence-classifier implements behind its own flag, scored against this deterministic baseline.
