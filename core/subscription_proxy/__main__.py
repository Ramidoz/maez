# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Run the subscription proxy:
    python -m core.subscription_proxy

Environment:
    MAEZ_SUBSCRIPTION_PROXY_PORT   127.0.0.1 bind port (default 11438)
    MAEZ_CLAUDE_BIN                path to `claude` (default /home/rohit/.local/bin/claude)
    OPENROUTER_API_KEY             needed to use the openrouter adapter
    MAEZ_<ADAPTER>_HOURLY_CAP      per-adapter hourly call cap
    MAEZ_<ADAPTER>_DAILY_CAP       per-adapter daily call cap
"""
import logging
import os

import uvicorn

from core.infra.secrets import (
    SECRET_NAMES,
    load_ordinary_config_for_process,
    load_secrets_for_process,
)

load_ordinary_config_for_process()
load_secrets_for_process(
    required=set(),
    optional=set(SECRET_NAMES),
    populate_environ=True,
)

from core.subscription_proxy.server import app


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    port = int(os.environ.get("MAEZ_SUBSCRIPTION_PROXY_PORT", "11438"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
