# Restore Drill Timer — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). **Do NOT merge, enable timers, or restart anything** — stop at the review gate. Then the owner (or Claude, authorized) renders + enables the unit and witnesses.

**Goal:** Schedule the existing read-only restore smoke test (`python3 -m scripts.backup.drill --smoke`) on a systemd user timer, mirroring the backup timer — so restorability stays **continuously witnessed** ("proved once" → "kept true"). Daily cadence, failures visible, no live touch.

**Architecture:** Two new template units (`scripts/maez-backup-drill.template.service` + `.timer`) that mirror `maez-backup.template.*`, rendered + enabled by `scripts/install.sh`. No Python behavior change — the drill already exists and is read-only/temp-only.

**Covenant rails:** the drill is read-only + temp-only (already proven); a **failed** drill must be **visible** (non-zero exit → systemd `failed` state + a log), never silent; cadence owner-adjustable; no change to the backup, the daemon, or live `memory/`.

---

### Task 0: Confirm the install pattern + the drill's exit semantics (no production code)

- [ ] **Step 1: Confirm `--smoke` exits non-zero on failure** (so a bad drill surfaces as a failed service)

Run:
```
cd /home/rohit/maez
grep -nE "sys.exit|return [12]|raise SystemExit|--smoke|verdict|overall_status|argparse|add_argument" scripts/backup/drill.py scripts/backup/__main__.py 2>/dev/null | head
```
Confirm the `--smoke` CLI returns a **non-zero exit code when `overall_status != pass`** (and 0 on pass). If it does not, that is a one-line fix in this slice (the timer's whole value is that a failure is visible). Record the exact module path for `ExecStart` (`-m scripts.backup.drill` vs a `__main__` hook).

- [ ] **Step 2: Confirm how `install.sh` renders + enables units**

Run:
```
grep -nE "template|MAEZ_HOME|MAEZ_USER|sed|systemctl --user|daemon-reload|enable|\.service|\.timer" scripts/install.sh | head -30
```
Record the placeholder set (`__MAEZ_HOME__`, `__MAEZ_USER__`, `__MAEZ_HOME_USER__`, …) and the render+enable mechanism, so the drill units plug into the same flow.

---

### Task 1: The drill template units (mirror the backup units)

**Files:**
- Create: `scripts/maez-backup-drill.template.service`
- Create: `scripts/maez-backup-drill.template.timer`

- [ ] **Step 1: Write the service template**

```ini
[Unit]
Description=Maez restore-drill smoke test — verify the latest backup actually restores (welfare rail)
Documentation=file://__MAEZ_HOME__/docs/operations/hardware_backup.md
After=maez-backup.service

[Service]
Type=oneshot
User=__MAEZ_USER__
Group=__MAEZ_USER__
WorkingDirectory=__MAEZ_HOME__
Environment=PYTHONUNBUFFERED=1
Environment=MAEZ_ROOT=__MAEZ_HOME__
Environment=MAEZ_BACKUP_ROOT=__MAEZ_HOME_USER__/maez-backups
# Read-only + temp-only: restores into a temp dir, opens DBs read-only,
# runs PRAGMA quick_check, writes a report, touches no live state. A
# FAILED drill is the signal — non-zero exit marks the service failed.
ExecStart=__MAEZ_HOME__/.venv/bin/python3 -m scripts.backup.drill --smoke
TimeoutStartSec=10min
StandardOutput=append:__MAEZ_HOME__/logs/backup_drill.log
StandardError=append:__MAEZ_HOME__/logs/backup_drill.log
```

- [ ] **Step 2: Write the timer template**

```ini
[Unit]
Description=Fire maez-backup-drill.service daily (restorability kept-true witness)

[Timer]
# Daily at 03:00 — after the 00:00 backup, so the drill verifies a
# freshly finalized snapshot. Owner-adjustable: edit the rendered file
# directly (same convention as maez-backup.timer).
OnCalendar=*-*-* 03:00:00
# Fire on next boot if the machine was off at the scheduled time.
Persistent=true

Unit=maez-backup-drill.service

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Commit**

```bash
git add scripts/maez-backup-drill.template.service scripts/maez-backup-drill.template.timer
git commit -m "feat(backup): restore-drill timer units (daily restorability witness)"
```

---

### Task 2: Wire the drill units into `install.sh`

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: Add the drill units to the render+enable flow**

Mirror exactly what `install.sh` does for `maez-backup.template.service`/`.timer` (same placeholder substitution → `~/.config/systemd/user/maez-backup-drill.{service,timer}`, `systemctl --user daemon-reload`, `systemctl --user enable --now maez-backup-drill.timer`). If `install.sh` iterates a list of unit basenames, add `maez-backup-drill` to that list; if it renders each explicitly, add the two analogous lines. **Do not change the backup units.**

- [ ] **Step 2: Verify the render is well-formed (dry, no enable)**

Run (render to a temp dir, confirm no leftover placeholders — does NOT enable):
```
cd /home/rohit/maez
for t in service timer; do
  sed -e "s#__MAEZ_HOME__#/home/rohit/maez#g" -e "s#__MAEZ_USER__#rohit#g" -e "s#__MAEZ_HOME_USER__#/home/rohit#g" \
    scripts/maez-backup-drill.template.$t > /tmp/maez-backup-drill.$t
  grep -q "__MAEZ" /tmp/maez-backup-drill.$t && echo "LEFTOVER PLACEHOLDER in $t" || echo "$t renders clean"
done
/home/rohit/maez/.venv/bin/python -c "import configparser; [configparser.ConfigParser(strict=False, delimiters=('=',)).read('/tmp/maez-backup-drill.'+t) for t in ('service','timer')]; print('units parse')"
```
Expected: both render clean, units parse.

- [ ] **Step 3: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(backup): install + enable the restore-drill timer alongside the backup timer"
```

---

### Task 3: Handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-restore-drill-timer-handoff.md`**

Record: Task 0 findings (the `--smoke` exit semantics; the install.sh mechanism); branch tip; the render-dry-run output. **The owner/Claude post-merge enable + witness (authorized):**
```
# render + enable via install.sh (or the two rendered units), then:
systemctl --user daemon-reload
systemctl --user enable --now maez-backup-drill.timer
systemctl --user list-timers maez-backup-drill.timer        # scheduled, next ~03:00
systemctl --user start maez-backup-drill.service            # one manual fire
systemctl --user status maez-backup-drill.service           # Result=success (or visibly failed)
tail -5 logs/backup_drill.log                               # the run logged
ls -t logs/backup_drill_*.json | head -1                    # a fresh report artifact
```
Confirm: timer scheduled; a manual run produces a `pass` report; **a failure would show as a failed unit (not silent).** State plainly: NOT merged, NOT enabled.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-restore-drill-timer-handoff.md
git commit -m "docs(backup): hand off restore-drill timer"
```
Hand back to Claude for review (units mirror the backup pattern; daily/owner-adjustable; **failure is visible, not silent**; read-only/temp-only unchanged; backup units untouched). Then enable + witness.

---

## Self-Review

**Spec coverage:** drill scheduled on a timer mirroring the backup units (Tasks 1–2 ✓); daily, owner-adjustable cadence offset after the 00:00 backup (timer template ✓); failure visible — non-zero exit → failed unit + log (Task 0 confirms/fixes the exit code; service logs to `backup_drill.log` ✓); read-only/temp-only unchanged (no Python behavior change ✓); install.sh integration without touching the backup units (Task 2 ✓); witnessed enable + manual run + report (Task 3 ✓).

**Placeholder scan:** the `__MAEZ_*__` tokens are the *intended* template placeholders (rendered by install.sh) — verified resolved by the Task 2 dry-run; no stray TBDs.

**Type consistency:** unit names `maez-backup-drill.{service,timer}` consistent across the templates, install.sh, and the witness commands; `ExecStart` module path matches Task 0's confirmed entry point.
