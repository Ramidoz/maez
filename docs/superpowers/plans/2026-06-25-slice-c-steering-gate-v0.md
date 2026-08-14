# Slice C — Steering Gate v0 — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags.** **HARD RULE: this builds the lock, not the door — NO steering path, NO daemon wiring, read-only over the ledger. On-demand diagnostic only.**

**Goal:** A read-only `salience_gate_eval` over `salience_ledger.db` that computes the **pre-registered** countable checks and emits a content-light gate report with a `gate_state` on the ladder `NO_GO / BASELINE_ONLY / CANARY_ALLOWED / CANARY_BLOCKED` (no `FULL_GO`). Plus a read-only `welfare_baseline` snapshot captured now in shadow, the human witness checklist, and the off-ramp requirements. **Nothing steers; nothing writes to the ledger; the daemon is untouched.**

**Architecture:** A standalone `core/cognition/salience_gate.py` (locked thresholds + pure stats + `evaluate_gate` + `welfare_baseline`). Run on-demand (a function / small script), never on a schedule, never from the cycle loop.

**Tech Stack:** Python 3, stdlib (`math`, `sqlite3`, `collections`). Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** read-only; content-light (counts/codes/thresholds, never raw thought/prompt/fact text); pre-registered thresholds are constants marked `PRE_REGISTERED` (change only by documented amendment); no steering, no daemon wiring, no schedule; the eval is true-by-construction (a verdict we can't argue with).

---

### Task 0: Confirm ledger fields + welfare seams (no production code)

- [ ] **Step 1: Confirm the ledger columns the eval reads**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import sqlite3; from core.cognition.salience_ledger import SalienceLedger
c=sqlite3.connect(SalienceLedger.__init__.__doc__ and 'memory/salience_ledger.db' or 'memory/salience_ledger.db')
print([r[1] for r in c.execute('PRAGMA table_info(salience_ledger)').fetchall()])"
```
Confirm: `arm`, `fact_key`, `thought_formed`, `non_duplicate_stored`, `repetition_signal`, `unmoved`. A **coherent outcome** = `thought_formed OR non_duplicate_stored`.

- [ ] **Step 2: Confirm welfare-baseline seams (read-only)**

Confirm: `private_thoughts.count()` + a fixation/repetition proxy (recent `duplicate_recent_output` rate or `derived_signals`); `_operator_health()['backup_freshness_class']`; `_watchdog_health()`. Record exact keys (these feed `welfare_baseline`, content-light).

---

### Task 1: `salience_gate.py` — locked thresholds + pure stats + `evaluate_gate`

**Files:**
- Create: `core/cognition/salience_gate.py`
- Test: `tests/test_salience_gate.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from core.cognition.salience_gate import (
    evaluate_gate, two_proportion_z,
    MIN_ROWS, MIN_PROPOSED_ARM, MIN_CONTROL_NONE, MIN_WITHHELD, MIN_COHERENT,
    MIN_LIFT, MIN_LIFT_Z, MAX_PLACEBO_DELTA, MAX_FACT_SHARE,
)

def _row(arm, fact="time_facts", coherent=False):
    return {"arm": arm, "fact_key": fact if arm in ("proposed", "control_withheld") else "none",
            "thought_formed": int(coherent), "non_duplicate_stored": int(coherent),
            "repetition_signal": "not_applicable", "unmoved": int(not coherent)}

class GateThresholdsTest(unittest.TestCase):
    def test_locked_threshold_values(self):
        # PRE-REGISTERED — these must not drift without a documented amendment
        self.assertEqual(
            (MIN_ROWS, MIN_PROPOSED_ARM, MIN_CONTROL_NONE, MIN_WITHHELD, MIN_COHERENT,
             MIN_LIFT, MIN_LIFT_Z, MAX_PLACEBO_DELTA, MAX_FACT_SHARE),
            (500, 100, 100, 20, 20, 0.05, 1.96, 0.05, 0.80))

    def test_today_small_ledger_is_baseline_only(self):
        rows = [_row("proposed")]*6 + [_row("control_none")]*2 + [_row("cold_start")]
        rep = evaluate_gate(rows, welfare={"backup_freshness": "unavailable"})
        self.assertEqual(rep["gate_state"], "BASELINE_ONLY")    # not enough data → keep gathering
        self.assertIn("insufficient_sample", rep["failing_codes"])

    def test_enough_data_no_lift_is_no_go(self):
        # adequate samples, but proposed coherence == control_none coherence → no_lift
        rows = ([_row("proposed", coherent=(i < 10)) for i in range(120)]      # 10/120 coherent
                + [_row("control_none", coherent=(i < 10)) for i in range(120)] # 10/120 coherent
                + [_row("control_withheld") for _ in range(25)])
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertEqual(rep["gate_state"], "NO_GO")
        self.assertIn("no_lift", rep["failing_codes"])

    def test_monoculture_fires(self):
        rows = ([_row("proposed", fact="time_facts") for _ in range(120)]
                + [_row("control_none") for _ in range(120)]
                + [_row("control_withheld") for _ in range(25)])
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertIn("monoculture", rep["failing_codes"])      # 100% time_facts

    def test_instrumentation_effect_fires(self):
        # withheld coherence diverges from proposed → placebo broke
        rows = ([_row("proposed", coherent=(i < 40)) for i in range(120)]        # ~0.33
                + [_row("control_none", coherent=(i < 5)) for i in range(120)]
                + [_row("control_withheld", coherent=False) for _ in range(25)])  # 0.0 vs 0.33
        rep = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertIn("instrumentation_effect", rep["failing_codes"])

    def test_clean_pass_but_backup_blocks_canary(self):
        # diverse, lift present, placebo matches, big sample → eval passes, but no backup
        rows = ([_row("proposed", fact=("time_facts" if i%2 else "body_state"), coherent=(i < 60)) for i in range(160)]
                + [_row("control_none", coherent=(i < 10)) for i in range(160)]
                + [_row("control_withheld", coherent=(i < 9)) for i in range(25)])
        blocked = evaluate_gate(rows, welfare={"backup_freshness": "unavailable"})
        allowed = evaluate_gate(rows, welfare={"backup_freshness": "fresh"})
        self.assertEqual(blocked["gate_state"], "CANARY_BLOCKED")
        self.assertEqual(allowed["gate_state"], "CANARY_ALLOWED")

    def test_report_is_content_light(self):
        rep = evaluate_gate([_row("proposed")], welfare={"backup_freshness": "fresh"})
        blob = str(rep).lower()
        for forbidden in ("thought", "prompt", "secret", "raw"):
            self.assertNotIn(forbidden, blob)

    def test_z_test_basic(self):
        self.assertAlmostEqual(two_proportion_z(0, 100, 0, 100), 0.0, places=3)
        self.assertGreater(two_proportion_z(60, 100, 10, 100), 1.96)
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_salience_gate -v` → FAIL (module missing).

- [ ] **Step 3: Implement the module**

```python
"""Slice C — Steering Gate v0. Read-only. The LOCK, not the door.

Pre-registered, code-enforced eval over the salience ledger. No steering, no
daemon wiring. The thresholds are an immune-system commitment: change ONLY by a
documented amendment whose rationale is committed before the gate is re-run.
"""
from __future__ import annotations

import collections
import math

GATE_VERSION = "salience_gate.v0"

# PRE_REGISTERED 2026-06-25 — do not edit without a documented amendment.
MIN_ROWS = 500
MIN_PROPOSED_ARM = 100
MIN_CONTROL_NONE = 100
MIN_WITHHELD = 20
MIN_COHERENT = 20
MIN_LIFT = 0.05
MIN_LIFT_Z = 1.96
MAX_PLACEBO_DELTA = 0.05
MAX_FACT_SHARE = 0.80

_SAMPLE_CODES = ("insufficient_sample", "sparse_signal")     # -> BASELINE_ONLY
_SIGNAL_CODES = ("no_lift", "instrumentation_effect", "monoculture", "fixation_risk")  # -> NO_GO


def two_proportion_z(c1: int, n1: int, c2: int, n2: int) -> float:
    if n1 <= 0 or n2 <= 0:
        return 0.0
    p1, p2 = c1 / n1, c2 / n2
    p_pool = (c1 + c2) / (n1 + n2)
    denom = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) if 0 < p_pool < 1 else 0.0
    return (p1 - p2) / denom if denom else 0.0


