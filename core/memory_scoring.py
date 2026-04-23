"""Phase 3 shim — delegates to core.memory.memory_scoring."""
import sys
from core.memory import memory_scoring as _real
sys.modules[__name__] = _real
