# Cockpit Real-State Bridge (organ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing-but-exposed cockpit real-state bridge on `main` — close the daemon's open `/internal/cockpit/state` with an S7 gate, owner-gate the web `/api/v1/daemon/state`, and make its proxy actually send the S7 token — so the daemon's live in-memory state is read only by the owner over an authenticated nerve.

**Architecture:** MODIFY existing functions in place (do NOT rebuild `_build_cockpit_state` / `_daemon_cockpit_state_proxy` / the flag-switch — they exist). Always-on auth (S7 on the daemon endpoint, owner on the web endpoint via #1's loopback/claimed matrix); the real-state SOURCE stays flag-gated (`MAEZ_COCKPIT_REAL_STATE`). Read-only.

**Tech Stack:** Python 3, Flask, `daemon/maez_daemon.py`, `skills/web_interface.py`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-06-18-cockpit-real-state-bridge-organ-design.md` (@24a5fd9).

---

## Lane discipline

- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` — named modules only, NEVER full-discover.
- Branch (use `superpowers:using-git-worktrees`): `cockpit-real-state-bridge-organ`. `main` local-only — **no push**.
- `## Predicted effect` on behavior commits; docs/proof/test-only commits omit it. End commits with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 4). No merge/restart/flag-flip/token-provision (owner-sovereign). Cross-lane Codex review at the gate.
- **HARDEN, do not rebuild.** If a task tempts you to recreate `_build_cockpit_state` or `_daemon_cockpit_state_proxy` or the flag-switch, STOP — modify the existing one.
- **Scope guard:** touch ONLY the named files; no web-owner-spine / voice code.

## File structure

- **Modify** `daemon/maez_daemon.py` — add the S7 gate to the existing `/internal/cockpit/state` handler.
- **Modify** `skills/web_interface.py` — add `_s7_internal_channel_headers` + the 2 web constants + `_owner_private_auth_required_response`; modify `_daemon_cockpit_state_proxy` (send header + reason); owner-gate `/api/v1/daemon/state`.
- **Modify** `tests/test_s7_1_daemon_internal_channel.py` — add the daemon `/internal/cockpit/state` route gate tests (reuse its captured-app test-client harness).
- **Create** `tests/test_cockpit_real_state_bridge.py` — the web-side hermetic tests (proxy header-capture, owner/flag/no-token matrix).
- **Create** `docs/proof/2026-06-18-cockpit-real-state-bridge-task0.md` (Task 0).

---

### Task 0: HARD PROOF GATE (docs/proof only — committed first)

**Files:** Create `docs/proof/2026-06-18-cockpit-real-state-bridge-task0.md`

- [ ] **Step 1: Consumer inventory of the daemon endpoint (only PRODUCTION consumer?)**
```bash
cd /home/rohit/maez
grep -rn "internal/cockpit/state\|DAEMON_COCKPIT_STATE_URL" daemon/ skills/ web/ tests/ core/
```
Classify EACH hit as **production** or **test**. Required conclusion: the only *production* reader of the daemon `/internal/cockpit/state` is the web `_daemon_cockpit_state_proxy` (via `DAEMON_COCKPIT_STATE_URL`). Test references are expected and do NOT refute the design. If any NON-test code reads it ungated, STOP for a scope decision.

- [ ] **Step 2: Consumer inventory of the web endpoint (Organ-1 orphan lesson)**
```bash
grep -rn "api/v1/daemon/state\|daemon/state\|_pollDaemon\|daemonState" web/cockpit/ skills/web_interface.py tests/
```
Record who calls `/api/v1/daemon/state`: expected = `web/cockpit/sim.jsx` `_pollDaemon`. Confirm the always-on owner gate won't orphan a *public* (no-cookie) consumer. The cockpit is the owner's authenticated browser → owner-gated is correct. Note any other consumer.

