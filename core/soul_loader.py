# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.evolution.soul_loader."""
import sys
from core.evolution import soul_loader as _real
sys.modules[__name__] = _real
