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
