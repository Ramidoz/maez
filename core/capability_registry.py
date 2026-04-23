"""Phase 3 shim — delegates to core.infra.capability_registry."""
import sys
from core.infra import capability_registry as _real
sys.modules[__name__] = _real