- [ ] **Step 3: Clean-separation proof**
```bash
sed -n '/def cockpit_state/,/_build_cockpit_state/p' daemon/maez_daemon.py | grep -iE 's7|web_owner|handle_message|voice' || echo "daemon handler clean"
sed -n '/def _daemon_cockpit_state_proxy/,/return {"status"/p' skills/web_interface.py | grep -iE 'web_owner|handle_message|voice|proxy_web_owner' || echo "web proxy clean"
```
Expected: both "clean" (the bridge calls no web-owner/voice spine).

- [ ] **Step 4: Import-resolution proof**
```bash
/home/rohit/maez/.venv/bin/python -c "import ast,sys; [None]"  # sanity
grep -n "def _owner_private_auth_ok\|def _api_daemon_state_log_scrape\|DAEMON_COCKPIT_STATE_URL" skills/web_interface.py
grep -n "def _s7_internal_channel_trusted\|S7_INTERNAL_CHANNEL_TOKEN_ENV\|S7_INTERNAL_CHANNEL_HEADER\|def _build_cockpit_state" daemon/maez_daemon.py
grep -n "def strict_env_flag" core/infra/env_flags.py
```
Expected: all resolve on main (they're the building blocks the organ composes). Record. If any is missing, STOP.

- [ ] **Step 5: Commit (docs only)**
```bash
git add docs/proof/2026-06-18-cockpit-real-state-bridge-task0.md
git commit -m "docs(proof): cockpit-real-state-bridge Task 0 — consumer inventory, clean separation, imports

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: Daemon — S7-gate the open `/internal/cockpit/state` (+ Origin-spoof pinned on this route)

**Files:** Modify `daemon/maez_daemon.py` (the `cockpit_state` handler — grep `"/internal/cockpit/state"`); Test: `tests/test_s7_1_daemon_internal_channel.py`.

- [ ] **Step 1: Add the failing tests — reuse the captured-app harness in `tests/test_s7_1_daemon_internal_channel.py`**

That file already builds the daemon's Flask app and exposes it via a captured-app `test_client()` (it patches the server factory to capture `app`, then `app.test_client()`), and sets the S7 token for the channel. **Read its existing test-client helper + token setup**, then add a test class mirroring it:
```python
class CockpitStateS7Gate(unittest.TestCase):
    # Build the daemon app + test_client via THIS module's existing captured-app helper
    # (the fake_make_server capture used by S71DaemonInternalChannelTests) and set
    # S7_INTERNAL_CHANNEL_TOKEN="test-channel-secret" the same way those tests do.

    def test_valid_s7_header_returns_200(self):
        client = self._daemon_test_client()                       # reuse the existing helper
        r = client.get("/internal/cockpit/state",
                       headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"})
        self.assertEqual(r.status_code, 200)                      # _build_cockpit_state tolerates missing attrs (nulls, no crash)

    def test_headerless_returns_403(self):
        client = self._daemon_test_client()
        r = client.get("/internal/cockpit/state")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json().get("error"), "s7_internal_channel_untrusted")

    def test_valid_header_plus_origin_still_403(self):           # the no-Origin guard, PINNED on this new open nerve
        client = self._daemon_test_client()
        r = client.get("/internal/cockpit/state",
                       headers={"X-Maez-S7-Internal-Channel": "test-channel-secret",
                                "Origin": "http://127.0.0.1:11437"})
        self.assertEqual(r.status_code, 403)
```
> Wire `_daemon_test_client()` to the module's existing app-capture helper (grep the file for the `make_server`/`test_client` capture used by `S71DaemonInternalChannelTests`) and the token env it sets. Do NOT instantiate a full real daemon — reuse the existing lightweight fixture. If that harness already exposes a client helper, call it directly.
>
> **Fallback (if the captured-app harness is genuinely impractical):** at minimum, ALSO add a direct gate-logic test mirroring the existing `S7InternalChannelRuntimeToken` class — `_s7_internal_channel_trusted(SimpleNamespace(headers={...}))` returns True for a valid token + no Origin, False for headerless, **False for valid-token + `Origin` set** — AND assert the `cockpit_state` handler source contains `_s7_internal_channel_trusted(request)` before `_build_cockpit_state`. The route-level test is preferred (the owner wants Origin-spoof pinned on the route); the gate-logic test is the floor, never the only coverage if the route test is achievable.

- [ ] **Step 2: Run — expect FAIL** (the route is currently ungated → headerless returns 200, Origin returns 200)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel -v`

- [ ] **Step 3: Add the S7 gate to the handler.** In `daemon/maez_daemon.py`, the `cockpit_state` handler currently is just `return jsonify(_build_cockpit_state(self))`. Add the gate first:
```python
        @app.route("/internal/cockpit/state")
        def cockpit_state():
            if not _s7_internal_channel_trusted(request):
                return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
            # FAST real-state read for the cockpit face ... (keep the existing comment)
            return jsonify(_build_cockpit_state(self))
```
(`request` is the Flask global already used elsewhere in this module; `_s7_internal_channel_trusted` already exists. Always-on — no flag.)

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_s7_1_daemon_internal_channel.py
git add daemon/maez_daemon.py tests/test_s7_1_daemon_internal_channel.py
git commit -m "feat(cockpit): S7-gate the daemon /internal/cockpit/state (close the open nerve)

## Predicted effect
The daemon's fast real-state endpoint now requires the S7 internal-channel token (constant-time
match, no-Origin CSRF guard) — a headerless, wrong-token, or browser-Origin request gets 403.
Previously it was open on 127.0.0.1:11435. Always-on (no flag).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Web — the proxy actually SENDS the S7 token (+ honest reason, no scrape fallback)

