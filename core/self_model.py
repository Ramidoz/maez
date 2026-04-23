"""Phase 3 shim — delegates to core.infra.self_model."""
import sys
from core.infra import self_model as _real
sys.modules[__name__] = _real
