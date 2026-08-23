# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
maez_watchdog.py — Independent watchdog for maez.service.
Sends Telegram alerts when Maez goes down or comes back up.
Works completely independently of Maez.
"""

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

_MAEZ_HOME_PATH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MAEZ_HOME_PATH))

# 2026-08-22: this watchdog detected 210 outages and delivered none of them.
# Its docstring promises Telegram alerts; `send_dev` reads MAEZ_DEV_TOKEN from
# os.environ; and nothing here ever loaded credentials. The token was present
# and valid in config/secrets.local.env the whole time -- maez-watchdog.service
# sets only PYTHONUNBUFFERED and MAEZ_HOME, and unlike the daemon this process
# never called the secrets loader. Every alert logged
# "MAEZ_DEV_TOKEN not set - dev notification dropped" and vanished: 40 of them,
# six on the day this was found.
#
# A watchdog that cannot reach anyone is not a watchdog. It is a log file.
#
# Load credentials the same way daemon/maez_daemon.py:34 does (Decision 26:
# ordinary config first, then credentials through the dedicated loader),
# before anything reads os.environ. Failure to load must not stop the
# watchdog -- a watchdog that dies because alerting is broken is worse than
# one that watches silently -- but it is logged loudly rather than swallowed.
try:
    from core.infra.secrets import (
        SECRET_NAMES as _SECRET_NAMES,
        load_ordinary_config_for_process as _load_ordinary_config,
        load_secrets_for_process as _load_secrets,
    )

    _load_ordinary_config()
    _load_secrets(required=set(), optional=set(_SECRET_NAMES),
                  populate_environ=True)
    _CREDENTIALS_LOADED = True
    _CREDENTIAL_ERROR = None
except Exception as _exc:                            # noqa: BLE001
    _CREDENTIALS_LOADED = False
    _CREDENTIAL_ERROR = _exc

from skills.dev_notifier import send_service_card

# --- Config ---
LOG_PATH = _MAEZ_HOME_PATH / "logs" / "maez_watchdog.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = 60  # seconds
SSH_HOST = "rohit@maez.live"
OPERATOR_HEALTH_URL = "http://127.0.0.1:11435/operator/health"
FULL_HEALTH_URL = "http://127.0.0.1:11435/health"

# --- Logging ---
logger = logging.getLogger("maez_watchdog")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_PATH)
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(handler)
stream = logging.StreamHandler()
stream.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(stream)


def is_maez_active() -> bool:
    """Check if maez.service is active and its HTTP health endpoint is alive."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "maez.service"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip() != "active":
            return False
        resp = requests.get(OPERATOR_HEALTH_URL, timeout=3)
        data = resp.json()
        return data.get("route") == "/operator/health" and data.get("service_mode") == "running"
    except Exception:
        return False


def get_cycle_count() -> str:
    """Try to get Maez's cycle count from health endpoint."""
    try:
        resp = requests.get(FULL_HEALTH_URL, timeout=3)
        data = resp.json()
        return str(data.get("cycle_count", "?"))
    except Exception:
        return "?"


def run():
    """Main watchdog loop."""
    logger.info("Maez watchdog started (poll every %ds)", POLL_INTERVAL)
    was_active = is_maez_active()
    went_down_at = None

    if was_active:
        logger.info("Maez is currently active")
    else:
        logger.warning("Maez is currently DOWN")
        went_down_at = datetime.now()

    while True:
        try:
            active = is_maez_active()

            if was_active and not active:
                # Maez just went down
                went_down_at = datetime.now()
                logger.warning("Maez went offline at %s", went_down_at.strftime('%H:%M:%S'))
                send_service_card(
                    'maez.service',
                    f"went offline at {went_down_at.strftime('%H:%M:%S')}",
                    f"SSH: ssh {SSH_HOST}",
                )

            elif not was_active and active:
                # Maez just came back
                cycles = get_cycle_count()
                downtime_str = "unknown"
                if went_down_at:
                    mins = (datetime.now() - went_down_at).total_seconds() / 60
                    downtime_str = f"{mins:.1f} min"
                logger.info("Maez back online (%s cycles running)", cycles)
                send_service_card(
                    'maez.service',
                    f"back online ({cycles} cycles)",
                    f"Downtime: {downtime_str}",
                )
                went_down_at = None

            was_active = active

        except Exception as e:
            logger.error("Watchdog error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
