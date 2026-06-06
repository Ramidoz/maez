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
