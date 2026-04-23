"""Phase 3 shim — delegates to core.evolution.wonderings."""
import sys
from core.evolution import wonderings as _real
sys.modules[__name__] = _real
