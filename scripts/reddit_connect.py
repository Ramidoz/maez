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
    # Load through Maez's credential system so we read the SAME values the daemon
    # has: MAEZ_REDDIT_HANDOFF_TOKEN is a secret (lives in config/secrets.local.env,
    # allowlisted in core.infra.secrets.SECRET_NAMES); MAEZ_REDDIT_CLIENT_ID is
    # ordinary config (config/.env). A bare os.environ read would miss both,
    # because the secret loader purges unmanaged secret-looking names.
    from core.infra.secrets import (
        load_ordinary_config_for_process,
        load_secrets_for_process,
    )
    load_ordinary_config_for_process()                       # client_id from config/.env
    load_secrets_for_process(                                 # handoff token from secrets.local.env
        required={"MAEZ_REDDIT_HANDOFF_TOKEN"}, optional=set(), populate_environ=True,
    )
    cid = os.environ.get("MAEZ_REDDIT_CLIENT_ID", "").strip()
    handoff = os.environ.get("MAEZ_REDDIT_HANDOFF_TOKEN", "").strip()
    if not cid:
        sys.exit("MAEZ_REDDIT_CLIENT_ID not set in config/.env (create an installed app at reddit.com/prefs/apps).")
    if not handoff:
        sys.exit("MAEZ_REDDIT_HANDOFF_TOKEN not set in config/secrets.local.env (must match the daemon's value).")
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
