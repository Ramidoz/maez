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

import datetime
import hmac
import os
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

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
