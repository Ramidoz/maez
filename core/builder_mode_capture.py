"""Phase 3 shim — delegates to core.infra.builder_mode_capture."""
import sys
from core.infra import builder_mode_capture as _real
sys.modules[__name__] = _real
