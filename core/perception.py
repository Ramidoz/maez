"""Phase 3 shim — delegates to core.memory.perception."""
import sys
from core.memory import perception as _real
sys.modules[__name__] = _real
