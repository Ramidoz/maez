"""Phase 3 shim — delegates to core.evolution.dream_state."""
import sys
from core.evolution import dream_state as _real
sys.modules[__name__] = _real
