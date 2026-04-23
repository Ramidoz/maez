"""Phase 3 shim — delegates to core.routing.context_compressor."""
import sys
from core.routing import context_compressor as _real
sys.modules[__name__] = _real
