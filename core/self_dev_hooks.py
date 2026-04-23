"""Phase 3 shim — delegates to core.self_dev.hooks."""
import sys
from core.self_dev import hooks as _real
sys.modules[__name__] = _real
