# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.infra.capability_acquisition_queue."""
import sys
from core.infra import capability_acquisition_queue as _real
sys.modules[__name__] = _real
