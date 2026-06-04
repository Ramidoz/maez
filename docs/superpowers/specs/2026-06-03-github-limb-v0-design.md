# GitHub Limb v0 — read-only "open the eye" smoke (device flow) — DESIGN

**Date:** 2026-06-03
**Status:** APPROVED design (delta off the Reddit v0 spec). Owner chose GitHub after Reddit gated app creation behind its Responsible Builder Policy (pre-approval now required, even for personal apps — updated 2026-05-18). Build is **Codex-implements? No — Claude-implements / Codex-reviews** (this session's lane).
**Base spec:** `docs/superpowers/specs/2026-06-03-reddit-limb-v0-design.md`. **All covenant rails, the hardened-handoff design, the content-free tile, the four covenant guard tests, and the acceptance criteria are IDENTICAL** — this doc states only the GitHub-specific deltas. **Branch:** `github-limb-v0`.

---

## Why GitHub, why device flow

Reddit's self-serve "installed app, no approval" path no longer exists (policy change). GitHub OAuth App creation is still free + self-serve. GitHub offers **device flow**, which needs **only a client_id — no client_secret** (unlike its redirect flow, and unlike Reddit). That is *more* covenant-aligned than the Reddit design: one fewer confidential secret to hold. So v0 uses device flow, no loopback listener.

This becomes the **first working Personal Data Limb** (Reddit stays built-but-dormant on main, revive-if-approved). Generalizing the two into a generic connector is a LATER slice (YAGNI now — mirror the proven Reddit shape).

## Deltas from the Reddit v0 spec

### Scope / endpoint
- **Scope:** `read:user` (read-only profile) — the identity-only analog. Pin enforced at the handoff: reject any scope outside `{read:user}`.
- **Identity call:** `GET https://api.github.com/user` with `Authorization: Bearer <token>` + a fixed `User-Agent`. 200 = identity confirmed; the body (login/id) is **discarded** (same as Reddit — tile records state only, never the username).

### Auth = OAuth device flow (replaces authorize-url + loopback exchange)
Owner prerequisite: create a GitHub **OAuth App** (github.com/settings/developers → New OAuth App), then **Enable Device Flow** on it; copy the **Client ID** (no secret). Homepage/callback URLs are required fields but unused by device flow (`http://localhost`).

Ceremony (`scripts/github_connect.py`, owner-run, device flow):
1. `POST https://github.com/login/device/code` with `client_id`, `scope=read:user`, `Accept: application/json` → `{device_code, user_code, verification_uri, expires_in, interval}`.
2. Print: "Go to **https://github.com/login/device** and enter code **`<user_code>`**" (open the browser to it).
3. Poll `POST https://github.com/login/oauth/access_token` with `client_id`, `device_code`, `grant_type=urn:ietf:params:oauth:grant-type:device_code`, `Accept: application/json` every `interval` s:
   - `authorization_pending` → keep polling; `slow_down` → increase interval by 5s; `expired_token`/`access_denied` → abort with a friendly message; success → `{access_token, scope, token_type}`.
4. Hand the token to the daemon over the **same hardened loopback handoff** (`POST /internal/limb/github/session`, `X-Maez-Github-Handoff` + `MAEZ_GITHUB_HANDOFF_TOKEN`, auth-before-envelope) — identical to Reddit's design, dedicated GitHub secret (isolated trust domain; NOT the Reddit secret, NOT the S7 channel, NOT Maez's operational `MAEZ_GITHUB_TOKEN` git PAT).

### Module / route / tile / secret names (GitHub-namespaced)
- `core/information_limb/github_limb.py` — mirrors `reddit_limb.py`: `request_device_code()`, `poll_for_token()` (ceremony-side helpers), `fetch_identity()`, `GithubLimb` (in-memory session + content-free `health()`), `handoff_trusted()`/`handle_handoff()` (identity-only pin = reject scope ∉ {read:user}).
- Daemon route `POST /internal/limb/github/session`; body tile key `github_limb` in `maez_body.v0` (the `test_maez_body_organ_view` schema-pin test MUST be updated to include it — learned from the Reddit slice).
- `scripts/github_connect.py` — the device-flow ceremony.
- Secrets: `MAEZ_GITHUB_CLIENT_ID` (not a secret → `config/.env`), `MAEZ_GITHUB_HANDOFF_TOKEN` (secret → allowlist in `core/infra/secrets.SECRET_NAMES`, lives in `config/secrets.local.env`). Ceremony loads both via `load_ordinary_config_for_process()` + `load_secrets_for_process()`.

### Tile (content-free, identical shape)
```json
"github_limb": {"state": "needs_auth|available|auth_error|revoked|rate_limited|unreachable",
                "last_success_at": "<iso|null>", "scopes": ["read:user"], "expires_in_bucket": "..."}
```
Note: device-flow tokens for OAuth Apps typically do not expire / have no refresh in v0 — `expires_in_bucket` will usually be `none`/`fresh`; still in-memory only, restart → `needs_auth`.

## UNCHANGED from the Reddit spec (do not re-derive)
Token-substrate-only / never logged; read-only; no ingestion; no LLM; no cloud egress; fail-closed; loopback + dedicated-secret handoff with **auth-before-envelope** (verify secret before reading the token-bearing body); content-free telemetry; the four covenant guard tests; in-memory-only token. Acceptance = the same witness (`available` → restart → `needs_auth`; scopes show only `read:user`; token absent from logs/health/telemetry; no GitHub content in memory).

## Testing (same structure as Reddit, GitHub values)
Unit (mocked HTTP): device-code request shape; poll handles `authorization_pending`/`slow_down`/success/`expired_token`; `fetch_identity` 200→available/401→auth_error/403→revoked/429→rate_limited/timeout→unreachable, body discarded. Covenant guards: token-never-leaks, no-egress/LLM imports, persists-nothing, **auth-before-envelope** (body_loader never called on bad secret), **identity-only pin** (scope outside {read:user} → 400), **credential-loadable** (MAEZ_GITHUB_HANDOFF_TOKEN classified secret AND allowlisted). Daemon route test (standalone Flask client). Manual owner-run integration smoke (real device-flow consent → /user 200 → tile available → restart → needs_auth). FULL `unittest discover` before "done" (the schema-pin lesson).
