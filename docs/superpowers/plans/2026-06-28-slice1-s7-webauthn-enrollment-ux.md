# Slice 1 — S7 WebAuthn Enrollment UX — Implementation Plan

> **For agentic workers:** Codex's build lane (Claude drafts plan + covenant-reviews; Codex builds; **owner performs the physical key ceremony**). **Do NOT merge, do NOT flip authority flags, do NOT change soul/body/constitution permissions.** This slice *completes and hardens an existing flow* and arms enrollment — it ungates nothing. Spec: [2026-06-28-slice1-s7-webauthn-enrollment-ux-design.md](../specs/2026-06-28-slice1-s7-webauthn-enrollment-ux-design.md).

**Goal:** Make founder-credential enrollment completable from the existing maez-web UI, with honest receipts and a verified server-side-only token boundary, so the owner can take the `s7_founder_webauthn_credentials` table from `0 → 1` with a physical key-tap.

**Architecture (verified 2026-06-28):** The flow already exists in `skills/web_interface.py` — front-end JS (`registerCredential`, `normalizeCreationOptions`, `encodeCredentialResponse`) calling the public proxy `/api/v1/s7/webauthn/...`; the server-side proxy `_s7_cockpit_proxy_to_daemon` injects `X-Maez-S7-Internal-Channel` from `S7_INTERNAL_CHANNEL_TOKEN` and forwards to daemon `/internal/...`. Ceremony flag (`S7_LIVE_WEBAUTHN_CEREMONY=1`) and token are live in the daemon. The likely stall cause is the **expired bootstrap intent** (2026-06-13), not missing code.

**Tech Stack:** Python 3 + Flask (maez-web in `skills/web_interface.py`), embedded HTML/JS, WebAuthn (`navigator.credentials.create`). Test runner: **unittest, NOT pytest** — `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`.

**Covenant rails:** no change to the daemon routes, ceremony service, verifier, store, flag, or channel-trust check; the internal token stays server-side only (the hard test guards this); no new authority semantics; the only state change in the whole slice is the owner's own `0→1` credential via key-tap.

---

### Task 0: Verify the existing flow end-to-end + find the real gap (no production code)

- [ ] **Step 1: Confirm the conversion helpers are correct**

```
cd /home/rohit/maez
grep -nA20 "function normalizeCreationOptions" skills/web_interface.py
grep -nA20 "function encodeCredentialResponse" skills/web_interface.py
```
Confirm `normalizeCreationOptions` decodes base64url `challenge` + `user.id` (and any `excludeCredentials[].id`) to `ArrayBuffer`/`Uint8Array` for `create()`, and `encodeCredentialResponse` re-encodes `rawId` + `response.{clientDataJSON,attestationObject}` to the base64url JSON `register_finish` expects. Record any mismatch against the actual `register_finish` contract (read `S7LocalWebAuthnCeremonyService.register_finish`). If a helper is wrong, that becomes a fix task; if correct, no code change there.

- [ ] **Step 2: Confirm the proxy process actually has the token**

```
# the daemon has it; the maez-web/proxy process is what needs it. Confirm which process serves /api/v1 and that S7_INTERNAL_CHANNEL_TOKEN is in ITS env.
grep -nE "S7_INTERNAL_CHANNEL_TOKEN|_DAEMON_BASE|def _s7_cockpit_proxy_to_daemon" skills/web_interface.py | head
WEB_PID=$(systemctl --user show maez-web.service -p MainPID --value 2>/dev/null || true)
[ -n "$WEB_PID" ] && [ "$WEB_PID" != "0" ] && tr '\0' '\n' < "/proc/$WEB_PID/environ" | grep -E '^S7_INTERNAL_CHANNEL_TOKEN=' >/dev/null && echo "maez-web has S7_INTERNAL_CHANNEL_TOKEN"
```
Record: same process as the daemon, or separate? If separate, the proxy env must carry the token (note as an owner-runbook item, not a code change).

- [ ] **Step 3: Confirm the stall cause + enumerate receipt/status gaps**

Read the enrollment view's status rendering + error handling (around `loadStatus`, `appendLog`, `describeError`, the `register error` path). Record: (a) does `status` already distinguish *no-credential / enrolled / ceremony-disabled(503) / channel-untrusted(403) / intent-expired*? (b) are failures shown as a human receipt or raw JSON? (c) is there a readiness surface telling the owner *which* precondition is missing? List the concrete gaps (this is the only real build surface). Confirm the expired-intent hypothesis via the ceremony store (`s7_bootstrap_intents.expires_at` past, `consumed_at NULL`, `0` founder credentials).

---

### Task 1: The credential-boundary hard test (Codex must-fix)

**Files:** Test: `tests/test_s7_webauthn_enrollment_asset_boundary.py` (new)

- [ ] **Step 1: Write the failing test — assert on BROWSER-DELIVERED output, not the source file**

> **Critical (Codex watch-item):** `skills/web_interface.py` legitimately contains the token name in its *server-side* proxy code. Do NOT grep the source file. Fetch what the browser actually receives and assert the secret is absent there.

