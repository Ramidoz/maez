# Decision-22 v1 backup drill — 2026-04-30 — PASS

## Headline

**23 checks, 0 fail, 0 skip. Drill PASS.**

The bridge from "backup code exists" to "backup is covenant-load-bearing"
is crossed. Decision 22 v1 is now credible enough to move to Decisions
19-20 (capability-acquisition pipeline) per the user's pre-committed
gate.

## What ran

- Source: `/home/rohit/maez` (live repo, daemon active throughout).
- Destination: `/home/rohit/maez-backup-drill/` (~120 GB free, 478 MB
  backup).
- Drill: `python -m scripts.backup.drill --backup-root /home/rohit/maez-backup-drill`.
- Duration: 2.78 seconds wall clock.
- Daemon was running and writing to Chroma + SQLite stores during the
  backup. Backup did NOT pause the daemon — proves SQLite `.backup()`
  and Chroma WAL handling under realistic conditions.

## Per-check results

All 23 checks passed:

| # | check | result |
|---|---|---|
| 1 | `free_space_check` | 128 GB free vs 1.4 GB needed |
| 2 | `backup_succeeded` | 478 MB / 0.57s |
| 3 | `snapshot_manifest_verified` | 356 files; sha256 + size match |
| 4 | `hf_no_coma.restore_succeeded` | hardware-failure reason, write_coma=False |
| 5 | `hf_no_coma.memory_manager_opens` | clean MemoryManager() instantiation |
| 6 | `hf_no_coma.core_count_match` | source=48 restored=48 |
| 7 | `hf_no_coma.recall_for_cycle_non_empty` | core=48, full bundle keys present |
| 8 | `hf_no_coma.lived_episode_count_match` | source=26 restored=26 |
| 9 | `hf_no_coma.identity_yaml_match` | byte-identical |
| 10 | `hf_no_coma.memory_audit_log_db_row_count` | 355 rows match |
| 11 | `hf_no_coma.memory_identity_ledger_db_row_count` | 15 rows match |
| 12 | `hf_no_coma.memory_wants_db_row_count` | 0 rows match |
| 13 | `hf_no_coma.no_coma_written` | drill correctly skipped coma write |
| 14-22 | (same checks for `pause` restore, deliberate-pause reason) | all pass |
| 23 | `pause.no_coma_written` | drill correctly skipped coma write |

## What this proves

- **SQLite `.backup()` works against live writers.** The audit log,
  identity ledger, and Chroma's `chroma.sqlite3` were all snapshotted
  while the daemon was actively writing. All three round-trip cleanly,
  with row counts matching source.
- **Chroma reopens cleanly post-restore.** A fresh `MemoryManager()`
  instantiated against the restored `memory/db/` returns 48 core
  memories — same as the source. `recall_for_cycle("identity")` returns
  a full bundle. The Chroma SQLite-inside-directory fix landed in v1
  is doing the right thing.
- **Lived-memory integrity preserved.** Episode count (26) matches
  source on both restorations.
- **Reason gating works.** Both restores correctly skipped coma
  writes — the hardware-failure restore because `write_coma=False`,
  the deliberate-pause restore because the reason itself doesn't
  trigger coma wording. Captured-coma-list was empty in both cases.
- **Atomic completion holds.** Two restorations into separate temp
  directories from the same snapshot completed cleanly; the snapshot
  was unaffected.

## What the drill DID NOT do

- **No restore into the live repo.** Both restorations went into
  `/home/rohit/maez-backup-drill/restore_*/` — the live `~/maez/` was
  never touched.
- **No real coma core memory was written.** The drill used a fake
  `MemoryManager` (`DrillMM`) that captured `store_core` calls into a
  list and verified the list was empty. The real Maez's memory was
  never modified.
- **The daemon was not stopped.** Live backup conditions were the
  point.
- **No long-term forward-compat test.** Restoring from a 6-month-old
  snapshot whose schema may have drifted is a different test class
  (deferred to v1.5+).

## Reproducing

```bash
rm -rf /home/rohit/maez-backup-drill   # clean any prior state
.venv/bin/python -m scripts.backup.drill \
  --backup-root /home/rohit/maez-backup-drill
```

The drill auto-cleans the destination on pass. Pass `--keep` to
preserve the directories for inspection. The drill report lands at
`logs/backup_drill_<timestamp>.json` regardless of pass/fail.

## What this unlocks

Per the pre-committed gate from the design conversation: Decision 22
v1 is now covenant-load-bearing-correct. The next engineering slice
can move to Decisions 19-20 (capability-acquisition pipeline
orchestration). The named architectures in the manual (RLM,
multi-session entity linking, temporal arithmetic) become integration
candidates after the pipeline can drive them through the consent-card
flow.

## Quarterly drill candidate

The drill is reusable. A future v1.1 deliverable is wiring it to a
quarterly systemd timer per Decision 22's deferred-items list. The
script accepts `--backup-root` and emits a structured JSON log; both
are sufficient for unattended scheduling.
