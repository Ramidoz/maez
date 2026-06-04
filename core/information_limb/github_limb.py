# core/information_limb/github_limb.py
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb v0 — read-only, identity-only OAuth device-flow smoke.

First WORKING Personal Data Limb (Reddit limb stays dormant — Reddit gated app
creation). OAuth App device flow: client_id only, NO client_secret. Scope
read:user only, in-memory token, one GET /user call, content-free health. No
password, no client secret, no persistence, no ingestion, no egress.
Spec: docs/superpowers/specs/2026-06-03-github-limb-v0-design.md

The GithubLimb state holder + hardened handoff + content-free health mirror the
reviewed reddit_limb.py byte-for-byte (renamed); only the device-flow auth
helpers (request_device_code / poll_for_token) and the GitHub endpoints differ.
"""

from __future__ import annotations

import datetime
import hmac
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

# v0 is identity-only. The read:user scope is read-only profile access — the
# GitHub analog of "prove this is the owner's account". Broader scopes (repo,
# user:email-write, etc.) are deferred to a later slice behind a separate gate.
_V0_SCOPES = ("read:user",)
_DEVICE_CODE_URL = "https://github.com/login/device/code"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_USER_AGENT = "maez-personal-limb/0.0 (local, read-only)"
_HTTP_TIMEOUT = 10  # seconds


class GithubLimbError(Exception):
    """Base for limb errors."""


class GithubAuthError(GithubLimbError):
    """Device-flow / token failure."""


@dataclass
class GithubSession:
    access_token: str
    scopes: list[str]
    obtained_at: float
    expires_at: float

    def is_expired(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


# ── device flow (ceremony-side helpers; no client secret) ─────────────


@dataclass
class DeviceCodeGrant:
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int


def request_device_code(*, client_id: str) -> DeviceCodeGrant:
    """Start the device flow. Returns the user_code the owner types at
    github.com/login/device plus the device_code we poll with."""
    resp = requests.post(
        _DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": " ".join(_V0_SCOPES)},
        headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
        timeout=_HTTP_TIMEOUT,
    )
    if resp.status_code != 200:
        raise GithubAuthError(f"device-code request failed: HTTP {resp.status_code}")
    body = resp.json()
    try:
        return DeviceCodeGrant(
            device_code=body["device_code"],
            user_code=body["user_code"],
            verification_uri=body.get("verification_uri", "https://github.com/login/device"),
            interval=int(body.get("interval", 5)),
            expires_in=int(body.get("expires_in", 900)),
        )
    except (KeyError, TypeError) as exc:
        raise GithubAuthError("device-code response missing fields") from exc


def poll_for_token(
    *,
    client_id: str,
    grant: DeviceCodeGrant,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> GithubSession:
    """Poll the token endpoint until the owner authorizes at github.com/login/
    device, or the device code expires. Handles authorization_pending / slow_down
    per the device-flow spec. `sleep`/`now` are injectable for tests."""
    interval = float(grant.interval)
    deadline = now() + float(grant.expires_in)
    while now() < deadline:
        sleep(interval)
        resp = requests.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "device_code": grant.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json", "User-Agent": _USER_AGENT},
            timeout=_HTTP_TIMEOUT,
        )
        body = resp.json() if resp.content else {}
        token = body.get("access_token")
        if token:
            # Fail closed on scope: GitHub's device-flow token response always
            # includes `scope`. A missing/empty/broader scope is abnormal and is
            # NOT identity proof — abort rather than fabricate ["read:user"].
            scope = body.get("scope")
            scopes = [s for s in (scope or "").replace(",", " ").split() if s]
            if set(scopes) != {"read:user"}:
                raise GithubAuthError(
                    f"unexpected token scope {scope!r}; v0 requires exactly read:user")
            t = time.time()
            # OAuth-App device-flow user tokens do not expire in v0 — use a long
            # horizon; the limb is in-memory only so a restart re-auths anyway.
            return GithubSession(access_token=token, scopes=scopes,
                                 obtained_at=t, expires_at=t + 365 * 24 * 3600)
        err = body.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval = float(body.get("interval", interval + 5))
            continue
        raise GithubAuthError(f"device-flow failed: {err or 'unknown'}")
    raise GithubAuthError("device code expired before authorization")


# ── identity read (substrate-side) ────────────────────────────────────

# tile states (content-free)
STATE_NEEDS_AUTH = "needs_auth"
STATE_AVAILABLE = "available"
STATE_AUTH_ERROR = "auth_error"
STATE_REVOKED = "revoked"
STATE_RATE_LIMITED = "rate_limited"
STATE_UNREACHABLE = "unreachable"


def fetch_identity(session: GithubSession) -> str:
    """GET /user. Returns ONLY a tile-state string; discards the body (never
    returns or stores the login/id). Fail-closed: any error → a non-available
    state, never raises into the caller."""
    try:
        resp = requests.get(
            _USER_URL,
            headers={
                "Authorization": f"Bearer {session.access_token}",
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
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


def fetch_repo_count(session: GithubSession) -> int:
    """GET /user; return ONLY public_repos.

    GitHub v1 ingests one minimized fact. This boundary discards the provider
    body after extracting that integer; login/id/email/repo names never cross
    into the v1 orchestrator.
    """
    try:
        resp = requests.get(
            _USER_URL,
            headers={
                "Authorization": f"Bearer {session.access_token}",
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
            timeout=_HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GithubAuthError("GitHub /user unreachable") from exc
    if resp.status_code != 200:
        raise GithubAuthError(f"GitHub /user HTTP {resp.status_code}")
    count = resp.json().get("public_repos")
    if type(count) is not int or count < 0:
        raise GithubAuthError("GitHub /user missing integer public_repos")
    return count


def _expires_bucket(session: GithubSession | None, now: float) -> str:
    if session is None:
        return "none"
    remaining = session.expires_at - now
    if remaining <= 0:
        return "expired"
    if remaining < 1800:
        return "<30m"
    return "fresh"


class GithubLimb:
    """In-memory session + content-free health. One instance per daemon.
    The session (token) lives only in process memory — never serialized."""

    def __init__(self) -> None:
        self._session: GithubSession | None = None
        self._state: str = STATE_NEEDS_AUTH
        self._last_success_at: str | None = None

    def set_session(self, session: GithubSession) -> None:
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


# ── hardened handoff (mirrors reddit_limb; dedicated GitHub secret) ────

GITHUB_HANDOFF_HEADER = "X-Maez-Github-Handoff"
GITHUB_HANDOFF_TOKEN_ENV = "MAEZ_GITHUB_HANDOFF_TOKEN"


def _secrets_compare(expected: str, presented: str) -> bool:
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))


def handoff_trusted(headers) -> bool:
    """True only for a loopback caller presenting the dedicated handoff secret.
    A browser (any Origin header) is rejected. Dedicated GitHub secret — NOT the
    Reddit secret, NOT the S7 channel, NOT Maez's operational MAEZ_GITHUB_TOKEN."""
    expected = os.environ.get(GITHUB_HANDOFF_TOKEN_ENV, "")
    presented = headers.get(GITHUB_HANDOFF_HEADER, "")
    if not expected or not presented:
        return False
    if headers.get("Origin"):
        return False
    return _secrets_compare(expected, presented)


