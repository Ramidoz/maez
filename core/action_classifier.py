"""Phase 3 shim — delegates to core.actions.action_classifier."""
import sys
from core.actions import action_classifier as _real
sys.modules[__name__] = _real
