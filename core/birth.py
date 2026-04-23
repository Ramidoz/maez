"""Phase 3 shim — delegates to core.memory.birth."""
import sys
from core.memory import birth as _real
sys.modules[__name__] = _real
