"""Phase 3 shim — delegates to core.learning.consequence_memory."""
import sys
from core.learning import consequence_memory as _real
sys.modules[__name__] = _real
