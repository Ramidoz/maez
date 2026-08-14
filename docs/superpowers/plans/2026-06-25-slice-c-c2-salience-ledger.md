# Slice C — C2 Private-Loop-Only Salience Ledger — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags** — stop at the review gate. Builds on C0.5 (locked reader) + C1 (shadow broker), both merged. Gated by the **same** flag as C1: `MAEZ_SALIENCE_BROKER_SHADOW`.

**Goal:** For each C1 proposal, record the idle loop's *own* later outcome over `[N, N+1]` — `thought_formed` / `non_duplicate_stored` / `repetition_signal` / `unmoved` (neutral) — bound to the concrete proposal, in a content-light append-only ledger. A notebook of correlation, not a judge; owner-reaction and open-loop-resolution are **structurally unreadable**.

**Architecture:** A pure `derive_outcome(...)` (idle-loop signals → the four outcome fields) and a `SalienceLedger` SQLite store, both in `core/cognition/salience_ledger.py`. The daemon keeps the *prior* pulse's proposals + heartbeat outcome in memory, and on the next pulse resolves them over `[N, N+1]` and appends rows.

**Tech Stack:** Python 3, stdlib `sqlite3`. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** outcomes from the idle loop only; `unmoved` is **neutral/unknown**, never failure; `repetition_signal` only on a real dup signal else `not_applicable`; `evolved_earlier_wondering` deferred to C2.1; content-light (hashes, never raw thought/prompt/fact text); every row binds to a concrete proposal (`pulse_id`/`strategy`/`fact_key`/`change_kind`); the verdict function **cannot** read owner-reaction / open-loop-resolution / fixation-score / contradiction / daemon-wide signals; shadow-only; default-off byte-identical.

---

### Task 0: Confirm the heartbeat outcome fields (no production code)

- [ ] **Step 1: Confirm the `LeanIdleResult` + receipt fields C2 reads**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, core.cognition.lean_idle_heartbeat as h
print([f.name for f in __import__('dataclasses').fields(h.LeanIdleResult)])
print(inspect.getsource(h._base_receipt))" | head -40
```
Confirm the per-pulse idle-loop outcome signals available to the daemon: `note_chars`, `stored`, `skip_reason` (and `output_chars`). Record their exact source (the `LeanIdleResult` and/or its `receipt` dict). These four are the **only** inputs `derive_outcome` may take.

---

### Task 1: `derive_outcome` — pure idle-loop outcome (the verdict, structurally isolated)

**Files:**
- Create: `core/cognition/salience_ledger.py` (this task: the pure function + the outcome dataclass)
- Test: `tests/test_salience_ledger.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from core.cognition.salience_ledger import derive_outcome, LEDGER_VERSION

def _hb(*, note_chars=0, stored=False, skip_reason="heartbeat_ok_or_rejected"):
    return {"note_chars": note_chars, "stored": stored, "skip_reason": skip_reason}

class DeriveOutcomeTest(unittest.TestCase):
    def test_unmoved_is_neutral_across_window(self):
        out = derive_outcome([_hb(), _hb()])   # HEARTBEAT_OK at N and N+1
        self.assertTrue(out["unmoved"])
        self.assertFalse(out["thought_formed"])
        self.assertFalse(out["non_duplicate_stored"])
        self.assertEqual(out["repetition_signal"], "not_applicable")  # no signal => not a claim

    def test_non_duplicate_stored(self):
        out = derive_outcome([_hb(), _hb(note_chars=80, stored=True, skip_reason="none")])
        self.assertTrue(out["thought_formed"])
        self.assertTrue(out["non_duplicate_stored"])
        self.assertFalse(out["unmoved"])

    def test_candidate_formed_but_duplicate_rejected(self):
        out = derive_outcome([_hb(note_chars=80, stored=False, skip_reason="duplicate_recent_output"), _hb()])
        self.assertTrue(out["thought_formed"])           # a candidate formed
        self.assertFalse(out["non_duplicate_stored"])    # but did not store
        self.assertEqual(out["repetition_signal"], "duplicate")
        self.assertFalse(out["unmoved"])

    def test_window_takes_best_across_N_and_N1(self):
        # immediate quiet, delayed store => stored wins
        out = derive_outcome([_hb(), _hb(note_chars=50, stored=True, skip_reason="none")])
        self.assertTrue(out["non_duplicate_stored"])

    def test_derive_outcome_only_consumes_idle_loop_fields(self):
        # passing excluded signals must be IGNORED (structural isolation)
        poisoned = {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected",
                    "owner_replied": True, "open_loop_resolved": True, "fixation_score": 99}
        out = derive_outcome([poisoned, poisoned])
        self.assertTrue(out["unmoved"])                  # excluded fields changed nothing
