# Reddit Limb v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove Maez can authenticate to Rohit's Reddit account via browser consent and confirm its own identity (`/api/v1/me`), surfacing a content-free health tile — no password, no persistence, no ingestion, no egress.

**Architecture:** A substrate-side limb module (`core/information_limb/reddit_limb.py`) holds an in-memory session + pure OAuth helpers + the hardened-handoff handler. A one-shot owner-run ceremony (`scripts/reddit_connect.py`) does the browser auth-code flow on a loopback listener and hands the short-lived token to the running daemon over a loopback + shared-secret endpoint. The daemon wires that endpoint and a content-free body tile. Mirrors the existing Calendar limb + the S7 internal-channel auth pattern.

**Tech Stack:** Python 3.14, `requests` (HTTP), Flask (daemon's existing "maez-health" app), `hmac`/`secrets` (constant-time compare), `unittest` (test runner — NOT pytest), `unittest.mock` for HTTP.

**Spec:** `docs/superpowers/specs/2026-06-03-reddit-limb-v0-design.md`. **Branch:** `reddit-limb-v0`. **Lane:** Codex implements / Claude reviews.

**Test runner note:** This repo uses `unittest`, run as `.venv/bin/python -m unittest tests.<module> -v`. There is NO pytest. All commands below use that form.

---

## File Structure

- **Create `core/information_limb/reddit_limb.py`** — the whole substrate-side limb: constants, `RedditSession`, pure OAuth helpers (`build_authorize_url`, `exchange_code_for_token`, `fetch_identity`), the in-memory `RedditLimb` state holder (`set_session`/`clear_session`/`health`), and the hardened handoff (`handoff_trusted`, `handle_handoff`). No Flask import (keeps it unit-testable).
- **Modify `daemon/maez_daemon.py`** — add the `POST /internal/limb/reddit/session` Flask route (thin wrapper over `reddit_limb.handle_handoff`) and add the `reddit_limb` key to `_body_health`'s `maez_body.v0` map.
- **Create `scripts/reddit_connect.py`** — the owner-run ceremony (browser + loopback listener + token exchange + handoff POST).
- **Create `tests/test_reddit_limb.py`** — unit tests for the pure helpers + state holder.
- **Create `tests/test_reddit_limb_handoff.py`** — the auth-before-envelope + token-never-leaks endpoint-handler tests.
- **Create `tests/test_reddit_limb_covenant.py`** — the source-contract covenant guards (no egress/LLM imports, persists nothing).

---

## Task 1: Limb constants + `RedditSession` + `build_authorize_url`

**Files:**
- Create: `core/information_limb/reddit_limb.py`
- Test: `tests/test_reddit_limb.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reddit_limb.py
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import reddit_limb  # noqa: E402


class BuildAuthorizeUrlTests(unittest.TestCase):
    def test_authorize_url_has_required_readonly_params(self):
        url = reddit_limb.build_authorize_url(
            client_id="CID",
            redirect_uri="http://localhost:65010/reddit/callback",
            state="STATE123",
        )
        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.reddit.com")
        self.assertEqual(parsed.path, "/api/v1/authorize")
        self.assertEqual(q["client_id"], ["CID"])
        self.assertEqual(q["response_type"], ["code"])
        self.assertEqual(q["state"], ["STATE123"])
        self.assertEqual(q["redirect_uri"], ["http://localhost:65010/reddit/callback"])
        self.assertEqual(q["duration"], ["temporary"])   # v0: no refresh token
        self.assertEqual(q["scope"], ["identity"])        # v0: identity-only

    def test_no_secret_in_authorize_url(self):
        url = reddit_limb.build_authorize_url(
            client_id="CID", redirect_uri="http://localhost:65010/reddit/callback", state="S",
        )
        self.assertNotIn("secret", url.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.information_limb.reddit_limb'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/information_limb/reddit_limb.py
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Reddit Limb v0 — read-only, identity-only OAuth smoke.

First Personal Data Limb. Installed-app OAuth (authorization-code, loopback,
duration=temporary), identity scope only, in-memory token, one /api/v1/me call,
content-free health. No password, no persistence, no ingestion, no egress.
Spec: docs/superpowers/specs/2026-06-03-reddit-limb-v0-design.md
"""

from __future__ import annotations

from urllib.parse import urlencode

# v0 is identity-only. history/read are explicitly deferred to v0.1 behind a
# separate acceptance gate — do NOT add them here.
_V0_SCOPES = ("identity",)
_AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    """Build the reddit.com installed-app authorize URL (read-only, temporary)."""
    params = {
        "client_id": client_id,
        "response_type": "code",
        "state": state,
        "redirect_uri": redirect_uri,
        "duration": "temporary",          # no refresh token in v0
        "scope": " ".join(_V0_SCOPES),
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/information_limb/reddit_limb.py tests/test_reddit_limb.py
git commit -m "feat(reddit-limb): build_authorize_url (identity-only, temporary)"
```

---

## Task 2: `RedditSession` + `exchange_code_for_token`

**Files:**
- Modify: `core/information_limb/reddit_limb.py`
- Test: `tests/test_reddit_limb.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_reddit_limb.py`, before `if __name__`)

