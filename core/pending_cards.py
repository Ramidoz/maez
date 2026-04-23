"""Phase 3 shim — delegates to core.decision.pending_cards."""
import sys
from core.decision import pending_cards as _real
sys.modules[__name__] = _real
