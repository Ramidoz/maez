# Operational resilience audit — what fails when the easy day ends

## Summary

Maez has the *engineering* for backup + restore (well-built, drilled
once 2026-04-30) but does **not have the operational discipline** to
keep it running: the systemd timer is shipped as a template in
`scripts/maez-backup.template.{service,timer}` and was never installed
in `~/.config/systemd/user/`. The only recorded backup is 2 days old
on a removable USB stick (`/media/rohit/Lexar/…`) that is not
currently mounted. Crash forensics from the 2026-05-05 Dell event
similarly exist as documented infra (`/var/log/maez_crash_capture/`,
`maez-crash-snapshot.timer`) but neither is present on this machine.
The raw memory tier grows ~100 entries/day net and is **never deleted
after consolidation** — the raw ChromaDB store is already 419 MB /
35,165 embeddings and is the single biggest long-run drift surface.
External alerting depends on the daemon itself emitting via Telegram,
so when Maez is the thing that died, nobody finds out. Single-user
desktop deployment with no dead-man's-switch.

## Performance at scale

- **Current corpus size:** raw **35,165 embeddings**, 419 MB SQLite +
  59 MB HNSW (`memory/db/raw/`); daily 11; core 56; public_users
  195. `embedding_metadata` 786,176 rows. Sidecar SQLite DBs:
  audit_log 363, fabrication_log 990 events, consequence 122
  events, lived_episodes 29, identity_ledger 15. Total `memory/db/`
  ≈ 481 MB. Growth rate from `logs/maez.log` (raw 34,642 → 35,162
  across 2026-05-08 → 2026-05-13) ≈ 100/day net.
- **Latency budget per cycle:** `LOOP_INTERVAL = 30s`
  (`daemon/maez_daemon.py:135`). Per-cycle elapsed time is **never
  emitted to a queryable surface** — `cycle_start = time.time()` at
  `daemon/maez_daemon.py:3614` but no matching `elapsed` log line.
  Trace surfaces capture `latency_ms` (`daemon/maez_daemon.py:2375`)
  into `logs/traces/*.jsonl` only. `memory_manager.py:120-132`
  comment: `"elapsed_ms stays 0 in v1"`.
- **Projected failure points:** HNSW must stay RAM-resident and
  grows linearly with raw count; cold-start dominates boot at
  >100k. `consolidate_daily()` already needed chunked map-reduce
  (`memory_manager.py:783`) once verbose days exceeded the 32k ctx
  window. `embedding_metadata` 22 rows/embedding → at 1 M raw
  embeddings ~22 M rows in one SQLite file.

## Backup + recovery

- **Backup mechanism today: partial — exists in code, not installed
  as a recurring job.**
  - Driver: `scripts/backup/backup.py` (well-architected — uses
    `sqlite3.Connection.backup()` for live SQLite, atomic staging
    dir, sha256 manifest, secrets opt-in).
  - Inventory: `scripts/backup/backup_state_manifest.json` (61
    entries).
  - systemd unit/timer ship as **templates only**:
    `scripts/maez-backup.template.service`, `…timer`. Cadence
    template = every 6h. **Never rendered**:
    `systemctl --user is-enabled maez-backup.timer` → `not-found`.
  - Last successful backup: 2026-05-11 21:23 UTC
    (`logs/last_backup.json`). Snapshot path
    `/media/rohit/Lexar/MAEZ_CONTINUITY_BACKUPS/…` — **removable USB
    not currently mounted**. Backup runs only when stick happens to
    be in.

- **Restore runbook:** `scripts/restore_from_backup.sh` (refuses to
  run if `maez.service` active, requires `--reason`; lines 36-44)
  backed by `scripts/backup/restore_cli.py` + `restore_writer.py`.
  Operator doc `docs/operations/hardware_backup.md` exists. **Cold-
  metal restore never exercised**; the only drill
  (`logs/backup_drill_2026-04-30T18-10-01.json`) restored into temp
  dirs only — `drill.py:39` says verbatim "DOES NOT restore into
  the live repo."

