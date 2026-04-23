"""Phase 3 shim — delegates to core.cognition.audit."""
import sys
from core.cognition import audit as _real
sys.modules[__name__] = _real
