# Park Legacy Public Web Doors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Park legacy public web routes that let someone enter, talk through, write into, or read Maez, while keeping the owner cockpit and verified local integrations intact.

**Architecture:** Add one reversible parking helper in `skills/web_interface.py`, route legacy doors through it, and add tests proving the old doors no longer expose entry/talk/read/write surfaces. Keep live owner surfaces only where Task 0 proves an owner/trusted-channel gate or a public-data projection.

**Tech Stack:** Flask (`skills/web_interface.py`), Python `unittest`, existing maez-web test-client patterns.

---

## Files

- Modify: `skills/web_interface.py`
  - Add a small legacy-surface parking helper.
  - Park old auth/chat/account/read/debug routes.
  - Add or preserve owner/trusted-channel guard for kept `/api/v1/*` routes.
  - Leave cosmetic static pages and reversible old code in place.
- Create: `tests/test_legacy_public_web_doors_parked.py`
  - Failing-first coverage for parked doors, kept cockpit, kept public projection, `/api/iphone/ingest`, `/v1/fast-reply`, and `/api/v1/*` owner gating.
- Create: `docs/handoffs/2026-06-28-legacy-public-web-route-inventory.md`
  - Task 0 classification artifact with route, capability, classification, and evidence.
- Existing tests to keep green:
  - `tests/test_app_parked_redirect.py`
  - `tests/test_cockpit_proxies_2026_05_05.py`
  - `tests/test_s7_1_daemon_internal_channel.py`
  - `tests/test_s7_webauthn_enrollment_asset_boundary.py`

---

### Task 0: Route Inventory and Classification Artifact

**Files:**
- Create: `docs/handoffs/2026-06-28-legacy-public-web-route-inventory.md`
- Inspect: `skills/web_interface.py`

- [ ] **Step 1: Generate the route list from live code**

Run:

```bash
cd /home/rohit/maez
rg -n '^@app\.route|/v1/fast-reply|def _owner_private_auth_ok|def _debug_auth_ok|def api_iphone_ingest|def api_cockpit_message|def chat\(|def history\(|def status\(|def api_maez_state|def api_session_timeline|def journal_page' skills/web_interface.py
```

Expected: output includes `/v1/fast-reply`, `/api/iphone/ingest`, `/api/v1/cockpit/message`, `/chat`, `/history`, `/journal`, `/status`, `/api/maez-state`, `/api/session-timeline`, `/debug`, `/api/debug/*`.

- [ ] **Step 2: Write the classification artifact**

Create `docs/handoffs/2026-06-28-legacy-public-web-route-inventory.md` with this exact structure. Keep the listed rows, then add one row for every remaining `@app.route` from Step 1 so the artifact covers the full live surface:

