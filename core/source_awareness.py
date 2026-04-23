"""Phase 3 shim — delegates to core.memory.source_awareness."""
import sys
from core.memory import source_awareness as _real
sys.modules[__name__] = _real
