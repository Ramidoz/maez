# Slice: Daemon Credential Hygiene

**Status:** CANONICAL. Decision 26 / ADR 0031. Built from
[`diagnostic.md`](diagnostic.md). Claude covenant council returned
RATIFY-WITH-AMENDMENTS; Codex engineering panel returned REVISE. This revision
folds both review lanes. No code has landed from this packet.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) — current env ingress, reader inventory,
  `/proc/<pid>/environ` measurement, subprocess inheritance risk, git-history
  note.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) —
  Decision 26.
- [`docs/adr/0031-daemon-credential-hygiene.md`](../../adr/0031-daemon-credential-hygiene.md) —
  ADR 0031.
- [`docs/adr/0023-hardware-failure-memory-backup.md`](../../adr/0023-hardware-failure-memory-backup.md) —
  Decision 22 continuity backup; credential files must become part of the
  operator's succession/restore discipline without being logged or published.
- [`docs/slices/body-topology/spec.md`](../body-topology/spec.md) — Decision 24
  capability quarantine and body-limb credential posture; credentials carried
  by body/information limbs are part of Maez's body boundary.
- [`docs/slices/s2-contextual-integrity-at-ingest/scoping.md`](../s2-contextual-integrity-at-ingest/scoping.md) —
  future information-limb ingest gate; S2 OAuth/account credentials should
  inherit the secret-loading interface and source-channel audit posture from
  this slice.
- [`reviews/claude-council.md`](reviews/claude-council.md) — covenant review,
  RATIFY-WITH-AMENDMENTS.
- [`reviews/codex-panel.md`](reviews/codex-panel.md) — engineering review,
  REVISE until per-service credential profiles, web/iPhone scope, bootstrap
  order, source semantics, subprocess hygiene, and rollback are folded.

**Classification:** security-shaped infrastructure work with covenant adjacency.
The engineering lane is primary. The covenant lane reviews invariant #11
(Cryptographic Continuity), body-boundary handling, and whether credential
source visibility strengthens rather than weakens identity continuity.

---

## Intent

Move identity-bearing credentials out of Maez's initial process environment
without breaking the existing daemon readers in one wide patch.

Provider-side rotation already happened. That closed the immediate stale-token
risk. This slice closes the next layer: fresh secrets should not sit in
`maez.service`'s `execve()` environment where `ps auxe` and
`/proc/<pid>/environ` can expose them.

The v1 target is deliberately narrow:

1. keep ordinary configuration ordinary;
2. load secrets from a credential source at startup;
3. validate required secrets per active service before that service is alive;
4. populate compatibility environment values only after process start;
5. sanitize daemon subprocess environments enough that compatibility loading
   does not immediately leak through child processes;
6. distinguish active service migration from dormant template hygiene;
7. log only the source channel, never key names or values;
8. test the Linux `/proc` assumption that makes v1 a real exposure reduction;
9. provide a rollback path if the new loader breaks authentication.

---

## Load-Bearing Rule

**Keys are identity-bearing material, not ordinary config.**

Maez's tokens and API keys are how it proves its identity to Telegram, iPhone
Shortcuts, GitHub, Cloudflare, frontier providers, observability providers, and
future information limbs. They are part of the identity boundary. They should
be rotated quickly after exposure, loaded through a narrow interface, and
excluded from broad process-environment exposure.

Allowed:

- ordinary config in `config/.env`;
- secrets in a credential source with `0600` permissions or systemd
  credentials;
- value-free startup logs such as `credential source: systemd LoadCredential`;
- compatibility population into Python `os.environ` after process start, only
  because this host empirically hides runtime assignments from
  `/proc/<pid>/environ`;
- sanitized subprocess envs that pass only the config a child actually needs.

Forbidden:

- secrets in `maez.service`'s initial systemd `EnvironmentFile=`;
- printing, logging, health-reporting, or snapshotting secret values;
- treating provider rotation as proof that storage hygiene is solved;
- moving model names, ports, paths, feature flags, or display variables into
  credential ceremony;
- child-process inheritance that quietly re-exposes runtime-loaded secrets.

---

## Empirical Basis For V1

The diagnostic measured this host with a dummy key and dummy value:

```text
runtime_assignment_visible_in_proc_environ=no
```

That finding is load-bearing. It means:

