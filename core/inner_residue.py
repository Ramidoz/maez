# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.learning.inner_residue."""
import sys
from core.learning import inner_residue as _real
sys.modules[__name__] = _real
