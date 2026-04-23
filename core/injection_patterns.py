"""Phase 3 shim — delegates to core.safety.injection_patterns.

The real module lives at core/safety/injection_patterns.py. New code
should import from core.safety directly.
"""
import sys
from core.safety import injection_patterns as _real
sys.modules[__name__] = _real
