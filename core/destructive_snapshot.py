"""Phase 3 shim — delegates to core.actions.destructive_snapshot."""
import sys
from core.actions import destructive_snapshot as _real
sys.modules[__name__] = _real
