"""Phase 3 shim — delegates to core.infra.private_thoughts."""
import sys
from core.infra import private_thoughts as _real
sys.modules[__name__] = _real