- secrets set by systemd before `execve()` are visible through the normal
  process environment surface;
- secrets assigned later inside Python via `os.environ[...] = ...` were not
  visible through `/proc/<pid>/environ` on this host;
- therefore v1's compatibility-population pattern is a real exposure reduction
  for the parent daemon process.

The implementation must preserve that claim with a regression test. If a future
kernel/glibc/Python behavior change makes runtime assignments visible through
`/proc/<pid>/environ`, the test should fail and v2 reader migration becomes
urgent.

The claim is only honest if subprocess inheritance is addressed. A daemon child
spawned after compatibility population can inherit Python's current
`os.environ`, and that child can expose secrets through its own
`/proc/<child>/environ`. V1 must either sanitize daemon child envs or explicitly
refuse to claim the subprocess surface is closed.

This spec chooses the stronger v1 posture: add sanitized subprocess env support
for daemon-owned launch sites and require high-risk daemon subprocess launches
to use it.

---

## Secret Boundary

### Secrets In Scope

Names only; values are never documented.

Currently present in `config/.env` and in scope:

```text
ANTHROPIC_API_KEY
CLOUDFLARE_API_TOKEN
MAEZ_DEV_TOKEN
MAEZ_GITHUB_TOKEN
MAEZ_IPHONE_INGEST_TOKEN
MAEZ_PUBLIC_TELEGRAM_TOKEN
MAEZ_TELEGRAM_TOKEN
```

Supported by code and in scope when configured:

```text
LANGFUSE_SECRET_KEY
OLLAMA_API_KEY
OPENAI_API_KEY
OPENROUTER_API_KEY
TELEGRAM_WEBHOOK_SECRET
XAI_API_KEY
```

Future S2/account connectors:

```text
OAuth refresh/access tokens
provider credential JSON files
information-limb account secrets
```

These are not implemented by this slice, but they must inherit this slice's
secret-loading discipline later.

### Ordinary Config Out Of Scope

These remain ordinary config unless a later slice widens privacy hygiene:

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
ports / local URLs / timeouts / paths / feature flags
DISPLAY
XAUTHORITY
PYTHONUNBUFFERED
MAEZ_HOME
```

`MAEZ_TELEGRAM_USER_ID` is identity-adjacent owner-local config, but it does not
authenticate Maez to a provider and should not be treated as a secret in v1.

---

## Current Reader Inventory

### Telegram / Surface

- `skills/telegram_voice.py:567` reads `MAEZ_TELEGRAM_TOKEN`.
- `skills/telegram_public.py:208-210` reads `MAEZ_PUBLIC_TELEGRAM_TOKEN`,
  `MAEZ_TELEGRAM_TOKEN`, and `MAEZ_TELEGRAM_USER_ID`.
- `skills/dev_notifier.py:43-44` reads `MAEZ_DEV_TOKEN` and
  `MAEZ_TELEGRAM_USER_ID`.
- `skills/surface/telegram_adapter.py:928` reads `TELEGRAM_WEBHOOK_SECRET`.

### iPhone Ingest

- `skills/iphone_ingest.py:79` reads `MAEZ_IPHONE_INGEST_TOKEN`.
- `skills/web_interface.py:6325-6336` mounts `/api/iphone/ingest`
  unconditionally. Missing token state fails closed with `401 unauthorized`.

V1 posture: the token is required when the web interface exposes the endpoint.
If a future flag disables/mounts the endpoint conditionally, the requirement can
become feature-gated.

The current route accepts the token from the `X-Maez-Token` header or from a
JSON body field. Header auth is the intended transport per
`skills/iphone_ingest.py`. V1 must remove the JSON-body token fallback after
the operator confirms the iPhone Shortcut uses the header. Until that happens,
body-token support remains an explicit residual risk because request bodies are
more likely to appear in debug captures, reverse-proxy logs, snapshots, or
error reports.

### GitHub

- `skills/github_skill.py:33` reads `MAEZ_GITHUB_TOKEN`.
- `skills/github_publish.py:36` reads `MAEZ_GITHUB_TOKEN`.

### Cloudflare

- `skills/dynamic_dns.py:23-24` reads `CLOUDFLARE_ZONE_ID` and
  `CLOUDFLARE_API_TOKEN`.

Only `CLOUDFLARE_API_TOKEN` is secret-shaped. `CLOUDFLARE_ZONE_ID` remains
ordinary config.

### Frontier / Routing

- `skills/claude_router.py:159` reads `ANTHROPIC_API_KEY`.
- `core/routing/fast_backend_cloud.py:97-99` reads `ANTHROPIC_API_KEY` and
  `OPENAI_API_KEY`.
- `core/subscription_proxy/adapters/http_forward.py:49` reads keys through
  adapter-specific `API_KEY_ENV`.
- `core/subscription_proxy/adapters/openrouter.py:40` names
  `OPENROUTER_API_KEY`.
- `core/subscription_proxy/adapters/openai_api.py:37` names `OPENAI_API_KEY`.
- `core/subscription_proxy/adapters/xai_api.py:26` names `XAI_API_KEY`.
- `core/subscription_proxy/adapters/ollama_cloud.py:28` names
  `OLLAMA_API_KEY`.

### Observability

- `core/cognition/observability.py:48-73` reads `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY`.
- `skills/web_interface.py:5207-5216` reads `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, and Langfuse host config.

