# Cockpit Conversation Spine 3a — Secure the Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close a write hole on the existing cockpit→daemon conversation path — owner-gate the web `api_cockpit_message` send, S7-gate the daemon `/message` receive — so only the owner browser may send, and only over the private S7 nerve.

**Architecture:** MODIFY two existing functions in place (do NOT rebuild; Approach A = gate the shared `/message` route). Both gates run BEFORE body parsing. Transport security only — no change to the inbound turn (`cockpit_core`/felt-time/tools are sub-organs 3b/3c). Telegram is unaffected (it reaches `handle_message` in-process, never the HTTP `/message` route).

**Tech Stack:** Python 3, Flask, `daemon/maez_daemon.py`, `skills/web_interface.py`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-06-18-cockpit-conversation-spine-3a-secure-design.md` (@bf382c4).

---

## ⚠️ Build prerequisite — Organ 2 must be merged first

3a REUSES two web symbols that exist ONLY on the unmerged Organ-2 branch (`cb7a37f`), NOT on `main`:
`_s7_internal_channel_headers()` and `_owner_private_auth_required_response()`. **The worktree must base on
`main` AFTER the owner has breathed/merged Organ 2.** Task 0 Step 4 verifies these resolve; if they do not,
**STOP** — the owner merges Organ 2 first. No new secret: the same `S7_INTERNAL_CHANNEL_TOKEN` Organ 2's
breath provisions covers 3a too.

## Lane discipline

- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` — named modules only, NEVER full-discover.
- Branch (use `superpowers:using-git-worktrees`): `cockpit-conversation-spine-3a-secure`, based on main-with-Organ-2. `main` local-only — **no push**.
- `## Predicted effect` on behavior commits; docs/proof/test-only omit it. End commits with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 3). No merge/restart/flag-flip/token-provision (owner-sovereign). Cross-lane Codex review at the gate.
- **HARDEN, do not rebuild.** Modify `api_cockpit_message` + the daemon `/message` route in place; add no new route (Approach A).
- **Scope guard:** touch ONLY `daemon/maez_daemon.py`, `skills/web_interface.py`, `tests/test_s7_1_daemon_internal_channel.py`, `tests/test_cockpit_proxies_2026_05_05.py`, and the proof/handoff docs. NO inbound-path / `cockpit_core` / felt-time / tools / `/chat` change.

## File structure

