# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""WARN-once helpers for owner-private model_reply persistence."""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger("core.ledger.model_reply_persistence")
_WARNED_KEYS: set[str] = set()


def warn_model_reply_persistence_once(
    key: str,
    message: str,
    *args: Any,
) -> None:
    """Emit a model_reply persistence warning once per process/key."""
    if key in _WARNED_KEYS:
        return
    _WARNED_KEYS.add(key)
    _LOGGER.warning(message, *args)


def warn_model_reply_persistence_skip(
    key: str,
    message: str,
    *args: Any,
) -> None:
    """WARN-once for call-site failures outside helper internals."""
    warn_model_reply_persistence_once(f"callsite:{key}", message, *args)
