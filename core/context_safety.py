# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Phase 3 shim — delegates to core.safety.context_safety.

The real module lives at core/safety/context_safety.py. This shim is
kept so pre-Phase-3 imports (`from core.context_safety import ...`,
`patch("core.context_safety.X")`, etc.) continue to resolve to the
exact same object. New code should import from core.safety directly.
"""
import sys
from core.safety import context_safety as _real
sys.modules[__name__] = _real
