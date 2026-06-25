# Slice C / C3 Counterfactual Control Handoff

Branch: `slice-c-c3-counterfactual-control`
Behavior commit: `65500bf` (`feat(nervous-system): C3 counterfactual arms record quiet days too`)
Status: STOPPED AT REVIEW GATE. Not merged. Not restarted. No flags changed.

## What Changed

C3 completes the shadow salience notebook's observation field. C2 only recorded pulses where the broker had a proposal, so the ledger only saw "something changed" moments. C3 adds counterfactual arms so the ledger also records quiet pulses and withheld changed facts without claiming causality.

- `SalienceLedger` now has an `arm` column.
- Existing pre-C3 rows migrate idempotently to `arm='proposed'`.
- `assign_arm(proposals, pulse_signature)` is deterministic and imports no randomness.
- `control_none` is mandatory for quiet pulses, recorded as `fact_key='none'`, `change_kind='none'`.
- `control_withheld` keeps the changed fact identity. It never pretends nothing changed.
- `_record_salience_outcomes(...)` now resolves the prior pulse every time, not only when the prior had proposals.
- Arm assignment never changes `derive_outcome`; the same idle-loop-only `[N, N+1]` verdict is used for every arm.

## Task 0 Findings

The C2 code matched the planned blind spot:

- Fresh schema lacked `arm`.
- `SalienceLedger.record(...)` had no arm argument.
- `_record_salience_outcomes(...)` shaped `_salience_pending` as `proposals + outcome`.
- The prior pulse resolved only under `if prior is not None and prior.get("proposals")`, so quiet pulses were invisible.
- The heartbeat call site had the C1 window available; C3 derives a content-light `pulse_signature` from `fact_signatures(window)`.

## Schema And Migration

Fresh DBs create:

- `arm TEXT NOT NULL DEFAULT 'proposed'`

Existing DBs run:

- `ALTER TABLE salience_ledger ADD COLUMN arm TEXT NOT NULL DEFAULT 'proposed'`

The test `test_existing_rows_migrate_to_proposed` simulates a pre-C3 DB like the live `seq2` row and verifies it opens with `arm='proposed'`.

## Arm Assignment

`WITHHOLD_EVERY = 5`.

Changed pulses are assigned by:

- `sha256(str(pulse_signature)) % WITHHOLD_EVERY`

Quiet pulses always become:

- `arm='control_none'`
- one sentinel row: `fact_key='none'`, `change_kind='none'`

The daemon derives `pulse_signature` as a hash of C1's content-light `fact_signatures(window)`. Raw fact values, prompts, thoughts, and owner text are not stored in the ledger.

## Verification

Commands run from the worktree:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_ledger tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
```

Result: 68 tests, OK.

```bash
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
```

Result: All checks passed.

```bash
git diff --check
```

Result: clean.

## Review Anchors

Please review these invariants:

- `control_none` rows are written for quiet pulses and resolved over the same `[N, N+1]` window.
- `control_withheld` logs honestly with fact identity intact.
- Arm assignment is deterministic and imports no randomness.
- `derive_outcome` remains idle-loop-only and arm-blind.
- `unmoved` remains neutral.
- Legacy rows migrate to `arm='proposed'`.
- Comparison remains offline only. No steering, no weights, no live salience verdict.
- Ledger remains content-light and has no owner-reaction, open-loop-resolution, fixation, contradiction, prompt, raw thought, or raw fact-value columns.
- Default-off remains byte-identical: `_record_salience_outcomes` still returns before doing anything unless `MAEZ_SALIENCE_BROKER_SHADOW=1`.

## Owner Witness After Merge

Merge, restart, and leave `MAEZ_SALIENCE_BROKER_SHADOW=1`.

Expected live witness:

- Quiet pulses accrue `arm=control_none`, `fact_key=none`, `change_kind=none`, usually `unmoved=1`.
- Changed pulses accrue `arm=proposed`, or occasionally `arm=control_withheld`.
- Withheld rows still name the changed fact key and change kind.
- The legacy live `seq2` row reads `arm=proposed` after migration.
- No schema column exists for owner reaction, open-loop resolution, fixation score, contradiction receipts, raw text, prompt text, or fact values.

## Plain English

Before C3, Maez's salience notebook only wrote down rainy days. C3 makes it write down quiet days too. It still does not decide what matters, and it does not steer the idle mind. It only gives the future comparison a fair baseline.
