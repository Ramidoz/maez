# Cockpit Re-Auth (loopback-is-owner) + Park Chat App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local cockpit recognize the loopback owner for access/chat without a login, keep the strict cookie proof for armed/felt-time actions, and park the `/app` chat surface by an unconditional redirect — with every live `/app` link repointed.

**Architecture:** One surgical edit to the `_owner_private_auth_ok` access gate (claimed + real-loopback → allow); the strict `_request_has_web_owner_cookie` gate untouched; `/app`+`/app/` → unconditional `redirect('/cockpit')` before any `test_t` bypass; a repo-wide `/app` inventory repoints/drops every live producer; `ui/app.html` retained with a parked header.

**Tech Stack:** Python 3, Flask, `unittest`. Spec: `docs/superpowers/specs/2026-06-20-cockpit-reauth-park-chat-app-design.md` (@e3a094d). Sensitive: live owner-facing web auth.

---

## Lane discipline (every task)

- **Worktree/branch:** via superpowers:using-git-worktrees. Branch **`cockpit-reauth-park-app`**. `main` local-only — **NO push**.
- **GIT HYGIENE:** NO `git checkout`/`switch`/`reset`/`rebase`. Only edit/test/add/commit. After each commit `git status` MUST show **`On branch cockpit-reauth-park-app`**. Detached → STOP.
- **Runner:** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`.
- **Commits:** behavior → `## Predicted effect`; docs/proof/test-only don't. End with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** after Task 3. The `maez-web` restart is the owner breath. **Live web auth → full two-stage review per task.**

## Invariants (reviewers verify)

1. claimed+loopback→access; claimed+remote+no-cookie→401; claimed+remote+valid-cookie→access; unclaimed+loopback→access; store-error→loopback-only.
2. **Strict gate `_request_has_web_owner_cookie()` UNCHANGED** — felt-time still cookie-gated (a test pins it returns False on loopback-no-cookie).
3. **Loopback is real-peer-only** — non-loopback `remote_addr`, OR `X-Forwarded-For: 127.0.0.1` from a non-loopback peer → NO access without cookie.
4. **`/app`+`/app/` → 302 `/cockpit` even WITH `?test_t=...`** (bypass cannot serve the old UI).
5. **No half-park** — repo-wide `/app` inventory complete; every live-served entry producer repointed/dropped; remaining refs classified.
6. `ui/app.html` retained (not deleted).
7. **Untouched:** strict gate, daemon S7 `/message`, daemon 3b felt-time mint, Telegram, time-sense, honesty work, reverse-proxy support (deferred).

## File structure

| File | Change |
|---|---|
| `skills/web_interface.py` | **Modify** — `_owner_private_auth_ok` (1 insert); `app_shell` → unconditional redirect; drop the `("/app","Channel")` nav tuple; repoint embedded `/app` JS |
| `ui/index.html`, `ui/login.html` (+ any Task-0 `repoint` static page) | **Modify** — entry links `/app`→`/cockpit` |
| `ui/app.html` | **Modify** — parked header comment only (retained) |
| `tests/test_owner_private_auth_loopback.py` | **Create** (Task 1) |
| `tests/test_app_parked_redirect.py` | **Create** (Task 2) |
| `docs/proof/2026-06-20-cockpit-reauth-park-app-task0.md` | **Create** (Task 0) |
| `docs/handoffs/2026-06-20-cockpit-reauth-park-app-handoff.md` | **Create** (Task 3) |

---

### Task 0: Proof gate — 4 security proofs + repo-wide `/app` inventory (docs/proof, committed first)

**Files:** Create `docs/proof/2026-06-20-cockpit-reauth-park-app-task0.md`. NO code. **If any security proof fails → VERDICT REFUTED, STOP.**

- [ ] **Step 1: SECURITY PROOF (all four; STOP if any fails).**
  1. `maez-web` binds **`127.0.0.1` only** — check the run command (`~/.config/systemd/user/maez-web.service` ExecStart / the `app.run(host=...)` / gunicorn bind in `skills/web_interface.py`). Confirm NOT `0.0.0.0`.
  2. `_request_is_loopback()` (web_interface.py:160) reads `request.remote_addr` (raw WSGI peer), NOT a header — quote it.
  3. **No `ProxyFix`** / trusted reverse proxy in the app middleware — grep `ProxyFix|wsgi_app =|werkzeug.middleware.proxy_fix` across `skills/web_interface.py` → must be ABSENT.
  4. **`X-Forwarded-For` cannot upgrade** — confirm `_request_is_loopback` never consults `X-Forwarded-For`/`X-Real-IP` (the docstring says so; verify the body).
