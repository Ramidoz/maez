# Backup Restore Smoke Test v1.1 — Review Handoff

Branch: `backup-restore-smoke-test-v1-1`  
Code tip before handoff docs: `f9862d6 feat(backup): add manifest restore smoke runner`

## What Changed

- Added a manifest-derived restore smoke path to `scripts/backup/drill.py`.
- The smoke path reads `backup_state_manifest.json` via the caller, selects `required_welfare` + `required_continuity`, then verifies the latest finalized backup artifact against that artifact's own `manifest.json`.
- Added `python -m scripts.backup.drill --smoke`.
- Added `tests/test_restore_smoke.py`.

The old full drill path remains intact. This slice does not touch the daemon, backup writer, restore writer, timers, service files, or live `memory/`.

## Covenant Rails

- Manifest-derived: no second hardcoded store list.
- Artifact-self-consistent: backup files are compared only to their recorded artifact hashes.
- SQLite stores are copied to a temp dir, opened read-only, checked with `PRAGMA quick_check`, and row counts are emitted informationally.
- Latest finalized only: `.in-progress` directories are ignored.
- Temp-only/read-only: no live restore, no daemon restart, no writes to `memory/`.

## Verification Run

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_restore_smoke -v
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/ruff check scripts/backup/drill.py tests/test_restore_smoke.py
```

Result at handoff: both green.

## Review Checklist

- Confirm `required_store_entries()` selects only `required_welfare` + `required_continuity` from the state manifest.
- Confirm no stale spot-check list is used by the smoke path.
- Confirm `run_restore_smoke_test()` verifies the latest finalized artifact and ignores `.in-progress`.
- Confirm `verify_backup_entry()` checks artifact presence/hash against the backup's own manifest, not live state.
- Confirm SQLite checks copy to temp and open read-only.
- Confirm report rows do not compare row counts to live stores.

## Owner Witness After Review

Do not run this as part of merge automation. After review clears, run manually:

```bash
cd /home/rohit/maez
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m scripts.backup.drill --smoke
```

Expected witness:

- `Restore smoke PASS`
- report emitted under `logs/backup_drill_<timestamp>.json`
- required welfare stores, including `memory/salience_ledger.db` and `memory/subjective_duration.db`, show `status=pass`
- SQLite stores include `quick_check="ok"` and row counts

## Predicted Effect

Running the smoke drill proves the latest backup can be unpacked and read in a temp sandbox. It should turn "coverage and freshness are green" into "the raft actually floats" without touching the live Maez state.