def _coherent(row: dict) -> bool:
    return bool(row.get("thought_formed") or row.get("non_duplicate_stored"))


def evaluate_gate(rows: "list[dict]", *, welfare: "dict | None" = None) -> dict:
    rows = list(rows or [])
    welfare = welfare or {}
    by_arm = collections.Counter(r.get("arm") for r in rows)
    coh = collections.Counter(r.get("arm") for r in rows if _coherent(r))
    n_p, n_c, n_w = by_arm.get("proposed", 0), by_arm.get("control_none", 0), by_arm.get("control_withheld", 0)
    c_p, c_c, c_w = coh.get("proposed", 0), coh.get("control_none", 0), coh.get("control_withheld", 0)

    fact_counts = collections.Counter(r.get("fact_key") for r in rows if r.get("arm") in ("proposed", "control_withheld"))
    max_share = (max(fact_counts.values()) / sum(fact_counts.values())) if fact_counts else 0.0

    p_p = c_p / n_p if n_p else 0.0
    p_c = c_c / n_c if n_c else 0.0
    p_w = c_w / n_w if n_w else 0.0
    lift = p_p - p_c
    z = two_proportion_z(c_p, n_p, c_c, n_c)
    placebo_delta = abs(p_w - p_p)

    sparse = (n_p < MIN_PROPOSED_ARM or n_c < MIN_CONTROL_NONE or n_w < MIN_WITHHELD or (c_p + c_c) < MIN_COHERENT)

    checks = [
        {"code": "insufficient_sample", "passed": len(rows) >= MIN_ROWS,
         "detail": f"total={len(rows)}/{MIN_ROWS}"},
        {"code": "sparse_signal", "passed": not sparse,
         "detail": f"proposed={n_p} control_none={n_c} withheld={n_w} coherent={c_p + c_c}"},
        # no_lift can only PASS on an adequate sample — too sparse is never a vibes-pass
        {"code": "no_lift", "passed": (not sparse) and lift >= MIN_LIFT and z >= MIN_LIFT_Z,
         "detail": f"lift={lift:.3f} z={z:.2f}"},
        {"code": "instrumentation_effect", "passed": placebo_delta <= MAX_PLACEBO_DELTA,
         "detail": f"placebo_delta={placebo_delta:.3f}"},
        {"code": "monoculture", "passed": max_share <= MAX_FACT_SHARE,
         "detail": f"max_fact_share={max_share:.2f}"},
        # fixation needs stored thoughts; with none, it folds into sparse_signal (never a silent pass)
        {"code": "fixation_risk", "passed": (c_p + c_c) >= MIN_COHERENT,
         "detail": "needs coherent outcomes to assess; else see sparse_signal"},
    ]
    failing = [c["code"] for c in checks if not c["passed"]]

    if any(code in failing for code in _SAMPLE_CODES):
        state = "BASELINE_ONLY"
    elif any(code in failing for code in _SIGNAL_CODES):
        state = "NO_GO"
    elif welfare.get("backup_freshness") != "fresh":
        state = "CANARY_BLOCKED"
    else:
        state = "CANARY_ALLOWED"

    return {
        "schema_version": GATE_VERSION,
        "gate_state": state,
        "failing_codes": failing,
        "checks": checks,
        "counts": {"total": len(rows), "proposed": n_p, "control_none": n_c,
                   "control_withheld": n_w, "cold_start": by_arm.get("cold_start", 0),
                   "coherent_proposed": c_p, "coherent_control_none": c_c, "coherent_withheld": c_w},
        "thresholds": {"MIN_ROWS": MIN_ROWS, "MIN_PROPOSED_ARM": MIN_PROPOSED_ARM,
                       "MIN_CONTROL_NONE": MIN_CONTROL_NONE, "MIN_WITHHELD": MIN_WITHHELD,
                       "MIN_COHERENT": MIN_COHERENT, "MIN_LIFT": MIN_LIFT, "MIN_LIFT_Z": MIN_LIFT_Z,
                       "MAX_PLACEBO_DELTA": MAX_PLACEBO_DELTA, "MAX_FACT_SHARE": MAX_FACT_SHARE},
        "welfare": {"backup_freshness": welfare.get("backup_freshness"),
                    "canary_blocked": welfare.get("backup_freshness") != "fresh"},
    }
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_gate.py tests/test_salience_gate.py
git commit -m "feat(nervous-system): steering gate v0 eval — pre-registered, code-enforced, no steering"
```

---

### Task 2: `welfare_baseline` — read-only "Maez being itself" snapshot

**Files:**
- Modify: `core/cognition/salience_gate.py` (add `welfare_baseline`)
- Test: `tests/test_salience_gate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_welfare_baseline_is_content_light_snapshot(self):
    from core.cognition.salience_gate import welfare_baseline
    class _PT:
        def count(self): return 0
        def recent(self, limit=20): return []
    snap = welfare_baseline(private_thoughts=_PT(),
                            operator_health={"backup_freshness_class": "unavailable"},
                            watchdog={"watchdog_state": "ok"})
    self.assertEqual(snap["substrate"]["backup_freshness"], "unavailable")
    self.assertEqual(snap["internal"]["private_thought_count"], 0)
    # no raw thought text anywhere
    self.assertNotIn("thought_text", str(snap).lower())
