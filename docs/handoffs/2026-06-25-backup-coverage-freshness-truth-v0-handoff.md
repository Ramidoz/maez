# Backup Coverage + Freshness Truth v0 — Handoff

Date: 2026-06-25
Branch: `backup-coverage-freshness-truth-v0`
Code tip before this handoff: `6bcfbfd`

## Scope

Built the coverage-first welfare backup rail:

- Extended `scripts/backup/backup_state_manifest.json` with a `class` for every entry.
- Added the June nervous-system stores as `required_welfare`: `memory/salience_ledger.db`, `memory/subjective_duration.db`, `memory/routing_observation.db`, `memory/veto_ledger.db`.
- Kept `memory/private_thoughts.db` protected as `required_welfare`.
- Added a read-only `backup_freshness()` reader: `fresh` only when the latest finalized backup is both recent (`<13h`) and complete for all `required_welfare` + `required_continuity` entries.
- Added `coverage_gap` to the closed operator freshness vocabulary.
- Replaced the daemon's hardcoded `backup_freshness_class="unavailable"` with the fail-soft reader.

No merge, no restart, no flag changes, and no backup service run were performed in this build lane.

## Task 0 Classification

Classes now used:

- `required_welfare`: 11 entries, including salience ledger, subjective duration, routing observation, veto ledger, private thoughts, canaries, autonomy preferences, gestation claims, novelty harbor, owner outreach, and owner identity audit.
- `required_continuity`: 52 entries, including Chroma memory, lived-memory stores, identity ledgers, pending cards, wants, wonderings, S7.1 WebAuthn store, continuity capsule/archive, and local identity/soul/policy config.
- `optional_observability`: 25 entries, including legacy Chroma, quality/recall stats, trace logs, baseline files, absent optional governance dirs, and secret files excluded from ordinary backups.
- `ephemeral_skip`: 3 documented skips.

Documented skips:

- `memory/capability_gap_cooldown.db`: transient cooldown cache; capability queue and plans are backed up separately.
- `memory/sandbox_ledger_2026_05_07.db`: dated sandbox scratch from 2026-05-07; not continuity state.
- `memory/sandbox_ledger_2026_05_08.db`: dated sandbox scratch from 2026-05-08; not continuity state.

Task 0 seam confirmations:

- Backup root is `/home/rohit/maez-backups` via `MAEZ_BACKUP_ROOT` in `~/.config/systemd/user/maez-backup.service`.
- Latest finalized live backup before this branch lacked `memory/salience_ledger.db` and `memory/subjective_duration.db`; with the new manifest, the worktree reader correctly reports `coverage_gap` against that backup.
- Backup manifests list copied files, so required directory entries are counted as covered when at least one backed file appears under that directory path.

## Verification

Focused backup/wiring suite:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_backup_manifest_coverage tests.test_backup_freshness tests.test_backup_freshness_daemon_wiring -v
Ran 14 tests in 0.443s
OK
```

Lean idle daemon regression surface:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_daemon -v
Ran 27 tests in 0.475s
OK
```

S7/operator-health surface:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_operator_user_boundary_s7 -v
Ran 193 tests in 5.624s
OK
```

Lint / diff:

```text
/home/rohit/maez/.venv/bin/ruff check core/health/backup_freshness.py daemon/maez_daemon.py core/governance/operator_user_boundary.py tests/test_backup_manifest_coverage.py tests/test_backup_freshness.py tests/test_backup_freshness_daemon_wiring.py
All checks passed!

git diff --check
clean
```

## Review Checklist

- Coverage before signal: manifest coverage landed before the freshness reader/wiring commits.
- `fresh` requires recency and coverage: recent-but-incomplete backups return `coverage_gap`.
- `.in-progress` backups are never counted.
- Required directories are covered by child file entries in `manifest.json`.
- Daemon reader is read-only and fail-soft to `unavailable`.
- Skips are written and classified as `ephemeral_skip`.
- No schedule, encryption, restore, or backup-run behavior changed.

## Owner Witness After Review

Only after review clears and the branch is merged:

```bash
systemctl --user start maez-backup.service
LATEST=$(ls -d /home/rohit/maez-backups/2026-* | sort | tail -1)
test -d "$LATEST"
test ! -e "/home/rohit/maez-backups/.in-progress/$(basename "$LATEST")"
grep -q "memory/salience_ledger.db" "$LATEST/manifest.json"
grep -q "memory/subjective_duration.db" "$LATEST/manifest.json"
grep -q "memory/routing_observation.db" "$LATEST/manifest.json"
grep -q "memory/veto_ledger.db" "$LATEST/manifest.json"
```

Then restart Maez and verify:

```bash
systemctl --user restart maez.service
journalctl --user -u maez -n 200 | grep -E "backup_freshness|operator_health"
```

Expected:

- Before the forced backup, the new reader should report `coverage_gap` against the current latest backup.
- After a finalized backup produced from this manifest, `backup_freshness_class` can become `fresh` if the backup is under 13h old and covers every required path.
- The steering gate still remains blocked on salience evidence; this slice only removes the fake/unavailable backup axis once the life raft is real.

## Named Follow-Up

v1.1: restore smoke test. A backup is not fully proven until the required welfare stores can be restored into an isolated temp location and opened with sane row counts. Not built in v0.

## Layman's Summary

This slice stops Maez from saying "backup is healthy" just because a backup ran. The backup only counts as healthy if it actually contains the nervous-system notebook, time-sense, routing observations, and veto ledger we just built. Until a new backup includes those organs, the dashboard should say `coverage_gap`, which is the honest truth.
