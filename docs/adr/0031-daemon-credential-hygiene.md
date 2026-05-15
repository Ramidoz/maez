# ADR 0031: Daemon Credential Hygiene

**Status:** Accepted
**Date:** 2026-05-14

## Context

Maez's provider-side credentials were rotated, but the live daemon still loaded
fresh identity-bearing secrets through `config/.env` as a systemd
`EnvironmentFile`. That meant the new keys remained visible through the initial
process environment surface (`ps auxe`, `/proc/<pid>/environ`) for any process
started with those values at `execve()`.

The diagnostic measured the Linux behavior that underwrites a compatibility v1:
runtime Python `os.environ[...] = ...` assignments did not appear in
`/proc/<pid>/environ` on this host. That empirical result makes a staged
migration possible: remove secrets from the initial environment, load them
inside the process after startup, and keep old env-based readers working while
reducing the visible process-environment exposure.

Pre-canonical review ran both lanes. Claude's six-role covenant council returned
RATIFY-WITH-AMENDMENTS. Codex's six-agent engineering panel returned REVISE,
catching service-boundary and implementation-realism issues: credentials must
be profiled per service, `maez-web` / iPhone ingest must be modeled explicitly,
bootstrap order must prevent import-time `.env` leaks, subprocess inheritance
must be part of v1, and rollback/active-unit closure must be documented. The
folded packet closes those issues before code.

## Decision

Maez treats identity-bearing credentials as a distinct secret class, not as
ordinary configuration.

V1 keeps ordinary config in `config/.env`, moves secrets into systemd
credentials or `config/secrets.local.env`, validates required credentials per
active service, then compatibility-populates Python `os.environ` only after
process start. The measured `/proc/<pid>/environ` behavior is part of the
contract and must be preserved by a regression test.

The load-bearing rule is:

> Keys are identity-bearing material, not ordinary config.

V1 also requires:

- one credential file per secret under `$CREDENTIALS_DIRECTORY`;
- no `SetCredential=` values embedded in unit text;
- `config/.env` never used as a secret source;
- source-channel-only logging (`systemd-credentials`, `secrets-local-env`,
  `none`, or `mixed`);
- service-scoped required/optional credential profiles;
- default-minus-secret subprocess environments with explicit opt-in
  pass-through tests;
- active-vs-dormant systemd unit inventory before closure;
- rollback via `MAEZ_SECRETS_DISABLE_NEW_LOADER=1`;
- backup/succession handling for `config/secrets.local.env` as
  encrypted-destination-only owner-local secret state;
- no health/log/snapshot output containing secret values or loaded-secret
  inventories.

Future S2 information limbs inherit this credential interface and source-channel
audit posture. OAuth/account connectors must not invent connector-specific
secret loaders.

## Consequences

This decision reduces the easy credential exposure surface without forcing a
large reader rewrite in the same patch. Existing `os.environ.get(...)` readers
can keep working in v1, but secrets are removed from the initial systemd
environment and daemon subprocesses must not inherit secret-shaped names by
default.

The decision also narrows blast radius: `maez.service`, `maez-web`, public/dev
Telegram surfaces, subscription proxy, dynamic DNS, GitHub helpers, observability
providers, and future information limbs get service-scoped credential profiles
instead of one global "all Maez secrets everywhere" shape.

Implementation is pre-code and RED-first. It must prove the `/proc` assumption,
the secret-source precedence, source-channel logging, value-free health,
subprocess env sanitization, service-scoped startup validation, rollback, backup
manifest handling, and live post-restart behavior. Live closure requires M1 to
remain enabled/healthy, heartbeat to advance after restart, and shutdown to
remain clean.

Changing the load-bearing rule, allowing secrets in the initial daemon
environment, dropping the `/proc` regression test, widening health/log output to
loaded key names or values, removing subprocess env hygiene from v1, or giving
future S2 information limbs a separate credential-loading path requires a new
reviewed decision.

Full diagnostic, spec, test contract, rollback posture, and review trail:
[`docs/slices/daemon-credential-hygiene/spec.md`](../slices/daemon-credential-hygiene/spec.md).

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 26.