```

- [ ] **Step 2: Run to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_salience_ledger -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `derive_outcome` (and the module header)**

```python
"""Slice C / C2 — private-loop-only salience ledger.

A notebook of correlation, not a judge. Outcomes are derived ONLY from the idle
loop's own per-pulse signals; `unmoved` is neutral (maybe restraint), never failure.
`evolved_earlier_wondering` is deferred to C2.1 (needs real stored thoughts).
"""
from __future__ import annotations

import sqlite3

LEDGER_VERSION = "salience_ledger.v0"

# The ONLY idle-loop signals the verdict may read. Anything else is ignored.
_OUTCOME_INPUT_KEYS = ("note_chars", "stored", "skip_reason")


def _pulse_signal(result: dict) -> dict:
    r = result or {}
    return {
        "note_chars": int(r.get("note_chars") or 0),
        "stored": bool(r.get("stored")),
        "skip_reason": str(r.get("skip_reason") or ""),
    }


def derive_outcome(window_results: "list[dict]") -> dict:
    """Resolve the idle loop's outcome over [N, N+1]. Neutral by default."""
    signals = [_pulse_signal(r) for r in (window_results or [])]
    thought_formed = any(s["note_chars"] > 0 for s in signals)
    non_duplicate_stored = any(s["stored"] for s in signals)
    duplicate = any(s["skip_reason"] == "duplicate_recent_output" for s in signals)
    unmoved = not thought_formed and not non_duplicate_stored
    return {
        "thought_formed": thought_formed,
        "non_duplicate_stored": non_duplicate_stored,
        "repetition_signal": "duplicate" if duplicate else "not_applicable",
        "unmoved": unmoved,   # NEUTRAL: "nothing private changed afterward", not "useless"
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_ledger.py
git commit -m "feat(nervous-system): C2 derive_outcome — idle-loop-only, neutral unmoved"
```

---

### Task 2: `SalienceLedger` store — content-light, proposal-bound rows

**Files:**
- Modify: `core/cognition/salience_ledger.py` (add the store)
- Test: `tests/test_salience_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
import tempfile, pathlib
from core.cognition.salience_ledger import SalienceLedger, derive_outcome

class SalienceLedgerStoreTest(unittest.TestCase):
    def _ledger(self):
        return SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "ledger.db")

    def test_row_binds_to_concrete_proposal(self):
        led = self._ledger()
        outcome = derive_outcome([{"note_chars": 80, "stored": True, "skip_reason": "none"}])
        led.record(pulse_id="p1", strategy="changed_since_last", fact_key="time_facts",
                   change_kind="changed", proposal_hash="abc123", outcome=outcome)
        rows = led.recent(limit=5)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["pulse_id"], r["strategy"], r["fact_key"], r["change_kind"]),
                         ("p1", "changed_since_last", "time_facts", "changed"))
        self.assertTrue(r["non_duplicate_stored"])

    def test_store_is_content_light(self):
        led = self._ledger()
        outcome = derive_outcome([{"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"}])
        led.record(pulse_id="p2", strategy="changed_since_last", fact_key="recent_private_thoughts",
                   change_kind="appeared", proposal_hash="deadbeef", outcome=outcome)
        # the schema must have NO column for raw thought/prompt/fact text
        cols = led.column_names()
        for forbidden in ("content", "thought", "prompt", "raw_text", "fact_value"):
            self.assertNotIn(forbidden, cols)
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_salience_ledger -k Store -v` → FAIL.

- [ ] **Step 3: Implement the store**

```python
class SalienceLedger:
    def __init__(self, db_path):
        from pathlib import Path
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS salience_ledger (
                    row_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    pulse_id             TEXT NOT NULL,
                    strategy             TEXT NOT NULL,
                    fact_key             TEXT NOT NULL,
                    change_kind          TEXT NOT NULL,
                    proposal_hash        TEXT NOT NULL,
                    thought_formed       INTEGER NOT NULL,
                    non_duplicate_stored INTEGER NOT NULL,
                    repetition_signal    TEXT NOT NULL,
                    unmoved              INTEGER NOT NULL,
                    schema_version       TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def record(self, *, pulse_id, strategy, fact_key, change_kind, proposal_hash, outcome) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO salience_ledger
                   (pulse_id, strategy, fact_key, change_kind, proposal_hash,
                    thought_formed, non_duplicate_stored, repetition_signal, unmoved, schema_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (str(pulse_id), str(strategy), str(fact_key), str(change_kind), str(proposal_hash),
                 int(bool(outcome["thought_formed"])), int(bool(outcome["non_duplicate_stored"])),
                 str(outcome["repetition_signal"]), int(bool(outcome["unmoved"])), LEDGER_VERSION),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, limit: int = 20) -> "list[dict]":
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM salience_ledger ORDER BY row_id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def column_names(self) -> "list[str]":
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM salience_ledger LIMIT 0")
            return [d[0] for d in cur.description]
        finally:
            conn.close()
```

- [ ] **Step 4: Run to verify they pass** — same as Step 2 → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_ledger.py
git commit -m "feat(nervous-system): C2 content-light proposal-bound ledger store"
```

---

### Task 3: Daemon wiring — capture, hold prior pulse, resolve over [N, N+1]

**Files:**
- Modify: `daemon/maez_daemon.py` (extend `_maybe_run_lean_idle_heartbeat`; add `_record_salience_outcomes`; init `_salience_pending`, `_salience_pulse_seq`, lazy `_salience_ledger`)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_salience_ledger_resolves_over_two_pulses(self):
    import os, tempfile, pathlib
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    from core.cognition.salience_ledger import SalienceLedger
    daemon = object.__new__(MaezDaemon)
    daemon._salience_pending = None
    daemon._salience_pulse_seq = 0
    daemon._salience_ledger = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    # pulse N: a proposal + HEARTBEAT_OK outcome
    props_n = [{"fact_key": "time_facts", "change_kind": "changed"}]
    # pulse N+1: a stored thought outcome
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False):
        daemon._record_salience_outcomes(props_n, {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"})
        daemon._record_salience_outcomes([], {"note_chars": 80, "stored": True, "skip_reason": "none"})
    rows = daemon._salience_ledger.recent(limit=5)
    self.assertEqual(len(rows), 1)                      # proposal from N resolved at N+1
    self.assertEqual(rows[0]["fact_key"], "time_facts")
    self.assertTrue(rows[0]["non_duplicate_stored"])   # [N,N+1] saw the stored thought

def test_salience_off_records_nothing(self):
    import os, tempfile, pathlib
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    from core.cognition.salience_ledger import SalienceLedger
    daemon = object.__new__(MaezDaemon)
    daemon._salience_pending = None; daemon._salience_pulse_seq = 0
    daemon._salience_ledger = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": ""}, clear=False):
        self.assertIsNone(daemon._record_salience_outcomes([{"fact_key": "x", "change_kind": "changed"}], {"note_chars": 0}))
    self.assertEqual(daemon._salience_ledger.recent(), [])
```

- [ ] **Step 2: Run to verify they fail** — `... -k salience -v` → FAIL.

- [ ] **Step 3: Implement the wiring**

Add `_record_salience_outcomes`, holding only the prior pulse and resolving over `[N, N+1]`:
```python
def _record_salience_outcomes(self, proposals: list, heartbeat_outcome: dict):
    if not _salience_broker_shadow_enabled():
        return None
    from core.cognition.salience_ledger import derive_outcome
    import hashlib, json
    self._salience_pulse_seq = int(getattr(self, "_salience_pulse_seq", 0)) + 1
    pulse_id = f"seq{self._salience_pulse_seq}"
    prior = getattr(self, "_salience_pending", None)
    # resolve the PRIOR pulse's proposals over [prior, current]
    if prior is not None:
        outcome = derive_outcome([prior["outcome"], heartbeat_outcome])
        ledger = getattr(self, "_salience_ledger", None)
        if ledger is not None:
            for p in prior["proposals"]:
                phash = hashlib.sha256(
                    json.dumps([prior["pulse_id"], p["fact_key"], p["change_kind"]], sort_keys=True).encode()
                ).hexdigest()[:16]
                ledger.record(pulse_id=prior["pulse_id"], strategy="changed_since_last",
                              fact_key=p["fact_key"], change_kind=p["change_kind"],
                              proposal_hash=phash, outcome=outcome)
    # current pulse becomes the new pending
    self._salience_pending = {"pulse_id": pulse_id, "proposals": list(proposals or []),
                              "outcome": dict(heartbeat_outcome or {})}
    return pulse_id
```
Then, in `_maybe_run_lean_idle_heartbeat`, after the broker runs and the heartbeat result is known, capture the outcome and call it (only when `broker_active`):
```python
    if broker_active:
        broker_receipt = self._maybe_run_salience_broker(window)
        proposals = (broker_receipt or {}).get("proposals", []) if broker_receipt else []
    ...
    # after the heartbeat `result` is computed (or, if heartbeat inactive, a HEARTBEAT_OK-shaped blank):
    if broker_active:
        hb_outcome = {
            "note_chars": int((getattr(result, "receipt", {}) or {}).get("note_chars", 0)) if hb_active else 0,
            "stored": bool(getattr(result, "stored", False)) if hb_active else False,
            "skip_reason": str(getattr(result, "skip_reason", "heartbeat_ok_or_rejected")) if hb_active else "heartbeat_ok_or_rejected",
        }
        self._record_salience_outcomes(proposals, hb_outcome)
```
Initialize `self._salience_pending = None`, `self._salience_pulse_seq = 0`, and a lazily-constructed `self._salience_ledger = SalienceLedger(<memory dir>/salience_ledger.db)` where the daemon builds its other idle state. (Task 0 / existing patterns confirm the memory dir, e.g. alongside `private_thoughts.db`.)

- [ ] **Step 4: Run to verify they pass** — same as Step 2 → PASS.

- [ ] **Step 5: Full suites + ruff + structural-exclusion confirmation**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_ledger tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
```
Expected: green; ruff clean. Confirm the ledger schema has **no** column for owner-reaction, open-loop-resolution, fixation, contradiction, or raw text (`test_store_is_content_light` + `test_derive_outcome_only_consumes_idle_loop_fields` together prove the structural isolation).

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): wire the private-loop-only salience ledger

## Predicted effect
With MAEZ_SALIENCE_BROKER_SHADOW=1, each broker proposal is recorded against the
idle loop's own outcome over [N, N+1] (thought_formed / non_duplicate_stored /
repetition_signal / unmoved-neutral). Owner reaction, open-loop resolution,
fixation, and contradiction are structurally unreadable. Today the ledger will be
sparse and dominated by neutral 'unmoved' rows. Default-off stays byte-identical."
```

---

### Task 4: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-slice-c-c2-salience-ledger-handoff.md`**