**Files:** Modify `skills/web_interface.py` (add constants + `_s7_internal_channel_headers`; modify `_daemon_cockpit_state_proxy`). Test: `tests/test_cockpit_real_state_bridge.py`.

- [ ] **Step 1: Write the failing tests — `tests/test_cockpit_real_state_bridge.py`**
```python
import json, os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from unittest import mock
import urllib.error
from skills import web_interface as W

class ProxySendsS7Token(unittest.TestCase):
    def test_proxy_sends_managed_token_header(self):
        captured = {}
        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"status": "ok", "cycle_count": 7}).encode()
        def fake_urlopen(req, timeout=None):
            captured["req"] = req                      # capture the OUTGOING Request
            return _Resp()
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok-123"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = W._daemon_cockpit_state_proxy()
        self.assertEqual(out["cycle_count"], 7)
        # the header was actually SENT (urllib title-cases the key):
        self.assertEqual(captured["req"].get_header("X-maez-s7-internal-channel"), "tok-123")

    def test_proxy_no_token_is_unreachable_with_reason(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            out = W._daemon_cockpit_state_proxy()
        self.assertEqual(out, {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})

    def test_proxy_daemon_403_is_untrusted_reason(self):
        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError("u", 403, "forbidden", {}, None)
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = W._daemon_cockpit_state_proxy()
        self.assertEqual(out, {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})

    def test_proxy_daemon_down_is_unreachable_reason(self):
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
            out = W._daemon_cockpit_state_proxy()
        self.assertEqual(out["status"], "unreachable")
        self.assertEqual(out["reason"], "daemon_unreachable")
```

- [ ] **Step 2: Run — expect FAIL** (`_daemon_cockpit_state_proxy` sends no header / returns no reason)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_real_state_bridge -v`

- [ ] **Step 3: Add the web S7 constants + headers helper, and modify the proxy.** In `skills/web_interface.py`, add near the other private helpers:
```python
_S7_INTERNAL_CHANNEL_HEADER = "X-Maez-S7-Internal-Channel"
_S7_INTERNAL_CHANNEL_TOKEN_ENV = "S7_INTERNAL_CHANNEL_TOKEN"


