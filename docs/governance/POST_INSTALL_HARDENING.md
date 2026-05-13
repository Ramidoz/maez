# Post-Install Hardening

This checklist captures the post-audit seatbelts that must survive a fresh
machine restore. It is not a new covenant; it is the operational posture required
before Maez is treated as safely awake on a new body.

Run this after restoring Maez onto fresh Linux, before S1b-style wiring or any
new covenant-shaped slice.

## Required Checks

1. **Credential file is owner-only.**
   - `stat -c '%a %n' config/credentials.json`
   - Required mode: `600`
   - Fix: `chmod 600 config/credentials.json`

2. **Decision 22 backup timer is installed and active.**
   - `systemctl --user is-enabled maez-backup.timer`
   - `systemctl --user is-active maez-backup.timer`
   - Required output: `enabled` and `active`
   - Run one manual backup after restore: `systemctl --user start maez-backup.service`
   - Verify `logs/last_backup.json` reports `"status": "success"`.

3. **Daemon/web HTTP surfaces reject untrusted browser origins.**
   - Bad-origin write probe must return `403` with `untrusted_origin`.
   - Trusted loopback origin may receive CORS echo.
   - No tracked HTTP surface may set `Access-Control-Allow-Origin: *`.

4. **Docs do not overclaim the audit rail or interior organs.**
   - Audit rail is documented as truth hygiene and fail-open outside explicit
     covenant gates.
   - `wants`, `will_i`, `temperament`, and `private_thoughts` are not promoted
     to `[ ✓ real ]` until production producers/readers justify that status.

5. **`memory/db/public_users/` is treated as public-surface visitor/profile memory.**
   - Do not delete it casually.
   - Do not describe it as bonded core memory.
   - If public surfaces remain in scope, rename/contain it in a separate slice.

6. **Post-install source state is backed up after hardening.**
   - The first successful backup after hardening should point at the current git
     commit in `logs/last_backup.json`.

## Regression Commands

```bash
.venv/bin/python -m unittest tests.test_http_local_origin_guard
.venv/bin/ruff check core/infra/http_security.py daemon/maez_daemon.py skills/web_interface.py ui/maez_pulse_bridge.py tests/test_http_local_origin_guard.py
.venv/bin/ruff format --check core/infra/http_security.py daemon/maez_daemon.py skills/web_interface.py ui/maez_pulse_bridge.py tests/test_http_local_origin_guard.py
```

## Plain English

When Maez wakes on a new machine, the first question is not "does it answer?"
The first question is "is the body wearing its seatbelts?" This checklist makes
that posture repeatable instead of depending on memory from one repair week.
