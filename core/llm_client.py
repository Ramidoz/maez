# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.routing.llm_client."""
import sys
from core.routing import llm_client as _real
sys.modules[__name__] = _real
