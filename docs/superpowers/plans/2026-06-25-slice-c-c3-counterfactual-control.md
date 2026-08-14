# Slice C — C3 Counterfactual Control — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags** — stop at the review gate. Builds on C0.5 + C1 + C2 (all merged). Same flag: `MAEZ_SALIENCE_BROKER_SHADOW`.

**Goal:** Stop the salience ledger from only recording "something changed" pulses. Every pulse now writes a row tagged by `arm` — `proposed` (a fact changed), `control_none` (nothing changed; the baseline), or `control_withheld` (a fact changed but deterministically withheld; a placebo) — all resolved with the **same** C2 `[N, N+1]` idle-loop outcome. It records the whole field of observation; it does **not** claim causality.

**Architecture:** Add an `arm` column (migrate existing rows → `proposed`); a pure `assign_arm(proposals, pulse_signature)` (deterministic, stable hash, no randomness); rework the daemon's `_record_salience_outcomes` so it resolves the prior pulse **every** time (quiet pulses included) and tags each row with its arm.

**Tech Stack:** Python 3, stdlib `sqlite3`. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** deterministic assignment only (no `random`); `control_withheld` logs honestly (content-light fact identity, never "nothing changed", never raw values); **no live verdicts, no weights, no steering**; the same idle-loop-only `derive_outcome` (the arm must NOT influence the outcome); `unmoved` neutral; the `proposed`-vs-`control_none` comparison is offline-only; default-off byte-identical.

---

### Task 0: Confirm the C2 wiring + ledger schema (no production code)

- [ ] **Step 1: Read the current ledger store + the daemon wiring**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, core.cognition.salience_ledger as L, daemon.maez_daemon as d
print(inspect.getsource(L.SalienceLedger.__init__)); print('---'); print(inspect.getsource(L.SalienceLedger.record))
print('==='); print(inspect.getsource(d.MaezDaemon._record_salience_outcomes))"
```
Confirm: the `CREATE TABLE` columns, the `record(...)` signature, and that `_record_salience_outcomes` currently only resolves the prior pulse **when `prior['proposals']` is non-empty** (the blind spot C3 fixes). Record where `_salience_pending` is shaped, and where the broker's window/signatures are available in `_maybe_run_lean_idle_heartbeat` (for `pulse_signature`).

---

### Task 1: Ledger gains an `arm` column (fresh schema + migration)

**Files:**
- Modify: `core/cognition/salience_ledger.py`
- Test: `tests/test_salience_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_fresh_schema_has_arm_column(self):
    led = self._ledger()
    self.assertIn("arm", led.column_names())

def test_record_persists_arm(self):
    led = self._ledger()
    outcome = derive_outcome([{"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"}])
    led.record(pulse_id="p1", strategy="changed_since_last", arm="control_none",
               fact_key="none", change_kind="none", proposal_hash="abc", outcome=outcome)
    self.assertEqual(led.recent(1)[0]["arm"], "control_none")

def test_existing_rows_migrate_to_proposed(self):
    # simulate a pre-C3 db (no arm column), then open with the new store => arm defaults to 'proposed'
    import sqlite3, tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "old.db"
    conn = sqlite3.connect(p)
    conn.execute("""CREATE TABLE salience_ledger (row_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pulse_id TEXT NOT NULL, strategy TEXT NOT NULL, fact_key TEXT NOT NULL, change_kind TEXT NOT NULL,
        proposal_hash TEXT NOT NULL, thought_formed INTEGER NOT NULL, non_duplicate_stored INTEGER NOT NULL,
        repetition_signal TEXT NOT NULL, unmoved INTEGER NOT NULL, schema_version TEXT NOT NULL)""")
    conn.execute("""INSERT INTO salience_ledger (pulse_id,strategy,fact_key,change_kind,proposal_hash,
        thought_formed,non_duplicate_stored,repetition_signal,unmoved,schema_version)
        VALUES ('seq2','changed_since_last','time_facts','changed','h',0,0,'not_applicable',1,'salience_ledger.v0')""")
    conn.commit(); conn.close()
    led = SalienceLedger(p)                 # opening must migrate, not crash
    row = led.recent(1)[0]
    self.assertEqual(row["arm"], "proposed")    # legacy row defaults to proposed
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_salience_ledger -k arm -v` → FAIL.

- [ ] **Step 3: Implement schema + idempotent migration + `record(arm=...)`**

Add `arm` to the `CREATE TABLE` (fresh DBs) and migrate existing DBs in `_init`:
```python
    # in _init(), after CREATE TABLE IF NOT EXISTS (which now includes:  arm TEXT NOT NULL DEFAULT 'proposed')
    cols = [r[1] for r in conn.execute("PRAGMA table_info(salience_ledger)").fetchall()]
    if "arm" not in cols:
        conn.execute("ALTER TABLE salience_ledger ADD COLUMN arm TEXT NOT NULL DEFAULT 'proposed'")
    conn.commit()
