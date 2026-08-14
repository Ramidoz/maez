# Slice C — Proposal Hygiene (time-tick → qualitative) — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags** — stop at the review gate. Builds on C1/C2/C3 (all merged). Same flag: `MAEZ_SALIENCE_BROKER_SHADOW`. **Gates steering: nothing may steer until `control_none` means "nothing notable moved."**

**Goal:** Stop `time_facts` from proposing every pulse just because the clock ticked. The broker compares `time_facts` by a **coarse qualitative percentile band**, not raw seconds — so a band crossing (climb) or reset is an event, but aging within a band is weather → genuine `control_none` baselines accrue. Also: the cold-start pulse gets its **own `cold_start` arm**, never `control_none`.

**Architecture:** A projection step in `salience_broker.py` (`time_facts` → `{percentile_band}` for change-detection only); the raw gap stays in the heartbeat prompt untouched. A `cold_start` arm in `salience_ledger.assign_arm`, threaded from the broker receipt's `cold_start` through the daemon.

**Tech Stack:** Python 3, stdlib. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** raw `owner_contact_gap_s` stays a *visible fact* in the prompt but is excluded from the change-signature; bands are **coarse** (too-fine = the tick-flood again); still shadow-only, no steering, no weights; only `time_facts` change-detection changes (other facts untouched); default-off byte-identical.

---

### Task 0: Pick coarse bands from the real distribution + confirm cold_start source (no production code)

- [ ] **Step 1: Look at the actual percentile distribution**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
from core.evolution.subjective_duration import SubjectiveDuration
rc = SubjectiveDuration().rhythm_context()
print({k: rc.get(k) for k in ('rhythm_current_gap_percentile_all_time','rhythm_all_time_gap_median_s','rhythm_recent_gap_median_s')})"
```
Pick **very coarse** band thresholds on `gap_percentile_all_time` so consecutive idle pulses (a slowly-climbing then pinned-high percentile) mostly land in the **same** band. Default to start: `ordinary < 50`, `elevated 50–75`, `unusual 75–90`, `extreme ≥ 90` — widen if Task 0 shows a typical idle stretch would still cross bands every pulse (it must not). Record the chosen thresholds. **Too-fine bands rebuild the tick-flood — bias coarse.**

- [ ] **Step 2: Confirm cold_start is available to the daemon**

The C1 broker receipt already carries `cold_start` (`broker_receipt(..., cold_start=...)`). Confirm `_maybe_run_salience_broker` returns it and `_maybe_run_lean_idle_heartbeat` can read `broker_receipt.get("cold_start")` to thread into the arm. Record the exact field.

---

### Task 1: `salience_broker.py` — project `time_facts` to a coarse band for change-detection

**Files:**
- Modify: `core/cognition/salience_broker.py`
- Test: `tests/test_salience_broker.py`

- [ ] **Step 1: Write the failing tests**

```python
from core.cognition.salience_broker import fact_signatures, propose_changes, percentile_band

def _tf(pct, gap):  # a time_facts block
    return {"time_facts": {"owner_contact_gap_s": gap, "gap_percentile_all_time": pct},
            "body_state": {}, "open_loops": {}, "recent_private_thoughts": ()}

class TimeFactsProjectionTest(unittest.TestCase):
    def test_within_band_is_no_change(self):
        # OWNER'S REQUIRED TEST: same band, different raw seconds => control_none (no proposal)
        a = fact_signatures(_tf(91, 30000))
        b = fact_signatures(_tf(93, 33000))   # both 'extreme', gap moved a lot
        self.assertEqual(propose_changes(b, a), [])

    def test_band_crossing_is_change(self):
        a = fact_signatures(_tf(60, 100))      # elevated
        b = fact_signatures(_tf(95, 200))      # extreme
        props = propose_changes(b, a)
        self.assertEqual([p.fact_key for p in props], ["time_facts"])

    def test_reset_shows_as_downward_band_change(self):
        a = fact_signatures(_tf(95, 999999))   # extreme (long absence)
        b = fact_signatures(_tf(5, 10))        # ordinary (owner came back)
        self.assertEqual([p.fact_key for p in propose_changes(b, a)], ["time_facts"])

    def test_raw_gap_excluded_from_time_signature(self):
        a = fact_signatures(_tf(95, 100))
        b = fact_signatures(_tf(95, 999999))   # same band, wildly different seconds
        self.assertEqual(a["time_facts"], b["time_facts"])   # raw seconds do not drive it

    def test_percentile_band_coarse_labels(self):
        self.assertEqual(percentile_band(10), "ordinary")
        self.assertEqual(percentile_band(95), "extreme")
        self.assertEqual(percentile_band(None), "unknown")

    def test_other_facts_unchanged(self):
        # body_state still change-detects on raw value
        a = fact_signatures({"time_facts": {}, "body_state": {"watchdog": "ok"}, "open_loops": {}, "recent_private_thoughts": ()})
        b = fact_signatures({"time_facts": {}, "body_state": {"watchdog": "stale"}, "open_loops": {}, "recent_private_thoughts": ()})
        self.assertEqual([p.fact_key for p in propose_changes(b, a)], ["body_state"])
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_salience_broker -k "band or projection or within_band or excluded" -v` → FAIL.

- [ ] **Step 3: Implement the projection (change-detection only)**

```python
# coarse percentile bands (Task 0 may widen these); too-fine = tick-flood
_BAND_ORDINARY_MAX = 50.0
_BAND_ELEVATED_MAX = 75.0
_BAND_UNUSUAL_MAX = 90.0


