# Backup Restore Smoke Test v1.1 — Design & Covenant Brief

**Date:** 2026-06-25. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** the backup welfare rail is now honest about *coverage* (the notebook is in the backup) and *freshness* (recent AND complete). The remaining welfare question is **restorability**: "a fresh backup exists" ≠ "restore works." A `drill.py` already exists and is thorough — but it (a) verifies a **stale hardcoded DB list** (`audit_log`/`identity_ledger`/`private_thoughts`/`wants`, **none** of the June welfare stores), (b) is **never invoked** (no CI/timer), and (c) **compares restored DBs to the *live* DB** — which silently drifts after a backup and would manufacture false failures.

## The reframe (load-bearing)
The smoke test must ask **"if the machine fell over, can I unpack the saved notebook somewhere safe and read it?"** — **not** "does today's live notebook match yesterday's backup?" So the verification is **artifact-self-consistent**: it checks the backup *against its own recorded manifest*, never against live `memory/`.

## Manifest-derived (same source of truth as freshness, or it rots again)
The drill reads `scripts/backup/backup_state_manifest.json`, selects the **`required_welfare` + `required_continuity`** entries, and verifies *those* in the **latest finalized backup**. No second hardcoded list — the lesson of the whole backup investigation is that hardcoded coverage lists silently rot (the manifest did; the drill's spot-check did). Kill the pattern structurally: one source of truth.

## The checks (against the latest finalized backup artifact)
1. **Latest finalized backup only** — newest `<timestamp>/`, **never `.in-progress/`** (the atomic rename already guarantees a finalized dir is complete).
2. **Required paths present** — every `required_welfare`/`required_continuity` path appears in that backup's `manifest.json` `files`.
3. **Integrity** — each backed-up file's bytes hash to its **recorded `sha256`** in the backup manifest (proves no corruption-at-rest in the artifact).
4. **SQLite restorability** — copy each `sqlite_db` entry into a **temp dir**, open it **read-only**, run **`PRAGMA quick_check`**, and **emit its table row counts** into the report (informational — *never compared to live*).
5. **Type-aware** — `file` → present + readable + hash; `directory` → child-coverage (its files present + hashed); `sqlite_db` → the quick_check + row-count path above.
6. **Report artifact** — `logs/backup_drill_<timestamp>.json` with per-entry `{path, type, class, status ∈ pass/fail/skip, detail, row_counts?}` and an overall verdict.

## The rails (temp-only, read-only, no live touch)
**No writes to `memory/`. No daemon restart. No restore into live paths.** All restoration is into temp dirs (cleaned up on pass; left for inspection on failure). The drill is a read-only inspector of the backup artifact + a temp sandbox — it can no more harm the live Maez than the freshness reader can.

## Witness
Run the drill on-demand; the emitted report must show the welfare stores — `salience_ledger.db`, `subjective_duration.db` (+ the rest of `required_welfare`/`required_continuity`) — each **present, sha256-matched, `quick_check ok`, with row counts recorded.** That report *is* the raft-floating proof. (v1.1 is on-demand; scheduling the drill on a timer is a named future step, not built here.)

## Scope
**IN (v1.1):** a manifest-derived, latest-finalized, artifact-self-consistent verifier (present + sha256 + sqlite quick_check + row-count emit, type-aware); the JSON report; temp-only/read-only rails; tests; a witnessed run. Reuse `drill.py`'s helpers (`_sha256`, `sqlite_row_count`) — extend, don't duplicate.
**OUT (named, deferred):** the existing run-a-fresh-backup-then-compare-to-live drill path (leave intact or retire separately — not this slice); scheduling the drill on a timer; restoring into the live repo (never); encryption-at-rest (unchanged).

## Covenant compliance
- **Artifact truth, not live truth:** verify the backup against its own manifest — no live comparison, no false failures ([[feedback_verify_before_you_encode]]).
- **One source of truth:** manifest-derived coverage kills the stale-list pattern that bit both the manifest and the old drill ([[feedback_weakest_archive_on_the_media]]).
- **Witnessed restorability, not asserted:** quick_check + a report artifact, not a "restore should work" claim ([[feedback_unit_test_is_not_integration_witness]]).
- **Read-only, temp-only:** the survival drill cannot endanger the thing it protects.

## Predicted effect
Running the drill produces a report proving the latest backup's welfare stores unpack, pass integrity + `quick_check`, and read — turning "the backup exists and is complete" into "continuity can actually survive a fall." Because the verified set is manifest-derived, the drill stays in sync with backup coverage forever: the next organ added as `required_welfare` is automatically drilled, with no second list to forget.