```python
from unittest import mock  # add at top with other imports


class ExchangeCodeTests(unittest.TestCase):
    def _fake_response(self, status=200, payload=None):
        resp = mock.Mock()
        resp.status_code = status
        resp.json.return_value = payload or {
            "access_token": "TOK", "token_type": "bearer",
            "expires_in": 3600, "scope": "identity",
        }
        return resp

    def test_exchange_uses_basic_auth_empty_password_and_grant(self):
        with mock.patch.object(reddit_limb.requests, "post") as post:
            post.return_value = self._fake_response()
            session = reddit_limb.exchange_code_for_token(
                client_id="CID", code="CODE",
                redirect_uri="http://localhost:65010/reddit/callback",
            )
        # installed app: HTTP Basic with client_id and EMPTY password
        _, kwargs = post.call_args
        self.assertEqual(kwargs["auth"], ("CID", ""))
        self.assertEqual(kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(kwargs["data"]["code"], "CODE")
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertEqual(session.access_token, "TOK")
        self.assertEqual(session.scopes, ["identity"])
        self.assertGreater(session.expires_at, session.obtained_at)

    def test_exchange_raises_on_non_200(self):
        with mock.patch.object(reddit_limb.requests, "post") as post:
            post.return_value = self._fake_response(status=401, payload={"error": "x"})
            with self.assertRaises(reddit_limb.RedditAuthError):
                reddit_limb.exchange_code_for_token(
                    client_id="CID", code="BAD",
                    redirect_uri="http://localhost:65010/reddit/callback",
                )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb.ExchangeCodeTests -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'requests'` / `exchange_code_for_token`.

- [ ] **Step 3: Write minimal implementation** (add to `reddit_limb.py`)

```python
import time
from dataclasses import dataclass, field

import requests

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_USER_AGENT = "maez-personal-limb/0.0 (local, read-only)"
_HTTP_TIMEOUT = 10  # seconds


class RedditLimbError(Exception):
    """Base for limb errors."""


class RedditAuthError(RedditLimbError):
    """Token exchange / auth failure."""


@dataclass
class RedditSession:
    access_token: str
    scopes: list[str]
    obtained_at: float
    expires_at: float

    def is_expired(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


def exchange_code_for_token(*, client_id: str, code: str, redirect_uri: str) -> RedditSession:
    """Exchange an authorization code for a short-lived access token.

    Installed apps are public clients: HTTP Basic auth with the client_id as
    username and an EMPTY password (no client secret exists).
    """
    resp = requests.post(
        _TOKEN_URL,
        auth=(client_id, ""),
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        headers={"User-Agent": _USER_AGENT},
        timeout=_HTTP_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RedditAuthError(f"token exchange failed: HTTP {resp.status_code}")
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise RedditAuthError("token exchange returned no access_token")
    now = time.time()
    scope = body.get("scope", "identity")
    return RedditSession(
        access_token=token,
        scopes=scope.split() if isinstance(scope, str) else list(scope),
        obtained_at=now,
        expires_at=now + float(body.get("expires_in", 3600)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/information_limb/reddit_limb.py tests/test_reddit_limb.py
git commit -m "feat(reddit-limb): exchange_code_for_token (installed-app Basic auth)"
```

