"""Phase 3 shim — delegates to core.memory.ambient_format."""
import sys
from core.memory import ambient_format as _real
sys.modules[__name__] = _real
