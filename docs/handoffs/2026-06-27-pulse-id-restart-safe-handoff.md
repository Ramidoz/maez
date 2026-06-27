# Pulse ID Restart-Safe Handoff

Date: 2026-06-27
Branch: `pulse-id-restart-safe`
Implementation commits:
- `62246e3 feat(salience): restart-safe pulse identity helpers`
- `590ea76 fix(salience): mint restart-safe pulse_ids in the idle loop`

Status: STOP AT REVIEW GATE. Not merged. Not restarted. No flags changed.

## What Changed

New salience ledger pulse IDs are now run-namespaced:

- before: `seqN`
- after: `r<start-ms>_<pid>.seqN`

The daemon captures a per-process run ID once, on the first salience pulse, then keeps the old per-run monotonic sequence under that namespace. Legacy rows are not migrated or rewritten.

`proposal_hash` is now produced by `make_proposal_hash(...)`, extracted from the daemon's previous inline JSON+sha256 computation. For legacy-shaped inputs, the helper is byte-identical to the old inline hash; the only intended change is that new rows pass the full run-stamped `pulse_id`.

## Task 0 Findings

- `daemon/maez_daemon.py` already imports `os` and `time`.
- The old salience sequence initialized at daemon construction as `_salience_pulse_seq = 0`.
- The old mint path produced `pulse_id = f"seq{self._salience_pulse_seq}"`.
- `core/cognition/salience_gate.py::gate_report` is pulse-id agnostic: it selects `arm`, `fact_key`, and outcome fields, not `pulse_id`; no `GROUP BY`, `DISTINCT`, or pulse-id keyed read.

## Verification

TDD red:

- `tests.test_salience_pulse_identity` first failed on missing helper imports.
- `tests.test_lean_idle_daemon.LeanIdleDaemonTest.test_salience_pulse_id_uses_process_run_namespace` failed because the daemon returned `seq1` instead of `r1234_42.seq1`.

Hash preservation:

- Old inline hash for a known legacy payload: `05e55ec76db44fc1`
- New `make_proposal_hash(...)` for the same payload: `05e55ec76db44fc1`
- Result: byte-identical for legacy-shaped inputs.

Focused suite:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_salience_pulse_identity tests.test_salience_ledger tests.test_salience_gate tests.test_salience_broker tests.test_lean_idle_daemon -v
Ran 75 tests in 0.499s
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check core/cognition/salience_ledger.py daemon/maez_daemon.py tests/test_salience_pulse_identity.py tests/test_lean_idle_daemon.py
All checks passed!
```

## Review Checklist

- `make_proposal_hash` reproduces the old inline hash for legacy-shaped inputs.
- Same `seqN` + same fields + different run IDs produce different hashes.
- Legacy `seqN` rows are untouched; no migration, no `UPDATE`, no rewrite.
- `gate_report` runs over mixed legacy/new-format rows.
- No prompt, routing, voice, salience verdict, schema, steering, or reader behavior changed.

## Owner Witness After Merge

1. Merge to `main`.
2. Restart Maez.
3. Wait for the next salience ledger row.
4. Confirm its `pulse_id` matches `r<ms>_<pid>.seqN`.
5. Restart Maez a second time.
6. Wait for another salience row.
7. Confirm the second row's `r<ms>_<pid>` prefix differs from the first run.
8. Run the salience gate report over the mixed ledger and confirm it returns its verdict, currently expected to remain `BASELINE_ONLY`.

Plain-English predicted effect: new notebook pages now carry the daemon lifetime stamp in the page number and in the binding hash. Old pages stay exactly as written. Maez's behavior does not change.