---

## Task 3: `fetch_identity` → state mapping, body discarded

**Files:**
- Modify: `core/information_limb/reddit_limb.py`
- Test: `tests/test_reddit_limb.py`

- [ ] **Step 1: Write the failing test** (append)

```python
class FetchIdentityTests(unittest.TestCase):
    def _session(self):
        now = 1000.0
        return reddit_limb.RedditSession(
            access_token="TOK", scopes=["identity"], obtained_at=now, expires_at=now + 3600
        )

    def _patch_get(self, status):
        resp = mock.Mock()
        resp.status_code = status
        resp.json.return_value = {"name": "rohit_secret_username", "id": "abc"}
        return mock.patch.object(reddit_limb.requests, "get", return_value=resp)

    def test_200_maps_to_available_and_returns_no_identity(self):
        with self._patch_get(200):
            state = reddit_limb.fetch_identity(self._session())
        self.assertEqual(state, "available")
        # fetch_identity returns ONLY a state string — never identity fields
        self.assertNotIn("rohit_secret_username", str(state))

    def test_status_to_state_mapping(self):
        cases = {401: "auth_error", 403: "revoked", 429: "rate_limited"}
        for status, expected in cases.items():
            with self._patch_get(status):
                self.assertEqual(reddit_limb.fetch_identity(self._session()), expected)

    def test_network_error_maps_to_unreachable(self):
        with mock.patch.object(reddit_limb.requests, "get",
                               side_effect=reddit_limb.requests.RequestException("boom")):
            self.assertEqual(reddit_limb.fetch_identity(self._session()), "unreachable")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb.FetchIdentityTests -v`
Expected: FAIL — `fetch_identity` not defined.

- [ ] **Step 3: Write minimal implementation** (add to `reddit_limb.py`)

```python
_ME_URL = "https://oauth.reddit.com/api/v1/me"

# tile states (content-free)
STATE_NEEDS_AUTH = "needs_auth"
STATE_AVAILABLE = "available"
STATE_AUTH_ERROR = "auth_error"
STATE_REVOKED = "revoked"
STATE_RATE_LIMITED = "rate_limited"
STATE_UNREACHABLE = "unreachable"


def fetch_identity(session: RedditSession) -> str:
    """GET /api/v1/me. Returns ONLY a tile-state string; discards the body
    (never returns or stores the username/id). Fail-closed: any error → a
    non-available state, never raises into the caller."""
    try:
        resp = requests.get(
            _ME_URL,
            headers={"Authorization": f"bearer {session.access_token}", "User-Agent": _USER_AGENT},
            timeout=_HTTP_TIMEOUT,
        )
    except requests.RequestException:
        return STATE_UNREACHABLE
    if resp.status_code == 200:
        return STATE_AVAILABLE          # body intentionally NOT read
    if resp.status_code == 401:
        return STATE_AUTH_ERROR
    if resp.status_code == 403:
        return STATE_REVOKED
    if resp.status_code == 429:
        return STATE_RATE_LIMITED
    return STATE_AUTH_ERROR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add core/information_limb/reddit_limb.py tests/test_reddit_limb.py
git commit -m "feat(reddit-limb): fetch_identity state mapping (body discarded)"
```

---

## Task 4: `RedditLimb` in-memory state holder + content-free `health()`

**Files:**
- Modify: `core/information_limb/reddit_limb.py`
- Test: `tests/test_reddit_limb.py`

- [ ] **Step 1: Write the failing test** (append)

