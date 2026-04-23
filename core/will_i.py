"""Phase 3 shim — delegates to core.evolution.will_i."""
import sys
from core.evolution import will_i as _real
sys.modules[__name__] = _real
