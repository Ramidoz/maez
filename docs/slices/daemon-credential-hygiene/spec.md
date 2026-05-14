# Slice: Daemon Credential Hygiene

**Status:** DRAFT. Built from
[`diagnostic.md`](diagnostic.md). Awaiting Codex engineering panel and Claude
covenant council review before canonicalization or code.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) — current env ingress, reader inventory,
  `/proc/<pid>/environ` measurement, subprocess inheritance risk, git-history
  note.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) —
  governance anchor. This slice is expected to become the next BAD decision if
  ratified.
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
3. validate required secrets before the daemon is alive;
4. populate compatibility environment values only after process start;
5. sanitize daemon subprocess environments enough that compatibility loading
   does not immediately leak through child processes;
6. log only the source channel, never key names or values;
7. test the Linux `/proc` assumption that makes v1 a real exposure reduction.

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

Systemd credentials may be implemented as one credential bundle or one file per
secret. The implementation should choose the shape that is easiest to manage
without exposing values in unit files. Systemd exposes credentials to the
service under `$CREDENTIALS_DIRECTORY`; the service then reads them at startup.

### 2. Secret Loader

Add `core/infra/secrets.py`.

Required behavior:

- Read systemd credentials first if `$CREDENTIALS_DIRECTORY` is present and
  contains Maez credentials.
- Fall back to `config/secrets.local.env` if no systemd credentials are
  available.
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

### 3. Startup Validation

Required secrets fail loud at startup before Maez becomes alive.

V1 required for `maez.service`:

```text
MAEZ_TELEGRAM_TOKEN
MAEZ_IPHONE_INGEST_TOKEN
```

Rationale:

- Telegram is the current bonded surface.
- iPhone ingest route is mounted unconditionally and should not run in a
  silently unusable auth state.

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

### 6. Subprocess Environment Hygiene

V1 must add a sanitized subprocess environment helper.

Default sanitized env should include only operational values needed for local
child processes, such as:

```text
PATH
HOME
USER
LOGNAME
SHELL
LANG
LC_ALL
MAEZ_HOME
DISPLAY
XAUTHORITY
XDG_RUNTIME_DIR
PIPEWIRE_RUNTIME_DIR
```

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

V1 must route high-risk daemon-owned subprocess launches through the helper.
At minimum, implementation should inspect and either update or justify:

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

### 9. S2 / Information-Limb Inheritance

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
5. Wire daemon startup to load and validate secrets before starting Telegram,
   web routes, M1, or background workers.
6. Split local config storage: ordinary config remains in `config/.env`; secrets
   move to `config/secrets.local.env` or systemd credentials.
7. Update `maez.service` and shipped templates so secret values are no longer
   in the initial process environment.
8. Route high-risk daemon subprocess launch sites through sanitized env helper.
9. Add value-logging scan command or script and test fixtures.
10. Update backup/succession manifest documentation so secret local files are
    carried in operator backup without entering git.
11. Restart daemon, verify `/health`, verify no secrets in
    `/proc/<maez-pid>/environ` by key-name/hash-free scan, and verify provider
    surfaces still authenticate without printing values.

---

## Test Contract

Minimum RED-first tests:

1. **Source priority:** systemd credential source wins over fallback file.
2. **Fallback source:** `config/secrets.local.env` loads when no systemd
   credential source exists.
3. **No `.env` secret source:** loader refuses to treat `config/.env` as a
   secret source.
4. **Ordinary config untouched:** non-secret env values remain readable through
   existing config paths.
5. **Required present:** required secret validation passes when required names
   are present and non-empty.
6. **Required missing:** missing required secret fails at startup with key name
   only and no values.
7. **Optional absent:** optional secret absence does not fail daemon startup.
8. **Compatibility population:** v1 loader can populate `os.environ` for
   existing readers.
9. **`/proc` regression:** runtime `os.environ` assignment is not visible in
   `/proc/<pid>/environ` on this Linux host; if visible, test fails with an
   instruction that compatibility v1's exposure claim is invalid.
10. **Source-channel logs:** startup logs source channel only.
11. **No key-name inventory in logs:** logs do not list loaded secret names.
12. **No values in logs:** fake secret values never appear in logs.
13. **Health aggregate only:** health exposes source and aggregate counts, not
    loaded names or values.
