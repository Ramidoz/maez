"""Phase 3 shim — delegates to core.self_dev.workshop."""
import sys
from core.self_dev import workshop as _real
sys.modules[__name__] = _real