def _s7_internal_channel_headers() -> dict[str, str]:
    token = os.environ.get(_S7_INTERNAL_CHANNEL_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError("s7_internal_channel_untrusted")
    return {_S7_INTERNAL_CHANNEL_HEADER: token}
```
Then **modify** `_daemon_cockpit_state_proxy` (keep its docstring; do NOT recreate it elsewhere):
```python
def _daemon_cockpit_state_proxy(timeout=1.5):
    """Proxy the daemon's fast real-state endpoint verbatim. ... (keep existing docstring)"""
    import urllib.error as _urlerr   # web_interface.py imports only urllib.request at top
    try:
        headers = _s7_internal_channel_headers()
    except RuntimeError:
        return {"status": "unreachable", "reason": "s7_internal_channel_untrusted"}
    try:
        req = urllib.request.Request(DAEMON_COCKPIT_STATE_URL, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except _urlerr.HTTPError as e:
        reason = "s7_internal_channel_untrusted" if e.code == 403 else "daemon_error"
        return {"status": "unreachable", "reason": reason}
    except Exception as e:
        logger.debug("daemon cockpit-state unreachable: %s", e)
        return {"status": "unreachable", "reason": "daemon_unreachable"}
```

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_real_state_bridge -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_cockpit_real_state_bridge.py
git add skills/web_interface.py tests/test_cockpit_real_state_bridge.py
git commit -m "feat(cockpit): web real-state proxy sends the S7 token + honest unreachable reason

## Predicted effect
_daemon_cockpit_state_proxy now sends X-Maez-S7-Internal-Channel with the managed token, and on
failure returns an honest {status: unreachable, reason: ...} (s7_internal_channel_untrusted when the
token is absent or the daemon 403s; daemon_unreachable when it's down) — never a scrape fallback or
fabricated state.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Web — owner-gate `/api/v1/daemon/state` (always-on, via #1's matrix)

**Files:** Modify `skills/web_interface.py` (`api_daemon_state` + add `_owner_private_auth_required_response`). Test: `tests/test_cockpit_real_state_bridge.py` (add the matrix).

- [ ] **Step 1: Add the failing tests** (append to `tests/test_cockpit_real_state_bridge.py`)
```python
from contextlib import contextmanager

class DaemonStateEndpointMatrix(unittest.TestCase):
    def setUp(self):
        W.app.config["TESTING"] = True
        self.client = W.app.test_client()

    @contextmanager
    def _owner(self, ok=True):
        with mock.patch.object(W, "_owner_private_auth_ok", return_value=ok):
            yield

    def test_non_owner_gets_401(self):
        with self._owner(ok=False):
            r = self.client.get("/api/v1/daemon/state")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json().get("error"), "owner_auth_required")

    def test_owner_flag_off_uses_log_scrape(self):
        with self._owner(), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_COCKPIT_REAL_STATE", None)
            r = self.client.get("/api/v1/daemon/state")
        self.assertEqual(r.status_code, 200)              # legacy log-scrape shape for the authorized owner

    def test_owner_flag_on_with_token_returns_real(self):
        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"status": "ok", "cycle_count": 42}).encode()
        with self._owner(), \
             mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": "1", "S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", return_value=_Resp()):
            r = self.client.get("/api/v1/daemon/state")
        self.assertEqual(r.get_json()["cycle_count"], 42)

    def test_owner_flag_on_no_token_is_unreachable_no_scrape(self):
        with self._owner(), mock.patch.dict(os.environ, {"MAEZ_COCKPIT_REAL_STATE": "1"}, clear=False):
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            r = self.client.get("/api/v1/daemon/state")
        body = r.get_json()
        self.assertEqual(body, {"status": "unreachable", "reason": "s7_internal_channel_untrusted"})
```

- [ ] **Step 2: Run — expect FAIL** (no owner gate → non-owner gets 200, not 401)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_real_state_bridge -v`