14. **Sanitized env excludes secrets:** helper removes names containing
    `TOKEN`, `API_KEY`, `SECRET`, `PASSWORD`, and `CREDENTIAL`.
15. **Sanitized env keeps operational basics:** helper preserves required local
    operational variables such as `PATH`, `HOME`, `MAEZ_HOME`, `DISPLAY`, and
    `XAUTHORITY` when present.
16. **Subprocess wrapper use:** high-risk daemon subprocess call sites use the
    sanitized helper or carry an explicit reviewed exception.
17. **iPhone token requirement:** missing `MAEZ_IPHONE_INGEST_TOKEN` fails
    startup while `/api/iphone/ingest` is mounted unconditionally.
18. **Telegram token requirement:** missing `MAEZ_TELEGRAM_TOKEN` fails startup
    for the bonded daemon.
19. **Optional provider degraded:** missing GitHub/Cloudflare/frontier optional
    secret disables or fails only that provider path.
20. **Pattern scanner catches synthetic leak:** scanner fails on a real-looking
    fake token in captured output.
21. **Pattern scanner allows explicit fixtures:** scanner allowlists known fake
    fixture strings used by tests.
22. **Systemd template posture:** shipped service templates no longer instruct
    operators to put identity-bearing secrets in the daemon's exec
    `EnvironmentFile=`.
23. **No values in docs:** spec/diagnostic examples include names and patterns
    only, not values or hashes.
24. **S2 inheritance pointer:** docs name this interface as future
    information-limb credential source.

Live verification after implementation:

1. Restart `maez.service`.
2. Confirm `/health` reports credential aggregate status without names/values.
3. Confirm `MAEZ_TELEGRAM_TOKEN`, `MAEZ_IPHONE_INGEST_TOKEN`, and other secret
   names are absent from `/proc/<maez-pid>/environ`.
4. Confirm ordinary config names remain available as expected.
5. Confirm Telegram bonded surface and iPhone ingest auth still work without
   printing values.
6. Launch at least one daemon-owned subprocess path and verify its environment
   does not contain secret-shaped names.

---

## Review Questions

### Codex Engineering Panel

1. Is `LoadCredential=` plus `config/secrets.local.env` the right v1 source
   shape for a user-scoped service on this machine?
2. Should v1 use one credential bundle or one file per secret?
3. Is compatibility population into Python `os.environ` acceptable given the
   measured `/proc` behavior?
4. Is the sanitized subprocess helper sufficient for v1, and which call sites
   must be mandatory in the first patch?
5. Are `MAEZ_TELEGRAM_TOKEN` and `MAEZ_IPHONE_INGEST_TOKEN` the right required
   daemon startup secrets?
6. How should adjacent services (`maez-subscription-proxy`,
   `maez-lived-memory-reflection`, self-dev scheduled service) be sequenced so
   the slice does not overclaim?
7. What pattern-scan rules catch real leaks without making fixtures
   unmaintainable?
8. Does the spec leave any path where a secret value can appear in logs, health,
   snapshots, subprocess env, or test output?

### Claude Covenant Council

1. Does the load-bearing rule correctly treat credentials as identity-bearing
   material under invariant #11?
2. Does source-channel-only visibility give Future-Rohit enough recovery signal
   without turning logs into a credential map?
3. Does requiring startup validation for Telegram and iPhone ingest preserve
   the bonded-surface continuity expectation?
4. Does the S2 inheritance pointer correctly connect future information limbs
   without smuggling OAuth connector work into this slice?
5. Does the v1/v2 split preserve the covenant surface while staying pragmatic?

---

## Observation / Closure

This slice closes only after implementation and live verification show:

- provider-side rotated credentials remain working;
- `maez.service` initial environment no longer contains secret names;
- `/proc/<maez-pid>/environ` does not expose secret names;
- daemon child-process paths audited in v1 do not inherit secret-shaped names;
- health/logs expose source channel and aggregate status only;
- M1 observation remains healthy after restart;
- heartbeat remains `cycle_stalled=false`;
- shutdown remains clean after the credential migration restart.

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
exist, logs only where the keys came from, never logs the keys themselves, and
keeps ordinary config ordinary.