```python
class RedditLimbStateTests(unittest.TestCase):
    def test_fresh_limb_is_needs_auth_and_content_free(self):
        limb = reddit_limb.RedditLimb()
        h = limb.health()
        self.assertEqual(h["state"], "needs_auth")
        self.assertIsNone(h["last_success_at"])
        # content-free: keys are a fixed allowlist, no token/identity fields
        self.assertEqual(set(h.keys()), {"state", "last_success_at", "scopes", "expires_in_bucket"})

    def test_set_session_then_available_records_no_token(self):
        limb = reddit_limb.RedditLimb()
        now = 2000.0
        limb.set_session(reddit_limb.RedditSession("SECRET_TOK", ["identity"], now, now + 3600))
        limb.mark_state("available", now=now)
        h = limb.health(now=now)
        self.assertEqual(h["state"], "available")
        self.assertIsNotNone(h["last_success_at"])
        self.assertEqual(h["scopes"], ["identity"])
        # the token must never appear anywhere in the health output
        self.assertNotIn("SECRET_TOK", repr(h))

    def test_expired_session_reports_needs_auth(self):
        limb = reddit_limb.RedditLimb()
        now = 3000.0
        limb.set_session(reddit_limb.RedditSession("T", ["identity"], now, now + 10))
        self.assertEqual(limb.health(now=now + 999)["state"], "needs_auth")

    def test_clear_session_returns_to_needs_auth(self):
        limb = reddit_limb.RedditLimb()
        now = 4000.0
        limb.set_session(reddit_limb.RedditSession("T", ["identity"], now, now + 3600))
        limb.clear_session()
        self.assertEqual(limb.health(now=now)["state"], "needs_auth")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb.RedditLimbStateTests -v`
Expected: FAIL — `RedditLimb` not defined.

- [ ] **Step 3: Write minimal implementation** (add to `reddit_limb.py`)

```python
def _expires_bucket(session: RedditSession | None, now: float) -> str:
    if session is None:
        return "none"
    remaining = session.expires_at - now
    if remaining <= 0:
        return "expired"
    if remaining < 1800:
        return "<30m"
    return "fresh"


class RedditLimb:
    """In-memory session + content-free health. One instance per daemon.
    The session (token) lives only in process memory — never serialized."""

    def __init__(self) -> None:
        self._session: RedditSession | None = None
        self._state: str = STATE_NEEDS_AUTH
        self._last_success_at: str | None = None

    def set_session(self, session: RedditSession) -> None:
        self._session = session

    def clear_session(self) -> None:
        self._session = None
        self._state = STATE_NEEDS_AUTH

    def mark_state(self, state: str, *, now: float | None = None) -> None:
        self._state = state
        if state == STATE_AVAILABLE:
            import datetime
            ts = now if now is not None else time.time()
            self._last_success_at = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc
            ).isoformat()

    def effective_state(self, *, now: float | None = None) -> str:
        n = now if now is not None else time.time()
        if self._session is None or self._session.is_expired(now=n):
            return STATE_NEEDS_AUTH
        return self._state

    def health(self, *, now: float | None = None) -> dict:
        n = now if now is not None else time.time()
        return {
            "state": self.effective_state(now=n),
            "last_success_at": self._last_success_at,
            "scopes": list(self._session.scopes) if self._session else [],
            "expires_in_bucket": _expires_bucket(self._session, n),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add core/information_limb/reddit_limb.py tests/test_reddit_limb.py
git commit -m "feat(reddit-limb): RedditLimb in-memory state + content-free health"
```

---

## Task 5: Hardened handoff — `handoff_trusted` + `handle_handoff` (auth before envelope)

**Files:**
- Modify: `core/information_limb/reddit_limb.py`
- Test: `tests/test_reddit_limb_handoff.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reddit_limb_handoff.py
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import reddit_limb  # noqa: E402

SENTINEL = "SENTINEL_ACCESS_TOKEN_DO_NOT_LEAK"


class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k, default)


class HandoffAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)

    def test_missing_secret_is_untrusted(self):
        self.assertFalse(reddit_limb.handoff_trusted(_Headers()))

    def test_wrong_secret_is_untrusted(self):
        self.assertFalse(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"})))

    def test_origin_header_is_untrusted_even_with_right_secret(self):
        self.assertFalse(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET", "Origin": "http://evil"})))

    def test_right_secret_no_origin_is_trusted(self):
        self.assertTrue(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"})))

    def test_auth_before_envelope_body_loader_never_called_on_bad_secret(self):
        """THE load-bearing test: a bad secret returns 403 and the body
        (which carries the live token) is NEVER read."""
        limb = reddit_limb.RedditLimb()
        body_loader = mock.Mock(return_value={"access_token": SENTINEL,
                                              "scopes": ["identity"], "expires_in": 3600})
        result, status = reddit_limb.handle_handoff(
            headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"}),
            body_loader=body_loader, limb=limb,
        )
        self.assertEqual(status, 403)
        body_loader.assert_not_called()                  # envelope never opened
        self.assertNotIn(SENTINEL, repr(result))         # token nowhere in response

    def test_valid_handoff_sets_session_and_fetches(self):
        limb = reddit_limb.RedditLimb()
        body_loader = mock.Mock(return_value={"access_token": SENTINEL,
                                              "scopes": ["identity"], "expires_in": 3600})
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            result, status = reddit_limb.handle_handoff(
                headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=body_loader, limb=limb,
            )
        self.assertEqual(status, 200)
        body_loader.assert_called_once()
        self.assertEqual(result["state"], "available")
        self.assertNotIn(SENTINEL, repr(result))         # token never echoed back


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb_handoff -v`
Expected: FAIL — `handoff_trusted` / `handle_handoff` not defined.

