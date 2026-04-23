"""Phase 3 shim — delegates to core.actions.tool_loop."""
import sys
from core.actions import tool_loop as _real
sys.modules[__name__] = _real