- [ ] **Step 2: REPO-WIDE `/app` INVENTORY (the consumer-boundary lesson).** `grep -rn "/app" skills/ ui/ daemon/ core/ tests/ docs/` (filter false positives like `/application`, file paths). Build a table classifying EACH producer as one of: **`repoint→/cockpit`** | **`drop-from-nav`** | **`parked-app-internal`** (inside `ui/app.html`) | **`archival/static-OUT`** | **`test/doc`**. Must include: the embedded JS in `skills/web_interface.py` (e.g. ~:9177 `test_t`, the "Resume/Enter the channel" link emitters), the `("/app","Channel")` nav tuple (:112), `ui/index.html`, `ui/login.html`, and any served static page (`ui/dashboard_public.html`, `ui/progress_public.html`, `ui/analytics_local.html`, etc.) — classify each as live (`repoint`) vs not (`OUT`). The Task-2 repoint/drop list = every row classified `repoint`/`drop-from-nav`.
- [ ] **Step 3: Confirm code shapes (current main line numbers).** `_owner_private_auth_ok` (~:9785) — quote the claimed-branch; `_request_has_web_owner_cookie` (~:9809) — the strict gate to LEAVE UNTOUCHED; `app_shell` (:1078-1085) — the `test_t` bypass + token-redirect to replace; the nav tuple (:112). Confirm the daemon S7 `/message` path, 3b felt-time mint, time-sense files, and honesty files are NOT in scope.
- [ ] **Step 4: VERDICT** `GO` (all 4 security proofs hold) / `REFUTED: <which proof failed>`. Record the inventory table + line numbers for Tasks 1-2.
- [ ] **Step 5: Commit (docs/proof — no predicted-effect).**
```bash
git add docs/proof/2026-06-20-cockpit-reauth-park-app-task0.md
git commit -m "docs(proof): cockpit-reauth-park-app Task 0 — 4 security proofs + repo-wide /app inventory (5-bucket)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch cockpit-reauth-park-app
```

---

### Task 1: Auth gate — claimed + real loopback → owner-private access

**Files:** Modify `skills/web_interface.py` (`_owner_private_auth_ok`); Create `tests/test_owner_private_auth_loopback.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_owner_private_auth_loopback.py` (hermetic — Flask `test_request_context` sets the peer + cookies; mock `accounts`):

```python
import unittest
from unittest import mock
import skills.web_interface as wi


def _ctx(remote_addr, cookie=None, xff=None):
    headers = {}
    if xff:
        headers["X-Forwarded-For"] = xff
    env = {"REMOTE_ADDR": remote_addr}
    cookies = {wi.AUTH_COOKIE: cookie} if cookie else {}
    # Flask test_request_context: pass cookies via headers
    cookie_hdr = f"{wi.AUTH_COOKIE}={cookie}" if cookie else ""
    if cookie_hdr:
        headers["Cookie"] = cookie_hdr
    return wi.app.test_request_context("/api/v1/cockpit/message", environ_base=env, headers=headers)


class OwnerPrivateAuthLoopback(unittest.TestCase):
    def test_claimed_loopback_allows_without_cookie(self):
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertTrue(wi._owner_private_auth_ok())   # physical body IS the owner

    def test_claimed_remote_no_cookie_denied(self):
        with _ctx("10.0.0.5"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._owner_private_auth_ok())

    def test_claimed_remote_valid_cookie_allows(self):
        with _ctx("10.0.0.5", cookie="goodtoken"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True), \
             mock.patch.object(wi.accounts, "get_by_token", return_value={"uuid": "u1"}), \
             mock.patch.object(wi.accounts, "get_user_record", return_value={"relationship": "owner", "trust_tier": 3}), \
             mock.patch.object(wi, "_is_owner", return_value=True):
            self.assertTrue(wi._owner_private_auth_ok())

    def test_unclaimed_loopback_allows(self):
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=False):
            self.assertTrue(wi._owner_private_auth_ok())

    def test_xff_spoof_from_remote_peer_denied(self):
        # remote_addr is non-loopback; X-Forwarded-For:127.0.0.1 must NOT upgrade to loopback.
        with _ctx("10.0.0.5", xff="127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._owner_private_auth_ok())

    def test_strict_gate_unchanged_loopback_no_cookie_is_false(self):
        # The STRICT felt-time gate must STILL require the cookie even on loopback (NOT loosened).
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._request_has_web_owner_cookie())
```

- [ ] **Step 2: Run, expect RED** (claimed+loopback currently returns False — no cookie).

