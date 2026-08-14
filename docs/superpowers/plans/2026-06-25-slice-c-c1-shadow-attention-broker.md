# Slice C — C1 Shadow Attention Broker — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags** — stop at the review gate. Builds on C0.5 (the locked source-scoped reader, already merged).

**Goal:** A shadow broker that, each idle pulse, observes **only which window facts changed since the last pulse** and logs a content-light proposal — a motion detector, never a taste-maker. No importance claims, no steering, no stored thoughts.

**Architecture:** Pure change-detection in a new `core/cognition/salience_broker.py` (content-light per-fact signatures → `changed`/`appeared`/`cleared` deltas, cold-start proposes nothing). The daemon builds the window facts once, runs the broker (own flag) and the heartbeat independently, and keeps an in-memory baseline across pulses.

**Tech Stack:** Python 3, stdlib. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** observation not judgment (no "important/unusual/deserves/matters"); cold-start proposes nothing; content-light deltas only (`fact_key`, `change_kind`, `strategy`, hashes — never raw thought text, raw prompt, raw fact values, or owner-reaction); shadow-only; default-off byte-identical; no steering.

---

### Task 0: Confirm the wiring site (no production code)

**Files:** none; record in the Task 3 handoff.

- [ ] **Step 1: Read `_maybe_run_lean_idle_heartbeat` and the four fact adapters**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, daemon.maez_daemon as d
print(inspect.getsource(d.MaezDaemon._maybe_run_lean_idle_heartbeat))"
```
Confirm: the four adapters (`_lean_idle_time_facts`, `_lean_idle_body_state`, `_lean_idle_open_loops`, `_lean_idle_recent_private_thoughts`) are called inside the `LeanIdleFacts(...)` construction, gated by `_lean_idle_heartbeat_any_enabled()` + `_lean_idle_heartbeat_eligible(gate_decision)`. Record the exact lines so Task 2 can build the window dict once and pass it to both the broker and `LeanIdleFacts`.

---

### Task 1: `core/cognition/salience_broker.py` — pure change detection

**Files:**
- Create: `core/cognition/salience_broker.py`
- Test: `tests/test_salience_broker.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from core.cognition.salience_broker import (
    fact_signatures, propose_changes, broker_receipt,
    BROKER_VERSION, STRATEGY, WATCHED_KEYS,
)

class SalienceBrokerTest(unittest.TestCase):
    def _facts(self, **over):
        base = {"time_facts": {"owner_contact_gap_s": 30}, "body_state": {"watchdog": "ok"},
                "open_loops": {"open_loop_count": 0}, "recent_private_thoughts": ()}
        base.update(over); return base

    def test_cold_start_proposes_nothing(self):
        cur = fact_signatures(self._facts())
        self.assertEqual(propose_changes(cur, None), [])   # baseline None => silence

    def test_changed_fact_is_proposed_as_observation(self):
        base = fact_signatures(self._facts(time_facts={"owner_contact_gap_s": 30}))
        cur = fact_signatures(self._facts(time_facts={"owner_contact_gap_s": 999}))
        props = propose_changes(cur, base)
        self.assertEqual([(p.fact_key, p.change_kind) for p in props], [("time_facts", "changed")])
        self.assertTrue(all(p.strategy == STRATEGY for p in props))

    def test_thought_appearing_and_clearing(self):
        empty = fact_signatures(self._facts(recent_private_thoughts=()))
        present = fact_signatures(self._facts(recent_private_thoughts=("a note",)))
        self.assertEqual([(p.fact_key, p.change_kind) for p in propose_changes(present, empty)],
                         [("recent_private_thoughts", "appeared")])
        self.assertEqual([(p.fact_key, p.change_kind) for p in propose_changes(empty, present)],
                         [("recent_private_thoughts", "cleared")])

    def test_unchanged_window_proposes_nothing(self):
        sig = fact_signatures(self._facts())
        self.assertEqual(propose_changes(sig, sig), [])

    def test_signatures_are_content_light(self):
        # raw values must NOT appear in signatures (hash or "empty" only)
        sigs = fact_signatures(self._facts(recent_private_thoughts=("SECRET THOUGHT",)))
        self.assertNotIn("SECRET", "".join(sigs.values()))

    def test_receipt_is_content_light_and_makes_no_importance_claim(self):
        base = fact_signatures(self._facts())
        cur = fact_signatures(self._facts(body_state={"watchdog": "stale"}))
        r = broker_receipt(propose_changes(cur, base), cold_start=False)
        blob = str(r).lower()
        for forbidden in ("important", "unusual", "deserves", "matters", "should", "secret"):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(r["strategy"], STRATEGY)
        self.assertEqual(r["proposals"], [{"fact_key": "body_state", "change_kind": "changed"}])