- **Modify** `daemon/maez_daemon.py` — add the S7 gate to the existing `/message` handler (before `get_json`).
- **Modify** `skills/web_interface.py` — add the owner gate + S7 header + missing-token 502 + `finally: e.close()` to `api_cockpit_message` (owner gate before `get_data`), preserving the tuple-return contract.
- **Modify** `tests/test_s7_1_daemon_internal_channel.py` — daemon `/message` gate tests (reuse the `_DaemonAppClientMixin` captured-app client, added by Organ 2's daemon-gate task and present on the Organ-2-merged base).
- **Modify** `tests/test_cockpit_proxies_2026_05_05.py` — update the existing HTTP test (owner mock + S7-header assertion) and add the web matrix.
- **Create** `docs/proof/2026-06-18-cockpit-conversation-spine-3a-task0.md` (Task 0).

---

### Task 0: HARD PROOF GATE (docs/proof only — committed first)

**Files:** Create `docs/proof/2026-06-18-cockpit-conversation-spine-3a-task0.md`

- [ ] **Step 1: Consumer inventory of daemon `/message` (decides A vs B)**
```bash
cd <worktree>
grep -rn '"/message"\|:11435/message\|_DAEMON_BASE' daemon/ skills/ web/ scripts/ tests/ core/
```
Classify EACH hit production vs test. Required conclusion: the only *production* HTTP caller of the daemon `/message` route is the web `api_cockpit_message` proxy (`f"{_DAEMON_BASE}/message"`). The only test that makes a *real HTTP POST* is `tests/test_cockpit_proxies_2026_05_05.py`. **Do NOT mis-classify** `tests/test_ui_message_history_threading.py` (it imports + calls `_pair_history_for_chat_threading` directly — no HTTP) or `tests/test_subjective_duration_static_boundaries.py` (it `read_text`+`ast.parse`-slices source — no HTTP). If a non-test, non-cockpit production HTTP caller exists → STOP and switch to **Approach B** (dedicated `/internal/cockpit/message` route); otherwise proceed with **Approach A**.

- [ ] **Step 2: Telegram-path proof (the daemon gate can't starve telegram)**
```bash
grep -n "handle_message" skills/surface/maez_adapter.py
grep -n "def handle_message" daemon/maez_daemon.py
```
Confirm telegram reaches `daemon.handle_message` **in-process** via `skills/surface/maez_adapter.py` (~:1197), NOT through the HTTP `/message` route. Record the call path. (So S7-gating `/message` affects only HTTP callers — the cockpit proxy.)

- [ ] **Step 3: Clean-separation proof**
```bash
sed -n '/def api_cockpit_message/,/daemon_unreachable/p' skills/web_interface.py | grep -iE 'proxy_web_owner|handle_message|voice|private_owner_bridge|/chat' || echo "web proxy: clean"
sed -n '/@app.route("\/message"/,/def message/p' daemon/maez_daemon.py | grep -iE 'web_owner|voice' || echo "daemon /message handler head: clean"
```
Expected: both clean (3a adds gates only; no web-owner-spine/voice/`private_owner_bridge`/`/chat`).

- [ ] **Step 4: Import-resolution proof — ON THE ORGAN-2-MERGED BASE (load-bearing)**
```bash
grep -n "def _s7_internal_channel_headers\|def _owner_private_auth_required_response\|def _owner_private_auth_ok\|_DAEMON_BASE =\|_COCKPIT_PROXY_TIMEOUT_S =\|def api_cockpit_message" skills/web_interface.py
grep -n "def _s7_internal_channel_trusted\|@app.route(\"/message\"" daemon/maez_daemon.py
```
Expected: ALL present. **If `_s7_internal_channel_headers` or `_owner_private_auth_required_response` is missing → Organ 2 is not merged into this base. STOP. The owner must breathe/merge Organ 2 first; do not re-create the helpers here (that would duplicate Organ 2).**

- [ ] **Step 5: Existing-test-breakage inventory**

Record: the only test exercising the gated HTTP path is `tests/test_cockpit_proxies_2026_05_05.py` (POSTs `/api/v1/cockpit/message` → becomes owner-gated → needs an owner mock; its `urlopen` patch now also sees the S7 header). It will be updated in Task 2. Re-grep to confirm no other test POSTs to `/api/v1/cockpit/message` or daemon `/message` over HTTP. End the doc with `TASK 0 VERDICT: GO (Approach A)` or `NO-GO — <reason>`.

- [ ] **Step 6: Commit (docs only)**
```bash
git add docs/proof/2026-06-18-cockpit-conversation-spine-3a-task0.md
git commit -m "docs(proof): cockpit-conversation-spine-3a Task 0 — consumer inventory, telegram-in-process, Organ-2 base

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: Daemon — S7-gate the `/message` route (gate before parse; Origin pinned)

**Files:** Modify `daemon/maez_daemon.py` (the `message` handler — grep `@app.route("/message"`); Test: `tests/test_s7_1_daemon_internal_channel.py`.

- [ ] **Step 1: Write the failing tests** — reuse the captured-app `_DaemonAppClientMixin` already in `tests/test_s7_1_daemon_internal_channel.py` (added by Organ 2's daemon-gate task; it captures the daemon Flask app → `_client()`, and the S7 tests set `S7_INTERNAL_CHANNEL_TOKEN="test-channel-secret"`). Add:
```python
class MessageRouteS7Gate(_DaemonAppClientMixin, unittest.TestCase):
    def test_valid_s7_header_returns_non_403(self):
        client = self._client()
        r = client.post("/message",
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret"},
                        json={"text": "hi"})
        self.assertNotEqual(r.status_code, 403)          # gate passes; downstream may 200/4xx, just not the gate's 403

    def test_headerless_returns_403(self):
        client = self._client()
        r = client.post("/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json().get("error"), "s7_internal_channel_untrusted")

    def test_wrong_token_returns_403(self):
        client = self._client()
        r = client.post("/message", headers={"X-Maez-S7-Internal-Channel": "nope"}, json={"text": "hi"})
        self.assertEqual(r.status_code, 403)

    def test_valid_header_plus_origin_still_403(self):    # no-Origin CSRF guard, PINNED on /message
        client = self._client()
        r = client.post("/message",
                        headers={"X-Maez-S7-Internal-Channel": "test-channel-secret",
                                 "Origin": "http://127.0.0.1:11437"},
                        json={"text": "hi"})
        self.assertEqual(r.status_code, 403)

    def test_gate_runs_before_body_parse(self):           # malformed body + no token -> still 403, never 400
        client = self._client()
        r = client.post("/message", data=b"not json", content_type="application/json")
        self.assertEqual(r.status_code, 403)
```
> Wire to the existing `_DaemonAppClientMixin` / `_client()` helper and the token env the existing S7 tests set. Do NOT instantiate a real daemon — reuse the Organ-1 fixture. `test_valid_s7_header_returns_non_403` asserts `!= 403` (not `== 200`) because the bare captured-app daemon may produce a non-gate status downstream; the gate's contract is "untrusted → 403," and the valid path must clear the gate.

- [ ] **Step 2: Run — expect FAIL** (route is ungated → headerless/Origin POSTs return non-403)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel -v`

- [ ] **Step 3: Add the S7 gate as the FIRST statements of the handler** (before `request.get_json`):
```python
        @app.route("/message", methods=["POST"])
        def message():
            if not _s7_internal_channel_trusted(request):
                return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403
            data = request.get_json(silent=True) or {}
            # ... existing body unchanged ...
```
(`_s7_internal_channel_trusted` and `request`/`jsonify` are already in module scope. Always-on; no flag. Do NOT touch anything below the gate.)

- [ ] **Step 4: Run — expect PASS** (all 5 new tests + the module's pre-existing tests green)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_s7_1_daemon_internal_channel.py
git add daemon/maez_daemon.py tests/test_s7_1_daemon_internal_channel.py
git commit -m "feat(cockpit): S7-gate the daemon /message route (close the write hole)

## Predicted effect
The daemon /message HTTP route now requires the S7 internal-channel token before parsing the body —
a headerless, wrong-token, or browser-Origin POST gets 403 s7_internal_channel_untrusted. Telegram is
unaffected (it reaches handle_message in-process, not via /message). Always-on (no flag).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Web — owner-gate the send + send the S7 token + honest missing-token 502 (preserve contract)

**Files:** Modify `skills/web_interface.py` (`api_cockpit_message`). Test: `tests/test_cockpit_proxies_2026_05_05.py`.

- [ ] **Step 1: Write the failing tests** — ADD to `tests/test_cockpit_proxies_2026_05_05.py` (it ALREADY exists with a `self.client` Flask test-client + a `_make_urlopen_response` helper; **add, don't clobber**). Read it first; reuse its helpers. Add a class:
```python
class CockpitMessageGate(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi
        wi.app.config["TESTING"] = True
        self.client = wi.app.test_client()

    def test_non_owner_gets_401_before_body(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=False):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json().get("error"), "owner_auth_required")

    def test_owner_no_token_is_502_failed_send(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=AssertionError("must not send without token")) as up:
            os.environ.pop("S7_INTERNAL_CHANNEL_TOKEN", None)
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json(), {"ok": False, "error": "s7_internal_channel_untrusted"})
        up.assert_not_called()                              # no send attempted

    def test_owner_with_token_sends_s7_header(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["req"] = req                           # capture OUTGOING Request
            return _make_urlopen_response(b'{"reply":"ok"}', status=200)
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "tok-123"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["req"].get_header("X-maez-s7-internal-channel"), "tok-123")

    def test_preserves_daemon_content_type(self):           # guards against re-hardcoding application/json
        def fake_urlopen(req, timeout=None):
            return _make_urlopen_response(b"plain reply", status=200, content_type="text/plain")
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.headers.get("Content-Type"), "text/plain")

    def test_daemon_down_is_502_unreachable(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("refused")):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json().get("error"), "daemon_unreachable")
```
> Confirm `_make_urlopen_response` accepts/forwards a `content_type` kwarg; if it doesn't, extend that helper to set the response's `headers["Content-Type"]` (it's the test file's own fake — extending it is in-scope). Use the module alias the file already uses (`mock`, `os` imports at top).

ALSO **update the existing HTTP test** in this file (`test_forwards_body_to_daemon_and_returns_reply`): wrap its request in `mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)` and set `S7_INTERNAL_CHANNEL_TOKEN` in env (else it now 401s / 502s). Keep its existing daemon-URL assertion; optionally also assert the S7 header on the captured request.

- [ ] **Step 2: Run — expect FAIL** (`api_cockpit_message` has no owner gate / sends no token)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_proxies_2026_05_05 -v`

- [ ] **Step 3: Modify `api_cockpit_message`** — add EXACTLY four things, preserving the tuple-return contract:
```python
@app.route("/api/v1/cockpit/message", methods=["POST"])
def api_cockpit_message():
    """Proxy the cockpit's chat send to the daemon's /message endpoint. ... (keep existing docstring)"""
    if not _owner_private_auth_ok():                                  # (1) gate BEFORE request.get_data()
        return _owner_private_auth_required_response()
    try:
        s7_headers = _s7_internal_channel_headers()                  # (2) raises if token absent
    except RuntimeError:
        return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 502
    import urllib.request as _urlreq
    import urllib.error as _urlerr
    body = request.get_data() or b"{}"
    headers = {"Content-Type": request.headers.get("Content-Type", "application/json"), **s7_headers}
    try:
        req = _urlreq.Request(f"{_DAEMON_BASE}/message", data=body, headers=headers, method="POST")
        with _urlreq.urlopen(req, timeout=_COCKPIT_PROXY_TIMEOUT_S) as resp:
            payload = resp.read()
            status = resp.status
            ctype = resp.headers.get("Content-Type", "application/json")
        return (payload, status, {"Content-Type": ctype})           # (3) PRESERVE contract — daemon CT
    except _urlerr.HTTPError as e:
        try:
            payload = e.read()
        except Exception:
            payload = str(e).encode("utf-8")
        finally:
            e.close()                                               # (4) close even if e.read() raised
        return (payload, e.code, {"Content-Type": "application/json"})
    except Exception as e:
        return jsonify({"ok": False, "error": "daemon_unreachable", "detail": str(e)[:200]}), 502
```
(The only additions vs. today: the owner gate, the `s7_headers` try + `**s7_headers` merge, and `finally: e.close()`. The success tuple and the HTTPError read-fallback stay verbatim. Do NOT introduce `Response(...)` or hardcode `application/json` on the success path.)

- [ ] **Step 4: Run — expect PASS** (the new class + the updated existing test + every other test in the module)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_proxies_2026_05_05 -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_cockpit_proxies_2026_05_05.py
git add skills/web_interface.py tests/test_cockpit_proxies_2026_05_05.py
git commit -m "feat(cockpit): owner-gate + S7-token the cockpit message send (close the write hole)

## Predicted effect
api_cockpit_message now requires the owner (401 before body parse) and sends the S7 token to the daemon;
a missing token is an honest 502 failed-send (not a fabricated reply). The daemon payload/status/Content-Type
contract is preserved unchanged, and the HTTPError response is closed in a finally. Only the owner browser
can now inject messages into Maez's conversation, over the private nerve.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-18-cockpit-conversation-spine-3a-handoff.md`.

- [ ] **Step 1: Whole-organ green + ruff**
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_1_daemon_internal_channel tests.test_cockpit_proxies_2026_05_05 -v
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py skills/web_interface.py tests/test_s7_1_daemon_internal_channel.py tests/test_cockpit_proxies_2026_05_05.py
```
Expected: all green; ruff clean. (If the worktree lacks `config/secrets.local.env`, run web-touching modules with `MAEZ_CONFIG=/home/rohit/maez/config` — the Organ-2 worktree-floor note.)

- [ ] **Step 2: Write the handoff + commit (docs).** Cover: branch tip, the Task-0 verdict (Approach A confirmed; Organ-2 base verified), the diff (daemon +1 gate, web +4 additions), test results, and the **Codex cross-lane anchors**: (1) harden-not-rebuild — two existing functions modified, no new route; (2) **gate-before-parse both sides** — owner before `get_data`, S7 before `get_json` (daemon test: malformed-body-no-token → 403 not 400); (3) the **write hole is closed** — non-owner send → 401, untrusted daemon `/message` → 403; (4) **Origin-spoof → 403 pinned on `/message`**; (5) the proxy **actually sends** `X-Maez-S7-Internal-Channel` (test captures the outgoing Request); (6) **missing token → 502 failed-send**, never a fabricated reply; (7) **contract preserved** — daemon payload/status/Content-Type tuple, no hardcoded JSON (preserve-contract test); (8) `e.close()` in `finally`; (9) **telegram in-process, unaffected**; (10) **no inbound-path/cockpit_core/felt-time/tools change**; (11) the **Organ-2 dependency** (built on the merged base; same S7 token). Then the **owner breath**: 3a needs **no new secret** — the same `S7_INTERNAL_CHANNEL_TOKEN` Organ 2 provisions; merge 3a after Organ 2; restart both; witness: (a) owner sends a cockpit message → gets a reply (one conversation), (b) non-owner/no-cookie POST to `/api/v1/cockpit/message` → 401, (c) `curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:11435/message -d '{"text":"hi"}'` → **403**. **Not `LIVE_WITNESSED` until the owner confirms.**
```bash
git add docs/handoffs/2026-06-18-cockpit-conversation-spine-3a-handoff.md
git commit -m "docs(handoff): cockpit conversation spine 3a — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP.** No merge/restart/flag/token-provision — owner-sovereign. Hand to Codex cross-lane review.

---

## Notes for the implementer

- **Harden, don't rebuild** — `api_cockpit_message` and the daemon `/message` route already exist; add gates only (Approach A, no new route).
- **Gate before parsing** — the owner gate is the FIRST statement of `api_cockpit_message` (before `request.get_data()`); the S7 gate is the FIRST statement of the daemon `message()` handler (before `request.get_json()`). The daemon test proves it (malformed body + no token → 403, not 400).
- **Preserve the contract** — keep the success-path `(payload, status, {"Content-Type": ctype})` tuple and the HTTPError `e.read()`→`str(e)` fallback verbatim; the preserve-contract test (non-JSON daemon Content-Type passes through) guards it.
- **The two tests that matter most** (Organ-2 carryover): the daemon `valid-token + Origin → 403` (proves the CSRF guard on `/message`), and the web test that captures the outgoing `Request` and asserts the S7 header (proves the token is actually sent, not just that the code didn't crash).
- **Hermetic only** — mock `_owner_private_auth_ok`, env the token; never the live `users.db`. Reuse the `_DaemonAppClientMixin` (from Organ 2's daemon-gate task) for the daemon route, and the existing `self.client`/`_make_urlopen_response` for the web side.
- **Don't chase false callers** — `test_ui_message_history_threading.py` and `test_subjective_duration_static_boundaries.py` make NO HTTP call; only `test_cockpit_proxies_2026_05_05.py` does.
