"""Phase 3 shim — delegates to core.brain.brain_loop."""
import sys
from core.brain import brain_loop as _real
sys.modules[__name__] = _real