```

- [ ] **Step 2: Run to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_salience_broker -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the module**

```python
"""Slice C / C1 — shadow attention broker (motion detector, not taste-maker).

Observes ONLY which window facts changed since the last pulse, as observations
('changed' / 'appeared' / 'cleared'), never as importance claims. Content-light:
signatures are hashes or the literal 'empty', never raw values.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json

BROKER_VERSION = "salience_broker.v0"
STRATEGY = "changed_since_last"
WATCHED_KEYS = ("time_facts", "body_state", "open_loops", "recent_private_thoughts")


@dataclass(frozen=True)
class Proposal:
    fact_key: str
    change_kind: str        # "changed" | "appeared" | "cleared" — observations only
    strategy: str = STRATEGY


def _sig(value: object) -> str:
    if value is None or value == {} or value == () or value == []:
        return "empty"
    canon = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def fact_signatures(facts: Mapping[str, object]) -> dict[str, str]:
    return {key: _sig((facts or {}).get(key)) for key in WATCHED_KEYS}


def _change_kind(base_sig: str, cur_sig: str) -> str:
    if base_sig == "empty" and cur_sig != "empty":
        return "appeared"
    if base_sig != "empty" and cur_sig == "empty":
        return "cleared"
    return "changed"


def propose_changes(
    current_sigs: Mapping[str, str],
    baseline_sigs: "Mapping[str, str] | None",
) -> list[Proposal]:
    if baseline_sigs is None:           # cold-start guardrail: silence, not fake change
        return []
    out: list[Proposal] = []
    for key in WATCHED_KEYS:
        cur = current_sigs.get(key, "empty")
        base = baseline_sigs.get(key, "empty")
        if cur != base:
            out.append(Proposal(fact_key=key, change_kind=_change_kind(base, cur)))
    return out


def broker_receipt(proposals: "list[Proposal]", *, cold_start: bool) -> dict:
    return {
        "schema_version": BROKER_VERSION,
        "strategy": STRATEGY,
        "cold_start": bool(cold_start),
        "watched_keys": list(WATCHED_KEYS),
        "proposals": [{"fact_key": p.fact_key, "change_kind": p.change_kind} for p in proposals],
        "proposal_count": len(proposals),
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_broker.py tests/test_salience_broker.py
git commit -m "feat(nervous-system): C1 change-detection broker — observations, not judgments"
```

---

### Task 2: Daemon wiring — own flag, shared window, in-memory baseline

**Files:**
- Modify: `daemon/maez_daemon.py` (flag helper + `_maybe_run_salience_broker`; refactor `_maybe_run_lean_idle_heartbeat` to build the window once and run both organs)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_broker_cold_start_then_change(self):
    import os
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    daemon = object.__new__(MaezDaemon)
    daemon._salience_broker_baseline = None
    receipts = []
    daemon._log_salience_receipt = lambda r: receipts.append(r)  # test seam if used; else patch logger
    window1 = {"time_facts": {"owner_contact_gap_s": 30}, "body_state": {}, "open_loops": {}, "recent_private_thoughts": ()}
    window2 = {"time_facts": {"owner_contact_gap_s": 999}, "body_state": {}, "open_loops": {}, "recent_private_thoughts": ()}
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False):
        r1 = daemon._maybe_run_salience_broker(window1)   # cold-start
        r2 = daemon._maybe_run_salience_broker(window2)   # change
    self.assertTrue(r1["cold_start"]); self.assertEqual(r1["proposal_count"], 0)
    self.assertFalse(r2["cold_start"])
    self.assertEqual(r2["proposals"], [{"fact_key": "time_facts", "change_kind": "changed"}])

def test_broker_off_is_noop(self):
    import os
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    daemon = object.__new__(MaezDaemon); daemon._salience_broker_baseline = None
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": ""}, clear=False):
        self.assertIsNone(daemon._maybe_run_salience_broker({"time_facts": {"x": 1}}))

def test_heartbeat_path_default_off_still_byte_identical(self):
    # both heartbeat + broker flags off => early return, no fact-building, no broker
    import os
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    daemon = object.__new__(MaezDaemon)
    touched = {"n": 0}
    for name in ("_lean_idle_time_facts", "_lean_idle_body_state", "_lean_idle_open_loops",
                 "_lean_idle_recent_private_thoughts", "_maybe_run_salience_broker"):
        setattr(daemon, name, lambda *a, **k: touched.__setitem__("n", touched["n"]+1) or {})
    gate = type("G", (), {"doorman_enabled": True, "reason_code": "wake_min_floor"})()
    with mock.patch.dict(os.environ, {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "", "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "",
                                      "MAEZ_SALIENCE_BROKER_SHADOW": ""}, clear=False):
        self.assertIsNone(daemon._maybe_run_lean_idle_heartbeat({}, gate))
    self.assertEqual(touched["n"], 0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_daemon -k "broker or byte_identical" -v`
Expected: FAIL (method/flag missing).

- [ ] **Step 3: Add the flag helper + broker method, and refactor the heartbeat path**

Flag helper (beside the other `_lean_idle_heartbeat_*` helpers):
```python
def _salience_broker_shadow_enabled(environ: object | None = None) -> bool:
    return _env_flag("MAEZ_SALIENCE_BROKER_SHADOW", environ=environ)
```
Broker method (on `MaezDaemon`):
```python
def _maybe_run_salience_broker(self, window: dict) -> dict | None:
    if not _salience_broker_shadow_enabled():
        return None
    from core.cognition.salience_broker import (
        fact_signatures, propose_changes, broker_receipt,
    )
    baseline = getattr(self, "_salience_broker_baseline", None)
    sigs = fact_signatures(window)
    proposals = propose_changes(sigs, baseline)
    receipt = broker_receipt(proposals, cold_start=baseline is None)
    self._salience_broker_baseline = sigs
    logger.info("salience_broker receipt=%s", json.dumps(receipt))
    return receipt
```
Refactor `_maybe_run_lean_idle_heartbeat` so the window is built once and both organs run independently (preserve byte-identical when both off):
```python
def _maybe_run_lean_idle_heartbeat(self, snap, gate_decision):
    hb_active = _lean_idle_heartbeat_any_enabled()
    broker_active = _salience_broker_shadow_enabled()
    if not hb_active and not broker_active:
        return None
    if not _lean_idle_heartbeat_eligible(gate_decision):
        return None
    window = {
        "time_facts": self._lean_idle_time_facts(),
        "body_state": self._lean_idle_body_state(),
        "open_loops": self._lean_idle_open_loops(),
        "recent_private_thoughts": self._lean_idle_recent_private_thoughts(),
    }
    if broker_active:
        self._maybe_run_salience_broker(window)
    if not hb_active:
        return None
    # ... existing heartbeat run, now passing the prebuilt window into LeanIdleFacts:
    #     time_facts=window["time_facts"], body_state=window["body_state"],
    #     open_loops=window["open_loops"], recent_private_thoughts=window["recent_private_thoughts"]
```
(Initialize `self._salience_broker_baseline = None` where the daemon initializes its other idle state, so a fresh process honestly cold-starts.)

- [ ] **Step 4: Run to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Full protected suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_broker.py daemon/maez_daemon.py \
  tests/test_salience_broker.py tests/test_lean_idle_daemon.py
```
Expected: all green; ruff clean. Confirm the heartbeat's own receipts/behavior are unchanged when `MAEZ_SALIENCE_BROKER_SHADOW` is unset.

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): wire the shadow attention broker onto the idle pulse

## Predicted effect
With MAEZ_SALIENCE_BROKER_SHADOW=1, each wake_min_floor pulse logs a content-light
salience_broker receipt naming which window facts changed since the last pulse
(cold-start proposes nothing). No prompt change, no stored thoughts, no importance
claim. Default-off (and broker-off) stays byte-identical to the current heartbeat."
```

---

### Task 3: Handoff + STOP

**Files:**
- Create: `docs/handoffs/2026-06-25-slice-c-c1-shadow-attention-broker-handoff.md`

- [ ] **Step 1: Write the handoff**

Record: Task 0 wiring site; branch tip; full test + ruff output; the witness sequence (**merge → owner restart with `MAEZ_SALIENCE_BROKER_SHADOW=1` → confirm: first pulse logs `cold_start=true, proposal_count=0`; later pulses log content-light `changed/appeared/cleared` proposals; no importance language; no prompt/behavior change**). State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-c1-shadow-attention-broker-handoff.md
git commit -m "docs(nervous-system): hand off C1 shadow attention broker"
```
Hand back to Claude for covenant review (observation-not-judgment; cold-start silence; content-light deltas; shadow-only; default-off byte-identical; no steering; no owner-reaction). **C2 does not begin until C1 is merged + witnessed.**

---

## Self-Review

**Spec coverage:** one strategy `changed_since_last` (Task 1 ✓); observation not judgment — `change_kind ∈ {changed,appeared,cleared}`, no importance words, enforced by `test_receipt_..._no_importance_claim` (✓); cold-start proposes nothing (Task 1 `propose_changes(_, None)` + Task 2 cold-start test ✓); content-light deltas only — signatures are hash/"empty", receipt carries `fact_key`/`change_kind`/`strategy`, `test_signatures_are_content_light` (✓); time-ticks flow undeclared (no special-case for `time_facts` ✓); flag-gated shadow-only default-off byte-identical (Task 2 `test_broker_off_is_noop` + `test_..._byte_identical` ✓); no steering/stored thoughts (broker only logs ✓). All C1 spec points map to a task.

**Placeholder scan:** the `_log_salience_receipt` test seam in Task 2 §1 is illustrative — if the implementation logs directly via `logger`, the test patches `daemon.maez_daemon.logger` / asserts the returned receipt dict instead (the method returns the receipt, so tests assert on the return value — no seam needed). No TBDs.

**Type consistency:** `Proposal(fact_key, change_kind, strategy)`, `fact_signatures`, `propose_changes`, `broker_receipt`, `BROKER_VERSION`/`STRATEGY`/`WATCHED_KEYS` names identical across Task 1 (def) and Task 2 (call). `window` dict keys match `WATCHED_KEYS` exactly and match the `LeanIdleFacts` field names.
