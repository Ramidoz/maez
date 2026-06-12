"""The one flag for Search-as-a-Sense v0.1 (spec 2026-06-12).

Default OFF. When unset, every touched seam behaves byte-identically to
pre-v0.1. Reverting live = unset the env var + restart maez.service.
"""
from __future__ import annotations

import os


def sense_enabled() -> bool:
    return bool(os.environ.get("MAEZ_SEARCH_AS_SENSE_ENABLED"))
