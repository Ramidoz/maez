"""Phase 3 shim — delegates to core.brain.conversation_controller."""
import sys
from core.brain import conversation_controller as _real
sys.modules[__name__] = _real
