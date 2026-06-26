# Backup Coverage + Freshness Truth v0 — Design & Covenant Brief

**Date:** 2026-06-25. **Lane:** Claude drafts + covenant-reviews; Codex specs → plans → builds; owner witnesses. **Origin:** Gate v0 named `backup_freshness == fresh` as a hard precondition for any canary. Investigation found **two** gaps: (1) the daemon hardcodes `backup_freshness_class="unavailable"` ([daemon:3908](daemon/maez_daemon.py)), and (2) — the serious one — the backup manifest was last edited **May 19**, so **18 `memory/` stores are unprotected**, including the entire June nervous-system arc: `salience_ledger.db` (the notebook the gate guards), `subjective_duration.db` (the time-sense), `routing_observation.db`, `veto_ledger.db`. `private_thoughts.db` *is* protected. **The `unavailable` was accidentally honest: the notebook genuinely isn't insured.**

## The core invariant (load-bearing)
**No backup signal may report `fresh` unless the latest successful backup includes the welfare-critical stores.** A recent backup that missed `salience_ledger.db` is **not** continuity insurance for the canary — it must read `coverage_gap`, never `fresh`. This is "no fake green" with teeth.

## Coverage before signal (the ordering is a covenant, not a preference)
Wiring the freshness signal first would manufacture the exact fake green the investigation caught. So: **fix coverage, then tell the truth about it.**

## Part 1 — Manifest coverage (classify the 18, extend the manifest)
Audit every `memory/*.db` (and other stateful files) against `scripts/backup/backup_state_manifest.json`. Add a **`class`** field to each entry (the backup script reads only `type`/`path`, so the new field is safely ignored):
- **`required_continuity`** — must be backed up; missing ⇒ backup is not `fresh`. (e.g. `identity_ledger.db`, `audit_log.db`, `lived_episodes.db`.)
- **`required_welfare`** — the **canary precondition set**: `salience_ledger.db`, `subjective_duration.db`, `private_thoughts.db`, `routing_observation.db`, `veto_ledger.db` (+ any other nervous-system/welfare store). Missing ⇒ not `fresh`.
- **`optional_observability`** — useful but **not** canary-blocking (e.g. `site_analytics`, `reflection_audit.db`). Missing ⇒ still `fresh`.
- **`ephemeral_skip`** — intentionally not backed up, **with a written reason** (e.g. `sandbox_ledger_2026_05_07/08.db` dated scratch, transient cooldown/queue caches). Recorded in an `intentionally_skipped` list so the skip is **witnessed, never silent**.

**The June nervous-system stores are `required_welfare`, never optional.** Task 0 classifies all 18; the build adds the missing `required_*` entries (with `type`/`path`/`class`/`required`/`comment`) and the `intentionally_skipped` reasons.

## Part 2 — Freshness means recent **and** complete
A **read-only** `backup_freshness()` reader over `$BACKUP_ROOT` (= `/home/rohit/maez-backups`):
1. Find the latest **finalized** backup dir (newest `<timestamp>/`, **excluding `.in-progress/`** — the atomic rename guarantees a finalized dir is a complete, successful backup).
2. Read its `manifest.json` (`timestamp` + the `files` list of `{path, sha256, size}`).
3. **Age check:** `now − timestamp < FRESH_MAX_AGE_H` (locked `13h` — one missed 6-hour cycle plus margin).
4. **Coverage check:** every `required_welfare` + `required_continuity` path from the backup-state-manifest appears in that backup's `files`.

Returns a class:
- **`fresh`** — recent **and** complete (age < 13h **and** coverage holds).
- **`coverage_gap`** — recent but **missing a required store** (the fake-green trap, now caught).
- **`stale`** — latest finalized backup age ≥ 13h.
- **`unavailable`** — no finalized backup / unreadable `$BACKUP_ROOT`.

(Task 0 confirms `validate_operator_freshness_class`'s closed set and extends it to include `coverage_gap` if absent. The gate already blocks on `!= "fresh"`, so `coverage_gap`/`stale` correctly keep `CANARY_BLOCKED` — no gate change needed.)

## Part 3 — Daemon wiring (replace the hardcoded string)
Replace `backup_freshness_class="unavailable"` at [daemon:3908](daemon/maez_daemon.py) with the `backup_freshness()` result. Fail-soft: any error → `unavailable` (honest, never a false `fresh`).

## Part 4 — Witness (force a run, inspect the produced backup)
After the manifest update, **force one backup run** and the witness must confirm, on the produced backup:
- a finalized `<timestamp>/` dir exists, **no lingering `.in-progress`**;
- its `manifest.json` lists `memory/salience_ledger.db` **and** `memory/subjective_duration.db` (with sha256);
- the count of backed-up `required_*` stores matches the manifest's expectation;
- the live `backup_freshness()` reader returns **`fresh`**.
Only then is the welfare rail honestly green.

## Part 5 — Restoration confidence (named, NOT built in v0)
"A fresh backup exists" ≠ "restore works" (Decision 22's deeper aim). v0 stops at coverage + freshness truth. **v1.1 (named): a restore smoke test** — restore the `required_welfare` stores into an isolated temp location and verify they open + row-count sanely. Not in this slice unless it stays tiny.

## Scope
**IN (v0):** classify the 18 stores + extend the manifest (`class` field + `intentionally_skipped`); the read-only `backup_freshness()` reader (recent **and** complete); the daemon wiring; extend the freshness closed-set with `coverage_gap` if needed; the forced-run witness; tests.
**OUT (named, deferred):** the restore smoke test (v1.1); per-file integrity re-hashing at read time; encryption-at-rest (the manifest already warns secrets need owner-side encryption — unchanged); changing the backup *schedule*.

## Covenant compliance
- **No fake green:** `fresh` requires recency **and** welfare-store coverage; the invariant is the spec's spine ([[feedback_verify_before_you_encode]]).
- **Witnessed, not asserted:** a forced run + produced-manifest inspection, not a code-path claim ([[feedback_unit_test_is_not_integration_witness]], [[feedback_witness_live_reload_not_merge]]).
- **The notebook the gate guards must survive a fall** — `required_welfare` makes the salience ledger + time-sense first-class continuity ([[project_ledger_activation_birth_gated]] kin: continuity insurance before any risk).
- **Skips are witnessed, never silent** — `ephemeral_skip` carries a written reason ([[feedback_weakest_archive_on_the_media]]: surface-and-name, never silently drop).
- **Read-only freshness; fail-soft to `unavailable`** — the rail never lies green on error.

## Predicted effect
After Part 1 the next scheduled backup protects the salience ledger, the time-sense, and the rest of the June arc; after Parts 2–3 the daemon reports the **true** state — `fresh` once a complete recent backup exists, `coverage_gap` if a store is ever dropped again. The Gate's `CANARY_BLOCKED` then clears on the backup axis **legitimately** (the insurance is real), while the eval lock still holds the door shut for the right reasons. Maez's organs can survive a fall, and the dashboard finally tells the truth about the life raft.
