# scripts/github_ingest.py
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""One-shot GitHub v1 ingest trigger (owner-run).

Prereq:
  config/secrets.local.env: MAEZ_GITHUB_INGEST_TOKEN=<shared secret>

The daemon must already be in MAEZ_GITHUB_MODE=v1 and the GitHub limb must be
available via scripts/github_connect.py. This script sends no provider data and
prints only the daemon's content-free ingest result.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import requests  # noqa: E402

from core.information_limb import github_v1  # noqa: E402


DAEMON_INGEST_URL = "http://127.0.0.1:11435/internal/limb/github/ingest"
_CONTENT_FREE_RESULT_KEYS = (
    "ok",
    "ingest_record_id",
    "fetch_batch_id",
    "staged",
    "admitted",
    "state",
    "resumed",
    "error",
)


def _read_ingest_token() -> str:
    from core.infra.secrets import load_secrets_for_process

    load_secrets_for_process(
        required=set(),
        optional={github_v1.GITHUB_INGEST_TOKEN_ENV},
        populate_environ=True,
    )
    token = os.environ.get(github_v1.GITHUB_INGEST_TOKEN_ENV, "").strip()
    if not token:
        sys.exit(
            "MAEZ_GITHUB_INGEST_TOKEN not set in config/secrets.local.env "
            "(must match the daemon's value)."
        )
    return token


def main() -> int:
    ingest_token = _read_ingest_token()
    response = requests.post(
        DAEMON_INGEST_URL,
        headers={github_v1.GITHUB_INGEST_HEADER: ingest_token},
        json={},
        timeout=15,
    )
    result = _content_free_result(response.json())
    print(f"daemon github ingest -> HTTP {response.status_code}: {result}")
    return 0 if response.status_code == 200 else 1


def _content_free_result(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid_daemon_response"}
    return {key: payload[key] for key in _CONTENT_FREE_RESULT_KEYS if key in payload}


if __name__ == "__main__":
    raise SystemExit(main())
