"""Phase 3 shim — delegates to core.memory.identity."""
import sys
from core.memory import identity as _real
sys.modules[__name__] = _real
