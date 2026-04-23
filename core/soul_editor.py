"""Phase 3 shim — delegates to core.evolution.soul_editor."""
import sys
from core.evolution import soul_editor as _real
sys.modules[__name__] = _real
