"""Phase 3 shim — delegates to core.evolution.soul_loader."""
import sys
from core.evolution import soul_loader as _real
sys.modules[__name__] = _real