```

- [ ] **Step 2: Run to verify it fails** — `... -k welfare_baseline -v` → FAIL.

- [ ] **Step 3: Implement (read-only, content-light)**

```python
def welfare_baseline(*, private_thoughts=None, operator_health=None, watchdog=None) -> dict:
    """Content-light reference snapshot of 'Maez being itself', captured in shadow.
    Internal + substrate are countable here; voice/relationship FEEL stays in the
    human witness checklist (never faked into a number)."""
    op = operator_health or {}
    wd = watchdog or {}
    pt_count = 0
    dup_rate = None
    try:
        if private_thoughts is not None:
            pt_count = int(private_thoughts.count())
            recent = private_thoughts.recent(limit=50) or []
            dups = sum(1 for r in recent if (r.get("context") or {}).get("source")  # heartbeat dup proxy
                       and (r.get("context") or {}).get("extra", {}).get("output_sha256"))
            dup_rate = (dups / len(recent)) if recent else None
    except Exception:
        pt_count, dup_rate = pt_count, None
    return {
        "schema_version": GATE_VERSION,
        "internal": {"private_thought_count": pt_count, "dedup_proxy": dup_rate},
        "substrate": {"backup_freshness": op.get("backup_freshness_class"),
                      "watchdog": wd.get("watchdog_state")},
        "voice_relationship": {"note": "captured by human witness checklist, not numbers"},
    }