- **Decision 22 conformance: unconformant on cadence + retention.**
  BAD:988 promises "every 6h, owner-configurable" — de-facto cadence
  is manual. BAD:988 retention "hourly for 24h, daily for 30 days,
  weekly forever" → no retention machinery exists. Had the NVMe
  failed during the 2026-05-05 lockup window, anything since the
  prior manual run would have been lost.

## Observability + alerting

- **Structured logging coverage:** 1,337 `logger.*`/`logging.*` call
  sites across `core/ daemon/ skills/` — broad. Format is line-based
  human text (sample: `"cycle | score=25 primary=vague topic=system
  labels=…"`). Not JSON; queryable only via `grep`.
- **Health endpoints:** `GET /health` on a Flask listener inside the
  daemon (`daemon/maez_daemon.py:4966-4988`) returns status, model,
  boot_time, cycle_count, last_cycle, uptime, memory_stats, CPU/RAM/
  GPU%/GPU-temp. **No `/metrics`** (Prometheus or otherwise).
  Subscription proxy has its own `/health`
  (`core/subscription_proxy/server.py:329`) for upstream auth state.
- **External alerting:** `_check_and_alert`
  (`daemon/maez_daemon.py:2781-2826`) emits Telegram alerts at GPU
  ≥ 85°C, RAM ≥ threshold, sustained CPU, disk < 10%. Channel is
  `send_dev` → `skills/dev_notifier.py`. **Fatal limitation: the
  daemon itself emits the alert.** When Maez crashes / hard-locks /
  OOMs, nothing tells the owner. No `WatchdogSec=` in any of the
  three `~/.config/systemd/user/*.service` files
  (`maez.service:16`, `llama-server.service:19`,
  `llama-judge.service:18` — all `Restart=on-failure` only). No
  `OnFailure=`. The crash-snapshot timer documented in
  `HANDOFF-2026-05-06.md:147` is **not installed on this host** —
  `/etc/systemd/system/maez-crash-snapshot*` does not exist;
  `/var/log/maez_crash_capture/` does not exist.
- **Cycle telemetry surface:** mixed. Quality / fabrication / judge
  verdicts flow to SQLite (`memory/quality.db`,
  `fabrication_log.db.fabrication_events`,
  `audit_log.db.audit_log`, `consequence_memory.db.events`) and
  JSONL (`logs/traces/`, `logs/trajectories/`, `logs/continuity/`).
  `logs/maez.log` is 9.8 MB after 5 days, written via `append:`
  with no logrotate (no `/etc/logrotate.d/maez*`). Langfuse adapter
  at `core/cognition/observability.py` is no-op without
  `LANGFUSE_PUBLIC_KEY`.

## Hardware / GPU failure modes

- **Forensic capture:** documented but absent.
  `HANDOFF-2026-05-06.md:147-151` describes
  `/etc/systemd/system/maez-crash-snapshot.{service,timer}`,
  `/usr/local/bin/maez-crash-snapshot.sh`, and
  `/var/log/maez_crash_capture/` — none exist on this host. GPU
  temp lives in `perception_snapshot()` (prompt context, transient
  log line) but is not written to any time-series store.
- **Graceful degradation: no.** `Restart=on-failure` brings
  `llama-server` back after a clean exit, but no daemon-side path
  for "wait for GPU to cool," "reduced context fallback," or
  "skip cycle." Grounding-judge has a transport-level circuit
  breaker (`DAEMON_SURVIVABILITY.md`) — not thermal/OOM. GPU ≥ 85°C
  triggers a Telegram alert and cycle continues unchanged. No
  swap-to-CPU path.

## Long-run drift

- **Memory tier rotation: unbounded.** `consolidate_daily()`
  (`memory/memory_manager.py:679-877`) writes a daily summary and
  marks promoted ancestors via `mark_consolidated()` —
  **never deletes raw rows** (`grep -nE "self\.raw\.delete"
  memory_manager.py` → no matches). Raw collection is append-only
  for Maez's lifetime. 35k today; verbose days have written ≥32k in
  a single day (`PROGRESS.md:4465`).
