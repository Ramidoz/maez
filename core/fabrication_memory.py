"""Phase 3 shim — delegates to core.learning.fabrication_memory."""
import sys
from core.learning import fabrication_memory as _real
sys.modules[__name__] = _real