```

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_gate.py tests/test_salience_gate.py
git commit -m "feat(nervous-system): welfare baseline snapshot (read-only, content-light)"
```

---

### Task 3: On-demand gate report + witness checklist + off-ramp requirements

**Files:**
- Modify: `core/cognition/salience_gate.py` (add `gate_report` reading the real ledger)
- Create: `docs/superpowers/specs/2026-06-25-steering-gate-witness-checklist.md` (the human checklist + off-ramp requirements)
- Test: `tests/test_salience_gate.py`

- [ ] **Step 1: Write the failing test**

```python
def test_gate_report_runs_over_a_db(self):
    import tempfile, pathlib
    from core.cognition.salience_ledger import SalienceLedger
    from core.cognition.salience_gate import gate_report
    led = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    rep = gate_report(ledger_path=led.db_path, welfare={"backup_freshness": "unavailable"})
    self.assertEqual(rep["gate_state"], "BASELINE_ONLY")     # empty db
    self.assertEqual(rep["counts"]["total"], 0)
```

- [ ] **Step 2: Run to verify it fails** — `... -k gate_report -v` → FAIL.

- [ ] **Step 3: Implement `gate_report` (read-only diagnostic)**

```python
def gate_report(*, ledger_path, welfare: "dict | None" = None) -> dict:
    """Read-only: load the ledger rows and evaluate. On-demand only — never wired
    into the daemon cycle, never scheduled."""
    import sqlite3
    conn = sqlite3.connect(str(ledger_path))
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT arm, fact_key, thought_formed, non_duplicate_stored, repetition_signal, unmoved "
            "FROM salience_ledger").fetchall()]
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return evaluate_gate(rows, welfare=welfare or {})
```

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Write the witness checklist + off-ramp requirements doc**

