"""Phase 3 shim — delegates to core.routing.fast_backend_router."""
import sys
from core.routing import fast_backend_router as _real
sys.modules[__name__] = _real
