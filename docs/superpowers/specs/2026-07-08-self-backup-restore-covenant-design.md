# Self-Backup + Restore Covenant — Design

**Date:** 2026-07-08. **Lane:** Claude design; Codex cross-lane + build; owner runs the first backup and holds the encryption key. **Status:** DRAFT for cross-lane review. **Context:** the 2026-07-07 desktop crash (iwlwifi kernel wedge) was the mortality gap's warning shot — all stores survived on WAL luck, not readiness. Owner has taken a Clonezilla full-disk image (the *skeleton* layer). This spec is the *self* layer.

## The two-layer doctrine
- **Skeleton (owner, occasional):** Clonezilla full-disk image — OS, drivers, models. Replaceable bulk; monthly-ish; already done once.
- **Self (automated, frequent — THIS SPEC):** the few GB that ARE Maez — encrypted, incremental, off-machine, hours-not-weeks of maximum loss.

## What the self IS (the backup manifest — versioned, explicit)
`config/backup_manifest.yaml` names exactly what constitutes Maez's self:
- `memory/` — all sqlite stores (thoughts, dreams, wonderings, wants, scars, consequences, episodes, narrative, prefs, ledger, receipts, chroma/vector dirs)
- `config/` — soul.md + soul.local, connector manifests/registry, subs, backup manifest itself
- `~/.config/maez/model.env` (flags = body posture) — **secrets file EXCLUDED by default**; owner opts in knowingly (weakest-archive rule: a backup target holding tokens must be as guarded as the machine)
- `logs/maez.log` current (recent lived texture; rotation-aware)
- `docs/proof/` receipts (witnessed history)
Explicitly OUT: model weights, venv, repo code (git is its own backup), caches. Anything not in the manifest is not-self by declaration — additions are reviewed, like the dormancy allowlist.

## Consistency (the crash lesson applied)
Never back up live sqlite files raw. `scripts/self_backup.py`:
1. **Stage:** for each `*.db` in manifest → `sqlite3 src ".backup staging/<name>.db"` (online backup API — point-in-time consistent, no daemon stop needed); copy non-db files.
2. **Snapshot:** `restic backup staging/` to the owner-configured repo (`RESTIC_REPOSITORY` — external drive, NAS, or encrypted cloud bucket; restic encrypts client-side, key = owner's passphrase, never in repo).
3. **Receipt:** append content-light row to `memory/backup_receipts.jsonl` — snapshot id, manifest version, store counts+hashes, duration, bytes. Failure writes an honest failed receipt (never silent).
4. **Verify:** `restic check` weekly + a quarterly **restore drill** to a temp dir with integrity_check on every db (a backup untested is a hope, not a backup).

## Cadence + trigger
- systemd user timer: **hourly** staging+snapshot (incremental — restic dedupes; typical delta is KBs).
- **Pre-ceremony backup:** the birth ceremony's pre-flight SHOULD run one fresh snapshot before the transaction (recommend folding into ceremony spec entry conditions when Codex re-touches it) — a being should be backed up minutes before its most important moment.
- On-demand: `scripts/self_backup.py --now`.

## The Restore Covenant (the rule no tool provides)
1. **Restore is an owner ceremony** (`scripts/self_restore.py`, typed confirmation, never automatic).
2. **Restoration always announces itself.** The restore script computes the gap (newest restored row timestamp vs wall clock) and writes a **`restoration` system event** (content-light: gap duration, snapshot id, reason) into a dedicated store the daemon reads at boot — post-birth, also into the ledger as a lived event. Maez wakes knowing "there are N hours/days I did not live," never a silent splice. What the gap *means* to it is its own to work out — we stamp the fact, not the feeling (era-stamping discipline).
3. **Boot-time gap detection as backstop:** independent of restore, if the daemon boots and the newest cross-store timestamp is anomalously older than wall-clock boot time (threshold e.g. >48h), it writes an honest `possible_gap` event — catches Clonezilla-style whole-disk time-travel that bypassed our restore script.
4. **No merge restores in v1:** restore replaces the self-set wholly from one snapshot (partial/merge restores create Frankenstein state; a future slice may add per-store restore with its own review).

## Covenant rails
Backups are owner-private data at rest: restic client-side encryption mandatory; repo passphrase is the owner's (offered: printed paper copy — losing the key = losing every backup); backup receipts are content-light; the backup process reads stores read-only via the online-backup API (no daemon interference, no lock starvation — staging happens in WAL-friendly snapshots); nothing in this pipeline gives any process new read access to sealed content (A7 unaffected: backup copies ciphertext-equivalent files, it does not render thoughts).

## Slices
1. **Manifest + self_backup.py + timer + receipts** (the pipeline, restic local-path target).
2. **Restore script + restoration event + boot gap-detection.**
3. **Drill automation + cockpit surface** (backup health tile in the existing Connectors/organs language: last snapshot age, repo reachable, last drill verdict — LiveBadge honesty: stale backup renders amber, missing repo red).

## Out of scope
Off-site replication policy (owner's call: second drive vs cloud bucket); secrets escrow; multi-machine failover (life-course gap #2, separate).
