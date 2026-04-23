"""Phase 3 shim — delegates to core.infra.fast_conversation_log."""
import sys
from core.infra import fast_conversation_log as _real
sys.modules[__name__] = _real
