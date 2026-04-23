"""Phase 3 shim — delegates to core.memory.perception_envelope."""
import sys
from core.memory import perception_envelope as _real
sys.modules[__name__] = _real
