# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — re-exports core.infra.capability_manual.

The module is a directory package (not a flat .py shim) so
``python -m core.capability_manual validate`` works through the
sibling __main__.py. Both ``from core.capability_manual import X``
and ``from core.infra.capability_manual import X`` resolve to the
same names.
"""
from core.infra.capability_manual import (
    CapabilityCovenant,
    CapabilityEntry,
    CapabilityManualError,
    CapabilityValidationIssue,
    ManualLoadResult,
    find_by_id,
    load_capability,
    load_manual,
    validate_capability,
)

__all__ = [
    "CapabilityCovenant",
    "CapabilityEntry",
    "CapabilityManualError",
    "CapabilityValidationIssue",
    "ManualLoadResult",
    "find_by_id",
    "load_capability",
    "load_manual",
    "validate_capability",
]