- [ ] **Step 3: Implement the one insert.** In `skills/web_interface.py` `_owner_private_auth_ok()`, after the `if not accounts.owner_claimed(): return _request_is_loopback()` line, add the claimed-loopback allowance:
```python
        if not accounts.owner_claimed():
            return _request_is_loopback()
        # Claimed owner on a single-user local machine: the real loopback peer IS the owner, so grant
        # owner-private ACCESS (read/chat) without a cookie. Remote requests still require the cookie below.
        # NOTE: the STRICT proof (_request_has_web_owner_cookie) is intentionally NOT given this recovery —
        # armed S7 / 3b felt-time stay cookie-gated. Loopback safety: _request_is_loopback() reads the raw
        # WSGI peer (no ProxyFix, never X-Forwarded-For); maez-web binds 127.0.0.1 only.
        if _request_is_loopback():
            return True
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        # ... rest unchanged
```

- [ ] **Step 4: Run, expect GREEN** (all 6 tests). The strict-gate test confirms `_request_has_web_owner_cookie` was NOT changed.

- [ ] **Step 5: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_owner_private_auth_loopback.py
git add skills/web_interface.py tests/test_owner_private_auth_loopback.py
git commit -m "fix(web-auth): claimed owner on real loopback gets owner-private access (no cookie); strict gate unchanged

## Predicted effect
On this single-user local machine, a real-loopback request is recognized as the owner for ACCESS (read/chat)
without a login cookie — the physical peer IS the owner. Remote requests still require the cookie. The strict
proof (_request_has_web_owner_cookie) is untouched, so armed S7 / 3b felt-time stay cookie-gated. Loopback is
raw-WSGI-peer-only (no ProxyFix, never X-Forwarded-For).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch cockpit-reauth-park-app
```

---

### Task 2: Park `/app` (unconditional redirect) + repoint every live `/app` producer

**Files:** Modify `skills/web_interface.py` (`app_shell` + nav tuple + embedded JS); `ui/index.html`, `ui/login.html` (+ Task-0 `repoint` pages); `ui/app.html` (parked header). Create `tests/test_app_parked_redirect.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_app_parked_redirect.py`:

```python
import os, re, unittest
import skills.web_interface as wi

UI_DIR = wi.UI_DIR


