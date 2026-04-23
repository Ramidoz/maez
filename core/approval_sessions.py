"""Phase 3 shim — delegates to core.decision.approval_sessions."""
import sys
from core.decision import approval_sessions as _real
sys.modules[__name__] = _real
