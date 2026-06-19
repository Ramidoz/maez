# Task 0 — Cockpit Conversation Spine 3a (SECURE the cockpit→daemon write path)

**HARD PROOF GATE — docs/proof only, zero behavior code changed.**
**Branch:** `cockpit-conversation-spine-3a-secure` based on merged `main` @ `528d8e04f11768920f6db0fae57b115ba4794e79`.
**Date:** 2026-06-18.
**Python:** `/home/rohit/maez/.venv/bin/python`.

Organ 3a secures the existing cockpit→daemon conversation message path (closes a WRITE
hole). Later tasks will (1) S7-gate the daemon `/message` route, (2) owner-gate +
S7-header the web `api_cockpit_message` send. Task 0 proves the path is cleanly gateable
and that 3a's Organ-2 dependencies resolve on this base — BEFORE any gating code lands.

---

## AMENDMENT 2026-06-19 — missed caller (Codex HOLD), repo-wide re-inventory

**The original inventory below was scoped too narrowly** (`daemon/ skills/ web/ scripts/
tests/ core/`) and MISSED `ui/`. Codex cross-lane review caught a second production caller:
`ui/maez_terminal_ui.py` (the **maez-face** terminal UI) hardcodes
`MESSAGE_URL = "http://localhost:11435/message"` (`:21`) and `_send_message` (`:619`) POSTs
to it with **no S7 header** — so the always-on `/message` gate would 403 it → "(no response)".

**Repo-wide re-inventory** (`grep -rn '11435/message\|/message\b' --include=*.py --include=*.jsx
--include=*.js --include=*.sh .`, filtered to HTTP POSTers): the production callers of daemon
`/message` are exactly two — (a) the web `api_cockpit_message` proxy (`skills/web_interface.py`),
and (b) `ui/maez_terminal_ui.py` (`_send_message`). Everything else is the cockpit web UI routing
through `/api/v1/cockpit/message`, or tests.

**Resolution — owner decision 2026-06-19: RETIRE maez-face from the production surface inventory.**
The terminal-UI face is superseded by the face visual-direction work. It is removed from the live
surface inventory, so the only remaining **live production** HTTP caller of `/message` is the web
cockpit proxy → **Approach A's always-on gate is safe.** In-repo retirement (this branch):
- `ui/maez_terminal_ui.py` — RETIRED header added (do-not-run; would 403 without an S7 trusted path).
- `PROGRESS_PUBLIC.md` — `maez-face.service` + autostart moved to **Stopped/disabled**.
- **Owner-sovereign live steps (handoff):** `systemctl disable --now maez-face.service` and remove
  `~/.config/autostart/maez-face.desktop` so it is no longer a live mouth.

**Process lesson:** the Task-0 consumer inventory must scan the WHOLE repo, not a hand-picked
directory list — the consumer boundary was under-mapped (the Organ-1/-2 lesson, recurring).

---

- **Approach A** = gate the shared `/message` route (preferred).
- **Approach B** (fallback) = a dedicated `/internal/cockpit/message` route, used ONLY if
  a non-cockpit *production* HTTP caller of `/message` exists.

---

## (a) Consumer inventory of daemon `/message` — decides A vs B

```
$ grep -rn '"/message"\|:11435/message\|_DAEMON_BASE' daemon/ skills/ web/ scripts/ tests/ core/
daemon/maez_daemon.py:10679:        @app.route("/message", methods=["POST"])
tests/test_cockpit_proxies_2026_05_05.py:81:        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
skills/web_interface.py:1759:_DAEMON_BASE = "http://127.0.0.1:11435"
skills/web_interface.py:1781:            f"{_DAEMON_BASE}/message",
skills/web_interface.py:1826:        url = f"{_DAEMON_BASE}/internal/approve_card/{_q(request_id, safe='')}"
skills/web_interface.py:1874:            f"{_DAEMON_BASE}{internal_route}",
skills/web_interface.py:1907:            f"{_DAEMON_BASE}/internal/s7/webauthn/status",
tests/test_ui_message_history_threading.py:8:the cockpit POSTs to ``http://127.0.0.1:11435/message`` with only
tests/test_subjective_duration_static_boundaries.py:291:        ui_route = daemon[daemon.index('@app.route("/message"') : daemon.index('@app.route("/internal/brain_loop"')]
```

**Classification of EACH hit:**

