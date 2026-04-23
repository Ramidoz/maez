"""Phase 3 shim — delegates to core.self_dev.persistence."""
import sys
from core.self_dev import persistence as _real
sys.modules[__name__] = _real
