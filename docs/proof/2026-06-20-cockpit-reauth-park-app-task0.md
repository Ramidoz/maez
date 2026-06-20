# Task 0 — Proof Gate: 4 security proofs + repo-wide `/app` inventory

**Slice:** cockpit-reauth-park-app · **Branch:** `cockpit-reauth-park-app` · **Date:** 2026-06-20
**Scope:** verification only (NO code). The 4 security proofs are BLOCKING — if any fails, VERDICT = REFUTED and STOP.

---

## VERDICT: **GO**

All 4 security proofs hold (loopback grant is sound). Repo-wide `/app` inventory complete — 18 producer rows classified into 5 buckets. The Task-2 work list (`repoint→/cockpit` + `drop-from-nav`) is at the bottom of the inventory.

---

## STEP 1 — THE 4 SECURITY PROOFS (all hold)

### Proof 1 — `maez-web` binds `127.0.0.1` ONLY ✅

`~/.config/systemd/user/maez-web.service` launches `web_interface.py` directly (no gunicorn/waitress in front):

```
ExecStart=/home/rohit/maez/.venv/bin/python3 /home/rohit/maez/skills/web_interface.py
```

The unit comment confirms loopback-only intent ("thin Flask app bound to loopback 127.0.0.1:11437 only"), and the actual bind is in `skills/web_interface.py:10512`:

```python
app.run(host="127.0.0.1", port=11437, debug=False)
```

Bind = `127.0.0.1`, NOT `0.0.0.0` and NOT a LAN IP. **HOLDS.**

### Proof 2 — `_request_is_loopback()` reads the REAL WSGI peer ✅

`skills/web_interface.py:160-166`:

```python
def _request_is_loopback() -> bool:
    """True only when the real TCP peer is loopback. Reads request.remote_addr
    (the raw WSGI peer — no ProxyFix is installed). NEVER consults
    X-Forwarded-For / X-Real-IP, which an attacker could set. Covers IPv4
    127.0.0.0/8, IPv6 ::1, and IPv4-mapped-IPv6 ::ffff:127.x."""
    addr = (getattr(request, "remote_addr", "") or "").strip()
    return addr.startswith("127.") or addr.startswith("::ffff:127.") or addr in _LOOPBACK_EXACT
```

with `_LOOPBACK_EXACT = {"::1"}` (line 157). The check reads `request.remote_addr` (the socket peer from the WSGI environ `REMOTE_ADDR`), NOT a header. **HOLDS.**

### Proof 3 — NO `ProxyFix` / trusted reverse proxy ✅

`grep -rn "ProxyFix\|proxy_fix\|wsgi_app *=\|X-Forwarded\|X-Real-IP" skills/web_interface.py` returns ONLY two hits — both inside the `_request_is_loopback` docstring:

```
skills/web_interface.py:162:    (the raw WSGI peer — no ProxyFix is installed). NEVER consults
skills/web_interface.py:163:    X-Forwarded-For / X-Real-IP, which an attacker could set. Covers IPv4
```

There is NO `from werkzeug.middleware.proxy_fix import ProxyFix`, NO `ProxyFix(...)` wrap, NO `app.wsgi_app = ...` assignment (a separate confirming grep `grep -n "ProxyFix\|from werkzeug.middleware" skills/web_interface.py` matches only line 162). ProxyFix is ABSENT, so `remote_addr` stays the true socket peer and cannot be overridden by `X-Forwarded-For`. **HOLDS.**

### Proof 4 — `X-Forwarded-For` CANNOT upgrade ✅