Record: Task 0 outcome-field decision; the `[N, N+1]` pending/resolve mechanism + `pulse_id` scheme; branch tip; full test + ruff output; the witness sequence (**merge → owner restart with `MAEZ_SALIENCE_BROKER_SHADOW=1` → confirm a `salience_ledger.db` accrues content-light rows bound to proposals; today they are almost all `unmoved` (neutral); no owner/open-loop/fixation/contradiction columns exist**). State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-c2-salience-ledger-handoff.md
git commit -m "docs(nervous-system): hand off C2 salience ledger"
```
Hand back to Claude for covenant review (idle-loop-only verdict; neutral unmoved; repetition only on a real signal; evolved deferred; proposal-bound rows; structural exclusion of owner-reaction/open-loop/fixation/contradiction; content-light; shadow-only; default-off byte-identical). **C3 does not begin until C2 is merged + witnessed.**

---

## Self-Review

**Spec coverage:** outcomes over `[N, N+1]` (Task 1 `derive_outcome` window + Task 3 pending/resolve ✓); the four v0 outcomes with **neutral** unmoved (Task 1 tests ✓); `repetition_signal` only on a real dup else `not_applicable` (✓); `evolved_earlier_wondering` deferred (module docstring + not implemented ✓); row binds to a concrete proposal `pulse_id/strategy/fact_key/change_kind` + hash (Task 2 ✓); verdict reads only idle-loop fields (`_OUTCOME_INPUT_KEYS` + `test_derive_outcome_only_consumes_idle_loop_fields` ✓); excluded signals have no column + can't be read (`test_store_is_content_light` ✓); shadow-only + default-off byte-identical (Task 3 `test_salience_off_records_nothing` ✓); same flag as C1 (✓).

**Placeholder scan:** the `_maybe_run_lean_idle_heartbeat` insertion is described against the C1 structure (the `broker_active` block already exists from C1); the heartbeat-inactive branch yields a HEARTBEAT_OK-shaped blank so the ledger never fabricates a thought from a missing heartbeat. No TBDs.

**Type consistency:** `derive_outcome(window_results) -> {thought_formed, non_duplicate_stored, repetition_signal, unmoved}` identical across Task 1/2/3. `SalienceLedger.record(pulse_id, strategy, fact_key, change_kind, proposal_hash, outcome)` identical in Task 2 (def) and Task 3 (call). Proposal dicts use `fact_key`/`change_kind` exactly as C1's `broker_receipt` emits them.
