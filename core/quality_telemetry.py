"""Phase 3 shim — delegates to core.cognition.quality_telemetry."""
import sys
from core.cognition import quality_telemetry as _real
sys.modules[__name__] = _real
