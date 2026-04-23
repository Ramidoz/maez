"""Phase 3 shim — delegates to core.routing.model_config."""
import sys
from core.routing import model_config as _real
sys.modules[__name__] = _real
