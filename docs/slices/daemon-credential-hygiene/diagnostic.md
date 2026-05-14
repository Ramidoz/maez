# Daemon Credential Hygiene Diagnostic

Status: DIAGNOSTIC ONLY
Date: 2026-05-14
Scope: credential storage and runtime exposure for `maez.service` and adjacent
Maez services that authenticate to remote systems.

## Question

After provider-side token rotation, what credential exposure surface remains,
and what should a v1 migration actually close?

Short answer: Maez's live user service currently execs with
`config/.env` as an `EnvironmentFile`, so identity-bearing credentials are
available in the process environment at daemon start. Rotation closed the
immediate stale-token risk. It did not close the structural exposure surface.

## Current Service Ingress

The live user unit currently loads two environment files:

```text
EnvironmentFile=/home/rohit/maez/config/.env
EnvironmentFile=/home/rohit/.config/maez/model.env
Environment=PYTHONUNBUFFERED=1
Environment=MAEZ_HOME=/home/rohit/maez
Environment=DISPLAY=:1
Environment=XAUTHORITY=/run/user/1000/gdm/Xauthority
```

`config/.env` is therefore part of the initial `execve()` environment for
`maez.service`. Any secret stored there is exposed as an exec-time process
environment variable.

The daemon also loads `config/.env` inside Python at startup:

- `daemon/maez_daemon.py:23-33` imports and calls `load_dotenv(...)`.
- `skills/web_interface.py:27-29` calls `load_dotenv(...)`.
- Several standalone skills and scripts call `load_dotenv(...)` for ad-hoc
  execution outside the daemon.

The migration must distinguish service-start ingress from Python compatibility
ingress. Removing secrets from the systemd `EnvironmentFile` closes the most
visible process-env surface only if Python's runtime assignments do not become
visible through `/proc/<pid>/environ`.

## Empirical `/proc/<pid>/environ` Result

Probe performed on this host with a dummy key and dummy value only:

```text
child process starts with no MAEZ_PROC_ENVIRON_PROBE_TOKEN in exec env
child process assigns os.environ["MAEZ_PROC_ENVIRON_PROBE_TOKEN"] at runtime
parent reads /proc/<child-pid>/environ
result: runtime_assignment_visible_in_proc_environ=no
```

Interpretation for this host:

- `/proc/<pid>/environ` did not show a value assigned after process start by
  CPython `os.environ[...] = ...`.
- If v1 starts the daemon without secrets in the initial systemd environment,
  then later Python-only compatibility population is not visible through
  ordinary `/proc/<pid>/environ` reads on this machine.
- That makes v1 a real exposure reduction, not just a storage relocation.

Important caveat:

- Python's mutated `os.environ` is still the environment inherited by future
  subprocesses unless those subprocesses pass an explicit sanitized `env=`.
- v1 reduces `ps auxe` / `/proc/<pid>/environ` exposure. It does not mean
  secrets are absent from daemon memory, child-process environments, tracebacks,
  memory dumps, or any code path that logs values.

## Secret vs Ordinary Config Boundary

This slice is about identity-bearing credentials only.

Secrets in scope:

- Tokens, API keys, webhook secrets, shared ingest tokens, and anything that
  authenticates Maez to a remote system.
- OAuth refresh/access tokens and provider credential files when a connector is
  live or planned.
- Public/private key material if later used for identity continuity or signing.

Ordinary config out of scope for v1:

- Ports, model names, local URLs, feature flags, paths, timeouts, UI toggles,
  and local hardware/display variables.
- These may stay in `config/.env`, `model.env`, or ordinary systemd
  `Environment=` entries.

Privacy-bearing but not credential-shaped config:

- Home location fields such as `MAEZ_HOME_LAT`, `MAEZ_HOME_LON`, and
  `MAEZ_HOME_PLACE` are personal data, but they do not authenticate Maez to a
  remote system. They should not be folded into this credential slice unless
  the operator explicitly widens the scope to privacy hygiene.

This boundary matters. If v1 moves every config value into credential ceremony,
operators lose clarity and future agents will treat harmless flags like secrets.

## Current Secret-Name Catalog

This catalog names variables only. It intentionally does not include values,
prefixes, hashes, or validity status.

### Currently present in `config/.env`

```text
ANTHROPIC_API_KEY
CLOUDFLARE_API_TOKEN
MAEZ_DEV_TOKEN
MAEZ_GITHUB_TOKEN
MAEZ_IPHONE_INGEST_TOKEN
MAEZ_PUBLIC_TELEGRAM_TOKEN
MAEZ_TELEGRAM_TOKEN
```

Associated non-secret config currently present in the same file:

```text
CLOUDFLARE_ZONE_ID
MAEZ_GITHUB_USERNAME
MAEZ_HOME_LAT
MAEZ_HOME_LON
MAEZ_HOME_PLACE
MAEZ_LIVE_FAST_LANE_ENABLED
MAEZ_LLAMACPP_MODEL
MAEZ_LLM_BACKEND
MAEZ_M1_LIVED_EPISODE_PROMOTION
MAEZ_TELEGRAM_USER_ID
MAEZ_WORKING_SELF
```

`MAEZ_TELEGRAM_USER_ID` is not an authentication secret, but it is
identity-adjacent and should remain access-controlled as owner-local config.

### Known secret names supported by code but not necessarily present

```text
LANGFUSE_SECRET_KEY
OLLAMA_API_KEY
OPENAI_API_KEY
OPENROUTER_API_KEY
TELEGRAM_WEBHOOK_SECRET
XAI_API_KEY
```

These should be supported by the same credential-hygiene mechanism even if not
currently active.

## Reader Inventory

### Telegram / surface credentials

- `skills/telegram_voice.py:567` reads `MAEZ_TELEGRAM_TOKEN`.
- `skills/telegram_public.py:208-210` reads `MAEZ_PUBLIC_TELEGRAM_TOKEN`,
  `MAEZ_TELEGRAM_TOKEN`, and `MAEZ_TELEGRAM_USER_ID`.
- `skills/dev_notifier.py:43-44` reads `MAEZ_DEV_TOKEN` and
  `MAEZ_TELEGRAM_USER_ID`.
- `skills/surface/telegram_adapter.py:928` reads `TELEGRAM_WEBHOOK_SECRET`.

### iPhone ingest

- `skills/iphone_ingest.py:79` reads `MAEZ_IPHONE_INGEST_TOKEN`.
- `config/identity.template.yaml:50` documents the same token as required for
  the iPhone ambient-awareness ingest path.
- `skills/web_interface.py:6325-6336` registers `/api/iphone/ingest`
  unconditionally. Missing or empty token state fails closed with
  `401 unauthorized`, but the endpoint is still mounted whenever the web
  interface is reachable.

### GitHub

- `skills/github_skill.py:33` reads `MAEZ_GITHUB_TOKEN`.
- `skills/github_publish.py:36` reads `MAEZ_GITHUB_TOKEN`.

### Cloudflare

- `skills/dynamic_dns.py:23-24` reads `CLOUDFLARE_ZONE_ID` and
  `CLOUDFLARE_API_TOKEN`.

`CLOUDFLARE_API_TOKEN` is the secret. `CLOUDFLARE_ZONE_ID` is operational
config and can remain ordinary config.

### Frontier / routing credentials

- `skills/claude_router.py:159` reads `ANTHROPIC_API_KEY`.
- `core/routing/fast_backend_cloud.py:97-99` reads `ANTHROPIC_API_KEY` and
  `OPENAI_API_KEY`.
- `core/subscription_proxy/adapters/http_forward.py:49` reads adapter-specific
  API keys through each adapter's `API_KEY_ENV`.
- `core/subscription_proxy/adapters/openrouter.py:40` names
  `OPENROUTER_API_KEY`.
- `core/subscription_proxy/adapters/openai_api.py:37` names `OPENAI_API_KEY`.
- `core/subscription_proxy/adapters/xai_api.py:26` names `XAI_API_KEY`.
- `core/subscription_proxy/adapters/ollama_cloud.py:28` names
  `OLLAMA_API_KEY`.

### Observability credentials

