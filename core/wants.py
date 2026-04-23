"""Phase 3 shim — delegates to core.evolution.wants."""
import sys
from core.evolution import wants as _real
sys.modules[__name__] = _real