- [ ] **Step 3: Write minimal implementation** (add to `reddit_limb.py`)

```python
import hmac
import os

REDDIT_HANDOFF_HEADER = "X-Maez-Reddit-Handoff"
REDDIT_HANDOFF_TOKEN_ENV = "MAEZ_REDDIT_HANDOFF_TOKEN"


def _secrets_compare(expected: str, presented: str) -> bool:
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))


def handoff_trusted(headers) -> bool:
    """True only for a loopback caller presenting the dedicated handoff secret.
    Mirrors daemon._s7_internal_channel_trusted but with the Reddit-specific,
    isolated secret. A browser (any Origin header) is rejected."""
    expected = os.environ.get(REDDIT_HANDOFF_TOKEN_ENV, "")
    presented = headers.get(REDDIT_HANDOFF_HEADER, "")
    if not expected or not presented:
        return False
    if headers.get("Origin"):
        return False
    return _secrets_compare(expected, presented)


def handle_handoff(*, headers, body_loader, limb: "RedditLimb") -> tuple[dict, int]:
    """Auth-before-envelope: verify the secret FIRST; only call body_loader()
    (which reads/parses the token-bearing body) once trusted. Returns
    (content-free tile dict, http_status). Never echoes the token."""
    if not handoff_trusted(headers):
        return {"ok": False, "error": "reddit_handoff_untrusted"}, 403
    body = body_loader() or {}
    token = body.get("access_token")
    if not token:
        return {"ok": False, "error": "missing_access_token"}, 400
    now = time.time()
    limb.set_session(RedditSession(
        access_token=token,
        scopes=list(body.get("scopes") or ["identity"]),
        obtained_at=now,
        expires_at=now + float(body.get("expires_in", 3600)),
    ))
    state = fetch_identity(limb._session)
    limb.mark_state(state, now=now)
    tile = limb.health(now=now)
    tile["ok"] = state == STATE_AVAILABLE
    return tile, (200 if state == STATE_AVAILABLE else 502)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb_handoff -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add core/information_limb/reddit_limb.py tests/test_reddit_limb_handoff.py
git commit -m "feat(reddit-limb): hardened handoff — auth before envelope, token never echoed"
```

---

## Task 6: Covenant guard tests (token-never-leaks, no-egress/LLM, persists-nothing)

