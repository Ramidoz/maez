"""Phase 3 shim — delegates to core.cognition.audit_log."""
import sys
from core.cognition import audit_log as _real
sys.modules[__name__] = _real
