# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.safety.injection_patterns.

The real module lives at core/safety/injection_patterns.py. New code
should import from core.safety directly.
"""
import sys
from core.safety import injection_patterns as _real
sys.modules[__name__] = _real
