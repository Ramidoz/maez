"""The one flag for Search-as-a-Sense v0.1 (spec 2026-06-12).

Default OFF. When unset, every touched seam behaves byte-identically to
pre-v0.1. Reverting live = unset the env var + restart maez.service.
"""
from __future__ import annotations

from core.infra.env_flags import strict_env_flag


def sense_enabled() -> bool:
    return strict_env_flag("MAEZ_SEARCH_AS_SENSE_ENABLED")


def page_read_enabled() -> bool:
    """Page-Read Sense v0 (spec 2026-06-12). Own flag, own witness, own revert."""
    return strict_env_flag("MAEZ_PAGE_READ_ENABLED")
