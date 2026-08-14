# Restart-Safe Pulse Identity — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD. **Do NOT merge, restart, or flip flags.** This is **ledger hygiene with no behavior change** — the witness is that two runs cannot share a `pulse_id`, that legacy rows are preserved untouched, and that the gate/report readers are unaffected.

**Goal:** Make `pulse_id` globally unique and restart-safe (`r<ms>_<pid>.seqN`) so two daemon runs can never share a notebook page number — without rewriting history or changing any cognition/voice/routing/steering behavior.

**Tech Stack:** Python 3, stdlib (`sqlite3`, `time`, `os`). Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** `pulse_id` stays `TEXT`; schema unchanged; legacy `seqN` rows are **never migrated or rewritten**; `gate_report`/`evaluate_gate` are **not touched** (verified `pulse_id`-agnostic); the broker stays shadow + the gate read-only.

---

### Task 0: Confirm imports + the construction site + legacy-row tolerance (no production code)

- [ ] **Step 1: Confirm `time`/`os` are importable in the daemon + pin the two edit sites**

```
cd /home/rohit/maez
grep -nE "^import os|^import time|^import os,|^import time," daemon/maez_daemon.py | head
sed -n '3457,3461p' daemon/maez_daemon.py     # the _salience_pulse_seq = 0 init
sed -n '5162,5168p' daemon/maez_daemon.py     # the from ... import + the seq/pulse_id mint
```
Confirm `time` and `os` are already imported at module top (they are used widely). Record the exact indentation of both sites. If either `time` or `os` is missing at top, add the import in Task 2 alongside the change.

- [ ] **Step 2: Confirm `gate_report` ignores `pulse_id` (reader compat baseline)**

```
sed -n '223,245p' core/cognition/salience_gate.py
```
Confirm the `SELECT` does not include `pulse_id` and there is no `GROUP BY`/`DISTINCT`. (Already verified in the spec — this is the build-lane re-confirmation.)

---

### Task 1: The two pure id helpers + their unit tests

**Files:**
- Modify: `core/cognition/salience_ledger.py`
- Test: `tests/test_salience_pulse_identity.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from core.cognition.salience_ledger import new_run_id, make_pulse_id

class PulseIdentityTest(unittest.TestCase):
    def test_namespacing_two_runs_cannot_collide(self):
        a = new_run_id(now_ms=1000, pid=100)
        b = new_run_id(now_ms=2000, pid=200)
        self.assertNotEqual(a, b)
        ids_a = {make_pulse_id(a, s) for s in range(1, 51)}
        ids_b = {make_pulse_id(b, s) for s in range(1, 51)}
        self.assertEqual(len(ids_a), 50)
        self.assertEqual(ids_a & ids_b, set())            # disjoint -> no collision

    def test_same_second_different_pid_is_distinct(self):
        self.assertNotEqual(new_run_id(now_ms=1000, pid=100),
                            new_run_id(now_ms=1000, pid=200))

    def test_within_run_stable_prefix_monotonic_seq(self):
        run = new_run_id(now_ms=1234, pid=42)
        self.assertEqual(make_pulse_id(run, 1), f"{run}.seq1")
        self.assertEqual(make_pulse_id(run, 7), f"{run}.seq7")
        self.assertTrue(make_pulse_id(run, 1).startswith(run))
        self.assertTrue(make_pulse_id(run, 2).startswith(run))

    def test_run_id_shape(self):
        self.assertEqual(new_run_id(now_ms=1000, pid=100), "r1000_100")

    # --- the binding string must follow the page number (owner watch-item) ---
    def test_proposal_hash_binds_full_pulse_id(self):
        from core.cognition.salience_ledger import make_proposal_hash
        run_a = new_run_id(now_ms=1000, pid=100)
        run_b = new_run_id(now_ms=2000, pid=200)
        fields = dict(strategy="changed_since_last", arm="proposed",
                      fact_key="f", change_kind="changed")
        h_a = make_proposal_hash(pulse_id=make_pulse_id(run_a, 1), **fields)
        h_b = make_proposal_hash(pulse_id=make_pulse_id(run_b, 1), **fields)
        self.assertNotEqual(h_a, h_b)        # same seq+fields, different run -> different hash
        self.assertEqual(h_a, make_proposal_hash(pulse_id=make_pulse_id(run_a, 1), **fields))  # deterministic
        self.assertNotEqual(h_a, make_proposal_hash(pulse_id="seq1", **fields))  # not bound to bare seqN
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_salience_pulse_identity -v` → FAIL (`ImportError: cannot import name 'new_run_id'`).

- [ ] **Step 3: Add the helpers** (top-level functions in `core/cognition/salience_ledger.py`, near `assign_arm`; ensure `import json` and `import hashlib` are present at module top — `hashlib` already is, add `json` if absent):

