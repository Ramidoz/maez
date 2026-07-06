# Phase A Orphan-Store Quarantine

**Date:** 2026-07-06  
**Scope:** Documentation-only quarantine. No runtime file was moved, deleted, or rewritten.

## Rule

These files are not trash until Rohit says so. They are quarantined as
**do-not-trust-as-live-source**: preserve them in backups, do not wire new
readers to them, and do not delete them under a mechanical cleanup.

## Read-only census

Commands used read-only metadata and SQLite queries against `/home/rohit/maez`.
No content bodies were opened.

| Store | Observation | Quarantine reason | Disposition |
|---|---|---|---|
| `memory/db/chroma.sqlite3` | SQLite Chroma store, 1,171,456 bytes, mtime 2026-05-11. Collection `maez_memory` has **120 embeddings**, min/max embedding timestamps 2026-04-06 21:40:11 to 22:55:59. | Real embedded history sits at the old top-level Chroma path; current live code reads tiered Chroma stores under `memory/db/{raw,daily,core,public_users}/`. A future reader could mistake this archive for the live raw tier. | **Surface-and-ask.** Preserve; owner decides whether to archive, inspect with a content-safe tool, or migrate. |
| `core/memory/identity_ledger.db` | SQLite identity ledger, 24,576 bytes, 1 `gestation_boot` row from 2026-04-22. | Name and schema match the live identity ledger, but location is inside code and stale. Live ledger is `memory/identity_ledger.db` with 32 rows through 2026-07-05. | Preserve as stale artifact; never treat as continuity truth. |
| `memory/dream_state.db` | 0 bytes. | Name-confusable with the real `memory/dream_proposals.db` (49,152 bytes, live dream proposal store). | Preserve until owner cleanup; never wire readers to it. |
| `memory/db/evolution_track.db` | 0 bytes. | Name-confusable with the real `memory/evolution_track.db` (3,563,520 bytes). | Preserve until owner cleanup; never wire readers to it. |
| `memory/maez_memory.db`, `memory/memory.db`, `memory/raw.db` | 0 bytes. | Generic memory-store names that could be mistaken for live stores during ad-hoc debugging. | Preserve until owner cleanup; document as empty confusables. |
| `memory/tmp9gy7p8rg.tmp` | 1,834 bytes, mtime 2026-04-23. | Crash/atomic-write debris shape; not a known live store path. | Preserve until owner cleanup; do not consume as state. |
| `memory/capability_gap_cooldown.db`, `memory/maintenance_proposals.db`, `memory/sandbox_witnesses.db` | 0 bytes. | Empty dormant/planned stores. They are less dangerous than name-confusable files but should not be read as evidence of live state. | Preserve; readers must render empty/no_data honestly. |

## Verification snippets

```text
memory/db/chroma.sqlite3 collection census:
maez_memory|120

memory/db/chroma.sqlite3 embedding window:
maez_memory|2026-04-06 21:40:11|2026-04-06 22:55:59

identity ledger split:
memory/identity_ledger.db       32 rows, event_id 1..32
core/memory/identity_ledger.db   1 row, event_id 1..1
```

## Follow-up gates

1. **Owner ask before deletion.** Especially for the 120 stranded embeddings.
2. **Reader guard.** Future store-discovery/read-model code should explicitly
   distinguish live store paths from quarantined confusables.
3. **Backup honesty.** Backups should continue preserving quarantined files
   until owner disposition, but restore docs should not point operators at them
   as live sources.