`_request_is_loopback` (the only function `_owner_private_auth_ok`'s loopback path calls) reads exactly one value — `request.remote_addr` (line 165). It never reads `request.headers`, `X-Forwarded-For`, `X-Real-IP`, or `request.access_route`. Combined with Proof 3 (no ProxyFix to rewrite `remote_addr`) and Proof 1 (loopback bind), a request arriving with `X-Forwarded-For: 127.0.0.1` from a non-loopback peer keeps `remote_addr` = the real (non-loopback) peer → `_request_is_loopback()` returns False → no access without the cookie. **HOLDS.**

**STEP 1 result: all 4 hold → SECURITY GO.**

---

## STEP 2 — REPO-WIDE `/app` INVENTORY (5-bucket)

`grep -rn "/app" skills/ ui/ daemon/ core/ tests/ docs/` then filtered to real `/app` ROUTE references (dropped `/application`, `/app.py`, `file/app/command` prose, `/appendix`). No `/app` route refs exist in `daemon/`, `core/`, or `tests/`.

**Liveness map (which `ui/*.html` is served by a live `@app.route`):**

| UI file | Served by route | Live? |
|---|---|---|
| `ui/index.html` | `/` (`index`, :1073) | **LIVE** |
| `ui/login.html` | `/login` GET (`login`, :6156) | **LIVE** |
| `ui/progress_public.html` | `/progress` (`progress_page`, :1088) | **LIVE** |
| `ui/progress_local.html` | `/planner` (`planner_page`, :1098, token-gated) | **LIVE** |
| `ui/analytics_local.html` | `/analytics` (`analytics_page`, :1108, token-gated) | **LIVE** |
| `ui/app.html` | `/app` (`app_shell`, :1078) — the surface being PARKED | parked |
| `ui/dashboard_public.html` | *(no route — `dashboard_public` is never `send_file`'d)* | **OUT** |

**Dead-constant note:** `skills/web_interface.py` defines two large HTML string constants — `LOGIN_PAGE` (:7272) and `HTML_PAGE` (:8155) — each referenced EXACTLY ONCE (its own definition; `grep -c` = 1 for both). They are NOT served by any route (the live `/login` serves `ui/login.html` via `send_file`, not `LOGIN_PAGE`). Therefore the embedded `/app` JS emitters inside them are NOT live producers — they are archival/OUT (recommend deletion as dead code, but OUT of this slice's repoint scope).

### Producer table

| # | File:line | Snippet | Bucket |
|---|---|---|---|
| 1 | `skills/web_interface.py:112` | `("/app", "Channel"),` — entry in `ANALYTICS_FUNNEL` tuple | **drop-from-nav** |
| 2 | `skills/web_interface.py:1078` | `@app.route("/app")` → `app_shell()` serves `app.html` | (the route Task 2 replaces with redirect — not a "link producer"; listed for completeness) |
| 3 | `skills/web_interface.py:8016` | `const href = hasToken ? '/app' : '/login';` — inside dead `LOGIN_PAGE` (:7272) | **archival/static-OUT** (dead constant) |
| 4 | `skills/web_interface.py:8045` | `location.replace('/app');` — inside dead `LOGIN_PAGE` | **archival/static-OUT** (dead constant) |
| 5 | `skills/web_interface.py:8140` | `location.replace('/app');` — inside dead `LOGIN_PAGE` | **archival/static-OUT** (dead constant) |
| 6 | `skills/web_interface.py:9182` | `history.replaceState(null, '', '/app');` — inside dead `HTML_PAGE` (:8155) | **archival/static-OUT** (dead constant) |
| 7 | `ui/index.html:1700` | `const entryHref = hasToken ? '/app' : '/login';` — LIVE home entry (served at `/`) | **repoint→/cockpit** |
| 8 | `ui/login.html:667` | `const href = hasToken ? '/app' : '/login';` — LIVE login entry (served at `/login`) | **repoint→/cockpit** |
| 9 | `ui/login.html:696` | `location.replace('/app');` — LIVE login post-auth redirect | **repoint→/cockpit** |
| 10 | `ui/login.html:855` | `location.replace('/app');` — LIVE login boot redirect | **repoint→/cockpit** |
| 11 | `ui/progress_public.html:967` | `channelLink.href = hasToken ? '/app' : '/login';` — LIVE (served at `/progress`) | **repoint→/cockpit** |
| 12 | `ui/progress_local.html:527` | `<a href="/app">Conversation</a>` — LIVE (served at `/planner`) | **repoint→/cockpit** |
| 13 | `ui/analytics_local.html:381` | `<a href="/app">Conversation</a>` — LIVE (served at `/analytics`) | **repoint→/cockpit** |
| 14 | `ui/analytics_local.html:562` | `{ path: '/app', label: 'Channel', count: 9 }` — analytics funnel data (display label, not an entry link) | **archival/static-OUT** (funnel datum on a served page; not a clickable entry — see note) |
| 15 | `ui/analytics_local.html:569` | `{ path: '/app', count: 9 }` — analytics funnel data | **archival/static-OUT** (funnel datum; not an entry link) |
| 16 | `ui/dashboard_public.html:2441` | `link.href = hasToken ? '/app' : '/login';` — NOT served by any route | **archival/static-OUT** |
| 17 | `ui/app.html:965` | `history.replaceState(null, '', '/app');` — inside the parked surface itself | **parked-app-internal** |
| 18 | `docs/**` (spec/plan/roadmap, e.g. `docs/superpowers/specs/...:30`, `docs/MAEZ_DESKTOP_BODY_ROADMAP.md:33`) | slice plan/spec text + roadmap prose | **test/doc** |

**Note on rows 14-15 (`analytics_local.html` funnel data):** these are funnel-display data objects (a path string + a count) rendered as a chart datum, NOT a daily-entry link the user clicks. They live on a served page (`/analytics`) but do not teach the route as a front door. Row 13 (the `<a href="/app">Conversation</a>` on the SAME page) IS a clickable entry → `repoint`. Rows 14-15 are left labeled OUT (cosmetic funnel labels); repointing them is optional and not required for "no live entry producer". The Task-2 entry-link coverage test (`test_served_entry_pages_have_no_app_daily_link`) regexes `href`/`location=` patterns and will NOT flag rows 14-15.

### Task-2 work list (rows classified `repoint→/cockpit` or `drop-from-nav`)

**`drop-from-nav` (1):**
- `skills/web_interface.py:112` — remove `("/app", "Channel"),` from `ANALYTICS_FUNNEL`.

**`repoint→/cockpit` (7 — every LIVE-served entry producer):**
- `ui/index.html:1700` — `entryHref` ternary → `/cockpit`.
- `ui/login.html:667` — `href` ternary → `/cockpit`.
- `ui/login.html:696` — `location.replace('/app')` → `/cockpit`.
- `ui/login.html:855` — `location.replace('/app')` → `/cockpit`.
- `ui/progress_public.html:967` — `channelLink.href` ternary → `/cockpit`.
- `ui/progress_local.html:527` — `<a href="/app">Conversation</a>` → `/cockpit`.
- `ui/analytics_local.html:381` — `<a href="/app">Conversation</a>` → `/cockpit`.

> **Plan delta (the implementer/Task-2 must note):** the plan's File-structure table and Task-2 Step 5 name only `ui/index.html` + `ui/login.html` as the static repoint set. The repo-wide inventory finds THREE more LIVE-served entry pages — `ui/progress_public.html`, `ui/progress_local.html`, `ui/analytics_local.html` — that each emit a daily-entry `/app` link. Task 2 MUST repoint all 5 served files (not just the two named) or it leaves a half-park (a button on `/progress` / `/planner` / `/analytics` still says "Conversation"/"Channel" and bounces). The plan's Task-2 Step 5 text already says "and any Task-0 `repoint` page", so this list IS the binding set. The Task-2 entry-link coverage test loop should be widened beyond `("index.html","login.html")` to include these three, OR a per-served-page assertion added.

**Left as-is (NOT touched by Task 2):**
- `archival/static-OUT`: dead-constant emitters (`web_interface.py:8016/8045/8140/9182`), `ui/dashboard_public.html:2441`, `ui/analytics_local.html:562/569` funnel data.
- `parked-app-internal`: `ui/app.html:965`.
- `test/doc`: docs refs.

---

## STEP 3 — Confirmed code shapes (current worktree line numbers)

### `_owner_private_auth_ok` — :9785 (the ACCESS gate Task 1 edits)

```python
def _owner_private_auth_ok() -> bool:
    """... claimed -> require the COOKIE-resolved owner identity (no ?test_t=/?web_token= bypass).
    On account-store failure: loopback (physical body) keeps recovery, remote fails closed."""
    try:
        if not accounts.owner_claimed():
            return _request_is_loopback()              # <-- Task 1 inserts claimed-loopback allowance AFTER this line
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        if not token:
            return False
        user = accounts.get_by_token(token)
        if not user:
            return False
        record = accounts.get_user_record(user.get("uuid", "")) or {}
        return _is_owner(record)
    except Exception as exc:
        logger.warning("owner gate degraded (%s); loopback-only recovery", exc, exc_info=True)
        return _request_is_loopback()
```

Claimed branch today = require the cookie-resolved owner (no loopback recovery). This is the one branch Task 1 amends (insert `if _request_is_loopback(): return True` after the `owner_claimed()` early-return).

### `_request_has_web_owner_cookie` — :9809 (STRICT gate, LEAVE UNTOUCHED)

```python
def _request_has_web_owner_cookie() -> bool:
    """Stricter than _owner_private_auth_ok: a COOKIE that resolves to a CLAIMED web_owner.
    No unclaimed-loopback recovery, no degraded-store fallback ..."""
    try:
        if not accounts.owner_claimed():
            return False
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        if not token:
            return False
        user = accounts.get_by_token(token)
        if not user:
            return False
        record = accounts.get_user_record(user.get("uuid", "")) or {}
        return _is_owner(record)
    except Exception:
        return False
```

No loopback path anywhere — returns False on loopback-no-cookie. Felt-time stays cookie-gated. Task 1 must NOT modify this. (Caller `:1789` `if _request_has_web_owner_cookie():` stamps the `X-Maez-Owner-Authenticated` header on the cockpit message proxy.)

### `app_shell` — :1078-1085 (the `test_t` bypass + token redirect Task 2 replaces)

```python
@app.route("/app")
def app_shell():
    if request.args.get("test_t", "").strip():
        return send_file(os.path.join(UI_DIR, "app.html"), mimetype="text/html")
    token = _request_token()
    if not token or not accounts.get_by_token(token):
        return redirect("/login")
    return send_file(os.path.join(UI_DIR, "app.html"), mimetype="text/html")
```

Confirmed: only `@app.route("/app")` — there is **NO `@app.route("/app/")`** yet (Task 2 adds it). The `?test_t=` bypass serves `app.html` directly (this is the half-park hole the unconditional redirect closes). `redirect` is already in scope (used at :1084).

### Nav tuple — :112

```python
ANALYTICS_FUNNEL = (
    ("/", "Landing"),
    ("/progress", "Progress"),
    ("/dashboard", "Architecture"),
    ("/login", "Login"),
    ("/app", "Channel"),          # <-- :112, drop this row
)
```

It is the `ANALYTICS_FUNNEL` definition (not a visual nav menu), but it is the `("/app","Channel")` tuple the plan/test target — Task 2 drops it.

### Out-of-scope confirmed

- **Daemon S7 `/message` path** — in the daemon, not `skills/web_interface.py`; the web layer only proxies via `/api/v1/cockpit/message` (:1764) and stamps the owner header off the STRICT cookie gate (untouched). OUT.
- **3b felt-time mint** — daemon-side, rides `_request_has_web_owner_cookie` (untouched). OUT.
- **time-sense files / honesty files** — no `/app` refs; not in this slice's file set. OUT.

---

## STEP 4 — VERDICT

**GO.**
- 4 security proofs: 127.0.0.1-only bind ✅ · `_request_is_loopback` reads raw `remote_addr` ✅ · no ProxyFix ✅ · X-Forwarded-For cannot upgrade ✅.
- Repo-wide `/app` inventory complete (18 rows, 5 buckets).
- Task-2 binding list: **drop** `web_interface.py:112`; **repoint** the 7 LIVE entry producers in `ui/index.html`, `ui/login.html` (×3), `ui/progress_public.html`, `ui/progress_local.html`, `ui/analytics_local.html`.
- Standing constraint recorded: the loopback grant is sound ONLY while all 4 proofs hold. If a reverse proxy / ProxyFix is ever added, OR maez-web is rebound off loopback, this grant MUST be revisited before exposing any cockpit-private route.
