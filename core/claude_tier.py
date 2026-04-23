"""Phase 3 shim — delegates to core.routing.claude_tier."""
import sys
from core.routing import claude_tier as _real
sys.modules[__name__] = _real