**Files:**
- Test: `tests/test_reddit_limb_covenant.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reddit_limb_covenant.py
import ast
import logging
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import reddit_limb  # noqa: E402

_LIMB_SRC = (_REPO / "core" / "information_limb" / "reddit_limb.py").read_text(encoding="utf-8")
SENTINEL = "SENTINEL_TOKEN_LEAK_CANARY"


class TokenNeverLeaksTests(unittest.TestCase):
    def test_token_absent_from_logs_and_health(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)
        limb = reddit_limb.RedditLimb()
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger("maez").debug("driving handoff")
            with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
                tile, _ = reddit_limb.handle_handoff(
                    headers={reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"},
                    body_loader=lambda: {"access_token": SENTINEL, "scopes": ["identity"]},
                    limb=limb,
                )
        blob = repr(tile) + "\n".join(logs.output)
        self.assertNotIn(SENTINEL, blob)


class NoEgressNoLLMTests(unittest.TestCase):
    def test_limb_imports_no_cloud_egress_or_llm_modules(self):
        tree = ast.parse(_LIMB_SRC)
        banned = ("llm_client", "subscription_proxy", "egress.gate", "cloud_redactor",
                  "claude_tier", "openai", "anthropic")
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for mod in imported:
            for b in banned:
                self.assertNotIn(b, mod, f"reddit_limb must not import {mod}")


class PersistsNothingTests(unittest.TestCase):
    def test_no_durable_writes(self):
        # no sqlite, no file-open-for-write in the limb — session is memory-only
        self.assertNotIn("sqlite3", _LIMB_SRC)
        tree = ast.parse(_LIMB_SRC)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
                modes = [a.value for a in node.args[1:2] if isinstance(a, ast.Constant)]
                for m in modes:
                    self.assertNotIn("w", str(m), "reddit_limb must not open files for writing")
                    self.assertNotIn("a", str(m), "reddit_limb must not append to files")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails (then passes — these assert existing properties)**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb_covenant -v`
Expected: PASS if Tasks 1–5 were implemented as written. If any FAILS, the limb violated a covenant rail — fix the limb, not the test.

- [ ] **Step 3: (only if a guard failed) fix the limb**

If `NoEgressNoLLMTests` fails: remove the offending import. If `PersistsNothingTests` fails: remove the durable write. If `TokenNeverLeaksTests` fails: find where the token is logged/returned and redact it.

- [ ] **Step 4: Run again**

Run: `.venv/bin/python -m unittest tests.test_reddit_limb_covenant -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_reddit_limb_covenant.py
git commit -m "test(reddit-limb): covenant guards — token-never-leaks, no-egress/LLM, persists-nothing"
```

---

## Task 7: Daemon route `POST /internal/limb/reddit/session` + body tile

**Files:**
- Modify: `daemon/maez_daemon.py` (Flask routes near the `/internal/s7/*` block ~line 9322; `_body_health` ~line 2887)

- [ ] **Step 1: Add the module-level limb singleton + route**

Near the top of `daemon/maez_daemon.py` (with other module imports), add:

```python
from core.information_limb import reddit_limb as _reddit_limb_mod

_REDDIT_LIMB = _reddit_limb_mod.RedditLimb()
```

**Loopback note:** the "maez-health" Flask app is already loopback-bound — `daemon/maez_daemon.py:9860` does `make_server("127.0.0.1", HEALTH_PORT, app)`. So spec §4.3's "reject non-loopback peer" is satisfied by the bind (same as the `/internal/s7/*` routes); `handoff_trusted` adds the dedicated-secret + no-`Origin` checks on top. Do not add a redundant peer-IP check.

In the Flask app setup block (where `@app.route("/internal/s7/webauthn/status"...)` lives, after the s7 routes), add:

```python
        @app.route("/internal/limb/reddit/session", methods=["POST"])
        def reddit_limb_session():
            # auth-before-envelope: handle_handoff checks the secret BEFORE
            # body_loader() is ever called, so the token-bearing JSON body is
            # not read on an auth failure.
            tile, status = _reddit_limb_mod.handle_handoff(
                headers=request.headers,
                body_loader=lambda: request.get_json(silent=True) or {},
                limb=_REDDIT_LIMB,
            )
            return jsonify(tile), status
```

- [ ] **Step 2: Wire the tile into `_body_health`**

In `_body_health` (the `return { "schema_version": "maez_body.v0", ... }` dict ~line 2905), add a key alongside `eyes`/`memory`:

```python
            "reddit_limb": _REDDIT_LIMB.health(),
```

- [ ] **Step 3: Verify the daemon imports + compiles**

Run: `.venv/bin/python -m py_compile daemon/maez_daemon.py && echo OK`
Expected: `OK`.

- [ ] **Step 4: Smoke-test the route in isolation with a tiny Flask client test**

Create `tests/test_reddit_daemon_route.py`:

