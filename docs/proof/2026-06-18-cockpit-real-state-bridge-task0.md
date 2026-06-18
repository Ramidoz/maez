# Cockpit Real-State Bridge — Task 0 Hard Proof Gate (2026-06-18)

**Slice:** cockpit-real-state-bridge-organ
**Task 0 scope:** DOCS/PROOF ONLY. No behavior code changed. Prove the bridge is
cleanly separable and composes with what is already on `main`, BEFORE any gating
code lands (Tasks 1–3 add: S7-gate the daemon `/internal/cockpit/state`,
owner-gate the web `/api/v1/daemon/state`, make the web proxy send the S7 token).

The organ HARDENS an existing-but-exposed bridge. It MODIFIES `_build_cockpit_state`,
`_daemon_cockpit_state_proxy`, and the `MAEZ_COCKPIT_REAL_STATE` flag-switch — it
never rebuilds them.

---

## (a) Consumer inventory of the daemon endpoint `/internal/cockpit/state`

Command:
```
grep -rn "internal/cockpit/state\|DAEMON_COCKPIT_STATE_URL" daemon/ skills/ web/ tests/ core/
```

Hits, each classified:

| Hit | Classification | Note |
|-----|----------------|------|
| `daemon/maez_daemon.py:10303` `@app.route("/internal/cockpit/state")` | PRODUCTION (the endpoint definition itself) | The route handler `cockpit_state()` → `_build_cockpit_state(self)`. Currently **ungated** (no `_s7_internal_channel_trusted` call) — Task 1 adds the S7 gate here. |
| `skills/web_interface.py:124` `DAEMON_COCKPIT_STATE_URL = "http://127.0.0.1:11435/internal/cockpit/state"` | PRODUCTION | URL constant consumed only by the proxy below. |
| `skills/web_interface.py:1545` `urllib.request.urlopen(DAEMON_COCKPIT_STATE_URL, ...)` | PRODUCTION — the only reader | Inside `_daemon_cockpit_state_proxy()`. This is the sole production code that *reads* the daemon endpoint. |
| `skills/web_interface.py:1559` (docstring of `api_daemon_state`) | PRODUCTION (comment only, not a read) | Documents the flag-on behavior. |

A separate grep of `tests/` for the same patterns returned **no hits** (exit 1):
no test references the daemon endpoint URL or the URL constant directly. (The
Task-1 daemon-gate test will exercise the route via a captured-app test client —
see (e) — not by hitting the literal string.)

**Conclusion:** The ONLY production reader of the daemon
`/internal/cockpit/state` is the web `_daemon_cockpit_state_proxy`
(`skills/web_interface.py:1537`) via `DAEMON_COCKPIT_STATE_URL`.
**No non-test production code reads it ungated outside that proxy.** An always-on
S7 gate on the daemon endpoint will only affect that single proxy reader, which
Task 3 teaches to send the S7 token. **NOT REFUTED.**

---

## (b) Consumer inventory of the web endpoint `/api/v1/daemon/state` (orphan-lesson)

Command:
```
grep -rn "api/v1/daemon/state\|_pollDaemon\|daemonState" web/cockpit/ skills/web_interface.py tests/
```

Consumers of `/api/v1/daemon/state`:

| Hit | Classification | Note |
|-----|----------------|------|
| `web/cockpit/sim.jsx:481` `fetch('/api/v1/daemon/state')` inside `_pollDaemon` (def at :479) | PRODUCTION — the live consumer | Default `fetch()` (same-origin, browser sends owner cookie if present). Polled every 5s (`setInterval(_pollDaemon, 5000)` at :704; first call at :701). |
| `skills/web_interface.py:1552` `@app.route("/api/v1/daemon/state")` | PRODUCTION (endpoint definition) | `api_daemon_state()`; flag-switch at :1562. |
| `tests/test_cockpit_real_state_bridge.py:174,198,206` `client.get("/api/v1/daemon/state")` | TEST | Part 3 web-proxy flag tests; today hit with no owner cookie and expect 200. |
| `tests/test_cockpit_push_user_turn.py:81` (references `setInterval(_pollDaemon` as a source-slice anchor) | TEST | Static slice of `sim.jsx`, not a network call. |

