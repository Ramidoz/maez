"""Phase 3 shim — delegates to core.routing.fast_backend_local."""
import sys
from core.routing import fast_backend_local as _real
sys.modules[__name__] = _real