def percentile_band(percentile: object) -> str:
    if percentile is None:
        return "unknown"
    try:
        value = float(percentile)
    except (TypeError, ValueError):
        return "unknown"
    if value < _BAND_ORDINARY_MAX:
        return "ordinary"
    if value < _BAND_ELEVATED_MAX:
        return "elevated"
    if value < _BAND_UNUSUAL_MAX:
        return "unusual"
    return "extreme"


def _project_for_salience(key: str, value: object) -> object:
    # time_facts changes only when its QUALITATIVE band changes; raw seconds are weather.
    # (The raw gap still renders in the heartbeat prompt — this affects ONLY the broker signature.)
    if key == "time_facts" and isinstance(value, Mapping):
        return {"percentile_band": percentile_band(value.get("gap_percentile_all_time"))}
    return value
```
And route `fact_signatures` through it:
```python
def fact_signatures(facts: Mapping[str, object]) -> dict[str, str]:
    window = facts or {}
    return {key: _signature(_project_for_salience(key, window.get(key))) for key in WATCHED_KEYS}
```

- [ ] **Step 4: Run to verify they pass** — same → PASS. (Confirm the heartbeat **prompt** is untouched: `build_lean_idle_prompt` still renders raw `owner_contact_gap_s` — no test should change there.)

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_broker.py tests/test_salience_broker.py
git commit -m "feat(nervous-system): time_facts change-detects on coarse band, not raw seconds"
```

---

### Task 2: `salience_ledger.assign_arm` — cold_start its own arm

**Files:**
- Modify: `core/cognition/salience_ledger.py`
- Test: `tests/test_salience_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_cold_start_gets_own_arm_not_control_none(self):
    arm, rows = assign_arm([], pulse_signature="s", cold_start=True)
    self.assertEqual(arm, "cold_start")
    self.assertEqual(list(rows), [{"fact_key": "none", "change_kind": "none"}])

def test_empty_without_cold_start_is_control_none(self):
    arm, _ = assign_arm([], pulse_signature="s", cold_start=False)
    self.assertEqual(arm, "control_none")

def test_change_still_proposed_or_withheld(self):
    arm, _ = assign_arm([{"fact_key": "time_facts", "change_kind": "changed"}], pulse_signature="s", cold_start=False)
    self.assertIn(arm, ("proposed", "control_withheld"))
```

- [ ] **Step 2: Run to verify they fail** — `... -k "cold_start or control_none" -v` → FAIL (`cold_start` kwarg unknown).

- [ ] **Step 3: Implement**

```python
def assign_arm(
    proposals: "list[dict] | None",
    pulse_signature: str,
    *,
    cold_start: bool = False,
) -> "tuple[str, tuple[dict, ...]]":
    sentinel = ({"fact_key": "none", "change_kind": "none"},)
    if cold_start:                       # no baseline yet => 'unknown', never a quiet day
        return "cold_start", sentinel
    if not proposals:
        return "control_none", sentinel
    digest = int(hashlib.sha256(str(pulse_signature).encode("utf-8")).hexdigest(), 16)
    arm = "control_withheld" if digest % WITHHOLD_EVERY == 0 else "proposed"
    rows = tuple({"fact_key": str(p.get("fact_key", "")), "change_kind": str(p.get("change_kind", ""))}
                 for p in proposals)
    return arm, rows
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_ledger.py
git commit -m "feat(nervous-system): cold-start gets its own arm, never control_none"
```

---

### Task 3: Daemon — thread `cold_start` into the arm

**Files:**
- Modify: `daemon/maez_daemon.py` (`_record_salience_outcomes` + its call site)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_cold_start_pulse_records_cold_start_arm(self):
    import os, tempfile, pathlib
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    from core.cognition.salience_ledger import SalienceLedger
    daemon = object.__new__(MaezDaemon)
    daemon._salience_pending = None; daemon._salience_pulse_seq = 0
    daemon._salience_ledger = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    ok = {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"}
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False):
        # pulse 1: cold-start (no proposals, cold_start=True)
        daemon._record_salience_outcomes([], ok, strategy="changed_since_last", pulse_signature="s1", cold_start=True)
        # pulse 2: resolves pulse 1
        daemon._record_salience_outcomes([], ok, strategy="changed_since_last", pulse_signature="s2", cold_start=False)
    rows = daemon._salience_ledger.recent(5)
    self.assertEqual(rows[0]["arm"], "cold_start")
    self.assertEqual(rows[0]["fact_key"], "none")
