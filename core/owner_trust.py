"""Phase 3 shim — delegates to core.safety.owner_trust.

The real module lives at core/safety/owner_trust.py. New code should
import from core.safety directly.
"""
import sys
from core.safety import owner_trust as _real
sys.modules[__name__] = _real
