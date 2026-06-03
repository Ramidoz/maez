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