Only `LANGFUSE_SECRET_KEY` is secret-shaped.

---

## V1 Design

### 1. Storage Split

`config/.env` remains the ordinary config file.

Secrets move out of `config/.env` into one of these sources:

1. systemd credentials when running under systemd;
2. `config/secrets.local.env` as the owner-local fallback for dev/manual runs.

`config/secrets.local.env` must be:

- gitignored;
- `0600`;
- key-value formatted;
- never printed by scripts;
- included in Decision 22 backup/succession manifest as owner-local secret
  state, not public repo state.

V1 systemd shape:

- one credential file per secret;
- credential ID equals the environment variable name;
- unit files use `LoadCredential=<NAME>:<0600-local-path>` or equivalent
  local credential references;
- do not use `SetCredential=` because it embeds values in unit text;
- service reads credentials from `$CREDENTIALS_DIRECTORY/<NAME>`.

Source precedence:

1. systemd credential file wins per key;
2. `config/secrets.local.env` may fill missing keys;
3. `config/.env` is never a secret source.

`mixed` source means at least one loaded secret came from systemd credentials
and at least one loaded secret came from `config/secrets.local.env`.

Malformed fallback file behavior:

- duplicate key in `config/secrets.local.env`: startup validation error;
- malformed non-comment line: startup validation error;
- empty required value: startup validation error;
- empty optional value: treated as absent.

This per-key fallback allows a user-scoped service to migrate incrementally
without hiding source ambiguity.

### 2. Secret Loader

Add `core/infra/secrets.py`.

Required behavior:

- Read systemd credentials first if `$CREDENTIALS_DIRECTORY` is present and
  contains Maez credentials.
- Fall back per key to `config/secrets.local.env` only for keys not provided by
  systemd credentials.
- Never read secret values from `config/.env`.
- Preserve ordinary config lookup through existing code paths.
- Return values by key for future v2 readers.
- Provide compatibility population into `os.environ` for v1 readers.
- Track source channel internally as one of:
  `systemd-credentials`, `secrets-local-env`, `none`, `mixed`.
- Never log key names or values by default.

The module may expose:

```python
load_secrets_for_process(required: set[str], optional: set[str]) -> SecretLoadReport
get_secret(name: str) -> str | None
sanitize_env(base: Mapping[str, str] | None = None, *, allow: Iterable[str] = ()) -> dict[str, str]
```

Exact API names may change during implementation. The semantic contract should
not.

Bootstrap order:

1. Load ordinary config, excluding secret-shaped names.
2. Load secrets through `core/infra/secrets.py`.
3. Validate the active service's required profile.
4. Populate compatibility `os.environ` for v1 readers.
5. Import or initialize modules/surfaces that read secret-bearing env names.

The implementation must remove or constrain import-time `load_dotenv(...)`
calls in daemon/web startup paths so secret readers do not observe the
pre-loader state. If a module still loads `.env` for ad-hoc CLI use, it must
load ordinary config only or fail if secret-shaped names remain in `.env`.

### 3. Startup Validation

Required secrets fail loud at startup before the service that needs them
appears alive.

V1 credential profiles:

```text
service_or_surface              required                         optional / degraded
maez.service                    MAEZ_TELEGRAM_TOKEN              MAEZ_DEV_TOKEN
maez-web / web interface        MAEZ_IPHONE_INGEST_TOKEN         LANGFUSE_SECRET_KEY, MAEZ_GITHUB_TOKEN
private Telegram bonded surface MAEZ_TELEGRAM_TOKEN              none
public Telegram surface         none                             MAEZ_PUBLIC_TELEGRAM_TOKEN
dev notifier                    none                             MAEZ_DEV_TOKEN
dynamic DNS                     none                             CLOUDFLARE_API_TOKEN
GitHub skills/publish           none                             MAEZ_GITHUB_TOKEN
frontier routing                none                             ANTHROPIC_API_KEY, OPENAI_API_KEY
subscription proxy              provider-specific                OPENROUTER_API_KEY, OPENAI_API_KEY, XAI_API_KEY, OLLAMA_API_KEY
Telegram webhook mode           TELEGRAM_WEBHOOK_SECRET if enabled none
```

Rationale:

- Telegram is the current bonded surface.
- The private Telegram daemon must not fail because a web/iPhone ingest token
  is absent.
- iPhone ingest token is required for the web/ingest surface while the route is
  mounted; if the route becomes feature-gated, this requirement becomes
  feature-gated.
- Public/dev Telegram tokens must not degrade the bonded private Telegram
  surface when absent.
- Missing private `MAEZ_TELEGRAM_TOKEN` must fail loud before Maez appears
  alive.

Optional / feature-gated in v1:

```text
ANTHROPIC_API_KEY
CLOUDFLARE_API_TOKEN
LANGFUSE_SECRET_KEY
MAEZ_DEV_TOKEN
MAEZ_GITHUB_TOKEN
MAEZ_PUBLIC_TELEGRAM_TOKEN
OPENAI_API_KEY
OPENROUTER_API_KEY
OLLAMA_API_KEY
TELEGRAM_WEBHOOK_SECRET
XAI_API_KEY
```

Optional means missing secrets disable or fail the specific provider/surface,
not the daemon as a whole. If a feature flag later marks one of these surfaces
mandatory, that feature's startup check can promote the secret to required.

Validation errors may name missing key names because no values exist. They must
not print source file contents or nearby config.

### 4. Source-Channel Logging

Startup may log:

```text
credential source: systemd-credentials
credential source: secrets-local-env
credential source: none
credential source: mixed
```

Startup must not log:

```text
loaded MAEZ_TELEGRAM_TOKEN
loaded 7 credentials: ...
token begins with ...
hash=...
```

Health may expose aggregate status only:

```json
{
  "credentials": {
    "source": "systemd-credentials",
    "required_present": true,
    "optional_loaded_count": 4,
    "missing_required_count": 0
  }
}
```

Health must not list loaded optional names by default. A later operator-only
forensic endpoint may list missing names if reviewed.

### 5. Systemd Unit Posture

`maez.service` must stop loading secret-bearing values through its initial
`EnvironmentFile=`.

V1 unit posture:

- Keep ordinary config `EnvironmentFile=` or equivalent for non-secret config.
- Remove secret values from any environment file used at service `execve()`.
- Add systemd credential loading or rely on the local fallback file read inside
  Python.
- Keep `MAEZ_HOME`, display variables, model config, and feature flags ordinary.

Adjacent shipped units that currently load `config/.env` must be inventoried
and either migrated or explicitly listed as residual risk:

- live user `maez.service`
- `maez-web` / `skills/web_interface.py` if active or reachable through another
  service;
- `scripts/maez.template.service`
- `scripts/maez-subscription-proxy.service`
- `scripts/maez-subscription-proxy.template.service`
- `scripts/maez-lived-memory-reflection.service`
- `scripts/maez-self-dev-scheduled.service`
- `scripts/maez-self-dev-scheduled.template.service`

Implementation should prioritize the live `maez.service` first, then any active
adjacent unit that authenticates to remote providers. It must not claim
repo-wide credential hygiene while any active systemd service still execs with
secret-bearing `EnvironmentFile=`.

Active/dormant inventory gate:

```text
unit_or_surface              state                     credential_hygiene_status
maez.service                 active_migrated | active_residual_risk
maez-web                     active_migrated | active_residual_risk | not_installed
maez-subscription-proxy      active_migrated | active_residual_risk | not_installed
maez-lived-memory-reflection dormant_template_updated | dormant_residual_risk | not_installed
maez-self-dev-scheduled      dormant_template_updated | dormant_residual_risk | not_installed
maez-backup                  active_migrated | active_residual_risk | not_installed
```

During this spec review, `systemctl --user` showed `maez.service`,
`llama-server.service`, `llama-judge.service`, and
`maez-backup.timer/service` as the active Maez-related user units. It did not
show active `maez-web`, subscription proxy, self-dev scheduled, or reflection
timer units. Implementation must re-check the live state rather than trust this
snapshot.

### 6. Subprocess Environment Hygiene

V1 must add a sanitized subprocess environment helper.

Default general helper behavior is **copy current env minus secret-shaped
names**, not a tiny allowlist. Tiny allowlists are allowed only in strict mode
for call sites that have been tested with the narrower environment.

The general helper should preserve ordinary operational variables such as
`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_ALL`, `MAEZ_HOME`,
`DISPLAY`, `XAUTHORITY`, `XDG_RUNTIME_DIR`, `PIPEWIRE_RUNTIME_DIR`,
`DBUS_SESSION_BUS_ADDRESS`, `SSH_AUTH_SOCK`, `VIRTUAL_ENV`, `PYTHONPATH`, and
other non-secret operational values already present in the parent environment.

It should exclude secret-shaped names by default:

```text
*TOKEN*
*API_KEY*
*SECRET*
*PASSWORD*
*CREDENTIAL*
```

Call sites that intentionally need a credential must opt in explicitly and
document why.

Credential opt-in requirements:

- exact key name allowlist;
- call-site comment explaining why the child needs the credential;
- test proving the allow path works;
- test proving unrelated secret-shaped keys remain excluded.

V1 must route high-risk daemon-owned subprocess launches through the helper.
At minimum, implementation must update or carry a reviewed exception marker for:

- `core/actions/action_engine.py`
- `skills/telegram_voice.py`
- `skills/web_interface.py`
- `core/self_dev/__init__.py`
- `core/actions/tool_loop.py`

Scripts that run outside the daemon can migrate later, but daemon-launched
children are part of v1's exposure claim.

### 7. Value Logging Guard

V1 must include both unit tests and a structural scan.

Required:

- tests proving `core/infra/secrets.py` logs no values;
- tests proving source-channel logs do not list loaded key names;
- tests proving health exposes aggregate counts only;
- a pattern scanner that can be run in CI or pre-push against selected logs/test
  output.

Initial forbidden output patterns:

```text
ghp_
github_pat_
sk-ant-
sk-
xoxb-
digits:telegram-token-body
```

The implementation may allowlist explicit fake fixtures such as `sk-lf-test`
while still failing on real-looking values.

### 8. Git History Follow-Up

This slice does not rewrite git history.

The diagnostic found no visible history for `config/.env`, `config/*.env`, or
top-level `.env`. It also found a bounded list of historical pattern hits in
docs/examples/tests/snapshots. Publication hardening should audit those hits
value-free before any OSS release and decide whether any history cleanup is
needed.

### 9. Backup / Succession

`config/secrets.local.env` is owner-local secret state. It must not enter git,
but it must have a documented continuity story.

Restore modes:

- `state_only_restore_requires_credential_rehydration`: memory and repo state
  restore succeeds, then the operator re-adds credentials manually before
  bonded/remote surfaces are expected to authenticate.
- `encrypted_continuity_restore_includes_secret_file`: encrypted destination
  includes `config/secrets.local.env` as a secret file, then post-restore
  verification checks required surfaces without printing values.

Implementation must update the Decision 22 backup manifest/test contract so
`config/secrets.local.env` is handled as encrypted-destination-only secret
state. It must also verify `.gitignore` names `config/secrets.local.env` before
the operator is asked to create it.

### 10. Recovery / Rollback

V1 needs a mechanical rollback because this slice touches daemon startup.

Rollback flag:

```text
MAEZ_SECRETS_DISABLE_NEW_LOADER=1
```

If set, the new secrets loader is bypassed and Maez temporarily returns to
v0-style local env behavior. This reaccepts process-environment exposure and
reopens the credential-hygiene slice; it is a recovery path, not a valid final
state.

Rollback runbook:

