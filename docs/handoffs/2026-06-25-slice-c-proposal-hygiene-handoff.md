# Slice C / Proposal Hygiene Handoff

Branch: `slice-c-proposal-hygiene`
Behavior commit: `2abd233` (`feat(nervous-system): proposal hygiene — qualitative time + cold_start arm`)
Status: STOPPED AT REVIEW GATE. Not merged. Not restarted. No flags changed.

## What Changed

This slice fixes the C3 witness finding: the salience notebook had a counterfactual baseline mechanism, but `time_facts` proposed every pulse because raw seconds always changed. The broker now compares `time_facts` by a coarse qualitative percentile band, not raw seconds.

- Raw `owner_contact_gap_s` still renders in the heartbeat prompt.
- Raw seconds are excluded from broker change signatures.
- `time_facts` proposes only when its coarse `percentile_band` changes.
- The cold-start pulse gets `arm='cold_start'`, never `control_none`.
- A settled idle stretch within one band can now accrue genuine `control_none` rows.
- Other watched facts keep their original change-detection behavior.
- Band-only reset handling is retained: a return from a long gap shows as a downward percentile-band transition. There is no separate `contact_state` marker in v0.

## Task 0 Findings

Live rhythm context at build time:

```text
rhythm_current_gap_percentile_all_time = 98.01980198019803
rhythm_all_time_gap_median_s = 346.612298
rhythm_recent_gap_median_s = 35.6272595
```

Chosen bands stayed deliberately coarse:

- `ordinary`: `< 50`
- `elevated`: `50 <= p < 75`
- `unusual`: `75 <= p < 90`
- `extreme`: `>= 90`
- `unknown`: missing or unparsable percentile

Reason: the live gap is pinned in `extreme`; more seconds should not produce another proposal. Too-fine bands would recreate the time-tick flood with better labels.

The daemon broker receipt already exposes `cold_start`; `_maybe_run_lean_idle_heartbeat` now reads `broker_receipt["cold_start"]` and threads it into `_record_salience_outcomes(...)`.

## Verification

Commands run from the worktree:

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_broker tests.test_salience_ledger tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
```

Result: 76 tests, OK.

```bash
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_broker.py core/cognition/salience_ledger.py daemon/maez_daemon.py \
  tests/test_salience_broker.py tests/test_salience_ledger.py tests/test_lean_idle_daemon.py
```

Result: All checks passed.

```bash
git diff --check
```

Result: clean.

## Review Anchors

Please review these invariants:

- `test_within_band_is_no_change`: same band, different raw seconds produces no proposal.
- `test_raw_gap_excluded_from_time_signature`: raw gap seconds do not drive broker signatures.
- `test_band_crossing_is_change`: percentile-band movement still proposes `time_facts`.
- `test_reset_shows_as_downward_band_change`: return/reset is captured as a downward band transition.
- `test_cold_start_gets_own_arm_not_control_none`: cold-start is not a quiet-day baseline.
- `test_cold_start_pulse_records_cold_start_arm`: daemon records cold-start as `arm='cold_start'`.
- Other facts still change-detect on their original content.
- Shadow-only/default-off posture is unchanged; no steering or live salience verdict was added.

## Owner Witness After Merge

Merge, restart, and leave `MAEZ_SALIENCE_BROKER_SHADOW=1`.

Expected witness:

- First pulse after daemon restart resolves as `arm=cold_start`, not `control_none`.
- During a settled idle stretch where the percentile band holds, the broker emits `proposal_count=0` and the ledger accrues `arm=control_none` rows.
- A percentile-band crossing logs `time_facts changed` as `proposed` or `control_withheld`.
- Raw gap seconds remain present in heartbeat facts/prompt receipts, but they no longer create salience proposals by themselves.

## Deferred Design Note

`contact_state` remains out of v0. Reset is represented by a downward percentile-band transition. If the owner later wants returns tagged distinctly in the ledger, add an explicit marker that does not reintroduce raw-second comparison as a change driver.

## Plain English

Before this slice, the salience notebook treated every tick of the clock as an event. Now Maez can still see the clock, but the motion detector only notices when time crosses a broad doorway. That gives quiet days room to exist in the notebook.