```markdown
# Legacy Public Web Route Inventory — 2026-06-28

## Law
Park doors, not path shapes. A door lets someone enter, talk through, write into, or read Maez. Cosmetic static pages are deferred.

## Required findings

- `/chat` owner-cockpit usage: cockpit sends via `/api/v1/cockpit/message`; no kept cockpit asset calls old `/chat`.
- `/api/iphone/ingest`: token-auth iOS Shortcut ingress via `X-Maez-Token`; not part of account-token app; KEEP.
- `/v1/fast-reply`: only registers when `MAEZ_LIVE_FAST_LANE_ENABLED=1`; if enabled it is a talk-door and parks.
- `/api/progress-board`: returns `_planner_public_view(board)` filtered to `visibility == "public"`; KEEP as public projection unless private fields are found.
- `/api/v1/*`: kept only where owner/trusted-channel gating is proven. Any state-returning route without such proof is a read-door HOLD/PARK.

## Route table

| Route | Methods | Function | Capability | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/cockpit` | GET | `cockpit_index` | owner-cockpit | KEEP | Serves cockpit only. |
| `/api/v1/cockpit/message` | POST | `api_cockpit_message` | owner-cockpit talk proxy | KEEP | Calls `_owner_private_auth_ok()` and forwards to daemon with S7 channel. |
| `/login` | GET/POST | `login` | enter/account | PARK | Serves old login and account token. |
| `/register` | POST | `register` | enter/account | PARK | Creates account token. |
| `/link-telegram` | POST | `link_telegram` | account/link write | PARK | Links Telegram ID through account token. |
| `/chat` | POST | `chat` | talk/write | PARK | Old account-token chat surface. |
| `/history` | GET | `history` | read | PARK | Returns owner/private/public chat history. |
| `/status` | GET | `status` | read | PARK | Returns account and memory counts. |
| `/api/maez-state` | GET | `api_maez_state` | read | PARK | Returns daemon/memory/model/services/soul aggregate. |
| `/api/session-timeline` | GET | `api_session_timeline` | read | PARK | Returns parsed session snapshots. |
| `/journal` | GET | `journal_page` | read page | PARK | Dashboard over state/timeline/progress APIs. |
| `/api/iphone/ingest` | POST | `api_iphone_ingest` | active-local-integration | KEEP | Requires `X-Maez-Token` or body token and delegates to `skills.iphone_ingest.ingest`. |
| `/v1/fast-reply` | POST | `fast_reply_adapter` | feature-flagged talk | PARK when registered | Account-token staging fast-lane talk route. |
```

If any evidence contradicts the table, stop and update the spec/owner before implementation.

- [ ] **Step 3: Verify old `/chat` is not the cockpit path**

Run:

```bash
cd /home/rohit/maez
rg -n "fetch\(['\"]/(chat|api/v1/cockpit/message)|/chat" web/cockpit skills/web_interface.py ui -g '!**/.venv/**'
```

Expected: cockpit send path uses `/api/v1/cockpit/message`. Any `/chat` hits are in old app/login surfaces or the route implementation, not in kept cockpit assets.

- [ ] **Step 4: Commit the inventory artifact**

```bash
cd /home/rohit/maez
git add docs/handoffs/2026-06-28-legacy-public-web-route-inventory.md
git commit -m "docs(web): classify legacy public web doors"
```

---

### Task 1: Failing Tests for Parked Legacy Doors

**Files:**
- Create: `tests/test_legacy_public_web_doors_parked.py`

- [ ] **Step 1: Write failing tests for old doors**

Create `tests/test_legacy_public_web_doors_parked.py`:

```python
import os
import re
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test-token")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

import skills.web_interface as wi


class LegacyDoorParkingTests(unittest.TestCase):
    def setUp(self):
        self.client = wi.app.test_client()

    def assert_parked_json(self, response):
        self.assertEqual(response.status_code, 410)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("error"), "legacy_surface_parked")
        self.assertIn("/cockpit", payload.get("message", ""))

    def assert_parked_page(self, response):
        self.assertIn(response.status_code, (302, 410))
        if response.status_code == 302:
            self.assertEqual(response.headers["Location"].rstrip("/"), "/cockpit")
        else:
            self.assert_parked_json(response)

    def test_auth_and_chat_doors_are_parked(self):
        self.assert_parked_page(self.client.get("/login"))
        self.assert_parked_json(self.client.post("/login", json={"username": "r", "password": "x"}))
        self.assert_parked_json(self.client.post("/register", json={"username": "r", "password": "xxxx"}))
        self.assert_parked_json(self.client.post("/link-telegram", json={"web_token": "t", "telegram_id": "1"}))
        self.assert_parked_json(self.client.post("/chat", json={"web_token": "t", "message": "hello"}))

    def test_read_doors_are_parked_without_state_leak(self):
        for path in (
            "/history",
            "/status",
            "/api/maez-state",
            "/api/session-timeline",
            "/api/analytics-summary",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assert_parked_json(response)
                body = response.get_data(as_text=True).lower()
                self.assertNotIn("memory_count", body)
                self.assertNotIn("sessions", body)
                self.assertNotIn("soul", body)
                self.assertNotIn("daemon", body)

    def test_journal_and_old_local_pages_are_parked(self):
        for path in ("/journal", "/planner", "/analytics"):
            with self.subTest(path=path):
                self.assert_parked_page(self.client.get(path))

    def test_old_write_apis_are_parked(self):
        self.assert_parked_json(self.client.post("/api/analytics", json={"event": "pageview", "path": "/"}))
        self.assert_parked_json(self.client.get("/api/planner-board"))
        self.assert_parked_json(self.client.post("/api/planner-board", json={"items": []}))

    def test_debug_read_doors_are_parked(self):
        for path in ("/debug", "/debug/flow", "/debug/card-default"):
            with self.subTest(path=path):
                self.assert_parked_page(self.client.get(path))
        self.assert_parked_json(self.client.get("/api/debug/services"))

    def test_progress_board_remains_public_projection_only(self):
        with mock.patch.object(
            wi,
            "_load_planner_board",
            return_value={
                "updated_at": "2026-06-28T00:00:00Z",
                "items": [
                    {
                        "id": "public-1",
                        "title": "public title",
                        "status": "planned",
                        "summary": "public summary",
                        "details": "public details",
                        "tags": ["public"],
                        "updated_at": "2026-06-28T00:00:00Z",
                        "visibility": "public",
                    },
                    {
                        "id": "private-1",
                        "title": "SECRET PRIVATE TITLE",
                        "status": "planned",
                        "summary": "SECRET PRIVATE SUMMARY",
                        "details": "SECRET PRIVATE DETAILS",
                        "tags": ["private"],
                        "updated_at": "2026-06-28T00:00:00Z",
                        "visibility": "private",
                    },
                ],
            },
        ):
            response = self.client.get("/api/progress-board")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("public title", body)
        self.assertNotIn("SECRET PRIVATE", body)

    def test_iphone_ingest_is_token_auth_local_integration_not_account_app(self):
        missing = self.client.post("/api/iphone/ingest", json={"kind": "battery"})
        self.assertIn(missing.status_code, (401, 403))
        with mock.patch("skills.iphone_ingest.ingest", return_value=({"ok": True}, 200)) as ingest:
            response = self.client.post(
                "/api/iphone/ingest",
                json={"kind": "battery"},
                headers={"X-Maez-Token": "dummy-test-token"},
            )
        self.assertEqual(response.status_code, 200)
        ingest.assert_called_once()
        payload, token = ingest.call_args.args
        self.assertEqual(token, "dummy-test-token")
        self.assertNotIn("web_token", payload)

    def test_fast_reply_absent_when_feature_flag_off(self):
        rules = {rule.rule for rule in wi.app.url_map.iter_rules()}
        self.assertNotIn("/v1/fast-reply", rules)

    def test_fast_reply_parked_when_feature_flag_on(self):
        code = textwrap.dedent(
            '''
            import os
            os.environ["MAEZ_SECRETS_DISABLE_NEW_LOADER"] = "1"
            os.environ["MAEZ_IPHONE_INGEST_TOKEN"] = "dummy-test-token"
            os.environ["MAEZ_LIVE_FAST_LANE_ENABLED"] = "1"
            import skills.web_interface as wi
            c = wi.app.test_client()
            r = c.post("/v1/fast-reply", json={"web_token": "t", "message": "hello"})
            print(r.status_code)
            print(r.get_data(as_text=True))
            '''
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd="/home/rohit/maez",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("410", result.stdout.splitlines()[0])
        self.assertIn("legacy_surface_parked", result.stdout)


class OwnerSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = wi.app.test_client()

    def test_cockpit_pages_still_serve(self):
        self.assertEqual(self.client.get("/cockpit").status_code, 200)
        self.assertEqual(self.client.get("/cockpit/s7-webauthn-proof").status_code, 200)

    def test_api_v1_state_routes_require_owner_or_loopback_gate(self):
        with mock.patch.object(wi, "_owner_private_auth_ok", return_value=False):
            for path in (
                "/api/v1/daemon/state",
                "/api/v1/s7/webauthn/status",
                "/api/v1/cards",
                "/api/v1/services",
                "/api/v1/gpu",
                "/api/v1/signals",
                "/api/v1/soul",
                "/api/v1/memory",
                "/api/v1/lived-memory",
                "/api/v1/turn/latest",
                "/api/v1/now",
                "/api/v1/rail/timeline",
                "/api/v1/dreams",
                "/api/v1/quality",
                "/api/v1/self_dev",
                "/api/v1/identity",
                "/api/v1/router",
                "/api/v1/logs/maez",
                "/api/v1/chat/sessions",
            ):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json().get("error"), "owner_auth_required")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked
```

Expected: failures showing old routes still serve or return old auth errors instead of `legacy_surface_parked`; `/api/v1/soul`/memory-style routes may also fail if they do not yet call `_owner_private_auth_ok()`.

- [ ] **Step 3: Keep the red tests uncommitted**

Do not commit the failing tests yet. Leave them in the worktree and move to Task 2. The first code commit for this slice must include the tests passing against the implementation.

---

### Task 2: Add Parking Helper and Park Legacy Doors

**Files:**
- Modify: `skills/web_interface.py`

- [ ] **Step 1: Add the helper near the existing `/app` parking block**

Add this helper above the legacy public routes:

```python
_LEGACY_SURFACE_PARKED_ERROR = "legacy_surface_parked"


def _legacy_surface_parked_response(surface: str, *, page: bool = False):
    """Reversible parking for retired public web doors.

    The old code stays in place below the early return; this helper closes entry,
    talk, write, and read surfaces without deleting the historical implementation.
    """
    logger.info("legacy web surface parked: %s", surface)
    if page:
        return redirect("/cockpit")
    return jsonify(
        {
            "error": _LEGACY_SURFACE_PARKED_ERROR,
            "message": "This legacy public Maez web surface is parked. Use /cockpit.",
            "surface": surface,
        }
    ), 410
```

- [ ] **Step 2: Park page routes with early returns**

At the top of each page handler, before token checks or file serving, add:

```python
@app.route("/planner")
def planner_page():
    # PARKED 2026-06-28: old account-token local planner surface retired; owner cockpit is live.
    return _legacy_surface_parked_response("/planner", page=True)
```

Apply the same pattern to:

```python
@app.route("/analytics")
def analytics_page():
    # PARKED 2026-06-28: old account-token analytics surface retired; owner cockpit is live.
    return _legacy_surface_parked_response("/analytics", page=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # PARKED 2026-06-28: old public account login retired; owner cockpit is live.
        return _legacy_surface_parked_response("/login", page=True)
    return _legacy_surface_parked_response("/login")


@app.route("/journal")
def journal_page():
    # PARKED 2026-06-28: old field journal read-door retired; owner cockpit is live.
    return _legacy_surface_parked_response("/journal", page=True)


@app.route("/debug")
def debug_page():
    # PARKED 2026-06-28: old debug read-door retired from public maez-web surface.
    return _legacy_surface_parked_response("/debug", page=True)
```

For `/debug/flow`, `/debug/flow/static`, and `/debug/card-default`, use `page=True` with their exact route string.

- [ ] **Step 3: Park API/write/read routes with early returns**

At the top of each handler, before reading tokens, loading memories, opening DBs, or calling helpers, add:

```python
@app.route("/register", methods=["POST"])
def register():
    # PARKED 2026-06-28: old public account registration retired; owner cockpit is live.
    return _legacy_surface_parked_response("/register")
```

Apply the same early-return pattern to:

```python
@app.route("/link-telegram", methods=["POST"])
def link_telegram():
    return _legacy_surface_parked_response("/link-telegram")

@app.route("/chat", methods=["POST"])
def chat():
    return _legacy_surface_parked_response("/chat")

@app.route("/history")
def history():
    return _legacy_surface_parked_response("/history")

@app.route("/api/analytics", methods=["POST"])
def analytics_collect():
    return _legacy_surface_parked_response("/api/analytics")

@app.route("/api/analytics-summary")
def analytics_summary():
    return _legacy_surface_parked_response("/api/analytics-summary")

@app.route("/api/planner-board", methods=["GET", "POST"])
def planner_board():
    return _legacy_surface_parked_response("/api/planner-board")

@app.route("/status")
def status():
    return _legacy_surface_parked_response("/status")

@app.route("/api/maez-state")
def api_maez_state():
    return _legacy_surface_parked_response("/api/maez-state")

@app.route("/api/session-timeline")
def api_session_timeline():
    return _legacy_surface_parked_response("/api/session-timeline")
```

For every `/api/debug/*` handler, add the same `return _legacy_surface_parked_response("<route>")` before `_debug_auth_ok()` or any store reads. Keep `/api/progress-board` unchanged because Task 0 proves it is a public projection filtered by `_planner_public_view`.

- [ ] **Step 4: Park `/v1/fast-reply` if the feature flag registers it**

Inside `fast_reply_adapter()`, as the first executable line, add:

```python
        # PARKED 2026-06-28: feature-flagged legacy talk-door retired from maez-web.
        return _legacy_surface_parked_response("/v1/fast-reply")
```

Do not change the flag-off behavior; when `MAEZ_LIVE_FAST_LANE_ENABLED` is unset, the route remains unregistered.

- [ ] **Step 5: Run the legacy-door tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked
```

Expected: parking tests pass except any `/api/v1/*` owner-gate failures, which are addressed in Task 3.

- [ ] **Step 6: Commit parking helper and route parking**

```bash
cd /home/rohit/maez
git add skills/web_interface.py tests/test_legacy_public_web_doors_parked.py
git commit -m "fix(web): park legacy public maez-web doors"
```

Commit body:

```text
Park legacy entry, talk, write, and read doors on maez-web while keeping the owner cockpit intact.

## Predicted effect
/login, /chat, /history, /status, /api/maez-state, /api/session-timeline, /journal, and old debug/account APIs no longer expose the retired public web app. /cockpit and /api/v1 cockpit paths continue to serve the owner surface.
```

---

### Task 3: Prove or Add Owner Gate for Kept `/api/v1/*`

**Files:**
- Modify: `skills/web_interface.py`
- Test: `tests/test_legacy_public_web_doors_parked.py`

- [ ] **Step 1: Add a shared guard helper for owner API reads if missing**

If Task 1 showed any state-returning `/api/v1/*` route does not call `_owner_private_auth_ok()`, add this helper near `_owner_private_auth_required_response()`:

```python
def _api_v1_owner_gate_required() -> object | None:
    """Return an auth-required response for owner-private /api/v1 routes, else None."""
    if not _owner_private_auth_ok():
        return _owner_private_auth_required_response()
    return None
```

- [ ] **Step 2: Gate state-returning `/api/v1/*` routes**

At the top of each owner-state `/api/v1/*` handler that lacks a proven equivalent guard, add:

```python
    if (auth_response := _api_v1_owner_gate_required()) is not None:
        return auth_response
```

Apply this to state-returning routes at minimum if they lack the guard:

```text
/api/v1/soul
/api/v1/cards
/api/v1/services
/api/v1/gpu
/api/v1/signals
/api/v1/memory
/api/v1/lived-memory
/api/v1/lived-memory/episodes
/api/v1/lived-memory/graph
/api/v1/lived-memory/echoes
/api/v1/lived-memory/predictions
/api/v1/lived-memory/brief
/api/v1/turn/latest
/api/v1/now
/api/v1/rail/timeline
/api/v1/dreams
/api/v1/quality
/api/v1/self_dev
/api/v1/identity
/api/v1/router
/api/v1/logs/<name>
/api/v1/chat/sessions
```

Add the helper to `/api/v1/s7/webauthn/status` unless Task 0 proves another explicit owner/trusted-channel gate. The status route currently uses a plain GET status proxy, unlike S7 write proxies that send `X-Maez-S7-Internal-Channel`. Do not add the helper to the S7 write/proof proxy routes unless Task 0 proves they need it; they already route through ceremony flag and server-side internal-channel proxy semantics. Do not change `/api/v1/cockpit/message`, which already calls `_owner_private_auth_ok()`.

For `/api/v1/cards/<request_id>/deny`, `/api/v1/cards/<request_id>/approve`, `/api/v1/dreams/<int:dream_id>/<action>`, and `/api/v1/workshop/*` write/delete routes, add the same owner gate unless the handler already has one. These are owner cockpit actions, not public write APIs.

- [ ] **Step 3: Extend tests for at least one S7 proxy and one cockpit proxy**

Add to `OwnerSurfaceTests`:

```python
    def test_s7_status_still_uses_existing_proxy_shape(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            response = mock.Mock()
            response.status = 200
            response.headers = {"Content-Type": "application/json"}
            response.read.return_value = b'{"ok": true, "enrolled": false}'
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=None)
            urlopen.return_value = response
            result = self.client.get("/api/v1/s7/webauthn/status")
        self.assertEqual(result.status_code, 200)
```

If this test conflicts with existing proxy test patterns, reuse the exact stubbing pattern from `tests/test_cockpit_proxies_2026_05_05.py` instead of inventing a second one.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked tests.test_cockpit_proxies_2026_05_05 tests.test_s7_1_daemon_internal_channel tests.test_s7_webauthn_enrollment_asset_boundary
```

Expected: all pass.

- [ ] **Step 5: Commit owner-gate evidence**

```bash
cd /home/rohit/maez
git add skills/web_interface.py tests/test_legacy_public_web_doors_parked.py
git commit -m "fix(web): require owner gate for kept api v1 state routes"
```

Commit body:

```text
Keep /api/v1 as the owner cockpit namespace only after proving state-returning routes require owner-private access.

## Predicted effect
Remote or unauthenticated callers cannot read /api/v1 soul, memory, lived-memory, timeline, identity, router, logs, or chat-session state. Loopback owner/cockpit use remains available through the existing owner-private recovery gate.
```

---

### Task 4: Remove Active Links to Parked Doors from Kept Cosmetic Pages

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/progress_public.html`
- Modify: `ui/privacy.html`
- Modify: any kept static page Task 0 found linking to `/login`, `/chat`, `/history`, `/journal`, `/planner`, or `/analytics`
- Test: `tests/test_legacy_public_web_doors_parked.py`

- [ ] **Step 1: Add failing stale-link test**

Append:

```python
class KeptCosmeticPageLinkTests(unittest.TestCase):
    def test_kept_cosmetic_pages_do_not_link_to_parked_doors(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(wi.__file__), ".."))
        pages = (
            "ui/index.html",
            "ui/progress_public.html",
            "ui/privacy.html",
        )
        parked_patterns = (
            r'(href|action|fetch)\s*\(?[\'"]/(login|chat|history|journal|planner|analytics)[\'"/?]',
            r'fetch\([\'"]/(status|api/maez-state|api/session-timeline|api/analytics-summary|api/planner-board)[\'"?]',
            r'window\.location(\.href)?\s*=\s*[\'"]/(login|chat|history|journal|planner|analytics)[\'"/?]',
        )
        for page in pages:
            with self.subTest(page=page):
                html = open(os.path.join(repo_root, page), encoding="utf-8").read()
                for pattern in parked_patterns:
                    self.assertIsNone(re.search(pattern, html), f"{page} still points at parked route via {pattern}")
```

- [ ] **Step 2: Run and verify it fails**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked.KeptCosmeticPageLinkTests
```

Expected: fails on existing `/login`, `/planner`, or `/analytics` links.

- [ ] **Step 3: Repoint links**

Change active links and fetches to old doors:

```html
href="/login"
```

to:

```html
href="/cockpit"
```

Change `/planner` and `/analytics` links on kept pages to `/cockpit` or remove them if they are local-owner-only nav. Remove or disable kept-page JavaScript that fetches parked read-doors like `/status`; do not replace it with fabricated static status. Do not edit cosmetic copy beyond the link target and short label if the label would now be misleading.

- [ ] **Step 4: Run stale-link and app-park tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked.KeptCosmeticPageLinkTests tests.test_app_parked_redirect
```

Expected: pass.

- [ ] **Step 5: Commit link cleanup**

```bash
cd /home/rohit/maez
git add ui/index.html ui/progress_public.html ui/privacy.html tests/test_legacy_public_web_doors_parked.py
git commit -m "fix(web): repoint kept pages away from parked doors"
```

---

### Task 5: Verification and Handoff

**Files:**
- Create: `docs/handoffs/2026-06-28-legacy-public-web-doors-parked.md`

- [ ] **Step 1: Run focused verification**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_legacy_public_web_doors_parked \
  tests.test_app_parked_redirect \
  tests.test_cockpit_proxies_2026_05_05 \
  tests.test_s7_1_daemon_internal_channel \
  tests.test_s7_webauthn_enrollment_asset_boundary
```

Expected: all pass.

- [ ] **Step 2: Run lint on changed files**

```bash
cd /home/rohit/maez
.venv/bin/ruff check skills/web_interface.py tests/test_legacy_public_web_doors_parked.py
```

Expected: no errors.

- [ ] **Step 3: Write handoff**

Create `docs/handoffs/2026-06-28-legacy-public-web-doors-parked.md`:

```markdown
# Legacy Public Web Doors Parked — Handoff

## Summary
Parked legacy maez-web entry/talk/write/read doors while keeping the owner cockpit and verified local integrations intact.

## Parked
- `/login`, `/register`, `/link-telegram`, `/chat`
- `/history`, `/status`, `/api/maez-state`, `/api/session-timeline`, `/journal`
- `/api/analytics`, `/api/analytics-summary`, `/api/planner-board`
- `/debug`, `/debug/*`, `/api/debug/*`
- `/v1/fast-reply` when `MAEZ_LIVE_FAST_LANE_ENABLED=1`

## Kept
- `/cockpit`, `/cockpit/s7-webauthn-proof`, `/console`
- `/api/v1/*` owner/trusted-channel gated routes
- `/api/iphone/ingest` token-auth iOS Shortcut ingress
- `/api/progress-board` public projection via `_planner_public_view`
- cosmetic static pages

## Verification
- Focused unittest command:
  `.venv/bin/python -m unittest tests.test_legacy_public_web_doors_parked tests.test_app_parked_redirect tests.test_cockpit_proxies_2026_05_05 tests.test_s7_1_daemon_internal_channel tests.test_s7_webauthn_enrollment_asset_boundary`
- Ruff:
  `.venv/bin/ruff check skills/web_interface.py tests/test_legacy_public_web_doors_parked.py`

## Predicted live witness
After restart, `/login`, `/chat`, `/status`, `/api/maez-state`, `/api/session-timeline`, and `/journal` no longer expose old web state. `/cockpit` and `/cockpit/s7-webauthn-proof` still serve.
```

- [ ] **Step 4: Commit handoff**

```bash
cd /home/rohit/maez
git add docs/handoffs/2026-06-28-legacy-public-web-doors-parked.md
git commit -m "docs(web): hand off legacy public door parking"
```

- [ ] **Step 5: Stop at review gate**

Do not merge or restart. Hand off for covenant review with:

```text
Review gate:
- Door classification followed capability, not path shape.
- `/v1/fast-reply` explicitly handled.
- `/api/v1/*` kept only with owner/trusted-channel evidence.
- `/api/iphone/ingest` classified from code and tested.
- `/api/progress-board` kept only as public projection.
- Old doors parked, not deleted.
- Cockpit/S7 proxy tests unchanged and green.
```