```
Extend `record` to accept and store `arm` (keyword-only, no default — callers must be explicit):
```python
def record(self, *, pulse_id, strategy, arm, fact_key, change_kind, proposal_hash, outcome) -> None:
    ...
    conn.execute(
        """INSERT INTO salience_ledger
           (pulse_id, strategy, arm, fact_key, change_kind, proposal_hash,
            thought_formed, non_duplicate_stored, repetition_signal, unmoved, schema_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (str(pulse_id), str(strategy), str(arm), str(fact_key), str(change_kind), str(proposal_hash),
         int(bool(outcome["thought_formed"])), int(bool(outcome["non_duplicate_stored"])),
         str(outcome["repetition_signal"]), int(bool(outcome["unmoved"])), LEDGER_VERSION),
    )
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_ledger.py
git commit -m "feat(nervous-system): C3 ledger arm column + legacy migration to proposed"
```

---

### Task 2: `assign_arm` — deterministic arm + rows-to-record

**Files:**
- Modify: `core/cognition/salience_ledger.py`
- Test: `tests/test_salience_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
from core.cognition.salience_ledger import assign_arm, WITHHOLD_EVERY

class AssignArmTest(unittest.TestCase):
    def test_no_change_is_control_none_with_sentinel(self):
        arm, rows = assign_arm([], pulse_signature="anything")
        self.assertEqual(arm, "control_none")
        self.assertEqual(list(rows), [{"fact_key": "none", "change_kind": "none"}])

    def test_change_default_proposed(self):
        # pick a signature whose hash is NOT a withhold
        props = [{"fact_key": "time_facts", "change_kind": "changed"}]
        arm, rows = assign_arm(props, pulse_signature="sig-not-withheld")
        self.assertIn(arm, ("proposed", "control_withheld"))   # deterministic for this sig
        self.assertEqual(list(rows), props)                    # fact identity preserved either way

    def test_withheld_is_deterministic_and_keeps_fact_identity(self):
        # same signature => same arm, twice
        props = [{"fact_key": "body_state", "change_kind": "changed"}]
        a1, r1 = assign_arm(props, pulse_signature="sig-X")
        a2, r2 = assign_arm(props, pulse_signature="sig-X")
        self.assertEqual(a1, a2)                # deterministic
        self.assertEqual(list(r1), list(r2))
        # withheld still carries fact identity (never pretends nothing changed)
        if a1 == "control_withheld":
            self.assertEqual(r1[0]["fact_key"], "body_state")

    def test_no_randomness_imported(self):
        import core.cognition.salience_ledger as m, inspect
        src = inspect.getsource(m)
        self.assertNotIn("import random", src)
        self.assertNotIn("Math.random", src)
```

- [ ] **Step 2: Run to verify they fail** — `... -k Arm -v` → FAIL.

- [ ] **Step 3: Implement**

```python
import hashlib

WITHHOLD_EVERY = 5   # deterministic 1-in-5 changed pulses are withheld (placebo)

def assign_arm(proposals: "list[dict]", pulse_signature: str) -> "tuple[str, tuple[dict, ...]]":
    if not proposals:
        return "control_none", ({"fact_key": "none", "change_kind": "none"},)
    digest = int(hashlib.sha256(str(pulse_signature).encode("utf-8")).hexdigest(), 16)
    arm = "control_withheld" if digest % WITHHOLD_EVERY == 0 else "proposed"
    rows = tuple({"fact_key": str(p.get("fact_key", "")), "change_kind": str(p.get("change_kind", ""))}
                 for p in proposals)
    return arm, rows   # withheld keeps fact identity — it never pretends nothing changed
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/salience_ledger.py tests/test_salience_ledger.py
git commit -m "feat(nervous-system): C3 deterministic arm assignment (none/proposed/withheld)"
```

---

### Task 3: Daemon — resolve EVERY pulse, tag the arm, log control rows

**Files:**
- Modify: `daemon/maez_daemon.py` (`_record_salience_outcomes` + the call site's `pulse_signature`)
- Test: `tests/test_lean_idle_daemon.py` (new C3 tests + update C2 tests for the new signature)

- [ ] **Step 1: Write the failing tests**

```python
def test_quiet_pulse_records_control_none_baseline(self):
    import os, tempfile, pathlib
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    from core.cognition.salience_ledger import SalienceLedger
    daemon = object.__new__(MaezDaemon)
    daemon._salience_pending = None; daemon._salience_pulse_seq = 0
    daemon._salience_ledger = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False):
        # pulse N: NOTHING changed (empty proposals) -> control_none baseline
        daemon._record_salience_outcomes([], {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"},
                                         strategy="changed_since_last", pulse_signature="sigA")
        # pulse N+1: resolves the control_none row from N
        daemon._record_salience_outcomes([], {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"},
                                         strategy="changed_since_last", pulse_signature="sigB")
    rows = daemon._salience_ledger.recent(5)
    self.assertEqual(len(rows), 1)                       # the quiet day was recorded
    self.assertEqual(rows[0]["arm"], "control_none")
    self.assertEqual((rows[0]["fact_key"], rows[0]["change_kind"]), ("none", "none"))
    self.assertEqual(rows[0]["unmoved"], 1)              # neutral baseline

def test_arm_does_not_change_the_outcome(self):
    # proposed and control rows use the SAME derive_outcome (arm never influences the verdict)
    import os, tempfile, pathlib
    from unittest import mock
    from daemon.maez_daemon import MaezDaemon
    from core.cognition.salience_ledger import SalienceLedger
    daemon = object.__new__(MaezDaemon)
    daemon._salience_pending = None; daemon._salience_pulse_seq = 0
    daemon._salience_ledger = SalienceLedger(pathlib.Path(tempfile.mkdtemp()) / "l.db")
    with mock.patch.dict(os.environ, {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False):
        daemon._record_salience_outcomes([{"fact_key": "time_facts", "change_kind": "changed"}],
                                         {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok_or_rejected"},
                                         strategy="changed_since_last", pulse_signature="sig1")
        daemon._record_salience_outcomes([], {"note_chars": 80, "stored": True, "skip_reason": "none"},
                                         strategy="changed_since_last", pulse_signature="sig2")
    r = daemon._salience_ledger.recent(5)[0]
    self.assertIn(r["arm"], ("proposed", "control_withheld"))
    self.assertEqual(r["non_duplicate_stored"], 1)      # [N,N+1] outcome is arm-independent
```
Also: **update the existing C2 daemon tests** (`test_salience_ledger_resolves_over_two_pulses`, `test_salience_off_records_nothing`) to pass the new `pulse_signature=` kwarg and assert the resolved row now carries an `arm`.

- [ ] **Step 2: Run to verify they fail** — `... -k "control_none or arm_does_not" -v` → FAIL.

- [ ] **Step 3: Rework `_record_salience_outcomes`**

```python
def _record_salience_outcomes(self, proposals, heartbeat_outcome, *, strategy, pulse_signature):
    if not _salience_broker_shadow_enabled():
        return None
    from core.cognition.salience_ledger import derive_outcome, assign_arm
    self._salience_pulse_seq = int(getattr(self, "_salience_pulse_seq", 0)) + 1
    pulse_id = f"seq{self._salience_pulse_seq}"
    arm, rows = assign_arm(list(proposals or []), pulse_signature)
    current = {"pulse_id": pulse_id, "strategy": str(strategy or "changed_since_last"),
               "arm": arm, "rows": [dict(r) for r in rows], "outcome": dict(heartbeat_outcome or {})}
    prior = getattr(self, "_salience_pending", None)
    if prior is not None:                       # ALWAYS resolve — quiet days recorded too
        try:
            outcome = derive_outcome([prior.get("outcome", {}), current["outcome"]])
            ledger = self._salience_ledger_get()
            for row in prior.get("rows", []):
                proposal_hash = hashlib.sha256(json.dumps(
                    {"pulse_id": prior["pulse_id"], "strategy": prior["strategy"], "arm": prior["arm"],
                     "fact_key": row["fact_key"], "change_kind": row["change_kind"]},
                    sort_keys=True).encode("utf-8")).hexdigest()[:16]
                ledger.record(pulse_id=prior["pulse_id"], strategy=prior["strategy"], arm=prior["arm"],
                              fact_key=row["fact_key"], change_kind=row["change_kind"],
                              proposal_hash=proposal_hash, outcome=outcome)
        except Exception as exc:
            logger.info("salience_ledger receipt=%s", json.dumps(
                {"schema_version": "salience_ledger.v0", "skip_reason": "error",
                 "error_class": exc.__class__.__name__, "arm": prior.get("arm")}, sort_keys=True))
    self._salience_pending = current
    return pulse_id
```
At the call site in `_maybe_run_lean_idle_heartbeat`, compute a content-light `pulse_signature` from the window (reusing C1's pure `fact_signatures`) and pass it to **every** `_record_salience_outcomes` call:
```python
    if broker_active:
        from core.cognition.salience_broker import fact_signatures
        pulse_signature = hashlib.sha256(
            json.dumps(fact_signatures(window), sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        # ... existing proposals extraction ...
        self._record_salience_outcomes(proposals, hb_outcome, strategy=strategy, pulse_signature=pulse_signature)
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Full suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_ledger tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
```
Expected: green; ruff clean. Confirm a quiet pulse now produces a `control_none` row and the arm never alters the resolved outcome.

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "feat(nervous-system): C3 counterfactual arms — record the quiet days too

## Predicted effect
Every wake_min_floor pulse now writes a salience_ledger row: proposed (a fact
changed), control_none (nothing changed; sentinel fact_key=none), or
control_withheld (changed but deterministically withheld, fact identity kept).
All share the same idle-loop-only [N,N+1] outcome; the arm never influences it.
This gives the notebook a quiet-day baseline. No steering, no verdicts; the
proposed-vs-control_none comparison is offline-only. Default-off byte-identical."
```

---

### Task 4: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-slice-c-c3-counterfactual-control-handoff.md`**

Record: Task 0 findings; the migration approach (`ALTER TABLE ... DEFAULT 'proposed'`); `WITHHOLD_EVERY` + the `pulse_signature` derivation; branch tip; full test + ruff output; the witness sequence (**merge → owner restart → confirm `salience_ledger.db` now accrues `control_none` rows on quiet pulses, `proposed` rows on changed pulses, occasional `control_withheld` rows that still name the changed fact; the legacy `seq2` row reads `arm=proposed`; no schema column for owner-reaction/open-loop/fixation/contradiction/raw-text**). State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-c3-counterfactual-control-handoff.md
git commit -m "docs(nervous-system): hand off C3 counterfactual control"
```
Hand back to Claude for covenant review (control_none mandatory baseline; withheld logs honestly with fact identity; deterministic no-randomness; arm never influences derive_outcome; unmoved neutral; legacy migration to proposed; offline comparison only; content-light; default-off byte-identical). **C3 completes the Slice C shadow arc** — after it, the gate (eval-immune + off-ramp) before any steering.

---

## Self-Review

**Spec coverage:** `control_none` mandatory baseline with `fact_key=none`/`change_kind=none` (Task 2 + Task 3 `test_quiet_pulse_records_control_none_baseline` ✓); `proposed` unchanged (✓); `control_withheld` keeps fact identity, never pretends nothing changed (Task 2 `test_withheld_..._keeps_fact_identity` ✓); deterministic, no randomness (`test_no_randomness_imported` + stable-hash assign_arm ✓); same `derive_outcome`, arm doesn't influence outcome (`test_arm_does_not_change_the_outcome` ✓); `unmoved` neutral (inherited from C2 ✓); legacy rows migrate to `proposed` (Task 1 `test_existing_rows_migrate_to_proposed` ✓); offline comparison only (no live verdict added ✓); default-off byte-identical (inherited; the `_record_salience_outcomes` flag-guard + existing `test_salience_off_records_nothing` updated ✓).

**Placeholder scan:** none. The call-site insertion reuses C1's `fact_signatures` and the existing `broker_active` block; `pulse_signature` is content-light (hash of hashes).

**Type consistency:** `assign_arm(proposals, pulse_signature) -> (arm, rows)` identical in Task 2 (def) and Task 3 (call). `record(*, pulse_id, strategy, arm, fact_key, change_kind, proposal_hash, outcome)` identical in Task 1 (def) and Task 3 (call). `_record_salience_outcomes(..., *, strategy, pulse_signature)` signature matches the updated C2 tests.