- `core/cognition/observability.py:48-73` reads `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY`.
- `skills/web_interface.py:5207-5216` reads `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, and Langfuse host config.

`LANGFUSE_PUBLIC_KEY` is public-ish provider config. `LANGFUSE_SECRET_KEY` is
the secret.

## Exposure Model

### Before rotation

Any old credential value already exposed through earlier process environments,
logs, command history, crash dumps, or accidental prints had to be treated as
burned. Provider-side rotation was the correct immediate action.

### After rotation, before migration

The live values are fresh, but the storage and runtime shape is unchanged:

- `config/.env` contains credentials and ordinary config together.
- `maez.service` uses `config/.env` as a systemd `EnvironmentFile`.
- Initial process environment exposure still exists.
- `/proc/<pid>/environ` and `ps auxe` exposure are relevant while the service
  starts with secrets in its exec environment.
- Any subprocess launched with inherited env may receive all current env vars.

### After v1, if implemented as compatibility population

Proposed v1 shape:

- Secrets leave `config/.env`.
- Systemd no longer injects secrets through `EnvironmentFile=`.
- A small secrets loader reads from systemd credential files or a `0600`
  local secrets file.
- The loader validates required secrets at startup.
- The loader can populate `os.environ` for compatibility so existing readers
  keep working in v1.

On this host, runtime `os.environ` population is not visible through
`/proc/<pid>/environ`, so v1 materially improves the visible process-env
surface.

Remaining v1 risks:

- Secrets still exist in daemon memory.
- Secrets can still be inherited by child processes unless subprocess calls
  sanitize `env=`.
- Existing readers can still log or print values if they have bugs.
- Any code path that enumerates `os.environ` can still see secrets in-process.

The subprocess caveat is not theoretical. Repo scan found many subprocess
launch sites across `core/`, `daemon/`, `skills/`, and `scripts/`, including
daemon-adjacent surfaces such as `core/actions/action_engine.py`,
`skills/telegram_voice.py`, `skills/web_interface.py`, and
`core/self_dev/__init__.py`. A child process launched after compatibility
population can inherit Python's current `os.environ`; that child may then
expose secrets through its own `ps auxe` or `/proc/<child>/environ` even if the
parent daemon does not.

Therefore, a v1 spec that claims to close `ps`/`/proc environ` exposure should
either require a sanitized subprocess environment for daemon-launched children
or explicitly narrow its claim to the parent daemon process only. The stronger
v1 posture is to introduce a small subprocess-env helper and route high-risk
daemon subprocess launches through it before declaring the surface closed.

### After v2

Proposed v2 shape:

- Readers move from `os.environ.get("SECRET_NAME")` to an explicit
  secret-access API.
- The secret-access API returns values only to named allowlisted call sites or
  modules.
- Subprocess launches default to a sanitized env.
- Tests and CI fail on secret-shaped output in logs/test output.

V2 is not required to get the first exposure reduction, but it is required to
remove env-based secret access as a general programming interface.

## Startup Validation Requirement

Required secrets should fail loud at daemon startup, not fail late at first
provider use.

Minimum v1 behavior:

- Validate configured required secrets are present and non-empty during daemon
  startup.
- Do not validate optional provider secrets unless the associated feature is
  enabled.
- Raise a clear startup error naming the missing secret key name only, never a
  value.
- Expose a value-free health summary such as:

```text
credential_source=systemd-credentials
required_credentials_present=true
optional_credentials_loaded_count=N
```

The health summary must not list loaded secret names by default. A forensic
operator-only mode may list names later if reviewed.

## Source-Channel Logging Requirement

Startup logs should record where secrets came from, not what secrets exist.

Allowed examples:

```text
credential source: systemd LoadCredential
credential source: config/secrets.local.env
credential source: none
```

Not allowed:

```text
loaded MAEZ_TELEGRAM_TOKEN
loaded 7 credentials: MAEZ_TELEGRAM_TOKEN, ...
MAEZ_TELEGRAM_TOKEN begins with ...
```

This gives the operator enough signal to debug "auth failed after restart"
without turning startup logs into a credential map.

## Value-Logging Guard

Tests should verify the secrets loader itself does not log values, but that is
not enough. The stronger v1/v2 guard is a repo-level or CI-level scan over test
output and selected logs for secret-shaped strings.

Initial patterns to consider:

```text
ghp_
github_pat_
sk-ant-
sk-
xoxb-
telegram bot token shape: digits:token-body
Cloudflare bearer-token-like strings when known by provider shape
```

This must be tuned carefully to avoid false positives from fixtures. Existing
tests already use fake values like `sk-lf-test`, so the first implementation
may need an allowlist for explicit test-fixture strings while still failing on
real-looking values.

## Git History Exposure Check

A value-free history check was run with pattern-based search, not specific
tokens.

Findings:

- `config/.env`, `config/*.env`, and top-level `.env` have no visible commit
  history in this repo.
- A broad historical pattern scan did find secret-shaped strings in tracked
  files, but the path list is consistent with examples, docs, tests, and
  snapshots rather than the private config file:

```text
.env.example
AGENTS.md
docs/GETTING_STARTED.md
docs/LAUNCH_CHECKLIST.md
docs/governance/SECURITY_AUDIT.md
docs/slices/m1-lived-episode-promotion/implementation-plan.md
docs/superpowers/plans/2026-04-20-langfuse-observability.md
logs/snapshots/session_snapshot_2026-05-13.txt
```

This diagnostic does not prove that no secret value has ever appeared in git
history. It proves only that the primary private env file was not found in git
history and that a broad pattern scan has a bounded follow-up set. A future
publication-hardening pass should audit those historical pattern hits
value-free, then decide whether any history rewrite is necessary.

## V1 / V2 Boundary

V1 should be storage and ingress migration, not a repo-wide reader rewrite.

V1 should:

- Remove secrets from the systemd exec environment.
- Keep ordinary config in ordinary config.
- Load secrets from systemd credentials if present.
- Fall back to a `0600` local secrets file for non-systemd/dev flows.
- Validate required secrets at startup.
- Optionally populate `os.environ` for compatibility after startup.
- Log source channel only.
- Add tests proving no values are logged.
- Add a regression test documenting the `/proc/<pid>/environ` behavior for
  runtime assignments on Linux.
- Sanitize daemon-launched subprocess environments or explicitly mark
  subprocess inheritance as an unresolved v1 residual risk.

V1 should not:

- Rewrite every `os.environ.get(...)` reader.
- Move ports, paths, model names, or feature flags into secret storage.
- Add a secrets manager dependency.
- Print credential names or values to health endpoints by default.
- Treat provider-side rotation as proof that storage hygiene is solved.

V2 should:

- Migrate high-value readers to an explicit `core.infra.secrets` API.
- Finish env-inheritance hardening for subprocess boundaries if v1 only covers
  the daemon's highest-risk launch sites.
- Add a structural CI guard against secret-shaped output.
- Consider rotation-without-restart for long-lived providers where the client
  can refresh credentials safely.
- Provide the credential interface future S2 information limbs inherit for
  OAuth/account tokens, so S2's provenance and credential posture are not a
  separate reinvention.

## Open Questions for Spec Review

1. Should v1 use systemd `LoadCredential=` as the primary local-host mechanism,
   with `config/secrets.local.env` as a development fallback?

2. Should v1 populate `os.environ` for compatibility, or should it provide a
   compatibility getter that only selected early readers adopt?

3. Which secrets are required for `maez.service` startup, and which are
   optional because the feature can degrade safely?

4. Should `MAEZ_TELEGRAM_TOKEN` be required because Telegram is currently the
   bonded surface, while `MAEZ_PUBLIC_TELEGRAM_TOKEN`, `MAEZ_DEV_TOKEN`,
   `MAEZ_GITHUB_TOKEN`, `CLOUDFLARE_API_TOKEN`, and frontier provider keys are
   optional?

5. Should `MAEZ_IPHONE_INGEST_TOKEN` be required only when the iPhone ingest
   endpoint is enabled, or always because the endpoint is currently mounted
   unconditionally and fails closed when the token is missing?

6. Should health expose only source channel and aggregate status, or should an
   operator-only endpoint list missing key names?

7. How should subprocess env scrubbing be sequenced? Existing daemon-adjacent
   subprocess launch sites mean parent-process `/proc` closure can leak through
   inherited child environments. Should v1 require a sanitized subprocess-env
   helper before ratifying the `ps`/`/proc` exposure claim, or explicitly limit
   the v1 claim to the parent daemon only?

8. Should provider-side credential rotation be documented as an operator
   runbook separate from storage migration, so future exposure events do not
   wait for architectural cleanup?

9. Should the spec cite the measured
   `runtime_assignment_visible_in_proc_environ=no` result as the basis for v1's
   compatibility-population security claim, and require a regression test so a
   future kernel/glibc/Python behavior change fails visibly?

10. Should the spec explicitly state that future S2 information-limb OAuth
    credentials inherit the `core.infra.secrets` interface and source-channel
    audit posture, rather than introducing connector-specific credential
    loaders?

## Non-Goals

- No provider calls in this diagnostic.
- No token values, token prefixes, hashes, or validity proofs in this document.
- No credential rotation in this document; rotation already happened as an
  operator action.
- No code changes.
- No systemd unit changes.
- No migration of OAuth account tokens for future information limbs; S2 and
  information-limb credential handling should inherit from this pattern later.
- No changes to M1, TRF, S1b, or the project panel.

## Plain English

The keys were rotated, so old exposed keys are dead. But Maez still keeps fresh
keys in the same jacket pocket: `config/.env`, loaded directly into the daemon's
startup environment.

The next fix is not "rotate again." It is moving keys into a locked drawer.
Normal settings like ports, model names, and feature flags can stay in `.env`.
Real keys and tokens should move to a secrets path that the daemon reads at
startup.

The important Linux detail was checked with a fake token: if Python adds a
secret to `os.environ` after the daemon starts, this machine does not show it
through `/proc/<pid>/environ`. That means a compatibility v1 can genuinely
reduce the easy exposure surface, as long as systemd stops putting secrets into
the daemon at launch. The remaining wound is the child-process edge: if Maez
spawns a subprocess after loading secrets into Python's environment, that child
can inherit the secrets and expose them again. The spec should either close
that in v1 with sanitized subprocess envs or name it honestly as residual risk.
