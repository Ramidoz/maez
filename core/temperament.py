"""Phase 3 shim — delegates to core.evolution.temperament."""
import sys
from core.evolution import temperament as _real
sys.modules[__name__] = _real
