# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Single source of truth for "is the ledger allowed to write?".

The switch is the env flag MAEZ_LEDGER_WRITES. This is intentionally a leaf
module (imports only os + logging) so writer, reconcile, and model_reply
persistence can share ONE predicate without a circular import — and so the
parse (including the unrecognized-value warning) does not fork.
"""

from __future__ import annotations

import logging
import os

_LOGGER = logging.getLogger("core.ledger.writes_flag")

_TRUE_VALUES = {"1", "true"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def ledger_writes_enabled() -> bool:
    """True only when MAEZ_LEDGER_WRITES is an explicit true value.

    Unset / falsy → False (default-off). An unrecognized non-empty value →
    False, with a single WARNING (do not silently treat junk as enabled).
    """
    raw = os.environ.get("MAEZ_LEDGER_WRITES", "")
    stripped = raw.strip().lower()
    if stripped in _TRUE_VALUES:
        return True
    if stripped in _FALSE_VALUES:
        return False
    _LOGGER.warning(
        "MAEZ_LEDGER_WRITES has unrecognized value %r; treating as disabled. "
        "Use '1' or 'true' to enable.",
        raw,
    )
    return False