```python
def new_run_id(*, now_ms: int, pid: int) -> str:
    """Process-stable, restart-distinct run identity for pulse_ids.

    now_ms = process start time in ms; pid = os.getpid(). A pid is never reused
    while its process lives, and a restart yields a strictly-later start time, so
    (now_ms, pid) is unique per run. Injectable args keep this deterministically
    testable; the daemon captures real values once per process.
    """
    return f"r{int(now_ms)}_{int(pid)}"


def make_pulse_id(run_id: str, seq: int) -> str:
    """Compose a globally-unique pulse page number: run identity + per-run seq."""
    return f"{run_id}.seq{int(seq)}"


def make_proposal_hash(
    *, pulse_id: str, strategy: str, arm: str, fact_key: str, change_kind: str
) -> str:
    """Bind a proposal row to its FULL pulse_id (not a bare seq or local counter).

    Byte-identical to the daemon's prior inline computation for the same inputs —
    only the pulse_id argument now carries the run stamp. Extracted so the binding
    is tested + cannot silently regress to seqN.
    """
    return hashlib.sha256(
        json.dumps(
            {
                "pulse_id": str(pulse_id),
                "strategy": str(strategy),
                "arm": str(arm),
                "fact_key": str(fact_key),
                "change_kind": str(change_kind),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
```

- [ ] **Step 4: Run to verify they pass** — same command → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_pulse_identity.py
git commit -m "feat(salience): restart-safe pulse identity helpers

Add new_run_id + make_pulse_id + make_proposal_hash: a per-run identity
(start-ms + pid) composed with the per-run seq, so two daemon runs cannot share
a pulse_id, and the proposal_hash binds to the full pulse_id (tested, cannot
regress to bare seqN). Pure + injectable for deterministic 'two restarts cannot
collide' tests. No wiring yet."
```

---

### Task 2: Wire the daemon + end-to-end no-collision + legacy-coexistence tests

**Files:**
- Modify: `daemon/maez_daemon.py` (the `__init__` seq site + the pulse-mint method)
- Test: `tests/test_salience_pulse_identity.py` (extend)

- [ ] **Step 1: Write the failing end-to-end + legacy tests** (append to the test module)

```python
import tempfile, os
from pathlib import Path
from core.cognition.salience_ledger import SalienceLedger, make_pulse_id, new_run_id

