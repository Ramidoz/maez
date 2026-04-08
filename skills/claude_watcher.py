"""
claude_watcher.py — Monitors Claude Code and notifies via Maez Dev bot.
Notifications only. Use HQSSH for terminal access and input.
"""

import fcntl
import json
import logging
import os
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path("/home/rohit/maez")))
from skills.dev_notifier import send_dev

# --- Config ---
LOG_PATH = Path("/home/rohit/maez/logs/claude_watcher.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = 15
LONG_RUNNING_THRESHOLD = 1800  # 30 minutes
LOCK_FILE = '/tmp/maez_claude_watcher.lock'
CACHE_FILE = '/tmp/maez_watcher_cache.json'
DEDUP_COOLDOWN = 300  # seconds

# --- Logging ---
logger = logging.getLogger("claude_watcher")
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(LOG_PATH)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_fh)
_sh = logging.StreamHandler()
_sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_sh)


# --- PID lock ---

def acquire_lock():
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except IOError:
        print("Another watcher instance is running. Exiting.")
        sys.exit(0)


# --- Deduplication ---

def _load_cache() -> dict:
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)


def _should_notify(event: str) -> bool:
    cache = _load_cache()
    now = time.time()
    if now - cache.get(event, 0) > DEDUP_COOLDOWN:
        cache[event] = now
        _save_cache(cache)
        return True
    return False


# --- Process detection ---

def find_claude_process() -> psutil.Process | None:
    """Find the main Claude Code process, ignoring this watcher."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            name = proc.info['name'] or ""
            if 'claude' in name.lower() or 'claude' in cmdline.lower():
                if 'claude_watcher' in cmdline:
                    continue
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


# --- Main loop ---

def run():
    running = False
    start_time: float | None = None
    long_run_notified = False
    idle_streak = 0

    logger.info("Claude watcher started (poll every %ds)", POLL_INTERVAL)

    while True:
        try:
            proc = find_claude_process()

            if proc and not running:
                # Just started
                running = True
                start_time = proc.create_time()
                long_run_notified = False
                idle_streak = 0
                if _should_notify('started'):
                    from datetime import datetime
                    ts = datetime.fromtimestamp(start_time).strftime('%H:%M:%S')
                    msg = f"\U0001f680 Claude Code started at {ts}"
                    logger.info(msg)
                    send_dev(msg)

            elif not proc and running:
                # Just exited
                running = False
                duration_s = time.time() - (start_time or time.time())
                mins = duration_s / 60
                long_run_notified = False
                idle_streak = 0
                if _should_notify('finished'):
                    if mins < 1:
                        dur = f"{duration_s:.0f}s"
                    else:
                        dur = f"{mins:.1f} min"
                    msg = f"\u2705 Claude Code finished after {dur}."
                    logger.info(msg)
                    send_dev(msg)
                start_time = None

            elif proc and running:
                # Still running — check duration and idle
                duration_s = time.time() - (start_time or time.time())

                # Long running check
                if duration_s > LONG_RUNNING_THRESHOLD and not long_run_notified:
                    long_run_notified = True
                    if _should_notify('long_running'):
                        mins = duration_s / 60
                        msg = f"\u23f1 Claude Code has been running for {mins:.0f} minutes."
                        logger.info(msg)
                        send_dev(msg)

                # Idle check (CPU < 0.5% for 2+ minutes while long-running)
                try:
                    cpu = proc.cpu_percent(interval=0)
                    if cpu < 0.5:
                        idle_streak += POLL_INTERVAL
                    else:
                        idle_streak = 0

                    if (idle_streak >= 120
                            and duration_s > LONG_RUNNING_THRESHOLD
                            and _should_notify('idle')):
                        msg = ("\u23f8 Claude Code may be waiting for input. "
                               "Open HQSSH to check.")
                        logger.info(msg)
                        send_dev(msg)
                        idle_streak = 0  # reset so it doesn't spam
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        except Exception as e:
            logger.error("Watcher error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path("/home/rohit/maez/config/.env"))

    _lock_fd = acquire_lock()
    run()
