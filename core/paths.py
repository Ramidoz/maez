"""Phase 3 shim — delegates to core.infra.paths."""
import sys
from core.infra import paths as _real
sys.modules[__name__] = _real
