"""Phase 3 shim — delegates to core.learning.error_classifier."""
import sys
from core.learning import error_classifier as _real
sys.modules[__name__] = _real
