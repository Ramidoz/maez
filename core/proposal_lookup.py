"""Phase 3 shim — delegates to core.decision.proposal_lookup."""
import sys
from core.decision import proposal_lookup as _real
sys.modules[__name__] = _real