1. Restore the local pre-migration `config/.env` backup on the operator host.
2. Set `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` in ordinary config.
3. Run `systemctl --user daemon-reload`.
4. Restart the affected service.
5. Verify the bonded/private surface works.
6. Record that process-env credential exposure is temporarily accepted.
7. Reopen the hygiene slice before further credential work.

Failed credential validation must fail before Maez appears alive and must not
create noisy restart loops with secret names or values in logs.

### 11. Operator Forensics

Default health stays aggregate-only. A future or v1 local CLI may list missing
key names value-free for operator diagnosis.

Allowed:

```text
missing required credential: MAEZ_TELEGRAM_TOKEN
optional credential absent: MAEZ_GITHUB_TOKEN
```

Forbidden:

```text
loaded MAEZ_TELEGRAM_TOKEN
MAEZ_TELEGRAM_TOKEN followed by any value
hash of any secret value
```

The CLI must never list loaded optional names by default and must never print
values.

### 12. S2 / Information-Limb Inheritance

Future S2 information limbs must not invent per-connector credential loading.

Calendar, Gmail, Slack, Notion, Drive, GitHub, and other account connectors
should inherit:

- `core/infra/secrets.py` source-channel posture;
- no-value logging discipline;
- startup/feature validation shape;
- source-channel-only health surface;
- subprocess env hygiene;
- Decision 24 body-limb credential posture.

This slice does not implement OAuth storage. It creates the credential interface
S2 should use later.

---

## Non-Goals

- No credential values, prefixes, hashes, or validity proofs in docs, tests, or
  logs.
- No provider calls during the spec.
- No provider-side rotation; already completed.
- No migration of every `os.environ.get(...)` reader in v1.
- No movement of ordinary config into secret storage.
- No secrets manager dependency.
- No OAuth account-connector implementation.
- No S2 fold work.
- No changes to M1, TRF, S1b, Body Topology, or the project panel.
- No git history rewrite.
- No claim that secrets are absent from daemon memory.
- No claim that v1 closes all possible same-UID introspection or memory-dump
  surfaces.
- No claim that web/iPhone credential hygiene is closed unless the web surface
  is migrated or explicitly listed as residual risk.

---

## Implementation Ladder

1. Add RED tests for `core/infra/secrets.py` source priority,
   startup validation, source-channel logging, no value logging, and aggregate
   health report shape.
2. Add RED test proving runtime Python `os.environ` assignment is not visible
   through `/proc/<pid>/environ` on Linux.
3. Add RED tests for sanitized subprocess env helper excluding secret-shaped
   names.
4. Implement `core/infra/secrets.py`.
5. Wire daemon/web startup to load ordinary config, then load secrets, then
   compatibility-populate `os.environ`, then import/initialize secret readers.
6. Split local config storage: ordinary config remains in `config/.env`; secrets
   move to `config/secrets.local.env` or systemd credentials.
7. Add `.gitignore` and backup-manifest handling for `config/secrets.local.env`.
8. Update `maez.service`, web surface posture, active adjacent units, and
   shipped templates so secret values are no longer in active initial process
   environments; mark dormant residual risk explicitly.
9. Route high-risk daemon subprocess launch sites through sanitized env helper.
10. Remove iPhone JSON-body token fallback or explicitly record it as residual
    risk until the operator Shortcut is updated.
11. Add value-logging scan command or script and test fixtures.
12. Add rollback flag and rollback runbook test.
13. Update backup/succession manifest documentation so secret local files are
    carried in operator backup without entering git.
14. Restart daemon, verify `/health`, verify no secrets in
    `/proc/<maez-pid>/environ` by key-name/hash-free scan, and verify provider
    surfaces still authenticate without printing values.

---

## Test Contract

Minimum RED-first tests:

1. **Source priority:** systemd credential source wins over fallback file.
2. **Fallback source:** `config/secrets.local.env` loads when no systemd
   credential source exists.
3. **Mixed source semantics:** systemd credentials win per key while fallback
   fills missing keys, and health reports `mixed` only when both sources
   contributed loaded secrets.
4. **Malformed fallback rejected:** duplicate keys, malformed non-comment
   lines, and empty required values in `config/secrets.local.env` fail startup.
5. **No `.env` secret source:** loader refuses to treat `config/.env` as a
   secret source.
