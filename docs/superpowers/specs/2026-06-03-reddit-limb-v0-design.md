# Reddit Limb v0 — read-only "open the eye" smoke — DESIGN

**Date:** 2026-06-03
**Status:** APPROVED design, ready for implementation plan. Owner + Claude brainstorm; build is **Codex-implements / Claude-reviews** ([[feedback_parallel_agents_for_maez]]).
**Context:** First concrete slice of the **Personal Data Limb Runtime** (settled design: `docs/superpowers/parked/2026-06-03-self-extending-senses-personal-data-ingestion-parked-sketch.md`). Slice 1 of that build order — the egress firewall (`owner_account_context` → blocks `cloud_model_inference`) — is **merged + live**. This is the first *limb* that breathes through that lock.

---

## 1. Goal (one sentence)

Prove Maez can **authenticate to Rohit's Reddit account with his browser consent and confirm its own identity (`/api/v1/me`)**, surfacing a content-free health tile — **without** holding his password, persisting anything, ingesting any content, or egressing anything.

Owner's framing: *"First prove Maez can open its eye with your permission. Don't ask it to read the room yet."*

## 2. Scope

**v0 (this slice) — identity-only:**
- Installed-app OAuth (authorization-code flow, loopback redirect), `duration=temporary`, scope = **`identity` only**.
- One authenticated call: `GET https://oauth.reddit.com/api/v1/me` → confirm HTTP 200 + a valid identity came back.
- A content-free body-health tile reflecting limb state.
- Token held **in memory only** in the running daemon; no disk, no refresh token.

**v0.1 (explicitly deferred behind a SECOND acceptance gate — NOT this slice):**
- Add scopes `history` (saved/upvoted/hidden) and/or `read` (listings/home), and one tiny content fetch.
- Still no ingestion/digestion/egress — just proving a content read.

**Out of scope entirely (later slices):** memory ingestion, LLM summarization, any cloud egress of Reddit payloads, refresh-token persistence / vault-at-rest, the generic connector/descriptor engine, the Privacy Filter, the provider registry.

## 3. Owner prerequisite (one-time, manual)

Rohit creates a Reddit **"installed app"** at <https://www.reddit.com/prefs/apps> (NOT "script", NOT "web app"):
- type: **installed app** (public client — no client secret).
- redirect URI: `http://localhost:65010/reddit/callback`.
- He provides the resulting **`client_id`** (not a secret; safe to place in `config/.env` as `MAEZ_REDDIT_CLIENT_ID`).

Installed apps authenticate the token exchange with HTTP Basic `client_id:` (empty password). No password, no secret ever enters Maez.

## 4. Architecture

Mirrors the existing **Calendar v1** personal-data limb (`core/information_limb/calendar_*.py` + `skills/calendar_perception.py` health), differing deliberately: installed-app OAuth (not google-auth), in-memory token (not `token.json`), identity-only, no ingestion.

Three units, each independently testable:

### 4.1 `core/information_limb/reddit_limb.py` — the limb (substrate-side state + fetch + health)
- Holds the in-memory session: `RedditSession(access_token, scopes, obtained_at, expires_at)` — process-memory only, never serialized.
- `build_authorize_url(client_id, redirect_uri, state, scopes) -> str` — pure function (no I/O), builds the reddit.com authorize URL (`response_type=code`, `duration=temporary`, `scope=identity`, `state=<csrf>`).
- `exchange_code_for_token(client_id, code, redirect_uri) -> RedditSession` — POST `https://www.reddit.com/api/v1/access_token`, Basic `client_id:`, `grant_type=authorization_code`. Required `User-Agent` header (fixed config string).
- `fetch_identity(session) -> bool` — `GET https://oauth.reddit.com/api/v1/me`; returns success/failure only. **Discards the body** (does not return or store the username/id); records only `state` + `last_success_at`.
- `health() -> dict` — the content-free tile (see §6).
- `set_session(session)` / `clear_session()` — the daemon's intake handle; clears on expiry.

### 4.2 `scripts/reddit_connect.py` — the one-shot ceremony (owner-invoked, ephemeral)
- Owner runs it. Reads `MAEZ_REDDIT_CLIENT_ID` from `config/.env`.
- Generates `state` (CSRF) + builds the authorize URL via `reddit_limb.build_authorize_url`; opens the browser (or prints the URL).
- Runs a **short-lived loopback HTTP listener** on `127.0.0.1:65010` for `/reddit/callback`; validates `state`; captures `code`; shuts down immediately after.
- Calls `reddit_limb.exchange_code_for_token` → obtains the access token in the **ceremony's** memory.
- **Hands the token to the running daemon** via the hardened loopback endpoint (§4.3): `POST http://127.0.0.1:<daemon_local_port>/limb/reddit/session`. The token crosses loopback exactly once.
- Prints a content-free result (`ok` / the tile state) and exits — the ceremony's copy of the token dies with the process.

### 4.3 Daemon hardened intake endpoint — `POST /limb/reddit/session`
- Added to the daemon's existing local API surface, reusing `core/infra/http_security.py` (loopback-only bind + the existing local-auth gate; reject non-127.0.0.1 and unauthenticated callers).
- Body: `{access_token, scopes, expires_in}`. The daemon calls `reddit_limb.set_session(...)`, immediately performs `fetch_identity`, sets the tile, and returns the content-free tile state (never echoes the token).
- This is the daemon's *only* token-bearing surface; the token lives in the daemon's process memory thereafter (session-scoped).

### 4.4 Body tile — `_body_health` addition
- Add `reddit_limb` to the `maez_body.v0` content-free organ map (alongside `eyes`, `memory`, etc.), so the existing owner dashboard shows it.

## 5. Data flow