```python
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from flask import Flask, request, jsonify  # noqa: E402
from core.information_limb import reddit_limb  # noqa: E402

SENTINEL = "ROUTE_SENTINEL_TOKEN"


def _build_app(limb):
    app = Flask("test")

    @app.route("/internal/limb/reddit/session", methods=["POST"])
    def session():
        tile, status = reddit_limb.handle_handoff(
            headers=request.headers,
            body_loader=lambda: request.get_json(silent=True) or {},
            limb=limb,
        )
        return jsonify(tile), status

    return app


class RedditDaemonRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)
        self.limb = reddit_limb.RedditLimb()
        self.client = _build_app(self.limb).test_client()

    def test_bad_secret_403_token_not_processed(self):
        r = self.client.post("/internal/limb/reddit/session",
                             headers={reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"},
                             json={"access_token": SENTINEL, "scopes": ["identity"]})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.limb.health()["state"], "needs_auth")  # session never set
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))

    def test_valid_secret_sets_session(self):
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            r = self.client.post("/internal/limb/reddit/session",
                                 headers={reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"},
                                 json={"access_token": SENTINEL, "scopes": ["identity"],
                                       "expires_in": 3600})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.limb.health()["state"], "available")
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
```

Run: `.venv/bin/python -m unittest tests.test_reddit_daemon_route -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_reddit_daemon_route.py
git commit -m "feat(reddit-limb): daemon handoff route + body tile (auth before envelope)"
```

---

## Task 8: The one-shot ceremony `scripts/reddit_connect.py`

**Files:**
- Create: `scripts/reddit_connect.py`

This is owner-run and does real browser/network I/O, so its witness is the manual integration smoke (Task 9). Keep it thin — it reuses `reddit_limb` for every pure step.

- [ ] **Step 1: Implement the ceremony**

```python
# scripts/reddit_connect.py
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""One-shot Reddit connect ceremony (owner-run).

Browser installed-app OAuth on a loopback listener; hands the short-lived token
to the running daemon over the loopback + shared-secret handoff endpoint. The
token lives only in this process's memory and the daemon's — never on disk.

Prereq: a Reddit "installed app" (reddit.com/prefs/apps) with redirect
http://localhost:65010/reddit/callback. Set in config/.env (or the daemon env):
  MAEZ_REDDIT_CLIENT_ID=<your installed-app client_id>
  MAEZ_REDDIT_HANDOFF_TOKEN=<shared secret, same value the daemon has>

Run:  .venv/bin/python scripts/reddit_connect.py
"""

from __future__ import annotations

import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import requests  # noqa: E402
from core.information_limb import reddit_limb  # noqa: E402

REDIRECT_HOST, REDIRECT_PORT = "localhost", 65010
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/reddit/callback"
DAEMON_HANDOFF_URL = "http://127.0.0.1:11435/internal/limb/reddit/session"


def _read_env() -> tuple[str, str]:
    cid = os.environ.get("MAEZ_REDDIT_CLIENT_ID", "").strip()
    handoff = os.environ.get("MAEZ_REDDIT_HANDOFF_TOKEN", "").strip()
    if not cid:
        sys.exit("MAEZ_REDDIT_CLIENT_ID not set (create an installed app at reddit.com/prefs/apps).")
    if not handoff:
        sys.exit("MAEZ_REDDIT_HANDOFF_TOKEN not set (must match the daemon's value).")
    return cid, handoff


def _capture_code(expected_state: str) -> str:
    holder: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [None])[0] == expected_state and "code" in q:
                holder["code"] = q["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Reddit connected. You can close this tab.")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"state mismatch or no code")

        def log_message(self, *a):  # silence
            return

    srv = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
    t = threading.Thread(target=srv.handle_request)  # serve exactly one request
    t.start()
    t.join(timeout=300)
    srv.server_close()
    if "code" not in holder:
        sys.exit("no authorization code received (timeout or state mismatch).")
    return holder["code"]


def main() -> int:
    client_id, handoff = _read_env()
    state = secrets.token_urlsafe(24)
    url = reddit_limb.build_authorize_url(
        client_id=client_id, redirect_uri=REDIRECT_URI, state=state)
    print("Opening your browser to consent at reddit.com ...")
    print(url)
    webbrowser.open(url)
    code = _capture_code(state)
    session = reddit_limb.exchange_code_for_token(
        client_id=client_id, code=code, redirect_uri=REDIRECT_URI)
    resp = requests.post(
        DAEMON_HANDOFF_URL,
        headers={reddit_limb.REDDIT_HANDOFF_HEADER: handoff},
        json={"access_token": session.access_token,
              "scopes": session.scopes,
              "expires_in": int(session.expires_at - session.obtained_at)},
        timeout=15,
    )
    # never print the token; print only the content-free tile the daemon returns
    print(f"daemon handoff -> HTTP {resp.status_code}: {resp.json()}")
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify it compiles**

Run: `.venv/bin/python -m py_compile scripts/reddit_connect.py && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add scripts/reddit_connect.py
git commit -m "feat(reddit-limb): one-shot connect ceremony (browser OAuth -> loopback handoff)"
```

---

## Task 9: Full suite + the manual integration smoke (owner-run witness)

**Files:** none (verification + docs).

- [ ] **Step 1: Run all Reddit-limb tests**

Run:
```bash
.venv/bin/python -m unittest tests.test_reddit_limb tests.test_reddit_limb_handoff \
  tests.test_reddit_limb_covenant tests.test_reddit_daemon_route -v
