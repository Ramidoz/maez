# scripts/github_connect.py
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""One-shot GitHub connect ceremony (owner-run, OAuth device flow).

No client secret, no loopback listener: request a device code, the owner enters
a short user code at github.com/login/device, we poll for the token and hand it
to the running daemon over the loopback + shared-secret handoff. The token lives
only in this process's memory and the daemon's — never on disk.

Prereq: a GitHub OAuth App (github.com/settings/developers -> New OAuth App) with
"Enable Device Flow" checked; copy its Client ID. Then set:
  config/.env:                MAEZ_GITHUB_CLIENT_ID=<client_id>   (not a secret)
  config/secrets.local.env:   MAEZ_GITHUB_HANDOFF_TOKEN=<shared secret, daemon's value>

Run:  .venv/bin/python scripts/github_connect.py
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import requests  # noqa: E402

from core.information_limb import github_limb  # noqa: E402

DAEMON_HANDOFF_URL = "http://127.0.0.1:11435/internal/limb/github/session"


def _read_env() -> tuple[str, str]:
    from core.infra.secrets import (
        load_ordinary_config_for_process,
        load_secrets_for_process,
    )
    load_ordinary_config_for_process()                       # client_id from config/.env
    load_secrets_for_process(                                 # handoff token from secrets.local.env
        required=set(), optional={"MAEZ_GITHUB_HANDOFF_TOKEN"}, populate_environ=True,
    )
    cid = os.environ.get("MAEZ_GITHUB_CLIENT_ID", "").strip()
    handoff = os.environ.get("MAEZ_GITHUB_HANDOFF_TOKEN", "").strip()
    if not cid:
        sys.exit("MAEZ_GITHUB_CLIENT_ID not set in config/.env (create an OAuth App + enable device flow at github.com/settings/developers).")
    if not handoff:
        sys.exit("MAEZ_GITHUB_HANDOFF_TOKEN not set in config/secrets.local.env (must match the daemon's value).")
    return cid, handoff


def main() -> int:
    client_id, handoff = _read_env()
    grant = github_limb.request_device_code(client_id=client_id)
    print("\n  Open this page and enter the code:")
    print(f"    {grant.verification_uri}")
    print(f"    code: {grant.user_code}\n")
    webbrowser.open(grant.verification_uri)
    print("Waiting for you to authorize in the browser ...")
    session = github_limb.poll_for_token(client_id=client_id, grant=grant)
    resp = requests.post(
        DAEMON_HANDOFF_URL,
        headers={github_limb.GITHUB_HANDOFF_HEADER: handoff},
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
