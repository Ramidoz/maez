# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — re-exports core.infra.capability_proposal.

Directory package (not a flat .py shim) so
``python -m core.capability_proposal '<query>'`` works through the
sibling ``__main__.py``.
"""
from core.infra.capability_proposal import (
    CapabilityProposal,
    generate_proposal,
    generate_proposals,
)

__all__ = [
    "CapabilityProposal",
    "generate_proposal",
    "generate_proposals",
]
