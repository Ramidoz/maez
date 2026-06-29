# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Neutral owner for the shared maez.cognition log handler."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def _default_log_path() -> Path:
    try:
        from core.paths import logs_dir as _logs_dir

        return _logs_dir() / "cognition.log"
    except Exception:
        return Path(__file__).resolve().parents[2] / "logs" / "cognition.log"


def ensure_cognition_log_handler() -> logging.Logger:
    """Attach the rotating cognition log handler without importing a scorer."""

    logger = logging.getLogger("maez.cognition")
    log_path = _default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(log_path.resolve())
    for handler in logger.handlers:
        if (
            isinstance(handler, logging.handlers.RotatingFileHandler)
            and getattr(handler, "baseFilename", None) == resolved
        ):
            logger.setLevel(logging.INFO)
            return logger
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