6. **Ordinary config untouched:** non-secret env values remain readable through
   existing config paths.
7. **Required present:** required secret validation passes when required names
   are present and non-empty.
8. **Required missing:** missing required secret fails at startup with key name
   only and no values.
9. **Optional absent:** optional secret absence does not fail daemon startup.
10. **Compatibility population:** v1 loader can populate `os.environ` for
   existing readers.
11. **Bootstrap order:** secret-reading modules do not observe secret-bearing
    names before the loader compatibility-populates `os.environ`.
12. **`/proc` regression:** runtime `os.environ` assignment is not visible in
   `/proc/<pid>/environ` on this Linux host; if visible, test fails with an
   instruction that compatibility v1's exposure claim is invalid.
13. **Source-channel logs:** startup logs source channel only.
14. **No key-name inventory in logs:** logs do not list loaded secret names.
15. **No values in logs:** fake secret values never appear in logs.
16. **Health aggregate only:** health exposes source and aggregate counts, not
    loaded names or values.
17. **Sanitized env excludes secrets:** helper removes names containing
    `TOKEN`, `API_KEY`, `SECRET`, `PASSWORD`, and `CREDENTIAL`.
18. **Sanitized env keeps operational basics:** default helper preserves
    non-secret operational variables such as `PATH`, `HOME`, `MAEZ_HOME`,
    `DISPLAY`, `XAUTHORITY`, `DBUS_SESSION_BUS_ADDRESS`, `SSH_AUTH_SOCK`,
    `VIRTUAL_ENV`, and `PYTHONPATH` when present.
19. **Sanitized env explicit opt-in:** a call site can pass one reviewed
    secret-shaped name only through an exact allowlist, while unrelated
    secret-shaped names remain excluded.
20. **Subprocess wrapper use:** high-risk daemon subprocess call sites use the
    sanitized helper or carry an explicit reviewed exception.
21. **Service-scoped iPhone token requirement:** missing
    `MAEZ_IPHONE_INGEST_TOKEN` fails startup or disables only the web/ingest
    surface while `/api/iphone/ingest` is mounted, not the private Telegram
    daemon.
22. **Telegram token requirement:** missing `MAEZ_TELEGRAM_TOKEN` fails startup
    for the bonded daemon.
23. **Public/dev Telegram degradation:** missing public/dev Telegram tokens do
    not degrade the private bonded surface.
24. **Optional provider degraded:** missing GitHub/Cloudflare/frontier optional
    secret disables or fails only that provider path.
25. **iPhone header-only transport:** JSON-body token fallback is removed or
    explicitly reported as residual risk.
26. **Pattern scanner catches synthetic leak:** scanner fails on a real-looking
    fake token in captured output.
27. **Pattern scanner allows explicit fixtures:** scanner allowlists known fake
    fixture strings used by tests.
28. **Systemd template posture:** shipped service templates no longer instruct
    operators to put identity-bearing secrets in the daemon's exec
    `EnvironmentFile=`.
29. **Active/dormant inventory:** live systemd unit/timer inventory classifies
    each Maez-related unit as migrated, residual risk, dormant template, or not
    installed.
30. **Fallback secret file ignored:** `config/secrets.local.env` is gitignored
    before migration.
31. **Backup manifest:** `config/secrets.local.env` is covered by encrypted
    destination / secret-file backup semantics.
32. **Rollback flag:** `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` bypasses the new
    loader and restores v0 local-env behavior for recovery.
33. **Rollback logs:** rollback never prints values and clearly records that
    process-env exposure is temporarily reaccepted.
34. **No values in docs:** spec/diagnostic examples include names and patterns
    only, not values or hashes.
35. **S2 inheritance pointer:** docs name this interface as future
    information-limb credential source.

Live verification after implementation:

1. Restart `maez.service`.
2. Confirm `/health` reports credential aggregate status without names/values.
3. Confirm `MAEZ_TELEGRAM_TOKEN`, `MAEZ_IPHONE_INGEST_TOKEN`, and other secret
   names are absent from `/proc/<maez-pid>/environ`.
4. Confirm ordinary config names remain available as expected.
5. Confirm Telegram bonded surface and iPhone ingest auth still work without
   printing values.
6. Verify every v1 mandatory daemon-owned subprocess path, or record a reviewed
   residual-risk exception, and confirm child environments do not contain
   secret-shaped names.