class AppParked(unittest.TestCase):
    def setUp(self):
        self.c = wi.app.test_client()

    def test_app_redirects_to_cockpit(self):
        r = self.c.get("/app", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")

    def test_app_trailing_slash_redirects(self):
        r = self.c.get("/app/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")

    def test_app_with_test_t_still_redirects_never_serves_old_ui(self):
        # THE half-park guard: the test_t bypass must NOT serve app.html.
        r = self.c.get("/app?test_t=anything", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"].rstrip("/"), "/cockpit")
        self.assertNotIn(b"<html", r.data.lower())   # no app.html body served


class NoLiveAppEntry(unittest.TestCase):
    def test_nav_tuple_app_channel_removed(self):
        src = open(wi.__file__, encoding="utf-8").read()
        self.assertNotIn('("/app", "Channel")', src)
        self.assertNotIn("('/app', 'Channel')", src)

    def test_served_entry_pages_have_no_app_daily_link(self):
        # The live-served entry surfaces (Task-0 'repoint' set) must not point users at /app.
        for page in ("index.html", "login.html"):   # + any Task-0 repoint page
            html = open(os.path.join(UI_DIR, page), encoding="utf-8").read()
            # no href/window.location to "/app" as a daily entry (allow none)
            self.assertFalse(re.search(r'(href|location(\.href)?\s*=)\s*[\'"]/app[\'"/]', html),
                             f"{page} still emits a /app entry link")

    def test_app_html_retained(self):
        self.assertTrue(os.path.exists(os.path.join(UI_DIR, "app.html")))   # parked, not deleted
```

- [ ] **Step 2: Run, expect RED** (`/app` serves app.html / nav tuple present / entry links present).

- [ ] **Step 3: Park `app_shell` — unconditional redirect.** Replace the `app_shell` body (web_interface.py:1078-1085) with:
```python
@app.route("/app")
@app.route("/app/")
def app_shell():
    # PARKED 2026-06-20: the thread-UI surface is retired (cockpit + Telegram is the live set). Redirect
    # UNCONDITIONALLY to /cockpit BEFORE any test_t/token/serve — no secret path to the old UI. ui/app.html
    # is retained (reversible); the /chat POST API is unchanged. See the cockpit-reauth-park-app slice.
    return redirect("/cockpit")
```
(`redirect` is already imported — it's used at the old :1084.)

- [ ] **Step 4: Drop the nav tuple + repoint embedded JS.** Remove the `("/app", "Channel")` line from the nav tuple (web_interface.py:112). For every embedded `/app` producer Task 0 classified `repoint` (e.g. the "Resume/Enter the channel" link emitters, the `test_t`-app JS ~:9177 if it's a live entry), change the target to `/cockpit` (or remove the dead emitter). Leave `parked-app-internal` / `archival-OUT` / `test-doc` refs.

- [ ] **Step 5: Repoint the static entry pages.** In `ui/index.html`, `ui/login.html`, and any Task-0 `repoint` page: change the daily-entry `/app` targets ("Resume the channel" / "Enter the channel" / "Channel" buttons) to `/cockpit`. Do NOT touch `parked-app-internal` (inside `ui/app.html`) or `archival-OUT` pages.

- [ ] **Step 6: Parked header in `ui/app.html`.** Add an HTML comment at the very top: `<!-- PARKED 2026-06-20: thread-UI surface retired; served route /app now redirects to /cockpit. Retained (not deleted) — may return as a polished front-door. -->`

- [ ] **Step 7: Run, expect GREEN.** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_app_parked_redirect -v`. If `test_served_entry_pages_have_no_app_daily_link` fails on a page Task 0 marked `repoint`, that page still has a link — fix it (don't weaken the regex).

- [ ] **Step 8: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_app_parked_redirect.py
git add skills/web_interface.py ui/index.html ui/login.html ui/app.html tests/test_app_parked_redirect.py
git commit -m "fix(web): park /app (unconditional redirect to /cockpit before test_t) + repoint every live /app entry

## Predicted effect
/app and /app/ now redirect to /cockpit unconditionally — the ?test_t bypass can no longer serve the old
thread UI. The ('/app','Channel') nav tuple and every live-served /app entry link (home/login + embedded JS)
are repointed to /cockpit, so no live surface teaches the parked route. ui/app.html retained (reversible);
the /chat POST API unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch cockpit-reauth-park-app
```

---

### Task 3: Whole-slice green + regression + handoff + STOP

**Files:** Create `docs/handoffs/2026-06-20-cockpit-reauth-park-app-handoff.md`.

- [ ] **Step 1: Slice modules green.**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_owner_private_auth_loopback tests.test_app_parked_redirect -v
```

- [ ] **Step 2: Regression — web auth / cockpit / web-interface surfaces.** `ls tests/ | grep -iE "web_interface|cockpit|owner_auth|s7|web_owner|auth"` and run them; confirm green (esp. any existing `_owner_private_auth_ok` / cockpit-state / felt-time-cookie test). Pre-existing failures must reproduce on `main`.

- [ ] **Step 3: ruff + scope check.** ruff the touched files; `git diff --stat main..HEAD` — confirm NO daemon `/message`/felt-time, time-sense, or honesty files; `_request_has_web_owner_cookie` NOT in the diff.

- [ ] **Step 4: Write the handoff** with: branch tip; commits; the **4 security proofs** (recorded as a standing constraint — *revisit the loopback grant before adding any reverse proxy / exposing cockpit-private routes*); Codex anchors (loopback-access-claimed / strict-gate-untouched-felt-time-still-gated / XFF-cannot-upgrade / unconditional-/app-redirect-before-test_t / repo-wide-inventory-complete-no-half-park / app.html-retained / no daemon-S7-time-sense-honesty entanglement / reverse-proxy-deferred); the Task-0 inventory; the test surface; and the **owner-breath**:
  > Restart `maez-web`. Witness: open the cockpit fresh on the local machine (no login) → chat works; `/app` (even `/app?test_t=x`) → lands on the cockpit; felt-time language on the cockpit only after `/login`; a simulated remote request without the cookie still 401s.

- [ ] **Step 5: Commit handoff + STOP.**
```bash
git add docs/handoffs/2026-06-20-cockpit-reauth-park-app-handoff.md
git commit -m "docs(handoff): cockpit-reauth-park-app — review gate + owner-breath + standing proxy constraint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch cockpit-reauth-park-app
```
**STOP.** No merge/restart. Report branch tip + the 4 security proofs + Task-0 inventory + test outputs + Codex anchors + owner-breath.

---

## Self-review (controller)

- **Spec coverage:** loopback-access change (Task 1) ✓; strict-gate-unchanged (Task 1 test) ✓; XFF-can't-upgrade (Task 1 test + Task 0 proof) ✓; unconditional `/app` redirect before `test_t` (Task 2 test) ✓; repo-wide inventory + repoint/drop (Task 0 + Task 2) ✓; app.html retained (Task 2 test) ✓; 4 security proofs (Task 0, STOP-if-fail) ✓; untouched surfaces (Task 0 Step 3 + Task 3 scope) ✓.
- **Open for Task 0 / implementer:** the exact maez-web bind command (Step 1.1); the full `/app` inventory rows (Step 2 — the `repoint` set drives Task 2 Steps 4-5 + the entry-page test loop); whether the Flask cookie-via-headers test helper resolves `request.cookies` (Task 1 — if not, set `environ_base`'s `HTTP_COOKIE` directly).
- **Type/name consistency:** `_owner_private_auth_ok` / `_request_has_web_owner_cookie` / `_request_is_loopback` / `app_shell` / `AUTH_COOKIE` / `UI_DIR` used consistently; the strict gate is referenced only to assert it's unchanged.
