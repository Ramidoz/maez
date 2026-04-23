"""Phase 3 shim — delegates to core.cognition.grounding_judge."""
import sys
from core.cognition import grounding_judge as _real
sys.modules[__name__] = _real
