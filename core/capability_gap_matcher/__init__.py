# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — re-exports core.infra.capability_gap_matcher.

Directory package (not a flat .py shim) so
``python -m core.capability_gap_matcher "<query>"`` works through
the sibling ``__main__.py``.
"""
from core.infra.capability_gap_matcher import (
    CapabilityMatch,
    _get_default_manual,
    clear_cache,
    match_gap,
    rank_capabilities,
)

__all__ = [
    "CapabilityMatch",
    "_get_default_manual",
    "clear_cache",
    "match_gap",
    "rank_capabilities",
]
