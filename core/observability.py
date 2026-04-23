"""Phase 3 shim — delegates to core.cognition.observability."""
import sys
from core.cognition import observability as _real
sys.modules[__name__] = _real