class PulseLedgerNoCollisionTest(unittest.TestCase):
    def _seed(self, ledger, pulse_id):
        ledger.record(
            pulse_id=pulse_id, strategy="changed_since_last", arm="proposed",
            fact_key="f", change_kind="changed", proposal_hash="h",
            outcome={"thought_formed": False, "non_duplicate_stored": False,
                     "repetition_signal": "not_applicable", "unmoved": True})

    def test_two_runs_write_distinct_pulse_ids(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = SalienceLedger(Path(d) / "s.db")
            run_a = new_run_id(now_ms=1000, pid=100)
            run_b = new_run_id(now_ms=2000, pid=200)
            for s in range(1, 6): self._seed(ledger, make_pulse_id(run_a, s))
            for s in range(1, 6): self._seed(ledger, make_pulse_id(run_b, s))
            import sqlite3
            conn = sqlite3.connect(Path(d) / "s.db")
            distinct = conn.execute("SELECT COUNT(DISTINCT pulse_id) FROM salience_ledger").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM salience_ledger").fetchone()[0]
            conn.close()
            self.assertEqual(total, 10)
            self.assertEqual(distinct, 10)        # zero collisions across two runs

    def test_gate_report_handles_legacy_and_new_rows(self):
        from core.cognition.salience_gate import gate_report
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.db"
            ledger = SalienceLedger(path)
            self._seed(ledger, "seq1")                                   # legacy format
            self._seed(ledger, make_pulse_id(new_run_id(now_ms=1000, pid=100), 1))  # new format
            report = gate_report(ledger_path=path)                       # must not crash / dedup
            self.assertIsInstance(report, dict)
```

- [ ] **Step 2: Run to verify the relevant test fails / baseline** — `... -m unittest tests.test_salience_pulse_identity -v`. The two new tests should PASS already at the helper/ledger level (they exercise helpers + the unchanged record/read path) — they are the **regression guard** for the wiring. If `gate_report`'s signature differs from `gate_report(ledger_path=...)`, adjust the call to the real signature (Task 0 Step 2 confirmed it); do not weaken the assertion.

- [ ] **Step 3: Wire the daemon**

In `__init__`, beside the seq init ([~3459](../../../daemon/maez_daemon.py)):
```python
        self._salience_pulse_seq = 0
        self._salience_run_id = None        # captured once on first pulse (process-stable)
```
In the pulse-mint method, replace the import + seq/pulse_id lines ([~5164-5167](../../../daemon/maez_daemon.py)):
```python
        from core.cognition.salience_ledger import (
            assign_arm, derive_outcome, make_proposal_hash, make_pulse_id, new_run_id,
        )

        if self._salience_run_id is None:
            self._salience_run_id = new_run_id(
                now_ms=int(time.time() * 1000), pid=os.getpid()
            )
        self._salience_pulse_seq = int(getattr(self, "_salience_pulse_seq", 0)) + 1
        pulse_id = make_pulse_id(self._salience_run_id, self._salience_pulse_seq)
```
(If Task 0 found `time` or `os` not imported at module top, add the import there.)

In the same method, replace the **inline** `proposal_hash` computation ([~5190-5201](../../../daemon/maez_daemon.py)) with the helper call (output byte-identical for the same inputs — the only change is that `prior["pulse_id"]` now carries the run stamp):
```python
                    proposal_hash = make_proposal_hash(
                        pulse_id=prior["pulse_id"],
                        strategy=prior_strategy,
                        arm=prior_arm,
                        fact_key=fact_key,
                        change_kind=change_kind,
                    )
```
Leave the rest of the method — pairing, `ledger.record`, the receipt — byte-unchanged. **Verify** the helper reproduces the prior hash for a known input (e.g. a quick REPL check with the old inline JSON) so legacy-shaped hashes are unaffected; only the `pulse_id` input differs by design.

- [ ] **Step 4: Run the focused suite + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_pulse_identity tests.test_salience_ledger tests.test_salience_gate -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_ledger.py daemon/maez_daemon.py tests/test_salience_pulse_identity.py
```
Expected: green; ruff clean. (Use the real salience test module names from `ls tests/ | grep salience` if they differ.)

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_salience_pulse_identity.py
git commit -m "fix(salience): mint restart-safe pulse_ids in the idle loop

Capture a per-process run-id once (start-ms + pid) and compose pulse_id as
run_id.seqN, so two daemon restarts can no longer reuse seq1/seq2/... The
proposal_hash (which embeds pulse_id) becomes unique per pulse. Legacy seqN
rows are left untouched; gate/report ignore pulse_id and are unaffected.

## Predicted effect
New idle-loop ledger rows carry pulse_ids of the form r<ms>_<pid>.seqN with
correspondingly-unique proposal_hashes; legacy seqN rows still read; gate/report
verdicts are identical (pulse_id-agnostic). No cognition/voice/routing/steering
change."
```

---

### Task 3: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-27-pulse-id-restart-safe-handoff.md`**

Record: Task 0 findings (imports present; `gate_report` `pulse_id`-agnostic confirmed); branch tip; full focused-suite + ruff output; the before/after pulse_id format (`seqN` → `r<ms>_<pid>.seqN`); explicit statements that **legacy rows were not migrated** and **no reader was changed**. Witness sequence for the owner/Claude post-merge: **merge → restart → confirm the next idle-loop row's `pulse_id` matches `r<ms>_<pid>.seqN`, a second restart yields a different `r<ms>_<pid>` prefix, and `gate_report` still returns its verdict over the mixed-format ledger.** State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-27-pulse-id-restart-safe-handoff.md
git commit -m "docs(salience): hand off restart-safe pulse identity"
```
Hand back to Claude for covenant review (helpers pure + namespacing disjoint; daemon captures run-id once/process; legacy rows untouched; `gate_report` handles mixed formats; no schema/reader/behavior change). Then the owner witnesses across two restarts.

---

## Self-Review

**Spec coverage:** process-stable + restart-safe identity (Task 1 helpers + Task 2 wiring ✓); preserve old rows without rewrite (no migration anywhere; legacy-coexistence test ✓); tests that two restarts cannot collide (namespacing + end-to-end DISTINCT-count tests ✓); **proposal_hash binds the full pulse_id, not bare seqN — extracted `make_proposal_hash` + `test_proposal_hash_binds_full_pulse_id` (owner watch-item, now locked) ✓**; gate/report readers handle legacy rows (Task 0 re-confirm + `test_gate_report_handles_legacy_and_new_rows` ✓); no steering/behavior change (pure id-format change, output-preserving hash extraction, broker stays shadow, gate untouched ✓).

**Placeholder scan:** the real salience test module names + the exact `gate_report` signature are Task 0/Step-4 confirmations (explicit, not TBD). No invented logic.

**Type consistency:** `new_run_id(*, now_ms, pid) -> str` and `make_pulse_id(run_id, seq) -> str` are used identically in the helpers, the daemon, and every test; `pulse_id` stays `TEXT`; `_salience_run_id` initialized to `None` and set once.
