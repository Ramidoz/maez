# Slice C C1 — Shadow Attention Broker Handoff

Branch: `slice-c-c1-shadow-attention-broker`
Status: STOPPED at review gate.

Not merged. Not restarted. No flags changed.

## What Changed

- Added `core.cognition.salience_broker`, a pure motion detector over the idle heartbeat window.
- The only strategy is `changed_since_last`.
- Cold start proposes nothing and only establishes the in-memory baseline.
- Later pulses produce observation-only proposals:
  - `changed`
  - `appeared`
  - `cleared`
- The daemon now builds the idle window once and lets the broker and heartbeat consume it independently.
- Added `MAEZ_SALIENCE_BROKER_SHADOW`; there is no enabled/steering flag in C1.

## Task 0 Wiring Site

- Reused `MaezDaemon._maybe_run_lean_idle_heartbeat`.
- The broker runs only after the existing quiet-floor eligibility gate:
  `wake_min_floor` with only `min_floor_due`.
- The window is the same four content-light facts already used by the lean idle heartbeat:
  - `time_facts`
  - `body_state`
  - `open_loops`
  - `recent_private_thoughts`
- C0.5 remains the private-thought seam underneath `recent_private_thoughts`.

## Covenant Guards

- Observation, not judgment:
  receipts carry only `fact_key`, `change_kind`, `strategy`, `proposal_count`, and watched-key names.
- The test suite forbids judgment words in the broker receipt, including:
  `importance`, `important`, `notable`, `priority`, `score`, `urgent`, `unusual`, `deserves`, `matters`, and `should`.
- Signatures are internal hashes or `empty`; raw values and private thought text do not enter receipts.
- Broker-off heartbeat leaves `_salience_broker_baseline` untouched.
- Default-off path returns before adapters or broker are touched.
- No salience scoring, no steering, no stored thoughts, no owner-reaction signal.

## Explorer Audit Notes Folded

- Reused the heartbeat window instead of adding a scheduler or reader.
- Avoided older salience organs (`record_salience_event`, cycle-packet salience, drive-curiosity salience, memory importance) because they already imply priority/meaning.
- Added the broker-off heartbeat regression the audit requested.
- Strengthened the no-importance-language guard.
- Kept signatures out of receipts intentionally; C1 receipts expose only keys and change kinds.

## Verification

Latest local verification before this handoff:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_salience_broker tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon tests.test_private_thoughts_source_scope -v

Ran 50 tests
OK
```

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/salience_broker.py daemon/maez_daemon.py \
  tests/test_salience_broker.py tests/test_lean_idle_daemon.py

All checks passed!
```

## Review Gate

Claude/Codex covenant review should verify:

- C1 is a motion detector only.
- Cold start logs `cold_start=true` and `proposal_count=0`.
- Later receipts contain only content-light deltas.
- There are no importance/priority/notability claims.
- Broker off leaves the heartbeat path unchanged.
- Default-off returns before fact adapters run.
- C2 remains blocked until C1 is merged and witnessed.

## Owner Breath After PASS

After review clears:

1. Merge this branch.
2. Restart Maez with `MAEZ_SALIENCE_BROKER_SHADOW=1`.
3. Let the next quiet floor pulse fire.
4. Witness:
   - first receipt: `cold_start=true`, `proposal_count=0`;
   - later receipts: content-light `changed` / `appeared` / `cleared` proposals;
   - no prompt change, no stored thoughts, no steering, no importance language.

C2 stays blocked until that witness lands.
