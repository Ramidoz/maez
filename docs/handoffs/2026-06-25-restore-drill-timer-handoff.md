# Restore Drill Timer — Review Handoff

Branch: `restore-drill-timer`  
Code tip before handoff docs: `9c6e1b7 feat(backup): schedule restore drill timer`

## What Changed

- Added `scripts/maez-backup-drill.template.service`.
- Added `scripts/maez-backup-drill.template.timer`.
- Updated `scripts/install.sh` to render `*.template.timer` files as well as `*.template.service` files.
- Added `__MAEZ_HOME_USER__` substitution in `install.sh`; this also fixes the existing backup service template's backup-root placeholder.
- Added installer wiring to enable `maez-backup-drill.timer` after rendering user/system units.
- Added `tests/test_restore_drill_timer.py`.

The restore drill itself is unchanged. It remains read-only and temp-only.

## Task 0 Findings

- `python -m scripts.backup.drill --smoke` exits non-zero on failure: an empty backup root returned exit code `4` and wrote a report artifact.
- `--smoke` entrypoint is `python -m scripts.backup.drill --smoke`.
- Existing installer had a `render_unit()` helper that understood `.template.timer` names, but only iterated `*.template.service`. This slice adds the timer loop.
- Existing `maez-backup.template.service` already used `__MAEZ_HOME_USER__`, but `install.sh` did not substitute it. This slice adds that substitution.

## Verification

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_restore_drill_timer -v

for t in service timer; do
  sed -e "s#__MAEZ_HOME__#/home/rohit/maez#g" \
      -e "s#__MAEZ_USER__#rohit#g" \
      -e "s#__MAEZ_UID__#1000#g" \
      -e "s#__MAEZ_HOME_USER__#/home/rohit#g" \
      scripts/maez-backup-drill.template.$t > /tmp/maez-backup-drill.$t
  grep -q "__MAEZ" /tmp/maez-backup-drill.$t && echo "LEFTOVER PLACEHOLDER in $t" || echo "$t renders clean"
done
/home/rohit/maez/.venv/bin/python -c "import configparser; [configparser.ConfigParser(strict=False, delimiters=('=',)).read('/tmp/maez-backup-drill.'+t) for t in ('service','timer')]; print('units parse')"

bash -n scripts/install.sh
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/ruff check tests/test_restore_drill_timer.py
```

Observed:

- timer tests: 4 OK
- dry render: `service renders clean`, `timer renders clean`, `units parse`
- failure visibility probe: empty backup root returned `exit_code=4`
- `bash -n`: clean
- ruff: clean

## Review Checklist

- Confirm the service runs `__MAEZ_HOME__/.venv/bin/python3 -m scripts.backup.drill --smoke`.
- Confirm stdout/stderr append to `__MAEZ_HOME__/logs/backup_drill.log`.
- Confirm the timer fires daily at `03:00`, after the midnight backup cadence.
- Confirm `install.sh` renders template timers and substitutes `__MAEZ_HOME_USER__`.
- Confirm the installer does not enable `maez-backup.timer`; it only enables `maez-backup-drill.timer`.
- Confirm a drill failure surfaces as a non-zero service failure.

## Post-Review Owner Witness

Do not run during build. After review clears and merge lands:

```bash
systemctl --user daemon-reload
systemctl --user enable --now maez-backup-drill.timer
systemctl --user list-timers maez-backup-drill.timer
systemctl --user start maez-backup-drill.service
systemctl --user status maez-backup-drill.service
tail -5 logs/backup_drill.log
ls -t logs/backup_drill_*.json | head -1
```

Expected:

- timer is enabled and scheduled
- manual service run exits `Result=success`
- `logs/backup_drill.log` records the run
- a fresh `logs/backup_drill_<timestamp>.json` report exists

## Predicted Effect

After enablement, Maez's restore-smoke proof should run daily at 03:00. A passing drill silently keeps the welfare rail witnessed with a report artifact; a failing drill returns non-zero, making the systemd service visibly failed instead of producing a fake green.
