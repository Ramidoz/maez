"""Phase 3 shim — delegates to core.evolution.soul_invariants."""
import sys
from core.evolution import soul_invariants as _real
sys.modules[__name__] = _real
