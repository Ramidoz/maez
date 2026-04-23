"""Phase 3 shim — delegates to core.infra.fast_reply_audit."""
import sys
from core.infra import fast_reply_audit as _real
sys.modules[__name__] = _real
