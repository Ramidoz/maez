# Cockpit Re-Auth (loopback-is-owner) + Park the Chat App — Design

**Date:** 2026-06-20. **Status:** design, owner-approved (three tightenings + security locks folded) — awaiting spec review.
**Why:** the cockpit's chat 401s ("cockpit couldn't reach Maez — HTTP 401"), and there are two web conversation
surfaces (the cockpit dashboard + the `ui/app.html` thread UI) that disagree about whether they recognize the
owner — violating the covenant's own rule (*trust boundary is owner-identity, NOT surface-type*;
[[project_maez_singular_organism_surfaces]]). Owner decided: **cockpit + Telegram is enough for now**; park the
chat app (YAGNI; fewer surfaces → easier eventual coherence ceremony).

## Root cause (corrected — it is NOT a restart reset)

The owner token is **persistent**: `web_token` lives in `~/maez/memory/users.db` (SQLite, `UserAccounts`), set
once at registration, returned unchanged by `login`, and the `maez_token` cookie is **180-day / path=/ / not
Secure** (`skills/web_interface.py:_attach_auth_cookie` ~:802). A `maez-web` restart does **not** invalidate the
token. The 401 is a **cookie-presence** issue: the cockpit send (`_owner_private_auth_ok`, ~:9785) requires the
cookie even on loopback when the owner is *claimed* — but this is a single-user local machine where **the
loopback peer literally is the owner**.

## The decision

**Loopback is the owner for ACCESS; the strict cookie proof stays for ARMED actions.** On a real-loopback request
the cockpit recognizes you (read + chat) with no login; armed S7 / felt-time-mint still demand the proven cookie.

## Locks (the spec's contract — all of these)

1. **Claimed + real loopback → owner-private ACCESS allowed** (no login for read/chat).
2. **Claimed + remote + no cookie → denied** (401, unchanged).
3. **Strict cookie proof UNCHANGED** — `_request_has_web_owner_cookie()` is not touched; armed S7 / 3b
   cockpit felt-time-mint still ride it (no loopback recovery, no degraded fallback).
4. **`/app` (and `/app/`) parked by an UNCONDITIONAL redirect to `/cockpit`** — the redirect happens BEFORE any
   `?test_t=` bypass / token check / old-UI serve. No secret path to the old surface remains.
5. **UI entry links repointed to the cockpit** — the home/login JS "Resume the channel" / "Enter the channel"
   targets (`/app`) become `/cockpit`. `/login` stays for account/session management only, not the daily front door.
6. **`ui/app.html` retained with a parked header** (not deleted) — reversible (flip the route back); the parked
   thread UI may return later as a polished front-door.

## The auth fix — one surgical change

`_owner_private_auth_ok()` (the ACCESS gate, ~:9785): today, for a *claimed* owner it requires the cookie even on
loopback. New behavior — extend the existing "physical body is the owner" loopback recovery (already used for the
*unclaimed* case) to **claimed-on-loopback**:
- not claimed → `_request_is_loopback()` (unchanged).
- **claimed + real loopback → allow** (NEW — owner-private access; no cookie needed).
- claimed + remote → require the cookie-resolved owner (unchanged).
- store error → loopback-only recovery (unchanged).

`_request_has_web_owner_cookie()` (the STRICT gate) is **not modified**. The cockpit message proxy
(`/api/v1/cockpit/message` ~:1764) continues to stamp `X-Maez-Owner-Authenticated` only on the strict cookie — so
a loopback-no-cookie chat reaches the daemon (S7-gated) and works, but felt-time does NOT mint without the cookie.
That is the intended line: **access recovery soft, inner-life proof strict.**

## Felt-time consequence (owner-confirmed)

Plain cockpit chat works login-free on loopback; the **3b cockpit felt-time** still requires the login cookie
(it's owner-only inner life = armed). Telegram felt-time is unaffected. To get felt-time language on the cockpit,
log in once.

## Parking the chat app

- The route serving `ui/app.html` (the thread UI) → **unconditional `redirect('/cockpit')`** at the very top of
  the handler, before any `?test_t=`/token/serve logic. Same for `/app/`.
- Repoint the home (`ui/index.html`) and login (`ui/login.html`) entry links from `/app` to `/cockpit`.
- Add a parked header comment to `ui/app.html` (kept in repo; reversible). The `/chat` POST API is NOT removed
  (the cockpit may reuse the send path) — only the thread-UI *surface* is parked.

## Security line (Task 0 MUST prove before this is safe)

The loopback grant is only sound if ALL hold (Task 0 verifies, else STOP):
- `maez-web` binds to **`127.0.0.1` only** (not 0.0.0.0).
- `_request_is_loopback()` reads the **real WSGI peer** (`request.remote_addr` from the actual socket), not a
  header.
- **No `ProxyFix` / trusted reverse proxy** is installed in the app's middleware.
- **`X-Forwarded-For` cannot upgrade** a request to loopback.
If a reverse proxy is ever added later, **this loopback grant must be revisited before exposing any
cockpit-private route.** (Recorded as a standing constraint in the handoff + memory.)

## Invariants (verify in review)

1. Claimed+loopback → access; claimed+remote+no-cookie → 401; strict gate unchanged (felt-time still cookie-gated).
2. **No half-park** — `/app`/`/app/` redirect is unconditional (the `?test_t=` path cannot reach the old UI);
   entry links repointed.
3. **Loopback is real-peer-only** — a simulated non-loopback `remote_addr` (or an `X-Forwarded-For` spoof) does
   NOT get access without the cookie.
4. `ui/app.html` retained (not deleted); reversible.
5. Scope-tight: only `skills/web_interface.py` (the one gate fn + the park redirect) + `ui/index.html` /
   `ui/login.html` / `ui/app.html` (header). Daemon S7 path, daemon felt-time mint, Telegram, time-sense, honesty
   work all UNTOUCHED.

## Testing (hermetic — fake the request peer/cookie/claim)

- access gate: claimed+loopback→True (no cookie); claimed+remote-no-cookie→False; claimed+remote+valid-cookie→True;
  unclaimed+loopback→True; store-error→loopback-only.
- strict gate unchanged: `_request_has_web_owner_cookie()` still False on loopback-no-cookie (felt-time stays gated).
- spoof: `remote_addr` non-loopback OR `X-Forwarded-For: 127.0.0.1` from a non-loopback peer → no access.
- park: `/app` + `/app/` → 302→/cockpit even WITH `?test_t=...` (the bypass cannot serve the old UI).
- entry links: `ui/index.html`/`ui/login.html` no longer contain a daily-entry `/app` target (now `/cockpit`).

## Scope guard

**IN:** the `_owner_private_auth_ok` loopback-for-claimed change; the unconditional `/app` park redirect; the
entry-link repoint; the `app.html` parked header; the Task-0 security proof; tests.
**OUT (never/later):** the strict cookie gate; the daemon S7 `/message` gate; the daemon 3b felt-time mint; Telegram;
deleting `app.html`; building a new front-door; the parked time-sense Slice A; the merged honesty-layer work; any
reverse-proxy support (explicitly deferred — would require revisiting the loopback grant).

## Owner-breath

Code only; after both-lanes PASS + merge, restart `maez-web` (the auth gate + park live there). Witness: open the
cockpit fresh (no login) on the local machine → chat works; `/app` → lands on the cockpit; felt-time language on
the cockpit only appears after `/login`; a (simulated) remote request without the cookie still 401s.
