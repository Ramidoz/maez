# Handoff — Cockpit Re-Auth (loopback-is-owner) + Park Chat App — REVIEW GATE

**Date:** 2026-06-20. **Branch:** `cockpit-reauth-park-app` (tip = latest; see `git log`. local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed per task + a CAUGHT REGRESSION narrowed and re-reviewed. **STOPPED at the review gate** — awaiting Codex cross-lane, then owner breath (restart `maez-web`). NOT live.
**Spec:** `docs/superpowers/specs/2026-06-20-cockpit-reauth-park-chat-app-design.md` (@e3a094d). Base `main` @`f4e1a1f`.

## What this slice does (one line)

The local cockpit recognizes the loopback owner for **access/chat without login** (the physical peer is the owner — *unless an explicit non-owner cookie says otherwise*); the **strict cookie proof is untouched** for armed S7 / 3b felt-time; and the `/app` thread UI is **parked** by an unconditional redirect to `/cockpit`, with every live `/app` entry link repointed.

## Commits

- `5847d1e` docs(proof): Task 0 — **4 security proofs (GO)** + repo-wide `/app` inventory (5-bucket).
- `9e24dd3` fix: claimed owner on real loopback → owner-private access (first cut).
- `157f810` fix: park `/app` (unconditional redirect before `test_t`) + repoint every live `/app` entry.
- `f16ee88` fix: **explicit cookie identity wins over loopback (no non-owner escalation)** — the narrow fix.
- (this) docs(handoff).

Net vs main: `web_interface.py +32/−`, 5 `ui/*.html` (repoints), `app.html` (parked header), 3 test files, 1 proof doc. Surgical (+390/−22).

## The 4 SECURITY PROOFS (Task 0 — all hold; standing constraint below)

1. `maez-web` binds **127.0.0.1 only** (`web_interface.py:10512` `app.run(host="127.0.0.1", port=11437)`).
2. `_request_is_loopback()` (:160) reads the **raw WSGI `request.remote_addr`**, never a header.
3. **No `ProxyFix`** / trusted reverse proxy in the app middleware (grep-confirmed absent).
4. **`X-Forwarded-For` cannot upgrade** — the loopback check never consults XFF/X-Real-IP.

## The caught regression (the careful lane earning its keep)

Task 1's first cut (`loopback → True` before the cookie check) PASSED the slice's own tests but **broke 2 existing security tests** (`test_claimed_nonowner_denies`, `test_no_query_token_bypass_when_claimed` — green on main, red on the branch) — surfaced by the **broader regression sweep**, not the slice tests. It was a **privilege escalation**: a logged-in NON-owner on loopback got owner-private access. Fixed by `f16ee88` (owner-directed): resolve the cookie identity FIRST — an explicit ID wins over loopback. `test_claimed_nonowner_denies` now passes **UNMODIFIED** (the invariant was real, not stale); the query-bypass test was repointed to a **remote** peer (its intent — query tokens can't bypass — preserved, not weakened).

## Codex cross-lane review anchors

1. **The 6-row access matrix** (`_owner_private_auth_ok`), each with an explicit test: claimed+loopback+no-cookie→allow; claimed+loopback+owner-cookie→allow; **claimed+loopback+non-owner-cookie→DENY** (the escalation fix — explicit ID wins over loopback); claimed+remote+no-cookie→deny; claimed+remote+owner-cookie→allow; unclaimed+loopback→allow; store-error→loopback-only.
2. **Strict gate `_request_has_web_owner_cookie()` BYTE-UNCHANGED** — armed S7 / 3b felt-time still cookie-gated (test pins it returns False on loopback-no-cookie). Confirmed not in the diff (only comment references).
3. **Loopback is real-peer-only / XFF can't upgrade** — `test_xff_spoof_from_remote_peer_denied` (non-loopback `remote_addr` + `X-Forwarded-For:127.0.0.1` → no access). Per the 4 security proofs.
4. **`/app` + `/app/` → 302 `/cockpit` even with `?test_t=...`** — the bypass that served `app.html` is GONE (test pins no app.html body served). The `/chat` POST API is unchanged.
5. **No half-park** — repo-wide inventory: every LIVE entry producer repointed/dropped (the `("/app","Channel")` nav tuple dropped; 5 served pages repointed: index/login/progress_public/progress_local/analytics_local). A fresh repo-wide sweep confirmed no missed live producer; remaining `/app` refs classified OUT (dead emitters / funnel-data / no-route page / app.html-internal). `ui/app.html` retained with a parked header (reversible).
6. **Untouched:** the daemon S7 `/message` path, the daemon 3b felt-time mint, Telegram, time-sense, honesty work — none in the diff. **Worktree hazard handled:** `UI_DIR` is hardcoded to the main checkout; the entry-link coverage test reads worktree-relative paths so it tests the edited files.

## Verification

Whole web-auth/cockpit set (`web_interface`/`cockpit`/`web_owner`/`s7_1`/`owner_auth`): **250 tests OK** (the 2 regressions resolved, 2 new escalation tests added). Slice tests + park: OK. ruff clean. Scope clean.

## STANDING CONSTRAINT (record before any future change)

The loopback grant is sound ONLY because of the 4 security proofs above. **If a reverse proxy is ever added in front of `maez-web`, or it is ever bound beyond 127.0.0.1, this loopback owner-access grant MUST be revisited first** (a proxy makes every `remote_addr` look like loopback → defeats the check). Do not expose any cockpit-private route without re-proving the 4 conditions.

## Owner-breath (after both-lanes PASS + merge — owner-sovereign)

Code only; restart `maez-web` (the gate + park live there). Witness:
- Open the cockpit **fresh on the local machine (no login)** → chat works.
- `/app` (even `/app?test_t=x`) → lands on the cockpit; no entry button still says "Channel/Conversation" and bounces.
- Felt-time language on the cockpit only appears after `/login` (armed inner-life still cookie-gated).
- A simulated remote request without the cookie still 401s; a non-owner cookie on loopback is denied.