```python
import os, unittest
from unittest import mock

class S7EnrollmentAssetBoundaryTest(unittest.TestCase):
    def _client(self):
        from skills.web_interface import app  # the Flask maez-web app
        app.config.update(TESTING=True)
        return app.test_client()

    def test_browser_assets_never_expose_channel_token(self):
        token = "boundary-test-channel-secret"
        client = self._client()

        def fake_urlopen(req, timeout=None):
            class _Response:
                status = 200
                headers = {"Content-Type": "application/json"}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b'{"ok": true, "credential_count": 0}'

            return _Response()

        # Every browser-facing surface for enrollment: the page + the status JSON.
        # The test sets a sentinel token so the literal-secret assertion cannot pass
        # vacuously, and stubs urlopen so it never reaches the live daemon.
        with mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": token}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            surfaces = []
            page = client.get("/cockpit/s7-webauthn-proof")
            surfaces.append(page.get_data(as_text=True))
            status = client.get("/api/v1/s7/webauthn/status")
            surfaces.append(status.get_data(as_text=True))

        for body in surfaces:
            self.assertNotIn(token, body)                       # the literal secret
            self.assertNotIn("S7_INTERNAL_CHANNEL_TOKEN", body) # the env name
            self.assertNotIn("X-Maez-S7-Internal-Channel", body)# the header name
            # no client-side persistence of a channel token
            self.assertNotRegex(body, r"(localStorage|sessionStorage)\.[A-Za-z]*[Ii]tem\([^)]*[Cc]hannel")
```

- [ ] **Step 2: Run to verify it passes against the current code** — `... -m unittest tests.test_s7_webauthn_enrollment_asset_boundary -v`. This SHOULD pass already (the boundary is correctly built); the test pins it so future UI polish can't regress it. If it FAILS, that is a real leak — STOP and surface it. Adjust the page route per Task 0; do not weaken the assertions. The unit test must remain hermetic: no live-daemon call, no ambient-token dependency.

- [ ] **Step 3: Commit**

```bash
git add tests/test_s7_webauthn_enrollment_asset_boundary.py
git commit -m "test(s7): pin channel token never reaches browser-delivered enrollment assets"
```

---

### Task 2: Close the receipt/status/readiness gaps found in Task 0 (only if any)

**Files:** Modify: `skills/web_interface.py` (the embedded enrollment view only)

- [ ] **Step 1: For each gap from Task 0 §3, write a failing test then implement**

For each concrete gap (e.g., 503 rendered as raw JSON instead of "ceremony not enabled"; no distinct expired-intent message; no readiness line), add a focused test against the maez-web `test_client` asserting the rendered state, then implement the minimal view change. **UI/receipt text only — no route, proxy, service, store, flag, or authority change.** If Task 0 finds the view already renders each state clearly, this task is empty — record that and skip.

- [ ] **Step 2: Run the focused suite + the boundary test + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_s7_webauthn_enrollment_asset_boundary tests.test_cockpit_proxies_2026_05_05 tests.test_s7_1_daemon_internal_channel -v
/home/rohit/maez/.venv/bin/ruff check skills/web_interface.py tests/test_s7_webauthn_enrollment_asset_boundary.py
```
Expected: green; ruff clean; the existing proxy/channel tests still pass unchanged (proof nothing in the boundary moved).

- [ ] **Step 3: Commit**

```bash
git add skills/web_interface.py tests/
git commit -m "feat(s7): honest enrollment receipts + readiness states (UI only, no authority change)"
```

---

### Task 3: Owner ceremony runbook + handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-28-slice1-s7-webauthn-enrollment-ux-handoff.md`**

Record Task 0 findings (helper correctness, proxy-token location, the stall cause, the gap list), the branch tip, the full test + ruff output, and the **owner ceremony runbook** — the steps only the owner can do:
```
1. (optional hygiene) rotate S7_INTERNAL_CHANNEL_TOKEN in daemon + proxy env, restart.
2. Mint a fresh bootstrap intent (the old one expired):
   python -m core.governance.s7_webauthn_bootstrap create --purpose register_primary --ttl-minutes 10
   -> note intent_id + token (one-time secret).
3. Open the maez-web enrollment view (`/cockpit/s7-webauthn-proof`); paste intent_id + token into the primary fields.
4. Click register(primary) -> the browser prompts -> TOUCH THE YUBIKEY.
5. Confirm the receipt shows enrolled + a credential_ref, and status flips to enrolled.
```
State the **witness**: `s7_founder_webauthn_credentials` goes `0 → 1` and `/api/v1/s7/webauthn/status` reports the credential, after a real key-tap. State plainly: NOT merged, NOT enrolled (enrollment is the owner's physical act), NO authority change.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-28-slice1-s7-webauthn-enrollment-ux-handoff.md
git commit -m "docs(s7): hand off slice 1 enrollment UX + owner ceremony runbook"
```
Hand back to Claude for covenant review (boundary test asserts on delivered assets not source; no route/proxy/service/store/flag/authority change; existing channel tests unchanged; scope stayed UI-only). Then the owner performs the ceremony and witnesses `0→1`.

---

## Self-Review

**Spec coverage:** completes/hardens the existing flow not a rebuild (Task 0 + Task 2 ✓); browser must call `/api/v1/...` with token server-side only (verified architecture + Task 1 boundary test ✓); the hard test asserts on **browser-delivered assets, not source** and is hermetic/non-vacuous (Task 1 §1 explicit ✓ — Codex watch-item); base64url↔ArrayBuffer conversion verified (Task 0 §1 ✓); honest receipts + readiness states (Task 2 ✓); narrow scope, no authority change (rails + every commit message ✓); witness = `0→1` after physical key-tap (Task 3 ✓).

**Placeholder scan:** the enrollment page route is pinned to the verified `/cockpit/s7-webauthn-proof` route; the exact gap list is an explicit Task 0 confirmation (the slice's discovery step), not a TBD.

**Type consistency:** the maez-web Flask `app` + `test_client` are the test surface throughout; `S7_INTERNAL_CHANNEL_TOKEN` / `X-Maez-S7-Internal-Channel` referenced by their verified names; no new symbols introduced in production code beyond optional receipt-rendering helpers.