```
Expected: all PASS.

- [ ] **Step 2: ruff + the existing leak guard (we added a new module)**

Run:
```bash
.venv/bin/ruff check core/information_limb/reddit_limb.py scripts/reddit_connect.py daemon/maez_daemon.py tests/test_reddit_limb*.py tests/test_reddit_daemon_route.py
.venv/bin/python -m unittest tests.test_no_bare_sqlite_connect
```
Expected: ruff clean; sqlite guards still green (the limb opens no sqlite).

- [ ] **Step 3: Confirm no full-suite regression** (the lesson from the sqlite arc — run the WHOLE suite, not just our modules)

Run: `.venv/bin/python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: no NEW failures vs the known pre-existing/environmental set (live-judge, web-search inventory, envelope-wiring, shim-smoke, cockpit-needs-daemon).

- [ ] **Step 4: Provision the secrets (owner, one-time)**

Document for Rohit:
1. Create an **installed app** at https://www.reddit.com/prefs/apps (redirect `http://localhost:65010/reddit/callback`); copy the `client_id`.
2. Add to the daemon env (where other `MAEZ_*` secrets live) AND `config/.env`:
   ```
   MAEZ_REDDIT_CLIENT_ID=<client_id>
   MAEZ_REDDIT_HANDOFF_TOKEN=<run: python -c "import secrets;print(secrets.token_urlsafe(32))">
   ```
3. Restart the daemon so it reads `MAEZ_REDDIT_HANDOFF_TOKEN` (deliberate, owner-timed).

- [ ] **Step 5: Manual integration smoke (the v0 witness)**

```bash
.venv/bin/python scripts/reddit_connect.py
```
Expected: browser opens → Rohit consents → terminal prints `HTTP 200` + a tile with `state=available`. Then:
- `curl -s http://127.0.0.1:11435/health | python3 -m json.tool | grep -A6 reddit_limb` → `state: available`, `last_success_at` set, `scopes: ["identity"]`.
- Restart the daemon → the same tile shows `state: needs_auth`.
- `journalctl --user -u maez.service --since "5 min ago" | grep -i <the access token>` → **empty** (token never logged).

- [ ] **Step 6: Hand to Claude for cross-lane review, then finish the branch**

Per the lane split (Codex implements / Claude reviews): Claude verifies the covenant guards have teeth (mutation: break the auth-before-envelope ordering → the handoff test must go RED), the token-never-leaks sentinel, and that the daemon route wiring matches the tested handler. Then `finishing-a-development-branch` → merge to main locally (no push, no restart unless owner says).

---

## Acceptance (from spec §10)

v0 passes when: the 4 covenant guard tests + all unit/route tests are green; the manual smoke shows `available` then `needs_auth` after restart; and a log grep for the token is empty. **v0.1** (adding `history`/`read` + one content fetch) is a separate slice behind a separate gate — not this plan.
