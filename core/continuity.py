"""Phase 3 shim — delegates to core.memory.continuity."""
import sys
from core.memory import continuity as _real
sys.modules[__name__] = _real
