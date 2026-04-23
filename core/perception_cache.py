"""Phase 3 shim — delegates to core.memory.perception_cache."""
import sys
from core.memory import perception_cache as _real
sys.modules[__name__] = _real