**Owner-gate orphan check.** The `/cockpit` index page that loads `sim.jsx` is
served by `cockpit_index()` (`skills/web_interface.py:1160`) via
`send_from_directory(COCKPIT_DIR, "index.html")` — **with no owner gate**. So the
cockpit surface is reachable without an owner cookie, and a no-cookie visitor's
browser WILL issue the `_pollDaemon` fetch. This is exactly the public/no-cookie
consumer the orphan-lesson asks us to look for.

It does **not** orphan, because the consumer already degrades gracefully on a
non-OK response:
- `sim.jsx:482` — `if (!r.ok) { markOffline('daemon', r.status); return; }`
- `sim.jsx:475–477` comment — "On fetch error we keep the fake data (silent
  fallback) so the cockpit never breaks when maez-web is offline."

Post-gate, a no-cookie visitor receives 401/403 → `markOffline` → keeps the
prototype fake data; the cockpit does not break. The real owner (cookie present,
same origin) passes `_owner_private_auth_ok()` and gets real state. The planned
always-on owner gate therefore **does not orphan a public consumer** — it
withholds *real inner-state* from non-owners (covenant-correct) while leaving the
public cockpit shell functional on fake data.

The three `tests/test_cockpit_real_state_bridge.py` requests currently issue
no-cookie 200s; Task 2 will need to add the owner cookie to those calls. That is
expected test maintenance for an added gate, **not** a refutation. **NOT REFUTED.**

---

## (c) Clean-separation proof (no web-owner-spine / voice entanglement)

Commands:
```
sed -n '/def cockpit_state/,/_build_cockpit_state/p' daemon/maez_daemon.py | grep -iE 's7|web_owner|handle_message|voice|proxy_web_owner' || echo "daemon cockpit_state handler: clean"
sed -n '/def _daemon_cockpit_state_proxy/,/return {"status"/p' skills/web_interface.py | grep -iE 'web_owner|handle_message|voice|proxy_web_owner' || echo "web proxy: clean"
```

Output:
```
daemon cockpit_state handler: clean
web proxy: clean
```