- [ ] **Step 3: Add the helper + the owner gate.** In `skills/web_interface.py`, add near the other auth helpers:
```python
def _owner_private_auth_required_response():
    return jsonify({"ok": False, "error": "owner_auth_required"}), 401
```
Then modify `api_daemon_state` — owner-gate FIRST, keep the existing flag-switch:
```python
@app.route("/api/v1/daemon/state")
def api_daemon_state():
    """Daemon state for the cockpit face. (keep the existing docstring)"""
    if not _owner_private_auth_ok():
        return _owner_private_auth_required_response()
    if strict_env_flag("MAEZ_COCKPIT_REAL_STATE"):
        return jsonify(_daemon_cockpit_state_proxy())
    return _api_daemon_state_log_scrape()
```

- [ ] **Step 4: Run — expect PASS** (the whole web module green)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_real_state_bridge -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_cockpit_real_state_bridge.py
git add skills/web_interface.py tests/test_cockpit_real_state_bridge.py
git commit -m "feat(cockpit): owner-gate /api/v1/daemon/state (close the open web endpoint)

## Predicted effect
/api/v1/daemon/state now requires the owner (via #1's _owner_private_auth_ok loopback/claimed matrix —
no lockout); a non-owner/remote request gets 401. The real-state source stays flag-gated; flag-off
serves the same log-scrape shape to the authorized owner. The daemon's live in-memory state is no
longer readable without owner auth.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-18-cockpit-real-state-bridge-organ-handoff.md`.

- [ ] **Step 1: Whole-organ green + ruff**
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel tests.test_cockpit_real_state_bridge -v
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py skills/web_interface.py tests/test_cockpit_real_state_bridge.py
```
Expected: all green; ruff clean.

- [ ] **Step 2: Write the handoff + commit (docs).** Cover: branch tip, the Task-0 proof outputs, the diff (daemon gate + web helpers/proxy/owner-gate), test results, and the **Codex cross-lane anchors**: (1) harden-not-rebuild — `_build_cockpit_state`/`_daemon_cockpit_state_proxy`/the flag-switch were MODIFIED not recreated; (2) the daemon `/internal/cockpit/state` is now S7-gated incl. **Origin-spoof → 403** pinned on the route; (3) the web proxy **actually sends** `X-Maez-S7-Internal-Channel` (test captures the outgoing Request); (4) flag-on + no/wrong token → honest `unreachable` + reason, **no scrape fallback**; (5) `/api/v1/daemon/state` owner-gated with **no lockout** (#1 loopback/claimed matrix); (6) clean separation — no web-owner/voice. Then the **owner breath**: provision `S7_INTERNAL_CHANNEL_TOKEN` in `config/secrets.local.env` for **both** maez + maez-web (NOT model.env), restart both, flip `MAEZ_COCKPIT_REAL_STATE=1`, and browser-witness the cockpit DaemonPane showing **real** daemon state (live `cycle_count`/`cognition`/`last_thought`/`valence`/`reasoning_loop`) — with the daemon endpoint now 403ing a headerless probe. **Not `LIVE_WITNESSED` until the owner confirms.**
```bash
git add docs/handoffs/2026-06-18-cockpit-real-state-bridge-organ-handoff.md
git commit -m "docs(handoff): cockpit real-state bridge organ — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP.** No merge/restart/flag/token-provision — owner-sovereign. Hand to Codex cross-lane review.

---

## Notes for the implementer

- **Harden, don't rebuild** — `_build_cockpit_state`, `_daemon_cockpit_state_proxy`, and the `MAEZ_COCKPIT_REAL_STATE` flag-switch already exist on main; modify in place.
- **Hermetic tests only** — mock `_owner_private_auth_ok` / set the token in `os.environ`; never touch the live `users.db`. The daemon-route tests reuse the existing captured-app harness in `tests/test_s7_1_daemon_internal_channel.py`.
- **The two tests that matter most** (the owner named them): browser-`Origin` spoofing fails on `/internal/cockpit/state` (403), and the web proxy *actually sends* the S7 token (assert on the captured outgoing `Request`, not just the response).
- **No lockout** — the owner gate is `_owner_private_auth_ok` (#1's loopback/claimed matrix); flag-off still serves the owner the log-scrape.
