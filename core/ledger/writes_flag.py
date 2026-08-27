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


def ledger_commits_paused() -> bool:
    """True when the owner has paused COMMITS (custody continues).

    MAEZ_LEDGER_COMMITS_PAUSED — ninth council round (2026-08-26),
    owner-ruled pause-with-custody. A NEW flag, never a reinterpretation
    of MAEZ_LEDGER_WRITES (round-5 binding): writes-off still wins and
    means no recording INCLUDING custody.

    Polarity (2-1, Codex+Claude over Grok): absent/false-like → NOT
    paused (a forgotten drop-in must never silently pause life). An
    unrecognized non-empty value → PAUSED, loudly: junk must never
    authorize an irreversible commit — pause is reversible, commits are
    not. The inverse of this module's writes-flag junk rule, for the
    same reason: fail away from the irreversible act.
    """
    raw = os.environ.get("MAEZ_LEDGER_COMMITS_PAUSED", "")
    stripped = raw.strip().lower()
    if stripped in _TRUE_VALUES:
        return True
    if stripped in _FALSE_VALUES:
        return False
    _LOGGER.warning(
        "MAEZ_LEDGER_COMMITS_PAUSED has unrecognized value %r; failing "
        "CLOSED to paused (junk never authorizes a commit). Use '1' to "
        "pause or unset to resume.", raw)
    return True


def commits_paused_flag_invalid() -> bool:
    """True when the pause flag holds an unrecognized value (which fails
    closed to paused). Surfaced so a typo is distinguishable from an
    intentional pause on the cockpit (Codex validation #7)."""
    raw = os.environ.get("MAEZ_LEDGER_COMMITS_PAUSED", "")
    stripped = raw.strip().lower()
    return bool(stripped) and stripped not in _TRUE_VALUES | _FALSE_VALUES