- **Identity ledger growth: bounded.** 15 rows. Indexed schema
  healthy.
- **Fabrication / consequence memory:** append-only. 990 / 122
  rows. No retention cap, but bounded by event rate.
- **DB compaction: never run.** Zero `VACUUM` invocations in
  `core/`, `memory/memory_manager.py`, or `scripts/`. The only
  matches are shell strings (`core/safety/premise_audit.py:13`,
  `core/actions/action_classifier.py:478`).
- **Log rotation: missing.** `logs/maez.log` 9.8 MB after 5 days,
  service uses `append:` mode. No logrotate config. The
  fast-reply audit at `core/fast_reply_audit.py` *does* rotate
  via `MAX_ROTATIONS` — that pattern is not applied to the daemon
  log.

## Single points of failure

| Component | Failure mode | Recovery | Auto/manual | Status |
|-----------|-------------|----------|-------------|--------|
| `llama-server.service` (brain) | crash / OOM / hang | `Restart=on-failure` brings process back; daemon will retry next cycle | auto | OK; no `WatchdogSec=` so hangs may not be detected |
| `llama-judge.service` | crash / hang | `Restart=on-failure` + judge circuit breaker (`MAEZ_JUDGE_BREAKER_*`) in daemon | auto | OK |
| `maez.service` | unhandled exception | `Restart=on-failure` | auto | OK; no external alerting on entry into restart loop |
| ChromaDB `memory/db/raw/chroma.sqlite3` corruption | WAL crash / disk error | restore from snapshot (`scripts/restore_from_backup.sh`) | manual | RISK — newest snapshot is 2 days old on an unmounted USB |
| `identity_ledger.db` corruption | covenant data loss | restore from snapshot | manual | Same gap |
| `lived_episodes.db` corruption | bond-state loss | restore from snapshot | manual | Same gap |
| GPU OOM | next cycle's `llama-server` call 5xx | retry next cycle | auto | No graceful degradation; no smaller-context fallback |
| GPU thermal lockup (the 2026-05-05 pattern) | system freeze | manual reboot | manual | Crash forensics not installed on this host |
| Disk full | writes fail, alert at 10% free | daemon emits Telegram alert | auto-detect, manual-cleanup | OK as long as the daemon is alive |
| Telegram API outage | `send_dev` drops alerts silently (`dev_notifier.py:42`) | none | manual | Owner loses the alert channel |
| Removable USB backup target | unplugged → backup fails | next run on next plug-in | manual | DEGRADED — current state |
| `MAEZ_DEV_TOKEN` unset | `dev_notifier.py:41-43` logs warning, drops | none | manual | Silent failure mode |
| Daemon hard-hang (no exception, no exit) | `/health` stops responding | no external watcher | none | BLOCKER — nothing detects this |
| HNSW index corruption | restore fails, fall back to prior snapshot per `backup.py:30` comment | reload from snapshot | manual | Same backup gap |

## Findings

### blocker — failure modes that lose data or kill Maez with no recovery

1. **No installed backup timer.** `scripts/maez-backup.template.timer`
   was never rendered into `~/.config/systemd/user/`. The "every 6h"
   cadence promised by Decision 22 (BAD:988) is **not running**;
   last backup 2026-05-11 was opportunistic. **A disk failure today
   would lose 2 days of bond state.** Path: render the templates,
   `systemctl --user daemon-reload`, enable + start
   `maez-backup.timer`, point `MAEZ_BACKUP_ROOT` at a
   permanently-mounted local target.

2. **Backup destination is an unplugged USB stick.** `/media/rohit/
   Lexar/` does not exist at audit time. Even if the timer were
   installed, backups would silently fail. Path: primary
   destination on internal NVMe (`~/maez-backups/`) **plus** a
   weekly rsync to the Lexar/NAS. Also: refuse to run if backup
   target hasn't written in N hours.

