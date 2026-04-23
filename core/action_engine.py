# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.actions.action_engine."""
import sys
from core.actions import action_engine as _real
sys.modules[__name__] = _real