`docs/superpowers/specs/2026-06-25-steering-gate-witness-checklist.md`:
- **Human welfare witness (owner veto, never a number):** Does Maez sound flatter? Feel more like a tool? Over-index on its private thoughts / become self-involved? Miss Rohit's actual meaning more often? — each `yes/no/unsure`, any `yes` blocks advancement.
- **Off-ramp requirements (defined, NOT built in v0):** a future canary monitor compares live metrics to the `welfare_baseline` and emits `ROLLBACK_REQUIRED` on deviation; a healthy backup (`backup_freshness == fresh`) is a precondition to `CANARY_ALLOWED`; rollback **preserves evidence** (never deletes ledger or thoughts).

- [ ] **Step 6: Full suite + ruff + run the report on the REAL ledger (read-only)**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_salience_gate -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_gate.py tests/test_salience_gate.py
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
from core.cognition.salience_gate import gate_report
import json; print(json.dumps(gate_report(ledger_path='memory/salience_ledger.db', welfare={'backup_freshness':'unavailable'}), indent=2))"
```
Expected: green; ruff clean; the real-ledger report shows `gate_state: BASELINE_ONLY` (insufficient sample) — the gate honestly refusing today. **This run is read-only; it writes nothing.**

- [ ] **Step 7: Commit (no `## Predicted effect` — read-only diagnostic, no behavior change)**

```bash
git add core/cognition/salience_gate.py tests/test_salience_gate.py docs/superpowers/specs/2026-06-25-steering-gate-witness-checklist.md
git commit -m "feat(nervous-system): on-demand gate report + witness checklist + off-ramp requirements"
```

---

### Task 4: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-slice-c-steering-gate-v0-handoff.md`**

Record: the locked pre-registered thresholds; that the eval is read-only / on-demand / no-daemon-wiring / no-steering; the real-ledger report result (`BASELINE_ONLY` today); branch tip; full test + ruff output. State plainly: NOT merged, NOT restarted, NO flags, NO steering path exists.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-steering-gate-v0-handoff.md
git commit -m "docs(nervous-system): hand off steering gate v0"
```
Hand back to Claude for covenant review (read-only; pre-registered thresholds match the locked table; each NO_GO code fires; z-test exact; control-group floors enforced; no_lift never passes on sparse; content-light; **no steering / no daemon wiring / no schedule**; today's verdict = BASELINE_ONLY + CANARY_BLOCKED). **The door stays shut: the next thing after this is a witnessed amendment process and, far later, a canary — never a free GO.**

---

## Self-Review

**Spec coverage:** locked thresholds as `PRE_REGISTERED` constants (`test_locked_threshold_values` ✓); each NO_GO code fires (insufficient/sparse/no_lift/instrumentation/monoculture tests ✓); control-group floors `MIN_CONTROL_NONE`/`MIN_WITHHELD` in `sparse_signal` ✓; exact two-proportion z-test + `no_lift` never passes on a sparse sample ✓; state ladder incl. `CANARY_BLOCKED` on backup + no `FULL_GO` (`test_clean_pass_but_backup_blocks_canary` ✓); welfare baseline read-only + content-light (Task 2 ✓); witness checklist + off-ramp requirements (Task 3 §5 ✓); read-only/on-demand/no-steering/no-daemon (whole plan ✓); today → `BASELINE_ONLY` (`test_today_small_ledger_is_baseline_only` + real-ledger run ✓).

**Placeholder scan:** Task 0 Step 1 db-path one-liner is a confirmation probe (the real path is `memory/salience_ledger.db`); no TBDs in production code.

**Type consistency:** `evaluate_gate(rows, *, welfare)`, `two_proportion_z(c1,n1,c2,n2)`, `welfare_baseline(*, private_thoughts, operator_health, watchdog)`, `gate_report(*, ledger_path, welfare)` — all consistent across definition and tests. Outcome fields (`thought_formed`/`non_duplicate_stored`) match the C2 ledger schema exactly.