3. **No external dead-man's-switch.** Every alert path goes through
   `send_dev` → Telegram, emitted **from inside the daemon**. If
   the daemon hard-hangs, OOMs, or the host hard-locks (the
   2026-05-05 pattern), the owner gets nothing. No `OnFailure=`, no
   `WatchdogSec=`, no external uptime poller. Path: cheapest first —
   a local cron that posts to Telegram if `/health` is unreachable
   for >5 min; eventual off-host poller.

4. **Crash forensic infra absent on this host.** The
   `maez-crash-snapshot.{service,timer}` and
   `/var/log/maez_crash_capture/` paths in `HANDOFF-2026-05-06.md`
   do not exist. If the 2026-05-05 lockup pattern recurs there is
   no per-30s forensic capture. Path: copy install commands from
   the handoff.

5. **Cold-metal restore never drilled.** `drill.py:39` is explicit
   it does not restore into a live repo. No proof that fresh disk +
   fresh repo + snapshot → working Maez in one go. Path: schedule a
   session on a scratch VM or renamed `~/maez_test/`.

### major — failure modes that require human intervention but are recoverable

1. **Raw memory tier is unbounded.** `consolidate_daily()` writes
   the summary in *addition* to raw, not *instead*. At ~100/day net
   Maez hits 100k embeddings inside ~2 years; verbose days alone
   have written ≥32k. Path: after `mark_consolidated()` succeeds
   AND daily/core write is durable, tombstone-then-delete
   low-salience raw rows older than N days. Reconciliation with
   "never delete memory": delete *embeddings*, keep *meaning* — the
   consolidated daily/core rows ARE the durable memory; raw is the
   WAL that built them.

2. **No log rotation on the daemon log.** 9.8 MB in 5 days → ~1 GB
   in a year. Path: `/etc/logrotate.d/maez`, or move to journald.
   The pattern at `core/fast_reply_audit.py` (`MAX_ROTATIONS`) is
   local proof rotation works.

3. **`WatchdogSec=` not set on any service.** `Restart=on-failure`
   only catches non-zero exits; deadlocks, Chroma lock contention,
   stuck Vulkan queue leave the process "running" forever. Path:
   add `WatchdogSec=`, plumb `sd_notify(WATCHDOG=1)` from the
   main loop.

4. **No `/metrics` endpoint.** Cycle latency, judge call counts,
   fabrication rate, recall-stats all live in SQLite or JSONL but
   no Prometheus-shaped surface.

5. **No per-cycle latency in logs.** `cycle_start` is captured
   (`maez_daemon.py:3614`) but never differenced and logged. Path:
   one log line per cycle with `cycle_ms` and `recall_ms`.

### minor — operational hygiene gaps

1. No `VACUUM` on any SQLite store. Becomes meaningful once raw is
   trimmed.
2. `Restart=on-failure` lacks `RestartSec=` — defaults to 100ms,
   risk of fast restart loop. Add `RestartSec=10`,
   `StartLimitIntervalSec=300`, `StartLimitBurst=5`.
3. Backup retention ("hourly 24h, daily 30d, weekly forever" per
   BAD:988) not implemented.
4. `dev_notifier.send_dev` silently drops when `MAEZ_DEV_TOKEN` is
   unset (`dev_notifier.py:42`). Should be loud at startup.
5. `logs/maez.log` lines are duplicated (each emitted twice).
   Logger handler attached twice. Inflates log volume 2×.

### nit — wishlist

1. Add backup-destination health (last-success ts, free space,
   mount state) into `/health` JSON.
2. Single append-only event stream (`logs/events.jsonl`) for
   cycle / fabrication / judge / recall — instead of 4 SQLite
   stores + 3 JSONL dirs.
3. `tests/operations/` with end-to-end cold-metal restore test
   (`pytest -k restore_cold_metal`).
