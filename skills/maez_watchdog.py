"""
maez_watchdog.py — Independent watchdog for maez.service.
Sends Telegram alerts when Maez goes down or comes back up.
Works completely independently of Maez.
"""

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests
import sys

sys.path.insert(0, str(Path("/home/rohit/maez")))
from skills.dev_notifier import send_dev

# --- Config ---
LOG_PATH = Path("/home/rohit/maez/logs/maez_watchdog.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = 60  # seconds
SSH_HOST = "rohit@[private-ip]"

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
    """Check if maez.service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "maez.service"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def get_cycle_count() -> str:
    """Try to get Maez's cycle count from health endpoint."""
    try:
        resp = requests.get("http://localhost:11435/health", timeout=3)
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
                msg = (
                    f"\u26a0\ufe0f Maez went offline at {went_down_at.strftime('%H:%M:%S')}.\n"
                    f"SSH: ssh {SSH_HOST}"
                )
                logger.warning(msg)
                send_dev(msg)

            elif not was_active and active:
                # Maez just came back
                cycles = get_cycle_count()
                downtime = ""
                if went_down_at:
                    mins = (datetime.now() - went_down_at).total_seconds() / 60
                    downtime = f" Downtime: {mins:.1f} minutes."
                msg = f"\u2705 Maez is back online. {cycles} cycles running.{downtime}"
                logger.info(msg)
                send_dev(msg)
                went_down_at = None

            was_active = active

        except Exception as e:
            logger.error("Watchdog error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
