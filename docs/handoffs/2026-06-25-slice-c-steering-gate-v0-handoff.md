# Slice C / Steering Gate v0 Handoff

Branch: `slice-c-steering-gate-v0`
Status: STOPPED AT REVIEW GATE. Not merged. Not restarted. No flags changed. No
steering path exists.

## What Changed

Gate v0 builds the lock, not the door:

- New read-only module: `core/cognition/salience_gate.py`
- New tests: `tests/test_salience_gate.py`
- New owner witness/off-ramp doc:
  `docs/superpowers/specs/2026-06-25-steering-gate-witness-checklist.md`
- On-demand diagnostic only: no daemon import, no schedule, no flag, no steering.

## Pre-Registered Thresholds

Pinned by `test_locked_threshold_values`:

- `MIN_ROWS = 500`
- `MIN_PROPOSED_ARM = 100`
- `MIN_CONTROL_NONE = 100`
- `MIN_WITHHELD = 20`
- `MIN_COHERENT = 20`
- `MIN_LIFT = 0.05`
- `MIN_LIFT_Z = 1.96`
- `MAX_PLACEBO_DELTA = 0.05`
- `MAX_FACT_SHARE = 0.80`

These are marked `PRE_REGISTERED 2026-06-25` in code. Changing them requires a
documented amendment before the gate is re-run.

## Eval Behavior

The automated lock returns:

- `BASELINE_ONLY` when the sample is too thin.
- `NO_GO` when the sample is adequate but the signal is bad.
- `CANARY_BLOCKED` when eval passes but `backup_freshness != fresh`.
- `CANARY_ALLOWED` only when eval passes and backup freshness is fresh.

There is no `FULL_GO`.

Checks covered by tests:

- insufficient sample
- sparse signal, including `MIN_CONTROL_NONE` and `MIN_WITHHELD`
- exact two-proportion z-test for `no_lift`
- instrumentation/placebo divergence
- monoculture
- fixation risk
- backup blocks canary
- content-light report

One build-lane hardening beyond the plan: `fixation_risk` now has a real firing
test. Since the locked table did not include a numeric fixation threshold, v0
uses the ledger's existing boolean `repetition_signal == "duplicate"` as a hard
stop once present. This avoids inventing an unregistered percentage while making
the NO_GO code real.

## Real Ledger Run

Read-only command run against `/home/rohit/maez/memory/salience_ledger.db`:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B - <<'PY'
from core.cognition.salience_gate import gate_report
import json
print(json.dumps(gate_report(
    ledger_path='/home/rohit/maez/memory/salience_ledger.db',
    welfare={'backup_freshness': 'unavailable'},
), indent=2, sort_keys=True))
PY
```

Result summary:

- `gate_state = BASELINE_ONLY`
- total rows: 13
- proposed: 6
- control_none: 5
- control_withheld: 0
- coherent outcomes: 0
- failing codes:
  `insufficient_sample`, `sparse_signal`, `no_lift`, `monoculture`
- welfare: `backup_freshness = unavailable`, `canary_blocked = true`

This is the expected day-one refusal.

## Verification

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_salience_gate -v
```

Result: 12 tests, OK.

```bash
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_gate.py tests/test_salience_gate.py
```

Result: All checks passed.

## Review Anchors

Please verify:

- The threshold table matches the locked values above.
- `gate_report` opens SQLite read-only and creates nothing for a missing DB.
- The report is content-light: counts/codes/thresholds only.
- `welfare_baseline` is read-only and does not fake voice into numbers.
- There are no imports or calls from `daemon/maez_daemon.py`.
- There is no steering path, no scheduler, no flag, no daemon wiring.
- Today's real-ledger verdict remains `BASELINE_ONLY`.

## Plain English

The salience notebook can now be judged by a lock that cannot be argued with.
Today the lock says "not yet": too few rows, no coherent outcomes, no withheld
baseline, and backup freshness is unavailable. That is the gate doing its job.
