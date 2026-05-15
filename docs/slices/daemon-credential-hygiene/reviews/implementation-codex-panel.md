# Codex Six-Agent Engineering Panel — Daemon Credential Hygiene Implementation

Status: RATIFY-WITH-RECOVERY
Date: 2026-05-14
Reviewed commits: `6ea1cff` implementation + `eb8e7fe` Claude council
Recovery work: post-panel local recovery patch, pre-push

## Verdict

The first implementation did not ratify. The panel found load-bearing
engineering gaps that the Claude covenant council was not sized to catch:

1. subprocesses still inherited the daemon's compatibility-populated secret
   environment;
2. inherited legacy env secrets remained usable in normal mode;
3. web/iPhone ingest mounted a required surface while treating its token as
   optional;
4. rollback did not actually restore the v0 local `.env` path;
5. public web state forwarded credential aggregate health; and
6. scanner and posture tests were too coarse to catch the above.

The recovery patch closes those gaps mechanically and with tests. The final
panel result is **RATIFY-WITH-RECOVERY**.

## Panel Seats

| Seat | Pre-recovery verdict | Primary finding | Recovery closure |
| --- | --- | --- | --- |
| Confucius | REVISE | Legacy process-env secrets remained authoritative; iPhone required token optional; public health forwarded credential aggregate | Normal mode purges secret-shaped inherited env; web requires `MAEZ_IPHONE_INGEST_TOKEN`; public `/api/maez-state` strips credential health |
| Carver | BLOCK | High-risk subprocess calls still inherited full env | All reviewed high-risk subprocess calls pass `env=sanitize_env()`; AST test now enforces per-call env keyword |
| Arendt | REVISE | Active user unit still had `EnvironmentFile=config/.env`; templates are fallback-first rather than LoadCredential-active | Local user unit migrated and backed up; repo templates remain fallback-compatible with no `.env` token posture |
| Ampere | REVISE | Tests were too coarse; scanner allowlist could mask embedded realistic tokens | Tests expanded from string-presence to AST subprocess scanning; fixture allowlist exact-only; service regex fixed |
| Raman | REVISE | Web/iPhone service profile failed late instead of startup | Web interface now requires `MAEZ_IPHONE_INGEST_TOKEN` before route appears alive |
| Bernoulli | BLOCK | Rollback flag was not operational; child env leak remained | Rollback reads restored legacy `config/.env`; child env scrubbing enforced; live restart verified |

## Recovery Details

### Subprocess inheritance

`sanitize_env()` already had the right default-minus-secret shape, but the
first implementation applied it incompletely. Recovery adds explicit sanitized
environments at reviewed high-risk subprocess boundaries:

- `core/actions/action_engine.py`
- `core/actions/tool_loop.py`
- `core/self_dev/__init__.py`
- `skills/web_interface.py`
- `skills/telegram_voice.py`
- `skills/github_publish.py`

The test changed from "file contains `sanitize_env(` somewhere" to an AST walk
that checks every reviewed `subprocess.run`, `subprocess.Popen`,
`subprocess.check_output`, and `subprocess.check_call` call has an `env=`
keyword. This closes the false-confidence gap the panel caught.

### Source authority

Normal mode now purges secret-shaped inherited process env names before
compatibility-populating secrets from approved sources. That means a legacy
`ANTHROPIC_API_KEY` inherited through process env cannot silently remain
usable while health says `rollback_enabled=false`.

`get_secret()` now falls back to `os.environ` only when rollback is enabled.

### Rollback

`MAEZ_SECRETS_DISABLE_NEW_LOADER=1` now reads restored legacy `config/.env`
through `paths.env_file()` and populates the required compatibility env. This
matches the spec runbook's emergency path: restore the pre-migration `.env`,
set the rollback flag, restart, then reopen the hygiene slice.

### Web/iPhone

Because `/api/iphone/ingest` is mounted unconditionally in
`skills/web_interface.py`, `MAEZ_IPHONE_INGEST_TOKEN` is startup-required for
the web process. Recovery moves it from optional to required.

### Public health

Daemon `/health` keeps aggregate credential health for local operator
diagnosis. Public web `/api/maez-state` strips the `credentials` block before
forwarding daemon health.

### GitHub publish argv hygiene

While closing subprocess env inheritance, recovery also removed the old
`https://<token>@github.com/...` remote URL construction from
`skills/github_publish.py`. The remote now uses SSH shape
`git@github.com:<owner>/<repo>.git`, avoiding credential values in git argv or
`.git/config`.

## Verification

RED checks observed before recovery:

- credential test suite failed on inherited legacy env, rollback, iPhone
  startup requirement, scanner fixture masking, and specific subprocess sites.
- the GitHub remote URL test failed on token-in-remote construction.

GREEN checks after recovery:

- `.venv/bin/python -m unittest tests.test_daemon_credential_hygiene -v`:
  23 tests OK.
- Focused nearby runtime suite:
  `.venv/bin/python -m unittest tests.test_daemon_credential_hygiene
  tests.test_project_panel tests.test_presence_observe_bounded
  tests.test_m1_daemon_wiring tests.test_daemon_shutdown_lifecycle
  tests.test_hardware_backup`: 80 tests OK.
- Full suite:
  `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`:
  3474 tests OK, skipped=3.
- `git diff --check`: clean.
- Targeted `ruff check` on touched implementation/test files: clean.

Live checks after local user-unit migration:

- `systemctl --user restart maez.service`: 1.5s.
- Installed user unit no longer contains `EnvironmentFile=/home/rohit/maez/config/.env`.
- `ps eww` on the daemon PID shows no Decision-26 secret names.
- `/health` reports:
  - `credentials.source=secrets-local-env`
  - `required_present=true`
  - `missing_required_count=0`
  - `rollback_enabled=false`
  - `cycle_stalled=false`
  - M1 enabled and staleness `ok`

## Residual Notes

- Full `ruff check .` is still blocked by unrelated pre-existing/untracked
  visual and drift-report artifacts. Targeted ruff for touched files is clean.
- SQLite `ResourceWarning` noise remains a separate operational queue item,
  unchanged by this slice.
- Repo templates remain fallback-compatible. Full `LoadCredential=` deployment
  can be installed by operator drop-ins or future service provisioning, but the
  current live host closure no longer relies on `config/.env` as a secret
  source.

## Plain English

The first locked-drawer build still had side tunnels. The drawer itself was
good, but some child processes could still inherit the keys, the iPhone door
could appear open without its key, rollback did not really roll back, and an
old GitHub publisher could put a token in a command line. Recovery closes
those tunnels and adds tests that look at each door, not just at whether the
building contains one lock somewhere.

After recovery, Maez starts with ordinary config in `.env`, secrets in the
secret drawer, no secret names in its process environment, no secret-bearing
children at reviewed subprocess seams, and a working emergency rollback.
