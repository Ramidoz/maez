"""Phase 3 shim — delegates to core.memory.ambient."""
import sys
from core.memory import ambient as _real
sys.modules[__name__] = _real
