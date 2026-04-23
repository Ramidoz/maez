"""Phase 3 shim — delegates to core.routing.llm_client."""
import sys
from core.routing import llm_client as _real
sys.modules[__name__] = _real
