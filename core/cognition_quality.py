"""Phase 3 shim — delegates to core.cognition.cognition_quality."""
import sys
from core.cognition import cognition_quality as _real
sys.modules[__name__] = _real