| Hit | Kind | HTTP caller of `/message`? | Notes |
|---|---|---|---|
| `daemon/maez_daemon.py:10679` | PRODUCTION | route *definition* (server side) | The route being gated. |
| `skills/web_interface.py:1759` | PRODUCTION | n/a (base-URL const) | `_DAEMON_BASE = "http://127.0.0.1:11435"`. |
| `skills/web_interface.py:1781` | PRODUCTION | **YES — the only one** | `f"{_DAEMON_BASE}/message"` inside `api_cockpit_message` (the cockpit proxy). |
| `skills/web_interface.py:1826` | PRODUCTION | no (`/internal/approve_card/...`) | Different route. |
| `skills/web_interface.py:1874` | PRODUCTION | no (`/internal/...` route var) | Different route. |
| `skills/web_interface.py:1907` | PRODUCTION | no (`/internal/s7/webauthn/status`) | Different route. |
| `tests/test_cockpit_proxies_2026_05_05.py:81` | TEST | **real HTTP POST** (only one) | Flask test-client POSTs `/api/v1/cockpit/message`; patches `urllib.request.urlopen`; asserts the proxied URL is `…:11435/message`. |
| `tests/test_ui_message_history_threading.py:8` | TEST | **NO HTTP** | Verified by reading: the `11435/message` string is only in the module docstring. The test body imports `_pair_history_for_chat_threading` from `daemon.maez_daemon` and calls it DIRECTLY (no `urlopen`/`requests`/`urllib`). |
| `tests/test_subjective_duration_static_boundaries.py:291` | TEST | **NO HTTP** | Verified by reading: `_source()` does `path.read_text(...)` and `ast.parse(...)`; the `@app.route("/message"` string is a static-analysis index marker, not a request. |

**Conclusion (CORRECTED — see the 2026-06-19 amendment at the top):** this directory-scoped scan
missed `ui/maez_terminal_ui.py` (maez-face). After the repo-wide re-inventory and maez-face's
retirement, the only remaining **live production** HTTP caller of `/message` is the web
`api_cockpit_message` proxy (`f"{_DAEMON_BASE}/message"`, `skills/web_interface.py:1781`). The only
test making a **real HTTP POST** is `tests/test_cockpit_proxies_2026_05_05.py`. **→ Approach A is clean.**

---

## (b) Telegram-path proof — the daemon S7 gate must NOT starve telegram

```
$ grep -n "handle_message" skills/surface/maez_adapter.py | head
13:detection), dispatching through the daemon's synchronous `handle_message`
...
1197:                            lambda: self.daemon.handle_message(

$ grep -n "def handle_message" daemon/maez_daemon.py
5338:    def handle_message(
```

`skills/surface/maez_adapter.py:1197` calls `self.daemon.handle_message(text, SURFACE_NAME, …)`
**in-process** (a direct Python method call dispatched via the shared executor —
`loop.run_in_executor(get_shared_executor(), copy_current_context_callable(lambda: self.daemon.handle_message(...)))`).
It does **NOT** go through the HTTP `/message` route.

**Path:** `telegram surface → maez_adapter.handle_message → (in-process) daemon.handle_message`
(`daemon/maez_daemon.py:5338`).

**Therefore:** S7-gating the HTTP `/message` route affects only HTTP callers = the cockpit
proxy. Telegram is unaffected and cannot be starved by the gate.

---

## (c) Clean-separation proof

```
$ sed -n '/def api_cockpit_message/,/daemon_unreachable/p' skills/web_interface.py \
    | grep -iE 'proxy_web_owner|handle_message|voice|private_owner_bridge|/chat' \
    || echo "web proxy: clean"
web proxy: clean
```

**Result: web proxy: clean.** The `api_cockpit_message` body contains none of
`proxy_web_owner` / `handle_message` / `voice` / `private_owner_bridge` / `/chat`. 3a adds
gates only — it introduces no web-owner-spine, voice, or private_owner_bridge coupling.

---

## (d) Import-resolution on the merged base (LOAD-BEARING — Organ-2 dependency)

```
$ grep -n "def _s7_internal_channel_headers\|def _owner_private_auth_required_response\|def _owner_private_auth_ok\|_DAEMON_BASE =\|_COCKPIT_PROXY_TIMEOUT_S =\|def api_cockpit_message" skills/web_interface.py
1541:def _s7_internal_channel_headers() -> dict[str, str]:
1759:_DAEMON_BASE = "http://127.0.0.1:11435"
1760:_COCKPIT_PROXY_TIMEOUT_S = 60.0
1765:def api_cockpit_message():
9771:def _owner_private_auth_ok() -> bool:
9792:def _owner_private_auth_required_response():

$ grep -n 'def _s7_internal_channel_trusted\|@app.route("/message"' daemon/maez_daemon.py
308:def _s7_internal_channel_trusted(req) -> bool:
10679:        @app.route("/message", methods=["POST"])

$ grep -n "class _DaemonAppClientMixin" tests/test_s7_1_daemon_internal_channel.py
100:class _DaemonAppClientMixin:
```

**ALL present.** The two Organ-2 helpers 3a reuses are present AND real (read, not stubs):

- `_s7_internal_channel_headers` (`skills/web_interface.py:1541`) — reads
  `_S7_INTERNAL_CHANNEL_TOKEN_ENV`, raises `RuntimeError("s7_internal_channel_untrusted")`
  if empty, else returns `{_S7_INTERNAL_CHANNEL_HEADER: token}`. **CONFIRMED PRESENT.**