7. Confirm active Maez-related units either migrated or have explicit residual
   risk status; do not infer repo-wide closure from `maez.service` alone.
8. Confirm `cycle_count` advances after restart, `last_cycle` is non-null, and
   at least one post-restart cycle reaches beyond the M1 flush stage.
9. Confirm `/health.lived_episodes.m1.enabled` matches pre-migration intent and
   M1 staleness does not regress.
10. Confirm `systemctl restart maez.service` exits cleanly with no SIGKILL,
    escalation, traceback, or stale predecessor PID.

---

## Resolved Review Questions

### Codex Engineering Panel

1. `LoadCredential=` plus `config/secrets.local.env` is acceptable for v1 if
   implementation proves user-service `$CREDENTIALS_DIRECTORY` behavior on this
   host and avoids `SetCredential=`.
2. V1 uses one credential file per secret under `$CREDENTIALS_DIRECTORY`.
3. Compatibility population into Python `os.environ` is acceptable for parent
   process exposure because the measured `/proc` behavior supports it.
4. Subprocess hygiene is sufficient only with default-minus-secret behavior,
   explicit opt-in pass-through tests, and mandatory high-risk call-site
   enforcement.
5. `MAEZ_TELEGRAM_TOKEN` is required for `maez.service`; `MAEZ_IPHONE_INGEST_TOKEN`
   is required for the web/iPhone surface while the route is mounted.
6. Adjacent services are sequenced by active/dormant inventory. Active services
   must migrate or be named residual risk; dormant templates can update without
   live `/proc` proof.
7. Pattern scans are feasible with fixture allowlisting.
8. Remaining leak paths are web/iPhone route posture, subprocess inheritance,
   backup/restore ambiguity, and active adjacent units; this revision names all
   of them as v1 requirements or residual-risk gates.

### Claude Covenant Council

1. Credentials are identity-bearing material under invariant #11.
2. Source-channel-only visibility is sufficient recovery signal without turning
   logs into a credential map.
3. Bonded-surface continuity requires service-scoped startup validation:
   private Telegram fails loud when its key is missing; unrelated optional
   surfaces degrade without breaking the private bond.
4. S2 inheritance is clean because this slice creates the interface and source
   posture only; it does not implement OAuth/account connectors.
5. V1/v2 split is pragmatic if rollback is documented and if subprocess
   inheritance is not deferred past the v1 exposure claim.

---

## Observation / Closure

This slice closes only after implementation and live verification show:

- provider-side rotated credentials remain working;
- active service inventory has no unacknowledged credential-env residual risk;
- `maez.service` initial environment no longer contains secret names;
- `/proc/<maez-pid>/environ` does not expose secret names;
- daemon child-process paths audited in v1 do not inherit secret-shaped names;
- health/logs expose source channel and aggregate status only;
- web/iPhone credential hygiene is migrated or explicitly recorded as residual
  risk;
- `config/secrets.local.env` is ignored by git and covered by secret-file backup
  semantics;
- rollback path is tested and documented;
- M1 observation remains healthy after restart, including
  `/health.lived_episodes.m1.enabled` matching pre-migration intent;
- heartbeat advances after restart, with `cycle_count` increasing and
  `last_cycle` non-null;
- shutdown remains clean after the credential migration restart, with no
  SIGKILL/escalation/traceback/stale predecessor PID.

---

## Plain English

The keys are fresh now, but they are still sitting in Maez's launch pocket. This
slice moves them into a locked drawer.

The trick is not to make every setting a secret. Model names, ports, display
settings, and feature flags can stay in the normal config file. Actual keys and
tokens move out.

On this machine, a useful thing is true: if Python loads a secret after the
daemon starts, that secret does not show up in `/proc/<pid>/environ`. So v1 can
keep old readers working while still hiding keys from the easy process-list
surface. But there is one little tunnel: subprocesses can inherit Python's
environment. So v1 must also teach Maez to launch child processes with a cleaned
environment, or else the keys leak through the children.

The result should be simple: Maez starts, checks that the keys it truly needs
exist for that specific surface, logs only where the keys came from, never logs
the keys themselves, and keeps ordinary config ordinary. The private Telegram
daemon should not fail because the iPhone web-ingest key is missing; each body
surface gets its own key profile.