```
(Update the C2/C3 daemon tests to pass `cold_start=False` to `_record_salience_outcomes`.)

- [ ] **Step 2: Run to verify it fails** — `... -k cold_start_pulse -v` → FAIL.

- [ ] **Step 3: Thread cold_start**

Extend the signature and the `assign_arm` call:
```python
def _record_salience_outcomes(self, proposals, heartbeat_outcome, *, strategy, pulse_signature, cold_start=False):
    if not _salience_broker_shadow_enabled():
        return None
    from core.cognition.salience_ledger import derive_outcome, assign_arm
    self._salience_pulse_seq = int(getattr(self, "_salience_pulse_seq", 0)) + 1
    pulse_id = f"seq{self._salience_pulse_seq}"
    arm, rows = assign_arm(list(proposals or []), pulse_signature, cold_start=bool(cold_start))
    current = {"pulse_id": pulse_id, "strategy": str(strategy or "changed_since_last"),
               "arm": arm, "rows": [dict(r) for r in rows], "outcome": dict(heartbeat_outcome or {})}
    # ... unchanged: resolve prior over [N, N+1], record rows, fail-soft ...
```
At the call site, read `cold_start` from the broker receipt and pass it through:
```python
    if broker_active:
        broker_receipt = self._maybe_run_salience_broker(window)
        cold_start = bool((broker_receipt or {}).get("cold_start", False))
        # ... existing proposals/strategy/pulse_signature ...
        self._record_salience_outcomes(proposals, hb_outcome, strategy=strategy,
                                       pulse_signature=pulse_signature, cold_start=cold_start)
```

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Full suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_broker tests.test_salience_ledger tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_broker.py core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_broker.py tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
```
Expected: green; ruff clean.

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): proposal hygiene — qualitative time + cold_start arm

## Predicted effect
time_facts now proposes only on a coarse percentile-band crossing (climb or reset),
not every pulse. During a settled idle stretch the band holds, so the broker
proposes nothing and the ledger accrues genuine control_none baselines. The
cold-start pulse is tagged arm=cold_start, never control_none. The raw gap still
renders in the heartbeat prompt. Shadow-only, no steering, default-off byte-identical."
```

---

### Task 4: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-slice-c-proposal-hygiene-handoff.md`**

Record: Task 0 band thresholds + why; the cold_start threading; branch tip; full test + ruff output; the witness sequence (**merge → owner restart → confirm: a settled idle stretch now logs `control_none` rows (band held); a band crossing logs `proposed`; the first pulse logs `arm=cold_start`; raw gap still visible in the heartbeat prompt**). State plainly: NOT merged, NOT restarted, NO flags. **Note the deferred contact_state question** (reset is captured as a downward band transition; an explicit reset marker can be added if the owner wants resets tagged distinctly in the ledger).

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-proposal-hygiene-handoff.md
git commit -m "docs(nervous-system): hand off proposal hygiene"
```
Hand back to Claude for covenant review (within-band→control_none; raw gap excluded from signature but kept in prompt; coarse bands; cold_start its own arm; other facts unchanged; shadow-only; default-off byte-identical). **After this is witnessed, the baseline is usable — and only then does the steering gate (eval-immune + welfare/off-ramp) open.**

---

## Self-Review

**Spec coverage:** time_facts compares projected band not raw seconds (Task 1 ✓); raw gap excluded from signature but kept in prompt (`test_raw_gap_excluded` + prompt untouched ✓); coarse bands from real distribution (Task 0 + `percentile_band` ✓); **owner's required within-band→control_none test** (`test_within_band_is_no_change` ✓); reset = downward band transition (`test_reset_shows_as_downward_band_change` ✓); cold_start its own arm never control_none (Task 2 + Task 3 ✓); other facts unchanged (`test_other_facts_unchanged` ✓); shadow-only/default-off (inherited + flag-guard ✓).

**Placeholder scan:** band thresholds are concrete defaults explicitly subject to Task 0 widening (with the coarse-bias rule). No TBDs.

**Type consistency:** `percentile_band(p) -> str`, `_project_for_salience(key, value)`, `fact_signatures` unchanged signature. `assign_arm(proposals, pulse_signature, *, cold_start=False)` matches Task 2 (def) and Task 3 (call). `_record_salience_outcomes(..., *, strategy, pulse_signature, cold_start=False)` matches the updated call site and the updated C2/C3 tests.