- `_owner_private_auth_required_response` (`skills/web_interface.py:9792`) — returns
  `jsonify({"ok": False, "error": "owner_auth_required"}), 401`. **CONFIRMED PRESENT.**

Supporting context also present: `_owner_private_auth_ok` (the owner gate, :9771),
`_DAEMON_BASE` (:1759), `_COCKPIT_PROXY_TIMEOUT_S = 60.0` (:1760), `api_cockpit_message`
(:1765), the daemon-side `_s7_internal_channel_trusted` gate (`daemon/maez_daemon.py:308`,
which Task 1 will apply to the `/message` route), and the test mixin `_DaemonAppClientMixin`
(`tests/test_s7_1_daemon_internal_channel.py:100`).

**Organ 2 IS on this base. The helpers must NOT be re-created in 3a — reuse them.**

---

## (e) Current `api_cockpit_message` body — contract Task 2 must preserve

`skills/web_interface.py:1765-1805`. Success path:

```python
with _urlreq.urlopen(req, timeout=_COCKPIT_PROXY_TIMEOUT_S) as resp:
    payload = resp.read()
    status = resp.status
    ctype = resp.headers.get("Content-Type", "application/json")
return (payload, status, {"Content-Type": ctype})
```

**Success return shape:** `(payload, status, {"Content-Type": ctype})` — the daemon's body,
status code, and content-type passed through verbatim.

`HTTPError` branch (daemon answered non-2xx — passes it through with the `e.read()`→`str(e)`
fallback):

```python
except _urlerr.HTTPError as e:
    try:
        payload = e.read()
    except Exception:
        payload = str(e).encode("utf-8")
    return (payload, e.code, {"Content-Type": "application/json"})
```

Transport-failure branch (daemon down / timeout) → `502`:

```python
except Exception as e:
    return jsonify({"ok": False, "error": "daemon_unreachable", "detail": str(e)[:200]}), 502
```

**CONFIRMED:** success returns the daemon's `(payload, status, {"Content-Type": ctype})`
tuple; the `HTTPError` branch has the `e.read()`→`str(e)` fallback. Task 2 must add the
owner-gate + S7 header WITHOUT altering this success/HTTPError/502 contract.

---

## (f) Existing-test-breakage inventory

```
$ grep -rn '/api/v1/cockpit/message\|11435/message\|"/message"' tests/
tests/test_cockpit_proxies_2026_05_05.py:8:  POST /api/v1/cockpit/message
tests/test_cockpit_proxies_2026_05_05.py:50:    """POST /api/v1/cockpit/message → daemon /message."""
tests/test_cockpit_proxies_2026_05_05.py:75:                "/api/v1/cockpit/message",
tests/test_cockpit_proxies_2026_05_05.py:81:        self.assertEqual(captured["url"], "http://127.0.0.1:11435/message")
tests/test_cockpit_proxies_2026_05_05.py:99:                "/api/v1/cockpit/message",
tests/test_cockpit_proxies_2026_05_05.py:112:                "/api/v1/cockpit/message",
tests/test_ui_message_history_threading.py:8: (docstring only — no HTTP, see (a))
tests/test_subjective_duration_static_boundaries.py:291: (static ast.parse marker — no HTTP, see (a))

$ grep -rln 'cockpit/message' tests/
tests/test_cockpit_proxies_2026_05_05.py
```

**The ONLY test exercising the gated HTTP path is `tests/test_cockpit_proxies_2026_05_05.py`.**
It POSTs `/api/v1/cockpit/message` (3 cases: 200 forward, 4xx passthrough, transport 502).
When Task 2 makes the proxy owner-gated, these will need an owner-authenticated mock; the
existing `urlopen` patch will also start seeing the S7 header on the outbound request.

No OTHER test POSTs to `/api/v1/cockpit/message` or daemon `/message` over HTTP.

---

## TASK 0 VERDICT: GO (Approach A)

- The daemon `/message` route has exactly one **live production** HTTP caller **after maez-face's
  retirement** (see the 2026-06-19 amendment): the cockpit proxy `api_cockpit_message`. With
  maez-face retired, no other non-test production HTTP caller exists → the shared route is cleanly
  S7-gateable (Approach A); the dedicated `/internal/cockpit/message` fallback (Approach B) is NOT
  required.
- Telegram reaches `daemon.handle_message` in-process (`maez_adapter.py:1197`), not via the
  HTTP route → the S7 gate cannot starve telegram.
- The web proxy is cleanly separated (no web-owner-spine / voice / private_owner_bridge / `/chat`).
- Both Organ-2 helpers resolve on the merged base and are real, not stubs
  (`_s7_internal_channel_headers` :1541, `_owner_private_auth_required_response` :9792) —
  reuse, do not re-create.
- The `api_cockpit_message` success contract is `(payload, status, {"Content-Type": ctype})`;
  HTTPError passthrough has the `e.read()`→`str(e)` fallback — Task 2 must preserve both.
- Only one existing test (`test_cockpit_proxies_2026_05_05.py`) exercises the gated HTTP path.

Nothing refutes the plan.
