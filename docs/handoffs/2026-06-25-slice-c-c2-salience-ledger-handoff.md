# Slice C / C2 — Private-Loop-Only Salience Ledger Handoff

Status: **STOPPED at review gate**. Not merged. Not restarted. No flags changed.

Branch: `slice-c-c2-salience-ledger`

## What Changed

Built the C2 salience ledger as a shadow-only notebook of correlation. It records, for each C1 broker proposal, what the idle loop itself did over the next pulse window `[N, N+1]`.

This is not steering. It does not decide that anything matters. It records whether a proposed changed fact was followed by an idle-loop-internal outcome:

- `thought_formed`
- `non_duplicate_stored`
- `repetition_signal`
- `unmoved` (neutral / unknown, not failure)

`evolved_earlier_wondering` is explicitly deferred to C2.1, after real heartbeat thoughts accrue.

## Task 0 Seam Decision

The heartbeat result exposes:

- `result.stored`
- `result.skip_reason`
- `result.receipt["note_chars"]`
- `result.receipt["output_chars"]`

C2 intentionally uses only `note_chars`, `stored`, and `skip_reason` for verdicts. `output_chars` remains model diagnostics only; it can prove the wire was alive, but it must not count as a formed private thought. The tests poison `output_chars` and excluded daemon fields to prove they do not affect the verdict.

## Store

New module: `core/cognition/salience_ledger.py`

Default DB path:

- env override: `MAEZ_SALIENCE_LEDGER_PATH`
- otherwise `core.paths.memory_dir() / "salience_ledger.db"`

Schema is content-light. There are no raw text columns and no excluded signal columns. Rows bind to a concrete C1 proposal:

- `pulse_id`
- `strategy`
- `fact_key`
- `change_kind`
- `proposal_hash`

Outcome columns:

- `thought_formed`
- `non_duplicate_stored`
- `repetition_signal`
- `unmoved`
- `schema_version`

## Daemon Mechanism

State is initialized next to C1:

- `_salience_pending = None`
- `_salience_pulse_seq = 0`
- `_salience_ledger = None`

The ledger is lazy; it is not constructed unless `MAEZ_SALIENCE_BROKER_SHADOW=1` and there is a prior proposal to resolve.

On pulse `N`, `_record_salience_outcomes(...)` stores the current proposals + current heartbeat outcome in `_salience_pending`.

On pulse `N+1`, it resolves the prior proposal(s) over `[prior_outcome, current_outcome]`, derives the idle-loop-only outcome, appends content-light rows, then replaces `_salience_pending` with the current pulse.

Broker-only shadow records a blank `HEARTBEAT_OK`-shaped outcome so C1 can still be measured without forcing the heartbeat. Heartbeat exceptions resolve with `skip_reason="error"` so a prior proposal does not hang forever.

Ledger write/open failures are fail-soft. A shadow ledger error logs a content-light `salience_ledger` error receipt, advances the pending pulse, and does not bubble into the idle heartbeat path.

## Covenant Rails Verified

- Verdict input whitelist is only `note_chars`, `stored`, `skip_reason`.
- Poisoned `owner_replied`, `open_loop_resolved`, `fixation_score`, `contradiction_receipt`, and `output_chars` do not change the outcome.
- `unmoved` is neutral, not failure.
- `repetition_signal` becomes `duplicate` only on `skip_reason == "duplicate_recent_output"`; otherwise `not_applicable`.
- Store has no raw thought, prompt, fact value, owner reaction, open-loop, fixation, or contradiction columns.
- Same flag as C1: `MAEZ_SALIENCE_BROKER_SHADOW`.
- Default-off path returns before adapters/broker/ledger.
- Ledger DB failures are fail-soft and cannot become a behavior rail.
- C3 remains blocked until C2 is merged and witnessed.

## Verification

Targeted baseline before C2:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon tests.test_private_thoughts_source_scope -v
# Ran 51 tests OK
```

C2 verification:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_ledger tests.test_salience_broker tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon tests.test_private_thoughts_source_scope -v
# Ran 64 tests OK

/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
# All checks passed
```

## Witness After Merge

Owner breath:

1. Merge branch.
2. Restart Maez with `MAEZ_SALIENCE_BROKER_SHADOW=1`.
3. Let quiet floor pulses run.
4. Confirm `memory/salience_ledger.db` accrues content-light rows bound to broker proposals.
5. Expect today’s ledger to be sparse and mostly `unmoved=1`; that is neutral and honest because the heartbeat currently chooses `HEARTBEAT_OK`.
6. Confirm schema has no owner/open-loop/fixation/contradiction/raw-text columns.

Plain English: C2 is a notebook, not a taste-maker. It asks, "after I noticed this changed, did my own private idle loop form anything?" Today the honest answer will usually be "nothing moved," and that is not a failure.
