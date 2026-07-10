# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Shared fail-closed pause/curtain gate for every desktop screen sense."""

from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_PAUSE_FILE = os.path.expanduser("~/.config/maez/screen_perception.paused")
DEFAULT_CURTAIN_FILE = os.path.expanduser("~/.config/maez/screen_perception.curtain")


def screen_privacy_state(env: Mapping[str, str] | None = None) -> str | None:
    """Return the first active owner privacy gate, without opening any sense."""
    values = os.environ if env is None else env
    pause_file = values.get("MAEZ_SCREEN_PAUSE_FILE", DEFAULT_PAUSE_FILE)
    curtain_file = values.get("MAEZ_SCREEN_CURTAIN_FILE", DEFAULT_CURTAIN_FILE)
    if os.path.exists(os.path.expanduser(pause_file)):
        return "paused"
    if os.path.exists(os.path.expanduser(curtain_file)):
        return "curtain_drawn"
    return None
