"""Phase 3 shim — delegates to core.decision.decision_pipeline."""
import sys
from core.decision import decision_pipeline as _real
sys.modules[__name__] = _real