def handle_handoff(*, headers, body_loader, limb: "GithubLimb") -> tuple[dict, int]:
    """Auth-before-envelope: verify the secret FIRST; only call body_loader()
    (which reads/parses the token-bearing body) once trusted. Returns
    (content-free tile dict, http_status). Never echoes the token."""
    if not handoff_trusted(headers):
        return {"ok": False, "error": "github_handoff_untrusted"}, 403
    body = body_loader() or {}
    token = body.get("access_token")
    if not token:
        return {"ok": False, "error": "missing_access_token"}, 400
    # v0 covenant pin — read:user only, enforced HERE at the trust boundary, not
    # just at the device-code request. FAIL CLOSED: the scope label must be
    # PRESENT and exactly read:user. A missing/empty scope is abnormal (GitHub
    # always returns scope in the token response), so it is rejected — never
    # treated as identity proof. Broader scopes are likewise rejected.
    scopes = body.get("scopes")
    if not scopes or set(scopes) != {"read:user"}:
        return {"ok": False, "error": "non_identity_scope_rejected"}, 400
    scopes = list(scopes)
    now = time.time()
    limb.set_session(GithubSession(
        access_token=token,
        scopes=scopes,
        obtained_at=now,
        expires_at=now + float(body.get("expires_in", 365 * 24 * 3600)),
    ))
    state = fetch_identity(limb._session)
    limb.mark_state(state, now=now)
    tile = limb.health(now=now)
    tile["ok"] = state == STATE_AVAILABLE
    return tile, (200 if state == STATE_AVAILABLE else 502)
