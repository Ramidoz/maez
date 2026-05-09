# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Cold activation configuration for recall projection.

Slice 4c.5c keeps projection activation disabled by default. The
positive env var avoids the double-negative operator trap:
activation is off unless the operator explicitly opts in later.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping


LOGGER_NAME = "maez.recall_activation"
MAEZ_PROJECTION_ACTIVATION_ENABLED = "MAEZ_PROJECTION_ACTIVATION_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def projection_activation_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return True only for explicit positive activation opt-in values."""

    env = os.environ if environ is None else environ
    raw = env.get(MAEZ_PROJECTION_ACTIVATION_ENABLED, "")
    return raw.strip().lower() in _TRUE_VALUES


def log_activation_startup_state(
    environ: Mapping[str, str] | None = None,
) -> None:
    """Log the cold kill-switch state once from process startup code."""

    enabled = projection_activation_enabled(environ)
    logger = logging.getLogger(LOGGER_NAME)
    if enabled:
        logger.info(
            "event=recall_activation_startup activation_state=enabled level=info env_var=%s",
            MAEZ_PROJECTION_ACTIVATION_ENABLED,
        )
        return

    logger.warning(
        "event=recall_activation_startup activation_state=disabled level=warning env_var=%s",
        MAEZ_PROJECTION_ACTIVATION_ENABLED,
    )
