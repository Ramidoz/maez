"""Phase 3 shim — delegates to core.actions.action_engine."""
import sys
from core.actions import action_engine as _real
sys.modules[__name__] = _real
