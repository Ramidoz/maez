"""Phase 3 shim — delegates to core.infra.builder_mode_perception."""
import sys
from core.infra import builder_mode_perception as _real
sys.modules[__name__] = _real
