"""Phase 3 shim — delegates to core.self_dev.scheduler."""
import sys
from core.self_dev import scheduler as _real
sys.modules[__name__] = _real
