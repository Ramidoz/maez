"""Phase 3 shim — delegates to core.infra.public_user_shaping."""
import sys
from core.infra import public_user_shaping as _real
sys.modules[__name__] = _real