Both ends are clean — the daemon handler and the web proxy carry no
web-owner-spine, `handle_message`, or voice entanglement. The bridge is a pure
state read/proxy and is cleanly separable. (Note: the daemon-side grep also
includes `s7` — confirming the daemon handler does **not** yet reference S7, so
Task 1's S7 gate is a clean addition, not a tangle with existing logic.)
**NOT REFUTED.**

---

## (d) Import-resolution proof — building blocks exist on `main`

```
grep -n "def _owner_private_auth_ok\|def _api_daemon_state_log_scrape\|DAEMON_COCKPIT_STATE_URL =\|def _daemon_cockpit_state_proxy\|def api_daemon_state" skills/web_interface.py
```
```
124:DAEMON_COCKPIT_STATE_URL = "http://127.0.0.1:11435/internal/cockpit/state"
1537:def _daemon_cockpit_state_proxy(timeout=1.5):
1553:def api_daemon_state():
1567:def _api_daemon_state_log_scrape():
9746:def _owner_private_auth_ok() -> bool:
```

```
grep -n "def _s7_internal_channel_trusted\|S7_INTERNAL_CHANNEL_TOKEN_ENV =\|S7_INTERNAL_CHANNEL_HEADER =\|def _build_cockpit_state\|/internal/cockpit/state" daemon/maez_daemon.py
```
```
281:S7_INTERNAL_CHANNEL_HEADER = "X-Maez-S7-Internal-Channel"
282:S7_INTERNAL_CHANNEL_TOKEN_ENV = "S7_INTERNAL_CHANNEL_TOKEN"
308:def _s7_internal_channel_trusted(req) -> bool:
2336:def _build_cockpit_state(daemon) -> dict:
10303:        @app.route("/internal/cockpit/state")
```

```
grep -n "def strict_env_flag" core/infra/env_flags.py
```
```
23:def strict_env_flag(name: str) -> bool:
```

All building blocks PRESENT on `main`:
- `_build_cockpit_state` (daemon `:2336`) — **already exists** → organ modifies, never rebuilds.
- `_daemon_cockpit_state_proxy` (web `:1537`) — **already exists** → organ modifies, never rebuilds.
- The `MAEZ_COCKPIT_REAL_STATE` flag-switch — **already exists** in `api_daemon_state()`
  (`:1562`: `if strict_env_flag("MAEZ_COCKPIT_REAL_STATE")`), selecting proxy (ON)
  vs `_api_daemon_state_log_scrape` (OFF). Both branches present.
- Owner gate `_owner_private_auth_ok` (web `:9746`) — present, ready for Task 2.
- S7 internal-channel primitives `_s7_internal_channel_trusted` (`:308`),
  `S7_INTERNAL_CHANNEL_HEADER` (`:281`), `S7_INTERNAL_CHANNEL_TOKEN_ENV` (`:282`)
  — present, ready for Tasks 1 & 3.
- `strict_env_flag` (`core/infra/env_flags.py:23`) — present.

Confirmed: the web proxy does **not** yet send the S7 header (grep of the proxy
body for `S7|X-Maez|header|Request(` returns nothing) — Task 3's addition is
clean. **No missing building block. NOT REFUTED.**

---

## (e) Daemon test-harness check (reusable for Task 1)

`tests/test_s7_1_daemon_internal_channel.py` **exists** (120 KB).

```
grep -n "make_server\|test_client\|_s7_internal_channel_trusted" tests/test_s7_1_daemon_internal_channel.py
```
```
63:                self.assertFalse(D._s7_internal_channel_trusted(req))
108:        def fake_make_server(_host, _port, app):
112:        with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
115:        return captured["app"].test_client()
120:        def fake_make_server(_host, _port, app):
124:        with patch("werkzeug.serving.make_server", side_effect=fake_make_server):
127:        return captured["app"].test_client()
```

The harness uses the captured-app pattern: it patches
`werkzeug.serving.make_server` to capture the Flask `app`, then returns
`captured["app"].test_client()`. It also already exercises
`_s7_internal_channel_trusted(req)` directly. The Task-1 daemon-gate test can
reuse this captured-app test-client pattern to GET `/internal/cockpit/state`
with and without the S7 header. **NOT REFUTED.**

---

## Summary

| Proof | Result |
|-------|--------|
| (a) daemon endpoint sole prod reader = web proxy | CONFIRMED (only reader; no ungated non-test prod consumer) |
| (b) web endpoint consumer = `sim.jsx` `_pollDaemon`; owner gate won't orphan | CONFIRMED (public cockpit page is ungated but degrades gracefully via `markOffline`) |
| (c) clean separation (no web-owner/voice) | CONFIRMED (both "clean") |
| (d) building blocks exist on main (`_build_cockpit_state` + `_daemon_cockpit_state_proxy` + flag-switch) | CONFIRMED (all present; organ modifies, never rebuilds) |
| (e) daemon test harness reusable | CONFIRMED (captured-app test-client pattern present) |

**Notable (not a refutation):** the `/cockpit` index page (`cockpit_index`,
`:1160`) is served without an owner gate, so a public/no-cookie visitor's browser
does reach `/api/v1/daemon/state`. The planned owner gate withholds real state
from non-owners (covenant-correct) and the JS already falls back to fake data on
non-OK responses, so no consumer is orphaned. Task 2 must update the three
no-cookie test requests in `tests/test_cockpit_real_state_bridge.py` to carry the
owner cookie — expected test maintenance for an added gate.

TASK 0 VERDICT: GO