```
Rohit ──creates installed app──> reddit.com (client_id)            [one-time, manual]
Rohit ──runs──> scripts/reddit_connect.py
   ceremony: build authorize URL ──browser──> Rohit consents at reddit.com
   reddit.com ──redirect code──> 127.0.0.1:65010/reddit/callback (ceremony listener)
   ceremony: code ──POST access_token (Basic client_id:)──> reddit.com ──> access_token
   ceremony ──POST /limb/reddit/session {token} (loopback+auth)──> daemon
   daemon: set_session(in-memory) ──GET /api/v1/me (bearer)──> oauth.reddit.com ──> 200
   daemon: tile = available, last_success_at = now   [body dashboard reflects it]
restart ──> in-memory session gone ──> tile = needs_auth
```

## 6. The body tile (content-free)

```json
"reddit_limb": {
  "state": "needs_auth | available | auth_error | revoked | rate_limited | unreachable",
  "last_success_at": "<iso8601 or null>",
  "scopes": ["identity"],
  "expires_in_bucket": "fresh | <30m | expired | none"
}
```
No username, no id, no post content, no token, no counts of personal items — ever. `schema_version` bumped or namespaced under the existing `maez_body.v0`.

## 7. Covenant rails (non-negotiable; enforced by tests in §9)

- **Tokens, never passwords** — installed-app OAuth; Rohit authenticates at reddit.com; Maez only ever holds a scoped token.
- **Token is substrate-only** — never in any prompt, chat transcript, log line, telemetry field, health output, or exception message. Redact on the way into any logger.
- **Read-only** — `identity` scope only in v0; no write scopes ever requested.
- **No ingestion / no digestion** — the limb persists nothing durable and never feeds memory or an LLM in this slice. `fetch_identity` discards the response body.
- **No cloud egress** — no Reddit-derived bytes reach any cloud-model path. (When v0.1+ ingests, that data is tagged `owner_account_context` and the live egress firewall blocks cloud inference by default.)
- **Fail closed** — any error → a tile state + no egress, never a silent "succeeded."
- **Loopback + auth only** — the intake endpoint binds 127.0.0.1 and rejects unauthenticated/non-loopback callers.
- **Content-free telemetry** — only the tile-state enum + timestamps + scope names; no Reddit content, no token.

## 8. Error handling (every failure → a tile state, fail-closed)

| Condition | Tile state |
|---|---|
| No session in memory (fresh boot / restart / cleared) | `needs_auth` |
| `/api/v1/me` 200 | `available` |
| Token expired (past `expires_at`) | `needs_auth` (no refresh in v0) |
| 401 / token rejected | `auth_error` |
| 403 / scope or app revoked | `revoked` |
| 429 / rate-limited (X-Ratelimit) | `rate_limited` |
| Network/DNS/timeout to reddit | `unreachable` |
| CSRF `state` mismatch at callback | ceremony aborts; nothing handed to daemon |

## 9. Testing

**Unit (no network — mock all HTTP):**
- `build_authorize_url` emits exactly `response_type=code`, `duration=temporary`, `scope=identity`, the configured `redirect_uri`, and a non-empty `state`; no secret present.
- `exchange_code_for_token` sends HTTP Basic `client_id:` (empty password), `grant_type=authorization_code`, the `User-Agent`; parses the token; builds a `RedditSession` with `expires_at`.
- `fetch_identity` maps 200→`available`, 401→`auth_error`, 403→`revoked`, 429→`rate_limited`, timeout→`unreachable`; and **returns/stores no identity fields**.
- Intake endpoint: rejects non-loopback origin; rejects unauthenticated; accepts a valid loopback+auth POST and never echoes the token.

**Covenant guard tests (the load-bearing ones):**
- **Token never leaks:** drive the full mocked flow with a sentinel token value, assert the sentinel appears in **no** log record, telemetry payload, `health()` output, or stringified exception.
- **No egress / no LLM:** a test (or AST/source-contract guard) that `reddit_limb.py` imports no cloud-egress/LLM-client module and reaches no `decide_egress`-cloud or `llm_client.chat` path.
- **Persists nothing:** source-contract test that the limb opens no sqlite/file for durable writes (no `open(...,'w')`, no `sqlite3.connect` to a real path) — session is memory-only.
- **Health is content-free:** `health()` keys ⊆ the §6 allowlist; values are enums/timestamps/scope-names only.

**Manual owner-run integration smoke (the witness, not in CI):**
- Real consent → `/api/v1/me` 200 → dashboard tile shows `available` + `last_success_at`. Restart daemon → tile shows `needs_auth`. Token never appears in `journalctl`/logs.

## 10. Acceptance

**v0 passes when:** the 4 covenant guard tests + the unit tests are green; the manual integration smoke shows `available` then `needs_auth` after restart; and a grep of logs/telemetry for the token sentinel is empty. Implementation reviewed by Claude (cross-lane), then merged to main locally (no push, no restart) per standing practice.

**v0.1 (separate slice, separate gate):** only after v0's witness passes does the owner decide whether to add `history`/`read` + one tiny content fetch — still no ingestion.

## 11. Notes / decisions captured

- `duration=temporary` (not `permanent`) → no refresh token → no persistence/vault decision now; restart returns `needs_auth` by design.
- One-shot ceremony → hardened loopback handoff chosen over daemon-runs-the-browser-flow: keeps the daemon's steady-state surface small (it only ever receives a short-lived token), ceremony is owner-invoked/visible/temporary.
- Supersede, don't extend, the dead `skills/reddit_skill.py` (unauthenticated public-JSON sub fetcher — a different thing; retire later).
- `User-Agent` is a fixed config string sent only to reddit.com (the owner's own service); it is never part of content-free telemetry.
