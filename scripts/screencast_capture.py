#!/usr/bin/env python3
"""Maez ScreenCast capture helper.

This runs on the system Python when it talks to the desktop portal, because
the Maez venv lacks gi/Gst/Gio. Those imports stay lazy so unit tests can
exercise the non-live rails in the venv.
"""

from __future__ import annotations

import json
import os
import sys

TOKEN_PATH = os.path.expanduser("~/.config/maez/screencast_restore_token")
CURTAIN_PATH = os.path.expanduser("~/.config/maez/screen_perception.curtain")
TEMP_PREFIX = "maez-screencast-"


def _result(
    status: str,
    temp_path: str | None = None,
    bytes_: int = 0,
    duration_ms: int = 0,
    error_class: str = "",
) -> dict:
    """Build the only stdout contract this helper may emit."""
    return {
        "status": status,
        "temp_path": temp_path,
        "bytes": int(bytes_),
        "duration_ms": int(duration_ms),
        "error_class": error_class,
    }


def _emit(result: dict) -> None:
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


def _curtain_drawn() -> bool:
    return os.path.exists(CURTAIN_PATH)


def _save_token(token: str) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token)
            f.write("\n")
    finally:
        os.chmod(TOKEN_PATH, 0o600)


def _load_token() -> str | None:
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        return None
    return token or None


def capture() -> dict:
    """Capture one frame, unless the privacy curtain is drawn."""
    if _curtain_drawn():
        return _result(status="curtain_drawn")
    return _capture_live()


def _capture_live() -> dict:
    return _result(status="capture_failed", error_class="gst")
